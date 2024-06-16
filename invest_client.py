import Salmon_invest
import Swinger_invest
import utils

import os
from rich.console import Console
from rich.table import Table
from rich.columns import Columns
import time
import schedule
from datetime import datetime

console = Console()

tables = []
for theme_name, no in utils.THEMES.items():
    theme_table = Table(theme_name)
    theme_stocks = utils.get_theme_stocks(no)
    i = 1
    for stock, name in theme_stocks.items():
        theme_table.add_row(name, stock)
        i += 1
    tables.append(theme_table)

tables = Columns(tables)

portfolios = {
    "1" : ["042700.KS", "000660.KS", "005930.KS"],
}

portfolio_table = Table("포트폴리오 선택")

for name, codes in portfolios.items():
    portfolio_table.add_row(name, *codes)

strategy_table = Table("전략 선택")
file_list = os.listdir('.')
strategy_names = [file[:-10] for file in file_list if file.endswith('_invest.py')]
for i in range(1, len(strategy_names) + 1):
    strategy_table.add_row(str(i)+"번", strategy_names[i-1])

tables2 = Columns([portfolio_table, strategy_table])

console.print(tables)
console.print(tables2)

strategy_needs = {
    "1" : ["이동 평균 돌파 전략 가중치", "쌍 매매 가중치", "추세 편향"],
    "2" : ["볼린저 밴드 역방향 가중치", "쌍 매매 가중치"]
}

portfolio = input("포트폴리오를 선택해주세요 (번호) : ")
strategy = input("전략을 선택해주세요 (번호) : ")

weights = []
for info in strategy_needs[strategy]:
    weights.append(float(input(f"{info} : ")))
invester = None
if strategy == "1":
    invester = Salmon_invest.SalmonInvest(portfolios[portfolio], weights[0], weights[1], weights[2])
elif strategy == "2":
    invester = Swinger_invest.SwingerInvest(portfolios[portfolio], weights[1], weights[0])

if invester == None:
    print("유효한 전략을 선택하세요.")
    exit()

def action():
    global invester
    invester.append_current_data()
    invester.action()

print("1. 백테스팅")
print("2. 투자 진행")
choice = input("입력 : ")
if choice == "1":
    invester.backtest()
elif choice == "2":
    print(f"{portfolios[portfolio]}에 대해 {strategy_names[int(strategy) - 1]} 전략을 가동합니다.")
    for hour in range(9, 16):
        schedule.every().day.at(f"{hour:02d}:00").do(action)
    schedule.every().day.at("15:30").do(action)
    while True:
        schedule.run_pending()
        time.sleep(1)