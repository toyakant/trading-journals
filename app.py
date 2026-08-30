
import streamlit as st
import sqlite3, os, uuid, shutil
from datetime import datetime, date, time
from pathlib import Path
import pandas as pd
import numpy as np

APP_DIR = Path(__file__).parent
DB = APP_DIR / "data" / "journal.db"
IMG_DIR = APP_DIR / "data" / "trade_images"
IMG_DIR.mkdir(parents=True, exist_ok=True)
DB.parent.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="Trading Journal", page_icon="📈", layout="wide")

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS accounts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        account_type TEXT NOT NULL,
        broker TEXT,
        starting_balance REAL DEFAULT 0,
        current_balance REAL DEFAULT 0,
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
        entry_time TEXT,
        exit_time TEXT,
        symbol TEXT,
        direction TEXT,
        timeframe TEXT,
        session TEXT,
        strategy TEXT,
        setup TEXT,
        market_condition TEXT,
        bias TEXT,
        entry REAL,
        stop_loss REAL,
        take_profit REAL,
        exit_price REAL,
        contracts REAL,
        point_value REAL,
        fees REAL DEFAULT 0,
        risk_dollars REAL DEFAULT 0,
        planned_rr REAL DEFAULT 0,
        pnl REAL DEFAULT 0,
        r_multiple REAL DEFAULT 0,
        holding_minutes REAL DEFAULT 0,
        confidence INTEGER DEFAULT 5,
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
    c.commit(); c.close()

init_db()

def q(sql, params=()):
    c=conn(); rows=c.execute(sql, params).fetchall(); c.close()
    return pd.DataFrame([dict(x) for x in rows])

def execute(sql, params=()):
    c=conn(); cur=c.execute(sql, params); c.commit(); last=cur.lastrowid; c.close(); return last

def calc_trade(direction, entry, stop, target, exitp, contracts, point_value, fees):
    if not all(x is not None for x in [entry, stop, target, exitp, contracts, point_value]):
        return 0,0,0
    risk = abs(entry-stop)*contracts*point_value
    reward = abs(target-entry)*contracts*point_value
    rr = reward/risk if risk else 0
    gross = ((exitp-entry) if direction=="Long" else (entry-exitp))*contracts*point_value
    pnl = gross-fees
    r = pnl/risk if risk else 0
    return risk, rr, pnl, r

def fmt_money(x):
    return f"${x:,.2f}"

def load_accounts():
    return q("SELECT * FROM accounts ORDER BY name")

def load_trades():
    return q("""SELECT t.*, a.name account_name, a.account_type
                FROM trades t LEFT JOIN accounts a ON a.id=t.account_id
                ORDER BY trade_date DESC, entry_time DESC, id DESC""")

st.title("📈 Trading Journal")
st.caption("A local-first trading journal for futures, funded accounts, evaluations, and personal trading.")

accounts = load_accounts()
trades = load_trades()

with st.sidebar:
    st.header("Navigation")
    page = st.radio("Go to", ["Dashboard","Add Trade","Trades","Accounts","Analytics","Daily Journal","Playbook"])
    st.divider()
    st.caption("Data is stored locally in data/journal.db")
    if st.button("Refresh"):
        st.rerun()

