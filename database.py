import sqlite3
import pandas as pd
from datetime import datetime

DB_NAME = "portfolio.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            fund_code TEXT,
            transaction_type TEXT,
            amount_tl REAL,
            lot REAL,
            price REAL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tracked_funds (
            fund_code TEXT PRIMARY KEY,
            category TEXT
        )
    ''')

    # Eğer takip tablosu tamamen boşsa, varsayılan listeyi veritabanına yaz
    cursor.execute('SELECT COUNT(*) FROM tracked_funds')
    if cursor.fetchone()[0] == 0:
        default_core = ["FMG", "MKG", "GGK", "YAY", "AFT", "IHK", "IHT"]
        default_sat = ["ACC", "TCD", "IIH", "NRC"]

        for f in default_core:
            cursor.execute('INSERT INTO tracked_funds (fund_code, category) VALUES (?, ?)', (f, 'Core'))
        for f in default_sat:
            cursor.execute('INSERT INTO tracked_funds (fund_code, category) VALUES (?, ?)', (f, 'Satellite'))

    conn.commit()
    conn.close()



def add_tracked_fund(fund_code, category):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO tracked_funds (fund_code, category) VALUES (?, ?)', (fund_code, category))
    conn.commit()
    conn.close()

def remove_tracked_fund(fund_code):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tracked_funds WHERE fund_code = ?', (fund_code,))
    conn.commit()
    conn.close()

def get_tracked_funds():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM tracked_funds", conn)
    conn.close()

    core_funds = df[df['category'] == 'Core']['fund_code'].tolist()
    satellite_funds = df[df['category'] == 'Satellite']['fund_code'].tolist()

    return core_funds, satellite_funds

def add_transaction(fund_code, transaction_type, amount_tl, lot, price, date=None):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO transactions (date, fund_code, transaction_type, amount_tl, lot, price)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (date, fund_code, transaction_type, amount_tl, lot, price))
    conn.commit()
    conn.close()

def get_all_transactions():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM transactions", conn)
    conn.close()
    return df

def get_portfolio_summary():
    df = get_all_transactions()
    if df.empty:
        return pd.DataFrame()

    summary = []
    for fund in df['fund_code'].unique():
        fund_tx = df[df['fund_code'] == fund]

        alimlar = fund_tx[fund_tx['transaction_type'] == 'ALIM']
        satimlar = fund_tx[fund_tx['transaction_type'] == 'SATIM']

        toplam_alinan_lot = alimlar['lot'].sum()
        toplam_satilan_lot = satimlar['lot'].sum()
        kalan_lot = toplam_alinan_lot - toplam_satilan_lot

        if kalan_lot > 0:
            toplam_alim_maliyeti = alimlar['amount_tl'].sum()
            ortalama_maliyet = toplam_alim_maliyeti / toplam_alinan_lot if toplam_alinan_lot > 0 else 0

            summary.append({
                'Fon Kodu': fund,
                'Sahip Olunan Lot': kalan_lot,
                'Ortalama Maliyet (TL)': ortalama_maliyet,
                'Yatırılan Ana Para (TL)': kalan_lot * ortalama_maliyet
            })

    return pd.DataFrame(summary)

def clear_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM transactions')
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()