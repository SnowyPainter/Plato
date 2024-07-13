import numpy as np
import pandas as pd
import statsmodels.api as sm
import matplotlib.pyplot as plt
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.stattools import coint

class OU:
    def __init__(self):
        pass
    
    def check_stationarity(self, series):
        series = series.dropna()
        result = adfuller(series)
        return result[1] < 0.05  # p-value < 0.05 indicates stationarity

    def estimate_ou_params(self, spread):
        spread_diff = spread.diff().dropna()
        spread_lag = spread.shift(1).dropna()
        spread_lag = sm.add_constant(spread_lag)

        model = sm.OLS(spread_diff, spread_lag)
        result = model.fit()
        beta = result.params.iloc[1]
        if beta <= -1:
            beta = -0.9999
        theta = -np.log(1 + beta)  # Ensure the argument of log is positive
        mu = result.params.iloc[0] / (1 - np.exp(-theta))
        sigma = np.std(result.resid) * np.sqrt(2 * theta / (1 - np.exp(-2 * theta)))
        return mu, theta, sigma

    def get_signal(self, symbol1, symbol2, price1, price2):
        spread = price1 - price2
        if not self.check_stationarity(spread):
            spread = spread.diff().dropna()
        mu, theta, sigma = self.estimate_ou_params(spread)
        current_spread = price1.tail(1).iloc[0] - price2.tail(1).iloc[0]
        z_score = (current_spread - mu) / sigma
        alpha_ratio = 1 if z_score > 1 or z_score < -1 else abs(z_score)
        if z_score < -1.0:
            return [symbol1], [symbol2], alpha_ratio
        elif z_score > 1.0:
            return [symbol2], [symbol1], alpha_ratio
        elif abs(z_score) < 0.5:
            return [], [symbol1, symbol2], alpha_ratio
        return [], [], alpha_ratio