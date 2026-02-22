import pandas as pd
from tefas import Crawler
import numpy as np
import streamlit as st
import time

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_single_fund(code):
    crawler = Crawler()
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.DateOffset(days=365)

    date_ranges = []
    current_start = start_date
    while current_start < end_date:
        current_end = min(current_start + pd.DateOffset(days=90), end_date)
        date_ranges.append((current_start, current_end))
        current_start = current_end + pd.DateOffset(days=1)

    print(f"-> {code} fonu TEFAS'tan çekiliyor...")
    fund_chunks = []

    try:
        for s_date, e_date in date_ranges:
            df_temp = crawler.fetch(
                start=s_date.strftime("%Y-%m-%d"),
                end=e_date.strftime("%Y-%m-%d"),
                name=code
            )

            if df_temp is not None and not df_temp.empty:
                df_temp.columns = df_temp.columns.str.lower()
                df_clean = df_temp[['code', 'date', 'price', 'title']].copy()
                fund_chunks.append(df_clean)

            time.sleep(0.2)

        if fund_chunks:
            combined_df = pd.concat(fund_chunks, ignore_index=True)
            combined_df = combined_df.drop_duplicates(subset=['date'])
            time.sleep(0.5)
            return combined_df
        else:
            print(f"!!️ {code} için hiçbir veri bulunamadı.")
            return pd.DataFrame()

    except Exception as e:
        print(f"!! {code} çekilirken hata oluştu: {e}")
        return pd.DataFrame()


# Ana Fonksiyon (Döngü)
def fetch_live_fund_data(fund_codes):
    all_data = []
    for code in fund_codes:

        with st.spinner(f"-> {code} fonu TEFAS'tan çekiliyor..."):
            df = fetch_single_fund(code)

        if not df.empty:
            all_data.append(df)

    if not all_data:
        return pd.DataFrame()

    df = pd.concat(all_data, ignore_index=True)
    df['price'] = df['price'].astype(float)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(by=['code', 'date'])

    return df

def calculate_metrics(df, risk_free_rate=45.0):
    pivot_df = df.pivot(index='date', columns='code', values='price')
    pivot_df = pivot_df.ffill()

    latest_prices = pivot_df.iloc[-1]
    last_date = pivot_df.index[-1]

    target_3m = last_date - pd.DateOffset(months=3)
    idx_3m = pivot_df.index.get_indexer([target_3m], method='nearest')[0]
    return_3m = ((pivot_df.iloc[-1] - pivot_df.iloc[idx_3m]) / pivot_df.iloc[idx_3m]) * 100

    target_1m = last_date - pd.DateOffset(months=1)
    idx_1m = pivot_df.index.get_indexer([target_1m], method='nearest')[0]
    return_1m = ((pivot_df.iloc[-1] - pivot_df.iloc[idx_1m]) / pivot_df.iloc[idx_1m]) * 100

    target_1w = last_date - pd.DateOffset(weeks=1)
    idx_1w = pivot_df.index.get_indexer([target_1w], method='nearest')[0]
    return_1w = ((pivot_df.iloc[-1] - pivot_df.iloc[idx_1w]) / pivot_df.iloc[idx_1w]) * 100

    try:
        first_day_of_year = pivot_df[pivot_df.index.year == last_date.year].iloc[0]
        return_ytd = ((pivot_df.iloc[-1] - first_day_of_year) / first_day_of_year) * 100
    except:
        return_ytd = np.nan

    target_1y = last_date - pd.DateOffset(years=1)
    try:
        idx_1y = pivot_df.index.get_indexer([target_1y], method='nearest')[0]
        return_1y = ((pivot_df.iloc[-1] - pivot_df.iloc[idx_1y]) / pivot_df.iloc[idx_1y]) * 100
    except:
        return_1y = np.nan

    daily_returns = pivot_df.pct_change().dropna()
    annual_volatility = daily_returns.std() * np.sqrt(252) * 100
    sharpe_ratio = (return_3m - (risk_free_rate / 4)) / annual_volatility

    metrics_df = pd.DataFrame({
        'Güncel Fiyat (TL)': latest_prices,
        'Haftalık Getiri (%)': return_1w,
        'Aylık Getiri (%)': return_1m,
        '3 Aylık Getiri (%)': return_3m,
        'YTD (%)': return_ytd,
        '1 Yıllık Getiri (%)': return_1y,
        'Volatilite (Risk %)': annual_volatility,
        'Sharpe Oranı': sharpe_ratio
    })

    metrics_df = metrics_df.round({
        'Güncel Fiyat (TL)': 4,
        'Haftalık Getiri (%)': 2,
        'Aylık Getiri (%)': 2,
        '3 Aylık Getiri (%)': 2,
        'YTD (%)': 2,
        '1 Yıllık Getiri (%)': 2,
        'Volatilite (Risk %)': 2,
        'Sharpe Oranı': 2
    })

    return metrics_df.sort_values(by='Sharpe Oranı', ascending=False)