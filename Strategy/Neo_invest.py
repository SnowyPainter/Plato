from Alpha1.strategy import *
from Alpha5.strategy import *

from Models import trend_predictor, ARIMA, volatility_predictor 
import backtester
import utils
from Investment import kis
from Strategy import pair_trade_strategy

from datetime import datetime
import itertools
import math
import numpy as np
import pandas as pd

import warnings
warnings.filterwarnings("ignore")

class NeoInvest(pair_trade_strategy.PairTradeStrategy):
    
    def _vw_apply(self, stock, alpha):
        return alpha * self.volatility_w[stock] + self.news_bias[stock]
    
    def __init__(self, symbol1, symbol2, client, orders={}, nobacktest=False, only_backtest=False):
        pair_trade_strategy.PairTradeStrategy.__init__(self, symbol1, symbol2, client, nobacktest=nobacktest, only_backtest=only_backtest)
        
        data_for_vp = self._create_init_data(self.symbols, utils.today_before(300), utils.today(), '1d')
        
        # Strategies
        self.OU = OU()
        self.technical_trend_predictors = trend_predictor.create_trend_predictors(self.symbols, self.raw_data)
        if not only_backtest:
            self.arima_trend_predictors = ARIMA.create_price_predictor(utils.nplog(self.raw_data).tail(60), self.symbols)
        self.volatility_predictors = volatility_predictor.create_volatility_predictors(self.symbols, data_for_vp)
        self.volatilities = {}
        self.volatility_w = {}
        self.news_bias = {}
        for symbol in self.symbols:
            self.news_bias[symbol] = 0
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

    def action(self, hour_divided_time=1):
        window = hour_divided_time * 52
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
        
        if self.bar % hour_divided_time == 0:
            text += "Technical alpha \n"
            for symbol in self.symbols:
                if not (symbol in self.technical_trend_predictors):
                    continue
                trend = self.technical_trend_predictors[symbol].predict(self.raw_data.tail(self.technical_trend_predictors[symbol].minimal_data_length), symbol)
                text += f"[Tech] {symbol} goes {('Up' if trend == 2 else ('Down' if trend == 0 else 'Sideway'))} \n"
                tech_signal[symbol] = (0.6 if trend == 2 else (-0.6 if trend == 0 else 0))
                if trend == 1:
                    not_trade.append(symbol)
        if self.bar % hour_divided_time == 0:
            text += "ARIMA alpha \n"
            for stock, p in self.arima_trend_predictors.items():
                y = p.make_forecast(10)
                x = np.arange(len(y))
                coefficients = np.polyfit(x, y, 1)
                v = coefficients[0] * 300
                serial_signal[stock] = (v if coefficients[0] > 0 else -v)
                text += f"[ARIMA] {stock} goes {('Up' if coefficients[0] > 0 else 'Down')} | W:{(v if coefficients[0] > 0 else -v)} \n"
        
        if self.bar > 0 and self.bar % (hour_divided_time * 3) == 0:
            text += "Volatility alpha \n"
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
        