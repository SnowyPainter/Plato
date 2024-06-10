import utils
import pandas as pd
pd.options.mode.chained_assignment = None
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report

class TrendPredictor:
    
    def _prepare_data(self, df, symbol):
        price_column = symbol+"_Price"
        df = df[[price_column]]
        df[price_column+"_Lag"] = utils.df_lags(df, price_column, 3)
        df[price_column+"_RSI"] = utils.calculate_rsi(df, price_column, 14)
        df[price_column+"_MACD"] = utils.df_MACD(df, price_column)
        df = utils.normalize(df)
        self.minimal_data_length = 14
        df.dropna(inplace=True)
        return df
    
    def _build_model(self):
        model = LogisticRegression()
        return model
    
    def __init__(self, symbol, start, end, interval):
        df = utils.load_historical_data(symbol, start, end, interval)
        self.x = self._prepare_data(df, symbol)
        self.y = utils.determine_trend(self.x, symbol+"_Price")
        self.model = self._build_model()
        
    def fit(self):
        X_train, X_test, y_train, y_test = train_test_split(self.x, self.y, test_size=0.2, random_state=42)
        self.model.fit(X_train.values, y_train)
        y_pred = self.model.predict(X_test.values)
        accuracy = accuracy_score(y_test, y_pred)
        return accuracy
    
    def predict(self, raw_df, symbol):
        df = self._prepare_data(raw_df, symbol)
        df = np.array([df.iloc[-1]])
        return self.model.predict(df)