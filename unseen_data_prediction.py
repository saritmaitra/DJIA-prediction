# -*- coding: utf-8 -*-
"""unseen data_prediction.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1JjUcFefPhRAWXpqHY0PP44quuFXhPC-L
"""

# Commented out IPython magic to ensure Python compatibility.
!pip install python_wtd
from python_wtd import WTD
import pandas  as pd
import matplotlib.pyplot as plt
import numpy as np
# %matplotlib inline
from sklearn import metrics # for the check the error and accuracy of the model
from sklearn.metrics import mean_squared_error, r2_score, accuracy_score
from math import sqrt
from xgboost import XGBRegressor
import xgboost as xgb
from sklearn.model_selection import train_test_split, KFold, StratifiedKFold, cross_val_score, GridSearchCV
import warnings
import seaborn as sns
sns.set()
import pandas_datareader as web
warnings.filterwarnings("ignore")
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 150)

df = web.DataReader('^DJI', data_source = 'yahoo', start = '2000-01-01')
print(df.head())
print('\n')
print(df.shape)

dataset = df.copy()
import plotly.graph_objects as go
fig = go.Figure(data=[go.Candlestick(x=dataset.index,
                open=dataset['Open'],
                high=dataset['High'],
                low=dataset['Low'],
                close=dataset['Close'])])
fig.show()
print('\n')

dataset.isnull().sum()

# empirical quantile of daily returns
import scipy.stats
dataset['daily_return'] = dataset['Adj Close'].pct_change()
round(dataset["daily_return"],2).quantile(0.05)

import seaborn as sns
sns.despine(left=True)

# Plot a simple histogram with binsize determined automatically
sns.distplot(dataset['daily_return'], color="green")
plt.title('Dow Jones')
plt.grid(True)
plt.show()

"""The 0.05 (p=0.05) empirical quantile of daily returns is at -0.02. This means that with 95% confidence, the worst daily loss will not exceed 2% (of the investment).

***As an example, if we have a €1M investment, our one-day 5% VaR is 0.02 * €1M = € 2k***
"""

dataset['daily_return'].plot(figsize = (10,5), grid=True)
plt.title('Daily return plot')
plt.show()

dataset['volatility'] = dataset['daily_return'].rolling(252).std()*(252**0.5)
dataset['volatility'].plot(figsize = (10,5), grid=True)
plt.title('Volatility plot')
plt.show()

# resetting index 
dataset.reset_index(inplace = True) 
dataset.tail()

dataset = dataset.sort_values(by = 'Date', ascending=True)
dataset.tail()

print(dataset.loc[[(len(dataset) -252)]]) # closing price 252 days back

plt.rcParams["figure.figsize"] = (10,6)
days = 252
start_price = 28745.089844 # Taken from above

#delta t
dt = 1/252
mu = dataset['daily_return'].mean() # mean return
sigma = dataset['daily_return'].std()  # volatility

#Function takes in stock price, number of days to run, mean and standard deviation values
def stock_monte_carlo(start_price, days, mu, sigma):
    price = np.zeros(days)
    price[0] = start_price
    
    shock = np.zeros(days)
    drift = np.zeros(days)
    
    for x in range(1,days):
        #Shock and drift formulas taken from the Monte Carlo formula
        shock[x] = np.random.normal(loc=mu*dt,scale=sigma*np.sqrt(dt))
        drift[x] = mu * dt
        
        #New price = Old price + Old price*(shock+drift)
        price[x] = price[x-1] + (price[x-1] * (drift[x]+shock[x]))
    return price
    
plt.plot(stock_monte_carlo(start_price, days, mu, sigma))
plt.xlabel('Days')
plt.ylabel('Price (US$)')
plt.title('Monte-Carlo Analysis for Dow Jones')
plt.show()

runs = 10000
simulations = np.zeros(runs)

for run in range(runs):
    simulations[run] = stock_monte_carlo(start_price,days,mu,sigma)[days-1]
q = np.percentile(simulations,1)

plt.hist(simulations, bins = 200)

