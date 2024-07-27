import pandas as pd
import numpy as np
from statsmodels.tsa.arima.model import ARIMA
from sklearn.metrics import mean_squared_error
from itertools import product
from pmdarima import auto_arima
import os

import warnings
from statsmodels.tools.sm_exceptions import ConvergenceWarning
warnings.filterwarnings("ignore", category=ConvergenceWarning)

import utils

class PricePredictorBT:
    def __init__(self, df):
        self.data = df
        self.model = None
        self.model_fit = None
        self.train_data = None
        self.test_data = None

    def preprocess_data(self, symbols, train_size=0.8, freq='H'):
        self.data.index = pd.to_datetime(self.data.index)
        inferred_freq = pd.infer_freq(self.data.index)
        if inferred_freq is not None:
            self.data = self.data.asfreq(inferred_freq)
        else:
            self.data = self.data.asfreq(freq)  # 기본 빈도를 일간으로 설정
        for symbol in symbols:
            self.data[symbol+"_Price"].interpolate(method='linear', inplace=True)
        train_size = int(len(self.data) * train_size)
        self.train_data, self.test_data = self.data[:train_size], self.data[train_size:]

    def train_model(self, price_column, order):
        self.model = ARIMA(self.train_data[price_column], order=order)
        self.model_fit = self.model.fit()

    def make_forecast(self, steps=1):
        forecast = self.model_fit.forecast(steps=steps)
        return forecast

    def evaluate_model(self, price_column):
        forecast = self.make_forecast(steps=len(self.test_data))
        rmse = np.sqrt(mean_squared_error(self.test_data[price_column], forecast))
        return rmse

    def find_best_order(self, price_column, max_p=5, max_d=5, max_q=5):
        best_rmse = float('inf')
        best_order = None

        for order in product(range(1, max_p+1), range(1, max_d+1), range(1, max_q+1)):
            try:
                self.train_model(price_column, order)
                rmse = self.evaluate_model(price_column)
                if rmse < best_rmse:
                    best_rmse = rmse
                    best_order = order
            except:
                continue

        self.best_order = best_order
        self.order = best_order
        print(f'{price_column} Best order: {best_order}, RMSE: {best_rmse}')
        return best_order

class PricePredictor:
    def __init__(self, df):
        self.data = df

    def preprocess_data(self, symbols, freq='H'):
        self.data.index = pd.to_datetime(self.data.index)
        inferred_freq = pd.infer_freq(self.data.index)
        if inferred_freq is not None:
            self.data = self.data.asfreq(inferred_freq)
        else:
            self.data = self.data.asfreq(freq)  # 기본 빈도를 일간으로 설정
        for symbol in symbols:
            self.data[symbol+"_Price"].interpolate(method='linear', inplace=True)

    def train_model(self, price_column):
        self.model = auto_arima(self.data[price_column], 
                   seasonal=True, 
                   m=6,
                   stepwise=False, 
                   trace=True, 
                   error_action='ignore', 
                   suppress_warnings=True, 
                   approximation=True)
        
    def make_forecast(self, n):
        forecast = self.model.predict(n_periods=n)
        return forecast

def create_price_predictor(df, symbols):
    models = {}
    for symbol in symbols:
        pp = PricePredictor(df)
        pp.train_model(symbol+"_Price")
        models[symbol] = pp
    return models

def create_price_predictor_BT(df, symbols, orders={}, freq='1h'):
    utils.create_params_dir()
    
    models = {}
    for symbol in symbols:
        pp = PricePredictorBT(df)
        pp.preprocess_data(symbols, freq=("30min" if freq == '30m' else "H"))
        if not (symbol in orders):
            if os.path.exists(f'./model_params/{symbol} ARIMA order.txt'):
                order = utils.get_order(f'./model_params/{symbol} ARIMA order.txt')
            else:
                order = pp.find_best_order(symbol+"_Price")
                with open(f'./model_params/{symbol} ARIMA order.txt', 'w') as file:
                    file.write(str(order))
        else:
            order = orders[symbol]
            
        pp.train_model(symbol+"_Price", order)
        models[symbol] = pp
    return models