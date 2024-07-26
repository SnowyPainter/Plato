import pandas as pd
import numpy as np
from arch import arch_model
from sklearn.metrics import mean_squared_error, mean_absolute_error

# Longer data length, Lower predict accuaracy

class VolatilityForecaster:
    
    def _preprocess_data(self, data):
        pct = data[self.price_column].pct_change() * 100
        train_size = int(len(data) * 0.8)
        self.train, self.test = pct[:train_size], pct[train_size:]
        self.train.dropna(inplace=True)
        self.test.dropna(inplace=True)
    
    def __init__(self, raw_df, price_column):
        self.data = raw_df
        self.gjr_garch_fit = None
        self.price_column = price_column
        self._preprocess_data(data=self.data)
    
    def train_model(self):
        bic_gjr_garch = []
        best_param = (1, 1)
        for p in range(1, 5):
            for q in range(1, 5):
                model = arch_model(self.train, vol='Garch', p=p, o=1, q=q, dist='Normal').fit(disp='off')
                bic_gjr_garch.append(model.bic)
                if model.bic == np.min(bic_gjr_garch):
                    best_param = p, q
        self.gjr_garch_fit = arch_model(self.train, vol='Garch', p=best_param[0], o=1, q=best_param[1], dist='Normal').fit(disp='off')
        
    def make_forecast(self, horizon=10):
        forecast = self.gjr_garch_fit.forecast(horizon=horizon)
        predicted_volatility = forecast.variance[-1:] ** 0.5
        return predicted_volatility.iloc[0].values.flatten().tolist()
    
    def evaluate(self):
        horizon = len(self.test)
        forecast = self.gjr_garch_fit.forecast(horizon=horizon)
        predicted_variance = forecast.variance[-horizon:]
        predicted_volatility = np.sqrt(predicted_variance)
        actual_volatility = self.test.rolling(window=10).std().dropna()
        adjusted_length = min(len(predicted_volatility), len(actual_volatility))
        comparison_df = pd.DataFrame({
            'Real Volat': actual_volatility.values[-adjusted_length:],
            'Pred Volat': predicted_volatility.values[0][-adjusted_length:]
        })
        
        mse = mean_squared_error(comparison_df['Real Volat'], comparison_df['Pred Volat'])
        mae = mean_absolute_error(comparison_df['Real Volat'], comparison_df['Pred Volat'])
        mape = np.mean(np.abs((comparison_df['Real Volat'] - comparison_df['Pred Volat']) / comparison_df['Real Volat'])) * 100
        #print(f"[GJRGARCH VF] EVALUTE {self.price_column} ... MSE({mse :.2f}) | MAE({mae :.2f}) | MAPE({mape :.2f} %)")
        
def create_vfs(symbols, data):
    vfs = {}
    for symbol in symbols:
        vf = VolatilityForecaster(data, symbol+"_Price")
        vf.train_model()
        vf.evaluate()
        vfs[symbol] = vf
    return vfs
    