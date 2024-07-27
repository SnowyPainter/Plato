# Plato

# Utils

## Preprocess Weights

To prevent the sum of the weights (ratios) from exceeding 1, first divide by the sum of the weights. The weights are then divided by the ratio of the purchaseable amount to the maximum manageable amount to determine the ratio to the manageable assets.
However, weights that are too small can become noise and may be ignored. Through this, the Sharpe ratio increased by about 0.1 and the rate of return increased by about 0%p to 3%p.

# Model

## Technical Trend Predictor

Trend predictor, requires RSI, ADX, Lag(1), MACD to predict trend during 1 hour. At least predicts 58% trends and At the best, almost 98%.

Using trend predictor, Max return 19% -> 25%, Lowest return -9% -> 0%. Also Sharp ratio could be higher.

It is stronger than SMA breaking through strategy.

So far, the predict accuracy over than 55%, it is better than without it.

## Price Predictor

Price Predictor predicts prices, but it is not useful about using only to predict price. but, making trend forecast is useful. 

With Technical Trend Predictor, Price Predictor affect that position.

## Volatility Forecaster

Volatility Forecaster predicts volatility of stocks. To use this model, make the linear regression and get coefficient. I grant some weights to trade.

So far, I cannot find environment to investment with this.

> With Volatility Forecaster  
* Backtest range 2024-06-01 ~ 2024-07-23 : 30m 
* Trade Count : 37
* End Return : 28.75 % 
* Worst ~ Best return -1.44 ~ 33.52 % 
* Sharp Ratio : 1.5076329237921464
* 329180.KS Profit : 1.65 %
* 010620.KS Profit : 35.16 %