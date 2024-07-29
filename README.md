# Plato

# READ ME 읽어주세요.

저는 이 프로그램 기본판을 판매하지 않습니다. 프로그램을 사용하여 발생하는 모든 손실에 해당하는 것은 실행한 본인의 책임입니다.  
프로그램에 정보를 입력한 후 실행하면, 장이 열리는 즉시 모델들에 의해서 투자가 진행됩니다. 이에 발생하는 손실에 대해서, **저는 책임이 없음을 고지합니다**.
다시 말하지만 **저는 프로그램을 판매하지 않고, 오픈소스로 저의 모델을 공유합니다**. GUI와 TUI, 그 외 모든 프로그램들은 **강제로 설치되지 않으며** 사용자 본인이 **직접 다운로드** 하였으며 API와 관련된 모든 것들 또한 **직접 입력**하였고, 그로 인해 **투자(Invest)를 실행하면 투자가 된다는 것을 인지하셨음을 압니다**.

I do not sell the basic version of this program. Any losses arising from the use of the program are the responsibility of the user who executed the program.  
If you enter information into the program and run it, investments will be made by models as soon as the market opens. **Please note that I am not responsible for any losses arising from this**.
Again, **I don't sell the program, I just share my models as open source**. GUI, TUI, and all other programs are **not forcefully installed** and are **downloaded** by the user themselves, and everything related to the API is also **entered** directly, resulting in **investment**. I know you realize that if you run , you will be making an investment**.

# Stocks that 'Corr High Finder' Found (ONLY KOSPI STOCKS)

**Term: 2024-06-01 ~ 2024-07-27 by 1h**  
**Used Neo Strategy**

## Best Sharp

| stock pair | sharp | return | theme |
|------------|-------|--------|-------|
|010620.KS, 009540.KS|1.58|43%~45%|ship|
|012450.KS, 079550.KS|1.55|19%~42%|military|

## Best Return

| stock pair | sharp | return | theme |
|------------|-------|--------|-------|
|006360.KS, 047040.KS|0.83|11%~32%|building|
|329180.KS, 009540.KS|1.17|57%~59%|ship|
|009540.KS, 012450.KS|1.33|54%~56%|military|
|064350.KS, 012450.KS|1.19|34%~36%|military|

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