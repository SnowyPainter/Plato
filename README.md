# Plato

# Stocks that 'Corr High Finder' Found (ONLY KOSPI STOCKS)

**Term: 2024-06-01 ~ 2024-07-27 by 1h**  
**Used Neo Strategy**

## Best Sharp

| stock pair | sharp | return | theme |
|------------|-------|--------|-------|
|010620.KS 009540.KS|1.58|43%~45%|ship|
|012450.KS 079550.KS|1.55|19%~42%|military|

## Best Return

| stock pair | sharp | return | theme |
|------------|-------|--------|-------|
|006360.KS 047040.KS|0.83|11%~32%|building|
|329180.KS 009540.KS|1.17|57%~59%|ship|
|009540.KS 012450.KS|1.33|54%~56%|military|

# Returns

## Compare stocks
**('064350.KS', '012450.KS')**
> Without Volatility Predictor   
sharp 1.33, max 27%  
> *With Volatility Predictor*  
> 1. sharp 1.45, max 26.81%, end 24.13%  
> 2. sharp 1.40, max 26.55%, end 23.61%
> 3. sharp 1.40, max 26.74%, end 23.64%

**('012450.KS', '009540.KS')**  
> Without Volatility Predictor  
sharp 1.48, max 45%  
> *With Volatility Predictor*  
> 1. sharp 1.47, max 44.63%, end 40.69%
> 2. sharp 1.44, max 46.78%, end 42.19%
> 3. sharp 1.44, max 47.23%, end 42.63%

**('329180.KS', '010620.KS')**  
> Without Volatility Predictor  
sharp 1.4, max 36%  
> *With Volatility Predictor*  
> 1. sharp 1.5, max 35.73%, end 30.87%  
> 2. sharp 1.49, max 36.28%, end 31.40%
> 3. sharp 1.49, max 36.20%, end 31.31%

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

Volatility Forecaster predicts volatility of stocks. To use this model, just pass a raw price dataframe.  
Sometime, it isn't good for some stock pairs.