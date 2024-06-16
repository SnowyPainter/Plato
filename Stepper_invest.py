from Alpha4.strategy import *
import backtester
import utils

from datetime import datetime
import itertools
import pandas as pd

class StepperInvest:
    def process_data(self, raw, norm_raw, bar):
        price_columns = list(map(lambda symbol: symbol+"_Price", self.symbols))
        
        return {
            "norm_price" : norm_raw[price_columns].iloc[bar],
            "price" : raw[price_columns].iloc[bar],
        }

    def __init__(self, symbols, day_before, interval):
        self.symbols = symbols
        self.BSR = BollingerSplitReversal()
        
    def backtest(self):
        bt = backtester.Backtester(self.symbols, '2023-01-01', '2024-01-01', '1h', 10000000, 0.0025, self.process_data)
        
        bar = 0
        while True:
            raw, data, today = bt.go_next()
            if data == -1:
                break
            
            if bar >= self.BSR.minimal_window:
                bands = {}
                for symbol in self.symbols:
                    ub, lb, mid = self.BSR.get_bollinger_band(raw, symbol+"_Price")
                    bands[symbol] = {}
                    bands[symbol]['ub'] = ub.iloc[bar]
                    bands[symbol]['lb'] = lb.iloc[bar]
                    bands[symbol]['mid'] = mid.iloc[bar]
                trade_strengths = self.BSR.action(self.symbols, data, bands)
                for symbol, strength in trade_strengths.items():
                    alpha_ratio = abs((strength / data['price'][symbol+"_Price"]) * 50)
                    if strength > 0:
                        bt.buy(symbol, alpha_ratio)
                    elif strength < 0:
                        bt.sell(symbol, alpha_ratio)
                    
            bar += 1
        bt.print_result()
        bt.plot_result()

#한미반도체, SK하이닉스, 삼성전자
symbols = ["042700.KS", "000660.KS", "005930.KS"]

invester = StepperInvest(symbols, 30, '1h')
invester.backtest()