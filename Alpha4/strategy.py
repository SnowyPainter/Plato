class BollingerSplitReversal:
    def __init__(self):
        self.minimal_window = 30
    
    def _close_to_mid(self, mid, price):
        return abs(mid - price) < (price / 1000)
    def get_bollinger_band(self, df, column):
        num_std = 2
        ma = df[column].rolling(window=self.minimal_window).mean()
        std = df[column].rolling(window=self.minimal_window).std()
        return ma + (std * num_std), ma - (std * num_std), ma
    
    def action(self, symbols, data, bands):
        trade_strength = {}
        for symbol in symbols:
            column = symbol+"_Price"
            price = data['price'][column]
            ub = bands[symbol]['ub']
            lb = bands[symbol]['lb']
            
            trade_strength[symbol] = 0
            if price >= ub:
                trade_strength[symbol] = ub - price
            elif price <= lb:
                trade_strength[symbol] = lb - price
            elif self._close_to_mid(bands[symbol]['mid'], price):
                trade_strength[symbol] = price / 1000
        return trade_strength
                
        