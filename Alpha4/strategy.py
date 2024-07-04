class BollingerSplitReversal:
    def __init__(self):
        self.minimal_window = 30
    
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
        return trade_strength
                
        