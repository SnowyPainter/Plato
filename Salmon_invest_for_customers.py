from Investment import kis
from Alpha1.strategy import *
from Alpha3.strategy import *
import utils
from Models import model

import itertools
import pandas as pd
import pytz
import math
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
        self.layout.addWidget(self.submit_button)
        
        self.setLayout(self.layout)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_market_and_execute)

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
            
        self.timer.start(3600 * 1000)  # 1 hour in milliseconds
    
    def check_market_and_execute(self):
        if self.client.is_market_open():
            self.execute_trading_strategy()
    
    def execute_trading_strategy(self):
        print("Executing trading strategy at", self.today())
        self.raw_data, processed_data = self.append_current_data(self.raw_data, self.symbols)
        red_flags = []
        trade_dict = {}
        basis = {}
        for symbol in self.symbols:
            trade_dict[symbol] = 0
            basis[symbol] = 0
            d = self.raw_data[[symbol+"_Price"]].iloc[-self.trend_predictors[symbol].minimal_data_length-1:-1]
            trend = self.trend_predictors[symbol].predict(d, symbol)
            if trend == 1: #up
                basis[symbol] += self.TREND_BIAS
            elif trend == 0:
                red_flags.append(symbol)
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

        print(trade_dict)
        for stock, amount in trade_dict.items():
            units = math.floor(abs(amount))
            ratio = 0.1 * (units + basis[stock])
            if stock in red_flags:
                continue
            code = stock.split('.')[0]
            if amount > 0:
                self.client.buy(code, processed_data["price"][stock+"_Price"], ratio)
            elif amount < 0:
                self.client.sell(code, processed_data["price"][stock+"_Price"], ratio)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = TradingApp()
    sys.exit(app.exec_())