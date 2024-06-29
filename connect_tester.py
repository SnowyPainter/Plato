from Swinger_invest import *
from Investment import kis

import os

def check_connection():
    if os.path.exists("token.dat"):
        os.remove("token.dat")
    
    long_symbols = ["042700.KS", "000660.KS", "005930.KS"]
    SPW = 2.5
    BW = 5
    invester = SwingerInvest(long_symbols, SPW, BW, 10000, exchange='krx')
    invester.append_current_data()