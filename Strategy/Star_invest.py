import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from Strategy import pair_trade_strategy
from Alpha5.strategy import *
import backtester
import utils
from scipy.optimize import minimize
from scipy.stats import norm

class StarInvest(pair_trade_strategy.PairTradeStrategy):
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
    
    def __init__(self, symbol1, symbol2, client, nobacktest, only_backtest):
        pair_trade_strategy.PairTradeStrategy.__init__(self, symbol1, symbol2, client, nobacktest=nobacktest, only_backtest=only_backtest)
        self.OU = OU()
    
    def action(self, hour_divided_time=1):
        pass
    
    def backtest(self, start='2024-06-01', end='2024-08-01', interval='5m', print_result=True, seperated=False, show_plot=True, show_result=True, show_only_text=False):
        limit = 10000000000
        bt = backtester.Backtester(self.symbols, start, end, interval, limit, 0.0025, self._process_data)
        bar = 0
        interval_minutes = 5
        period_minutes = 380
        N = period_minutes // interval_minutes
        dt = interval_minutes / 60
        T = period_minutes / 60
        i = 0

        theta1_opt, theta2_opt = 0.7, 0.7
        mu = 0.5
        sigma = 0.05
        
        while True:
            raw, data, today = bt.go_next()
            if data == -1:
                break
            
            trade_dict = {}
            for symbol in self.symbols:
                trade_dict[symbol] = 0
            
            sigma_series = utils.get_pct_changes(bt.portfolio_evaluates).rolling(window=12).std()
            if len(sigma_series) > N:
                sigma = sigma_series.iloc[-1]
            if bar > N and bar % N == 0:
                p1 = data["norm_price_series"][self.symbols[0]+"_Price"].iloc[bar-N:bar]
                p2 = data["norm_price_series"][self.symbols[1]+"_Price"].iloc[bar-N:bar]
                spread = p1 - p2
                mu = np.mean(spread)
                initial_params = [0.1, 0.1, 0.03, 0.02]
                result1 = minimize(self._log_likelihood, initial_params, args=(p1, spread, dt), method='L-BFGS-B', bounds=((0, None), (0, None), (0, None), (0, None)))
                result2 = minimize(self._log_likelihood, initial_params, args=(p2, spread, dt), method='L-BFGS-B', bounds=((0, None), (0, None), (0, None), (0, None)))
                kappa0_opt, kappa1_opt, theta1_opt, sigma_opt = result1.x
                kappa0_opt, kappa1_opt, theta2_opt, sigma_opt = result2.x
            
            if bar % N == 0:
                X00 = data["norm_price"][self.symbols[0]+"_Price"]
                X01 = data["norm_price"][self.symbols[1]+"_Price"]
                t, price1 = self._simulate_cir_process(theta1_opt, mu, sigma, X00, T, dt, N)
                t, price2 = self._simulate_cir_process(theta2_opt, mu, sigma, X01, T, dt, N)
                buy_list, sell_list, alpha_ratio = self.OU.get_signal(self.symbols[0], self.symbols[1], pd.Series(price1), pd.Series(price2))
                for b in buy_list:
                    trade_dict[b] += alpha_ratio
                for s in sell_list:
                    trade_dict[s] -= alpha_ratio
            
            action_dicts = [utils.preprocess_weights({k: v for k, v in trade_dict.items() if v > 0}, bt.current_amount, limit), 
                            {k: v for k, v in trade_dict.items() if v < 0}]
            
            for stock, alpha in action_dicts[1].items(): # sell
                alpha_ratio = abs(alpha)
                bt.sell(stock, alpha_ratio)
            for stock, alpha in action_dicts[0].items(): # buy
                alpha_ratio = abs(alpha)
                bt.buy(stock, alpha_ratio)    
            
            bar += 1
            
            bt.print_stock_weights()
            
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