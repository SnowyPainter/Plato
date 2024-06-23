from Swinger_invest import *
from Investment import kis

long_symbols = ["042700.KS", "000660.KS", "005930.KS"]
SPW = 2.5
BW = 5
invester = SwingerInvest(long_symbols, SPW, BW, exchange='krx')
invester.append_current_data()
print(invester.raw_data)