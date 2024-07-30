from Alpha1.strategy import *
from Alpha5.strategy import *

from Models import trend_predictor, ARIMA, volatility_predictor 
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
    
    def _vw_apply(self, stock, alpha):
        return alpha * self.volatility_w[stock]
    
    def __init__(self, symbol1, symbol2, max_operate_amount, orders={}, nobacktest=False, nolog=False, only_backtest=False):
        self.symbols = [symbol1, symbol2]
        self.client = kis.KISClient(self.symbols, max_operate_amount, nolog)
        self.OU = OU()
        start, end, interval = utils.today_before(50), utils.today(), '30m'
        self.raw_data = self._create_init_data(self.symbols, start, end, interval)
        data_for_vp = self._create_init_data(self.symbols, utils.today_before(300), utils.today(), '1d')
        self.technical_trend_predictors = trend_predictor.create_trend_predictors(self.symbols, self.raw_data)
        if not only_backtest:
            self.arima_trend_predictors = ARIMA.create_price_predictor(utils.nplog(self.raw_data).tail(60), self.symbols)
        self.volatility_predictors = volatility_predictor.create_volatility_predictors(self.symbols, data_for_vp)
        self.volatilities = {}
        self.volatility_w = {}
        for symbol in self.symbols:
            self.volatilities[symbol] = []
            self.volatilities[symbol].append(self.volatility_predictors[symbol].predict(self.raw_data.tail(12)))
            self.volatility_w[symbol] = 1
        
        self.orders = orders
        if not (symbol1 in orders) or not (symbol2 in orders) or (self.orders == {} and not nobacktest):
            self.orders = utils.get_saved_orders(self.symbols)
            if self.orders == {}:
                print(f"Get Params for Backtest")
                ARIMA.create_price_predictor_BT(utils.nplog(self.raw_data), self.symbols, {})
                self.orders = utils.get_saved_orders(self.symbols)
        self.bar = 0

    def get_information(self):
        text = f"MOA: {self.client.max_operate_amount}\n"
        text += f"Stocks: {self.client.stocks_qty}\n"
        text += f"AVGP: {self.client.stocks_avg_price}\n"
        text += f"Cash: {self.client.max_operate_cash()}\n"
        text += f"Bar: {self.bar}\n"
        return text
    
    def update_max_operate_amount(self, amount):
        self.client.update_max_operate_amount(amount)
    
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
        
        text += "Pair Trade ALPHA \n"
        text += f"[OU] Buy {buy_list} | Sell {sell_list} | Alpha : {alpha_ratio} \n"
        text += "\n"
        for b in buy_list:
            trade_dict[b] += alpha_ratio
        for s in sell_list:
            trade_dict[s] -= alpha_ratio
        
        text += "Models ALPHA \n"
        
        if self.bar % hour_divided_time == 0:
            for symbol in self.symbols:
                if not (symbol in self.technical_trend_predictors):
                    continue
                trend = self.technical_trend_predictors[symbol].predict(self.raw_data.tail(self.technical_trend_predictors[symbol].minimal_data_length), symbol)
                text += f"[Tech] {symbol} goes {('Up' if trend == 2 else ('Down' if trend == 0 else 'Sideway'))} \n"
                tech_signal[symbol] = (0.6 if trend == 2 else (-0.6 if trend == 0 else 0))
                if trend == 1:
                    not_trade.append(symbol)
        if self.bar % hour_divided_time == 0:
            for stock, p in self.arima_trend_predictors.items():
                y = p.make_forecast(10)
                x = np.arange(len(y))
                coefficients = np.polyfit(x, y, 1)
                v = coefficients[0] * 300
                serial_signal[stock] = (v if coefficients[0] > 0 else -v)
                text += f"[ARIMA] {stock} goes {('Up' if coefficients[0] > 0 else 'Down')} | W:{(v if coefficients[0] > 0 else -v)} \n"
        
        if self.bar > 0 and self.bar % (hour_divided_time * 3) == 0:
            for symbol in self.symbols:
                self.volatilities[symbol].append(self.volatility_predictors[symbol].predict(self.raw_data.tail(hour_divided_time*6)))
                self.volatility_w[symbol] = 0.9 if self.volatilities[symbol][-1] - self.volatilities[symbol][-2] > 0 else 2
                text += f"[Volatility Predictor] {symbol} w: {self.volatility_w[symbol]}\n"
        for symbol in self.symbols:
            trade_dict[symbol] += (serial_signal[symbol] + tech_signal[symbol]) / 2
        
        cash, limit = self.client.max_operate_cash(), self.client.max_operate_amount
        action_dicts = [utils.preprocess_weights({k: self._vw_apply(k, v) for k, v in trade_dict.items() if v > 0}, cash, limit), 
                        {k: self._vw_apply(k, v) for k, v in trade_dict.items() if v < 0}]
        
        text += "\n"
        
        for stock, alpha in action_dicts[1].items(): # sell
            if stock in not_trade:
                continue
            alpha_ratio = min(abs(alpha), 1)
            qty = self.client.sell(stock, self.current_data["price"][stock+"_Price"], alpha_ratio)
            text += f"Sell {stock}, ratio: {alpha_ratio}, qty: {qty}\n"
        for stock, alpha in action_dicts[0].items(): # buy
            if stock in not_trade:
                continue
            alpha_ratio = min(abs(alpha), 1)
            qty = self.client.buy(stock, self.current_data["price"][stock+"_Price"], alpha_ratio)
            text += f"Buy {stock}, ratio: {alpha_ratio}, qty: {qty}\n"
        
        self.bar += 1
        print(text)
        return text
        
    def backtest(self, start='2023-01-01', end='2024-01-01', interval='1h', print_result=True, seperated=False, show_plot=True, show_result=True, show_only_text=False):
        
        print(f"Backtest for {self.symbols} | {start} ~ {end} *{interval}")
        
        limit = 1000000000
        bt = backtester.Backtester(self.symbols, start, end, interval, limit, 0.0025, self._process_data)
        bar = 0
        hdt = (2 if interval == '30m' else 1)
        day_t = 6 * hdt
        window = 50 * hdt
        volatilities = {}
        volatility_w = {}
            
        for symbol in self.symbols:
            volatilities[symbol] = []
            volatilities[symbol].append(self.volatility_predictors[symbol].predict(bt.raw_data[0:day_t]))
            volatility_w[symbol] = 1
        
        while True:
            raw, data, today = bt.go_next()
            if data == -1:
                break
            
            not_trade = []
            trade_dict = {}
            tech_signal = {}
            serial_signal = {}

            for symbol in self.symbols:
                trade_dict[symbol] = 0
                tech_signal[symbol] = 0
                serial_signal[symbol] = 0

                
            if bar != 0 and bar >= window:
                price1, price2 = data["norm_price_series"][self.symbols[0]+"_Price"], data["norm_price_series"][self.symbols[1]+"_Price"]
                price1 = price1[bar - window:bar]
                price2 = price2[bar - window:bar]
                buy_list, sell_list, alpha_ratio = self.OU.get_signal(self.symbols[0], self.symbols[1], price1, price2)
                for b in buy_list:
                    trade_dict[b] += alpha_ratio
                for s in sell_list:
                    trade_dict[s] -= alpha_ratio
            
            if bar > 30 and bar % hdt == 0:
                self.arima_trend_predictors = ARIMA.create_price_predictor_BT(utils.nplog(raw)[0:bar], self.symbols, self.orders)
                for stock, p in self.arima_trend_predictors.items():
                    y = p.make_forecast(day_t)
                    a = utils.coef(y)
                    v = a * 300
                    serial_signal[stock] = (v if a > 0 else -v)

            for symbol in self.symbols:
                hdt = 1 if interval == '1h' else 2
                if bar > self.technical_trend_predictors[symbol].minimal_data_length and (bar - self.technical_trend_predictors[symbol].minimal_data_length) % hdt == 0:
                    trend = self.technical_trend_predictors[symbol].predict(raw.iloc[bar-self.technical_trend_predictors[symbol].minimal_data_length:bar], symbol)
                    tech_signal[symbol] = (1 if trend == 2 else (-1 if trend == 0 else 0))
                    if trend == 1:
                        not_trade.append(symbol)
            
            if bar > 0 and bar % day_t == 0:
                for symbol in self.symbols:
                    volatilities[symbol].append(self.volatility_predictors[symbol].predict(raw[bar - day_t:bar]))
                    volatility_w[symbol] = 0.9 if volatilities[symbol][-1] - volatilities[symbol][-2] > 0 else 2
            
            for symbol in self.symbols:
                trade_dict[symbol] += (serial_signal[symbol] + tech_signal[symbol] / 2)
            
            cash = bt.current_amount
            action_dicts = [utils.preprocess_weights({k: self._vw_apply(k, v) for k, v in trade_dict.items() if v > 0}, cash, limit), 
                            {k: self._vw_apply(k, v) for k, v in trade_dict.items() if v < 0}]
            
            for stock, alpha in action_dicts[1].items(): # sell
                if stock in not_trade:
                    continue
                alpha_ratio = abs(alpha)
                # 하한선 - 얼마 이하가 되면 보충하여 매매
                if alpha_ratio <= 0.05:
                    alpha_ratio = 0.1
                
                bt.sell(stock, alpha_ratio)
            for stock, alpha in action_dicts[0].items(): # buy
                if stock in not_trade:
                    continue
                alpha_ratio = abs(alpha)

                # 하한선 - 얼마 이하가 되면 우선하여 매매
                if alpha_ratio <= 0.05:
                    alpha_ratio = 0.1

                bt.buy(stock, alpha_ratio)

            bt.print_stock_weights()
            bar += 1
        
        if show_only_text:
            return bt.print_result('for_show')
        else:
            if print_result:
                if show_result:
                    bt.print_result()
                if show_plot:
                    bt.plot_result() 
            else:   
                if seperated:
                    return bt.print_result(fname='sum')
                return bt.print_result(fname='return')
        