from datetime import datetime
import mojito
import math
import timeit
import numpy as np
import pprint
import json
import pytz, os
import configparser

import logger

class KISClient:
    
    def _read_config(self):
        if not os.path.exists("./settings/keys.ini"):
            self.logger.log("No Key files")
            return -1
        try:
            self.logger.log("Reading ./settings/keys.ini ... ")
            config = configparser.ConfigParser()
            config.read("./settings/keys.ini")
            return {
                "APIKEY" : config["API"]["KEY"],
                "APISECRET" : config["API"]["SECRET"],
                "ACCNO" : config["API"]["ACCNO"]
            }
        except Exception as e:
            self.logger.log(f"{str(e)}")
            return -1
    
    def _get_balance(self):
        broker = self.broker
        resp = broker.fetch_balance()
        amount = int(resp['output2'][0]['prvs_rcdl_excc_amt'])
        init_amount = int(resp['output2'][0]['tot_evlu_amt'])
        stocks_qty = {}
        avgp = {}
        for stock in resp['output1']:
            stocks_qty[stock['pdno']] = int(stock['hldg_qty'])
            avgp[stock['pdno']] = float(stock['pchs_avg_pric'])
        return init_amount, amount, stocks_qty, avgp
    
    def _max_units_could_affordable(self, ratio, init_amount, current_amount, price, fee):
        money = init_amount * ratio * (1+fee)
        if current_amount >= money:
            return math.floor(money / price)
        else:
            return math.floor(current_amount / price)

    def _max_units_could_sell(self, ratio, init_amount, current_units, price, fee):
        money = init_amount * ratio * (1+fee)
        units = math.floor(money / price)
        if current_units > units:
            return units
        else:
            return current_units
    
    def _evalute_balance(self):
        self.init_amount, self.current_amount, self.stocks_qty, self.stocks_avg_price = self._get_balance()
        return self.init_amount

    def __init__(self, name):
        self.logger = logger.Logger(name)
        self.trade_logger = logger.TradeLogger(f"./settings/{name}_Trades.csv")
        self.keys = self._read_config()
        if self.keys == -1:
            self.logger.log("Failed to load ./settings/keys.ini")
            exit()
        self.broker = mojito.KoreaInvestment(api_key=self.keys["APIKEY"], api_secret=self.keys["APISECRET"], acc_no=self.keys["ACCNO"], mock=False)
        self.init_amount, self.current_amount, self.stocks_qty, self.stocks_avg_price = self._get_balance()
        self.logger.log(f"Loading balance ...")
        self.logger.log(f"Initial Amount : {self.init_amount}")
        self.logger.log(f"Current Amount : {self.current_amount}")
        for stock, qty in self.stocks_qty.items():
            self.logger.log(f"{stock} : {qty} - {self.stocks_avg_price[stock]}")
        
    def is_market_open(self):
        now = datetime.now()
        return (now.hour >= 9) and (now.hour <= 15 and now.minute <= 30)
    
    def get_price(self, symbol):
        resp = self.broker.fetch_price(symbol)
        return float(resp['output']['stck_prpr'])
        
    def buy(self, symbol, price, ratio):
        price = int(price)
        qty = self._max_units_could_affordable(ratio, self.init_amount, self.current_amount, price, 0.0025)
        if qty == 0:
            return
        resp = self.broker.create_limit_buy_order(
            symbol = symbol,
            price = str(price),
            quantity = str(qty),
        )
        self.current_amount -= qty * price * (1 + 0.0025)
        self.trade_logger.log("buy", symbol, qty, price, evaluated)
        self.logger.log(f"Buy {symbol} - {qty}/{price}, {resp['msg1']} | current {self.current_amount}")
        
    def sell(self, symbol, price, ratio):
        if not (symbol in self.stocks_qty):
            self.stocks_qty[symbol] = 0
        price = int(price)
        qty = self._max_units_could_sell(ratio, self.init_amount, self.stocks_qty[symbol], price, 0.0025)
        if qty == 0:
            return
        resp = self.broker.create_limit_sell_order(
            symbol=symbol,
            price=str(price),
            quantity=str(qty)
        )
        self.current_amount += qty * price * (1 - 0.0025)
        self.trade_logger.log("sell", symbol, qty, price, evaluated)
        self.logger.log(f"Sell {symbol} - {qty}/{price}, {resp['msg1']} | current {self.current_amount}")