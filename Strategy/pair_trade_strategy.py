from abc import ABC, abstractmethod
import utils

from datetime import datetime
import itertools
import math
import numpy as np
import pandas as pd

import warnings
warnings.filterwarnings("ignore")

class PairTradeStrategy(ABC):
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
    
    def __init__(self, symbol1, symbol2, client, nobacktest=False, only_backtest=False):
        self.symbols = [symbol1, symbol2]
        self.client = client
        start, end, interval = utils.today_before(50), utils.today(), '30m'
        self.raw_data = self._create_init_data(self.symbols, start, end, interval)
        self.bar = 0

    def get_information(self):
        text = f"MOA: {self.client.max_operate_amount}\n"
        text += f"Stocks: {self.client.stocks_qty}\n"
        text += f"AVGP: {self.client.stocks_avg_price}\n"
        text += f"Cash: {self.client.max_operate_cash()}\n"
        text += f"Bar: {self.bar}\n"
        return text
    
    def append_current_data(self):
        df = self._get_current_prices(self.symbols)
        self.raw_data = pd.concat([self.raw_data, df])
        self.current_data = self._process_data(self.raw_data, utils.normalize(self.raw_data), -1)
    
    @abstractmethod
    def action(self, hour_divided_time=1):
        pass
    
    @abstractmethod
    def backtest(self, start='2023-01-01', end='2024-01-01', interval='1h', print_result=True, seperated=False, show_plot=True, show_result=True, show_only_text=False):
        pass
        