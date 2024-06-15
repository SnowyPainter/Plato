import pandas as pd
import utils

from datetime import timedelta
import matplotlib.pyplot as plt

def read_trades_csv(fname):
    df = pd.read_csv(fname)
    df.index = pd.to_datetime(df['date'], format="%Y-%m-%d %H:%M:%S%z")
    df.drop(columns=["date"], inplace=True)
    return df

def get_historical_same_size(df):
    first = df.index[0].date().strftime("%Y-%m-%d")
    last = (df.index[-1].date() + timedelta(days=1)).strftime("%Y-%m-%d")
    df['symbol'] = df['symbol'].apply(lambda x: x.split('.')[0].zfill(6)+'.'+x.split('.')[1])
    symbols = df['symbol'].unique()
    historical, symbols = utils.load_historical_datas(symbols, first, last, '1h')
    return historical, symbols

def plot(trades, historical, symbols):
    historical.index = historical.index.strftime('%Y-%m-%d %H')
    trades.index = trades.index.strftime('%Y-%m-%d %H')
    trade_points = trades.index.unique()
    filtered_historical = historical[historical.index.isin(trade_points)]
    norm_historical = filtered_historical
    fig = plt.figure(figsize=(10, 8))
    i = 1
    for symbol in symbols:
        ax = fig.add_subplot(6, 3, i)
        ax.set_title(symbol)
        signals = trades[trades['symbol'] == symbol]
        buy_signals = signals[signals['action'] == 'buy']
        sell_signals = signals[signals['action'] == 'sell']
        ax.plot(filtered_historical.index, filtered_historical[symbol+"_Price"], label=symbol)
        for signal, marker, color in zip([buy_signals, sell_signals], ['^', 'v'], ['green', 'red']):
            x = signal.index
            y = signal['price']
            ax.scatter(x, y, color=color, marker=marker, s=30)

        i += 1
    
    ax2 = fig.add_subplot(5, 3, i)
    ax2.set_title("evaluated")
    ax2.plot(trades.index, trades['evalu_amt'])    
    
    plt.legend()
    figManager = plt.get_current_fig_manager()
    figManager.window.showMaximized()
    plt.show()