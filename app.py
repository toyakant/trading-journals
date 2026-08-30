
import streamlit as st
import sqlite3, uuid, os
from pathlib import Path
from datetime import datetime, date
import pandas as pd
import numpy as np
import calendar as pycalendar

APP_DIR = Path(__file__).parent
DB = APP_DIR / "data" / "journal.db"
IMG_DIR = APP_DIR / "data" / "trade_images"
DB.parent.mkdir(parents=True, exist_ok=True)
IMG_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="Trading Journal", page_icon="📈", layout="wide")

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS accounts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        account_type TEXT NOT NULL,
        broker TEXT,
        starting_balance REAL NOT NULL DEFAULT 0,
        profit_target REAL DEFAULT 0,
        daily_loss_limit REAL DEFAULT 0,
        max_drawdown REAL DEFAULT 0,
        consistency_pct REAL DEFAULT 0,
        min_trading_days INTEGER DEFAULT 0,
        notes TEXT,
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS trades(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_uid TEXT UNIQUE,
        account_id INTEGER,
        trade_date TEXT,
        symbol TEXT,
        direction TEXT,
        timeframe TEXT,
        session TEXT,
        strategy TEXT,
        setup TEXT,
        market_condition TEXT,
        bias TEXT,

        risk_amount REAL NOT NULL,
        closing_amount REAL NOT NULL,
        pnl REAL NOT NULL,
        r_multiple REAL NOT NULL,
        result TEXT NOT NULL,

        confidence INTEGER,
        emotion_before TEXT,
        emotion_during TEXT,
        emotion_after TEXT,
        mistakes TEXT,
        entry_reason TEXT,
        exit_reason TEXT,
        lesson TEXT,
        notes TEXT,
        created_at TEXT,

        FOREIGN KEY(account_id) REFERENCES accounts(id)
    );

    CREATE TABLE IF NOT EXISTS images(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_id INTEGER,
        image_type TEXT,
        path TEXT,
        caption TEXT,
        created_at TEXT,
        FOREIGN KEY(trade_id) REFERENCES trades(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS journal_days(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        journal_date TEXT UNIQUE,
        sleep INTEGER,
        energy INTEGER,
        focus INTEGER,
        stress INTEGER,
        confidence INTEGER,
        notes TEXT,
        created_at TEXT
    );
    """)
    c.commit()
    c.close()

init_db()

def execute(sql, params=()):
    c = db()
    cur = c.execute(sql, params)
    c.commit()
    last = cur.lastrowid
    c.close()
    return last

def query(sql, params=()):
    c = db()
    rows = c.execute(sql, params).fetchall()
    c.close()
    return pd.DataFrame([dict(r) for r in rows])

def money(x):
    x = float(x or 0)
    return f"${x:,.2f}"

def accounts_df():
    return query("SELECT * FROM accounts ORDER BY name")

def trades_df():
    return query("""
        SELECT t.*, a.name AS account_name, a.account_type
        FROM trades t
        LEFT JOIN accounts a ON a.id=t.account_id
        ORDER BY trade_date DESC, id DESC
    """)

def account_stats(account_id):
    a = query("SELECT * FROM accounts WHERE id=?", (account_id,))
    t = query("SELECT * FROM trades WHERE account_id=? ORDER BY id", (account_id,))
    if a.empty:
        return None, t
    row = a.iloc[0]
    pnl = t.pnl.sum() if not t.empty else 0
    balance = row.starting_balance + pnl
    return row, t

def calc_pnl(risk, closing_amount):
    pnl = float(closing_amount)
    r = pnl / risk if risk > 0 else 0
    result = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "BE")
    return pnl, r, result


accounts = accounts_df()
trades = trades_df()

st.title("📈 Trading Journal")
st.caption("Balance-based journaling: enter what you risked and your closing balance. P&L and R are calculated automatically.")

with st.sidebar:
    st.header("Navigation")
    page = st.radio(
        "Go to",
        ["Dashboard", "Calendar", "Add Trade", "Trades", "Accounts", "Analytics", "Daily Journal", "Playbook"]
    )
    st.divider()
    st.caption("Local SQLite storage")
    if st.button("Refresh"):
        st.rerun()

# ================= DASHBOARD =================
if page == "Dashboard":
    st.subheader("Performance Dashboard")

    if trades.empty:
        st.info("No trades yet. Add your first trade.")
    else:
        pnl = trades.pnl.astype(float)
        wins = pnl[pnl > 0]
        losses = pnl[pnl < 0]

        total = len(trades)
        winrate = len(wins) / total * 100
        gross_wins = wins.sum()
        gross_losses = abs(losses.sum())
        pf = gross_wins / gross_losses if gross_losses else np.inf
        avg_r = trades.r_multiple.mean()
        expectancy = pnl.mean()

        equity = pnl.cumsum()
        peak = equity.cummax()
        drawdown = equity - peak
        maxdd = abs(drawdown.min()) if len(drawdown) else 0

        c1,c2,c3,c4,c5,c6 = st.columns(6)
        c1.metric("Net P&L", money(pnl.sum()))
        c2.metric("Win Rate", f"{winrate:.1f}%")
        c3.metric("Profit Factor", "∞" if np.isinf(pf) else f"{pf:.2f}")
        c4.metric("Average R", f"{avg_r:.2f}R")
        c5.metric("Expectancy", money(expectancy))
        c6.metric("Max Drawdown", money(maxdd))

        left,right = st.columns(2)
        with left:
            st.markdown("### Equity Curve")
            eq = pd.DataFrame({"Trade": range(1,len(equity)+1), "Equity": equity.values})
            st.line_chart(eq.set_index("Trade"))

        with right:
            st.markdown("### Daily P&L")
            daily = trades.groupby("trade_date", as_index=False).pnl.sum()
            daily["trade_date"] = pd.to_datetime(daily.trade_date)
            st.bar_chart(daily.set_index("trade_date").pnl)

        st.markdown("### Account Snapshot")
        for _, a in accounts.iterrows():
            row, at = account_stats(int(a.id))
            if row is None:
                continue
            apnl = at.pnl.sum() if not at.empty else 0
            bal = row.starting_balance + apnl
            with st.container(border=True):
                c1,c2,c3,c4 = st.columns(4)
                c1.metric(row["name"], row["account_type"])
                c2.metric("Current Balance", money(bal))
                c3.metric("Net P&L", money(apnl))
                c4.metric("Trades", len(at))

# ================= CALENDAR =================
elif page == "Calendar":
    st.subheader("📅 Trading Calendar")
    st.caption("Green = profitable day • Red = losing day • Gray = no trading")

    if trades.empty:
        st.info("Your calendar will populate after you add trades.")
    else:
        years = sorted(pd.to_datetime(trades.trade_date).dt.year.unique(), reverse=True)
        c1,c2,c3 = st.columns(3)
        year = c1.selectbox("Year", years)
        months = list(range(1,13))
        month = c2.selectbox("Month", months, format_func=lambda x: pycalendar.month_name[x])
        selected_account = c3.selectbox(
            "Account", ["All"] + accounts.name.tolist()
        )

        df = trades.copy()
        df["trade_date"] = pd.to_datetime(df.trade_date)
        df = df[df.trade_date.dt.year == year]
        df = df[df.trade_date.dt.month == month]

        if selected_account != "All":
            df = df[df.account_name == selected_account]

        daily = df.groupby(df.trade_date.dt.day).agg(
            pnl=("pnl","sum"),
            trades=("id","count"),
            wins=("result", lambda x: (x=="WIN").sum()),
            losses=("result", lambda x: (x=="LOSS").sum())
        )

        weeks = pycalendar.monthcalendar(year, month)
        headers = st.columns(7)
        for h, name in zip(headers, ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]):
            h.markdown(f"**{name}**")

        for week in weeks:
            cols = st.columns(7)
            for i, day_num in enumerate(week):
                with cols[i]:
                    if day_num == 0:
                        st.write("")
                    else:
                        if day_num in daily.index:
                            d = daily.loc[day_num]
                            p = float(d.pnl)
                            icon = "🟢" if p > 0 else ("🔴" if p < 0 else "⚪")
                            st.markdown(f"### {day_num} {icon}")
                            st.write(money(p))
                            st.caption(f"{int(d.trades)} trade(s)")
                        else:
                            st.markdown(f"### {day_num}")
                            st.caption("No trades")

        st.divider()
        st.markdown("### Selected Month Summary")
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Month P&L", money(df.pnl.sum() if not df.empty else 0))
        c2.metric("Trading Days", df.trade_date.dt.date.nunique() if not df.empty else 0)
        c3.metric("Trades", len(df))
        c4.metric("Win Rate", f"{(df.result=='WIN').mean()*100:.1f}%" if not df.empty else "0.0%")

        if not df.empty:
            st.markdown("### Daily Details")
            summary = df.groupby("trade_date").agg(
                Trades=("id","count"),
                PnL=("pnl","sum"),
                Wins=("result",lambda x:(x=="WIN").sum()),
                Losses=("result",lambda x:(x=="LOSS").sum()),
                Avg_R=("r_multiple","mean")
            ).reset_index()
            summary["trade_date"] = summary.trade_date.dt.date
            st.dataframe(summary.sort_values("trade_date", ascending=False), use_container_width=True, hide_index=True)

# ================= ADD TRADE =================
elif page == "Add Trade":
    st.subheader("➕ Add Trade")

    if accounts.empty:
        st.warning("Create an account first under Accounts.")
    else:
        with st.form("trade_form"):
            c1,c2,c3 = st.columns(3)
            account_id = c1.selectbox(
                "Account",
                accounts.id.tolist(),
                format_func=lambda x: accounts.loc[accounts.id==x,"name"].iloc[0]
            )
            trade_date = c2.date_input("Trade Date", date.today())
            symbol = c3.text_input("Symbol", "MNQ").upper()

            c1,c2,c3,c4 = st.columns(4)
            direction = c1.selectbox("Direction", ["Long","Short"])
            timeframe = c2.selectbox("Timeframe", ["1m","2m","3m","5m","15m","30m","1H","4H","1D","1W"])
            session = c3.selectbox("Session", ["Asia","London","New York","NY Open","NY AM","NY PM","Other"])
            strategy = c4.text_input("Strategy", "CRT")

            c1,c2,c3 = st.columns(3)
            setup = c1.text_input("Setup / Model", "Sweep + FVG")
            market = c2.selectbox("Market Condition", ["Trending","Ranging","Volatile","Choppy","Expansion","Reversal"])
            bias = c3.selectbox("Bias", ["Bullish","Bearish","Neutral"])

            st.markdown("### 💰 Risk & Closing Amount")
            st.caption("Enter only your risk and the signed result of the trade. Positive = profit, 0 = break-even, negative = loss.")
            c1,c2 = st.columns(2)
            risk = c1.number_input("Amount Risked ($)", min_value=0.01, value=20.0, step=1.0)
            closing_amount = c2.number_input("Closing Amount ($)", value=0.0, step=1.0, format="%.2f")

            preview_pnl, preview_r, preview_result = calc_pnl(risk, closing_amount)
            c1,c2,c3 = st.columns(3)
            c1.metric("Automatic P&L", money(preview_pnl))
            c2.metric("Automatic R", f"{preview_r:.2f}R")
            c3.metric("Result", preview_result)

            confidence = st.slider("Confidence", 1, 10, 7)

            c1,c2,c3 = st.columns(3)
            emotion_before = c1.selectbox("Emotion Before", ["Calm","Confident","Uncertain","FOMO","Fear","Frustrated","Excited"])
            emotion_during = c2.selectbox("Emotion During", ["Calm","Focused","Anxious","Greedy","Fearful","Impatient","Overconfident"])
            emotion_after = c3.selectbox("Emotion After", ["Satisfied","Neutral","Frustrated","Angry","Regret","Confident"])

            mistakes = st.multiselect("Mistakes", [
                "None","FOMO","Revenge trade","Overtrading","Entered early","Entered late",
                "Moved SL","Took profit early","Oversized","No confirmation","Against bias",
                "Outside session","Broke daily loss rule","Emotional trade","Poor exit"
            ])

            c1,c2 = st.columns(2)
            entry_reason = c1.text_area("Why did you enter?")
            exit_reason = c2.text_area("Why did you exit?")

            c1,c2 = st.columns(2)
            lesson = c1.text_area("Lesson Learned")
            notes = c2.text_area("Additional Notes")

            images = st.file_uploader(
                "Trade Screenshots",
                type=["png","jpg","jpeg","webp"],
                accept_multiple_files=True
            )
            image_type = st.selectbox("Screenshot Type", ["Before Trade","Entry","Management","Exit","Post-Trade"])
            caption = st.text_input("Screenshot Caption")

            submitted = st.form_submit_button("Save Trade", type="primary")

        if submitted:
            if risk <= 0:
                st.error("Risk amount must be greater than $0.")
            else:
                pnl, r, result = calc_pnl(risk, closing_amount)
                uid = "TRD-" + datetime.now().strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:6].upper()
                now = datetime.now().isoformat(timespec="seconds")

                trade_id = execute("""
                    INSERT INTO trades(
                        trade_uid,account_id,trade_date,symbol,direction,timeframe,session,
                        strategy,setup,market_condition,bias,risk_amount,
                        closing_amount,pnl,r_multiple,result,confidence,emotion_before,
                        emotion_during,emotion_after,mistakes,entry_reason,exit_reason,
                        lesson,notes,created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    uid,int(account_id),str(trade_date),symbol,direction,timeframe,session,
                    strategy,setup,market,bias,risk,closing_amount,pnl,r,result,
                    confidence,emotion_before,emotion_during,emotion_after,
                    ", ".join(mistakes),entry_reason,exit_reason,lesson,notes,now
                ))

                for f in images or []:
                    suffix = Path(f.name).suffix.lower()
                    path = IMG_DIR / (uid + "_" + uuid.uuid4().hex[:8] + suffix)
                    with open(path, "wb") as out:
                        out.write(f.getbuffer())
                    execute(
                        "INSERT INTO images(trade_id,image_type,path,caption,created_at) VALUES(?,?,?,?,?)",
                        (trade_id,image_type,str(path),caption,now)
                    )

                st.success(f"Saved {uid}: {money(pnl)} / {r:.2f}R")
                st.rerun()

# ================= TRADES =================
elif page == "Trades":
    st.subheader("📋 Trade History")

    if trades.empty:
        st.info("No trades recorded.")
    else:
        c1,c2,c3,c4 = st.columns(4)
        search = c1.text_input("Search")
        direction_f = c2.multiselect("Direction", ["Long","Short"])
        result_f = c3.selectbox("Result", ["All","Wins","Losses","Break-even"])
        account_f = c4.multiselect("Account", accounts.name.tolist())

        df = trades.copy()
        if search:
            mask = (
                df.symbol.str.contains(search, case=False, na=False) |
                df.strategy.str.contains(search, case=False, na=False) |
                df.setup.str.contains(search, case=False, na=False)
            )
            df = df[mask]
        if direction_f:
            df = df[df.direction.isin(direction_f)]
        if result_f == "Wins":
            df = df[df.result=="WIN"]
        elif result_f == "Losses":
            df = df[df.result=="LOSS"]
        elif result_f == "Break-even":
            df = df[df.result=="BE"]
        if account_f:
            df = df[df.account_name.isin(account_f)]

        cols = [
            "trade_uid","trade_date","account_name","symbol","direction","session",
            "strategy","risk_amount","closing_amount","pnl","r_multiple","result","mistakes"
        ]
        st.dataframe(df[cols], use_container_width=True, hide_index=True)
        st.download_button("Export CSV", df.to_csv(index=False).encode(), "trading_journal.csv", "text/csv")

        if not df.empty:
            uid = st.selectbox("Open Trade", df.trade_uid.tolist())
            row = df[df.trade_uid==uid].iloc[0]

            st.divider()
            st.markdown(f"### {uid} — {row.symbol} {row.direction}")

            c1,c2,c3,c4,c5 = st.columns(5)
            c1.metric("P&L", money(row.pnl))
            c2.metric("R", f"{row.r_multiple:.2f}R")
            c3.metric("Risk", money(row.risk_amount))
            c4.metric("Closing Amount", money(row.closing_amount))
            c5.metric("Result", row.result)

            st.write(
                f"**Account:** {row.account_name}  |  **Strategy:** {row.strategy}  | "
                f"**Setup:** {row.setup}  | **Session:** {row.session} | **Timeframe:** {row.timeframe}"
            )

            a,b = st.columns(2)
            with a:
                st.markdown("**Why did I enter?**")
                st.write(row.entry_reason or "—")
                st.markdown("**Why did I exit?**")
                st.write(row.exit_reason or "—")
            with b:
                st.markdown("**Mistakes**")
                st.write(row.mistakes or "None")
                st.markdown("**Lesson**")
                st.write(row.lesson or "—")

            imgs = query("SELECT * FROM images WHERE trade_id=? ORDER BY id", (int(row.id),))
            if not imgs.empty:
                st.markdown("### 📸 Image Session")
                columns = st.columns(min(3,len(imgs)))
                for i, im in imgs.iterrows():
                    with columns[i % len(columns)]:
                        if os.path.exists(im.path):
                            st.image(im.path, caption=f"{im.image_type} — {im.caption or ''}", use_container_width=True)

# ================= ACCOUNTS =================
elif page == "Accounts":
    st.subheader("💼 Accounts")

    with st.form("account_form"):
        c1,c2,c3 = st.columns(3)
        name = c1.text_input("Account Name", "My Funded Account")
        atype = c2.selectbox("Account Type", ["Funded","Evaluation","Personal"])
        broker = c3.text_input("Broker / Prop Firm")

        c1,c2,c3,c4 = st.columns(4)
        starting = c1.number_input("Starting Balance", min_value=0.0, value=1000.0, step=1.0)
        target = c2.number_input("Profit Target", min_value=0.0, value=0.0, step=1.0)
        daily = c3.number_input("Daily Loss Limit", min_value=0.0, value=0.0, step=1.0)
        maxdd = c4.number_input("Max Drawdown", min_value=0.0, value=0.0, step=1.0)

        c1,c2 = st.columns(2)
        consistency = c1.number_input("Consistency Requirement %", min_value=0.0, max_value=100.0, value=0.0)
        min_days = c2.number_input("Minimum Trading Days", min_value=0, value=0, step=1)

        notes = st.text_area("Account Rules / Notes")

        if st.form_submit_button("Create Account", type="primary"):
            execute("""
                INSERT INTO accounts(
                    name,account_type,broker,starting_balance,profit_target,
                    daily_loss_limit,max_drawdown,consistency_pct,min_trading_days,notes,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """, (
                name,atype,broker,starting,target,daily,maxdd,consistency,min_days,
                notes,datetime.now().isoformat()
            ))
            st.success("Account created.")
            st.rerun()

    accounts = accounts_df()

    if not accounts.empty:
        st.markdown("### Account Overview")
        for _, a in accounts.iterrows():
            row, at = account_stats(int(a.id))
            apnl = at.pnl.sum() if not at.empty else 0
            balance = a.starting_balance + apnl

            with st.container(border=True):
                c1,c2,c3,c4 = st.columns(4)
                c1.metric(a["name"], a["account_type"])
                c2.metric("Current Balance", money(balance))
                c3.metric("Net P&L", money(apnl))
                c4.metric("Trades", len(at))

                if a.profit_target > 0:
                    progress = max(0, min(1, apnl / a.profit_target))
                    st.progress(progress, text=f"Profit target: {money(max(0,apnl))} / {money(a.profit_target)}")

                if a.max_drawdown > 0:
                    equity = a.starting_balance + at.pnl.cumsum() if not at.empty else pd.Series([a.starting_balance])
                    peak = equity.cummax()
                    current_dd = max(0, float((peak - equity).iloc[-1]))
                    dd_progress = max(0, min(1,current_dd/a.max_drawdown))
                    st.progress(dd_progress, text=f"Current drawdown: {money(current_dd)} / {money(a.max_drawdown)}")

# ================= ANALYTICS =================
elif page == "Analytics":
    st.subheader("📊 Analytics")

    if trades.empty:
        st.info("Add trades to unlock analytics.")
    else:
        df = trades.copy()

        tabs = st.tabs(["Strategy","Session","Symbol","Timeframe","Mistakes","Long vs Short","R Distribution"])

        with tabs[0]:
            st.dataframe(
                df.groupby("strategy").agg(
                    Trades=("id","count"),
                    Net_PnL=("pnl","sum"),
                    Win_Rate=("result",lambda x:(x=="WIN").mean()*100),
                    Avg_R=("r_multiple","mean"),
                    Total_R=("r_multiple","sum")
                ).sort_values("Net_PnL",ascending=False),
                use_container_width=True
            )

        with tabs[1]:
            st.dataframe(
                df.groupby("session").agg(
                    Trades=("id","count"),
                    Net_PnL=("pnl","sum"),
                    Win_Rate=("result",lambda x:(x=="WIN").mean()*100),
                    Avg_R=("r_multiple","mean")
                ).sort_values("Net_PnL",ascending=False),
                use_container_width=True
            )

        with tabs[2]:
            st.dataframe(
                df.groupby("symbol").agg(
                    Trades=("id","count"),
                    Net_PnL=("pnl","sum"),
                    Win_Rate=("result",lambda x:(x=="WIN").mean()*100),
                    Avg_R=("r_multiple","mean")
                ).sort_values("Net_PnL",ascending=False),
                use_container_width=True
            )

        with tabs[3]:
            st.dataframe(
                df.groupby("timeframe").agg(
                    Trades=("id","count"),
                    Net_PnL=("pnl","sum"),
                    Win_Rate=("result",lambda x:(x=="WIN").mean()*100),
                    Avg_R=("r_multiple","mean")
                ).sort_values("Net_PnL",ascending=False),
                use_container_width=True
            )

        with tabs[4]:
            m = df.assign(mistake=df.mistakes.fillna("").str.split(", ")).explode("mistake")
            m = m[(m.mistake!="") & (m.mistake!="None")]
            if m.empty:
                st.info("No mistakes tagged.")
            else:
                st.dataframe(
                    m.groupby("mistake").agg(
                        Trades=("id","count"),
                        Net_PnL=("pnl","sum"),
                        Avg_R=("r_multiple","mean")
                    ).sort_values("Net_PnL"),
                    use_container_width=True
                )

        with tabs[5]:
            st.dataframe(
                df.groupby("direction").agg(
                    Trades=("id","count"),
                    Net_PnL=("pnl","sum"),
                    Win_Rate=("result",lambda x:(x=="WIN").mean()*100),
                    Avg_R=("r_multiple","mean")
                ),
                use_container_width=True
            )

        with tabs[6]:
            st.bar_chart(df.r_multiple.value_counts().sort_index())

# ================= DAILY JOURNAL =================
elif page == "Daily Journal":
    st.subheader("🧠 Daily Trading Psychology")
    d = st.date_input("Journal Date", date.today())

    with st.form("daily"):
        c1,c2,c3,c4,c5 = st.columns(5)
        sleep = c1.slider("Sleep",1,10,7)
        energy = c2.slider("Energy",1,10,7)
        focus = c3.slider("Focus",1,10,7)
        stress = c4.slider("Stress",1,10,3)
        confidence = c5.slider("Confidence",1,10,7)
        notes = st.text_area("Notes")

        if st.form_submit_button("Save Daily Journal"):
            execute("""
                INSERT INTO journal_days(
                    journal_date,sleep,energy,focus,stress,confidence,notes,created_at
                ) VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(journal_date) DO UPDATE SET
                    sleep=excluded.sleep,energy=excluded.energy,focus=excluded.focus,
                    stress=excluded.stress,confidence=excluded.confidence,notes=excluded.notes
            """,(str(d),sleep,energy,focus,stress,confidence,notes,datetime.now().isoformat()))
            st.success("Saved.")

    logs = query("SELECT * FROM journal_days ORDER BY journal_date DESC")
    if not logs.empty:
        st.dataframe(logs,use_container_width=True,hide_index=True)

# ================= PLAYBOOK =================
else:
    st.subheader("📚 Trading Playbook")
    st.markdown("""
### HTF Bias
- ☐ Daily / 4H / 1H direction
- ☐ Major liquidity
- ☐ Key highs/lows
- ☐ Order blocks
- ☐ Fair value gaps
- ☐ Previous day/week levels

### Entry Checklist
- ☐ Bias established
- ☐ Liquidity identified
- ☐ Sweep occurred
- ☐ Displacement confirmed
- ☐ Entry model present
- ☐ Risk defined
- ☐ Minimum R:R met
- ☐ Session/time is valid
- ☐ Daily loss limit respected

### Execution Rules
- Define risk before entry
- Never widen the stop
- Avoid revenge trades
- Avoid FOMO
- Screenshot before and after
- Record the reason, not just the result

### Review
- Did I follow my plan?
- Was the setup valid?
- Was execution clean?
- What did price do afterward?
- What should I repeat?
- What should I eliminate?
""")
