from Alpha1.strategy import *
from Alpha5.strategy import *

from Models import trend_predictor, ARIMA
import backtester
import utils
from Investment import kis

from datetime import datetime
import itertools
import math
import numpy as np
import pandas as pd

class NeoInvest:
    def _process_data(self, raw, norm_raw, bar):
        price_columns = list(map(lambda symbol: symbol+"_Price", self.symbols))
        LMA = norm_raw[price_columns].rolling(50).mean().iloc[bar]
        SMA = norm_raw[price_columns].rolling(14).mean().iloc[bar]
        return {
            "norm_price_series" : norm_raw[price_columns],
            "norm_price" : norm_raw[price_columns].iloc[bar],
            "price" : raw[price_columns].iloc[bar],
            "LMA" : LMA,
            "SMA" : SMA
        }
    def _get_current_prices(self, symbols):
        df = {}
        for symbol in symbols:
            code = symbol.split('.')[0]
            pr,hpr,lpr = self.client.get_price(code)
            df[symbol+"_Price"] = pr
            df[symbol+"_High"] = hpr
            df[symbol+"_Low"] = lpr
        df = pd.DataFrame(df, index=[datetime.now()])
        return df
    def _create_init_data(self, symbols, start, end, interval):
        raw_data, symbols = utils.load_historical_datas(symbols, start, end, interval)
        raw_data.index = pd.to_datetime(raw_data.index).tz_localize(None)
        raw_data.drop(columns=[col for col in raw_data.columns if col.endswith('_Volume')], inplace=True)
        
        raw_data.dropna(inplace=True)
        
        return raw_data

    def __init__(self, symbol1, symbol2, current_amount, orders={}):
        self.symbols = [symbol1, symbol2]
        self.client = kis.KISClient(self.symbols[0], current_amount)
        
        self.OU = OU()
        self.MABT = MABreakThrough()
        start, end, interval = utils.today_before(120), utils.today(), '1h'
        self.raw_data = self._create_init_data(self.symbols, start, end, interval)
        self.technical_trend_predictors = trend_predictor.create_trend_predictors(self.symbols, start, end, interval)
        self.arima_trend_predictors = ARIMA.create_price_predictor(utils.normalize(self.raw_data), self.symbols, orders)
        self.bar = 0

    def append_current_data(self):
        df = self._get_current_prices(self.symbols)
        self.raw_data = pd.concat([self.raw_data, df])
        self.current_data = self._process_data(self.raw_data, utils.normalize(self.raw_data), -1)
    
    def action(self, hour_divided_time=1):
        window = 62
        norm_raw = utils.normalize(self.raw_data)
        price1 = norm_raw[self.symbols[0]+"_Price"].tail(window)
        price2 = norm_raw[self.symbols[1]+"_Price"].tail(window)
        
        not_trade = []
        trade_dict = {}
        for symbol in self.symbols:
            trade_dict[symbol] = 0
        
        buy_list, sell_list, alpha_ratio = self.OU.get_signal(self.symbols[0], self.symbols[1], price1, price2)
        for b in buy_list:
            trade_dict[b] += alpha_ratio
        for s in sell_list:
            trade_dict[s] -= alpha_ratio
        
        for symbol in self.symbols:
            if not (symbol in self.technical_trend_predictors) or self.bar % hour_divided_time != 0:
                continue
            trend = self.technical_trend_predictors[symbol].predict(self.raw_data.tail(self.technical_trend_predictors[symbol].minimal_data_length), symbol)
            indic = "down" if trend == 0 else ("up" if trend == 2 else "sideway")
            print(f"{symbol} : {indic}")
            if trend == 2:
                trade_dict[symbol] += 0.6
            elif trend == 0:
                trade_dict[symbol] *= 0.3
            else:
                not_trade.append(symbol)
        
        action_dicts = [utils.process_weights({k: v for k, v in trade_dict.items() if v > 0}), {k: v for k, v in trade_dict.items() if v < 0}]
        for stock, alpha in action_dicts[1].items(): # sell
            if stock in not_trade:
                continue
            alpha_ratio = abs(alpha)
            print("Sell ", stock, alpha_ratio)
            self.client.sell(stock, self.current_data["price"][stock+"_Price"], alpha_ratio)
        for stock, alpha in action_dicts[0].items(): # buy
            if stock in not_trade:
                continue
            alpha_ratio = abs(alpha)
            if alpha_ratio <= 0.1 and alpha_ratio >= 0.01:
                alpha_ratio = 0.1
            print("Buy ", stock, alpha_ratio)
            self.client.buy(stock, self.current_data["price"][stock+"_Price"], alpha_ratio)
        
        self.bar += 1
        
    def backtest(self, start='2023-01-01', end='2024-01-01', interval='1h', print_result=True):
        bt = backtester.Backtester(self.symbols, start, end, interval, 10000000, 0.0025, self._process_data)
        bar = 0
        window = 62
        while True:
            raw, data, today = bt.go_next()
            if data == -1:
                break
            
            not_trade = []
            trade_dict = {}
            for symbol in self.symbols:
                trade_dict[symbol] = 0
                        
            if bar != 0 and bar >= window:
                price1, price2 = data["norm_price_series"][self.symbols[0]+"_Price"], data["norm_price_series"][self.symbols[1]+"_Price"]
                price1 = price1[bar - window:bar]
                price2 = price2[bar - window:bar]
                buy_list, sell_list, alpha_ratio = self.OU.get_signal(self.symbols[0], self.symbols[1], price1, price2)
                for b in buy_list:
                    trade_dict[b] += alpha_ratio
                for s in sell_list:
                    trade_dict[s] -= alpha_ratio
            
            for stock, p in self.arima_trend_predictors.items():
                y = p.make_forecast(10)
                x = np.arange(len(y))
                coefficients = np.polyfit(x, y, 1)
                trade_dict[stock] += coefficients[0] * 20
            
            for symbol in self.symbols:
                if not (symbol in self.technical_trend_predictors):
                    continue
                hdt = 1 if interval == '1h' else 2
                if bar > self.technical_trend_predictors[symbol].minimal_data_length and (bar - self.technical_trend_predictors[symbol].minimal_data_length) % hdt == 0:
                    trend = self.technical_trend_predictors[symbol].predict(raw.iloc[bar-self.technical_trend_predictors[symbol].minimal_data_length:bar], symbol)
                    if trend == 2:
                        trade_dict[symbol] += 0.6
                    elif trend == 0:
                        trade_dict[symbol] *= 0.25
                    else:
                        not_trade.append(symbol)
            
            action_dicts = [utils.process_weights({k: v for k, v in trade_dict.items() if v > 0}), {k: v for k, v in trade_dict.items() if v < 0}]
            for stock, alpha in action_dicts[1].items(): # sell
                if stock in not_trade:
                    continue
                alpha_ratio = abs(alpha)
                bt.sell(stock, alpha_ratio)
            for stock, alpha in action_dicts[0].items(): # buy
                if stock in not_trade:
                    continue
                alpha_ratio = abs(alpha)
                bt.buy(stock, alpha_ratio)

            #bt.print_stock_weights()
            bar += 1
        
        if print_result:
            bt.print_result()
            bt.plot_result() 
        else:   
            return bt.print_result(fname='return')
        