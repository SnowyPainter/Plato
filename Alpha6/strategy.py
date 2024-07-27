import utils

import pandas as pd
import numpy as np

class VolatilityAct:
    def __init__(self, symbols):
        self.symbols = symbols
        self.volatilities = {}
        self.last_volatilities_coefs = {}
        self.fixed_bias_by_volatility = {}
        for symbol in symbols:
            self.fixed_bias_by_volatility[symbol] = 0
            self.volatilities[symbol] = []
            self.last_volatilities_coefs[symbol] = []
    
    def append_data(self, volatility):
        for symbol in self.symbols:
            volatility.dropna(inplace=True)
            self.volatilities[symbol].append(volatility.tail(1)[0])
    
    def action(self):
        for symbol in self.symbols:
            if len(self.volatilities[symbol]) <= 1:
                continue
            a = utils.coef(self.volatilities[symbol])
            self.last_volatilities_coefs[symbol].append(a)
            if len(self.last_volatilities_coefs[symbol]) == 1:
                continue
            v = -a*75 if a - self.last_volatilities_coefs[symbol][-2] > 0 else a*65
            self.fixed_bias_by_volatility[symbol] = v
            self.last_volatilities_coefs[symbol].append(a)
            self.volatilities[symbol] = []
        return self.fixed_bias_by_volatility