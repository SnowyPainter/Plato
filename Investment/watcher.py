import utils
from Models import MC_VaR

class Watcher:
    # Mission: Watch TP/SL, Volatility, VaR
    
    def _refresh_data(self):
        self.qtys, self.avgps = self.client.get_acc_status()
        for symbol in self.symbols:
            pr, hpr, lpr = self.client.get_price(symbol[:6])
            self.prices[symbol].append({'pr': pr, 'hpr': hpr, 'lpr': lpr})
    
    def __init__(self, client, symbols):
        self.client = client
        self.prices = {}
        self.symbols = symbols
        for symbol in symbols:
            self.prices[symbol] = []
    
    def watch_TP(self, tp=0.03):
        self._refresh_data()
        sell_list = []
        for symbol in self.symbols:
            code = symbol[:6]
            p = utils.calculate_stock_increase_p(self.qtys[code], self.avgps[code], self.prices[symbol][-1]['pr'])            
            if p >= tp:
                sell_list.append({"symbol":symbol, "p": p})
        return sell_list

    def watch_SL(self, sl=-0.03):
        self._refresh_data()
        sell_list = []
        for symbol in self.symbols:
            code = symbol[:6]
            p = utils.calculate_stock_increase_p(self.qtys[code], self.avgps[code], self.prices[symbol][-1]['pr'])            
            if p <= sl:
                sell_list.append({"symbol":symbol, "p": p})
        return sell_list
    