import datetime
import pandas as pd
import os

class Logger:
    def log(self, text):
        now = datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        with open(self.fname, "a") as myfile:
            myfile.write(f"[{now}]\t{text}\n")
    def __init__(self, title) -> None:
        if not os.path.exists('./log'):
            os.makedirs('./log')
        self.fname = "./log/" + datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S") + " " + title + ".txt"
        self.log(title)
        
class TradeLogger:
    def log(self, action, symbol, qty, price, evaluated_amount):
        df = pd.DataFrame({
            "date" : [datetime.datetime.now()],
            "evalu_amt" : [evaluated_amount],
            "action" : [action],
            "symbol" : [symbol],
            "qty" : [qty],
            "price" : [price]
        })
        df.set_index("date", inplace=True)
        existing_df = pd.read_csv(self.csv, index_col='date', parse_dates=True)
        if existing_df.empty:
            merged = df
        else:
            merged = pd.concat([existing_df, df])
        merged.to_csv(self.csv)
        
    def __init__(self, csv_name):
        self.csv = csv_name
        if not os.path.exists(self.csv):
            df = pd.DataFrame({
                "date" : [],
                "evalu_amt" : [],
                "action" : [],
                "symbol" : [],
                "qty" : [],
                "price" : []
            })
            df.set_index("date", inplace=True)
            df.to_csv(self.csv)