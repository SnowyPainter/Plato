import utils

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error

class VolatilityPredictor:
    def _preprocess_data(self):
        price = self.raw[self.price_column]
        return_pct = price.pct_change()
        self.data = pd.DataFrame({'Price' : utils.nplog(price), 'Volatility' : return_pct.rolling(window=80).std(), 'Return' : return_pct})
        self.data.dropna(inplace=True)
        self.X = self.data[['Price', 'Return']].values
        self.Y = self.data[['Volatility']].values
        
    def __init__(self, raw, price_column):
        self.raw = raw
        self.price_column = price_column
        self._preprocess_data()
        
    def build_model(self):
        
        X_train, X_test, y_train, y_test = train_test_split(self.X, self.Y, test_size=0.4, random_state=42)
        self.mlp = MLPRegressor(hidden_layer_sizes=(256, 128), max_iter=1000, random_state=42)
        self.mlp.fit(X_train, y_train)
        
        y_train_pred = self.mlp.predict(X_train)
        y_test_pred = self.mlp.predict(X_test)
        train_mse = mean_squared_error(y_train, y_train_pred)
        test_mse = mean_squared_error(y_test, y_test_pred)

        print(f"{self.price_column} - Train MSE: {train_mse :.4f} | Test MSE: {test_mse :.4f}")
        return train_mse, test_mse
    
    def predict(self, x):
        price = x[self.price_column]
        return_pct = price.pct_change()
        x = pd.DataFrame({'Return' :return_pct, 'Price' : utils.nplog(price)})
        x.dropna(inplace=True)
        return self.mlp.predict(x.tail(1))[0]
    
def create_volatility_predictors(symbols, data):
    vps = {}
    for symbol in symbols:
        vp = VolatilityPredictor(data, symbol+"_Price")
        train_mse, test_mse = vp.build_model()
        vps[symbol] = vp
    return vps