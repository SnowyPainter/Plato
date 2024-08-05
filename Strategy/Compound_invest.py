import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from Strategy import pair_trade_strategy
from Alpha5.strategy import *
import backtester
import utils
from scipy.optimize import minimize
from scipy.stats import norm

class CompoundInvest(pair_trade_strategy.PairTradeStrategy):
    def _simulate_cir_process(self, theta, mu, sigma, X0, T, dt, N):
        t = np.linspace(0, T, N)
        X = np.zeros(N)
        X[0] = X0
        for i in range(1, N):
            dW = np.random.normal(0, np.sqrt(dt))
            X[i] = X[i-1] + theta * (mu - X[i-1]) * dt + sigma * np.sqrt(X[i-1]) * dW
            if X[i] < 0:
                X[i] = 0  # CIR 모델에서 음수 값 방지
        return t, X
    
    def _log_likelihood(self, params, prices, spreads, dt):
        kappa0, kappa1, theta, sigma = params
        n = len(prices)
        
        likelihood = 0
        for i in range(1, n):
            r_t = prices[i-1]
            r_t_next = prices[i]
            S_t = spreads[i-1]
            kappa = kappa0 + kappa1 * S_t
            mu = kappa * (theta - r_t) * dt
            variance = sigma ** 2 * r_t * dt
            if variance > 0:
                likelihood += -0.5 * np.log(2 * np.pi * variance) - (r_t_next - r_t - mu) ** 2 / (2 * variance)
        return -likelihood
    
    def _fit_theta(self, p1, p2, dt):
        spread = p1 - p2
        result1 = minimize(self._log_likelihood, [0.1, 0.1, 0.05, 0.01], args=(p1, spread, dt), method='L-BFGS-B', bounds=((0, None), (0, None), (0, None), (0, None)))
        result2 = minimize(self._log_likelihood, [0.1, 0.1, 0.05, 0.01], args=(p2, spread, dt), method='L-BFGS-B', bounds=((0, None), (0, None), (0, None), (0, None)))
        kappa0_opt, kappa1_opt, theta1_opt, sigma1_opt = result1.x
        kappa0_opt, kappa1_opt, theta2_opt, sigma2_opt = result2.x
        return theta1_opt, theta2_opt, sigma1_opt, sigma2_opt
    
    def __init__(self, symbol1, symbol2, client, nobacktest, only_backtest):
        pair_trade_strategy.PairTradeStrategy.__init__(self, symbol1, symbol2, client, nobacktest=nobacktest, only_backtest=only_backtest)
        self.OU = OU()
        self.interval_minutes = 30
        self.period_minutes = 380
        self.N = self.period_minutes // self.interval_minutes
        self.dt = self.interval_minutes / 60
        self.T = self.period_minutes / 60
    
    # 30분 간격 데이터로 고정, 하루마다 매매.
    def action(self):
        trade_dict = {}
        for symbol in self.symbols:
            trade_dict[symbol] = 0
        text = ''
        p1 = self.current_data["norm_price_series"][self.symbols[0]+"_Price"].tail(self.N)
        p2 = self.current_data["norm_price_series"][self.symbols[1]+"_Price"].tail(self.N)
        mu = np.mean(p1-p2)
        theta1_opt, theta2_opt, sigma1_opt, sigma2_opt = self._fit_theta(p1, p2, self.dt)
        X00 = self.current_data["norm_price"][self.symbols[0]+"_Price"]
        X01 = self.current_data["norm_price"][self.symbols[1]+"_Price"]
        t, price1 = self._simulate_cir_process(theta1_opt, mu, sigma1_opt, X00, self.T, self.dt, self.N)
        t, price2 = self._simulate_cir_process(theta2_opt, mu, sigma2_opt, X01, self.T, self.dt, self.N)
        buy_list, sell_list, alpha_ratio = self.OU.get_signal(self.symbols[0], self.symbols[1], pd.Series(price1), pd.Series(price2))
        for b in buy_list:
            trade_dict[b] += alpha_ratio
        for s in sell_list:
            trade_dict[s] -= alpha_ratio
        
        text += f"[OU] Buy: {buy_list}, Sell: {sell_list} | Z-score: {alpha_ratio :.3f}\n"
            
        cash, limit = self.client.max_operate_cash(), self.client.max_operate_amount
        action_dicts = [utils.preprocess_weights({k: v for k, v in trade_dict.items() if v > 0}, cash, limit), 
                        {k: v for k, v in trade_dict.items() if v < 0}]
        
        for stock, alpha in action_dicts[1].items(): # sell
            alpha_ratio = abs(alpha)
            if alpha_ratio < 0.1:
                continue
            qty = 0
            qty = self.client.sell(stock, self.current_data["price"][stock+"_Price"], alpha_ratio)
            text += f"Sell {stock}, ratio: {alpha_ratio :.3f}, qty: {qty}\n"
        for stock, alpha in action_dicts[0].items(): # buy
            alpha_ratio = abs(alpha)
            if alpha_ratio < 0.1:
                continue
            qty = 0
            qty = self.client.buy(stock, self.current_data["price"][stock+"_Price"], alpha_ratio)   
            text += f"Buy {stock}, ratio: {alpha_ratio :.3f}, qty: {qty}\n"
        print(text)
        return text
        
    def backtest(self, start='2024-06-01', end='2024-08-01', interval='30m', print_result=True, seperated=False, show_plot=True, show_result=True, show_only_text=False):
        limit = 10000000000
        self.bt = backtester.Backtester(self.symbols, start, end, interval, limit, 0.0025, self._process_data)
        bar = 0
        interval_minutes = 30
        period_minutes = 380
        N = period_minutes // interval_minutes
        dt = interval_minutes / 60
        T = period_minutes / 60
        refresh = 24
        theta1_opt, theta2_opt = 0.7, 0.7
        sigma1_opt, sigma2_opt = 0.05, 0.05
        mu = 0.5
        
        while True:
            raw, data, today = self.bt.go_next()
            if data == -1:
                break
            
            trade_dict = {}
            for symbol in self.symbols:
                trade_dict[symbol] = 0
            
            if bar > N and bar % refresh == 0:
                p1 = data["norm_price_series"][self.symbols[0]+"_Price"].iloc[bar-N:bar]
                p2 = data["norm_price_series"][self.symbols[1]+"_Price"].iloc[bar-N:bar]
                spread = p1 - p2
                mu = np.mean(spread)
                theta1_opt, theta2_opt, sigma1_opt, sigma2_opt = self._fit_theta(p1, p2, dt)
            
                X00 = data["norm_price"][self.symbols[0]+"_Price"]
                X01 = data["norm_price"][self.symbols[1]+"_Price"]
                t, price1 = self._simulate_cir_process(theta1_opt, mu, sigma1_opt, X00, T, dt, N)
                t, price2 = self._simulate_cir_process(theta2_opt, mu, sigma2_opt, X01, T, dt, N)

                buy_list, sell_list, alpha_ratio = self.OU.get_signal(self.symbols[0], self.symbols[1], pd.Series(price1), pd.Series(price2))
                for b in buy_list:
                    trade_dict[b] += alpha_ratio
                for s in sell_list:
                    trade_dict[s] -= alpha_ratio
                action_dicts = [utils.preprocess_weights({k: v for k, v in trade_dict.items() if v > 0}, self.bt.current_amount, limit), 
                                {k: v for k, v in trade_dict.items() if v < 0}]
                
                for stock, alpha in action_dicts[1].items(): # sell
                    alpha_ratio = abs(alpha)
                    if alpha_ratio < 0.1:
                        continue
                    self.bt.sell(stock, alpha_ratio)
                for stock, alpha in action_dicts[0].items(): # buy
                    alpha_ratio = abs(alpha)
                    if alpha_ratio < 0.1:
                        continue
                    self.bt.buy(stock, alpha_ratio)    
            
            bar += 1
            
            self.bt.print_stock_weights()
        
        if show_only_text:
            if show_plot:
                self.bt.plot_result()
            if show_result:
                self.bt.print_result()
            return self.bt.print_result('for_show')
        else:
            if print_result:
                if show_result:
                    self.bt.print_result()
                if show_plot:
                    self.bt.plot_result() 
            else: 
                if seperated:
                    return self.bt.print_result(fname='sum')
            return self.bt.print_result(fname='return')