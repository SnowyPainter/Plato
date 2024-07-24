import time
import schedule
from datetime import datetime

import Neo_invest
import corr_high_finder
import utils
import connect_tester

i = input("Continue to Check Connection?(yes/no) : ")
if i == 'yes':
    connect_tester.check_connection()


def get_symbols(option):
    print(f"{option} 선택됨. 심볼 2개를 입력하세요:")
    symbols = []
    for i in range(2):
        symbol = input(f"심볼 {i + 1}: ")
        symbols.append(symbol)
    return symbols

def get_bt_term(option):
    print(f"{option} 선택됨")
    start = input(f"시작 날짜를 입력하세요(20xx-xx-xx) : ")
    end = input(f"종료 날짜를 입력하세요(20xx-xx-xx) : ")
    return start, end

def get_current_amount(option):
    print(f"{option} 선택됨.")
    amount = input("투자 허용 금액을 입력하세요 : ")
    return float(amount)

invester = None
hour_divided_time = 1
options = ['백테스팅', '실전 투자', '종목 추천']

while True:
    i = 1
    for option in options:
        print(f"{i} : {option}")
        i += 1
    opt = input("Option : ")
    
    if opt == "1":
        selected_option = "Backtest"
        symbols = get_symbols(selected_option)
        start, end = get_bt_term(selected_option)
        print(f"심볼 : {', '.join(symbols)}")
        print(f"기간 : {start} ~ {end}")
        invester = Neo_invest.NeoInvest(symbols[0], symbols[1], 10000000000)
        invester.backtest(start, end)
    elif opt == "2":
        selected_option = "Invest"
        symbols = get_symbols(selected_option)
        amount = get_current_amount(selected_option)
        invester = Neo_invest.NeoInvest(symbols[0], symbols[1], amount)
        
        start, end = utils.today_and_month_ago()
        interval = ''
        h1_result = invester.backtest(start, end, '1h', False)
        m30_result = invester.backtest(start, end, '30m', False)
        
        end_diff = abs(h1_result['end'] - m30_result['end'])
        if end_diff <= 0.02:
            if h1_result['sharp'] > m30_result['sharp']:
                interval = '1h'
            else:
                interval = '30m'
        else:
            interval = '1h' if h1_result['end'] > m30_result['end'] else '30m'
        
        def action():
            global invester, interval
            hdt = 1 if interval == '1h' else 2
            invester.append_current_data()
            invester.action(hour_divided_time=hdt)
        
        print(f"{', '.join(symbols)}에 관해서 OU+TP Strategy를 {interval} 마다 가동합니다.")
        
        if interval == '1h':
            for hour in range(9, 16):
                schedule.every().day.at(f"{hour:02d}:01").do(action)
        elif interval == '30m':
            for hour in range(9, 16):
                schedule.every().day.at(f"{hour:02d}:01").do(action)
                schedule.every().day.at(f"{hour:02d}:31").do(action)
        while True:
            schedule.run_pending()
            time.sleep(1)
    elif opt == "3":
        for name, theme in utils.THEMES.items():
            corr_high_finder.find_stocks_to_invest(theme, name)