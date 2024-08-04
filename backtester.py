import pandas as pd
import yfinance as yf
import pytz
from datetime import datetime, timedelta, time
import math, utils
import numpy as np
import matplotlib.pyplot as plt
import mplcursors

class Backtester:
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
    
    def __init__(self, symbols, start, end, interval, initial_amount, fee, data_proc_func):
        self.init_amount = initial_amount
        self.evaluated_amount = initial_amount
        self.current_amount = initial_amount
        self.fee = fee
        self.raw_data, symbols = utils.load_historical_datas(symbols, start, end, interval)
        self.symbols = symbols
        self.start, self.end, self.interval = start, end, interval
        self.data_proc_func = data_proc_func
        self.portfolio_evaluates = []
        self.portfolio_returns = []
        self.protfolio_stock_profits = {}
        self.portfolio_infos = {f"{symbol}_Weight": [] for symbol in symbols}
        self.profit_history = []
        for symbol in symbols:
            self.protfolio_stock_profits[symbol] = []
        self.price = {}
        self.entry_price = {}
        self.units = {}
        self.trades = pd.DataFrame({
            "bar" : [],
            "stock" : [],
            "action" : [],
            "stock" : [],
            "profit" : []
        })
        for symbol in symbols:
            self.price[symbol] = 0
            self.entry_price[symbol] = 0
            self.units[symbol] = 0    
        self.bar = 0
        self.trade_count = 0
    
    def print_stock_weights(self):
        total_units = sum(self.units.values())
        for stock, unit in self.units.items():
            if total_units > 0:
                weight = unit / total_units * 100
            else:
                weight = 0
            print(f"{stock}: {weight:.2f}% |", end='')
        print(f' - {self.bar} / {len(self.raw_data)}')
    
    def weight_of_stock(self, stock):
        total_units = sum(self.units.values())
        return self.units[stock] / total_units
    
    def profit_of_stock(self, stock):
        if self.entry_price[stock] == 0:
            return 0
        return (self.price[stock] - self.entry_price[stock]) / self.entry_price[stock]
    
    def print_result(self, fname=''):
        self.portfolio_returns = np.array(self.portfolio_returns)
        self.portfolio_returns[np.isnan(self.portfolio_returns)] = 0.0
        end_return, best_return, worst_return, sharp_ratio, VaR = utils.get_bt_result(self.portfolio_returns, self.portfolio_evaluates, self.init_amount)
        VaR = round(VaR, 2)
        text = ""
        text += f"======= {self.symbols[0]} and {self.symbols[1]} =======\n"
        text += f"Backtest range {self.start} ~ {self.end} : {self.interval} \n"
        text += f"Trade Count : {self.trade_count}\n"
        text += f"End Return : {end_return * 100:.2f} % \n"
        text += f"Worst ~ Best return {worst_return * 100:.2f} ~ {best_return * 100:.2f} % \n\n"
        text += f"Sharp Ratio : {sharp_ratio :.4f}\n"
        text += f"VaR : {utils.korean_currency_format(VaR)} / {utils.korean_currency_format(self.init_amount)}\n\n"
        
        for symbol in self.symbols:
            profits = self.protfolio_stock_profits[symbol]
            total_return = 1.0
            for r in profits:
                total_return *= (1 + r)
            total_return -= 1
            text += f"{symbol} Profit : {total_return*100:.2f} %\n"

        if fname == '':
            print(text)
        elif fname == 'return':
            return {
                'sharp' : sharp_ratio,
                'end' : end_return,
                'worst' : worst_return,
                'best' : best_return,
                'trades' : self.trade_count,
                'VaR' : VaR
            }
        elif fname == 'sum':
            return {
                "index": self.raw_data.index,
                "evlus": self.portfolio_evaluates, 
                "returns": self.portfolio_returns,
                "ph": self.profit_history
            }
        elif fname == 'for_show':
            return text
        else:
            with open(fname, 'w') as f:
                f.write(text)

    def plot_result(self):
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        norm_raw = utils.normalize(self.raw_data)
         
        for symbol in self.symbols:
            ax1.plot(self.raw_data.index, norm_raw[symbol+"_Price"], label=symbol)
        ax1.set_xlabel('Date')
        
        self.portfolio_evaluates = np.array(self.portfolio_evaluates)
        self.portfolio_evaluates[np.isnan(self.portfolio_evaluates)] = 0.0
        mean = np.mean(self.portfolio_evaluates)
        std = np.std(self.portfolio_evaluates)
        norm_evalu = (self.portfolio_evaluates - mean) / std
        
        for symbol in self.symbols:
            spec_symbol_signals = self.trades[self.trades['stock'] == symbol]
            buy_signals = spec_symbol_signals[spec_symbol_signals['action'] == 'buy']
            sell_signals = spec_symbol_signals[spec_symbol_signals['action'] == 'sell']
            for signal, marker, color in zip([buy_signals, sell_signals], ['^', 'v'], ['green', 'red']):
                x = [signal.index[int(i)] for i in signal['bar']]
                y = [norm_raw[symbol+"_Price"].iloc[int(i)] for i in signal['bar']]
                ax1.scatter(x, y, color=color, marker=marker, s=30, label=f"{symbol} {'Bought' if color == 'green' else 'Sold'}")
                
        ax2.plot(self.raw_data.index, norm_evalu, 'k-', label='Evaluated Asset Value')
        ax2.set_ylabel('Evaluated Asset Value', color='k')
        
        ax3 = ax2.twinx()
        for symbol in self.symbols:
            ax3.plot(self.raw_data.index, self.portfolio_infos[f"{symbol}_Weight"], label=f"{symbol}")
        
        ph_dates = self.raw_data.index[:len(self.profit_history)]
        ph_colors = ['green' if value >= 0 else 'red' for value in self.profit_history]
        ax4 = ax2.twinx()
        for i in range(len(ph_dates) - 1):
            ax4.fill_between(ph_dates[i:i + 2], [0, 0], [self.profit_history[i], self.profit_history[i + 1]], step='post', color=ph_colors[i], alpha=0.5)
        
        
        signal_data = []
        scatter_data = []
        for action, marker, color in zip(['buy', 'sell'], ['^', 'v'], ['green', 'red']):
            signals = self.trades[self.trades['action'] == action]
            signal_data.append(signals)
            x = [signals.index[int(i)] for i in signals['bar']]
            y = [norm_evalu[int(i)] for i in signals['bar']]
            scatter_data.append(ax2.scatter(x, y, color=color, marker=marker, s=50, label=f"{'Bought' if color == 'green' else 'Sold'}"))
        
        cursor = mplcursors.cursor(scatter_data[0], hover=True)
        @cursor.connect("add")
        def buy_scatter_hover(sel):
            index = sel.index
            sel.annotation.set(text=f"Amount: {signal_data[0]['amount'].iloc[index]}")
            sel.annotation.get_bbox_patch().set(fc="white", alpha=0.9)
        
        cursor2 = mplcursors.cursor(scatter_data[1], hover=True)
        @cursor2.connect("add")
        def sell_scatter_hover(sel):
            index = sel.index
            sel.annotation.set(text=f"Profit: {signal_data[1]['profit'].iloc[index]}")
            sel.annotation.get_bbox_patch().set(fc="white", alpha=0.9)
        
        fig.tight_layout()
        ax1.legend(loc='upper left')
        ax2.legend(loc='upper right')
        ax3.legend(loc='lower right')
        ax4.legend(loc='upper left')
        
        plt.title('Stock Price, Trade Signals, and Asset Value Over Time')
        plt.show()
    
    def go_next(self):
        if self.bar >= self.raw_data.shape[0]:
            return -1, -1, datetime.now()
        self.evaluated_amount = self.current_amount
        for symbol in self.symbols:
            self.price[symbol] = self.raw_data[symbol+"_Price"].iloc[self.bar]
            self.evaluated_amount += self.units[symbol] * self.price[symbol]
        
        total_units = sum(self.units.values())
        for stock, unit in self.units.items():
            if total_units > 0:
                weight = unit / total_units * 100
            else:
                weight = 0
            self.portfolio_infos[f"{stock}_Weight"].append(weight)
        self.portfolio_evaluates.append(self.evaluated_amount)
        
        if len(self.portfolio_evaluates) > 1:
            self.profit_history.append((self.portfolio_evaluates[-1] - self.portfolio_evaluates[-2]) / self.portfolio_evaluates[-1])
        
        self.portfolio_returns.append((self.evaluated_amount - self.init_amount) / self.init_amount)
        self.bar += 1
        return self.raw_data, self.data_proc_func(self.raw_data, utils.normalize(self.raw_data), self.bar - 1), self.raw_data.index[self.bar - 1]
    
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
            self.trades = pd.concat([self.trades, pd.DataFrame({
                "bar": bar,
                "action" : "buy",
                "amount" : units,
                "stock" : symbol,
                "profit" : -0.0025
            }, index=self.raw_data.index)])
            self.trade_count += 1
    
    def sell(self, symbol, ratio=0.1):
        units = self._max_units_could_sell(ratio, self.init_amount, self.units[symbol], self.price[symbol], self.fee)
        bar = self.bar - 1
        if units > 0:
            self.current_amount += (self.price[symbol] * units * (1 - self.fee))
            profit = (self.price[symbol] - self.entry_price[symbol]) / self.entry_price[symbol]
            self.protfolio_stock_profits[symbol].append(profit)
            self.units[symbol] -= units
            if self.units[symbol] <= 0:
                self.entry_price[symbol] = 0
            self.trades = pd.concat([self.trades, pd.DataFrame({
                "bar" : bar,
                "action" : "sell",
                "amount" : units,
                "stock" : symbol,
                "profit" : profit
            }, index=self.raw_data.index)])
            self.trade_count += 1
            
