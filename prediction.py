import numpy as np
import pandas as pd
from prophet import Prophet

def run_monte_carlo_simulation(fund_history, days_to_simulate=30, num_simulations=1000):
    returns = fund_history.pct_change().dropna()
    mu = returns.mean()
    sigma = returns.std()
    last_price = fund_history.iloc[-1]

    simulations = np.zeros((days_to_simulate, num_simulations))
    simulations[0, :] = last_price

    for t in range(1, days_to_simulate):
        Z = np.random.normal(0, 1, num_simulations)
        daily_returns = np.exp((mu - 0.5 * sigma ** 2) + sigma * Z)
        simulations[t, :] = simulations[t - 1, :] * daily_returns

    final_prices = simulations[-1, :]

    return {
        'last_price': last_price,
        'expected': np.mean(final_prices),
        'worst': np.percentile(final_prices, 5),
        'p25': np.percentile(final_prices, 25),
        'median': np.percentile(final_prices, 50),
        'p75': np.percentile(final_prices, 75),
        'best': np.percentile(final_prices, 95),
        'simulations': simulations
    }

def run_prophet_forecast(fund_data, days_to_predict=30):
    df_prophet = fund_data[['date', 'price']].copy()
    df_prophet = df_prophet.rename(columns={'date': 'ds', 'price': 'y'})

    # Modeli başlat (Haftalık ve yıllık döngüleri yakalamaya açık)
    m = Prophet(
        daily_seasonality=False,
        yearly_seasonality=True,
        weekly_seasonality=True,
        changepoint_prior_scale=0.05  # Trend kırılımlarına duyarlılık ayarı
    )

    m.fit(df_prophet)

    # Gelecek 30 gün için boş bir takvim oluştur ve tahminleri doldur
    future = m.make_future_dataframe(periods=days_to_predict)
    forecast = m.predict(future)

    return forecast, m