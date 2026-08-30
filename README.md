# Trading Journal

A local-first trading journal built with Python + Streamlit + SQLite.

## Features
- Dashboard with equity curve, P&L, win rate, profit factor, expectancy and drawdown
- Trade entry with automatic risk, R:R, P&L and R calculations
- Funded / evaluation / personal account tracking
- Daily loss and drawdown progress
- Trade screenshots with before/entry/management/exit/post-trade categories
- Search and filtering
- CSV export
- Strategy, session, symbol, timeframe, mistake and direction analytics
- Psychology / daily journal
- Trading playbook and checklist
- No external database required

## Run

1. Install Python 3.10+
2. Open a terminal in this folder.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Start:

```bash
streamlit run app.py
```

The browser will open the journal. Your database and screenshots are stored in `data/`.
