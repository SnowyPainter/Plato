from Investment import kis
from Alpha1.strategy import *
from Alpha3.strategy import *
import utils
from Models import model
import backtester
import read_trades
import Salmon_invest

import pandas as pd
import pytz
import math
import itertools
import schedule
from datetime import datetime, timedelta
import time
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QFileDialog
from PyQt5.QtCore import QTimer, QTime

#042700.KS 000660.KS 005930.KS

class TradingApp(QWidget): 
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

    def __init__(self):
        super().__init__()
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
        
        self.show_trade_log_button = QPushButton("Show Log")
        self.show_trade_log_button.clicked.connect(self.show_log)
        
        self.layout.addWidget(self.submit_button)
        self.layout.addWidget(self.backtest_button)
        self.layout.addWidget(self.show_trade_log_button)
        
        self.setLayout(self.layout)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.execute_action)
        self.daily_timer = QTimer(self)
        self.daily_timer.timeout.connect(self.check_start_time)
        
        self.symbols = []
        
        self.show()
    
    def on_submit(self):
        self.symbols = self.symbol_input.text().split(' ')
        self.MABT_weight = float(self.mabt_input.text())
        self.SP_weight = float(self.sp_input.text())
        self.TREND_BIAS = float(self.trend_bias_input.text())
        QMessageBox.information(self, "Submit, ", f"Symbols: {self.symbols}\nSMA BO W: {self.MABT_weight}\nPT W: {self.SP_weight}\nTrend B : {self.TREND_BIAS}")
        
        self.invester = Salmon_invest.SalmonInvest(self.symbols, self.MABT_weight, self.SP_weight, self.TREND_BIAS, 30)
        
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
        self.invester.append_current_data()
        self.invester.action()

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

        bt = backtester.Backtester(symbols, '2023-01-01', '2024-01-01', '1h', 1000000000, 0.0025, self.process_data)
        symbols = bt.symbols
        MABT = MABreakThrough()
        SP = StockPair()

        bias = {}
        bar = 0
        while True:
            raw, data, today = bt.go_next()
            if data == -1:
                break
            trade_dict = {}
            for symbol in symbols:
                bias[symbol] = 0
                trade_dict[symbol] = 0
                if bar > trend_predictors[symbol].minimal_data_length:
                    trend = trend_predictors[symbol].predict(raw[[symbol+"_Price", symbol+"_Volume"]].iloc[bar-trend_predictors[symbol].minimal_data_length:bar], symbol)
                    bias[symbol] = trend * 0.3 * TREND_BIAS
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
                if amount > 0:
                    bt.buy(stock, 0.1 * (units + bias[stock]))
                elif amount < 0:
                    bt.sell(stock, 0.1 * (units + bias[stock]))
            
            bar += 1

        bt.print_result(f'./{datetime.now().strftime("%Y-%m-%d %H-%M-%S")}.txt')
        bt.plot_result()
    
    def show_log(self):
        path = QFileDialog.getOpenFileName(self, 'Trades File', './', "CSV Files (*.csv)")
        if path != ('', ''):
            trades = read_trades.read_trades_csv(path[0])
            df, symbols = read_trades.get_historical_same_size(trades)
            read_trades.plot(trades, df, symbols)
    
if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = TradingApp()
    sys.exit(app.exec_())