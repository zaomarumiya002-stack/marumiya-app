import os
os.environ["STREAMLIT_THEME_BASE"] = "light"
os.environ["STREAMLIT_THEME_PRIMARY_COLOR"] = "#2563EB"
os.environ["STREAMLIT_THEME_BACKGROUND_COLOR"] = "#F8FAFC"
os.environ["STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR"] = "#F1F5F9"
os.environ["STREAMLIT_THEME_TEXT_COLOR"] = "#0F172A"

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid
from datetime import datetime, timedelta, date
import gspread
from google.oauth2.service_account import Credentials
import numpy as np

def to_int(v):
    try:
        if isinstance(v, pd.Series): v = v.sum()
        if pd.isna(v) or str(v).strip() == "": return 0
        return int(float(v))
    except: return 0

def format_date_jp(d):
    if d is None: return ""
    try:
        if pd.isna(d) or d == "": return ""
    except: pass
    weekdays = ["月","火","水","木","金","土","日"]
    try:
        if isinstance(d, str): d = pd.to_datetime(d.split(" ")[0])
        return f"{d.strftime('%Y/%m/%d')} ({weekdays[d.weekday()]})"
    except: return str(d).split(" ")[0]

def safe_dt_date(series):
    return pd.to_datetime(series, errors='coerce').dt.date

def is_special_order(rem):
    return "特注" in str(rem) or "チャーター便" in str(rem)

def make_csv_bytes(df):
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

