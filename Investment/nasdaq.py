from datetime import datetime
import mojito
import math
import os
import configparser
import yfinance as yf

import logger

class NasdaqClient:
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
        resp = self.broker.fetch_present_balance()
        init_amount = round(float(resp['output2'][0]['frcr_evlu_amt2']) / float(resp['output2'][0]['frst_bltn_exrt']), 2)
        amount = float(resp['output2'][0]['frcr_dncl_amt_2'])
        stocks_qty = {}
        avgp = {}
        for stock in resp['output1']:
            stocks_qty[stock['pdno']] = int(float(stock['ccld_qty_smtl1']))
            avgp[stock['pdno']] = float(stock['avg_unpr3'])
        return init_amount, amount, stocks_qty, avgp
    
    def _max_units_could_affordable(self, ratio, init_amount, current_amount, price, fee):
        money = init_amount * ratio * (1+fee)
        if current_amount >= money:
            return math.floor(money / price)
        else:
            return math.floor(current_amount / price)

    def _max_units_could_sell(self, ratio, init_amount, current_units, price, fee):
        money = init_amount * ratio * (1-fee)
        units = math.floor(money / price)
        if current_units > units:
            return units
        else:
            return current_units
    
    def __init__(self, name):
        self.logger = logger.Logger(name)
        if not os.path.exists('./settings'):
            os.makedirs('./settings')
        self.trade_logger = logger.TradeLogger(f"./settings/{name}_Trades.csv")
        self.keys = self._read_config()
        if self.keys == -1:
            self.logger.log("Failed to load ./settings/keys.ini")
            exit()
        
        self.broker = mojito.KoreaInvestment(api_key=self.keys["APIKEY"], api_secret=self.keys["APISECRET"], acc_no=self.keys["ACCNO"], exchange='나스닥', mock=False)
        self.init_amount, self.current_amount, self.stocks_qty, self.stocks_avg_price = self._get_balance()
        self.logger.log(f"Loading balance ...")
        self.logger.log(f"Initial Amount : {self.init_amount}")
        self.logger.log(f"Current Amount : {self.current_amount}")
        for stock, qty in self.stocks_qty.items():
            self.logger.log(f"{stock} : {qty} - {self.stocks_avg_price[stock]}")

    def get_price(self, symbol):
        t = yf.Ticker(symbol)
        return t.info.get('currentPrice')
    
    def calculate_evaluated(self):
        evaluate_stocks = 0
        for stock, qty in self.stocks_qty.items():
            evaluate_stocks += self.stocks_qty[stock] * self.get_price(stock)
        return self.current_amount + evaluate_stocks
    
    def buy(self, symbol, price, ratio):
        price = float(price)
        code = symbol.split('.')[0]
        qty = self._max_units_could_affordable(ratio, self.init_amount, self.current_amount, price, 0.0025)
        if qty == 0:
            return
        resp = self.broker.create_limit_buy_order(
            symbol = code,
            price = str(price),
            quantity = str(qty),
        )
        if "초과" in resp['msg1'] and qty > 1:
            resp = self.broker.create_limit_buy_order(
                symbol = code,
                price = str(price),
                quantity = str(qty-1),
            )
            qty -= 1
        self.current_amount -= qty * price * (1 + 0.0025)
        if not (code in self.stocks_qty):
            self.stocks_qty[code] = 0
        self.stocks_qty[code] += qty
        self.trade_logger.log("buy", symbol, qty, price, self.calculate_evaluated())
        self.logger.log(f"Buy {code} - {qty}({ratio*100}%), price: {price}, {resp['msg1']} | current {self.current_amount}")
        
    def sell(self, symbol, price, ratio):
        code = symbol.split('.')[0]
        if not (code in self.stocks_qty):
            self.stocks_qty[code] = 0
            return
        price = float(price)
        qty = self._max_units_could_sell(ratio, self.init_amount, self.stocks_qty[code], price, 0.0025)
        if qty == 0:
            return
        resp = self.broker.create_limit_buy_order(
            symbol=code,
            price=str(price),
            quantity=str(qty)
        )
        self.current_amount += qty * price * (1 - 0.0025)
        self.stocks_qty[code] -= qty
        self.trade_logger.log("sell", symbol, qty, price, self.calculate_evaluated())
        self.logger.log(f"Sell {code} - {qty}({ratio*100}%), price: {price}, {resp['msg1']} | current {self.current_amount}")