plt.figtext(0.6,0.8,s="Start price: $%.2f" %start_price)
plt.figtext(0.6,0.7,"Mean final price: $%.2f" % simulations.mean())
plt.figtext(0.6,0.6,"VaR(0.99): $%.2f" % (start_price -q,))
plt.figtext(0.15,0.6, "q(0.99): $%.2f" % q)
plt.axvline(x=q, linewidth=4, color='r')

plt.title(u"Final price distribution for Dow Jones after %s days" %days, weight='bold')
plt.show()

"""## Setting index"""

#dataset.set_index('Date', inplace=True)
dq = df.copy()
dq['h_o'] = dq['High'] - dq['Open'] # distance between Highest and Opening price
dq['l_o'] = dq['Low'] - dq['Open']
dq['Open-Close'] = dq.Open - dq.Close
dq['High-Low'] = dq.High - dq.Low 
dq['volume_gap'] = dq.Volume.pct_change()
# feature engineering
dq['day_of_week'] = dq.index.dayofweek
dq['day_of_month'] = dq.index.day

ema_12 = dq['Adj Close'].ewm(span=10).mean()
ema_26 = dq['Adj Close'].ewm(span=26).mean()
dq['ROC'] = ((dq['Adj Close'] - dq['Adj Close'].shift(5)) / (dq['Adj Close'].shift(5)))*100

delta = dq['Adj Close'].diff()
window = 14
up_days = delta.copy()
up_days[delta<=0]=0.0
down_days = abs(delta.copy())
down_days[delta>0]=0.0
RS_up = up_days.rolling(window).mean()
RS_down = down_days.rolling(window).mean()
dq['rsi'] = 100-100/(1+RS_up/RS_down)
dq['macd'] = ema_12 - ema_26
#print(dataset)

lags = 3
# Create the shifted lag series of prior trading period close values
for i in range(0, lags):
    dq["Lag%s" % str(i+1)] = dq["Adj Close"].shift(i+1).pct_change()

future_pred = int(15)
dq['prediction'] = dq['Adj Close'].shift(-future_pred)
dq.head()

dq = dq.drop(['High','Low','Open','Close','Volume',	'Adj Close'],1)

plt.figure(figsize= (15,6))
pd.plotting.scatter_matrix(dq, grid=True, diagonal='kde', figsize= (15,10))
plt.show()

dq = dq.drop(['High','Low','Open','Close','Volume',	'Adj Close'],1)

dq.dropna(inplace=True)
X = dq.drop(['prediction'],1)
X_fcast = X[-future_pred:] # future prediction set
X = X[:-future_pred] # removing last 15 rows
y = y[:-future_pred]
#y = dq.prediction

from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, random_state=42)

# Commented out IPython magic to ensure Python compatibility.
from sklearn import linear_model
ols = linear_model.LinearRegression()
ols.fit(X_train, y_train)

