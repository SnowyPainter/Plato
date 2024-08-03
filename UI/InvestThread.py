from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSlot, pyqtSignal
from datetime import datetime, timedelta
import time

from Investment import watcher
from UI import Presets

class InvestThread(QThread):
    update_signal = pyqtSignal(str)
    
    def _invest_action(self):
        self.invester.append_current_data()
        text = self.invester.action(hour_divided_time=1 if self.interval == '1h' else 2)
        self.invest_logs.append(text)
        self.update_signal.emit(f"{self.invester.symbols} {datetime.now()}")
        
    def _update_news_bias(self, symbol, score):
        self.invester.news_bias[symbol] = score / 10

    def _forced_sell(self, sell_list, ratio, title=''):
        for sell in sell_list:
            symbol = sell['symbol']
            price = self.watcher.prices[symbol][-1]['pr']
            qty = self.invester.client.sell(symbol, price, ratio)
            text = ''
            text += f"{title} \n"
            text += f"{symbol} : {sell['p'] * 100 :.2f}, qty: {qty}\n"
            self.invest_logs.append(text)
            self.update_signal.emit(f"{title} {self.invester.symbols} {datetime.now()}")
    
    def __init__(self, news_reader, interval, process_name, invester, invest_logs, preset):
        super().__init__()
        self.news_reader = news_reader
        self.interval = interval
        self.process_name = process_name
        self.invester = invester
        self.watcher = watcher.Watcher(self.invester.client, self.invester.symbols)
        self.invest_logs = invest_logs
        self.watch_TP_flag = preset['enable_takeprofit']
        self.watch_SL_flag = preset['enable_stoploss']
        self.tp = preset['takeprofit']
        self.sl = preset['stoploss']
        self.preset = preset
        self._is_running = True
    
    @pyqtSlot(str)
    def invest_info_update_signal_update(self, body):
        value = body.split('&')[1]
        if "$MOA$" in body:
            self.invester.client.update_max_operate_amount(float(value))
            Presets.update_preset(self.preset, 'max_operate_amount', self.invester.client.max_operate_amount)
        if "$WATCH_TP$" in body:
            self.watch_TP_flag = True if value == "true" else False
            Presets.update_preset(self.preset, 'enable_takeprofit', self.watch_TP_flag)
        if "$WATCH_SL$" in body:
            self.watch_SL_flag = True if value == "true" else False
            Presets.update_preset(self.preset, 'enable_stoploss', self.watch_SL_flag)

    def run(self):
        start_time = datetime.strptime("09:00", "%H:%M").time()
        end_time = datetime.strptime("15:30", "%H:%M").time()
        interval_minutes = [0, 29]
        if self.interval == '1h':
            interval_minutes = [0]
        elif self.interval == '30m':
            interval_minutes = [0, 29]
        
        watch_TP_interval_minutes = list(range(0, 60, 1))
        watch_SL_interval_minutes = list(range(0, 60, 1))
        news_update_interval_minutes = list(range(0, 60, 10))
        
        now = datetime.now()
        if now > datetime.combine(now.date(), end_time):
            start_time = (datetime.combine(now, start_time) + timedelta(days=1)).time()

        while self._is_running:
            now = datetime.now()
            if start_time <= now.time() <= end_time:
                if now.minute in interval_minutes and now.second == 1:
                    self._invest_action()
                    time.sleep(1)
                
                if now.minute in watch_TP_interval_minutes and now.second == 1 and self.watch_TP_flag:
                    sell_list = self.watcher.watch_TP(self.tp)
                    self._forced_sell(sell_list, 0.5, 'Take Profit')
                
                if now.minute in watch_SL_interval_minutes and now.second == 1 and self.watch_SL_flag:
                    sell_list = self.watcher.watch_SL(self.sl)
                    self._forced_sell(sell_list, 1, 'Stop Loss')
                    
                if now.minute in news_update_interval_minutes and now.second == 1:
                    for symbol in self.invester.symbols:
                        news = self.news_reader.today_only(self.news_reader.get_news_by_page(symbol[:6], 1))
                        score = sum(self.news_reader.score(self.news_reader.analyze(self.news_reader.preprocess_x(news))))
                        self._update_news_bias(symbol, score)
            time.sleep(1)
        
    def stop(self):
        self._is_running = False