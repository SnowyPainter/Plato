import pandas as pd
import yfinance as yf
import pytz
from datetime import datetime, timedelta, time
import math, utils
import numpy as np

class Backtester:
    def _load_historical_data(self, symbol, start, end):
        d = yf.download(symbol, start=start, end=end)
        d.rename(columns={'Open': symbol+'_Price', 'Volume' : symbol+"_Volume"}, inplace=True)
        d.index = pd.to_datetime(d.index, format="%Y-%m-%d %H:%M:%S%z")
        return d[[symbol+'_Price', symbol+"_Volume"]]
    def _load_historical_datas(self, symbols, start, end):
        dfs = []
        for symbol in symbols:
            dfs.append(self._load_historical_data(symbol, start, end))
        return utils.merge_dfs(dfs)
    
    def _normalize_raw_data(self):
        mean, std = self.raw_data.mean(), self.raw_data.std()
        return (self.raw_data - mean) / std
    
    def _max_units_could_affordable(self, ratio, init_amount, current_amount, price, fee):
        money = init_amount * ratio * (1+fee)
        if current_amount >= money:
            return math.floor(money / price)
        else:
            return math.floor(current_amount / price)
    def _max_units_could_sell(self, ratio, init_amount, current_units, price, fee):
        money = init_amount * ratio * (1+fee)
        units = math.floor(money / price)
        if current_units > units:
            return units
        else:
            return current_units
            
    def __init__(self, symbols, start, end, initial_amount, fee, data_proc_func):
        self.init_amount = initial_amount
        self.evaluated_amount = initial_amount
        self.current_amount = initial_amount
        self.fee = fee
        self.symbols = symbols
        self.raw_data = self._load_historical_datas(symbols, start, end)
        self.data_proc_func = data_proc_func
        self.portfolio_returns = []
        self.price = {}
        self.entry_price = {}
        self.units = {}
        self.logs = []
        for symbol in symbols:
            self.price[symbol] = 0
            self.entry_price[symbol] = 0
            self.units[symbol] = 0    
        self.bar = 0
        self.trade = 0
    
    def print_result(self, fname=''):
        end_return = self.portfolio_returns[-1]
        worst_return = min(self.portfolio_returns)
        best_return = max(self.portfolio_returns)
        mean_return = np.mean(self.portfolio_returns)
        std_return = np.std(self.portfolio_returns)
        sharp_ratio = mean_return / std_return
        text = f"End Return : {end_return} \n"
        text += f"Worst ~ Best return {worst_return} ~ {best_return} \n"
        text += f"Shart Ratio : {sharp_ratio}\n"
        print(text)
    
    def go_next(self):
        if self.bar >= self.raw_data.shape[0]:
            return -1
        self.evaluated_amount = self.current_amount
        for symbol in self.symbols:
            self.price[symbol] = self.raw_data[symbol+"_Price"].iloc[self.bar]
            self.evaluated_amount += self.units[symbol] * self.price[symbol]
    
        self.portfolio_returns.append((self.evaluated_amount - self.init_amount) / self.init_amount)
        self.bar += 1
        return self.data_proc_func(self.raw_data, self.bar - 1)
    
    def buy(self, symbol, ratio=0.1):
        units = self._max_units_could_affordable(ratio, self.init_amount, self.current_amount, self.price[symbol], self.fee)
        bar = self.bar - 1
        if units > 0:
            self.current_amount -= (self.price[symbol] * units * (1 + self.fee))
            self.units[symbol] += units
            if self.entry_price[symbol] == 0:
                self.entry_price[symbol] = self.price[symbol]
            else:
                self.entry_price[symbol] = (self.entry_price[symbol] + (self.price[symbol] * units)) / (units + 1)
            self.logs.append({
                "bar": bar,
                "action" : "buy",
                "amount" : units,
                "avg_price" : self.entry_price[symbol]
            })
            self.trade += 1
    
    def sell(self, symbol, ratio=0.1):
        units = self._max_units_could_sell(ratio, self.init_amount, self.units[symbol], self.price[symbol], self.fee)
        bar = self.bar - 1
        if units > 0:
            self.current_amount += (self.price[symbol] * units * (1 - self.fee))
            self.units[symbol] -= units
            self.logs.append({
                "bar" : bar,
                "action" : "sell",
                "amount" : units,
                "profit" : (self.price[symbol] - self.entry_price[symbol]) / self.entry_price[symbol]
            })
            self.trade += 1