from sklearn.metrics import mean_squared_error, r2_score
# The mean squared error
print("Mean squared error: %.2f"% mean_squared_error(y_train, ols.predict(X_train)))
# Explained variance score: 1 is perfect prediction
print('Variance score: %.2f' % r2_score(y_train, ols.predict(X_train)))
# The mean squared error
print("Mean squared error: %.2f"
# % mean_squared_error(y_test, ols.predict(X_test)))
# Explained variance score: 1 is perfect prediction
print('Variance score: %.2f' % r2_score(y_test, ols.predict(X_test)))

print('Training Variance score (R^2)', r2_score(y_train, ols.predict(X_train)))
# Explained variance score: 1 is perfect prediction
print('Test Variance score (R^2): ', r2_score(y_test, ols.predict(X_test)))

reg = XGBRegressor(objective ='reg:squarederror', n_jobs=-1).fit(X_train, y_train)

# Explained variance score: 1 is perfect prediction
print('Variance score: %.2f' % r2_score(y_train, reg.predict(X_train)))
# Explained variance score: 1 is perfect prediction
print('Variance score: %.2f' % r2_score(y_test, reg.predict(X_test)))

prediction = reg.predict(X_fcast)
print('\033[4mExpected Close price for next 15 days\033[0m')
print(prediction)
print('\n')

rmse = np.sqrt(mean_squared_error(y_test[:future_pred], prediction[:future_pred]))
print('Test RMSE: %.3f' % rmse)

df.tail(2)

d = df[['Adj Close']].tail(len(prediction)); 
d

d = df[['Adj Close']].tail(len(prediction)); 
d.reset_index(inplace = True)
d = d.append(pd.DataFrame({'Date': pd.date_range(start = d.Date.iloc[-1], 
                                             periods = (len(d)+1), freq = 'D', closed = 'right')}))
d = d.tail(future_pred); 
d.set_index('Date', inplace = True)
prediction = pd.DataFrame(prediction)
prediction.index = d.index
prediction.rename(columns = {0: 'Forecasted_price'}, inplace=True)
prediction

df[['Adj Close']].tail(60).plot(figsize = (10,5), grid = True)
prediction.plot()

fig = go.Figure()
n = prediction.index[0]
fig.add_trace(go.Scatter(x = df.index[-100:], y = df['Adj Close'][-100:],
                         marker = dict(color ="red"), name = "Actual close price"))
fig.add_trace(go.Scatter(x = prediction.index, y = prediction['Forecasted_price'], marker=dict(
        color = "green"), name = "Future prediction"))


fig.update_xaxes(showline = True, linewidth = 2, linecolor='black', mirror = True, showspikes = True,)
fig.update_yaxes(showline = True, linewidth = 2, linecolor='black', mirror = True, showspikes = True,)
fig.update_layout(
    title= "15 days days DJIA Forecast", 
    yaxis_title = 'DJIA (US$)',
    hovermode = "x",
    hoverdistance = 100, # Distance to show hover label of data point
    spikedistance = 1000,
    shapes = [dict(
        x0 = n, x1 = n, y0 = 0, y1 = 1, xref = 'x', yref = 'paper',
        line_width = 2)],
    annotations = [dict(x = n, y = 0.05, xref = 'x', yref = 'paper', showarrow = False, 
                        xanchor = 'left', text = 'Prediction')]) 
fig.update_layout(autosize = False, width = 1000, height = 400,)
fig.show()

from xgboost import plot_importance
# Feature importance
plt.rcParams['figure.figsize'] = [15, 8]
plot_importance(reg)

from sklearn.linear_model import LinearRegression

linreg = LinearRegression(n_jobs=-1)
linreg.fit(X_train, y_train)
confidence = linreg.score(X_test, y_test)
print("Confidence %:", round(confidence*100, 2))
print('\n')

print('\n')
prediction = linreg.predict(X_fcast)
print('\033[4mExpected Close price for next 30 days\033[0m')
print(prediction)
print('\n')

RMSE = np.sqrt(mean_squared_error(y_test[:future_pred], prediction[:future_pred]))
print('Test RMSE: %.3f' % RMSE)

import datetime
# assigning date to the predicted values
df1['pred'] = np.nan
last_date = df1.iloc[-1].name
last_unix = last_date.timestamp()
one_day = 86400
next_unix = last_unix + one_day 

for i in prediction1:
  next_date = datetime.datetime.fromtimestamp(next_unix)
  next_unix += one_day
  df1.loc[next_date] = [np.nan for _ in range(len(df1.columns)-1)] + [i]

#create an index of just the date portion of our index (this is the slow step)
ts_days = pd.to_datetime(df1['pred'].index.date)

#create a range of business days over that period
bdays = pd.bdate_range(start=df1['pred'].index[0].date(), end=df1['pred'].index[-1].date())

#Filter the series to just those days contained in the business day range.
df1['pred'] = round(df1.pred[ts_days.isin(bdays)],2)
print('\033[4mExpected Close price for next 4 weeks\033[0m')
df1['pred'].tail(30)

df1['Close'].tail(60).plot(figsize = (10,5), grid=True)
df1['pred'].plot()
plt.title('Predicted Close price- Linear Regression')
plt.show()