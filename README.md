# Fund Tracking & Analysis Dashboard

A financial analysis tool developed to track, manage, and predict investment fund performances on the Turkish TEFAS market. This terminal combines real-time data crawling, portfolio optimization, and advanced machine learning models for future projections.

## Features

* **Real-time Analysis:** Live data fetching from TEFAS with automated metric calculations including Volatility and Sharpe Ratio.
* **Core-Satellite Portfolio Management:** Organizes funds into "Core" for long-term stability and "Satellite" for high-growth alpha.
* **AI-Powered Predictions:** 
  * **Facebook Prophet:** Seasonal trend analysis and price projections.
  * **Monte Carlo Simulation:** 1,000+ stochastic path simulations for probability distributions.
* **Persistence:** Local SQLite database integration for transaction history and asset management.

## Tech Stack

* **Language:** Python 3.11+
* **Framework:** Streamlit
* **Analysis:** Pandas, NumPy, Facebook Prophet
* **Visualization:** Plotly
* **Database:** SQLite

## Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/compaxion/FonTakibiDashboard.git
   cd FonTakibiDashboard

2. **Create and activate virtual environment:**
   ```bash
    python -m venv .venv
    source .venv/bin/activate
   
3. **Install Dependencies:**
   ```bash
    pip install -r requirements.txt
   
4. **Run the application:**
    ```bash
   streamlit run app.py

## Methodology
The terminal utilizes the Sharpe Ratio to measure risk-adjusted returns, helping investors identify funds that provide the highest return for each unit of risk taken. The predictive models visualize both the "most likely" outcome and the extreme risk scenarios using confidence intervals.

Note: This project is developed for educational and personal financial tracking purposes. It does not constitute investment advice.