def mutil_bt_plot(index, evlus, ph, title=''):
    ax = plt.subplot()

    evlus[np.isnan(evlus)] = 0.0
    mean = np.mean(evlus)
    std = np.std(evlus)
    norm_evalu = (evlus - mean) / std

    ax.plot(index, norm_evalu, 'k-', label='Evaluated Asset Value')
    ax.set_ylabel('Evaluated Asset Value', color='k')

    ph_dates = index[:len(ph)]
    ph_colors = ['green' if value >= 0 else 'red' for value in ph]
    ax1 = ax.twinx()
    for i in range(len(ph_dates) - 1):
        ax1.fill_between(ph_dates[i:i + 2], [0, 0], [ph[i], ph[i + 1]], step='post', color=ph_colors[i], alpha=0.5)
    
    ax.legend(loc='upper right')
    ax1.legend(loc='upper left')
    
    plt.title(f'{title}')
    plt.show()

def multi_bt_result_print(returns, evlus, init_amount):
    returns = np.array(returns)
    returns[np.isnan(returns)] = 0.0
    end_return, best_return, worst_return, sharp_ratio, VaR = utils.get_bt_result(returns, evlus, init_amount)
    VaR = round(VaR, 2)
    text = ""
    text += f"End Return : {end_return * 100:.2f} % \n"
    text += f"Worst ~ Best return {worst_return * 100:.2f} ~ {best_return * 100:.2f} % \n\n"
    text += f"Sharp Ratio : {sharp_ratio :.4f}\n"
    text += f"VaR : {utils.korean_currency_format(VaR)} / {utils.korean_currency_format(init_amount)}\n\n"
    print(text)
    return text