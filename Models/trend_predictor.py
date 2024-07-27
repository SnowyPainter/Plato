import utils
import pandas as pd
pd.options.mode.chained_assignment = None
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import classification_report, accuracy_score

class TrendPredictor:
    
    def _determine_macd_trend(self, row, symbol):
        if row[symbol+'_MACD'] > row[symbol+'_Signal_Line']:
            return 2
        elif row[symbol+'_MACD'] < row[symbol+'_Signal_Line']:
            return 0
        else:
            return 1

    def _load_train_data(self, df, symbol):
        price_column = symbol+"_Price"
        self.price_column = price_column
        df = utils.normalize(df)
        df[price_column+"_Lag"] = utils.df_lags(df, price_column, 5)
        df[price_column+"_MACD"] = utils.df_MACD(df, price_column)
        df[price_column+"_RSI"] = utils.calculate_rsi(df, price_column, 36)
        df[price_column+"_ADX"] = utils.df_ADX(df, symbol, period=50)
        df[price_column+'_Signal_Line'] = df[price_column+'_MACD'].ewm(span=50, adjust=False).mean()
        df[price_column+"_Trend"] = df.apply(lambda row: self._determine_macd_trend(row, price_column), axis=1)
        df.dropna(inplace=True)
        y = df[price_column+"_Trend"]
        self.minimal_data_length = 100
        
        return df[[price_column+"_Lag", price_column+"_MACD", price_column+"_RSI", price_column+"_ADX", price_column]], y
    
    def _build_model(self):
        model = MLPClassifier(hidden_layer_sizes=(64, 32), activation='logistic', solver='adam', max_iter=1000, random_state=42)
        return model
    
    def __init__(self, symbol, df):
        self.x, self.y = self._load_train_data(df, symbol)
        self.model = self._build_model()
        
    def fit(self):
        #cross_val_scores = cross_val_score(self.model, self.x, self.y, cv=5)  # 5-겹 교차 검증
        #print(f"Cross-Validation Scores: {cross_val_scores}")
        #print(f"Mean Cross-Validation Score: {cross_val_scores.mean()}")
        
        X_train, X_test, y_train, y_test = train_test_split(self.x, self.y, test_size=0.4, random_state=42)
        self.model.fit(X_train.values, y_train)
        y_train_pred = self.model.predict(X_train)
        y_test_pred = self.model.predict(X_test)

        train_accuracy = accuracy_score(y_train, y_train_pred)
        test_accuracy = accuracy_score(y_test, y_test_pred)
        print(f"Trend Predictor {self.price_column} - Train ACC : {train_accuracy :.2f} | Test ACC : {test_accuracy :.2f}")
        return train_accuracy, test_accuracy
    
    def predict(self, raw_df, symbol):
        x, y = self._load_train_data(raw_df, symbol)
        df = np.array([x.iloc[-1]])
        return self.model.predict(df)
    
def create_trend_predictors(symbols, df):
    trend_predictors = {}
    for symbol in symbols:
        tp = TrendPredictor(symbol, df)
        train_acc, test_acc = tp.fit()
        if test_acc >= 0.55:
            trend_predictors[symbol] = tp
    return trend_predictors