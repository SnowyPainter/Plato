import sys
from PyQt5.QtWidgets import QMenu, QAction, QApplication, QMainWindow, QPushButton, QHBoxLayout, QVBoxLayout, QWidget, QLabel, QComboBox, QLineEdit, QMessageBox, QInputDialog, QListWidget, QListWidgetItem
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSlot, pyqtSignal
import time
from datetime import datetime, timedelta
import multiprocessing as mp
import os
import configparser

from LM import news
import Neo_invest
import corr_high_finder
import utils
import connect_tester

class InvestThread(QThread):
    update_signal = pyqtSignal(str)
    
    def __init__(self, news_reader, interval, process_name, invester, invest_logs):
        super().__init__()
        self.news_reader = news_reader
        self.interval = interval
        self.process_name = process_name
        self.invester = invester
        self.invest_logs = invest_logs
        self._is_running = True
    
    @pyqtSlot(str)
    def invest_info_update_signal_update(self, body):
        value = body.split('&')[1]
        if "$MOA$" in body:
            self.invester.update_max_operate_amount(float(value))
    
    def run(self):
        def action():
            self.invester.append_current_data()
            text = self.invester.action(hour_divided_time=1 if self.interval == '1h' else 2)
            self.invest_logs.append(text)
            self.update_signal.emit(f"{self.invester.symbols} {datetime.now()}")

        def update_news_bias(symbol, score):
            self.invester.news_bias[symbol] = score / 10
        
        start_time = datetime.strptime("09:00", "%H:%M").time()
        end_time = datetime.strptime("15:30", "%H:%M").time()
        interval_minutes = [0, 29]
        if self.interval == '1h':
            interval_minutes = [0]
        elif self.interval == '30m':
            interval_minutes = [0, 29]
        
        news_update_interval_minutes = [0, 10, 20, 30, 40, 50]
        
        now = datetime.now()
        if now > datetime.combine(now.date(), end_time):
            start_time = (datetime.combine(now, start_time) + timedelta(days=1)).time()

        while self._is_running:
            now = datetime.now()
            if start_time <= now.time() <= end_time:
                curr = datetime.now()
                if now.minute in interval_minutes and now.second == 1:
                    action()
                    time.sleep(60)
                
                if now.minute in news_update_interval_minutes and now.second == 1:
                    for symbol in self.invester.symbols:
                        news = self.news_reader.today_only(self.news_reader.get_news_by_page(symbol[:6], 1))
                        score = sum(self.news_reader.score(self.news_reader.analyze(self.news_reader.preprocess_x(news))))
                        update_news_bias(symbol, score)
                        
                    time.sleep(60)
                
                if curr.time() > end_time:
                    print(f"Trade Done {self.process_name}")
                    self.update_signal.emit(f"$END$&{self.process_name}")
                    break

            time.sleep(1)
        
    def stop(self):
        self._is_running = False

class TradingApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.news_reader = news.NewsReader()
        if os.path.exists('./models/'+self.news_reader.BEST_MODEL_NAME):
            self.news_reader.load_model()
        else:
            self.news_reader.train_model()
        
        self.setWindowTitle("Trading Application")
        self.setGeometry(100, 100, 400, 300)
        self.setFixedSize(1024, 680)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.body = QHBoxLayout()
        self.act_layout = QVBoxLayout()
        self.etc_layout = QVBoxLayout()
        self.opt_layout = QHBoxLayout()
        self.text_layout = QHBoxLayout()
        self.bt_layout = QVBoxLayout()
        self.invest_layout = QVBoxLayout()

        self.central_widget.setLayout(self.body)
        self.option_combo = QComboBox()
        self.options = ['Backtest', 'Invest', 'Recommend Stocks']
        self.option_combo.addItems(self.options)
        self.act_layout.addWidget(self.option_combo)

        self.continue_button = QPushButton("Run")
        self.continue_button.clicked.connect(self.handle_option)
        self.act_layout.addWidget(self.continue_button)

        self.process_list_label = QLabel("Invest process running:")
        self.act_layout.addWidget(self.process_list_label)

        self.process_list_widget = QListWidget()
        self.process_list_widget.itemDoubleClicked.connect(self.show_process_info)
        self.process_list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.process_list_widget.customContextMenuRequested.connect(self.show_proc_interact_menu)
        self.act_layout.addWidget(self.process_list_widget)
        
        self.refresh_token_btn = QPushButton("Refresh Token")
        self.refresh_token_btn.clicked.connect(self.refresh_token)
        self.set_api_btn = QPushButton("Set API")
        self.set_api_btn.clicked.connect(self.set_api)
        
        self.opt_layout.addWidget(self.refresh_token_btn, stretch=3)
        self.opt_layout.addWidget(self.set_api_btn, stretch=1)
        
        self.bt_result_texts = []
        self.bt_result_list = QListWidget(self)
        self.bt_result_list.itemClicked.connect(self.show_bt_result)
        self.bt_layout.addWidget(self.bt_result_list)
        
        self.invest_logs = []
        self.invest_log_list = QListWidget(self)
        self.invest_log_list.itemClicked.connect(self.show_invest_log)
        self.invest_layout.addWidget(self.invest_log_list)
        
        self.etc_layout.addLayout(self.opt_layout, stretch=1)
        self.etc_layout.addLayout(self.text_layout, stretch=5)
        self.text_layout.addLayout(self.bt_layout, stretch=2)
        self.text_layout.addLayout(self.invest_layout, stretch=2)
        
        self.body.addLayout(self.act_layout, stretch=1)
        self.body.addLayout(self.etc_layout, stretch=3)
        self.hour_divided_time = 1
        self.scheduled_jobs = {}
        self.processes = {}
    
    def show_proc_interact_menu(self, position):
        selected_item = self.process_list_widget.itemAt(position)
        if selected_item is not None:
            menu = QMenu()
            cancel_action = QAction('Cancel', self)
            cancel_action.triggered.connect(lambda: self.cancel_selected_process(selected_item))
            menu.addAction(cancel_action)

            update_moa = QAction('Update MOA', self)
            update_moa.triggered.connect(lambda: self.update_moa(selected_item))
            menu.addAction(update_moa)
            
            news_evlu = QAction("Current News", self)
            news_evlu.triggered.connect(lambda: self.show_news_evluate(selected_item))
            menu.addAction(news_evlu)
            
            show_info = QAction('Info', self)
            show_info.triggered.connect(lambda: self.show_process_info(selected_item))
            menu.addAction(show_info)
            
            menu.exec_(self.process_list_widget.viewport().mapToGlobal(position))
    
    def show_process_info(self, item):
        if item is None:
            return
        
        proc = self.processes[item.text()]
        text = ''
        text += f"===== {proc.process_name} =====\n"
        text += f"{proc.invester.get_information()}"
        QMessageBox.information(self, f'{proc.process_name} Info', text)
    
    def update_moa(self, item):
        if item:
            value, ok = QInputDialog.getDouble(self, "Update MOA", "Enter Max Operate Amount:")
            if ok:
                self.processes[item.text()].invest_info_update_signal_update(f"$MOA$&{value}")
    def cancel_selected_process(self, item):
        if not item:
            QMessageBox.warning(self, "Warning", "You didn't select any process.")
            return
        process_name = item.text()
        if process_name in self.processes:
            self.processes[process_name].stop()
            self.processes[process_name].wait()
            del self.processes[process_name]
        self.process_list_widget.takeItem(self.process_list_widget.row(item))
        QMessageBox.information(self, "Cancel", f"{process_name} is canceled.")
    
    def update_invest_log_list(self, text):
        if "$END$" in text:
            process_name = text.split('&')[1]
            self.processes[process_name].stop()
            self.processes[process_name].wait()
            del self.processes[process_name]
            for i in range(0, self.process_list_widget.count()):
                item = self.process_list_widget.item(i)
                if item.text() == process_name:
                    self.process_list_widget.takeItem(i)
            return
        self.invest_log_list.addItem(text)
    
    def show_news_evluate(self, item):
        symbols = self.processes[item.text()].invester.symbols
        text = ''
        for symbol in symbols:
            symbol = symbol[:6]
            news_data = self.news_reader.today_only(self.news_reader.get_news_by_page(symbol, 1))
            x = self.news_reader.preprocess_x(news_data)
            analyzed = self.news_reader.analyze(x)
            score = self.news_reader.score(analyzed)
            label = self.news_reader.label(analyzed)
            text += f"{symbol}'s Today News: {len(news_data)}\n"
            text += f"Positive: {label.count('positive')}, Neutral: {label.count('neutral')}, Negative: {label.count('negative')}\n"
            text += f"Total Score: {sum(score) :.2f}\n\n"
        
        QMessageBox.information(self, "News Evluate", text)
    
    def show_invest_log(self, item):
        index = self.invest_log_list.row(item)
        t = self.invest_logs[index]
        QMessageBox.information(self, 'Invest act', t)
    
    def show_bt_result(self, item):
        index = self.bt_result_list.row(item)
        t = self.bt_result_texts[index]
        QMessageBox.information(self, 'Backtest Result', t)

    def set_api(self):
        key, ok = QInputDialog.getText(self, "Input", f"API Key: ")
        if not ok:
            return
        secret, ok = QInputDialog.getText(self, "Input", f"API Secret: ")
        if not ok:
            return
        accno, ok = QInputDialog.getText(self, "Input", f"Account No.: ")
        if not ok:
            return
        
        config = configparser.ConfigParser()
        config['API'] = {
            'KEY': key,
            'SECRET': secret,
            'ACCNO': accno
        }
        if not os.path.exists('./settings'):
            os.mkdir('./settings')
        with open('./settings/keys.ini', 'w') as configfile:
            config.write(configfile)
        
    def refresh_token(self):
        connect_tester.check_connection()
    
    @pyqtSlot()
    def handle_option(self):
        opt = self.option_combo.currentText()
        if opt == 'Backtest':
            self.backtest()
        elif opt == 'Invest':
            self.invest()
        elif opt == 'Recommend Stocks':
            self.recommend_stocks()
        else:
            QMessageBox.warning(self, "Warning", "Not Available Option.")
    
    def get_symbols(self, option):
        symbols_input, ok = QInputDialog.getText(self, "Input", f"{option} - seperate symbols by ',' :")
        if ok and symbols_input:
            symbols = [symbol.strip() for symbol in symbols_input.split(",")]
            if len(symbols) == 2:
                return symbols
            else:
                QMessageBox.warning(self, "Warning", "Input two symbols seperate by ',' ")
                return self.get_symbols(option)
        else:
            return []

    def get_bt_term(self, option):
        start, ok = QInputDialog.getText(self, "Input", f"{option} - Start(2023-xx-xx):")
        if not ok:
            return '', ''
        
        end, ok = QInputDialog.getText(self, "Input", f"{option} - End(2024-xx-xx):")
        if not ok:
            return '', ''
        
        if utils.start_end_date_valid(start, end) and utils.is_valid_date_format(start) and utils.is_valid_date_format(end):
            return start, end
        
        return '', ''

    def get_amounts(self, option):
        max_operate_amount, ok = QInputDialog.getDouble(self, "Input", f"{option} - Max Operatable Amount:")
        
        if max_operate_amount <= 0 or not ok:
            return 0
        
        return max_operate_amount
    
    def backtest(self):
        symbols = self.get_symbols("Backtest")
        if len(symbols) == 0:
            return
        start, end = self.get_bt_term("Backtest")
        if start == '' or end == '':
            return
        
        invester = Neo_invest.NeoInvest(symbols[0], symbols[1], 10000000000, nolog=True, only_backtest=True)
        result = invester.backtest(start, end, show_only_text=True)
        self.bt_result_texts.append(result)
        self.bt_result_list.addItem(f"{symbols} | {start} ~ {end}")
        QMessageBox.information(self, "Done", "Backtesting Done")

    def invest(self):
        symbols = self.get_symbols("Invest")
        if len(symbols) == 0:
            return
        
        max_operate_amount = self.get_amounts("Invest")
        if max_operate_amount <= 0:
            return
        
        '''
        exists_params = QMessageBox.question(self, "Confirm", "Does it exist that learned parameters for ARIMA?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes
        if exists_params:
            orders = utils.get_saved_orders(symbols)
        else:
            orders = {}
        '''
        interval = '30m'
        orders = {}
        process_name = f"{symbols[0]}_{symbols[1]}_{interval}"
        
        self.process_list_widget.addItem(process_name)
        self.schedule_action(interval, process_name, Neo_invest.NeoInvest(symbols[0], symbols[1], max_operate_amount, orders))
    
    def schedule_action(self, interval, process_name, invester):
        if process_name in self.processes:
            QMessageBox.warning(self, "Warning", "Process already scheduled for these symbols.")
            return
        
        worker_thread = InvestThread(self.news_reader, interval, process_name, invester, self.invest_logs)
        worker_thread.update_signal.connect(self.update_invest_log_list)
        worker_thread.start()
        self.processes[process_name] = worker_thread
        
    def recommend_stocks(self):
        processes = []
        result_batch = []
        for theme_name, theme in utils.THEMES.items():
            pairs = corr_high_finder.find_stocks_to_invest(theme)
            if len(pairs) == 0:
                continue
            manager = mp.Manager()
            results = manager.dict()
            result_batch.append(results)
            start, end = utils.today_and_month_ago()

            for pair in pairs:
                p = mp.Process(target=corr_high_finder.run_backtest, args=(pair, start, end, results))
                processes.append(p)
                p.start()
            for p in processes:
                p.join()
            corr_high_finder.save_results(results, theme_name)
        QMessageBox.information(self, "Done", "Recommendation finishied")
    
    

if __name__ == '__main__':
    app = QApplication(sys.argv)
    trading_app = TradingApp()
    trading_app.show()
    sys.exit(app.exec_())