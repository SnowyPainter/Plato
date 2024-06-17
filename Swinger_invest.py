from Alpha3.strategy import *
from Alpha4.strategy import *
from Models import model
import backtester
import utils
from Investment import kis, nasdaq

from datetime import datetime
import itertools
import pandas as pd

class SwingerInvest:
    def _process_data(self, raw, norm_raw, bar):
        price_columns = list(map(lambda symbol: symbol+"_Price", self.symbols))
        return {
            "norm_price" : norm_raw[price_columns].iloc[bar],
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

    def __init__(self, symbols, SP_weight, Band_weight, exchange='krx'):
        if exchange == 'nyse':
            self.client = nasdaq.NasdaqClient(symbols[0])
        elif exchange == 'krx':
            self.client = kis.KISClient(symbols[0])
        
        self.symbols = symbols
        self.BSR = BollingerSplitReversal()
        self.SP = StockPair()
        self.SPW = SP_weight
        self.BW = Band_weight
    
        start, end, interval = utils.today_before(30), utils.today(), '1h'
        self.raw_data = self._create_init_data(self.symbols, start, end, interval)
    
    def append_current_data(self):
        df = self._get_current_prices(self.symbols)
        self.raw_data = pd.concat([self.raw_data, df])
        self.current_data = self._process_data(self.raw_data, utils.normalize(self.raw_data), -1)
    
    def action(self):
        trade_dict = {}
        for symbol in self.symbols:
            trade_dict[symbol] = 0
        
        for pair in list(itertools.combinations(self.symbols, 2)):
            buy_list, sell_list = self.SP.action(self.current_data, pair[0], pair[1])
            for stock in buy_list:
                trade_dict[stock] += self.SPW
            for stock in sell_list:
                trade_dict[stock] -= self.SPW
        bands = {}
        for symbol in self.symbols:
            ub, lb, mid = self.BSR.get_bollinger_band(self.raw_data, symbol+"_Price")
            bands[symbol] = {}
            bands[symbol]['ub'] = ub.iloc[-1]
            bands[symbol]['lb'] = lb.iloc[-1]
            bands[symbol]['mid'] = mid.iloc[-1]
        
        trade_strengths = self.BSR.action(self.symbols, self.current_data, bands)
        for symbol, strength in trade_strengths.items():
            if strength > 0:
                trade_dict[symbol] += self.BW
            elif strength < 0:
                trade_dict[symbol] -= self.BW
    
        for stock, score in trade_dict.items():
            alpha_ratio = abs(0.1 * score)
            if score > 0:
                print(f"buy {stock} {alpha_ratio}")
                self.client.buy(stock, self.current_data["price"][stock+"_Price"], alpha_ratio)
            elif score < 0:
                print(f"sell {stock} {alpha_ratio}")
                self.client.sell(stock, self.current_data["price"][stock+"_Price"], alpha_ratio)
        
    def backtest(self):
        bt = backtester.Backtester(self.symbols, '2023-01-01', '2024-01-01', '1h', 10000000, 0.0025, self._process_data)
        bar = 0
        while True:
            raw, data, today = bt.go_next()
            if data == -1:
                break
            
            weights = {}
            for symbol in self.symbols:
                weights[symbol] = 0
            
            trade_strengths = {}
            bands = {}
            if bar >= self.BSR.minimal_window:
                for symbol in self.symbols:
                    ub, lb, mid = self.BSR.get_bollinger_band(raw, symbol+"_Price")
                    bands[symbol] = {}
                    bands[symbol]['ub'] = ub.iloc[bar]
                    bands[symbol]['lb'] = lb.iloc[bar]
                    bands[symbol]['mid'] = mid.iloc[bar]
                trade_strengths = self.BSR.action(self.symbols, data, bands)
            
            for symbol, strength in trade_strengths.items():
                if strength > 0:
                    weights[symbol] += self.BW
                elif strength < 0:
                    weights[symbol] -= self.BW
            
            for pair in list(itertools.combinations(self.symbols, 2)):
                buy_list, sell_list = self.SP.action(data, pair[0], pair[1])
                for stock in buy_list:
                    weights[stock] += self.SPW
                for stock in sell_list:
                    weights[stock] -= self.SPW
            
            for stock, score in weights.items():
                alpha_ratio = abs(0.1 * score)
                if score > 0:
                    bt.buy(stock, alpha_ratio)
                elif score < 0:
                    bt.sell(stock, alpha_ratio)
            
            bar += 1
        bt.print_result()
        bt.plot_result()

long_symbols = ["042700.KS", "000660.KS", "005930.KS"]
phi2 = ["TSLA", "MSFT", "AAPL", "NVDA", "META"]
SPW = 2.5
BW = 5
def bt():
    invester = SwingerInvest(phi2, SPW, BW)
    invester.backtest()
def test():
    invester = SwingerInvest(phi3, SPW, BW, exchange='nyse')
    for i in range(0, 2):
        invester.append_current_data()
        invester.action()