# ---------- DASHBOARD ----------
if page == "Dashboard":
    st.subheader("Performance Dashboard")
    if trades.empty:
        st.info("No trades yet. Add your first trade to populate the dashboard.")
    else:
        pnl = trades["pnl"].fillna(0)
        wins = pnl[pnl>0]; losses = pnl[pnl<0]
        total = len(trades)
        winrate = len(wins)/total*100
        gross_win = wins.sum()
        gross_loss = abs(losses.sum())
        pf = gross_win/gross_loss if gross_loss else np.inf
        avg_r = trades["r_multiple"].mean()
        expectancy = pnl.mean()
        peak = pnl.cumsum().cummax()
        equity = pnl.cumsum()
        dd = equity-peak
        maxdd = abs(dd.min()) if len(dd) else 0
        c1,c2,c3,c4,c5,c6 = st.columns(6)
        c1.metric("Net P&L", fmt_money(pnl.sum()))
        c2.metric("Win Rate", f"{winrate:.1f}%")
        c3.metric("Profit Factor", "∞" if np.isinf(pf) else f"{pf:.2f}")
        c4.metric("Avg R", f"{avg_r:.2f}R")
        c5.metric("Expectancy", fmt_money(expectancy))
        c6.metric("Max Drawdown", fmt_money(maxdd))

        left,right=st.columns(2)
        with left:
            st.markdown("### Equity Curve")
            edf=pd.DataFrame({"Trade":range(1,len(equity)+1),"Equity":equity.values})
            st.line_chart(edf.set_index("Trade"))
        with right:
            st.markdown("### P&L by Day")
            daily=trades.groupby("trade_date",as_index=False)["pnl"].sum()
            daily["trade_date"]=pd.to_datetime(daily["trade_date"])
            st.bar_chart(daily.set_index("trade_date")["pnl"])

        st.markdown("### Quick Breakdown")
        a,b,c=st.columns(3)
        with a:
            st.write("**By Strategy**")
            st.dataframe(trades.groupby("strategy")["pnl"].agg(["count","sum","mean"]).sort_values("sum",ascending=False), use_container_width=True)
        with b:
            st.write("**By Session**")
            st.dataframe(trades.groupby("session")["pnl"].agg(["count","sum","mean"]).sort_values("sum",ascending=False), use_container_width=True)
        with c:
            st.write("**By Symbol**")
            st.dataframe(trades.groupby("symbol")["pnl"].agg(["count","sum","mean"]).sort_values("sum",ascending=False), use_container_width=True)

