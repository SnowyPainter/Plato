from Investment import kis
from Alpha1.strategy import *
from Alpha3.strategy import *
import utils
from Models import model
import backtester

import pandas as pd
import pytz
import math
import itertools
import schedule
from datetime import datetime, timedelta
import time
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from PyQt5.QtCore import QTimer, QTime
    
class TradingApp(QWidget):
    def today(self, tz = 'Asia/Seoul'):
        return datetime.now(pytz.timezone(tz))
    def today_before(self, day, tz = 'Asia/Seoul'):
        return datetime.now(pytz.timezone(tz)) - timedelta(days=day)

    def current_prices(self, symbols):
        df = {}
        for symbol in symbols:
            code = symbol.split('.')[0]
            df[symbol+"_Price"] = self.client.get_price(code)
        df = pd.DataFrame(df, index=[datetime.now()])
        return df

    def process_data(self, raw, norm_raw, bar):
        price_columns = list(map(lambda symbol: symbol+"_Price", self.symbols))
        LMA = norm_raw[price_columns].rolling(50).mean().iloc[bar]
        SMA = norm_raw[price_columns].rolling(14).mean().iloc[bar]
        return {
            "norm_price" : norm_raw[price_columns].iloc[bar],
            "price" : raw[price_columns].iloc[bar],
            "LMA" : LMA,
            "SMA" : SMA
        }

    def append_current_data(self, raw_data, symbols):
        df = self.current_prices(symbols)
        raw_data = pd.concat([raw_data, df])
        return raw_data, self.process_data(raw_data, utils.normalize(raw_data), -1)
            
    def __init__(self):
        super().__init__()
        self.client = kis.KISClient("Salmon Sk Samsung Hanmi")
        self.MABT_strategy = MABreakThrough()
        self.SP_strategy = StockPair()
        
        self.layout = QVBoxLayout()
        
        self.symbol_label = QLabel('Symbols :')
        self.symbol_input = QLineEdit()
        self.layout.addWidget(self.symbol_label)
        self.layout.addWidget(self.symbol_input)
        
        self.mabt_label = QLabel('SMA BO Weight :')
        self.mabt_input = QLineEdit()
        self.layout.addWidget(self.mabt_label)
        self.layout.addWidget(self.mabt_input)
        
        self.sp_label = QLabel('Pair Trading Weigh :')
        self.sp_input = QLineEdit()
        self.layout.addWidget(self.sp_label)
        self.layout.addWidget(self.sp_input)
        
        self.trend_bias_label = QLabel('Trend Bias :')
        self.trend_bias_input = QLineEdit()
        self.layout.addWidget(self.trend_bias_label)
        self.layout.addWidget(self.trend_bias_input)
        
        self.submit_button = QPushButton('Submit')
        self.submit_button.clicked.connect(self.on_submit)
        
        self.backtest_button = QPushButton('Backtest')
        self.backtest_button.clicked.connect(self.backtest)
        
        self.layout.addWidget(self.submit_button)
        self.layout.addWidget(self.backtest_button)
        
        self.setLayout(self.layout)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.execute_action)
        self.daily_timer = QTimer(self)
        self.daily_timer.timeout.connect(self.check_start_time)
        self.show()
    
    def on_submit(self):
        self.symbols = self.symbol_input.text().split(' ')
        self.MABT_weight = float(self.mabt_input.text())
        self.SP_weight = float(self.sp_input.text())
        self.TREND_BIAS = float(self.trend_bias_input.text())
        QMessageBox.information(self, "Submit, ", f"Symbols: {self.symbols}\nSMA BO W: {self.MABT_weight}\nPT W: {self.SP_weight}\nTrend B : {self.TREND_BIAS}")
        self.trend_predictors = {}
        start, end, interval = self.today_before(30), self.today(), '1h'
        self.raw_data, self.symbols = utils.load_historical_datas(self.symbols, start, end, interval)
        self.raw_data.index = pd.to_datetime(self.raw_data.index).tz_localize(None)
        self.raw_data.drop(columns=[col for col in self.raw_data.columns if col.endswith('_Volume')], inplace=True)

        for symbol in self.symbols:
            self.trend_predictors[symbol] = model.TrendPredictor(symbol, start, end, interval)
            print(self.trend_predictors[symbol].fit())

        self.daily_timer.start(60000)
        self.submit_button.setText("Running")
        
    def execute_action(self):
        if self.client.is_market_open():
            self.execute_trading_strategy()
        else:
            self.timer.stop()
    
    def start_hourly_timer(self):
        if self.client.is_market_open():
            self.timer.start(3600000)  # 3600000 milliseconds = 1 hour
            self.execute_action()  # Execute immediately upon starting
        else:
            print("Market is closed")

    def check_start_time(self):
        now = QTime.currentTime()
        if now.hour() == 9 and now.minute() == 0:
            self.start_hourly_timer()
    
    def execute_trading_strategy(self):
        print("Executing trading strategy at", self.today())
        self.raw_data, processed_data = self.append_current_data(self.raw_data, self.symbols)
        trade_dict = {}
        basis = {}
        for symbol in self.symbols:
            trade_dict[symbol] = 0
            d = self.raw_data[[symbol+"_Price"]].iloc[-self.trend_predictors[symbol].minimal_data_length-1:-1]
            trend = self.trend_predictors[symbol].predict(d, symbol)
            basis[symbol] = trend * 0.5 * self.TREND_BIAS
        buy_list, sell_list = self.MABT_strategy.action(self.symbols, processed_data)
        for stock in buy_list:
            trade_dict[stock] += 1 * self.MABT_weight
        for stock in sell_list:
            trade_dict[stock] -= 1 * self.MABT_weight
            
        for pair in list(itertools.combinations(self.symbols, 2)):
            buy_list, sell_list = self.SP_strategy.action(processed_data, pair[0], pair[1])
            for stock in buy_list:
                trade_dict[stock] += 1 * self.SP_weight
            for stock in sell_list:
                trade_dict[stock] -= 1 * self.SP_weight

        for stock, amount in trade_dict.items():
            units = math.floor(abs(amount))
            ratio = 0.1 * (units + basis[stock])
            code = stock.split('.')[0]
            if amount > 0:
                self.client.buy(code, processed_data["price"][stock+"_Price"], ratio)
            elif amount < 0:
                self.client.sell(code, processed_data["price"][stock+"_Price"], ratio)

    def backtest(self):
        self.symbols = self.symbol_input.text().split(' ')
        symbols = self.symbols
        MABT_weight = float(self.mabt_input.text())
        SP_weight = float(self.sp_input.text())
        TREND_BIAS = float(self.trend_bias_input.text())
        trend_predictors = {}
        for symbol in symbols:
            trend_predictors[symbol] = model.TrendPredictor(symbol, '2023-05-01', '2024-06-12', '1h')
            trend_predictors[symbol].fit()

        bt = backtester.Backtester(symbols, '2023-01-01', '2024-01-01', '1d', 1000000000, 0.0025, self.process_data)
        symbols = bt.symbols
        MABT = MABreakThrough()
        SP = StockPair()

        basis = {}
        bar = 0
        while True:
            raw, data, today = bt.go_next()
            if data == -1:
                break
            red_flags = []
            trade_dict = {}
            for symbol in symbols:
                basis[symbol] = 0
                trade_dict[symbol] = 0
                if bar > trend_predictors[symbol].minimal_data_length:
                    trend = trend_predictors[symbol].predict(raw[[symbol+"_Price", symbol+"_Volume"]].iloc[bar-trend_predictors[symbol].minimal_data_length:bar], symbol)
                    if trend == 1: #up
                        basis[symbol] += TREND_BIAS
                    elif trend == 0:
                        red_flags.append(symbol)
            buy_list, sell_list = MABT.action(symbols, data)
            for stock in buy_list:
                trade_dict[stock] += 1 * MABT_weight
            for stock in sell_list:
                trade_dict[stock] -= 1 * MABT_weight
            
            for pair in list(itertools.combinations(symbols, 2)):
                buy_list, sell_list = SP.action(data, pair[0], pair[1])
                for stock in buy_list:
                    trade_dict[stock] += 1 * SP_weight
                for stock in sell_list:
                    trade_dict[stock] -= 1 * SP_weight

            for stock, amount in trade_dict.items():
                units = math.floor(abs(amount))
                if stock in red_flags:
                    continue
                if amount > 0:
                    bt.buy(stock, 0.1 * (units + basis[stock]))
                elif amount < 0:
                    bt.sell(stock, 0.1 * (units + basis[stock]))
            
            bar += 1

        bt.print_result(f'./{datetime.now()}.txt')
        bt.plot_result()
    
if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = TradingApp()
    sys.exit(app.exec_())