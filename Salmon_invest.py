from Investment import kis, nasdaq
from Alpha1.strategy import *
from Alpha3.strategy import *
import utils
from Models import model
import backtester

import itertools
import pandas as pd
import math
import schedule
from datetime import datetime, timedelta
import time
import sys

class SalmonInvest:

    def _get_current_prices(self, symbols):
        df = {}
        for symbol in symbols:
            code = symbol.split('.')[0]
            pr, hpr, lpr = self.client.get_price(code)
            df[symbol+"_Price"] = pr
        df = pd.DataFrame(df, index=[datetime.now()])
        return df

    def _process_data(self, raw, norm_raw, bar):
        price_columns = list(map(lambda symbol: symbol+"_Price", self.symbols))
        LMA = norm_raw[price_columns].rolling(50).mean().iloc[bar]
        SMA = norm_raw[price_columns].rolling(14).mean().iloc[bar]
        return {
            "norm_price" : norm_raw[price_columns].iloc[bar],
            "price" : raw[price_columns].iloc[bar],
            "LMA" : LMA,
            "SMA" : SMA
        }
    
    def _create_init_data(self, symbols, start, end, interval):
        raw_data, symbols = utils.load_historical_datas(symbols, start, end, interval)
        raw_data.index = pd.to_datetime(raw_data.index).tz_localize(None)
        raw_data.drop(columns=[col for col in raw_data.columns if col.endswith('_Volume')], inplace=True)
        return raw_data
    
    def __init__(self, yfsymbols, MABT_W, SP_W, Trend_B, current_amount, day_before=30,exchange='krx'):
        if exchange == 'nyse':
            self.client = nasdaq.NasdaqClient(yfsymbols[0])
        elif exchange == 'krx':
            self.client = kis.KISClient(yfsymbols[0], current_amount)
        
        self.MABT = MABreakThrough()
        self.SP = StockPair()
        self.MABT_W = MABT_W
        self.SP_W = SP_W
        self.Trend_B = Trend_B
        
        self.symbols = yfsymbols
        start, end, interval = utils.today_before(day_before), utils.today(), '1h'
        self.raw_data = self._create_init_data(yfsymbols, start, end, interval)
        self.trend_predictors = model.create_trend_predictors(yfsymbols, start, end, interval)
    
    def append_current_data(self):
        df = self._get_current_prices(self.symbols)
        self.raw_data = pd.concat([self.raw_data, df])
        self.current_data = self._process_data(self.raw_data, utils.normalize(self.raw_data), -1)
    
    def action(self):
        trade_dict = {}
        bias = {}
        for symbol in self.symbols:
            trade_dict[symbol] = 0
            d = self.raw_data[[symbol+"_Price"]].iloc[-self.trend_predictors[symbol].minimal_data_length-1:-1]
            trend = self.trend_predictors[symbol].predict(d, symbol)
            bias[symbol] = trend * 0.3 * self.Trend_B
            
        buy_list, sell_list = self.MABT.action(self.symbols, self.current_data)
        for stock in buy_list:
            trade_dict[stock] += 1 * self.MABT_W
        for stock in sell_list:
            trade_dict[stock] -= 1 * self.MABT_W
        
        for pair in list(itertools.combinations(self.symbols, 2)):
            buy_list, sell_list = self.SP.action(self.current_data, pair[0], pair[1])
            for stock in buy_list:
                trade_dict[stock] += 1 * self.SP_W
            for stock in sell_list:
                trade_dict[stock] -= 1 * self.SP_W

        print(trade_dict)
        for stock, amount in trade_dict.items():
            units = math.floor(abs(amount))
            ratio = 0.1 * (units + bias[stock])
            if amount > 0:
                print(f'buy {stock} {ratio}')
                self.client.buy(stock, self.current_data["price"][stock+"_Price"], ratio)
            elif amount < 0:
                print(f'sell {stock} {ratio}')
                self.client.sell(stock, self.current_data["price"][stock+"_Price"], ratio)

    def backtest(self):
        bt = backtester.Backtester(self.symbols, '2023-01-01', '2024-01-01', '1h', 1000000000, 0.0025, self._process_data)
        bias = {}
        bar = 0
        while True:
            raw, data, today = bt.go_next()
            if data == -1:
                break
            trade_dict = {}
            for symbol in self.symbols:
                bias[symbol] = 0
                trade_dict[symbol] = 0
                if bar > self.trend_predictors[symbol].minimal_data_length:
                    trend = self.trend_predictors[symbol].predict(raw[[symbol+"_Price", symbol+"_Volume"]].iloc[bar-self.trend_predictors[symbol].minimal_data_length:bar], symbol)
                    bias[symbol] = trend * 0.3 * self.Trend_B
            buy_list, sell_list = self.MABT.action(self.symbols, data)
            for stock in buy_list:
                trade_dict[stock] += 1 * self.MABT_W
            for stock in sell_list:
                trade_dict[stock] -= 1 * self.MABT_W
            
            for pair in list(itertools.combinations(self.symbols, 2)):
                buy_list, sell_list = self.SP.action(data, pair[0], pair[1])
                for stock in buy_list:
                    trade_dict[stock] += 1 * self.SP_W
                for stock in sell_list:
                    trade_dict[stock] -= 1 * self.SP_W

            for stock, amount in trade_dict.items():
                units = math.floor(abs(amount))
                if amount > 0:
                    bt.buy(stock, 0.1 * (units + bias[stock]))
                elif amount < 0:
                    bt.sell(stock, 0.1 * (units + bias[stock]))
            
            bar += 1

        bt.print_result()
        bt.plot_result()
    
def test():
    symbols = ["042700.KS", "000660.KS", "005930.KS"]
    MABT_weight = 2
    SP_weight = 1.5
    TREND_BIAS = 2.5
        
    invest = SalmonInvest(symbols, MABT_W=MABT_weight, SP_W=SP_weight, Trend_B=TREND_BIAS)
    invest.backtest()
    invest.append_current_data()
    invest.action()