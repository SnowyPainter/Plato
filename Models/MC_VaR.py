import numpy as np 
import pandas as pd

def get_historical_VaR2(returns, initial_investment, n_var):
    portfolio_returns = np.diff(returns) / returns[:-1]
    mean_return = portfolio_returns.mean()
    std_return = portfolio_returns.std()
    n_simulations = 10000
    simulated_end_values = initial_investment * (1 + np.random.normal(mean_return, std_return, n_simulations)) ** n_var
    confidence_level = 0.95
    VaR = initial_investment - np.percentile(simulated_end_values, (1 - confidence_level) * 100)
    print(f"Monte Carlo Simulation VaR (at {confidence_level*100}% confidence level): {VaR:.2f} 원")
    return VaR

def get_historical_VaR(historical, symbols, initial_investment, stock_weights, n_var):
    returns = historical[[symbol+"_Price" for symbol in symbols]].pct_change().dropna()
    portfolio_returns = returns.dot(stock_weights)
    mean_return = portfolio_returns.mean()
    std_return = portfolio_returns.std()
    n_simulations = 10000
    simulated_end_values = initial_investment * (1 + np.random.normal(mean_return, std_return, n_simulations)) ** n_var
    confidence_level = 0.95
    VaR = initial_investment - np.percentile(simulated_end_values, (1 - confidence_level) * 100)
    print(f"Monte Carlo Simulation VaR (at {confidence_level*100}% confidence level): {VaR:.2f} 원")
    return VaR