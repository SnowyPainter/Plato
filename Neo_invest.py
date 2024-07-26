from Alpha1.strategy import *
from Alpha5.strategy import *

from Models import trend_predictor, ARIMA, GJRGARCH 
import backtester
import utils
from Investment import kis

from datetime import datetime
import itertools
import math
import numpy as np
import pandas as pd

import warnings
warnings.filterwarnings("ignore")

class NeoInvest:
    def _process_data(self, raw, norm_raw, bar):
        price_columns = list(map(lambda symbol: symbol+"_Price", self.symbols))
        LMA = norm_raw[price_columns].rolling(120).mean().iloc[bar]
        SMA = norm_raw[price_columns].rolling(25).mean().iloc[bar]
        return {
            "norm_price_series" : utils.nplog(raw)[price_columns],
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

    def __init__(self, symbol1, symbol2, max_operate_amount, orders={}, nobacktest=False, nolog=False):
        self.symbols = [symbol1, symbol2]
        self.client = kis.KISClient(self.symbols, max_operate_amount, nolog)
        self.OU = OU()
        self.MABT = MABreakThrough()
        start, end, interval = utils.today_before(120), utils.today(), '1h'
        self.raw_data = self._create_init_data(self.symbols, start, end, interval)
        self.technical_trend_predictors = trend_predictor.create_trend_predictors(self.symbols, start, end, interval)
        self.orders = orders
        if not (symbol1 in orders) or not (symbol2 in orders) or (self.orders == {} and not nobacktest):
            self.orders = utils.get_saved_orders(self.symbols)
            if self.orders == {}:
                print(f"Get Params for Backtest")
                ARIMA.create_price_predictor_BT(utils.nplog(self.raw_data), self.symbols, {})
                self.orders = utils.get_saved_orders(self.symbols)
        self.bar = 0

    def append_current_data(self):
        df = self._get_current_prices(self.symbols)
        self.raw_data = pd.concat([self.raw_data, df])
        self.current_data = self._process_data(self.raw_data, utils.normalize(self.raw_data), -1)
    
    def action(self, hour_divided_time=1):
        window = hour_divided_time * 50
        log = utils.nplog(self.raw_data)
        price1 = log[self.symbols[0]+"_Price"].tail(window)
        price2 = log[self.symbols[1]+"_Price"].tail(window)
        
        not_trade = []
        trade_dict = {}
        tech_signal = {}
        serial_signal = {}
        for symbol in self.symbols:
            trade_dict[symbol] = 0
            tech_signal[symbol] = 0
            serial_signal[symbol] = 0
        
        text = ""
        
        buy_list, sell_list, alpha_ratio = self.OU.get_signal(self.symbols[0], self.symbols[1], price1, price2)
        
        text += f"[OU] Buy {buy_list} | Sell {sell_list} | Alpha : {alpha_ratio} \n"
        
        for b in buy_list:
            trade_dict[b] += alpha_ratio
        for s in sell_list:
            trade_dict[s] -= alpha_ratio
        
        if self.bar % hour_divided_time == 0:
            for symbol in self.symbols:
                if not (symbol in self.technical_trend_predictors):
                    continue
                trend = self.technical_trend_predictors[symbol].predict(self.raw_data.tail(self.technical_trend_predictors[symbol].minimal_data_length), symbol)
                text += f"[Tech] {symbol} goes {('Up' if trend == 2 else ('Down' if trend == 0 else 'Sideway'))} \n"
                tech_signal[symbol] = (0.6 if trend == 2 else (-0.6 if trend == 0 else 0))
                if trend == 1:
                    not_trade.append(symbol)
        if self.bar % (hour_divided_time * 2) == 0:
            self.arima_trend_predictors = ARIMA.create_price_predictor(utils.nplog(self.raw_data).tail(50), self.symbols)
            for stock, p in self.arima_trend_predictors.items():
                y = p.make_forecast(10)
                x = np.arange(len(y))
                coefficients = np.polyfit(x, y, 1)
                v = coefficients[0] * 300
                serial_signal[stock] = (v if coefficients[0] > 0 else -v)
                text += f"[ARIMA] {stock} goes {('Up' if coefficients[0] > 0 else 'Down')} | W:{(v if coefficients[0] > 0 else -v)} \n"
        
        for symbol in self.symbols:
            trade_dict[symbol] += (serial_signal[symbol] + tech_signal[symbol]) / 2

        cash, limit = self.client.max_operate_cash(), self.client.max_operate_amount
        action_dicts = [utils.preprocess_weights({k: v for k, v in trade_dict.items() if v > 0}, cash, limit), {k: v for k, v in trade_dict.items() if v < 0}]
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
            print("Buy ", stock, alpha_ratio)
            self.client.buy(stock, self.current_data["price"][stock+"_Price"], alpha_ratio)
        
        print(text)
        
        self.bar += 1
        
    def backtest(self, start='2023-01-01', end='2024-01-01', interval='1h', print_result=True):
        
        print(f"Backtest for {self.symbols} | {start} ~ {end} *{interval}")
        
        limit = 1000000000
        bt = backtester.Backtester(self.symbols, start, end, interval, limit, 0.0025, self._process_data)
        bar = 0
        hdt = (2 if interval == '30m' else 1)
        window = 50 * hdt
        while True:
            raw, data, today = bt.go_next()
            if data == -1:
                break
            
            not_trade = []
            trade_dict = {}
            tech_signal = {}
            serial_signal = {}
            volatility_risk_weight = {}
            
            for symbol in self.symbols:
                trade_dict[symbol] = 0
                tech_signal[symbol] = 0
                serial_signal[symbol] = 0
                volatility_risk_weight[symbol] = 1
            
            if bar != 0 and bar >= window:
                price1, price2 = data["norm_price_series"][self.symbols[0]+"_Price"], data["norm_price_series"][self.symbols[1]+"_Price"]
                price1 = price1[bar - window:bar]
                price2 = price2[bar - window:bar]
                buy_list, sell_list, alpha_ratio = self.OU.get_signal(self.symbols[0], self.symbols[1], price1, price2)
                for b in buy_list:
                    trade_dict[b] += alpha_ratio
                for s in sell_list:
                    trade_dict[s] -= alpha_ratio
            
            if bar > 30 and bar % (hdt*2) == 0:
                self.arima_trend_predictors = ARIMA.create_price_predictor_BT(utils.nplog(raw)[0:bar], self.symbols, self.orders)
                for stock, p in self.arima_trend_predictors.items():
                    y = p.make_forecast(10)
                    a = utils.coef(y)
                    v = a * 300
                    serial_signal[stock] = (v if a > 0 else -v)

            '''
            if bar > 50 and bar % (hdt*2) == 0:
                vfs = GJRGARCH.create_vfs(self.symbols, raw[bar-50:bar])
                for stock, vf in vfs.items():
                    a = utils.coef(vf.make_forecast(30))
                    volatility_risk_weight[stock] = 0.8 if a > 0 else 1.3
            '''
                     
            for symbol in self.symbols:
                hdt = 1 if interval == '1h' else 2
                if bar > self.technical_trend_predictors[symbol].minimal_data_length and (bar - self.technical_trend_predictors[symbol].minimal_data_length) % hdt == 0:
                    trend = self.technical_trend_predictors[symbol].predict(raw.iloc[bar-self.technical_trend_predictors[symbol].minimal_data_length:bar], symbol)
                    tech_signal[symbol] = (1 if trend == 2 else (-1 if trend == 0 else 0))
                    if trend == 1:
                        not_trade.append(symbol)
            
            for symbol in self.symbols:
                trade_dict[symbol] += (serial_signal[symbol] + tech_signal[symbol] / 2)
            
            cash = bt.current_amount
            action_dicts = [utils.preprocess_weights({k: v for k, v in trade_dict.items() if v > 0}, cash, limit), {k: v for k, v in trade_dict.items() if v < 0}]
            
            for stock, alpha in action_dicts[1].items(): # sell
                if stock in not_trade:
                    continue
                alpha_ratio = abs(alpha)
                
                # 하한선 - 얼마 이하가 되면 보충하여 매매
                if alpha_ratio <= 0.03:
                    alpha_ratio = 0.08
                
                bt.sell(stock, alpha_ratio)
            for stock, alpha in action_dicts[0].items(): # buy
                if stock in not_trade:
                    continue
                alpha_ratio = abs(alpha)
                
                # 하한선 - 얼마 이하가 되면 우선하여 매매
                if alpha_ratio <= 0.05:
                    alpha_ratio = 0.1
                bt.buy(stock, alpha_ratio)

            #bt.print_stock_weights()
            bar += 1
        
        if print_result:
            bt.print_result()
            bt.plot_result() 
        else:   
            return bt.print_result(fname='return')
        