# ---------- ADD TRADE ----------
elif page == "Add Trade":
    st.subheader("➕ Add Trade")
    if accounts.empty:
        st.warning("Create an account first in Accounts.")
    else:
        with st.form("trade_form"):
            c1,c2,c3=st.columns(3)
            account_id=c1.selectbox("Account", accounts["id"], format_func=lambda x: accounts.loc[accounts.id==x,"name"].iloc[0])
            trade_date=c2.date_input("Trade date", date.today())
            symbol=c3.text_input("Symbol", "MNQ").upper()
            c1,c2,c3,c4=st.columns(4)
            direction=c1.selectbox("Direction",["Long","Short"])
            timeframe=c2.selectbox("Timeframe",["1m","2m","3m","5m","15m","30m","1H","4H","1D","1W"])
            session=c3.selectbox("Session",["Asia","London","New York","NY Open","NY AM","NY PM","Other"])
            strategy=c4.text_input("Strategy", "CRT")
            c1,c2,c3,c4=st.columns(4)
            entry=c1.number_input("Entry",value=0.0,format="%.4f")
            stop=c2.number_input("Stop Loss",value=0.0,format="%.4f")
            target=c3.number_input("Take Profit",value=0.0,format="%.4f")
            exitp=c4.number_input("Exit Price",value=0.0,format="%.4f")
            c1,c2,c3,c4=st.columns(4)
            contracts=c1.number_input("Contracts",min_value=0.01,value=1.0,step=1.0)
            point_value=c2.number_input("$ per point / contract",min_value=0.01,value=2.0)
            fees=c3.number_input("Fees / commission",min_value=0.0,value=0.0)
            setup=c4.text_input("Setup / Model", "Sweep + FVG")
            c1,c2,c3=st.columns(3)
            market=c1.selectbox("Market Condition",["Trending","Ranging","Volatile","Choppy","Expansion","Reversal"])
            bias=c2.selectbox("Bias",["Bullish","Bearish","Neutral"])
            confidence=c3.slider("Confidence",1,10,7)
            c1,c2,c3=st.columns(3)
            emotion_before=c1.selectbox("Emotion Before",["Calm","Confident","Uncertain","FOMO","Fear","Frustrated","Excited"])
            emotion_during=c2.selectbox("Emotion During",["Calm","Focused","Anxious","Greedy","Fearful","Impatient","Overconfident"])
            emotion_after=c3.selectbox("Emotion After",["Satisfied","Neutral","Frustrated","Angry","Regret","Confident"])
            mistakes=st.multiselect("Mistakes",[
                "None","FOMO","Revenge trade","Overtrading","Entered early","Entered late",
                "Moved SL","Took profit early","Oversized","No confirmation","Against bias",
                "Outside session","Broke daily loss rule","Emotional trade","Poor exit"
            ])
            c1,c2=st.columns(2)
            entry_reason=c1.text_area("Why did you enter?")
            exit_reason=c2.text_area("Why did you exit?")
            c1,c2=st.columns(2)
            lesson=c1.text_area("Lesson learned")
            notes=c2.text_area("Additional notes")
            images=st.file_uploader("Trade screenshots",type=["png","jpg","jpeg","webp"],accept_multiple_files=True)
            image_type=st.selectbox("Screenshot type",["Before Trade","Entry","Management","Exit","Post-Trade"])
            captions=st.text_input("Screenshot caption","")
            submitted=st.form_submit_button("Save Trade",type="primary")

        if submitted:
            if entry==0 or stop==0 or target==0 or exitp==0:
                st.error("Entry, stop, target, and exit price are required.")
            else:
                risk,rr,pnl,r=calc_trade(direction,entry,stop,target,exitp,contracts,point_value,fees)
                uid="TRD-"+datetime.now().strftime("%Y%m%d")+"-"+uuid.uuid4().hex[:6].upper()
                now=datetime.now().isoformat(timespec="seconds")
                trade_id=execute("""INSERT INTO trades
                (trade_uid,account_id,trade_date,entry_time,exit_time,symbol,direction,timeframe,session,strategy,setup,
                 market_condition,bias,entry,stop_loss,take_profit,exit_price,contracts,point_value,fees,risk_dollars,
                 planned_rr,pnl,r_multiple,confidence,emotion_before,emotion_during,emotion_after,mistakes,
                 entry_reason,exit_reason,lesson,notes,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (uid,int(account_id),str(trade_date),"","",symbol,direction,timeframe,session,strategy,setup,market,bias,
                 entry,stop,target,exitp,contracts,point_value,fees,risk,rr,pnl,r,confidence,emotion_before,
                 emotion_during,emotion_after,", ".join(mistakes),entry_reason,exit_reason,lesson,notes,now))
                for f in images or []:
                    suffix=Path(f.name).suffix.lower()
                    path=IMG_DIR/(uid+"_"+uuid.uuid4().hex[:8]+suffix)
                    with open(path,"wb") as out: out.write(f.getbuffer())
                    execute("INSERT INTO images(trade_id,image_type,path,caption,created_at) VALUES(?,?,?,?,?)",
                            (trade_id,image_type,str(path),captions,now))
                st.success(f"Saved {uid} | P&L {fmt_money(pnl)} | {r:.2f}R")
                st.rerun()

# ---------- TRADES ----------
elif page == "Trades":
    st.subheader("📋 Trade History")
    if trades.empty:
        st.info("No trades recorded.")
    else:
        c1,c2,c3,c4=st.columns(4)
        search=c1.text_input("Search symbol/strategy")
        direction_f=c2.multiselect("Direction",["Long","Short"])
        result_f=c3.selectbox("Result",["All","Wins","Losses"])
        account_f=c4.multiselect("Account",accounts["name"].tolist())
        df=trades.copy()
        if search: df=df[df.symbol.str.contains(search,case=False,na=False)|df.strategy.str.contains(search,case=False,na=False)]
        if direction_f: df=df[df.direction.isin(direction_f)]
        if result_f=="Wins": df=df[df.pnl>0]
        if result_f=="Losses": df=df[df.pnl<0]
        if account_f: df=df[df.account_name.isin(account_f)]
        display_cols=["trade_uid","trade_date","account_name","symbol","direction","session","strategy","entry","exit_price","contracts","risk_dollars","planned_rr","pnl","r_multiple","mistakes"]
        st.dataframe(df[display_cols],use_container_width=True,hide_index=True)
        st.download_button("Export CSV",df.to_csv(index=False).encode(),"trading_journal.csv","text/csv")
        if not df.empty:
            uid=st.selectbox("Open trade",df.trade_uid.tolist())
            row=df[df.trade_uid==uid].iloc[0]
            st.divider()
            st.markdown(f"### {uid} — {row.symbol} {row.direction}")
            c1,c2,c3,c4,c5=st.columns(5)
            c1.metric("P&L",fmt_money(row.pnl))
            c2.metric("R",f"{row.r_multiple:.2f}R")
            c3.metric("Risk",fmt_money(row.risk_dollars))
            c4.metric("Planned R:R",f"{row.planned_rr:.2f}")
            c5.metric("Confidence",str(row.confidence)+"/10")
            st.write(f"**Strategy:** {row.strategy}  |  **Setup:** {row.setup}  |  **Session:** {row.session}  |  **Bias:** {row.bias}")
            a,b=st.columns(2)
            with a:
                st.write("**Entry reason**"); st.write(row.entry_reason or "—")
                st.write("**Exit reason**"); st.write(row.exit_reason or "—")
            with b:
                st.write("**Mistakes**"); st.write(row.mistakes or "None")
                st.write("**Lesson**"); st.write(row.lesson or "—")
            imgs=q("SELECT * FROM images WHERE trade_id=? ORDER BY id",(int(row.id),))
            if not imgs.empty:
                st.markdown("### 📸 Trade Images")
                cols=st.columns(min(3,len(imgs)))
                for i,(_,im) in enumerate(imgs.iterrows()):
                    with cols[i%len(cols)]:
                        if os.path.exists(im.path):
                            st.image(im.path,caption=f"{im.image_type}: {im.caption or ''}",use_container_width=True)

# ---------- ACCOUNTS ----------
elif page == "Accounts":
    st.subheader("💼 Accounts")
    with st.form("account_form"):
        c1,c2,c3=st.columns(3)
        name=c1.text_input("Account name","My Funded Account")
        atype=c2.selectbox("Type",["Funded","Evaluation","Personal"])
        broker=c3.text_input("Broker / Prop Firm")
        c1,c2,c3,c4=st.columns(4)
        starting=c1.number_input("Starting balance",min_value=0.0,value=1000.0)
        target=c2.number_input("Profit target",min_value=0.0,value=0.0)
        daily=c3.number_input("Daily loss limit",min_value=0.0,value=0.0)
        maxdd=c4.number_input("Max drawdown",min_value=0.0,value=0.0)
        c1,c2=st.columns(2)
        consistency=c1.number_input("Consistency %",min_value=0.0,max_value=100.0,value=0.0)
        min_days=c2.number_input("Minimum trading days",min_value=0,value=0,step=1)
        notes=st.text_area("Rules / notes")
        if st.form_submit_button("Create Account",type="primary"):
            execute("""INSERT INTO accounts(name,account_type,broker,starting_balance,current_balance,profit_target,
            daily_loss_limit,max_drawdown,consistency_pct,min_trading_days,notes,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",(name,atype,broker,starting,starting,target,daily,maxdd,consistency,min_days,notes,datetime.now().isoformat()))
            st.success("Account created."); st.rerun()

    accounts=load_accounts()
    if not accounts.empty:
        st.markdown("### Account Overview")
        tr=load_trades()
        for _,a in accounts.iterrows():
            t=tr[tr.account_id==a.id] if not tr.empty else pd.DataFrame()
            pnl=t.pnl.sum() if not t.empty else 0
            balance=a.starting_balance+pnl
            target_progress=(pnl/a.profit_target*100) if a.profit_target else 0
            daily_loss=0
            if not t.empty:
                today=str(date.today())
                daily_loss=t[t.trade_date==today].pnl.sum()
            with st.container(border=True):
                c1,c2,c3,c4=st.columns(4)
                c1.metric(a["name"],a["account_type"])
                c2.metric("Balance",fmt_money(balance),fmt_money(pnl))
                c3.metric("Today's P&L",fmt_money(daily_loss))
                c4.metric("Target Progress",f"{target_progress:.1f}%" if a.profit_target else "N/A")
                if a.daily_loss_limit:
                    st.progress(min(1,max(0,abs(min(0,daily_loss))/a.daily_loss_limit)),text=f"Daily loss used: {fmt_money(abs(min(0,daily_loss)))} / {fmt_money(a.daily_loss_limit)}")
                if a.max_drawdown:
                    peak=a.starting_balance+max(0,t.pnl.cumsum().max() if not t.empty else 0)
                    dd=max(0,peak-balance)
                    st.progress(min(1,dd/a.max_drawdown),text=f"Drawdown: {fmt_money(dd)} / {fmt_money(a.max_drawdown)}")

# ---------- ANALYTICS ----------
elif page == "Analytics":
    st.subheader("📊 Advanced Analytics")
    if trades.empty:
        st.info("Add trades to unlock analytics.")
    else:
        df=trades.copy()
        tabs=st.tabs(["Strategy","Session","Symbol","Timeframe","Mistakes","Long vs Short"])
        with tabs[0]:
            st.dataframe(df.groupby("strategy").agg(Trades=("id","count"),Net_PnL=("pnl","sum"),Win_Rate=("pnl",lambda x:(x>0).mean()*100),Avg_R=("r_multiple","mean"),Avg_RR=("planned_rr","mean")).sort_values("Net_PnL",ascending=False),use_container_width=True)
        with tabs[1]:
            st.dataframe(df.groupby("session").agg(Trades=("id","count"),Net_PnL=("pnl","sum"),Win_Rate=("pnl",lambda x:(x>0).mean()*100),Avg_R=("r_multiple","mean")).sort_values("Net_PnL",ascending=False),use_container_width=True)
        with tabs[2]:
            st.dataframe(df.groupby("symbol").agg(Trades=("id","count"),Net_PnL=("pnl","sum"),Win_Rate=("pnl",lambda x:(x>0).mean()*100),Avg_R=("r_multiple","mean")).sort_values("Net_PnL",ascending=False),use_container_width=True)
        with tabs[3]:
            st.dataframe(df.groupby("timeframe").agg(Trades=("id","count"),Net_PnL=("pnl","sum"),Win_Rate=("pnl",lambda x:(x>0).mean()*100),Avg_R=("r_multiple","mean")).sort_values("Net_PnL",ascending=False),use_container_width=True)
        with tabs[4]:
            m=df.assign(mistake=df.mistakes.fillna("").str.split(", ")).explode("mistake")
            m=m[m.mistake.notna() & (m.mistake!="") & (m.mistake!="None")]
            if m.empty: st.info("No mistakes tagged.")
            else: st.dataframe(m.groupby("mistake").agg(Trades=("id","count"),Net_PnL=("pnl","sum"),Avg_R=("r_multiple","mean")).sort_values("Net_PnL"),use_container_width=True)
        with tabs[5]:
            st.dataframe(df.groupby("direction").agg(Trades=("id","count"),Net_PnL=("pnl","sum"),Win_Rate=("pnl",lambda x:(x>0).mean()*100),Avg_R=("r_multiple","mean")),use_container_width=True)

# ---------- DAILY JOURNAL ----------
elif page == "Daily Journal":
    st.subheader("🧠 Daily Trading Psychology")
    d=st.date_input("Journal date",date.today())
    with st.form("daily"):
        c1,c2,c3,c4,c5=st.columns(5)
        sleep=c1.slider("Sleep",1,10,7)
        energy=c2.slider("Energy",1,10,7)
        focus=c3.slider("Focus",1,10,7)
        stress=c4.slider("Stress",1,10,3)
        confidence=c5.slider("Confidence",1,10,7)
        notes=st.text_area("Pre/post-market notes")
        if st.form_submit_button("Save Daily Journal"):
            execute("""INSERT INTO journal_days(journal_date,sleep,energy,focus,stress,confidence,notes,created_at)
                       VALUES(?,?,?,?,?,?,?,?)
                       ON CONFLICT(journal_date) DO UPDATE SET sleep=excluded.sleep,energy=excluded.energy,
                       focus=excluded.focus,stress=excluded.stress,confidence=excluded.confidence,notes=excluded.notes""",
                    (str(d),sleep,energy,focus,stress,confidence,notes,datetime.now().isoformat()))
            st.success("Daily journal saved.")
    logs=q("SELECT * FROM journal_days ORDER BY journal_date DESC")
    if not logs.empty: st.dataframe(logs,use_container_width=True,hide_index=True)

# ---------- PLAYBOOK ----------
else:
    st.subheader("📚 Trading Playbook")
    st.markdown("""
### Recommended playbook structure

**1. HTF Bias**
- Daily / 4H / 1H direction
- Major liquidity
- Key highs/lows
- Order blocks
- Fair value gaps
- Previous day/week levels

**2. Setup Checklist**
- ☐ Bias established
- ☐ Liquidity identified
- ☐ Sweep occurred
- ☐ Displacement confirmed
- ☐ Entry model present
- ☐ Stop location logical
- ☐ Minimum R:R met
- ☐ Session/time is valid
- ☐ Risk is within limits

**3. Execution Rules**
- Define risk before entry
- Never widen the stop
- Avoid revenge trades
- Respect daily loss limit
- Screenshot before and after
- Record the reason, not just the result

**4. Review**
After every trade ask:
- Did I follow the plan?
- Was the setup valid?
- Was execution clean?
- What did price do afterward?
- What one thing will I repeat?
- What one thing will I eliminate?
""")
