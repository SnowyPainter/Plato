import numpy as np
import pandas as pd
import statsmodels.api as sm

data = {
    'stock_return': [0.01, 0.02, 0.015, -0.005, 0.01],
    'market_return': [0.005, 0.015, 0.02, -0.01, 0.005]
}

def CAPM(price_raw, market, columns, stock_weights):
    price_raw = (price_raw.pct_change())
    price_raw.dropna(inplace=True)
    market = (np.diff(market) / market[:-1])
    price_raw = price_raw.tail(len(market))

    E_R_m = np.mean(market)
    betas = {}
    for col in columns:
        X = sm.add_constant(market)
        model = sm.OLS(price_raw[col], X).fit()
        betas[col] = model.params['x1']
    
    expected_returns = {}
    for stock, beta in betas.items():
        expected_returns[stock] = 0 + beta * (E_R_m - 0)
    portfolio_expected_return = sum(expected_returns[stock] * weight for stock, weight in stock_weights.items())
    return portfolio_expected_return