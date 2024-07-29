from datetime import datetime
import mojito
import math
import os
import time
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
    
    # Get balance는 딱 한번 호출됨.
    
    def _get_acc_status(self):
        broker = self.broker
        resp = broker.fetch_balance()
        #amount = int(resp['output2'][0]['prvs_rcdl_excc_amt'])
        #init_amount = int(resp['output2'][0]['tot_evlu_amt'])
        stocks_qty = {}
        avgp = {}
        for stock in resp['output1']:
            stocks_qty[stock['pdno']] = int(stock['hldg_qty'])
            avgp[stock['pdno']] = float(stock['pchs_avg_pric'])
        
        return stocks_qty, avgp
    
    #매입 단가 기준 자산 (투입 금액)
    def _asset_bought_amount(self):
        stocks_qty, stocks_avg_price = self._get_acc_status()
        
        asset_before_evlu = 0
        for symbol in self.symbols:
            symbol = symbol[:6]
            if symbol in stocks_qty and symbol in stocks_avg_price:
                asset_before_evlu += stocks_qty[symbol] * stocks_avg_price[symbol]
        return asset_before_evlu
    
    def max_operate_cash(self):
        asset_before_evlu = self._asset_bought_amount()
        operate_cash = self.max_operate_amount - asset_before_evlu
        return operate_cash
    
    def _max_units_could_affordable(self, ratio, init_amount, current_amount, price, fee):
        money = init_amount * ratio * (1+fee)
        qty = math.floor(money / price)
        bought_asset = self._asset_bought_amount()
        if current_amount <= 0 or bought_asset > self.max_operate_amount:
            return 0
        
        if bought_asset + (qty * price) > self.max_operate_amount:
            qty = math.floor(((self.max_operate_amount - bought_asset) * (1 - fee)) / price)
            print(qty, bought_asset, ((self.max_operate_amount - bought_asset) * (1 - fee)), self.max_operate_amount)
        
        print(qty)
        
        return abs(qty)

    def _max_units_could_sell(self, ratio, init_amount, current_units, price, fee):
        money = init_amount * ratio * (1-fee)
        units = math.floor(money / price)
        if current_units > units:
            return units
        else:
            return current_units

    def __init__(self, symbols, max_operate_amount,nolog=False):
        name = symbols[0]
        if not os.path.exists('./settings'):
            os.makedirs('./settings')
        self.trade_logger = logger.TradeLogger(f"./settings/{name}_Trades.csv", nolog)
        self.logger = logger.Logger(name, nolog)
        self.keys = self._read_config()
        if self.keys == -1:
            self.logger.log("Failed to load ./settings/keys.ini")
            exit()
        self.symbols = symbols
        self.max_operate_amount = max_operate_amount
        self.init_amount = self.max_operate_amount
        self.current_price = {}
        
        self.broker = mojito.KoreaInvestment(api_key=self.keys["APIKEY"], api_secret=self.keys["APISECRET"], acc_no=self.keys["ACCNO"], mock=False)
        self.stocks_qty, self.stocks_avg_price = self._get_acc_status()
        
        self.current_amount = self.max_operate_cash()
        self.logger.log(f"Loading balance ...")
        self.logger.log(f"Max Operating Asset Amount : {self.max_operate_amount}")
        self.logger.log(f"Affordable Cash : {self.current_amount}")
        
        '''
        
        투자 비율의 대상을 일정 금액(max_operate_amount)으로 지정하게 된다면
        50%, 50% 비율로 각각 매매할 때 어느 한 주식에 대한 50% 비율이 실제 가지고 있는 돈 보다 많아서 50%가 사실상 100%로 체결되어 그 다음 것을 체결하지 못함.
        
        투자 비율의 대상을 가변적으로(max_operate_cash()) 지정하게 된다면
        200만원이 있고, 주식 가치가 190만원일 때 실제 투자 가능 금액은 10만원이라 그 중에서 비율(ex 10% -> 1만원)로 하면 금액이 너무 작아
        매수, 매도 시그널이 의미가 없어짐.
        
        '''
        
        for stock, qty in self.stocks_qty.items():
            self.logger.log(f"{stock} : {qty} - {self.stocks_avg_price[stock]}")
        
    def is_market_open(self):
        now = datetime.now()
        return (now.hour >= 9) and (now.hour <= 15 and now.minute <= 30)
    
    def get_price(self, symbol):
        time.sleep(0.1)
        resp = self.broker.fetch_price(symbol)
        if not 'output' in resp:
            return self.get_price(symbol)
        pr = float(resp['output']['stck_prpr'])
        self.current_price[symbol] = pr
        return pr, float(resp['output']['stck_hgpr']), float(resp['output']['stck_lwpr'])
    
    def calculate_evaluated(self):
        return -1 * (self.max_operate_cash() - self.max_operate_amount)
    
    def buy(self, symbol, price, ratio):
        price = int(price)
        code = symbol.split('.')[0]
        qty = self._max_units_could_affordable(ratio, self.init_amount, self.current_amount, price, 0.0025)
        if qty == 0:
            return

        resp = {'msg1' : '11'}
        '''
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
        '''
        self.current_amount -= qty * price * (1 - 0.0025)
        if not (code in self.stocks_qty):
            self.stocks_qty[code] = 0
        self.stocks_qty[code] += qty
        self.trade_logger.log("buy", symbol, qty, price, self.calculate_evaluated())
        self.logger.log(f"Buy {code} - {qty}({ratio*100}%, {qty*price}), price: {price}, {resp['msg1']} | current {self.current_amount}")
        
    def sell(self, symbol, price, ratio):
        code = symbol.split('.')[0]
        if not (code in self.stocks_qty):
            self.stocks_qty[code] = 0
            return
        price = int(price)
        qty = self._max_units_could_sell(ratio, self.init_amount, self.stocks_qty[code], price, 0.0025)
        if qty == 0:
            return
        resp = {'msg1' : '11'}
        '''
        resp = self.broker.create_market_sell_order(
            symbol=code,
            quantity=str(qty)
        )
        '''
        self.current_amount += qty * price * (1 - 0.0025)
        self.stocks_qty[code] -= qty
        self.trade_logger.log("sell", symbol, qty, price, self.calculate_evaluated())
        self.logger.log(f"Sell {code} - {qty}({ratio*100}%, {qty*price}), price: {price}, {resp['msg1']} | current {self.current_amount}")