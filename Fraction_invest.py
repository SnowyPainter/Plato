from Alpha1.strategy import *
from Alpha3.strategy import *
from Alpha4.strategy import *
from Models import model
import backtester
import utils
from Investment import kis

from datetime import datetime
import itertools
import pandas as pd

class FractionInvest:
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

    def __init__(self, symbols, Pair_weight, Band_weight, MA_weight, current_amount):

        self.pairs = symbols["pairs"]
        self.long = symbols["long"]
        self.symbols = self.long + [element for tup in self.pairs for element in tup]
        self.client = kis.KISClient(self.symbols[0], current_amount)
        
        self.MABT = MABreakThrough()
        self.BSR = BollingerSplitReversal()
        self.SP = StockPair()
        
        self.MABTW = MA_weight
        self.SPW = Pair_weight
        self.BW = Band_weight
        start, end, interval = utils.today_before(90), utils.today(), '1h'
        self.raw_data = self._create_init_data(self.symbols, start, end, interval)
        self.ban_trade = {}
        for symbol in self.symbols:
            self.ban_trade[symbol] = 0
        
    def append_current_data(self):
        df = self._get_current_prices(self.symbols)
        self.raw_data = pd.concat([self.raw_data, df])
        self.current_data = self._process_data(self.raw_data, utils.normalize(self.raw_data), -1)
    
    def action(self):
        weights = {}
        for stock, _ in self.ban_trade.items():
            self.ban_trade[stock] -= 1
        
        for symbol in self.symbols:
            weights[symbol] = 0
        
        for pair in self.pairs:
            buy_list, sell_list = self.SP.action(self.current_data, pair[0], pair[1])
            for stock in buy_list:
                weights[stock] += self.SPW
            for stock in sell_list:
                weights[stock] -= self.SPW
        
        buy_list, sell_list = self.MABT.action(self.symbols, self.current_data)
        for stock in buy_list:
            weights[stock] += self.MABTW
        for stock in sell_list:
            weights[stock] -= self.MABTW
        
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
                weights[symbol] += self.BW
            elif strength < 0:
                weights[symbol] -= self.BW
        
        for stock, turns in self.ban_trade.items():
            if turns > 0:
                weights[stock] = 0
        
        alphas = {key:0.1 * (value) for key, value in weights.items()}
        print(alphas)
        action_dicts = [utils.process_weights({k: v for k, v in alphas.items() if v > 0}), {k: v for k, v in alphas.items() if v < 0}]
        for stock, alpha in action_dicts[1].items(): # sell
            alpha_ratio = abs(alpha)
            print(f"sell {stock} {alpha_ratio}")
            self.client.sell(stock, self.current_data["price"][stock+"_Price"], alpha_ratio)
        for stock, alpha in action_dicts[0].items(): # buy
            alpha_ratio = abs(alpha)
            print(f"buy {stock} {alpha_ratio}")
            self.client.buy(stock, self.current_data["price"][stock+"_Price"], alpha_ratio)
        
    def backtest(self, interval='1h'):
        bt = backtester.Backtester(self.symbols, '2023-01-01', '2024-01-01', interval, 10000000, 0.0025, self._process_data)
        bar = 0
        
        ban_trade = {}
        for symbol in self.symbols:
            ban_trade[symbol] = 0
        
        while True:
            raw, data, today = bt.go_next()
            if data == -1:
                break
            
            weights = {}
            for stock, _ in ban_trade.items():
                ban_trade[stock] -= 1
            for symbol in self.symbols:
                weights[symbol] = 0
            
            for pair in self.pairs:
                buy_list, sell_list = self.SP.action(data, pair[0], pair[1])
                for stock in buy_list:
                    weights[stock] += self.SPW
                for stock in sell_list:
                    weights[stock] -= self.SPW
            
            buy_list, sell_list = self.MABT.action(self.long, data)
            for stock in buy_list:
                weights[stock] += self.MABTW
            for stock in sell_list:
                weights[stock] -= self.MABTW

            bands = {}
            for symbol in self.symbols:
                ub, lb, mid = self.BSR.get_bollinger_band(self.raw_data, symbol+"_Price")
                bands[symbol] = {}
                bands[symbol]['ub'] = ub.iloc[-1]
                bands[symbol]['lb'] = lb.iloc[-1]
                bands[symbol]['mid'] = mid.iloc[-1]
            trade_strengths = self.BSR.action(self.symbols, data, bands)
            for symbol, strength in trade_strengths.items():
                if strength > 0:
                    weights[symbol] += self.BW
                elif strength < 0:
                    weights[symbol] -= self.BW
            
            for stock, turns in ban_trade.items():
                if turns > 0:
                    weights[stock] = 0
            
            alphas = {key:0.1 * (value) for key, value in weights.items()}
            action_dicts = [utils.process_weights({k: v for k, v in alphas.items() if v > 0}), {k: v for k, v in alphas.items() if v < 0}]
            
            for stock, alpha in action_dicts[1].items(): # sell
                alpha_ratio = abs(alpha)
                bt.sell(stock, alpha_ratio)
            for stock, alpha in action_dicts[0].items(): # buy
                alpha_ratio = abs(alpha)
                bt.buy(stock, alpha_ratio)
            
            bt.print_stock_weights()
            
            bar += 1
        bt.print_result()
        bt.plot_result()