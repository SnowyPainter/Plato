from Alpha5.strategy import *

from Models import model
import backtester
import utils
from Investment import kis

from datetime import datetime
import itertools
import pandas as pd

class NeoInvest:
    def _process_data(self, raw, norm_raw, bar):
        price_columns = list(map(lambda symbol: symbol+"_Price", self.symbols))
        return {
            "norm_price_series" : norm_raw[price_columns],
            "price" : raw[price_columns].iloc[bar]
        }
    def _get_current_prices(self, symbols):
        df = {}
        for symbol in symbols:
            code = symbol.split('.')[0]
            df[symbol+"_Price"] = self.client.get_price(code)
        df = pd.DataFrame(df, index=[datetime.now()])
        return df
    def _create_init_data(self, symbols, start, end, interval):
        raw_data, symbols = utils.load_historical_datas(symbols, start, end, interval)
        raw_data.index = pd.to_datetime(raw_data.index).tz_localize(None)
        raw_data.drop(columns=[col for col in raw_data.columns if col.endswith('_Volume')], inplace=True)
        return raw_data

    def __init__(self, symbol1, symbol2, current_amount):
        self.symbols = [symbol1, symbol2]
        self.client = kis.KISClient(self.symbols[0], current_amount)
        
        self.OU = OU()
        start, end, interval = utils.today_before(50), utils.today(), '1h'
        self.raw_data = self._create_init_data(self.symbols, start, end, interval)
        
    def append_current_data(self):
        df = self._get_current_prices(self.symbols)
        self.raw_data = pd.concat([self.raw_data, df])
        self.current_data = self._process_data(self.raw_data, utils.normalize(self.raw_data), -1)
    
    def action(self):
        window = 62
        norm_raw = utils.normalize(self.raw_data)
        price1 = norm_raw[self.symbols[0]+"_Price"].tail(window)
        price2 = norm_raw[self.symbols[1]+"_Price"].tail(window)
        
        buy_list, sell_list, alpha_ratio = self.OU.get_signal(self.symbols[0], self.symbols[1], price1, price2)
        for b in buy_list:
            print("Buy ", b)
            self.client.buy(b, self.current_data["price"][b+"_Price"], alpha_ratio)
        for s in sell_list:
            print("Sell ", s)
            self.client.sell(s, self.current_data["price"][s+"_Price"], alpha_ratio)
        
    def backtest(self, start='2023-01-01', end='2024-01-01', interval='1h', print_result=True):
        bt = backtester.Backtester(self.symbols, start, end, interval, 10000000, 0.0025, self._process_data)
        bar = 0
        window = 62

        while True:
            raw, data, today = bt.go_next()
            if data == -1:
                break
            
            if bar != 0 and bar >= window:
                price1, price2 = data["norm_price_series"][self.symbols[0]+"_Price"], data["norm_price_series"][self.symbols[1]+"_Price"]
                price1 = price1[bar - window:bar]
                price2 = price2[bar - window:bar]
                buy_list, sell_list, alpha_ratio = self.OU.get_signal(self.symbols[0], self.symbols[1], price1, price2)

                for b in buy_list:
                    bt.buy(b, alpha_ratio)
                for s in sell_list:
                    bt.sell(s, alpha_ratio)    
            bt.print_stock_weights()
            bar += 1
        
        if print_result:
            bt.print_result()
            bt.plot_result() 
        else:   
            return bt.print_result(fname='return')
        