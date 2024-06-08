class StockPair:
    def _determin_to_trade(self, data, symbol1, symbol2):
        diff = data["norm_price"][symbol1+"_Price"] - data["norm_price"][symbol2+"_Price"]
        diff = 1 if diff < 0 else (2 if diff > 0 else 0)
        return diff
    def action(self, data, symbol1, symbol2):
        result = self._determin_to_trade(data, symbol1, symbol2)
        if result == 1:
            return [symbol1], [symbol2]
        elif result == 2:
            return [symbol2], [symbol1]
        else:
            return [], []