st.set_page_config(page_title="丸実屋 統合管理", page_icon="🏭", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');
html, body, [data-testid="stAppViewContainer"] { font-family: 'Noto Sans JP', sans-serif !important; font-size: 15px !important; background: #F8FAFC !important; }
p, span, label, div { color: #0F172A !important; }
[data-testid="stSidebar"] { background: linear-gradient(180deg,#1E293B 0%,#0F172A 100%) !important; border-right: none !important; }
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label, [data-testid="stSidebar"] div { color: #CBD5E1 !important; }
[data-testid="stSidebar"] .stButton > button { height: 46px !important; font-size: 14px !important; border-radius: 8px !important; font-weight: 600 !important; background: rgba(255,255,255,0.07) !important; color: #E2E8F0 !important; border: 1px solid rgba(255,255,255,0.1) !important; transition: all .2s !important; }
[data-testid="stSidebar"] .stButton > button:hover { background: rgba(37,99,235,0.4) !important; border-color: #3B82F6 !important; color: #fff !important; }
[data-testid="stSidebar"] .stButton > button[kind="primary"] { background: #2563EB !important; color: #fff !important; border-color: #1D4ED8 !important; }
.page-header { padding: 14px 24px; border-radius: 12px; margin-bottom: 16px; background: linear-gradient(135deg,#1E3A8A 0%,#3B82F6 100%); }
.page-header h1 { color: white !important; margin: 0 !important; font-size: 19px !important; font-weight: 800 !important; }
[data-testid="stPills"] button { padding: 16px 30px !important; font-size: 20px !important; font-weight: 900 !important; border-radius: 12px !important; border: 2px solid #CBD5E1 !important; margin: 6px !important; min-height: 60px !important; line-height: 1.4 !important; transition: all .15s !important; }
[data-testid="stPills"] button[aria-selected="true"] { background: #2563EB !important; color: #fff !important; box-shadow: 0 4px 14px rgba(37,99,235,0.4) !important; border-color: #1D4ED8 !important; }
.info-card { background: white; border-radius: 12px; padding: 16px 20px; box-shadow: 0 1px 6px rgba(0,0,0,0.07); border-left: 5px solid #2563EB; margin-bottom: 10px; }
.info-card.green  { border-left-color: #059669; } .info-card.red { border-left-color: #DC2626; } .info-card.yellow { border-left-color: #D97706; }
.kpi-row { display:flex; gap:12px; margin-bottom:16px; }
.kpi-box { flex:1; background:white; border-radius:10px; padding:14px 18px; box-shadow:0 1px 5px rgba(0,0,0,0.07); text-align:center; border-top: 4px solid #2563EB; }
.sched-table { width:100%; border-collapse:collapse; background:white; font-size:14px; border-radius:10px; overflow:hidden; }
.sched-table th { background:#1E293B; color:white; padding:10px 12px; text-align:left; } .sched-table td { padding:9px 12px; border-bottom:1px solid #F1F5F9; vertical-align:top; }
.badge { display:inline-block; padding:2px 8px; border-radius:20px; font-size:11px; font-weight:700; }
.badge-special { background:#7C3AED; color:white !important; } .badge-charter { background:#0891B2; color:white !important; }
.shortage-red { color:#DC2626 !important; font-weight:900 !important; }
.drill-panel { background:#F0F7FF; border-radius:12px; padding:18px 20px; border:2px solid #BFDBFE; margin-top:12px; }
.task-card { background:white; border-radius:10px; padding:14px 16px; box-shadow:0 2px 8px rgba(0,0,0,0.08); border-left:5px solid #2563EB; margin-bottom:10px; }
.task-card.critical { border-left-color:#DC2626; background:#FFF5F5; } .task-card.warning  { border-left-color:#D97706; background:#FFFBEB; } .task-card.ok { border-left-color:#059669; background:#F0FDF4; }
.section-title { font-size:15px; font-weight:800; color:#1E293B; border-left:4px solid #2563EB; padding-left:10px; margin:18px 0 10px; }
</style>
""", unsafe_allow_html=True)

def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.markdown("<div style='text-align:center;margin-top:60px;'><span style='font-size:72px;'>🏭</span><h2 style='color:#1E3A8A;'>丸実屋　受発注管理 ログイン</h2></div>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            pwd = st.text_input("パスワードを入力", type="password")
            if st.button("ログイン", use_container_width=True, type="primary"):
                if pwd == st.secrets["app_password"]: st.session_state["password_correct"] = True; st.rerun()
                else: st.error("❌ パスワードが違います")
        st.stop()
check_password()

@st.cache_resource
def get_client():
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

client = get_client()
sheet  = client.open_by_url(st.secrets["spreadsheet_url"])

def load_data_from_cloud(name):
    cols_def = {
        "orders":           ["ID","納品予定日","顧客名","大カテゴリ","製品名","ケース数","運送会社","備考","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考","不良廃棄フラグ","日付未定フラグ","登録日時"],
        "manufactures":     ["ID","製造予定日","大カテゴリ","製品名","ケース数","リパックフラグ","備考","登録日時"],
        "master":           ["大カテゴリ","製品名","初期在庫数","使用資材名","資材使用数","入数","単位区分","特注フラグ","チャーターフラグ","時間あたり生産量","歩留まり率","リードタイム時間","安全在庫数","段取りグループ"],
        "customers":        ["顧客名","ふりがな","帳合先","支店名"],
        "packaging_master": ["資材名","品番","規格","仕入先","保管場所","単位","初期在庫","発注点","発注リードタイム"],
        "packaging_logs":   ["ID","登録日","資材名","処理区分","数量","理由","備考","関連製品名","理論在庫","登録日時"],
        "shipping_master":  ["運送会社名"],
        "special_schedule": ["ID","受注ID","製品名","顧客名","納品予定日","出荷予定日","備考","更新日時"],
    }
    target_cols = cols_def.get(name, [])
    if not target_cols: return pd.DataFrame()
    try: ws = sheet.worksheet(name)
    except:
        ws = sheet.add_worksheet(title=name, rows="1000", cols="30")
        if name == "shipping_master": ws.update(values=[target_cols,["ヤマト運輸"],["佐川急便"],["自社配送"]], range_name="A1")
        else: ws.update(values=[target_cols], range_name="A1")
    try:
        data = ws.get_all_values()
        if len(data) <= 1: return pd.DataFrame(columns=target_cols)
        df = pd.DataFrame(data[1:], columns=data[0])
        df.columns = df.columns.str.strip().str.replace(' ','').str.replace('　','')
        df = df.loc[:, ~df.columns.duplicated()]
        df = df.reindex(columns=target_cols, fill_value="")
        num_cols = ["ケース数","初期在庫数","資材使用数","初期在庫","発注点","数量","理論在庫"]
        for c in num_cols:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).apply(to_int)
        date_cols = ["納品予定日","製造予定日","登録日","登録日時","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","出荷予定日","更新日時"]
        for c in date_cols:
            if c in df.columns: df[c] = pd.to_datetime(df[c], errors='coerce')
        bool_cols = ["荷姿チェック","不良廃棄フラグ","リパックフラグ","日付未定フラグ","特注フラグ","チャーターフラグ"]
        for c in bool_cols:
            if c in df.columns: df[c] = df[c].astype(str).str.upper() == "TRUE"
        return df[target_cols]
    except: return pd.DataFrame(columns=target_cols)

def save_and_sync(name, df):
    try: ws = sheet.worksheet(name)
    except: ws = sheet.add_worksheet(title=name, rows="1000", cols="30")
    ws.clear()
    df_s = df.copy()
    for col in df_s.columns:
        if pd.api.types.is_datetime64_any_dtype(df_s[col]): df_s[col] = df_s[col].dt.strftime('%Y-%m-%d %H:%M:%S').fillna('').replace('NaT','')
        elif pd.api.types.is_bool_dtype(df_s[col]): df_s[col] = df_s[col].astype(str).str.upper()
        elif pd.api.types.is_numeric_dtype(df_s[col]): df_s[col] = df_s[col].fillna(0).apply(to_int).astype(str)
        else: df_s[col] = df_s[col].astype(str)
    df_s = df_s.fillna("").replace(["nan","None","NaT","NaN"],"")
    ws.update(values=[df_s.columns.tolist()] + df_s.values.tolist(), range_name='A1')
    st.cache_data.clear()
    st.session_state[f"{name}_df"] = load_data_from_cloud(name)

def append_and_sync(name, new_row_df):
    try: ws = sheet.worksheet(name)
    except:
        ws = sheet.add_worksheet(title=name, rows="1000", cols="30")
        ws.append_row(new_row_df.columns.tolist())
    row_copy = new_row_df.copy()
    existing_cols = pd.DataFrame(ws.get("A1:Z1")).values[0].tolist() if len(ws.get("A1:Z1")) > 0 else []
    for c in row_copy.columns:
        if c not in existing_cols: existing_cols.append(c)
    for c in existing_cols:
        if c not in row_copy.columns: row_copy[c] = ""
    row_copy = row_copy[existing_cols]
    for col in row_copy.columns:
        if pd.api.types.is_datetime64_any_dtype(row_copy[col]): row_copy[col] = row_copy[col].dt.strftime('%Y-%m-%d %H:%M:%S').fillna('').replace('NaT','')
        elif pd.api.types.is_bool_dtype(row_copy[col]): row_copy[col] = row_copy[col].astype(str).str.upper()
    row_to_send = row_copy.fillna("").astype(str).replace(["nan","None","NaT","NaN"],"").values[0].tolist()
    ws.append_row(row_to_send)
    st.cache_data.clear()
    st.session_state[f"{name}_df"] = pd.concat([st.session_state[f"{name}_df"], new_row_df], ignore_index=True)

_sheets = ["orders","manufactures","master","customers","packaging_master","packaging_logs","shipping_master","special_schedule"]
for _s in _sheets:
    if f"{_s}_df" not in st.session_state: st.session_state[f"{_s}_df"] = load_data_from_cloud(_s)
if "current_page" not in st.session_state: st.session_state.current_page = "📋 受注登録"
if "drill_product"  not in st.session_state: st.session_state.drill_product = None

orders_df   = st.session_state.orders_df
manus_df    = st.session_state.manufactures_df
master_df   = st.session_state.master_df
cust_df     = st.session_state.customers_df
pack_mst_df = st.session_state.packaging_master_df
pack_log_df = st.session_state.packaging_logs_df
ship_mst_df = st.session_state.shipping_master_df
special_df  = st.session_state.special_schedule_df

CATEGORIES = ["🍝 つきこん","🟫 平こん","🍜 糸こん・しらたき","🔺 三角こん","🟤 玉こん","🎲 ダイスこん","🏷️ 短冊","🇯🇵 国産","🤲 ちぎりこん","🏮 大黒屋","🏭 かねこ","🍱 ショクカイ","❄️ 冷凍耐性","📦 その他"]
SPECIAL_TYPES = ["（なし）","⭐ 特注","🚌 チャーター便"]

def format_name(n): return f"⚫️ {n}" if "黒" in str(n) else f"⚪️ {n}" if "白" in str(n) else f"📦 {n}"

def get_product_unit_info(prod_name):
    if master_df.empty or not prod_name: return 1, "ケース"
    row = master_df[master_df["製品名"] == prod_name]
    if row.empty: return 1, "ケース"
    nyusuu = to_int(row.iloc[0].get("入数", 1))
    if nyusuu <= 0: nyusuu = 1
    tani = str(row.iloc[0].get("単位区分", "ケース")).strip()
    if not tani or tani in ["nan","None",""]: tani = "ケース"
    return nyusuu, tani

def get_toriatsuki_list():
    if cust_df.empty: return []
    col = "帳合先" if "帳合先" in cust_df.columns else "顧客名"
    return sorted(cust_df[col].dropna().unique().tolist())

def get_shiten_list(toriatsuki):
    if cust_df.empty or not toriatsuki: return []
    if "帳合先" not in cust_df.columns or "支店名" not in cust_df.columns: return []
    rows = cust_df[cust_df["帳合先"] == toriatsuki]
    return sorted(rows["支店名"].dropna().replace("","").unique().tolist())

def get_product_special_flags(prod_name):
    if master_df.empty or not prod_name: return False, False
    row = master_df[master_df["製品名"] == prod_name]
    if row.empty: return False, False
    sp_f = str(row.iloc[0].get("特注フラグ","")).upper() in ["TRUE","1","YES","○","◯"]
    ch_f = str(row.iloc[0].get("チャーターフラグ","")).upper() in ["TRUE","1","YES","○","◯"]
    return sp_f, ch_f

today = pd.Timestamp.today().normalize()
dates = pd.date_range(today, today + timedelta(days=60))

current_stocks = {}
future_stocks  = {}
master_df_unique = master_df.drop_duplicates(subset=["製品名"]) if not master_df.empty else pd.DataFrame(columns=["大カテゴリ","製品名","初期在庫数","使用資材名","資材使用数","入数","単位区分","特注フラグ","チャーターフラグ","時間あたり生産量","歩留まり率","リードタイム時間","安全在庫数","段取りグループ"])

if not master_df_unique.empty:
    _EMPTY_EV = pd.DataFrame(columns=["日付","製品名","qty"])
    if not orders_df.empty:
        o_ev = orders_df[["納品予定日","製品名","ケース数"]].copy()
        o_ev = o_ev.rename(columns={"納品予定日":"日付","ケース数":"qty"})
        o_ev["qty"] = -pd.to_numeric(o_ev["qty"], errors='coerce').fillna(0).abs()
    else: o_ev = _EMPTY_EV.copy()
    
    if not manus_df.empty:
        _valid_m = manus_df[~manus_df["備考"].fillna("").str.contains("【在庫非反映】")]
        m_ev = _valid_m[["製造予定日","製品名","ケース数"]].copy()
        m_ev = m_ev.rename(columns={"製造予定日":"日付","ケース数":"qty"})
        m_ev["qty"] = pd.to_numeric(m_ev["qty"], errors='coerce').fillna(0).abs()
    else: m_ev = _EMPTY_EV.copy()

    all_ev = pd.concat([o_ev, m_ev], ignore_index=True)
    for _c in ["日付","製品名","qty"]:
        if _c not in all_ev.columns: all_ev[_c] = None
    all_ev = all_ev.dropna(subset=["製品名","日付"])
    all_ev["qty"] = all_ev["qty"].apply(to_int)
    past_ev   = all_ev[all_ev["日付"] < today].groupby("製品名")["qty"].sum()
    future_ev = all_ev[all_ev["日付"] >= today]
    pivot_ev  = future_ev.pivot_table(index="製品名", columns="日付", values="qty", aggfunc="sum") if not future_ev.empty else pd.DataFrame()
    for _, r in master_df_unique.iterrows():
        p = r["製品名"]
        curr_stock = to_int(r.get("初期在庫数",0)) + to_int(past_ev.get(p,0))
        current_stocks[p] = curr_stock
        p_row = pivot_ev.loc[p] if p in pivot_ev.index else pd.Series(0, index=dates)
        if isinstance(p_row, pd.DataFrame): p_row = p_row.sum(axis=0)
        p_cumsum = p_row.reindex(dates, fill_value=0).fillna(0).cumsum()
        future_stocks[p] = {d: curr_stock + to_int(p_cumsum.get(d,0)) for d in dates}

pack_summary = {}
pack_mst_unique = pack_mst_df.drop_duplicates(subset=["資材名"]) if not pack_mst_df.empty else pd.DataFrame(columns=["資材名","品番","規格","仕入先","保管場所","単位","初期在庫","発注点","発注リードタイム"])
if not pack_mst_unique.empty:
    for _, r in pack_mst_unique.iterrows():
        pack_summary[r["資材名"]] = {"品番": str(r.get("品番","")), "規格": str(r.get("規格","")), "仕入先": str(r.get("仕入先","")), "保管場所": str(r.get("保管場所","")), "単位": str(r.get("単位","")), "期首在庫": to_int(r.get("初期在庫",0)), "発注点": to_int(r.get("発注点",0)), "発注リードタイム": to_int(r.get("発注リードタイム",7)), "期間入庫累計": 0, "期間出庫消費": 0, "現在庫": 0}
if not pack_log_df.empty:
    for _, r in pack_log_df.iterrows():
        pn, qty, pt = r.get("資材名",""), to_int(r.get("数量",0)), str(r.get("処理区分",""))
        if pn in pack_summary:
            if "連動" in pt: continue
            if "入庫" in pt: pack_summary[pn]["期間入庫累計"] += qty
            elif "出庫" in pt: pack_summary[pn]["期間出庫消費"] += qty
if not manus_df.empty and not master_df_unique.empty:
    _mpi = master_df_unique.set_index("製品名")[["使用資材名","資材使用数"]].to_dict('index')
    for _, r in manus_df.iterrows():
        prod, qty, rem = str(r.get("製品名","")), to_int(r.get("ケース数",0)), str(r.get("備考",""))
        if prod in _mpi and "【資材非連動】" not in rem:
            pn = _mpi[prod].get("使用資材名",""); pu = to_int(_mpi[prod].get("資材使用数",0))
            if pn and pu > 0 and pn in pack_summary:
                pack_summary[pn]["期間出庫消費"] += (qty * pu)
for d in pack_summary.values():
    d["現在庫"] = d["期首在庫"] + d["期間入庫累計"] - d["期間出庫消費"]
    d["状態"] = "⚠️ 注意" if d["現在庫"] < d["発注点"] else "✅ 正常"

with st.sidebar:
    st.markdown("<div style='padding:16px 8px 8px;'><span style='font-size:22px;'>🏭</span><span style='font-size:16px; font-weight:900; color:#F1F5F9; margin-left:8px;'>丸実屋システム</span></div>", unsafe_allow_html=True)
    try:
        if not orders_df.empty and "納品予定日" in orders_df.columns: today_orders_cnt = int((pd.to_datetime(orders_df["納品予定日"], errors='coerce').dt.date == date.today()).sum())
        else: today_orders_cnt = 0
    except: today_orders_cnt = 0
    shortage_count = sum(1 for fs in future_stocks.values() if any(v < 0 for v in list(fs.values())[:7]))
    st.markdown(f"""
    <div style="margin:8px 0 12px; background:rgba(255,255,255,0.07); border-radius:8px; padding:10px 14px;">
        <div style="font-size:12px; color:#94A3B8; margin-bottom:4px;">本日状況</div>
        <div style="display:flex; gap:12px;">
            <div><span style="font-size:20px; font-weight:900; color:#60A5FA;">{today_orders_cnt}</span><span style="font-size:11px; color:#94A3B8;"> 出荷</span></div>
            <div><span style="font-size:20px; font-weight:900; color:#F87171;">{shortage_count}</span><span style="font-size:11px; color:#94A3B8;"> 欠品予測</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<div style='height:1px; background:rgba(255,255,255,0.1); margin:0 0 10px;'></div>", unsafe_allow_html=True)
    menu_items = [
        ("📋 受注登録", "受注"), ("🏭 製造登録", "製造"), ("🚚 出荷・発送管理", "出荷"), ("📦 資材・入出庫", "資材"),
        ("📑 登録一覧", "一覧"), ("📊 在庫・スケジュール", "在庫"), ("🏗️ 製造スケジューラー", "スケジューラー"),
        ("⭐ 特注・チャータースケジュール", "特注"), ("📈 経営・分析ダッシュボード", "分析"), ("⚙️ マスタ・分析", "マスタ")
    ]
    for item, _ in menu_items:
        if st.button(item, key=f"menu_{item}", use_container_width=True, type="primary" if st.session_state.current_page == item else "secondary"):
            st.session_state.current_page = item
            st.session_state.drill_product = None
            st.rerun()

page = st.session_state.current_page
HEADER_COLORS = {
    "📋 受注登録": "linear-gradient(135deg,#1E3A8A 0%,#3B82F6 100%)",
    "🏭 製造登録": "linear-gradient(135deg,#064E3B 0%,#10B981 100%)",
    "🚚 出荷・発送管理": "linear-gradient(135deg,#047857 0%,#34D399 100%)",
    "📦 資材・入出庫": "linear-gradient(135deg,#B45309 0%,#F59E0B 100%)",
    "📑 登録一覧": "linear-gradient(135deg,#0F766E 0%,#14B8A6 100%)",
    "📊 在庫・スケジュール": "linear-gradient(135deg,#1E3A8A 0%,#6366F1 100%)",
    "🏗️ 製造スケジューラー": "linear-gradient(135deg,#1C1917 0%,#78350F 100%)",
    "⭐ 特注・チャータースケジュール": "linear-gradient(135deg,#5B21B6 0%,#8B5CF6 100%)",
    "📈 経営・分析ダッシュボード": "linear-gradient(135deg,#0C4A6E 0%,#0EA5E9 100%)",
    "⚙️ マスタ・分析": "linear-gradient(135deg,#475569 0%,#1E293B 100%)",
}
def page_header(title): st.markdown(f'<div class="page-header" style="background:{HEADER_COLORS.get(title,"linear-gradient(135deg,#1E3A8A 0%,#3B82F6 100%)")};"><h1>{title}</h1></div>', unsafe_allow_html=True)
def section(txt): st.markdown(f'<div class="section-title">{txt}</div>', unsafe_allow_html=True)
---
# ─────────────────────────────────────────────
# 6. 受注登録
# ─────────────────────────────────────────────
if page == "📋 受注登録":
    page_header("📋 受注 登録")
    with st.container():
        is_date_undef = st.checkbox("📅 納品日を後で決める（日付未定で登録）", value=False)
        if is_date_undef:
            st.markdown('<div class="info-card yellow" style="background:#FFFBEB;padding:10px 16px;">🟡 <b>日付未定</b> として登録されます。後から納品日・帳合先を確定できます。</div>', unsafe_allow_html=True)
            o_date = None
        else: o_date = st.date_input("📅 納品日", value=date.today() + timedelta(days=1))

        ship_list = ship_mst_df["運送会社名"].tolist() if not ship_mst_df.empty else []
        tori_list = get_toriatsuki_list()
        ta1, ta2, ta3 = st.columns([2, 2, 1])
        sel_toriatsuki = ta1.selectbox("🏢 帳合先", options=tori_list, index=None, placeholder="帳合先を選択…（後からでも可）", key="sel_tori")
        shiten_candidates = get_shiten_list(sel_toriatsuki) if sel_toriatsuki else []
        if shiten_candidates:
            shiten_input = ta2.selectbox("🏬 支店・店舗名", options=["（なし）"] + shiten_candidates, index=0, key="sel_shiten")
            shiten_val = "" if shiten_input == "（なし）" else shiten_input
        else: shiten_val = ta2.text_input("🏬 支店・店舗名（直接入力可）", key="txt_shiten", placeholder="例：仙台支店")
        ship_comp = ta3.selectbox("🚚 運送会社", options=ship_list, index=None, placeholder="未定")

        def build_cust_name(tori, shiten): return f"{tori} {shiten}".strip() if shiten else (tori if tori else "未指定")

        cat_full = st.pills("カテゴリ", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
        cat = cat_full.split(" ",1)[1] if cat_full else CATEGORIES[0].split(" ",1)[1]
        sc1, sc2, sc3 = st.columns([1.5, 2.5, 1.5])
        search_p = sc1.text_input("🔍 製品検索", placeholder="名称の一部を入力...", key="search_prod")
        prods = ([p for p in master_df_unique["製品名"].tolist() if search_p in p] if search_p else master_df_unique[master_df_unique["大カテゴリ"] == cat]["製品名"].tolist() if not master_df_unique.empty else [])
        prod = sc2.selectbox("確定製品", options=prods, index=None, placeholder="選択してください", format_func=format_name)

        prod_sp_flag, prod_ch_flag = get_product_special_flags(prod)
        auto_sp = "⭐ 特注" if prod_sp_flag else ("🚌 チャーター便" if prod_ch_flag else "（なし）")
        sp_idx = SPECIAL_TYPES.index(auto_sp) if auto_sp in SPECIAL_TYPES else 0
        special_type = sc3.selectbox("⭐ 種別", options=SPECIAL_TYPES, index=sp_idx, key="sel_special")

        nyusuu, tani = get_product_unit_info(prod)
        if tani not in ["ケース","","nan","None"] and nyusuu > 1:
            q1, q2 = st.columns([1, 2])
            input_mode = q1.radio(f"入力単位（1cs＝{nyusuu}{tani}）", ["個数で入力", "ケース数で入力"], horizontal=True, key="qty_mode")
            if input_mode == "個数で入力":
                raw_qty = q2.number_input(f"📦 個数（{tani}）", min_value=1, step=1, format="%d", value=None, key="raw_qty")
                if raw_qty is not None and int(raw_qty) > 0:
                    cs_val = int(raw_qty) // nyusuu
                    rem_ind = int(raw_qty) % nyusuu
                    qty = cs_val if cs_val > 0 else None
                    hint = f"➡ <b>{cs_val} ケース</b>" + (f" <span style='color:#F59E0B;'>（端数 {rem_ind} {tani}は切り捨て）</span>" if rem_ind > 0 else "")
                    q2.markdown(f"<div style='font-size:13px;color:#475569;margin-top:2px;'>{hint}</div>", unsafe_allow_html=True)
                else: qty = None
            else:
                qty = q2.number_input("📦 ケース数", min_value=1, step=1, format="%d", value=None, key="cs_qty")
                if qty: q2.markdown(f"<div style='font-size:13px;color:#475569;margin-top:2px;'>≒ <b>{to_int(qty)*nyusuu} {tani}</b></div>", unsafe_allow_html=True)
        else: qty = st.number_input("📦 ケース数", min_value=1, step=1, format="%d", value=None, key="cs_qty_plain")

        r1, r2 = st.columns([2, 2])
        rem = r1.text_input("📝 備考")
        col_chk1, col_chk2 = r2.columns(2)
        is_substitute = col_chk1.checkbox("🔄 代替品として送付")
        is_irregular  = col_chk2.checkbox("⚠️ 不良廃棄")
        st.write("---")

        if prod and qty is not None and to_int(qty) > 0:
            cur_stock = current_stocks.get(prod, 0)
            if cur_stock < to_int(qty):
                st.markdown(f'<div class="info-card red" style="background:#FEF2F2;">🚨 <b>製品在庫が不足します！</b>　現在庫: <b>{cur_stock} cs</b> &nbsp;／&nbsp; 不足分: <span class="shortage-red">－{to_int(qty) - cur_stock} cs</span></div>', unsafe_allow_html=True)

        msg_slot_add = st.empty()
        if st.session_state.get("msg_order_add"): msg_slot_add.success(st.session_state.msg_order_add); st.session_state.msg_order_add = None

        if st.button("✅ 受注を登録する", type="primary", use_container_width=True):
            if not prod or qty is None or to_int(qty) < 1: msg_slot_add.error("⚠️ 【製品・ケース数（1以上）】は必須です。")
            else:
                prefix = ("【代替品】" if is_substitute else "") + ("【不良廃棄】" if is_irregular else "")
                sp_label = "特注" if "特注" in special_type else ("チャーター便" if "チャーター便" in special_type else "")
                full_rem = f"{prefix} {sp_label} {rem}".strip()
                cust_name = build_cust_name(sel_toriatsuki, shiten_val)
                new_id = str(uuid.uuid4())[:6].upper()
                delivery_date = pd.to_datetime(o_date) if o_date else pd.NaT
                new_row = pd.DataFrame([{"ID": new_id, "納品予定日": delivery_date, "顧客名": cust_name, "大カテゴリ": cat, "製品名": prod, "ケース数": to_int(qty), "運送会社": ship_comp if ship_comp else "", "備考": full_rem, "荷姿チェック": False, "賞味期限1":"","賞味期限2":"","賞味期限3":"","賞味期限4":"","賞味期限5":"", "発送備考":"", "不良廃棄フラグ": is_irregular, "日付未定フラグ": is_date_undef, "登録日時": datetime.now()}])
                append_and_sync("orders", new_row)
                if sp_label and o_date:
                    append_and_sync("special_schedule", pd.DataFrame([{"ID": str(uuid.uuid4())[:6].upper(), "受注ID": new_id, "製品名": prod, "顧客名": cust_name, "納品予定日": delivery_date, "出荷予定日": delivery_date - timedelta(days=1), "備考": full_rem, "更新日時": datetime.now()}]))
                st.session_state.msg_order_add = f"✨ 登録完了: {prod} ({to_int(qty)}cs) {format_date_jp(o_date) if o_date else '日付未定'}"
                st.rerun()

    if not orders_df.empty and "日付未定フラグ" in orders_df.columns:
        undef_orders = orders_df[orders_df["日付未定フラグ"] == True].copy().reset_index(drop=True)
        if not undef_orders.empty:
            st.markdown(f'<div style="background:linear-gradient(135deg,#FFFBEB,#FEF3C7);border:2px solid #F59E0B;border-radius:12px;padding:14px 18px;margin:16px 0;">🟡 <b style="font-size:16px;color:#92400E;">日付未定の受注が {len(undef_orders)} 件あります</b>　— 納品日を確定してください</div>', unsafe_allow_html=True)
            with st.expander("🟡 日付未定受注を確定する", expanded=True):
                undef_disp = undef_orders[["ID","製品名","ケース数","備考","顧客名","運送会社"]].copy()
                undef_disp.insert(4, "納品予定日(確定)", None); undef_disp.insert(5, "帳合先(確定)", ""); undef_disp.insert(6, "支店名(確定)", "")
                edited_undef = st.data_editor(undef_disp, use_container_width=True, hide_index=True, column_config={"ID": None, "製品名": st.column_config.TextColumn("製品名", disabled=True), "ケース数": st.column_config.NumberColumn("ケース数", disabled=True), "備考": st.column_config.TextColumn("備考", disabled=True), "顧客名": st.column_config.TextColumn("現在の顧客名", disabled=True), "納品予定日(確定)": st.column_config.DateColumn("📅 納品日【必須】", format="YYYY/MM/DD"), "帳合先(確定)": st.column_config.SelectboxColumn("🏢 帳合先（任意）", options=get_toriatsuki_list()), "支店名(確定)": st.column_config.TextColumn("🏬 支店名（任意）"), "運送会社": st.column_config.SelectboxColumn("🚚 運送会社", options=ship_mst_df["運送会社名"].tolist() if not ship_mst_df.empty else [])}, key="edit_undef")
                msg_undef = st.empty()
                if st.session_state.get("msg_undef_save"): msg_undef.success(st.session_state.msg_undef_save); st.session_state.msg_undef_save = None
                if st.button("✅ 日付を確定して消込する", type="primary", use_container_width=True):
                    updated_orders = orders_df.copy(); confirmed_count = 0
                    for i in range(len(edited_undef)):
                        oid = undef_orders.iloc[i]["ID"] if i < len(undef_orders) else None
                        if not oid: continue
                        row = edited_undef.iloc[i]
                        if pd.isnull(row.get("納品予定日(確定)")) or not row.get("納品予定日(確定)"): continue
                        mask = updated_orders["ID"] == oid
                        updated_orders.loc[mask, "納品予定日"] = pd.to_datetime(row.get("納品予定日(確定)"))
                        updated_orders.loc[mask, "日付未定フラグ"] = False
                        if row.get("帳合先(確定)"): updated_orders.loc[mask, "顧客名"] = f"{row.get('帳合先(確定)')} {row.get('支店名(確定)','')}".strip()
                        if row.get("運送会社"): updated_orders.loc[mask, "運送会社"] = str(row.get("運送会社")).strip()
                        confirmed_count += 1
                    if confirmed_count > 0: save_and_sync("orders", updated_orders); st.session_state.msg_undef_save = f"✅ {confirmed_count} 件の受注を確定しました！"; st.rerun()

    section("✏️ 直近データの修正・削除")
    if not orders_df.empty:
        disp_orders = orders_df.sort_values("登録日時", ascending=False).copy()
        disp_orders["納品予定日(表示)"] = disp_orders.apply(lambda r: ("🟡 日付未定" if r.get("日付未定フラグ") is True else format_date_jp(r["納品予定日"])), axis=1) if "日付未定フラグ" in disp_orders.columns else disp_orders["納品予定日"].apply(format_date_jp)
        disp_cols = ["ID","納品予定日(表示)","顧客名","製品名","ケース数","運送会社","備考","不良廃棄フラグ"]
        recent = disp_orders.head(5).copy()
        edited = st.data_editor(recent[disp_cols], num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"ケース数": st.column_config.NumberColumn("ケース数", min_value=1, step=1, format="%d"), "ID": None}, key="edit_o")
        msg_slot_edit = st.empty()
        if st.session_state.get("msg_order_edit"): msg_slot_edit.success(st.session_state.msg_order_edit); st.session_state.msg_order_edit = None
        if st.button("💾 直近データを修正・削除保存", key="btn_edit_o"):
            save_df = edited.copy()
            save_df["納品予定日"] = pd.to_datetime(save_df["納品予定日(表示)"].str.replace("🟡 日付未定","").str.replace("🟡 ","").str.split(" ").str[0], errors="coerce")
            keep_cols = [c for c in ["ID","大カテゴリ","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考","日付未定フラグ","登録日時"] if c in orders_df.columns]
            save_and_sync("orders", pd.concat([orders_df[~orders_df["ID"].isin(recent["ID"])], pd.merge(save_df, orders_df[keep_cols], on="ID", how="left")], ignore_index=True))
            st.session_state.msg_order_edit = "✅ 受注データを修正しました"; st.rerun()
        with st.expander("📂 全データ一括編集・削除"):
            edited_all = st.data_editor(disp_orders[disp_cols], num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"ケース数": st.column_config.NumberColumn("ケース数", min_value=1, step=1, format="%d"), "ID": None}, key="edit_all_o", height=400)
            if st.button("💾 全データを上書き保存", key="btn_edit_all_o"):
                save_df_all = edited_all.copy()
                save_df_all["納品予定日"] = pd.to_datetime(save_df_all["納品予定日(表示)"].str.replace("🟡 日付未定","").str.replace("🟡 ","").str.split(" ").str[0], errors="coerce")
                save_and_sync("orders", pd.merge(save_df_all, orders_df[keep_cols], on="ID", how="left")); st.rerun()

elif page == "🚚 出荷・発送管理":
    page_header("🚚 出荷・発送 消込管理")
    tab_ship1, tab_ship2, tab_ship3 = st.tabs(["📋 日次消込", "📅 週間出荷一覧", "📥 出荷CSV出力"])
    with tab_ship1:
        target_date = st.date_input("📅 対象日を選択", value=date.today())
        day_orders = orders_df[(safe_dt_date(orders_df["納品予定日"]) == target_date) & (orders_df["不良廃棄フラグ"] == False)].copy() if not orders_df.empty else pd.DataFrame()
        if day_orders.empty: st.info(f"📭 {format_date_jp(target_date)} の出荷予定はありません。")
        else:
            done = day_orders[day_orders["荷姿チェック"] == True]; undone = day_orders[day_orders["荷姿チェック"] == False]
            c1,c2,c3 = st.columns(3)
            c1.metric("出荷件数", f"{len(day_orders)} 件"); c2.metric("✅ 消込済", f"{len(done)} 件"); c3.metric("⏳ 未消込", f"{len(undone)} 件", delta_color="inverse")
            if not undone.empty and target_date <= date.today(): st.error(f"🚨 出荷漏れ（荷姿未チェック）が **{len(undone)} 件** あります！")
            disp_df = day_orders[["ID","顧客名","製品名","ケース数","運送会社","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考"]].copy()
            for c in ["賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5"]: disp_df[c] = pd.to_datetime(disp_df[c], errors="coerce").dt.date
            edited_ship = st.data_editor(disp_df.style.apply(lambda r: ['background-color:#D1FAE5; color:#065F46; text-decoration:line-through;']*len(r) if str(r.get("荷姿チェック",False)).upper()=="TRUE" else ['']*len(r), axis=1), use_container_width=True, hide_index=True, column_config={"ID": None, "顧客名": st.column_config.TextColumn("顧客名", disabled=True), "製品名": st.column_config.TextColumn("製品名", disabled=True), "ケース数": st.column_config.NumberColumn("ケース数", disabled=True), "運送会社": st.column_config.SelectboxColumn("🚚 運送会社", options=ship_mst_df["運送会社名"].tolist() if not ship_mst_df.empty else []), "荷姿チェック": st.column_config.CheckboxColumn("✅ 荷姿", default=False), "賞味期限1": st.column_config.DateColumn("賞味1", format="YYYY-MM-DD"), "賞味期限2": st.column_config.DateColumn("賞味2", format="YYYY-MM-DD"), "賞味期限3": st.column_config.DateColumn("賞味3", format="YYYY-MM-DD"), "賞味期限4": st.column_config.DateColumn("賞味4", format="YYYY-MM-DD"), "賞味期限5": st.column_config.DateColumn("賞味5", format="YYYY-MM-DD")}, key="edit_shipping")
            if st.button("💾 発送・消込データを保存", type="primary", use_container_width=True):
                upd = orders_df.copy().astype(object)
                for idx, row in edited_ship.iterrows():
                    mask = upd["ID"] == row["ID"]
                    if mask.any():
                        upd.loc[mask,"運送会社"] = str(row.get("運送会社","")); upd.loc[mask,"荷姿チェック"] = str(row.get("荷姿チェック",False)).upper()
                        for c in ["賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5"]:
                            val = row.get(c)
                            upd.loc[mask,c] = val.strftime("%Y-%m-%d") if pd.notnull(val) and val else ""
                        upd.loc[mask,"発送備考"] = str(row.get("発送備考",""))
                save_and_sync("orders", upd); st.session_state.msg_ship_edit = "✅ 発送・消込データを保存しました！"; st.rerun()

    with tab_ship2:
        col_wk1, col_wk2 = st.columns([2, 2])
        start_wk = col_wk1.date_input("開始日", value=date.today()); wk_days  = col_wk2.number_input("表示日数", min_value=1, max_value=30, value=7, step=1)
        view_mode = st.radio("表示モード", ["📋 日別折りたたみ", "📊 全件一覧（フルスクリーン対応）"], horizontal=True)
        if view_mode == "📋 日別折りたたみ":
            for i in range(int(wk_days)):
                d = pd.Timestamp(start_wk) + timedelta(days=i)
                wk_ord = orders_df[safe_dt_date(orders_df["納品予定日"]) == d.date()].copy() if not orders_df.empty else pd.DataFrame()
                if wk_ord.empty: continue
                with st.expander(f"**{format_date_jp(d)}**　{len(wk_ord)}件 ✅{len(wk_ord[wk_ord['荷姿チェック']==True])}件完了", expanded=(d.date()==date.today())):
                    st.dataframe(wk_ord[["顧客名","製品名","ケース数","運送会社","荷姿チェック","発送備考"]].style.apply(lambda r: ['background-color:#D1FAE5;']*len(r) if r.get("荷姿チェック")==True else ['']*len(r), axis=1), use_container_width=True, hide_index=True)
        else:
            all_wk_rows = []
            for i in range(int(wk_days)):
                d = pd.Timestamp(start_wk) + timedelta(days=i)
                wk_ord = orders_df[safe_dt_date(orders_df["納品予定日"]) == d.date()].copy() if not orders_df.empty else pd.DataFrame()
                if not wk_ord.empty: wk_ord["納品日"] = format_date_jp(d); all_wk_rows.append(wk_ord)
            if not all_wk_rows: st.info("該当期間の出荷予定はありません。")
            else:
                all_wk_df = pd.concat(all_wk_rows, ignore_index=True)
                c_w1, c_w2, c_w3 = st.columns(3)
                c_w1.metric("期間 出荷件数", f"{len(all_wk_df)} 件"); c_w2.metric("✅ 消込済", f"{len(all_wk_df[all_wk_df['荷姿チェック']==True])} 件"); c_w3.metric("総出荷数", f"{all_wk_df['ケース数'].apply(to_int).sum():,} cs")
                show_cols_wk = [c for c in ["納品日","顧客名","製品名","ケース数","運送会社","荷姿チェック","発送備考","備考"] if c in all_wk_df.columns]
                st.dataframe(all_wk_df[show_cols_wk].style.apply(lambda r: ['background-color:#D1FAE5; color:#065F46;']*len(r) if r.get("荷姿チェック")==True else ['']*len(r), axis=1), use_container_width=True, hide_index=True, height=min(600, max(300, len(all_wk_df)*38+60)))
                st.download_button("📥 週間出荷一覧をCSV出力", data=make_csv_bytes(all_wk_df[show_cols_wk]), file_name=f"週間出荷一覧_{start_wk}.csv", mime="text/csv", use_container_width=True)

    with tab_ship3:
        col_e1, col_e2 = st.columns(2)
        exp_start = col_e1.date_input("出力開始日", value=date.today().replace(day=1)); exp_end = col_e2.date_input("出力終了日", value=date.today())
        if not orders_df.empty:
            exp_df = orders_df[(safe_dt_date(orders_df["納品予定日"]) >= exp_start) & (safe_dt_date(orders_df["納品予定日"]) <= exp_end)].copy()
            exp_df["納品予定日"] = pd.to_datetime(exp_df["納品予定日"],errors='coerce').apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "")
            for c in ["賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5"]:
                if c in exp_df.columns: exp_df[c] = pd.to_datetime(exp_df[c],errors='coerce').apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "")
            exp_df["荷姿チェック"] = exp_df["荷姿チェック"].map({True:"済",False:"未"}).fillna("")
            out_c = [c for c in ["納品予定日","顧客名","製品名","ケース数","運送会社","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考","備考"] if c in exp_df.columns]
            st.metric("対象件数", f"{len(exp_df)} 件")
            st.download_button("📥 出荷データCSV出力", data=make_csv_bytes(exp_df[out_c]), file_name=f"出荷データ_{exp_start}_{exp_end}.csv", mime="text/csv", type="primary", use_container_width=True)
        else: st.info("出荷データがありません。")

elif page == "🏭 製造登録":
    page_header("🏭 製造・リパック 登録")
    with st.container():
        col1, col2 = st.columns([1,1])
        m_date = col1.date_input("📅 製造日", value=date.today())
        m_qty  = col2.number_input("📦 製造ケース数", min_value=1, step=1, format="%d", value=None)
        cat_full_m = st.pills("カテゴリ製造", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
        cat_m = cat_full_m.split(" ",1)[1] if cat_full_m else CATEGORIES[0].split(" ",1)[1]
        sc1_m, sc2_m = st.columns([1.5, 2.5])
        search_p_m = sc1_m.text_input("🔍 製品名検索", placeholder="検索...")
        prods_m = ([p for p in master_df_unique["製品名"].tolist() if search_p_m in p] if search_p_m else master_df_unique[master_df_unique["大カテゴリ"]==cat_m]["製品名"].tolist() if not master_df_unique.empty else [])
        prod_m = sc2_m.selectbox("確定製品", options=prods_m, index=None, format_func=format_name)
        m_rem  = sc2_m.text_input("📝 備考（製造）")

        is_repack = st.checkbox("🔄 リパック製造（在庫加算）")
        is_pack_link = st.checkbox("📦 紐づく資材の在庫も同時に減らす", value=True) if is_repack else True

        if prod_m and m_qty:
            cur_stock = current_stocks.get(prod_m, 0)
            if cur_stock <= 0: st.markdown(f"<div class='info-card red' style='background:#FEF2F2; padding:10px;'>現在庫: <span class='shortage-red'>{cur_stock} cs</span>　→　製造後予定: <b>{cur_stock + to_int(m_qty)} cs</b></div>", unsafe_allow_html=True)
        st.write("---")
        msg_slot_m_add = st.empty()
        if st.session_state.get("msg_manu_add"): msg_slot_m_add.success(st.session_state.msg_manu_add); st.session_state.msg_manu_add = None

        if st.button("➕ 製造データを記録する", type="primary", use_container_width=True):
            if not prod_m or m_qty is None: msg_slot_m_add.error("⚠️ 【製品・数量】は必須です。")
            else:
                rem_text = f"{'【リパック】' if is_repack else ''} {'【資材非連動】' if is_repack and not is_pack_link else ''} {m_rem}".strip()
                new_m_id = str(uuid.uuid4())[:6].upper()
                append_and_sync("manufactures", pd.DataFrame([{"ID":new_m_id,"製造予定日":pd.to_datetime(m_date),"大カテゴリ":cat_m,"製品名":prod_m,"ケース数":to_int(m_qty),"リパックフラグ":is_repack,"備考":rem_text,"登録日時":datetime.now()}]))
                if is_pack_link and not master_df_unique.empty:
                    _mpi2 = master_df_unique.set_index("製品名")[["使用資材名","資材使用数"]].to_dict('index')
                    if prod_m in _mpi2:
                        pn2 = _mpi2[prod_m].get("使用資材名",""); pu2 = to_int(_mpi2[prod_m].get("資材使用数",0))
                        if pn2 and pu2 > 0:
                            append_and_sync("packaging_logs", pd.DataFrame([{"ID":str(uuid.uuid4())[:6].upper(),"登録日":pd.to_datetime(m_date),"資材名":pn2,"処理区分":"製造連動","数量":abs(to_int(m_qty)*pu2),"理由":f"製造ID:{new_m_id}","関連製品名":prod_m,"理論在庫":pack_summary.get(pn2,{}).get("現在庫",0) - (to_int(m_qty)*pu2),"備考":"自動記録","登録日時":datetime.now()}]))
                st.session_state.msg_manu_add = f"✨ 製造登録完了: {prod_m}"; st.rerun()

    section("✏️ 直近データの修正・削除")
    if not manus_df.empty:
        disp_manus = manus_df.sort_values("登録日時", ascending=False).copy()
        disp_manus["製造予定日(表示)"] = disp_manus["製造予定日"].apply(format_date_jp)
        disp_cols_m = ["ID","製造予定日(表示)","製品名","ケース数","リパックフラグ","備考"]
        recent_m = disp_manus.head(5).copy()
        edited_m = st.data_editor(recent_m[disp_cols_m], num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"ケース数": st.column_config.NumberColumn("CS数",min_value=1,step=1,format="%d"),"ID":None})
        if st.button("💾 直近データを修正・削除保存"):
            save_df_m = edited_m.copy(); save_df_m["製造予定日"] = pd.to_datetime(save_df_m["製造予定日(表示)"].str.split(" ").str[0], errors="coerce")
            save_and_sync("manufactures", pd.concat([manus_df[~manus_df["ID"].isin(recent_m["ID"])], pd.merge(save_df_m, manus_df[["ID","大カテゴリ","登録日時"]], on="ID", how="left")], ignore_index=True))
            st.rerun()
        with st.expander("📂 全データ一括編集・削除"):
            edited_all_m = st.data_editor(disp_manus[disp_cols_m], num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"ケース数": st.column_config.NumberColumn("CS数",min_value=1,step=1,format="%d"),"ID":None}, height=400)
            if st.button("💾 全データを上書き保存"):
                save_df_all_m = edited_all_m.copy(); save_df_all_m["製造予定日"] = pd.to_datetime(save_df_all_m["製造予定日(表示)"].str.split(" ").str[0], errors="coerce")
                save_and_sync("manufactures", pd.merge(save_df_all_m, manus_df[["ID","大カテゴリ","登録日時"]], on="ID", how="left")); st.rerun()

elif page == "📦 資材・入出庫":
    page_header("📦 資材・段ボール入出庫")
    shortage_packs = [pn for pn,d in pack_summary.items() if d["現在庫"] < d["発注点"]]
    if shortage_packs: st.error("🚨 **要発注アラート（現在庫が発注点未満）:**　" + "、".join(shortage_packs))
    t_p1, t_p2, t_p3, t_p4 = st.tabs(["📦 発注日予測（リードタイム連動）","📊 状況サマリ＆分析","📝 単体入出庫・棚卸","✏️ 履歴・かんたん修正"])

    with t_p1:
        section("📦 資材 発注日予測（出荷予測 × リードタイム）")
        if pack_mst_unique.empty: st.warning("⚙️ マスタ管理から資材を登録してください。")
        else:
            no_lt = [r["資材名"] for _, r in pack_mst_unique.iterrows() if to_int(r.get("発注リードタイム", 0)) == 0]
            if no_lt: st.warning(f"⚠️ **リードタイム未設定の資材があります：** {' / '.join(no_lt)}\n\n👉 **マスタ・分析 → 📦 資材マスタ** で設定してください。")
            with st.expander("📋 現在のリードタイム設定一覧（参照）", expanded=False):
                lt_disp = pack_mst_unique[["資材名","発注点","発注リードタイム"]].copy() if "発注リードタイム" in pack_mst_unique.columns else pack_mst_unique[["資材名","発注点"]].copy()
                if "発注リードタイム" not in lt_disp.columns: lt_disp["発注リードタイム"] = 7
                lt_disp.columns = ["資材名","発注点（cs）","発注リードタイム（日）"]
                st.dataframe(lt_disp, use_container_width=True, hide_index=True)

            st.write("")
            if master_df_unique.empty or orders_df.empty: st.info("製品マスタまたは受注データがありません。")
            else:
                _mpi_lt = master_df_unique.set_index("製品名")[["使用資材名","資材使用数"]].to_dict("index")
                forecast_days = 90
                pack_forecast = {}
                for _, o_row in orders_df.iterrows():
                    prod = str(o_row.get("製品名","")); qty = to_int(o_row.get("ケース数", 0))
                    dt = pd.to_datetime(o_row.get("納品予定日"), errors="coerce")
                    if pd.isna(dt) or dt.date() < date.today() or dt > today + timedelta(days=forecast_days): continue
                    if prod not in _mpi_lt: continue
                    pn_lt = str(_mpi_lt[prod].get("使用資材名","")); pu_lt = to_int(_mpi_lt[prod].get("資材使用数", 0))
                    if not pn_lt or pu_lt <= 0: continue
                    pack_forecast.setdefault(pn_lt, {})
                    pack_forecast[pn_lt][dt.normalize()] = pack_forecast[pn_lt].get(dt.normalize(), 0) + qty * pu_lt

                for _, pm_row in pack_mst_unique.iterrows():
                    if pm_row["資材名"] not in pack_forecast: pack_forecast[pm_row["資材名"]] = {}

                order_alerts = []
                for pn_lt, daily_use in pack_forecast.items():
                    lt_days = pack_summary.get(pn_lt, {}).get("発注リードタイム", 7)
                    if lt_days == 0: lt_days = 7
                    curr_inv = pack_summary.get(pn_lt, {}).get("現在庫", 0)
                    ord_pt = pack_summary.get(pn_lt, {}).get("発注点", 0)

                    running_inv = curr_inv; reorder_date = None; zero_date = None; inv_at_order = None; cumulative_use = 0
                    for d_lt in pd.date_range(today, today + timedelta(days=forecast_days)):
                        use = daily_use.get(d_lt, 0)
                        running_inv -= use; cumulative_use += use
                        if running_inv <= ord_pt and reorder_date is None: reorder_date = d_lt; inv_at_order = running_inv
                        if running_inv <= 0 and zero_date is None: zero_date = d_lt

                    if reorder_date is not None:
                        order_date = reorder_date - timedelta(days=lt_days)
                        days_until_order = (order_date.date() - date.today()).days
                        if days_until_order <= 0: urgency, urgency_color, border_color = "🔴 今すぐ発注！", "#FEE2E2", "#DC2626"
                        elif days_until_order <= 3: urgency, urgency_color, border_color = f"🟠 {days_until_order}日以内に発注", "#FFF7ED", "#EA580C"
                        elif days_until_order <= 7: urgency, urgency_color, border_color = f"🟡 {days_until_order}日以内に発注", "#FFFBEB", "#D97706"
                        else: urgency, urgency_color, border_color = f"🔵 {days_until_order}日後に発注推奨", "#EFF6FF", "#2563EB"
                    else:
                        order_date = None; inv_at_order = None; days_until_order = 999
                        urgency, urgency_color, border_color = "✅ 当面問題なし（90日以内に発注点到達なし）", "#F0FDF4", "#059669"

                    order_alerts.append({"資材名": pn_lt, "現在庫": curr_inv, "発注点": ord_pt, "リードタイム(日)": lt_days, "90日消費予測": int(cumulative_use), "発注推奨日（リマインド日）": order_date.strftime("%Y/%m/%d (%a)") if order_date else "―", "発注点到達日": reorder_date.strftime("%Y/%m/%d") if reorder_date else "なし", "在庫切れ予測日": zero_date.strftime("%Y/%m/%d (%a)") if zero_date else "―", "到達時の予測在庫": f"{inv_at_order:,}" if inv_at_order is not None else "―", "緊急度": urgency, "_sort": days_until_order, "_color": urgency_color, "_border": border_color})

                df_alerts = pd.DataFrame(order_alerts).sort_values("_sort").reset_index(drop=True)
                urgent = df_alerts[df_alerts["_sort"] <= 7]
                if not urgent.empty:
                    st.markdown("### 🚨 直近7日以内に発注手配が必要な資材")
                    for _, al in urgent.iterrows():
                        st.markdown(f'<div style="background:{al["_color"]};border-left:6px solid {al["_border"]};border-radius:10px;padding:14px 18px;margin-bottom:10px;box-shadow:0 1px 4px rgba(0,0,0,0.08);"><div style="display:flex;justify-content:space-between;align-items:center;"><b style="font-size:16px;">📦 {al["資材名"]}</b><span style="font-size:16px;font-weight:900;">{al["緊急度"]}</span></div><div style="margin-top:6px;font-size:13px;color:#374151;">現在庫: <b>{al["現在庫"]:,}</b> &nbsp;|&nbsp; 発注点: <b>{al["発注点"]:,}</b> &nbsp;|&nbsp; リードタイム: <b>{al["リードタイム(日)"]}日</b><br>⏰ <b>発注点到達日: {al["発注点到達日"]}</b>（到達時の在庫: {al["到達時の予測在庫"]}）<br>📉 <b>在庫切れ予測（ゼロ到達）: {al["在庫切れ予測日"]}</b></div></div>', unsafe_allow_html=True)
                else: st.success("✅ 直近7日以内に発注手配が必要な資材はありません。")

                st.markdown("### 📋 全資材 発注スケジュール一覧")
                show_alert_cols = ["資材名","現在庫","発注点","リードタイム(日)","90日消費予測","発注推奨日（リマインド日）","発注点到達日","到達時の予測在庫","在庫切れ予測日","緊急度"]
                st.dataframe(df_alerts[show_alert_cols].style.apply(lambda r: ['background-color:#FEE2E2; font-weight:bold;']*len(r) if "今すぐ" in str(r.get("緊急度","")) else (['background-color:#FFF7ED;']*len(r) if "🟠" in str(r.get("緊急度","")) else (['background-color:#FFFBEB;']*len(r) if "🟡" in str(r.get("緊急度","")) else (['background-color:#EFF6FF;']*len(r) if "🔵" in str(r.get("緊急度","")) else ['background-color:#F0FDF4;']*len(r)))), axis=1), use_container_width=True, hide_index=True, height=min(len(df_alerts)*40+55, 520))
                st.download_button("📥 発注スケジュールCSV", data=make_csv_bytes(df_alerts[show_alert_cols]), file_name=f"発注スケジュール_{date.today()}.csv", mime="text/csv")

                st.write(""); section("📈 資材別 在庫推移予測グラフ（今後90日）")
                sel_pack_graph = st.selectbox("グラフ表示する資材を選択", options=[r["資材名"] for _, r in pack_mst_unique.iterrows()])
                if sel_pack_graph:
                    lt_g = pack_summary.get(sel_pack_graph, {}).get("発注リードタイム", 7) or 7
                    inv_g = pack_summary.get(sel_pack_graph, {}).get("現在庫", 0)
                    ord_pt_g = pack_summary.get(sel_pack_graph, {}).get("発注点", 0)
                    daily_g = pack_forecast.get(sel_pack_graph, {})
                    graph_dates, graph_stock, graph_use = [], [], []
                    running_g = inv_g
                    for d_g in pd.date_range(today, today + timedelta(days=forecast_days)):
                        use_g = daily_g.get(d_g, 0); running_g -= use_g; graph_dates.append(d_g.strftime("%m/%d")); graph_stock.append(running_g); graph_use.append(use_g)

                    fig_pack = go.Figure()
                    fig_pack.add_trace(go.Bar(x=graph_dates, y=graph_use, name="日別消費量（出荷連動）", marker_color="#F43F5E", opacity=0.55))
                    fig_pack.add_trace(go.Scatter(x=graph_dates, y=graph_stock, name="推定在庫推移", mode="lines+markers", line=dict(color="#2563EB", width=2.5), marker=dict(size=4)))
                    fig_pack.add_hline(y=ord_pt_g, line_dash="dash", line_color="#F59E0B", annotation_text=f"発注点 ({ord_pt_g:,})", annotation_position="top left")
                    fig_pack.add_hline(y=0, line_dash="dot", line_color="#DC2626", annotation_text="ゼロ", annotation_position="bottom right")

                    alert_row = df_alerts[df_alerts["資材名"] == sel_pack_graph]
                    if not alert_row.empty:
                        rem_day_str = alert_row.iloc[0]["発注推奨日（リマインド日）"]
                        if rem_day_str not in ("―", ""):
                            try:
                                od_mmdd = pd.to_datetime(rem_day_str.split(" ")[0]).strftime("%m/%d")
                                if od_mmdd in graph_dates: fig_pack.add_vline(x=od_mmdd, line_dash="dash", line_color="#2563EB", annotation_text="📅 発注手配 推奨日", annotation_position="top right")
                            except: pass
                        ord_day_str = alert_row.iloc[0]["発注点到達日"]
                        if ord_day_str not in ("―", "なし"):
                            try:
                                od_mmdd = pd.to_datetime(ord_day_str.split(" ")[0]).strftime("%m/%d")
                                if od_mmdd in graph_dates: fig_pack.add_vline(x=od_mmdd, line_dash="dash", line_color="#DC2626", annotation_text="🔻 発注点 到達日", annotation_position="bottom right")
                            except: pass
                        zero_day_str = alert_row.iloc[0]["在庫切れ予測日"]
                        if zero_day_str not in ("―", ""):
                            try:
                                zd_mmdd = pd.to_datetime(zero_day_str.split(" ")[0]).strftime("%m/%d")
                                if zd_mmdd in graph_dates: fig_pack.add_vline(x=zd_mmdd, line_dash="solid", line_color="#000000", annotation_text="📉 在庫切れ予測", annotation_position="top left")
                            except: pass

                    fig_pack.update_layout(title=f"【{sel_pack_graph}】 在庫推移予測（今後90日） / リードタイム: {lt_g}日", hovermode="x unified", barmode="relative", margin=dict(l=10,r=10,t=55,b=10), height=380, legend=dict(orientation="h", y=1.12))
                    st.plotly_chart(fig_pack, use_container_width=True)

    with t_p2:
        section("📊 資材の在庫推移サマリ")
        if pack_mst_unique.empty: st.info("⚙️ マスタ管理から資材を登録してください。")
        else:
            df_pack = pd.DataFrame([{"資材名":k,**v} for k,v in pack_summary.items()])
            st.dataframe(df_pack[["資材名","品番","規格","仕入先","保管場所","現在庫","発注点","状態","単位"]].style.apply(lambda r: ['background-color:#FFEDD5; color:#C2410C; font-weight:bold;']*len(r) if to_int(r.get("現在庫",0)) < to_int(r.get("発注点",0)) else ['']*len(r), axis=1), use_container_width=True, hide_index=True)
            st.download_button("📥 サマリCSV出力", data=make_csv_bytes(df_pack), file_name=f"資材状況_{date.today()}.csv", use_container_width=True)
        st.write("---"); section("📈 資材使用分析（期間指定）")
        cd1,cd2 = st.columns(2); start_d = cd1.date_input("開始日", value=date.today().replace(day=1)); end_d = cd2.date_input("終了日", value=date.today())
        if not manus_df.empty and not master_df_unique.empty:
            _mpi3 = master_df_unique.set_index("製品名")[["使用資材名","資材使用数"]].to_dict('index')
            period_m = manus_df[(safe_dt_date(manus_df["製造予定日"]) >= start_d) & (safe_dt_date(manus_df["製造予定日"]) <= end_d)].copy()
            adata = [{"資材名":_mpi3[prod].get("使用資材名",""),"製品名":prod,"使用総数":to_int(r.get("ケース数",0))*to_int(_mpi3[prod].get("資材使用数",0))} for _, r in period_m.iterrows() for prod in [str(r.get("製品名",""))] if prod in _mpi3 and "【資材非連動】" not in str(r.get("備考","")) and _mpi3[prod].get("使用資材名","") and to_int(_mpi3[prod].get("資材使用数",0)) > 0]
            if adata: st.write("▼ 製品別・資材別の製造時消費実績"); st.dataframe(pd.DataFrame(adata).pivot_table(index="製品名", columns="資材名", values="使用総数", aggfunc="sum", fill_value=0), use_container_width=True)
            else: st.info("指定期間内の実績はありません。")

    with t_p3:
        section("📝 資材の単体入出庫・棚卸調整")
        p_date = st.date_input("📅 処理日", value=date.today())
        sc1p, sc2p = st.columns([1.5,2.5])
        search_pack = sc1p.text_input("🔍 資材名検索", placeholder="検索...")
        filtered_p = [p for p in pack_mst_unique["資材名"].tolist() if search_pack in p] if search_pack else pack_mst_unique["資材名"].tolist()
        sel_pack = sc2p.selectbox("📦 対象資材", options=filtered_p, index=None, placeholder="選択してください")
        p_type = st.radio("処理区分", options=["📥 入庫（在庫を増やす）","📤 出庫・廃棄（在庫を減らす）","📋 棚卸（実在庫を入力）"], horizontal=True)
        if "棚卸" in p_type: p_qty = st.number_input("現在の実在庫数", min_value=0, step=1, format="%d", value=None); reason_opts = ["棚卸調整"]
        else: p_qty = st.number_input("処理する数量（正の数で入力）", min_value=1, step=1, format="%d", value=None); reason_opts = ["仕入（購入）","返品受付","その他入庫"] if "入庫" in p_type else ["破損・廃棄","サンプル出荷","その他出庫"]
        p_reason = st.selectbox("詳細な理由", options=reason_opts); p_rem = st.text_input("📝 備考")
        msg_slot_p_add = st.empty()
        if st.button("➕ 資材ログを登録", type="primary", use_container_width=True):
            if not sel_pack or p_qty is None: msg_slot_p_add.error("⚠️ 資材名と数量は必須です。")
            else:
                log_qty = to_int(p_qty); final_pt = "入庫" if "入庫" in p_type else "出庫"
                if "棚卸" in p_type:
                    diff = log_qty - pack_summary.get(sel_pack,{}).get("現在庫",0)
                    if diff >= 0: final_pt, log_qty = "入庫", diff
                    else: final_pt, log_qty = "出庫", abs(diff)
                if log_qty > 0:
                    append_and_sync("packaging_logs", pd.DataFrame([{"ID":str(uuid.uuid4())[:6].upper(),"登録日":pd.to_datetime(p_date),"資材名":sel_pack,"処理区分":final_pt,"数量":log_qty,"理由":p_reason,"関連製品名":"","理論在庫":"","備考":p_rem,"登録日時":datetime.now()}]))
                    st.session_state.msg_pack_add = f"✨ 資材ログ登録: {sel_pack} ({final_pt} {log_qty})"; st.rerun()
                else: msg_slot_p_add.info("現在の計算在庫と一致しているため調整不要です。")

    with t_p4:
        section("✏️ 登録データのかんたん修正・削除")
        if not pack_log_df.empty:
            disp_pack = pack_log_df.sort_values("登録日時", ascending=False).copy()
            disp_pack["登録日(表示)"] = disp_pack["登録日"].apply(format_date_jp)
            disp_cols_p = ["ID","登録日(表示)","資材名","処理区分","数量","理由","関連製品名","備考"]
            edited_p = st.data_editor(disp_pack.head(5).copy()[disp_cols_p], num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"登録日(表示)": st.column_config.TextColumn("登録日",disabled=True),"処理区分": st.column_config.SelectboxColumn("処理区分",options=["入庫","出庫","製造連動"]),"数量": st.column_config.NumberColumn("数量",min_value=1,step=1,format="%d"),"ID":None})
            if st.button("💾 直近データを修正・削除保存"):
                save_df_p = edited_p.copy(); save_df_p["登録日"] = pd.to_datetime(save_df_p["登録日(表示)"].str.split(" ").str[0], errors="coerce")
                save_and_sync("packaging_logs", pd.concat([pack_log_df[~pack_log_df["ID"].isin(disp_pack.head(5)["ID"])], pd.merge(save_df_p, pack_log_df[["ID","理論在庫","登録日時"]], on="ID", how="left")], ignore_index=True)); st.rerun()

elif page == "📑 登録一覧":
    page_header("📑 登録データ一覧・出力")
    t_l1, t_l2, t_l3 = st.tabs(["📋 受注・出荷データ","🏭 製造データ","📦 資材利用ログ"])
    with t_l1:
        if orders_df.empty: st.info("登録データがありません。")
        else:
            edf = orders_df.sort_values("登録日時", ascending=False).copy()
            edf["納品予定日(表示)"] = edf["納品予定日"].apply(format_date_jp)
            cols_l = ["ID","登録日時","大カテゴリ","顧客名","納品予定日(表示)","製品名","ケース数","運送会社","備考","荷姿チェック","発送備考","不良廃棄フラグ"]
            edf = edf[[c for c in cols_l if c in edf.columns]]
            def get_stock_status(row):
                try:
                    ds = str(row["納品予定日(表示)"]).split(" ")[0]; d2 = pd.Timestamp(ds).normalize(); p2 = row["製品名"]
                    stock = future_stocks[p2][d2] if d2>=today and p2 in future_stocks and d2 in future_stocks[p2] else current_stocks.get(p2,0)
                    return f"在庫不足 ({stock})" if stock < 0 else f"OK (+{stock})"
                except: return "不明"
            edf.insert(7,"在庫状況",edf.apply(get_stock_status,axis=1))
            def hl_row(row):
                irr = row.get("不良廃棄フラグ")==True or str(row.get("不良廃棄フラグ")).upper()=="TRUE"
                sho = "不足" in str(row.get("在庫状況",""))
                chk = row.get("荷姿チェック")==True or str(row.get("荷姿チェック")).upper()=="TRUE"
                nod = row.get("日付未定フラグ") is True or str(row.get("日付未定フラグ","")).upper()=="TRUE"
                if chk: return ['background-color:#D1FAE5; color:#065F46;']*len(row)
                if nod: return ['background-color:#FFFBEB; color:#92400E; border-left:3px solid #F59E0B;']*len(row)
                if sho and irr: return ['background-color:#FEF08A; color:#DC2626; font-weight:bold;']*len(row)
                if sho: return ['background-color:#FEE2E2; color:#DC2626; font-weight:bold;']*len(row)
                if irr: return ['background-color:#FEF08A; color:#854D0E; font-weight:bold;']*len(row)
                return ['']*len(row)
            odf2 = orders_df.sort_values("登録日時",ascending=False).copy()
            odf2["納品予定日"] = pd.to_datetime(odf2["納品予定日"],errors='coerce').apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "")
            for c in ["賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5"]:
                if c in odf2.columns: odf2[c] = pd.to_datetime(odf2[c],errors='coerce').apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "")
            odf2["荷姿チェック"] = odf2["荷姿チェック"].map({True:"済",False:"未"}).fillna("")
            odf2["不良廃棄フラグ"] = odf2["不良廃棄フラグ"].map({True:"○",False:""}).fillna("")
            csv_c = [c for c in ["納品予定日","顧客名","大カテゴリ","製品名","ケース数","運送会社","備考","荷姿チェック","発送備考","不良廃棄フラグ"] if c in odf2.columns]
            st.download_button("📥 受注一覧をCSV出力", data=make_csv_bytes(odf2[csv_c]), file_name=f"受注一覧_{date.today()}.csv", mime="text/csv", use_container_width=True)
            if "日付未定フラグ" in edf.columns: edf["状態"] = edf.apply(lambda r: "🟡 日付未定" if (r.get("日付未定フラグ") is True) else "", axis=1)
            st.markdown("""<div style="font-size:13px; margin:8px 0;">🎨 <span style="background:#FEE2E2;color:#DC2626;padding:2px 6px;border-radius:4px;">在庫不足</span>　<span style="background:#FEF08A;color:#854D0E;padding:2px 6px;border-radius:4px;">不良廃棄</span>　<span style="background:#D1FAE5;color:#065F46;padding:2px 6px;border-radius:4px;">✅荷姿完了</span>　<span style="background:#FFFBEB;color:#92400E;border:1px solid #F59E0B;padding:2px 6px;border-radius:4px;">🟡 日付未定</span></div>""", unsafe_allow_html=True)
            st.dataframe(edf.style.apply(hl_row,axis=1), use_container_width=True, hide_index=True, height=600)
    with t_l2:
        if manus_df.empty: st.info("製造データがありません。")
        else:
            mdf2 = manus_df.sort_values("登録日時",ascending=False).copy(); mdf2["製造予定日(表示)"] = mdf2["製造予定日"].apply(format_date_jp)
            om2 = mdf2.copy(); om2["製造予定日"] = om2["製造予定日"].apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else ""); om2["リパック"] = om2["リパックフラグ"].map({True:"○",False:""}).fillna("")
            st.download_button("📥 製造一覧をCSV出力", data=make_csv_bytes(om2[["製造予定日","製品名","ケース数","リパック","備考"]]), file_name=f"製造一覧_{date.today()}.csv", mime="text/csv", use_container_width=True)
            st.dataframe(mdf2[["ID","製造予定日(表示)","製品名","ケース数","リパックフラグ","備考"]].style.apply(lambda r: ['background-color:#DBEAFE; color:#1E3A8A; font-weight:bold;']*len(r) if str(r.get("リパックフラグ")).upper()=="TRUE" else ['']*len(r),axis=1), use_container_width=True, hide_index=True, height=600)
    with t_l3:
        if pack_log_df.empty: st.info("資材ログがありません。")
        else:
            ep = pack_log_df.sort_values("登録日時",ascending=False).copy(); ep["登録日(表示)"] = ep["登録日"].apply(format_date_jp)
            op = ep.copy(); op["登録日"] = op["登録日"].apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "")
            st.download_button("📥 資材ログをCSV出力", data=make_csv_bytes(op[["登録日","資材名","処理区分","数量","理由","関連製品名","備考"]]), file_name=f"資材ログ_{date.today()}.csv", mime="text/csv", use_container_width=True)
            st.dataframe(ep[["ID","登録日(表示)","資材名","処理区分","数量","理由","関連製品名","備考"]], use_container_width=True, hide_index=True, height=600)
```
elif page == "📊 在庫・スケジュール":
    page_header("📊 在庫予測 ＆ スケジュール")

    t0, t1, t2, t3, t4 = st.tabs(["⚠️ 7日以内欠品予測", "📉 1ヶ月在庫予測", "📅 週間カレンダー", "🔍 製品別詳細ビュー", "👤 顧客別スケジュール"])

    with t0:
        section("⚠️ 7日以内 欠品予測アラート")
        st.info("💡 直近7日間で在庫がマイナス（不足）になる製品とその顧客のリストです。")
        al = []
        for prod2, fs2 in future_stocks.items():
            for d2 in pd.date_range(today, today + timedelta(days=7)):
                v2 = fs2.get(d2, 0)
                if v2 < 0:
                    day_orders = orders_df[(orders_df["製品名"] == prod2) & (safe_dt_date(orders_df["納品予定日"]) == d2.date()) & (orders_df["不良廃棄フラグ"] == False)] if not orders_df.empty else pd.DataFrame()
                    al.append({"日付": format_date_jp(d2), "製品名": prod2, "予測在庫": v2, "現在庫": current_stocks.get(prod2, 0), "顧客名": " / ".join(day_orders["顧客名"].dropna().unique()) if not day_orders.empty else "―", "備考": " / ".join(day_orders["備考"].dropna().unique()) if not day_orders.empty else ""})
        if al:
            df_al = pd.DataFrame(al).drop_duplicates()
            st.dataframe(df_al.style.map(lambda v: 'color:#DC2626; font-weight:900; background-color:#FEE2E2;' if isinstance(v, (int,float)) and v < 0 else '', subset=["予測在庫"]), use_container_width=True, hide_index=True)
            st.download_button("📥 欠品アラートをCSV出力", data=make_csv_bytes(df_al), file_name=f"欠品アラート_{date.today()}.csv", mime="text/csv")
        else: st.success("✅ 直近7日以内の欠品予測はありません。")

    with t1:
        if master_df_unique.empty: st.info("製品マスタが空です。")
        else:
            inv_list = []
            show_dates = pd.date_range(today, today + timedelta(days=30))
            for _, r in master_df_unique.iterrows():
                p2 = r["製品名"]; curr_s = current_stocks.get(p2, 0)
                row_d = {"カテゴリ": r["大カテゴリ"], "製品名": p2, "現在庫": curr_s}
                for d2 in show_dates: row_d[format_date_jp(d2)] = future_stocks.get(p2, {}).get(d2, curr_s)
                inv_list.append(row_d)
            inv_df = pd.DataFrame(inv_list).sort_values("カテゴリ").reset_index(drop=True)

            col_inv1, col_inv2 = st.columns([3, 1])
            col_inv1.markdown('<div style="font-size:13px; color:#64748B; margin-bottom:6px;">💡 テーブルの <b>行をクリック</b> して製品名を選択 → 下の詳細が展開されます。右上の <b>⛶</b> ボタンで全画面表示。</div>', unsafe_allow_html=True)
            if col_inv2.button("🔄 詳細を閉じる", key="close_drill"): st.session_state.drill_product = None; st.rerun()

            sel_event = st.dataframe(inv_df.style.map(lambda v: 'color:#DC2626; font-weight:bold; background-color:#FEE2E2;' if isinstance(v, (int,float)) and v < 0 else ''), use_container_width=True, hide_index=True, height=min(max(len(inv_df)*35+50, 200), 700), on_select="rerun", selection_mode="single-row", key="inv_tbl_sel")
            selected_rows = sel_event.selection.get("rows", []) if hasattr(sel_event, "selection") else []
            if selected_rows: st.session_state.drill_product = inv_df.iloc[selected_rows[0]]["製品名"]
            st.download_button("📥 在庫予測CSVを出力", data=make_csv_bytes(inv_df), file_name=f"在庫予測_{date.today()}.csv", mime="text/csv", use_container_width=True)

            dp = st.session_state.drill_product
            if dp:
                st.markdown(f'<div class="drill-panel">### 📦 {format_name(dp)} の詳細スケジュール', unsafe_allow_html=True)
                one_year_ago = today - timedelta(days=365)
                p_o_hist = orders_df[(orders_df["製品名"] == dp) & (pd.to_datetime(orders_df["納品予定日"], errors='coerce') >= one_year_ago) & (pd.to_datetime(orders_df["納品予定日"], errors='coerce') < today)][["納品予定日","顧客名","ケース数","備考","荷姿チェック","不良廃棄フラグ"]].copy() if not orders_df.empty else pd.DataFrame()
                p_m_hist = manus_df[(manus_df["製品名"] == dp) & (pd.to_datetime(manus_df["製造予定日"], errors='coerce') >= one_year_ago) & (pd.to_datetime(manus_df["製造予定日"], errors='coerce') < today)][["製造予定日","ケース数","リパックフラグ","備考"]].copy() if not manus_df.empty else pd.DataFrame()

                with st.expander("📜 過去1年の履歴（出荷・製造 統合ビュー）", expanded=True):
                    total_shipped_h = p_o_hist["ケース数"].apply(to_int).sum() if not p_o_hist.empty else 0
                    total_mfg_h     = p_m_hist["ケース数"].apply(to_int).sum() if not p_m_hist.empty else 0
                    hk1, hk2, hk3, hk4 = st.columns(4)
                    hk1.metric("🚚 過去1年 出荷合計", f"{total_shipped_h:,} cs", delta=f"{len(p_o_hist) if not p_o_hist.empty else 0} 件")
                    hk2.metric("🏭 過去1年 製造合計", f"{total_mfg_h:,} cs", delta=f"{len(p_m_hist) if not p_m_hist.empty else 0} 回")
                    hk3.metric("差引（製造－出荷）", f"{total_mfg_h - total_shipped_h:+,} cs", delta_color="normal" if total_mfg_h - total_shipped_h >= 0 else "inverse")
                    hk4.metric("現在庫", f"{current_stocks.get(dp,0):,} cs")

                    hist_gr = []
                    if not p_o_hist.empty:
                        p_o_h2 = p_o_hist.copy(); p_o_h2["年月"] = pd.to_datetime(p_o_h2["納品予定日"],errors='coerce').dt.to_period("M").astype(str)
                        for ym, g in p_o_h2.groupby("年月"): hist_gr.append({"年月":ym,"区分":"🚚 出荷","cs":g["ケース数"].apply(to_int).sum()})
                    if not p_m_hist.empty:
                        p_m_h2 = p_m_hist.copy(); p_m_h2["年月"] = pd.to_datetime(p_m_h2["製造予定日"],errors='coerce').dt.to_period("M").astype(str)
                        for ym, g in p_m_h2.groupby("年月"): hist_gr.append({"年月":ym,"区分":"🏭 製造","cs":g["ケース数"].apply(to_int).sum()})
                    if hist_gr:
                        df_hgr = pd.DataFrame(hist_gr).sort_values("年月")
                        fig_hgr = go.Figure()
                        mfg_data  = df_hgr[df_hgr["区分"]=="🏭 製造"].set_index("年月")["cs"]; ship_data = df_hgr[df_hgr["区分"]=="🚚 出荷"].set_index("年月")["cs"]
                        all_months = sorted(df_hgr["年月"].unique())
                        fig_hgr.add_trace(go.Bar(x=all_months, y=[mfg_data.get(m,0) for m in all_months], name="🏭 製造", marker_color="#10B981", opacity=0.85))
                        fig_hgr.add_trace(go.Bar(x=all_months, y=[-ship_data.get(m,0) for m in all_months], name="🚚 出荷", marker_color="#F43F5E", opacity=0.85))
                        fig_hgr.add_trace(go.Scatter(x=all_months, y=[mfg_data.get(m,0) - ship_data.get(m,0) for m in all_months], name="差引（製造－出荷）", mode="lines+markers", line=dict(color="#7C3AED", width=2, dash="dot"), marker=dict(size=6)))
                        fig_hgr.add_hline(y=0, line_color="#94A3B8", line_dash="dash")
                        fig_hgr.update_layout(barmode="relative", hovermode="x unified", title=f"【{dp}】 月次 製造（上）・出荷（下）・差引推移", margin=dict(l=10,r=10,t=45,b=10), height=300, legend=dict(orientation="h", y=1.12))
                        st.plotly_chart(fig_hgr, use_container_width=True)

                    col_h1, col_h2 = st.columns(2)
                    with col_h1:
                        st.markdown('<div style="font-size:13px;font-weight:800;color:#DC2626;border-left:4px solid #DC2626;padding-left:8px;margin-bottom:6px;">🚚 出荷履歴</div>', unsafe_allow_html=True)
                        if p_o_hist.empty: st.info("出荷履歴なし")
                        else:
                            po_d = p_o_hist.copy(); po_d["日付"] = po_d["納品予定日"].apply(format_date_jp); po_d["荷姿"] = po_d["荷姿チェック"].map({True:"✅",False:"⏳"}).fillna("") if "荷姿チェック" in po_d.columns else ""; po_d["廃棄"] = po_d["不良廃棄フラグ"].map({True:"⚠️",False:""}).fillna("") if "不良廃棄フラグ" in po_d.columns else ""
                            st.dataframe(po_d[["日付","顧客名","ケース数","荷姿","廃棄"]].sort_values("日付",ascending=False).style.apply(lambda r: ["background:#FEF3C7;"]*len(r) if r.get("廃棄")=="⚠️" else (["background:#FFF7F7;"]*len(r) if r.get("荷姿")=="⏳" else ["background:#FFF0F0;"]*len(r)), axis=1), use_container_width=True, hide_index=True, height=min(len(po_d)*35+50, 420))
                    with col_h2:
                        st.markdown('<div style="font-size:13px;font-weight:800;color:#059669;border-left:4px solid #059669;padding-left:8px;margin-bottom:6px;">🏭 製造履歴</div>', unsafe_allow_html=True)
                        if p_m_hist.empty: st.info("製造履歴なし")
                        else:
                            pm_d = p_m_hist.copy(); pm_d["日付"] = pm_d["製造予定日"].apply(format_date_jp); pm_d["種別"] = pm_d["リパックフラグ"].map({True:"🔄リパック",False:"🏭通常"}).fillna("🏭通常") if "リパックフラグ" in pm_d.columns else "🏭通常"
                            st.dataframe(pm_d[["日付","ケース数","種別","備考"]].sort_values("日付",ascending=False).style.apply(lambda r: ["background:#EFF6FF;"]*len(r) if "リパック" in str(r.get("種別","")) else ["background:#F0FDF4;"]*len(r), axis=1), use_container_width=True, hide_index=True, height=min(len(pm_d)*35+50, 420))

                st.markdown('<div class="section-title">📅 今後60日間の予定スケジュール</div>', unsafe_allow_html=True)
                p_o_ev2 = orders_df[(orders_df["製品名"]==dp) & (pd.to_datetime(orders_df["納品予定日"],errors='coerce') >= today)][["納品予定日","顧客名","ケース数","備考"]].copy() if not orders_df.empty else pd.DataFrame(columns=["納品予定日","顧客名","ケース数","備考"])
                p_m_ev2 = manus_df[(manus_df["製品名"]==dp) & (pd.to_datetime(manus_df["製造予定日"],errors='coerce') >= today)][["製造予定日","ケース数","備考"]].copy() if not manus_df.empty else pd.DataFrame(columns=["製造予定日","ケース数","備考"])
                detail2 = []; tmp_s = current_stocks.get(dp, 0)
                for d2 in pd.date_range(today, today + timedelta(days=59)):
                    day_o2 = p_o_ev2[safe_dt_date(p_o_ev2["納品予定日"]) == d2.date()] if not p_o_ev2.empty else pd.DataFrame()
                    out_q = to_int(day_o2["ケース数"].sum()) if not day_o2.empty else 0
                    day_m2 = p_m_ev2[safe_dt_date(p_m_ev2["製造予定日"]) == d2.date()] if not p_m_ev2.empty else pd.DataFrame()
                    in_q = to_int(day_m2["ケース数"].sum()) if not day_m2.empty else 0
                    tmp_s = tmp_s + in_q - out_q
                    detail2.append({"日付": format_date_jp(d2), "製造(入)": in_q if in_q > 0 else "", "製造詳細": " / ".join([f"製造({to_int(r['ケース数'])}cs)" for _, r in day_m2.iterrows()]) if not day_m2.empty else "", "出荷(出)": out_q if out_q > 0 else "", "出荷先": " / ".join([f"{'⭐' if is_special_order(str(r['備考'])) else ''}{r['顧客名']}({to_int(r['ケース数'])}cs)" for _, r in day_o2.iterrows()]) if not day_o2.empty else "", "予定在庫": tmp_s, "": "🔴" if tmp_s < 0 else ""})
                df_d2 = pd.DataFrame(detail2)

                fig2 = go.Figure()
                fig2.add_trace(go.Bar(x=df_d2["日付"], y=[r["製造(入)"] if r["製造(入)"] != "" else 0 for _,r in df_d2.iterrows()], name="製造(入)", marker_color="#10B981", opacity=0.7))
                fig2.add_trace(go.Bar(x=df_d2["日付"], y=[-(r["出荷(出)"] if r["出荷(出)"] != "" else 0) for _,r in df_d2.iterrows()], name="出荷(出)", marker_color="#F43F5E", opacity=0.7))
                fig2.add_trace(go.Scatter(x=df_d2["日付"], y=df_d2["予定在庫"], name="予定在庫", mode="lines+markers", line=dict(color="#2563EB", width=2.5), marker=dict(size=5)))
                fig2.update_layout(barmode="relative", hovermode="x unified", margin=dict(l=10,r=10,t=30,b=10), height=320, legend=dict(orientation="h",y=1.1))
                st.plotly_chart(fig2, use_container_width=True)

                active_rows = df_d2[(df_d2["製造(入)"] != "") | (df_d2["出荷(出)"] != "") | (df_d2["予定在庫"] < 0)]
                if not active_rows.empty: st.dataframe(active_rows.style.map(lambda v: 'color:#DC2626; font-weight:900; background-color:#FEE2E2;' if isinstance(v,(int,float)) and v < 0 else '', subset=["予定在庫"]), use_container_width=True, hide_index=True)
                else: st.info("この期間に製造・出荷の予定はありません。")
                st.markdown('</div>', unsafe_allow_html=True)

    with t2:
        cal_data = []
        html = '<table class="sched-table"><tr><th style="width:130px;">日付</th><th style="width:38%;">🏭 製造 / リパック</th><th style="width:44%;">🚚 出荷 / 不良廃棄</th></tr>'
        for i in range(7):
            d2 = today + timedelta(days=i); m_h = ""; o_h = ""
            if not manus_df.empty:
                for _, r in manus_df[pd.to_datetime(manus_df["製造予定日"],errors='coerce').dt.normalize() == d2].iterrows():
                    p2, qty2 = r["製品名"], to_int(r.get("ケース数",0))
                    is_rp = r.get("リパックフラグ") in [True,"TRUE"]
                    bg,bc = ("#DBEAFE","#1E3A8A") if is_rp else ("#F0FFF4","#10B981")
                    m_h += f'<div style="background:{bg};border-left:4px solid {bc};padding:6px;margin-bottom:4px;border-radius:6px;"><b>{format_name(p2)}</b><span style="float:right;"><span style="color:{"#1E3A8A" if is_rp else "#059669"}; font-weight:900;">{qty2}cs{"(リパック)" if is_rp else ""}</span></span></div>'
            if not orders_df.empty:
                for _, r in orders_df[pd.to_datetime(orders_df["納品予定日"],errors='coerce').dt.normalize() == d2].iterrows():
                    p2, qty2 = r["製品名"], to_int(r.get("ケース数",0)); sod = future_stocks.get(p2,{}).get(d2,0)
                    is_chk = r.get("荷姿チェック") in [True,"TRUE"]; is_irr = r.get("不良廃棄フラグ") in [True,"TRUE"]
                    sp_b = '<span class="badge badge-special">特注</span>' if "特注" in str(r.get("備考","")) else ('<span class="badge badge-charter">チャーター</span>' if "チャーター便" in str(r.get("備考","")) else "")
                    if is_chk: qh,bg,bc = f'<span style="color:#065F46;font-weight:900;text-decoration:line-through;">{qty2}cs</span>',"#D1FAE5","#059669"
                    elif is_irr: qh,bg,bc = f'<span style="color:#B45309;font-weight:900;">{qty2}cs(不良)</span>',"#FEF3C7","#D97706"
                    elif sod < 0: qh,bg,bc = f'<span class="shortage-red">{qty2}cs(不足)</span>',"#FEE2E2","#DC2626"
                    else: qh,bg,bc = f'<span style="color:#1D4ED8;font-weight:900;">{qty2}cs</span>',"#F0F7FF","#2563EB"
                    o_h += f'<div style="background:{bg};border-left:4px solid {bc};padding:6px;margin-bottom:4px;border-radius:6px;"><b>{r["顧客名"]}: {format_name(p2)}</b>{sp_b}<span style="float:right;">{qh}</span></div>'
            html += f'<tr><td><b>{format_date_jp(d2)}</b></td><td>{m_h if m_h else "<span style=\'color:#94A3B8;font-size:12px;\'>なし</span>"}</td><td>{o_h if o_h else "<span style=\'color:#94A3B8;font-size:12px;\'>なし</span>"}</td></tr>'
            cal_data.append({"日付": format_date_jp(d2), "製造予定": " / ".join([f"{r['製品名']}({to_int(r['ケース数'])}cs)" for _,r in manus_df[pd.to_datetime(manus_df["製造予定日"],errors='coerce').dt.normalize()==d2].iterrows()]) if not manus_df.empty else "", "出荷予定": " / ".join([f"{r['顧客名']}:{r['製品名']}({to_int(r['ケース数'])}cs)" for _,r in orders_df[pd.to_datetime(orders_df["納品予定日"],errors='coerce').dt.normalize()==d2].iterrows()]) if not orders_df.empty else ""})
        st.download_button("🖨️ カレンダーCSVを出力", data=make_csv_bytes(pd.DataFrame(cal_data)), file_name=f"カレンダー_{today.strftime('%Y%m%d')}.csv", type="primary", use_container_width=True)
        st.markdown(html + '</table>', unsafe_allow_html=True)

    with t3:
        section("🔍 製品別 在庫推移と詳細スケジュール")
        if master_df_unique.empty: st.info("製品が登録されていません。")
        else:
            cat_full_det = st.pills("カテゴリ詳細", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed", key="pills_det")
            cat_det = cat_full_det.split(" ",1)[1] if cat_full_det else CATEGORIES[0].split(" ",1)[1]
            sc1d, sc2d = st.columns([1.5, 2.5])
            srch_d = sc1d.text_input("🔍 製品名検索", placeholder="名称の一部を入力...", key="search_det")
            prods_d = ([p for p in master_df_unique["製品名"].tolist() if srch_d in p] if srch_d else master_df_unique[master_df_unique["大カテゴリ"] == cat_det]["製品名"].tolist() if not master_df_unique.empty else [])
            dp = st.session_state.get("drill_product")
            if dp and dp not in prods_d: prods_d.insert(0, dp)
            sel_prod = sc2d.selectbox("確定製品", options=prods_d, index=prods_d.index(dp) if dp in prods_d else None, format_func=format_name, key="sel_det", placeholder="選択してください")

            if sel_prod:
                st.session_state.drill_product = sel_prod; one_year_ago_t3 = today - timedelta(days=365)
                curr_stk = current_stocks.get(sel_prod, 0)
                past_o_all = orders_df[(orders_df["製品名"]==sel_prod) & (pd.to_datetime(orders_df["納品予定日"],errors='coerce') >= one_year_ago_t3) & (pd.to_datetime(orders_df["納品予定日"],errors='coerce') < today)] if not orders_df.empty else pd.DataFrame()
                past_m_all = manus_df[(manus_df["製品名"]==sel_prod) & (pd.to_datetime(manus_df["製造予定日"],errors='coerce') >= one_year_ago_t3) & (pd.to_datetime(manus_df["製造予定日"],errors='coerce') < today)] if not manus_df.empty else pd.DataFrame()
                
                kpi1, kpi2, kpi3, kpi4 = st.columns(4)
                kpi1.metric("現在庫", f"{curr_stk:,} cs", delta="現時点")
                kpi2.metric("過去1年 出荷合計", f"{past_o_all['ケース数'].apply(to_int).sum():,} cs" if not past_o_all.empty else "0 cs", delta=f"{len(past_o_all)} 件")
                kpi3.metric("過去1年 製造合計", f"{past_m_all['ケース数'].apply(to_int).sum():,} cs" if not past_m_all.empty else "0 cs", delta=f"{len(past_m_all)} 回")
                kpi4.metric("7日以内 欠品日数", f"{sum(1 for d2 in pd.date_range(today, today+timedelta(days=7)) if future_stocks.get(sel_prod,{}).get(d2,0) < 0)} 日", delta_color="inverse")

                dtab_hist, dtab_future, dtab_graph = st.tabs(["📜 過去1年の履歴", "📅 今後60日の予定", "📈 月次グラフ（1年+予測）"])

                with dtab_hist:
                    with st.expander("➕ 過去の製造実績を登録する（在庫に反映させない記録用）", expanded=False):
                        st.info("💡 過去の実績や、在庫調整済みのデータを**グラフと履歴にのみ残す**ための登録です。（現在の在庫予測には影響しません）")
                        h_col1, h_col2, h_col3 = st.columns([1, 1, 2])
                        hist_date = h_col1.date_input("📅 製造日（過去）", value=today - timedelta(days=1), key="hist_m_date")
                        hist_qty  = h_col2.number_input("📦 製造ケース数", min_value=1, step=1, key="hist_m_qty")
                        hist_rem  = h_col3.text_input("📝 備考", placeholder="例：過去実績入力", key="hist_m_rem")
                        if st.button("💾 履歴として登録（在庫非反映）", key="btn_hist_add"):
                            append_and_sync("manufactures", pd.DataFrame([{"ID": str(uuid.uuid4())[:6].upper(), "製造予定日": pd.to_datetime(hist_date), "大カテゴリ": cat_det, "製品名": sel_prod, "ケース数": to_int(hist_qty), "リパックフラグ": False, "備考": f"【在庫非反映】 {hist_rem}".strip(), "登録日時": datetime.now()}]))
                            st.success(f"✅ {sel_prod} の過去実績（{hist_qty}cs）を登録しました！"); st.rerun()

                    t3_out_total = past_o_all["ケース数"].apply(to_int).sum() if not past_o_all.empty else 0
                    t3_mfg_total = past_m_all["ケース数"].apply(to_int).sum() if not past_m_all.empty else 0
                    sk1, sk2, sk3, sk4 = st.columns(4)
                    sk1.metric("🚚 過去1年 出荷合計", f"{t3_out_total:,} cs", delta=f"{len(past_o_all) if not past_o_all.empty else 0} 件")
                    sk2.metric("🏭 過去1年 製造合計", f"{t3_mfg_total:,} cs", delta=f"{len(past_m_all) if not past_m_all.empty else 0} 回")
                    sk3.metric("差引（製造－出荷）", f"{t3_mfg_total - t3_out_total:+,} cs", delta_color="normal" if t3_mfg_total - t3_out_total >= 0 else "inverse")
                    sk4.metric("現在庫", f"{curr_stk:,} cs")

                    hist_gr = []
                    if not past_o_all.empty:
                        po_g = past_o_all.copy(); po_g["年月"] = pd.to_datetime(po_g["納品予定日"],errors="coerce").dt.to_period("M").astype(str)
                        for ym, g in po_g.groupby("年月"): hist_gr.append({"年月":ym,"区分":"🚚 出荷","cs":g["ケース数"].apply(to_int).sum()})
                    if not past_m_all.empty:
                        pm_g = past_m_all.copy(); pm_g["年月"] = pd.to_datetime(pm_g["製造予定日"],errors="coerce").dt.to_period("M").astype(str)
                        for ym, g in pm_g.groupby("年月"): hist_gr.append({"年月":ym,"区分":"🏭 製造","cs":g["ケース数"].apply(to_int).sum()})
                    if hist_gr:
                        df_t3gr = pd.DataFrame(hist_gr).sort_values("年月"); all_m = sorted(df_t3gr["年月"].unique())
                        mfg_s = df_t3gr[df_t3gr["区分"]=="🏭 製造"].set_index("年月")["cs"]; ship_s = df_t3gr[df_t3gr["区分"]=="🚚 出荷"].set_index("年月")["cs"]
                        fig_t3h = go.Figure()
                        fig_t3h.add_trace(go.Bar(x=all_m, y=[mfg_s.get(m,0) for m in all_m], name="🏭 製造", marker_color="#10B981", opacity=0.85))
                        fig_t3h.add_trace(go.Bar(x=all_m, y=[-ship_s.get(m,0) for m in all_m], name="🚚 出荷", marker_color="#F43F5E", opacity=0.85))
                        fig_t3h.add_trace(go.Scatter(x=all_m, y=[mfg_s.get(m,0)-ship_s.get(m,0) for m in all_m], name="差引（製造－出荷）", mode="lines+markers", line=dict(color="#7C3AED",width=2,dash="dot"), marker=dict(size=6)))
                        fig_t3h.add_hline(y=0, line_color="#94A3B8", line_dash="dash")
                        fig_t3h.update_layout(barmode="relative", hovermode="x unified", title=f"【{sel_prod}】 月次 製造（上）・出荷（下）・差引推移（過去1年）", margin=dict(l=10,r=10,t=45,b=10), height=300, legend=dict(orientation="h", y=1.12))
                        st.plotly_chart(fig_t3h, use_container_width=True)

                    tc1, tc2 = st.columns(2)
                    with tc1:
                        st.markdown('<div style="font-size:13px;font-weight:800;color:#DC2626;border-left:4px solid #DC2626;padding-left:8px;margin-bottom:6px;">🚚 出荷履歴</div>', unsafe_allow_html=True)
                        if past_o_all.empty: st.info("出荷履歴なし")
                        else:
                            po_d3 = past_o_all.copy(); po_d3["日付"] = po_d3["納品予定日"].apply(format_date_jp)
                            po_d3["荷姿"] = po_d3["荷姿チェック"].map({True:"✅",False:"⏳"}).fillna("") if "荷姿チェック" in po_d3.columns else ""
                            po_d3["廃棄"] = po_d3["不良廃棄フラグ"].map({True:"⚠️",False:""}).fillna("") if "不良廃棄フラグ" in po_d3.columns else ""
                            st.dataframe(po_d3[["日付","顧客名","ケース数","荷姿","廃棄"]].sort_values("日付",ascending=False).style.apply(lambda r: ["background:#FEF3C7;"]*len(r) if r.get("廃棄")=="⚠️" else (["background:#FFF7F7;"]*len(r) if r.get("荷姿")=="⏳" else ["background:#FFF0F0;"]*len(r)), axis=1), use_container_width=True, hide_index=True, height=min(len(po_d3)*35+50, 420))
                    with tc2:
                        st.markdown('<div style="font-size:13px;font-weight:800;color:#059669;border-left:4px solid #059669;padding-left:8px;margin-bottom:6px;">🏭 製造履歴</div>', unsafe_allow_html=True)
                        if past_m_all.empty: st.info("製造履歴なし")
                        else:
                            pm_d3 = past_m_all.copy(); pm_d3["日付"] = pm_d3["製造予定日"].apply(format_date_jp)
                            pm_d3["種別"] = pm_d3["リパックフラグ"].map({True:"🔄リパック",False:"🏭通常"}).fillna("🏭通常") if "リパックフラグ" in pm_d3.columns else "🏭通常"
                            st.dataframe(pm_d3[["日付","ケース数","種別","備考"]].sort_values("日付",ascending=False).style.apply(lambda r: ["background:#F8FAFC; color:#64748B;"]*len(r) if "【在庫非反映】" in str(r.get("備考","")) else (["background:#EFF6FF;"]*len(r) if "リパック" in str(r.get("種別","")) else ["background:#F0FDF4;"]*len(r)), axis=1), use_container_width=True, hide_index=True, height=min(len(pm_d3)*35+50, 420))

                with dtab_future:
                    p_o3 = orders_df[(orders_df["製品名"]==sel_prod) & (pd.to_datetime(orders_df["納品予定日"],errors='coerce') >= today)][["納品予定日","顧客名","ケース数","備考"]].copy() if not orders_df.empty else pd.DataFrame()
                    _valid_m3 = manus_df[~manus_df["備考"].fillna("").str.contains("【在庫非反映】")] if not manus_df.empty else pd.DataFrame()
                    p_m3 = _valid_m3[(_valid_m3["製品名"]==sel_prod) & (pd.to_datetime(_valid_m3["製造予定日"],errors='coerce') >= today)][["製造予定日","ケース数"]].copy() if not _valid_m3.empty else pd.DataFrame()
                    dl3 = []; ts3 = current_stocks.get(sel_prod, 0)
                    for d3 in pd.date_range(today, today+timedelta(days=59)):
                        do3 = p_o3[safe_dt_date(p_o3["納品予定日"]) == d3.date()] if not p_o3.empty else pd.DataFrame()
                        oq3 = to_int(do3["ケース数"].sum()) if not do3.empty else 0
                        dm3 = p_m3[safe_dt_date(p_m3["製造予定日"]) == d3.date()] if not p_m3.empty else pd.DataFrame()
                        iq3 = to_int(dm3["ケース数"].sum()) if not dm3.empty else 0
                        ts3 = ts3 + iq3 - oq3
                        dl3.append({"日付": format_date_jp(d3), "製造(入)": iq3 if iq3>0 else "", "製造詳細": " / ".join([f"製造({to_int(r['ケース数'])}cs)" for _,r in dm3.iterrows()]) if not dm3.empty else "", "出荷(出)": oq3 if oq3>0 else "", "出荷詳細": " / ".join([f"{'⭐' if is_special_order(str(r.get('備考',''))) else ''}{r['顧客名']}({to_int(r['ケース数'])}cs)" for _,r in do3.iterrows()]) if not do3.empty else "", "予定在庫": ts3, "": "🔴" if ts3<0 else ""})
                    df3 = pd.DataFrame(dl3)
                    fig3 = go.Figure()
                    fig3.add_trace(go.Bar(x=df3["日付"], y=[r["製造(入)"] if r["製造(入)"]!="" else 0 for _,r in df3.iterrows()], name="製造", marker_color="#10B981", opacity=0.7))
                    fig3.add_trace(go.Bar(x=df3["日付"], y=[-(r["出荷(出)"] if r["出荷(出)"]!="" else 0) for _,r in df3.iterrows()], name="出荷", marker_color="#F43F5E", opacity=0.7))
                    fig3.add_trace(go.Scatter(x=df3["日付"], y=df3["予定在庫"], name="予定在庫", mode="lines+markers", line=dict(color="#2563EB",width=2.5)))
                    fig3.update_layout(barmode="relative", hovermode="x unified", margin=dict(l=10,r=10,t=40,b=10), height=320, legend=dict(orientation="h",y=1.1))
                    st.plotly_chart(fig3, use_container_width=True)
                    active3 = df3[(df3["製造(入)"]!="") | (df3["出荷(出)"]!="") | (df3["予定在庫"]<0)]
                    if not active3.empty: st.dataframe(active3.style.map(lambda v: 'color:#DC2626; font-weight:bold; background-color:#FEE2E2;' if isinstance(v,(int,float)) and v < 0 else '', subset=["予定在庫"]), use_container_width=True, hide_index=True)
                    else: st.info("今後60日間に製造・出荷の予定はありません。")

                with dtab_graph:
                    graph_rows = []
                    if not past_o_all.empty:
                        po_m = past_o_all.copy(); po_m["年月"] = pd.to_datetime(po_m["納品予定日"],errors='coerce').dt.to_period("M").astype(str)
                        for ym, grp in po_m.groupby("年月"): graph_rows.append({"年月": ym, "種別": "出荷(実績)", "ケース数": grp["ケース数"].apply(to_int).sum()})
                    if not past_m_all.empty:
                        pm_m = past_m_all.copy(); pm_m["年月"] = pd.to_datetime(pm_m["製造予定日"],errors='coerce').dt.to_period("M").astype(str)
                        for ym, grp in pm_m.groupby("年月"): graph_rows.append({"年月": ym, "種別": "製造(実績)", "ケース数": grp["ケース数"].apply(to_int).sum()})
                    fut_o = orders_df[(orders_df["製品名"]==sel_prod) & (pd.to_datetime(orders_df["納品予定日"],errors='coerce') >= today)] if not orders_df.empty else pd.DataFrame()
                    fut_m = _valid_m3[(_valid_m3["製品名"]==sel_prod) & (pd.to_datetime(_valid_m3["製造予定日"],errors='coerce') >= today)] if not _valid_m3.empty else pd.DataFrame()
                    if not fut_o.empty:
                        fo_m = fut_o.copy(); fo_m["年月"] = pd.to_datetime(fo_m["納品予定日"],errors='coerce').dt.to_period("M").astype(str)
                        for ym, grp in fo_m.groupby("年月"): graph_rows.append({"年月": ym, "種別": "出荷(予定)", "ケース数": grp["ケース数"].apply(to_int).sum()})
                    if not fut_m.empty:
                        fm_m = fut_m.copy(); fm_m["年月"] = pd.to_datetime(fm_m["製造予定日"],errors='coerce').dt.to_period("M").astype(str)
                        for ym, grp in fm_m.groupby("年月"): graph_rows.append({"年月": ym, "種別": "製造(予定)", "ケース数": grp["ケース数"].apply(to_int).sum()})
                    
                    if graph_rows:
                        df_gr = pd.DataFrame(graph_rows).sort_values("年月")
                        fig_gr = px.bar(df_gr, x="年月", y="ケース数", color="種別", barmode="group", color_discrete_map={"出荷(実績)":"#F43F5E","出荷(予定)":"#FCA5A5","製造(実績)":"#10B981","製造(予定)":"#6EE7B7"}, title=f"【{sel_prod}】 月次 製造・出荷量（過去1年 ＋ 今後予定） / 今月: {today.strftime('%Y-%m')}")
                        fig_gr.update_layout(margin=dict(l=10,r=10,t=50,b=10), height=400, legend=dict(orientation="h",y=1.1))
                        st.plotly_chart(fig_gr, use_container_width=True)
                        st.dataframe(df_gr.pivot_table(index="年月", columns="種別", values="ケース数", aggfunc="sum").fillna(0).reset_index(), use_container_width=True, hide_index=True)
                    else: st.info("グラフ表示に必要なデータがありません。")

    with t4:
        section("👤 顧客別 今後の発送スケジュール")
        cust_list_s = sorted(orders_df[orders_df["顧客名"].str.strip()!=""]["顧客名"].unique().tolist()) if not orders_df.empty else []
        sc1c,sc2c = st.columns([1.5,2.5])
        srch_c = sc1c.text_input("🔍 顧客検索", placeholder="名前の一部を入力...")
        sel_c  = sc2c.selectbox("対象顧客を選択", options=[c for c in cust_list_s if srch_c in c] if srch_c else cust_list_s, index=None, placeholder="選択してください")
        if sel_c:
            co = orders_df[(orders_df["顧客名"]==sel_c) & (pd.to_datetime(orders_df["納品予定日"],errors='coerce') >= today)].copy()
            if co.empty: st.info("今後の納品予定はありません。")
            else:
                co = co.sort_values("納品予定日")
                co["在庫状況"] = co.apply(lambda r: f"❌ 欠品 ({future_stocks.get(r['製品名'],{}).get(pd.Timestamp(r['納品予定日']).normalize(),0)})" if future_stocks.get(r['製品名'],{}).get(pd.Timestamp(r['納品予定日']).normalize(),0) < 0 else "✅ OK", axis=1)
                co["納品予定日"] = co["納品予定日"].apply(format_date_jp)
                st.dataframe(co[["納品予定日","製品名","ケース数","在庫状況","備考"]].style.map(lambda v: 'color:#DC2626; font-weight:bold; background-color:#FEE2E2;' if "❌" in str(v) else '', subset=["在庫状況"]), use_container_width=True, hide_index=True)

elif page == "⭐ 特注・チャータースケジュール":
    page_header("⭐ 特注・チャータースケジュール")
    sp_orders = orders_df[orders_df["備考"].apply(is_special_order)].copy() if not orders_df.empty else pd.DataFrame()
    tab_sp1, tab_sp2, tab_sp3 = st.tabs(["📋 特注・チャーター便一覧","📅 製品別 出荷日スケジュール","✏️ スケジュール編集・保存"])

    with tab_sp1:
        if sp_orders.empty: st.info("特注・チャーター便の受注データがありません。")
        else:
            sp_orders["種別"] = sp_orders["備考"].apply(lambda rem: "特注+チャーター便" if "特注" in str(rem) and "チャーター便" in str(rem) else ("特注" if "特注" in str(rem) else "チャーター便"))
            sp_orders["納品予定日(表示)"] = sp_orders["納品予定日"].apply(format_date_jp)
            if not special_df.empty:
                sm = pd.merge(sp_orders, special_df[["受注ID","出荷予定日","備考"]].rename(columns={"備考":"出荷備考","受注ID":"ID"}), on="ID", how="left")
                sm["出荷予定日"] = pd.to_datetime(sm["出荷予定日"],errors='coerce').apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "（未設定）")
            else: sm = sp_orders.copy(); sm["出荷予定日"] = "（未設定）"; sm["出荷備考"] = ""
            sc = [c for c in ["種別","顧客名","納品予定日(表示)","出荷予定日","製品名","ケース数","備考"] if c in sm.columns]
            st.dataframe(sm[sc].style.apply(lambda r: ['background-color:#F3E8FF; font-weight:bold;']*len(r) if "特注" in str(r.get("種別","")) and "チャーター" in str(r.get("種別","")) else (['background-color:#EDE9FE; font-weight:bold;']*len(r) if "特注" in str(r.get("種別","")) else ['background-color:#E0F2FE; font-weight:bold;']*len(r)), axis=1), use_container_width=True, hide_index=True)

    with tab_sp2:
        section("📅 製品別 出荷日スケジュール一覧")
        if sp_orders.empty: st.info("特注・チャーター便の受注データがありません。")
        else:
            pl = sorted(sp_orders["製品名"].unique().tolist())
            sel_sp_p = st.selectbox("製品を選択", options=["（全製品）"]+pl, index=0, key="sel_sp_prod")
            fsp = sp_orders.copy() if sel_sp_p=="（全製品）" else sp_orders[sp_orders["製品名"]==sel_sp_p].copy()
            fsp = fsp.sort_values("納品予定日"); fsp["納品予定日(表示)"] = fsp["納品予定日"].apply(format_date_jp)
            if not special_df.empty:
                fsm = pd.merge(fsp, special_df[["受注ID","出荷予定日"]].rename(columns={"受注ID":"ID"}), on="ID", how="left")
                fsm["出荷予定日"] = pd.to_datetime(fsm["出荷予定日"],errors='coerce').apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "（未設定）")
            else: fsm = fsp.copy(); fsm["出荷予定日"] = "（未設定）"
            sf = [c for c in ["製品名","顧客名","納品予定日(表示)","出荷予定日","ケース数","備考"] if c in fsm.columns]
            st.dataframe(fsm[sf], use_container_width=True, hide_index=True)

    with tab_sp3:
        section("✏️ 出荷予定日の編集・保存")
        if sp_orders.empty: st.info("特注・チャーター便の受注データがありません。")
        else:
            ex_ids = special_df["受注ID"].tolist() if not special_df.empty else []
            new_sp_rows = [{"ID":str(uuid.uuid4())[:6].upper(),"受注ID":r["ID"],"製品名":r["製品名"],"顧客名":r["顧客名"],"納品予定日":r["納品予定日"],"出荷予定日":r["納品予定日"]-timedelta(days=1) if pd.notnull(r["納品予定日"]) else None,"備考":r.get("備考",""),"更新日時":datetime.now()} for _, r in sp_orders.iterrows() if r["ID"] not in ex_ids]
            special_df_work = pd.concat([special_df, pd.DataFrame(new_sp_rows)], ignore_index=True) if new_sp_rows else special_df.copy()
            sp_edit = pd.merge(special_df_work, orders_df[["ID","備考"]].rename(columns={"ID":"受注ID","備考":"受注備考"}), on="受注ID", how="left")
            sp_edit["種別"] = sp_edit["受注備考"].apply(lambda x: "特注" if "特注" in str(x) else "チャーター便")
            sp_edit["納品予定日(表示)"] = pd.to_datetime(sp_edit["納品予定日"],errors='coerce').apply(format_date_jp)
            sp_edit["出荷予定日_edit"] = pd.to_datetime(sp_edit["出荷予定日"],errors='coerce').dt.date
            ec = [c for c in ["ID","種別","製品名","顧客名","納品予定日(表示)","出荷予定日_edit","備考"] if c in sp_edit.columns]
            edited_sp = st.data_editor(sp_edit[ec], use_container_width=True, hide_index=True, column_config={"ID":None,"種別":st.column_config.TextColumn("種別",disabled=True),"製品名":st.column_config.TextColumn("製品名",disabled=True),"顧客名":st.column_config.TextColumn("顧客名",disabled=True),"納品予定日(表示)":st.column_config.TextColumn("納品予定日",disabled=True),"出荷予定日_edit":st.column_config.DateColumn("📅 出荷予定日（編集可）",format="YYYY/MM/DD"),"備考":st.column_config.TextColumn("備考（メモ）")}, key="edit_sp_sched")
            if st.button("💾 特注スケジュールを保存・同期", type="primary", use_container_width=True):
                save_sp = special_df_work.copy()
                for idx, row in edited_sp.iterrows():
                    id_v = sp_edit.iloc[idx]["ID"] if idx < len(sp_edit) else None
                    if id_v:
                        mask = save_sp["ID"] == id_v
                        if row.get("出荷予定日_edit"): save_sp.loc[mask,"出荷予定日"] = pd.to_datetime(row.get("出荷予定日_edit"))
                        save_sp.loc[mask,"備考"] = str(row.get("備考",""))
                        save_sp.loc[mask,"更新日時"] = datetime.now()
                save_and_sync("special_schedule", save_sp); st.rerun()

elif page == "📈 経営・分析ダッシュボード":
    page_header("📈 経営・製造管理 ダッシュボード")
    tab_d1,tab_d2,tab_d3,tab_d4 = st.tabs(["🏠 経営サマリ","📦 製品・ABC分析","🏭 製造効率分析","📅 月次トレンド"])
    with tab_d1:
        section("📊 経営 KPI サマリ")
        if not orders_df.empty:
            this_m = date.today().replace(day=1)
            _om = orders_df[(safe_dt_date(orders_df["納品予定日"]) >= this_m) & (orders_df["不良廃棄フラグ"]==False)]
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("今月 出荷総数", f"{_om['ケース数'].apply(to_int).sum():,} cs", delta=f"{_om['顧客名'].nunique()} 顧客")
            c2.metric("今月 不良廃棄", f"{orders_df[(safe_dt_date(orders_df['納品予定日']) >= this_m) & (orders_df['不良廃棄フラグ']==True)]['ケース数'].apply(to_int).sum():,} cs", delta_color="inverse")
            c3.metric("荷姿チェック率", f"{int(len(orders_df[orders_df['荷姿チェック']==True]) / max(len(orders_df),1)*100)} %")
            c4.metric("現在 欠品品目数", f"{sum(1 for v in current_stocks.values() if v<=0)} 品目", delta_color="inverse")
        else: st.info("受注データがありません。")
        col_a,col_b = st.columns(2)
        with col_a:
            section("🚚 運送会社別 出荷構成")
            if not orders_df.empty:
                ss = orders_df[orders_df["運送会社"].str.strip()!=""]["運送会社"].value_counts().reset_index()
                ss.columns=["運送会社","件数"]
                if not ss.empty: st.plotly_chart(px.pie(ss,names="運送会社",values="件数",hole=0.4,title="運送会社別 出荷件数"), use_container_width=True)
        with col_b:
            section("🏢 顧客別 出荷量 TOP5")
            if not orders_df.empty:
                ca = orders_df[orders_df["顧客名"]!="未指定"].groupby("顧客名")["ケース数"].apply(lambda x: x.apply(to_int).sum()).reset_index().sort_values("ケース数",ascending=False).head(5)
                if not ca.empty: st.plotly_chart(px.bar(ca,x="ケース数",y="顧客名",orientation='h',title="主要顧客 TOP5 出荷量",color="ケース数",color_continuous_scale="Blues"), use_container_width=True)

    with tab_d2:
        section("📦 製品 ABC分析")
        if not orders_df.empty:
            os2 = orders_df[orders_df["不良廃棄フラグ"]==False].copy(); os2["ケース数"] = os2["ケース数"].apply(to_int)
            abc = os2.groupby("製品名")["ケース数"].sum().reset_index().sort_values("ケース数",ascending=False)
            if abc["ケース数"].sum() > 0:
                abc["累計比率"] = abc["ケース数"].cumsum()/abc["ケース数"].sum()*100
                abc["ランク"] = pd.cut(abc["累計比率"],bins=[0,70,90,100],labels=["A（主力）","B（中堅）","C（その他）"])
                fig_abc = px.bar(abc.head(20),x="製品名",y="ケース数",color="ランク",color_discrete_map={"A（主力）":"#DC2626","B（中堅）":"#F59E0B","C（その他）":"#6B7280"},title="製品ABC分析 TOP20")
                fig_abc.update_layout(xaxis_tickangle=-45); st.plotly_chart(fig_abc, use_container_width=True)
                st.dataframe(abc.style.map(lambda v: 'background-color:#FEE2E2;font-weight:900;' if "A" in str(v) else ('background-color:#FEF3C7;' if "B" in str(v) else ''), subset=["ランク"]), use_container_width=True, hide_index=True)
        
    with tab_d3:
        section("🏭 製造効率・実績分析")
        if not manus_df.empty:
            mtm = manus_df[safe_dt_date(manus_df["製造予定日"]) >= date.today().replace(day=1)]
            tm_cs = mtm["ケース数"].apply(to_int).sum(); rp_cs = mtm[mtm["リパックフラグ"]==True]["ケース数"].apply(to_int).sum()
            c1m,c2m = st.columns(2); c1m.metric("今月 製造総数",f"{tm_cs:,} cs"); c2m.metric("今月 リパック",f"{rp_cs:,} cs",delta=f"製造比 {int(rp_cs/max(tm_cs,1)*100)}%")
            st.plotly_chart(px.histogram(manus_df,x="製造予定日",y="ケース数",color="大カテゴリ",title="製造量推移（カテゴリ別）",barmode="stack"), use_container_width=True)
            cat_m2 = manus_df.groupby("大カテゴリ")["ケース数"].apply(lambda x: x.apply(to_int).sum()).reset_index()
            if not cat_m2.empty: st.plotly_chart(px.pie(cat_m2,names="大カテゴリ",values="ケース数",title="カテゴリ別 製造比率",hole=0.4), use_container_width=True)
        st.write("---"); section("📦 資材 消費ペース（発注判断）")
        if pack_summary:
            st.dataframe(pd.DataFrame([{"資材名":k,"現在庫":v["現在庫"],"発注点":v["発注点"],"期間消費":v["期間出庫消費"],"状態":v["状態"]} for k,v in pack_summary.items()]).style.apply(lambda r: ['background-color:#FFEDD5;color:#C2410C;font-weight:bold;']*len(r) if to_int(r.get("現在庫",0)) < to_int(r.get("発注点",0)) else ['']*len(r), axis=1), use_container_width=True, hide_index=True)

    with tab_d4:
        section("📅 月次 出荷トレンド")
        if not orders_df.empty:
            tdf = orders_df[orders_df["不良廃棄フラグ"]==False].copy(); tdf["年月"] = pd.to_datetime(tdf["納品予定日"],errors='coerce').dt.to_period("M").astype(str)
            mon = tdf.groupby(["年月","大カテゴリ"])["ケース数"].apply(lambda x: x.apply(to_int).sum()).reset_index()
            if not mon.empty: st.plotly_chart(px.bar(mon,x="年月",y="ケース数",color="大カテゴリ",title="月次 カテゴリ別 出荷量推移",barmode="stack"), use_container_width=True)
            mon_sum = tdf.groupby("年月").agg(出荷件数=("ID","count"),総CS数=("ケース数",lambda x: x.apply(to_int).sum()),顧客数=("顧客名","nunique")).reset_index()
            st.dataframe(mon_sum, use_container_width=True, hide_index=True)

elif page == "⚙️ マスタ・分析":
    page_header("⚙️ マスタ・データ分析")
    t_m1,t_m2,t_m3,t_m4,t_m5 = st.tabs(["📦 製品マスタ","🏢 顧客マスタ","📦 資材マスタ","🚚 運送会社マスタ","📊 ABC分析"])
    with t_m1:
        em = st.data_editor(master_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"大カテゴリ": st.column_config.SelectboxColumn("大カテゴリ",options=[c.split(" ",1)[1] for c in CATEGORIES],required=True), "製品名": st.column_config.TextColumn("製品名",required=True), "初期在庫数": st.column_config.NumberColumn("初期在庫数",min_value=-9999,step=1,format="%d",default=0,required=True), "使用資材名": st.column_config.SelectboxColumn("使用資材名",options=pack_mst_unique["資材名"].tolist() if not pack_mst_unique.empty else []), "資材使用数": st.column_config.NumberColumn("1csあたりの資材数",min_value=0,step=1,format="%d",default=1), "入数": st.column_config.NumberColumn("入数",min_value=1,step=1,format="%d",default=1), "単位区分": st.column_config.SelectboxColumn("単位区分",options=["ケース","個","本","袋","パック","箱"]), "特注フラグ": st.column_config.CheckboxColumn("⭐ 特注品",default=False), "チャーターフラグ": st.column_config.CheckboxColumn("🚌 チャーター",default=False), "時間あたり生産量": st.column_config.NumberColumn("⏱ 生産量(cs/h)",min_value=0,step=1,format="%d",default=0), "歩留まり率": st.column_config.NumberColumn("📊 歩留まり率(%)",min_value=1,max_value=100,step=1,format="%d",default=95), "リードタイム時間": st.column_config.NumberColumn("⏳ リードタイム(h)",min_value=0,step=1,format="%d",default=0), "安全在庫数": st.column_config.NumberColumn("🛡 安全在庫(cs)",min_value=0,step=1,format="%d",default=0), "段取りグループ": st.column_config.TextColumn("🔧 段取りグループ")}, key="edit_master", height=500)
        if st.button("💾 製品マスタを保存・同期", type="primary", use_container_width=True): save_and_sync("master", em); st.rerun()
    with t_m2:
        ec2 = st.data_editor(cust_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"顧客名": st.column_config.TextColumn("顧客名（旧形式・互換用）"),"ふりがな": st.column_config.TextColumn("ふりがな"),"帳合先": st.column_config.TextColumn("🏢 帳合先（親会社・取引先名）"),"支店名": st.column_config.TextColumn("🏬 支店・店舗名")}, key="edit_cust")
        if st.button("💾 顧客マスタを保存・同期", type="primary", use_container_width=True): save_and_sync("customers", ec2); st.rerun()
    with t_m3:
        ep3 = st.data_editor(pack_mst_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"資材名": st.column_config.TextColumn("資材名", required=True), "品番": st.column_config.TextColumn("品番"), "規格": st.column_config.TextColumn("規格"), "仕入先": st.column_config.TextColumn("仕入先"), "保管場所": st.column_config.TextColumn("保管場所"), "単位": st.column_config.TextColumn("単位"), "初期在庫": st.column_config.NumberColumn("初期在庫", step=1, format="%d", default=0, required=True), "発注点": st.column_config.NumberColumn("発注点（cs）", step=1, format="%d", default=100), "発注リードタイム": st.column_config.NumberColumn("📅 発注リードタイム（日）", min_value=0, max_value=365, step=1, format="%d", default=7)}, key="edit_pack_mst")
        if st.button("💾 資材マスタを保存・同期", type="primary", use_container_width=True): save_and_sync("packaging_master", ep3); st.rerun()
    with t_m4:
        es4 = st.data_editor(ship_mst_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"運送会社名": st.column_config.TextColumn("運送会社名",required=True)}, key="edit_ship_mst")
        if st.button("💾 運送会社マスタを保存・同期", type="primary", use_container_width=True): save_and_sync("shipping_master", es4); st.rerun()

elif page == "🏗️ 製造スケジューラー":
    page_header("🏗️ 製造スケジューラー — 逆算自動計画")
    def get_prod_params(prod_name):
        default = {"時間あたり生産量": 0, "歩留まり率": 95, "リードタイム時間": 0, "安全在庫数": 0, "段取りグループ": ""}
        if master_df_unique.empty or not prod_name: return default
        row = master_df_unique[master_df_unique["製品名"] == prod_name]
        if row.empty: return default
        r = row.iloc[0]
        return {"時間あたり生産量": max(1, to_int(r.get("時間あたり生産量", 0))), "歩留まり率": max(1, min(100, to_int(r.get("歩留まり率", 95)) or 95)), "リードタイム時間": to_int(r.get("リードタイム時間", 0)), "安全在庫数": to_int(r.get("安全在庫数", 0)), "段取りグループ": str(r.get("段取りグループ", "") or "")}

    def calc_schedule_tasks(orders_df, manus_df, current_stocks, future_stocks, master_df_unique, horizon_days=30):
        tasks = []; now = pd.Timestamp.today().normalize()
        if orders_df.empty: return tasks
        future_orders = orders_df[(orders_df["不良廃棄フラグ"] == False) & (pd.to_datetime(orders_df["納品予定日"], errors="coerce") >= now)].copy()
        future_orders["納品予定日"] = pd.to_datetime(future_orders["納品予定日"], errors="coerce")
        future_orders = future_orders.dropna(subset=["納品予定日"]).sort_values("納品予定日")

        for prod_name, grp in future_orders.groupby("製品名"):
            params = get_prod_params(prod_name)
            curr_s = current_stocks.get(prod_name, 0)
            for _, order_row in grp.iterrows():
                ship_date = pd.Timestamp(order_row["納品予定日"]).normalize()
                need_qty = to_int(order_row.get("ケース数", 0))
                shortage = need_qty - max(0, future_stocks.get(prod_name, {}).get(ship_date, curr_s) - params["安全在庫数"])
                if shortage <= 0:
                    tasks.append({"製品名": prod_name, "顧客名": str(order_row.get("顧客名","")), "受注ID": str(order_row.get("ID","")), "出荷日": ship_date, "受注数(cs)": need_qty, "製造必要量(cs)": 0, "製造時間(h)": 0, "製造開始期限": ship_date, "製造終了期限": ship_date, "優先度": 5, "ステータス": "✅ 在庫充足", "備考": f"現在庫{curr_s}cs → 不足なし", "段取りグループ": params["段取りグループ"]})
                    continue
                mfg_qty_cs = int(np.ceil(shortage / (params["歩留まり率"] / 100)))
                mfg_hours = mfg_qty_cs / max(1, params["時間あたり生産量"])
                start_dead = ship_date - timedelta(days=max(1, int(np.ceil((mfg_hours + params["リードタイム時間"]) / 9))))
                days_left = (ship_date - now).days
                prio = 1 if days_left <= 1 else (2 if days_left <= 3 else (3 if days_left <= 7 else (4 if days_left <= 14 else 5)))
                status = "🔴 緊急（今すぐ製造）" if start_dead <= now else ("🟠 要注意（3日以内）" if days_left <= 3 else ("🟡 注意（1週間以内）" if days_left <= 7 else "🟢 計画内"))
                tasks.append({"製品名": prod_name, "顧客名": str(order_row.get("顧客名","")), "受注ID": str(order_row.get("ID","")), "出荷日": ship_date, "受注数(cs)": need_qty, "製造必要量(cs)": mfg_qty_cs, "製造時間(h)": round(mfg_hours, 1), "製造開始期限": start_dead, "製造終了期限": ship_date - timedelta(hours=mfg_hours + params["リードタイム時間"]), "優先度": prio, "ステータス": status, "備考": f"不足{shortage}cs→投入{mfg_qty_cs}cs", "段取りグループ": params["段取りグループ"]})
        
        tasks_need = [t for t in tasks if t["製造必要量(cs)"] > 0]
        tasks_need.sort(key=lambda t: (t["段取りグループ"] or "ZZZ", t["優先度"], t["出荷日"]))
        return tasks_need + [t for t in tasks if t["製造必要量(cs)"] == 0]

    ctrl1, ctrl2, ctrl3, ctrl4 = st.columns([1, 1, 1, 1])
    horizon_days = ctrl1.slider("📅 計画期間（日）", min_value=7, max_value=60, value=30, step=7)
    show_ok = ctrl2.checkbox("✅ 在庫充足品も表示", value=False)
    auto_refresh = ctrl3.button("🔄 スケジュール再計算", type="primary")
    tasks = calc_schedule_tasks(orders_df, manus_df, current_stocks, future_stocks, master_df_unique, horizon_days)
    tasks_need = [t for t in tasks if t["製造必要量(cs)"] > 0]
    display_tasks = tasks if show_ok else tasks_need

    k1,k2,k3,k4 = st.columns(4)
    k1.metric("🔴 緊急タスク", f"{sum(1 for t in tasks_need if t['優先度'] <= 2)} 件", delta_color="inverse")
    k2.metric("🟡 要注意タスク", f"{sum(1 for t in tasks_need if t['優先度'] == 3)} 件", delta_color="inverse")
    k3.metric("📋 製造必要タスク", f"{len(tasks_need)} 件")
    k4.metric("⏱ 総製造時間", f"{sum(t['製造時間(h)'] for t in tasks_need):.1f} h")

    tab_s1, tab_s2, tab_s3, tab_s4 = st.tabs(["📋 タスク一覧＆優先順序", "📊 ガントチャート", "🔧 段取り最適化", "⚙️ 生産性マスタ設定"])

    with tab_s1:
        if not display_tasks: st.success("✅ 計画期間内に製造が必要なタスクはありません。")
        else:
            df_task = pd.DataFrame(display_tasks)
            for dc in ["出荷日","製造開始期限","製造終了期限"]:
                if dc in df_task.columns: df_task[dc] = pd.to_datetime(df_task[dc], errors="coerce").apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "")
            show_cols = [c for c in ["優先度","ステータス","製品名","顧客名","出荷日","受注数(cs)","製造必要量(cs)","製造時間(h)","製造開始期限","段取りグループ","備考"] if c in df_task.columns]
            st.dataframe(df_task[show_cols].style.apply(lambda r: ['background-color:#FEE2E2; font-weight:bold;']*len(r) if r.get("優先度",5) <= 1 else (['background-color:#FFEDD5;']*len(r) if r.get("優先度",5) == 2 else (['background-color:#FFFBEB;']*len(r) if r.get("優先度",5) == 3 else ['']*len(r))), axis=1), use_container_width=True, hide_index=True, height=500)

    with tab_s2:
        if not tasks_need: st.info("製造タスクがありません。")
        else:
            gantt_data = [dict(Task=f"{t['製品名'][:15]}({t['受注数(cs)']}cs)", Start=t["製造開始期限"].strftime("%Y-%m-%d"), Finish=(t["製造開始期限"] + timedelta(hours=t["製造時間(h)"])).strftime("%Y-%m-%d") if (t["製造開始期限"] + timedelta(hours=t["製造時間(h)"])) > t["製造開始期限"] else (t["製造開始期限"] + timedelta(hours=1)).strftime("%Y-%m-%d"), Resource=t["ステータス"], 優先度=str(t["優先度"]), 顧客名=t["顧客名"], 出荷日=t["出荷日"].strftime("%Y/%m/%d"), 必要量=f"{t['製造必要量(cs)']}cs") for t in tasks_need if pd.notnull(t.get("製造開始期限")) and pd.notnull(t.get("出荷日"))]
            if gantt_data:
                fig_gantt = px.timeline(pd.DataFrame(gantt_data), x_start="Start", x_end="Finish", y="Task", color="Resource", color_discrete_map={"🔴 緊急（今すぐ製造）":"#DC2626", "🟠 要注意（3日以内）":"#EA580C", "🟡 注意（1週間以内）":"#D97706", "🟢 計画内":"#059669"}, hover_data=["顧客名","出荷日","必要量"], title="製造タスク ガントチャート")
                fig_gantt.update_yaxes(autorange="reversed")
                fig_gantt.add_vline(x=date.today().strftime("%Y-%m-%d"), line_dash="dash", line_color="#64748B")
                st.plotly_chart(fig_gantt, use_container_width=True)

    with tab_s3:
        if not tasks_need: st.info("製造タスクがありません。")
        else:
            groups = {}; prev_group = None; recommended_order = []; total_time = 0
            for t in tasks_need: groups.setdefault(t["段取りグループ"] or "（グループ未設定）", []).append(t)
            for g_name, g_tasks in groups.items():
                changeover = 30 if prev_group and prev_group != g_name else 0
                for t in sorted(g_tasks, key=lambda t: (t["優先度"], t["出荷日"])):
                    recommended_order.append({"推奨順序": len(recommended_order)+1, "段取りグループ": g_name, "製品名": t["製品名"], "顧客名": t["顧客名"], "製造量(cs)": t["製造必要量(cs)"], "製造時間(h)": t["製造時間(h)"], "段取り替え(分)": changeover, "出荷日": t["出荷日"].strftime("%Y/%m/%d"), "優先度": t["優先度"], "ステータス": t["ステータス"]})
                    total_time += t["製造時間(h)"]; changeover = 0
                prev_group = g_name
            df_order = pd.DataFrame(recommended_order)
            c_s1, c_s2, c_s3 = st.columns(3); c_s1.metric("✅ 最適化後 段取り替え回数", f"{max(0,len(groups)-1)} 回"); c_s2.metric("⏳ 段取り削減時間", f"{(len(tasks_need) - len(groups)) * 30} 分"); c_s3.metric("⏱ 総製造時間（段取除く）", f"{total_time:.1f} h")
            st.dataframe(df_order[["推奨順序","段取りグループ","製品名","顧客名","製造量(cs)","製造時間(h)","段取り替え(分)","出荷日","ステータス"]].style.apply(lambda r: ['background-color:#FEE2E2;']*len(r) if to_int(r.get("優先度",5)) <= 2 else (['background-color:#FFFBEB;']*len(r) if to_int(r.get("優先度",5)) == 3 else ['']*len(r)), axis=1), use_container_width=True, hide_index=True)

    with tab_s4:
        param_cols = [c for c in ["製品名","大カテゴリ","時間あたり生産量","歩留まり率","リードタイム時間","安全在庫数","段取りグループ"] if c in master_df.columns]
        if not master_df.empty and param_cols:
            edited_param = st.data_editor(master_df[param_cols].copy(), use_container_width=True, hide_index=True, column_config={"製品名": st.column_config.TextColumn("製品名", disabled=True), "大カテゴリ": st.column_config.TextColumn("カテゴリ", disabled=True), "時間あたり生産量": st.column_config.NumberColumn("⏱ 生産量(cs/h)",min_value=0,step=1,format="%d"), "歩留まり率": st.column_config.NumberColumn("📊 歩留まり率(%)",min_value=1,max_value=100,step=1,format="%d"), "リードタイム時間": st.column_config.NumberColumn("⏳ リードタイム(h)",min_value=0,step=1,format="%d"), "安全在庫数": st.column_config.NumberColumn("🛡 安全在庫(cs)",min_value=0,step=1,format="%d"), "段取りグループ": st.column_config.TextColumn("🔧 段取りグループ")}, height=500)
            if st.button("💾 生産性パラメータを保存・同期", type="primary", use_container_width=True):
                updated_master = master_df.copy()
                for col in ["時間あたり生産量","歩留まり率","リードタイム時間","安全在庫数","段取りグループ"]:
                    if col in edited_param.columns and col in updated_master.columns: updated_master[col] = edited_param[col].values
                save_and_sync("master", updated_master); st.rerun()
