import os
import io
import math
# テーマ強制設定（視認性固定・文字消失防止）
os.environ["STREAMLIT_THEME_BASE"] = "light"
os.environ["STREAMLIT_THEME_PRIMARY_COLOR"] = "#2563EB"
os.environ["STREAMLIT_THEME_BACKGROUND_COLOR"] = "#F8FAFC"
os.environ["STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR"] = "#F1F5F9"
os.environ["STREAMLIT_THEME_TEXT_COLOR"] = "#0F172A"

import streamlit as st
import pandas as pd
import plotly.express as px
import uuid
from datetime import datetime, timedelta, date, time
import gspread
from google.oauth2.service_account import Credentials

# ─────────────────────────────────────────────
# 0. 絶対安全な数値変換 ＆ 曜日フォーマット
# ─────────────────────────────────────────────
def to_int(v):
    try:
        if isinstance(v, pd.Series): v = v.sum()
        if pd.isna(v) or str(v).strip() == "": return 0
        return int(float(v))
    except: return 0

def to_float(v):
    try:
        if isinstance(v, pd.Series): v = v.sum()
        if pd.isna(v) or str(v).strip() == "": return 0.0
        return float(v)
    except: return 0.0

def format_date_jp(d):
    if pd.isna(d) or d == "": return ""
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    try:
        if isinstance(d, str): d = pd.to_datetime(d.split(" ")[0])
        return f"{d.strftime('%Y/%m/%d')} ({weekdays[d.weekday()]})"
    except: return str(d).split(" ")[0]

# ─────────────────────────────────────────────
# 1. ページ設定 & CSS
# ─────────────────────────────────────────────
st.set_page_config(page_title="丸実屋 次世代生産管理システム", page_icon="🏭", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&display=swap');
    html, body, [data-testid="stAppViewContainer"] { font-family: 'Noto Sans JP', sans-serif !important; font-size: 16px !important; }
    p, span, label, div { color: #0F172A !important; }
    [data-testid="stSidebar"] { background-color: #F8FAFC !important; border-right: 1px solid #E2E8F0; }
    [data-testid="stSidebar"] .stButton > button { height: 45px !important; font-size: 15px !important; border-radius: 8px !important; font-weight: 600 !important; }
    .block-container { padding-top: 1rem !important; }
    .slim-header { background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%); padding: 12px 24px; border-radius: 10px; color: white !important; margin-bottom: 12px; }
    .slim-header h1 { color: white !important; margin: 0 !important; font-size: 20px !important; font-weight: 800 !important; }
    .header-manu { background: linear-gradient(135deg, #064E3B 0%, #10B981 100%); }
    /* 特大カテゴリボタン */
    [data-testid="stPills"] button { padding: 24px 48px !important; font-size: 28px !important; font-weight: 900 !important; border-radius: 16px !important; border: 2px solid #CBD5E1 !important; margin: 10px !important; min-height: 85px !important; }
    [data-testid="stPills"] button span { font-size: 28px !important; font-weight: 900 !important; white-space: nowrap !important; }
    [data-testid="stPills"] button[aria-selected="true"] { background-color: #2563EB !important; color: #FFFFFF !important; box-shadow: 0 6px 15px rgba(37, 99, 235, 0.4) !important; }
    .sched-table { width: 100%; border-collapse: collapse; background: white; font-size: 15px; border-radius: 10px; overflow: hidden; }
    .sched-table th { background: #F8FAFC; padding: 10px; border-bottom: 2px solid #E2E8F0; }
    .sched-table td { padding: 10px; border-bottom: 1px solid #F1F5F9; vertical-align: top; }
</style>
""", unsafe_allow_html=True)

def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.markdown("<div style='text-align:center; margin-top:50px;'><span style='font-size:80px;'>🏭</span><h2 style='color:#1E3A8A;'>丸実屋システム ログイン</h2></div>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            pwd = st.text_input("パスワードを入力", type="password")
            if st.button("ログイン", use_container_width=True, type="primary"):
                if pwd == st.secrets["app_password"]: st.session_state["password_correct"] = True; st.rerun()
                else: st.error("❌ 違います")
        st.stop()
check_password()

# ─────────────────────────────────────────────
# 3. GSpread 同期ロジック (PMS向けマスタ自動拡張)
# ─────────────────────────────────────────────
@st.cache_resource
def get_client():
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

client = get_client()
sheet = client.open_by_url(st.secrets["spreadsheet_url"])

@st.cache_data(ttl=600) # 高速化キャッシュ
def load_data_from_cloud(name):
    # ★ PMS（生産管理）向けの新規シート・列定義を自動追加
    cols_def = {
        "orders": ["ID","納品予定日","顧客名","大カテゴリ","製品名","ケース数","運送会社","備考","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考","不良廃棄フラグ","登録日時"],
        "manufactures": ["ID","製造予定日","大カテゴリ","製品名","ケース数","出来高数","賞味期限","担当者","リパックフラグ","備考","登録日時"],
        "master": ["大カテゴリ","製品名","初期在庫数","使用資材名","資材使用数","入数","安全在庫数","製造ロット数","リードタイム日","バッチ製造時間分","使用設備","特注品"],
        "customers": ["顧客名","ふりがな"],
        "packaging_master": ["資材名","品番","規格","仕入先","保管場所","単位","初期在庫","発注点"],
        "raw_materials": ["原料名","仕入先","単位","初期在庫","発注点","単価"], # 新規: 原料マスタ
        "bom_master": ["製品名","アイテム名","区分","1CS使用量"], # 新規: レシピ(BOM)
        "equipment_master": ["設備名","1日稼働上限時間"], # 新規: 設備マスタ
        "material_logs": ["ID","登録日","アイテム名","区分","処理区分","数量","理由","関連製品名","理論在庫","登録日時"], # 原料・資材統合ログ
        "shipping_master": ["運送会社名"],
        "employees_master": ["従業員名"],
        "labor_logs": ["ID","作業日","従業員名","終業時間","残業時間","作業内容","作業詳細","登録日時"]
    }
    target_cols = cols_def.get(name, [])
    if not target_cols: return pd.DataFrame()
    
    try: ws = sheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=name, rows="1000", cols="30")
        if name == "shipping_master": ws.update(values=[target_cols, ["ヤマト運輸"], ["佐川急便"]], range_name="A1")
        elif name == "equipment_master": ws.update(values=[target_cols, ["第1ライン", "480"], ["第2ライン", "480"]], range_name="A1")
        else: ws.update(values=[target_cols], range_name="A1")
    
    try:
        data = ws.get_all_values()
        if len(data) <= 1: return pd.DataFrame(columns=target_cols)
        df = pd.DataFrame(data[1:], columns=data[0])
        df.columns = df.columns.str.strip().str.replace(' ', '').str.replace('　', '')
        df = df.loc[:, ~df.columns.duplicated()]
        df = df.reindex(columns=target_cols, fill_value="")
        
        # 数値型変換
        num_cols = ["ケース数", "初期在庫数", "資材使用数", "初期在庫", "発注点", "数量", "理論在庫", "入数", "出来高数", "安全在庫数", "製造ロット数", "リードタイム日", "バッチ製造時間分", "1日稼働上限時間"]
        for c in num_cols:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).apply(to_int)
        
        float_cols = ["1CS使用量", "単価", "残業時間"]
        for c in float_cols:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0).apply(to_float)

        date_cols = ["納品予定日", "製造予定日", "登録日", "登録日時", "賞味期限1", "賞味期限2", "賞味期限3", "賞味期限4", "賞味期限5", "賞味期限", "作業日"]
        for c in date_cols:
            if c in df.columns: df[c] = pd.to_datetime(df[c], errors='coerce')
            
        bool_cols = ["荷姿チェック", "不良廃棄フラグ", "リパックフラグ", "特注品"]
        for c in bool_cols:
            if c in df.columns: df[c] = df[c].astype(str).str.upper() == "TRUE"
        return df[target_cols]
    except Exception: return pd.DataFrame(columns=target_cols)

def save_and_sync(name, df):
    try: ws = sheet.worksheet(name)
    except: ws = sheet.add_worksheet(title=name, rows="1000", cols="30")
    ws.clear()
    df_save = df.copy()
    for col in df_save.columns:
        if pd.api.types.is_datetime64_any_dtype(df_save[col]): df_save[col] = df_save[col].dt.strftime('%Y-%m-%d %H:%M:%S').replace('NaT', '')
        elif pd.api.types.is_bool_dtype(df_save[col]): df_save[col] = df_save[col].astype(str).str.upper()
        elif col in ["1CS使用量", "単価", "残業時間"]: df_save[col] = df_save[col].fillna(0.0).apply(to_float).astype(str)
        elif pd.api.types.is_numeric_dtype(df_save[col]): df_save[col] = df_save[col].fillna(0).apply(to_int).astype(str)
        else: df_save[col] = df_save[col].astype(str)
    df_save = df_save.fillna("").replace(["nan", "None", "NaT"], "")
    ws.update(values=[df_save.columns.values.tolist()] + df_save.values.tolist(), range_name='A1')
    st.cache_data.clear()
    st.session_state[f"{name}_df"] = load_data_from_cloud(name)

def append_and_sync(name, new_row_df):
    try: ws = sheet.worksheet(name)
    except: ws = sheet.add_worksheet(title=name, rows="1000", cols="30"); ws.append_row(new_row_df.columns.tolist())
    row_copy = new_row_df.copy()
    existing_cols = pd.DataFrame(ws.get("A1:Z1")).values[0].tolist() if len(ws.get("A1:Z1")) > 0 else []
    for c in row_copy.columns:
        if c not in existing_cols: existing_cols.append(c)
    for c in existing_cols:
        if c not in row_copy.columns: row_copy[c] = ""
    row_copy = row_copy[existing_cols]
    for col in row_copy.columns:
        if pd.api.types.is_datetime64_any_dtype(row_copy[col]): row_copy[col] = row_copy[col].dt.strftime('%Y-%m-%d %H:%M:%S').replace('NaT', '')
        elif pd.api.types.is_bool_dtype(row_copy[col]): row_copy[col] = row_copy[col].astype(str).str.upper()
    row_to_send = row_copy.fillna("").astype(str).replace(["nan", "None", "NaT"], "").values[0].tolist()
    ws.append_row(row_to_send)
    st.cache_data.clear()
    st.session_state[f"{name}_df"] = pd.concat([st.session_state[f"{name}_df"], new_row_df], ignore_index=True)

# ─────────────────────────────────────────────
# セッション初期化
# ─────────────────────────────────────────────
sheet_names = ["orders", "manufactures", "master", "customers", "packaging_master", "raw_materials", "bom_master", "equipment_master", "material_logs", "shipping_master", "employees_master", "labor_logs"]
for sheet_name in sheet_names:
    if f"{sheet_name}_df" not in st.session_state: st.session_state[f"{sheet_name}_df"] = load_data_from_cloud(sheet_name)

if "current_page" not in st.session_state: st.session_state.current_page = "📋 受注登録"

orders_df = st.session_state.orders_df
manus_df = st.session_state.manufactures_df
master_df = st.session_state.master_df
cust_df = st.session_state.customers_df
pack_mst_df = st.session_state.packaging_master_df
raw_mst_df = st.session_state.raw_materials_df
bom_df = st.session_state.bom_master_df
equip_df = st.session_state.equipment_master_df
mat_log_df = st.session_state.material_logs_df
ship_mst_df = st.session_state.shipping_master_df
emp_mst_df = st.session_state.employees_master_df
labor_df = st.session_state.labor_logs_df

CATEGORIES = ["🍝 つきこん", "🟫 平こん", "🍜 糸こん・しらたき", "🔺 三角こん", "🟤 玉こん", "🎲 ダイスこん", "🏷️ 短冊", "🇯🇵 国産", "🤲 ちぎりこん", "🏮 大黒屋", "🏭 かねこ", "🍱 ショクカイ", "❄️ 冷凍耐性", "📦 その他"]
def format_name(n): return f"⚫️ {n}" if "黒" in str(n) else f"⚪️ {n}" if "白" in str(n) else f"📦 {n}"

# ─────────────────────────────────────────────
# 4. 在庫計算エンジン & スケジューラ用データ作成
# ─────────────────────────────────────────────
today = pd.Timestamp.today().normalize()
dates = pd.date_range(today, today + timedelta(days=60))

# --- 製品在庫推移の計算 ---
current_stocks = {}
future_stocks = {}
master_df_unique = master_df.drop_duplicates(subset=["製品名"]) if not master_df.empty else pd.DataFrame(columns=["大カテゴリ","製品名","初期在庫数","使用資材名","資材使用数","安全在庫数","製造ロット数","リードタイム日","バッチ製造時間分","使用設備","特注品"])

if not master_df_unique.empty:
    o_ev = orders_df[["納品予定日", "製品名", "ケース数"]].copy() if not orders_df.empty else pd.DataFrame(columns=["納品予定日", "製品名", "ケース数"])
    if not o_ev.empty:
        o_ev = o_ev.rename(columns={"納品予定日":"日付", "ケース数":"qty"})
        o_ev["qty"] = -pd.to_numeric(o_ev["qty"], errors='coerce').fillna(0).abs()
    m_ev = manus_df[["製造予定日", "製品名", "ケース数"]].copy() if not manus_df.empty else pd.DataFrame(columns=["製造予定日", "製品名", "ケース数"])
    if not m_ev.empty:
        m_ev = m_ev.rename(columns={"製造予定日":"日付", "ケース数":"qty"})
        m_ev["qty"] = pd.to_numeric(m_ev["qty"], errors='coerce').fillna(0).abs()
        
    all_ev = pd.concat([o_ev, m_ev]).dropna(subset=["製品名", "日付"])
    all_ev["qty"] = all_ev["qty"].apply(to_int)
    
    past_ev = all_ev[all_ev["日付"] < today].groupby("製品名")["qty"].sum()
    future_ev = all_ev[all_ev["日付"] >= today]
    pivot_ev = future_ev.pivot_table(index="製品名", columns="日付", values="qty", aggfunc="sum") if not future_ev.empty else pd.DataFrame()
    
    for _, r in master_df_unique.iterrows():
        p = r["製品名"]
        curr_stock = to_int(r.get("初期在庫数", 0)) + to_int(past_ev.get(p, 0))
        current_stocks[p] = curr_stock
        p_future_row = pivot_ev.loc[p] if p in pivot_ev.index else pd.Series(0, index=dates)
        if isinstance(p_future_row, pd.DataFrame): p_future_row = p_future_row.sum(axis=0)
        p_future_cumsum = p_future_row.reindex(dates, fill_value=0).fillna(0).cumsum()
        future_stocks[p] = {d: curr_stock + to_int(p_future_cumsum.get(d, 0)) for d in dates}

# --- 原料・資材（統合）サマリの計算 ---
mat_summary = {}

# 資材マスタ登録
if not pack_mst_df.empty:
    for _, r in pack_mst_df.drop_duplicates(subset=["資材名"]).iterrows():
        mat_summary[r["資材名"]] = {"区分": "資材", "期首在庫": to_int(r.get("初期在庫", 0)), "発注点": to_int(r.get("発注点", 0)), "期間入庫累計": 0, "期間出庫消費": 0, "現在庫": 0}
# 原料マスタ登録
if not raw_mst_df.empty:
    for _, r in raw_mst_df.drop_duplicates(subset=["原料名"]).iterrows():
        mat_summary[r["原料名"]] = {"区分": "原料", "期首在庫": to_int(r.get("初期在庫", 0)), "発注点": to_int(r.get("発注点", 0)), "期間入庫累計": 0, "期間出庫消費": 0, "現在庫": 0}

# ログからの増減
if not mat_log_df.empty:
    for _, r in mat_log_df.iterrows():
        m_name, qty, m_type = r.get("アイテム名", ""), to_float(r.get("数量", 0)), str(r.get("処理区分", ""))
        if m_name in mat_summary:
            if "連動" in m_type: continue # 二重計算防止
            if "入庫" in m_type: mat_summary[m_name]["期間入庫累計"] += qty
            elif "出庫" in m_type: mat_summary[m_name]["期間出庫消費"] += qty

# ★ BOM（レシピ）および製品マスタに基づく「製造時」の自動引き落とし
if not manus_df.empty and not master_df_unique.empty:
    # 1. 古い資材連動ロジック（後方互換）
    master_pack_info = master_df_unique.set_index("製品名")[["使用資材名", "資材使用数"]].to_dict('index')
    # 2. 新しいBOMロジック
    bom_info = {}
    if not bom_df.empty:
        for p, group in bom_df.groupby("製品名"):
            bom_info[p] = group[["アイテム名", "1CS使用量"]].to_dict('records')

    for _, r in manus_df.iterrows():
        prod, qty, rem = str(r.get("製品名", "")), to_int(r.get("ケース数", 0)), str(r.get("備考", ""))
        if "【資材非連動】" in rem: continue
        
        # BOMに登録があればBOMから引く
        if prod in bom_info:
            for item in bom_info[prod]:
                i_name = item["アイテム名"]
                i_usage = to_float(item["1CS使用量"])
                if i_name in mat_summary:
                    mat_summary[i_name]["期間出庫消費"] += (qty * i_usage)
        # BOMが無く、古いマスタ設定があればそちらから引く
        elif prod in master_pack_info:
            p_name = master_pack_info[prod].get("使用資材名", "")
            p_usage = to_int(master_pack_info[prod].get("資材使用数", 0))
            if p_name and p_usage > 0 and p_name in mat_summary:
                mat_summary[p_name]["期間出庫消費"] += (qty * p_usage)

for d in mat_summary.values():
    d["現在庫"] = d["期首在庫"] + d["期間入庫累計"] - d["期間出庫消費"]
    d["状態"] = "⚠️ 注意" if d["現在庫"] < d["発注点"] else "✅ 正常"

# ─────────────────────────────────────────────
# ★ AI自動生産スケジューラ エンジン
# ─────────────────────────────────────────────
proposed_schedules = []
if not master_df_unique.empty:
    # 仮想的に在庫を回復させてシミュレーションする用
    sim_stocks = {p: {d: future_stocks[p][d] for d in dates} for p in master_df_unique["製品名"]}
    
    for _, r in master_df_unique.iterrows():
        p = r["製品名"]
        safe_stock = to_int(r.get("安全在庫数", 0))
        lot_size = to_int(r.get("製造ロット数", 0))
        lead_time = to_int(r.get("リードタイム日", 0))
        equip = str(r.get("使用設備", ""))
        make_time = to_int(r.get("バッチ製造時間分", 0))
        
        if safe_stock > 0 and lot_size > 0:
            for d in dates:
                if sim_stocks[p][d] < safe_stock:
                    shortage = safe_stock - sim_stocks[p][d]
                    lots = math.ceil(shortage / lot_size)
                    plan_qty = lots * lot_size
                    plan_date = d - timedelta(days=lead_time)
                    if plan_date < today: plan_date = today # 過去は今日に丸める
                    
                    proposed_schedules.append({
                        "製造予定日": plan_date.strftime("%Y-%m-%d"), "大カテゴリ": r["大カテゴリ"], "製品名": p, "ケース数": plan_qty, 
                        "使用設備": equip, "想定所要時間(分)": lots * make_time, "理由": f"{d.strftime('%m/%d')}の在庫不足({sim_stocks[p][d]}cs)"
                    })
                    # 以降の仮想在庫を回復させる（二重提案防止）
                    for fd in pd.date_range(plan_date + timedelta(days=lead_time), dates[-1]):
                        sim_stocks[p][fd] += plan_qty

# ─────────────────────────────────────────────
# 5. サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<p style='font-size:20px; font-weight:900; color:#1E3A8A; margin-bottom:20px;'>🏭 丸実屋システム</p>", unsafe_allow_html=True)
    st.write("---")
    menu_items = ["📋 受注登録", "🏭 製造・日報登録", "🚚 出荷・特注品管理", "📦 資材・原料管理", "🤖 自動生産スケジューラ", "📊 在庫・カレンダー", "⚙️ マスタ・分析"]
    for item in menu_items:
        if st.button(item, key=f"menu_{item}", use_container_width=True, type="primary" if st.session_state.current_page == item else "secondary"):
            st.session_state.current_page = item; st.rerun()
page = st.session_state.current_page

# ─────────────────────────────────────────────
# 6. 画面描画
# ─────────────────────────────────────────────

# --- 📋 受注登録 ---
if page == "📋 受注登録":
    st.markdown('<div class="slim-header"><h1>📋 受注 登録</h1></div>', unsafe_allow_html=True)
    with st.container():
        c1, c2, c3 = st.columns([1, 2, 1])
        o_date = c1.date_input("📅 納品日", value=date.today() + timedelta(days=1))
        c_name = c2.selectbox("🏢 顧客名", options=sorted(cust_df["顧客名"].unique()) if not cust_df.empty else [], index=None, placeholder="検索...")
        qty = c3.number_input("📦 ケース数 (正の数)", min_value=1, step=1, format="%d", value=None)
        
        cat_full = st.pills("カテゴリ", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
        cat = cat_full.split(" ", 1)[1] if cat_full else CATEGORIES[0].split(" ", 1)[1]
        sc1, sc2 = st.columns([1.5, 2.5])
        search_p = sc1.text_input("🔍 製品検索", placeholder="名称の一部を入力...")
        prods = [p for p in master_df_unique["製品名"].tolist() if search_p in p] if search_p else (master_df_unique[master_df_unique["大カテゴリ"] == cat]["製品名"].tolist() if not master_df_unique.empty else [])
        prod = sc2.selectbox("確定製品", options=prods, index=None, placeholder="選択してください", format_func=format_name)
        
        r1, r2 = sc2.columns([1, 2])
        ship_list = ship_mst_df["運送会社名"].tolist() if not ship_mst_df.empty else []
        ship_comp = r1.selectbox("🚚 運送会社", options=ship_list, index=None, placeholder="未定")
        rem = r2.text_input("📝 備考")
        
        col_chk1, col_chk2 = sc2.columns(2)
        is_substitute = col_chk1.checkbox("🔄 代替品として送付")
        is_irregular = col_chk2.checkbox("⚠️ 水漏れ・イレギュラーによる在庫減 (不良廃棄)")
        st.write("---")

        if prod and qty is not None and qty > 0:
            cur_stock = current_stocks.get(prod, 0)
            if cur_stock < qty:
                st.markdown(f"""
                <div style='background-color:#FEE2E2; padding:15px; border-radius:10px; border:2px solid #FCA5A5; color:#DC2626; font-size:18px;'>
                    🚨 <b>製品在庫が不足します！</b> （現在庫: <b>{cur_stock}</b> cs / <span style='font-size:1.2em; font-weight:900; color:#FF0000;'>不足分: -{qty - cur_stock} cs</span>）
                </div>
                """, unsafe_allow_html=True)
                st.write("")

        msg_slot_add = st.empty()
        if st.button("✅ 登録する", type="primary", use_container_width=True):
            if not prod or qty is None: msg_slot_add.error("⚠️ 【製品・ケース数】は必須です。")
            else:
                prefix = ""
                if is_substitute: prefix += "【代替品】"
                if is_irregular: prefix += "【不良廃棄】"
                
                new_row = pd.DataFrame([{
                    "ID": str(uuid.uuid4())[:6].upper(), "納品予定日": pd.to_datetime(o_date), "顧客名": c_name if c_name else "未指定",
                    "大カテゴリ": cat, "製品名": prod, "ケース数": to_int(qty), "運送会社": ship_comp if ship_comp else "", 
                    "備考": f"{prefix} {rem}".strip(), "荷姿チェック": False, "賞味期限1": "", "賞味期限2": "", "賞味期限3": "", "賞味期限4": "", "賞味期限5": "", "発送備考": "",
                    "不良廃棄フラグ": is_irregular, "登録日時": datetime.now()
                }])
                append_and_sync("orders", new_row)
                st.toast(f"✨ 登録を完了しました: {prod} ({qty}cs)", icon="✅")
                st.rerun()

    st.markdown('<h2 style="font-size:18px; margin-top:30px;">✏️ 登録データのかんたん修正・削除</h2>', unsafe_allow_html=True)
    if not orders_df.empty:
        disp_orders = orders_df.sort_values("登録日時", ascending=False).copy()
        disp_orders["納品予定日(表示)"] = disp_orders["納品予定日"].apply(format_date_jp)
        disp_cols = ["ID", "納品予定日(表示)", "顧客名", "製品名", "ケース数", "運送会社", "備考", "不良廃棄フラグ"]
        
        recent = disp_orders.head(5).copy()
        edited = st.data_editor(
            recent[disp_cols], num_rows="dynamic", use_container_width=True, hide_index=True, 
            column_config={"ケース数": st.column_config.NumberColumn("ケース数", min_value=1, step=1, format="%d"), "ID": None}, 
            key="edit_o"
        )
        if st.button("💾 直近データを修正・削除保存", key="btn_edit_o"):
            save_df = edited.copy()
            save_df["納品予定日"] = pd.to_datetime(save_df["納品予定日(表示)"].str.split(" ").str[0], errors="coerce")
            merged_df = pd.merge(save_df, orders_df[["ID", "大カテゴリ", "荷姿チェック", "賞味期限1", "賞味期限2", "賞味期限3", "賞味期限4", "賞味期限5", "発送備考", "登録日時"]], on="ID", how="left")
            save_and_sync("orders", pd.concat([orders_df[~orders_df["ID"].isin(recent["ID"])], merged_df], ignore_index=True))
            st.toast("✅ 受注データの修正を保存しました")
            st.rerun()
            
        with st.expander("📂 過去の全データを一括編集・削除（クリックで拡大展開）"):
            st.info("💡 **操作方法:** セルをクリックして直接文字や数字を打ち変えられます。左端のチェックボックスを選択してキーボードの「Delete」を押すと行（データ）の削除が可能です。")
            edited_all = st.data_editor(
                disp_orders[disp_cols], num_rows="dynamic", use_container_width=True, hide_index=True, 
                column_config={"ケース数": st.column_config.NumberColumn("ケース数", min_value=1, step=1, format="%d"), "ID": None}, 
                key="edit_all_o", height=400
            )
            if st.button("💾 全データを上書き保存", key="btn_edit_all_o"):
                save_df_all = edited_all.copy()
                save_df_all["納品予定日"] = pd.to_datetime(save_df_all["納品予定日(表示)"].str.split(" ").str[0], errors="coerce")
                merged_all = pd.merge(save_df_all, orders_df[["ID", "大カテゴリ", "荷姿チェック", "賞味期限1", "賞味期限2", "賞味期限3", "賞味期限4", "賞味期限5", "発送備考", "登録日時"]], on="ID", how="left")
                save_and_sync("orders", merged_all)
                st.toast("✅ 全データの更新・削除を完了しました")
                st.rerun()

# --- 🏭 製造・日報登録 ---
elif page == "🏭 製造・日報登録":
    st.markdown('<div class="slim-header header-manu"><h1>🏭 製造・リパック・日報登録</h1></div>', unsafe_allow_html=True)
    t_m1, t_m2, t_m3 = st.tabs(["🏭 製造・リパック登録", "👷 労務データ登録", "📄 生産日報出力"])
    
    with t_m1:
        with st.container():
            c1, c2, c3 = st.columns([1, 1, 1])
            m_date = c1.date_input("📅 製造日", value=st.session_state.get("m_last_date", date.today()))
            m_exp = c2.date_input("📅 賞味期限", value=st.session_state.get("m_last_exp", date.today() + timedelta(days=7)))
            emp_list = emp_mst_df["従業員名"].tolist() if not emp_mst_df.empty else []
            m_worker = c3.selectbox("👷 担当者", options=emp_list, index=emp_list.index(st.session_state.m_last_worker) if st.session_state.get("m_last_worker") in emp_list else None)
            
            cat_full_m = st.pills("カテゴリ製造", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
            cat_m = cat_full_m.split(" ", 1)[1] if cat_full_m else CATEGORIES[0].split(" ", 1)[1]
            
            sc1_m, sc2_m, sc3_m = st.columns([1.5, 2.5, 1])
            search_p_m = sc1_m.text_input("🔍 製品名検索", placeholder="検索...", key="sm")
            prods_m = [p for p in master_df_unique["製品名"].tolist() if search_p_m in p] if search_p_m else (master_df_unique[master_df_unique["大カテゴリ"] == cat_m]["製品名"].tolist() if not master_df_unique.empty else [])
            prod_m = sc2_m.selectbox("確定製品", options=prods_m, index=None, format_func=format_name, key="selm")
            m_qty = sc3_m.number_input("📦 CS数 (箱数)", min_value=1, step=1, format="%d", value=None)
            
            dekidaka = 0
            if prod_m and m_qty:
                master_info = master_df_unique[master_df_unique["製品名"] == prod_m]
                irisuu = to_int(master_info["入数"].iloc[0]) if not master_info.empty else 0
                dekidaka = to_int(m_qty) * irisuu
                st.info(f"💡 **自動計算**: {prod_m} (入数: {irisuu}個) × {m_qty}CS = 出来高 **{dekidaka}** 個")
                
            r1, r2 = st.columns(2)
            is_repack = r1.checkbox("🔄 リパック製造 (在庫加算)")
            is_pack_link = r2.checkbox("📦 製造と同時に、レシピ(BOM)から原料・資材の在庫を自動で減らす", value=True)
            st.write("---")

            # ★ 原料・資材不足アラート（BOM対応）
            if prod_m and m_qty is not None and m_qty > 0 and is_pack_link:
                bom_info = {}
                if not bom_df.empty:
                    for _, r in bom_df[bom_df["製品名"] == prod_m].iterrows():
                        bom_info[r["アイテム名"]] = to_float(r["1CS使用量"])
                if not bom_info: # BOMがなければ旧マスタから取得
                    m_info = master_df_unique[master_df_unique["製品名"] == prod_m]
                    if not m_info.empty and m_info["使用資材名"].iloc[0]:
                        bom_info[m_info["使用資材名"].iloc[0]] = to_float(m_info["資材使用数"].iloc[0])
                
                shortages = []
                for i_name, usage in bom_info.items():
                    req_qty = m_qty * usage
                    cur_stock = mat_summary.get(i_name, {}).get("現在庫", 0)
                    if cur_stock < req_qty:
                        shortages.append(f"・{i_name} （現在庫: {cur_stock} / 不足分: -{req_qty - cur_stock}）")
                
                if shortages:
                    st.markdown(f"<div style='background-color:#FEE2E2; padding:12px; border-radius:8px; border:1px solid #FCA5A5; color:#DC2626; font-size:16px;'>🚨 <b>原料・資材が不足します！</b><br>" + "<br>".join(shortages) + "</div>", unsafe_allow_html=True)
                    st.write("")

            msg_slot_m_add = st.empty()
            if st.button("➕ 製造データを記録する", type="primary", use_container_width=True):
                if not prod_m or m_qty is None or not m_worker: 
                    msg_slot_m_add.error("⚠️ 【製品】【CS数】【担当者】は必須です。")
                else:
                    st.session_state.m_last_date = m_date
                    st.session_state.m_last_exp = m_exp
                    st.session_state.m_last_worker = m_worker
                    
                    rem = "【資材非連動】" if not is_pack_link else ""
                    new_m_id = str(uuid.uuid4())[:6].upper()
                    new_row = pd.DataFrame([{
                        "ID": new_m_id, "製造予定日": pd.to_datetime(m_date), "大カテゴリ": cat_m, "製品名": prod_m, "ケース数": to_int(m_qty), 
                        "出来高数": dekidaka, "賞味期限": pd.to_datetime(m_exp), "担当者": m_worker, "リパックフラグ": is_repack, "備考": rem, "登録日時": datetime.now()
                    }])
                    append_and_sync("manufactures", new_row)
                    
                    # BOM連動自動引き落とし
                    if is_pack_link:
                        logs_to_add = []
                        bom_info = {}
                        if not bom_df.empty:
                            for _, r in bom_df[bom_df["製品名"] == prod_m].iterrows():
                                bom_info[r["アイテム名"]] = {"区分": r["区分"], "使用量": to_float(r["1CS使用量"])}
                        if not bom_info:
                            m_info = master_df_unique[master_df_unique["製品名"] == prod_m]
                            if not m_info.empty and m_info["使用資材名"].iloc[0]:
                                bom_info[m_info["使用資材名"].iloc[0]] = {"区分": "資材", "使用量": to_float(m_info["資材使用数"].iloc[0])}
                        
                        for i_name, i_data in bom_info.items():
                            used_qty = to_float(m_qty) * i_data["使用量"]
                            if used_qty > 0:
                                t_stock = mat_summary.get(i_name, {}).get("現在庫", 0) - used_qty
                                logs_to_add.append({
                                    "ID": str(uuid.uuid4())[:6].upper(), "登録日": pd.to_datetime(m_date), "アイテム名": i_name, "区分": i_data["区分"],
                                    "処理区分": "製造連動", "数量": abs(used_qty), "理由": f"製造ID:{new_m_id}", "関連製品名": prod_m, "理論在庫": t_stock, "備考": "BOM自動引落", "登録日時": datetime.now()
                                })
                        if logs_to_add:
                            append_and_sync("material_logs", pd.DataFrame(logs_to_add))
                    
                    st.toast(f"✨ 製造登録を完了しました: {prod_m}", icon="✅")
                    st.rerun()

        st.markdown('<h2 style="font-size:18px; margin-top:20px;">✏️ かんたん修正（直近5件）</h2>', unsafe_allow_html=True)
        if not manus_df.empty:
            recent_m = manus_df.sort_values("登録日時", ascending=False).head(5).copy()
            recent_m["製造予定日(表示)"] = recent_m["製造予定日"].apply(format_date_jp)
            disp_cols = ["ID", "製造予定日(表示)", "製品名", "ケース数", "出来高数", "担当者", "リパックフラグ"]
            edited_m = st.data_editor(recent_m[disp_cols], num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"ケース数": st.column_config.NumberColumn("CS数", step=1, format="%d"), "出来高数": st.column_config.NumberColumn("出来高", step=1, format="%d"), "ID": None}, key="edit_m")
            if st.button("💾 直近データを修正・削除保存", key="smb"):
                save_df_m = edited_m.copy()
                save_df_m["製造予定日"] = pd.to_datetime(save_df_m["製造予定日(表示)"].str.split(" ").str[0], errors="coerce")
                merged_m = pd.merge(save_df_m, manus_df[["ID", "大カテゴリ", "賞味期限", "備考", "登録日時"]], on="ID", how="left")
                save_and_sync("manufactures", pd.concat([manus_df[~manus_df["ID"].isin(recent_m["ID"])], merged_m], ignore_index=True))
                st.toast("✅ 製造データの修正を保存しました"); st.rerun()

    with t_m2:
        st.markdown("### 👷 労務・作業内容の登録")
        l1, l2 = st.columns(2)
        l_date = l1.date_input("📅 作業日", value=date.today())
        l_worker = l2.selectbox("👷 担当者 (労務)", options=emp_list, index=emp_list.index(st.session_state.get("m_last_worker")) if st.session_state.get("m_last_worker") in emp_list else None)
        
        t_l1, t_l2 = st.columns(2)
        l_end_time = t_l1.time_input("🕒 終業時間", value=time(17, 30))
        l_overtime = t_l2.number_input("⏱️ 残業時間 (H)", min_value=0.0, step=0.5, value=0.0)
        l_task = st.selectbox("📋 作業内容 (メイン)", options=["OKM", "プラント", "箱詰め", "バケット", "5S", "その他"])
        l_detail = st.text_input("📝 作業詳細・連絡事項")
        
        if st.button("✅ 労務データを記録する", type="primary", use_container_width=True):
            if not l_worker: st.error("⚠️ 担当者を選択してください。")
            else:
                new_labor = pd.DataFrame([{"ID": str(uuid.uuid4())[:6].upper(), "作業日": pd.to_datetime(l_date), "従業員名": l_worker, "終業時間": l_end_time.strftime("%H:%M"), "残業時間": l_overtime, "作業内容": l_task, "作業詳細": l_detail, "登録日時": datetime.now()}])
                append_and_sync("labor_logs", new_labor)
                st.toast(f"✨ 労務データを登録しました: {l_worker}", icon="✅")
                st.rerun()

    with t_m3:
        st.markdown("### 📄 生産日報の作成・出力")
        st.info("💡 指定した日付の「製造実績」と「労務実績」をまとめ、Excelファイルとしてダウンロードできます。")
        report_date = st.date_input("📅 日報の対象日を選択", value=date.today())
        
        target_m = manus_df[manus_df["製造予定日"].dt.date == report_date].copy() if not manus_df.empty else pd.DataFrame()
        target_l = labor_df[labor_df["作業日"].dt.date == report_date].copy() if not labor_df.empty else pd.DataFrame()
        
        st.write(f"**対象日の実績:** 製造 {len(target_m)} 件 / 労務 {len(target_l)} 件")
        
        if st.button("📥 生産日報 (Excel) をダウンロード", type="primary", use_container_width=True):
            if target_m.empty and target_l.empty:
                st.warning("対象日のデータがありません。")
            else:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    if not target_m.empty:
                        out_m = target_m[["製品名", "ケース数", "出来高数", "賞味期限", "担当者", "リパックフラグ", "備考"]].copy()
                        out_m["賞味期限"] = out_m["賞味期限"].dt.strftime("%Y/%m/%d")
                        out_m.to_excel(writer, sheet_name="製造実績", index=False)
                    else: pd.DataFrame({"メッセージ":["製造データなし"]}).to_excel(writer, sheet_name="製造実績", index=False)
                    
                    if not target_l.empty:
                        out_l = target_l[["従業員名", "終業時間", "残業時間", "作業内容", "作業詳細"]].copy()
                        out_l.to_excel(writer, sheet_name="労務実績", index=False)
                    else: pd.DataFrame({"メッセージ":["労務データなし"]}).to_excel(writer, sheet_name="労務実績", index=False)
                st.download_button(label="ここをクリックして保存", data=output.getvalue(), file_name=f"生産日報_{report_date}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

# --- 🚚 出荷・特注品管理 ---
elif page == "🚚 出荷・特注品管理":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #047857 0%, #10B981 100%);"><h1>🚚 出荷・発送 ＆ 特注品管理</h1></div>', unsafe_allow_html=True)
    t_ship1, t_ship2 = st.tabs(["📅 日別 出荷・消込", "⭐ 特注品スケジュール管理"])
    
    with t_ship1:
        st.markdown("💡 その日の出荷予定に対して、**運送会社の変更**、**賞味期限（最大5つ）の記録**、**荷姿確認の消込（チェック）** が行えます。")
        target_date = st.date_input("📅 表示する納品予定日を選択", value=date.today())
        day_orders = orders_df[(orders_df["納品予定日"].dt.date == target_date) & (orders_df["不良廃棄フラグ"] == False)].copy()
        
        if day_orders.empty: st.info(f"{format_date_jp(target_date)} の出荷予定データはありません。")
        else:
            unprocessed = day_orders[day_orders["荷姿チェック"] == False]
            if not unprocessed.empty and target_date <= date.today():
                st.error(f"🚨 **本日の出荷漏れ（荷姿未チェック）が {len(unprocessed)} 件あります！**")

            edit_cols = ["ID", "顧客名", "製品名", "ケース数", "運送会社", "荷姿チェック", "賞味期限1", "賞味期限2", "賞味期限3", "賞味期限4", "賞味期限5", "発送備考"]
            disp_df = day_orders[edit_cols].copy()
            for c in ["賞味期限1", "賞味期限2", "賞味期限3", "賞味期限4", "賞味期限5"]: disp_df[c] = pd.to_datetime(disp_df[c], errors="coerce").dt.date
                
            def highlight_shipped(row):
                if str(row.get("荷姿チェック", False)).upper() == "TRUE": return ['background-color: #D1FAE5; color: #065F46; text-decoration: line-through;'] * len(row)
                return [''] * len(row)
                
            edited_ship = st.data_editor(disp_df.style.apply(highlight_shipped, axis=1), use_container_width=True, hide_index=True, column_config={"ID": None, "顧客名": st.column_config.TextColumn("顧客名", disabled=True), "製品名": st.column_config.TextColumn("製品名", disabled=True), "ケース数": st.column_config.NumberColumn("ケース数", disabled=True), "運送会社": st.column_config.SelectboxColumn("運送会社", options=ship_mst_df["運送会社名"].tolist() if not ship_mst_df.empty else []), "荷姿チェック": st.column_config.CheckboxColumn("✅ 荷姿", default=False), "賞味期限1": st.column_config.DateColumn("賞味1", format="YYYY-MM-DD"), "賞味期限2": st.column_config.DateColumn("賞味2", format="YYYY-MM-DD"), "賞味期限3": st.column_config.DateColumn("賞味3", format="YYYY-MM-DD"), "賞味期限4": st.column_config.DateColumn("賞味4", format="YYYY-MM-DD"), "賞味期限5": st.column_config.DateColumn("賞味5", format="YYYY-MM-DD"), "発送備考": st.column_config.TextColumn("発送備考")}, key="edit_shipping")
            
            if st.button("💾 発送・消込データを保存", type="primary", use_container_width=True):
                updated_orders = orders_df.copy().astype(object)
                for idx, row in edited_ship.iterrows():
                    row_mask = updated_orders["ID"] == row["ID"]
                    if row_mask.any():
                        updated_orders.loc[row_mask, "運送会社"] = str(row.get("運送会社", ""))
                        updated_orders.loc[row_mask, "荷姿チェック"] = str(row.get("荷姿チェック", False)).upper()
                        for c in ["賞味期限1", "賞味期限2", "賞味期限3", "賞味期限4", "賞味期限5"]:
                            val = row.get(c)
                            updated_orders.loc[row_mask, c] = val.strftime("%Y-%m-%d") if pd.notnull(val) else ""
                        updated_orders.loc[row_mask, "発送備考"] = str(row.get("発送備考", ""))
                save_and_sync("orders", updated_orders)
                st.toast("✅ 発送・消込データを保存しました！", icon="✅")
                st.rerun()

    with t_ship2:
        st.markdown("### ⭐ 特注製品の出荷スケジュール一括管理")
        tokuchu_prods = master_df_unique[master_df_unique["特注品"] == True]["製品名"].tolist() if not master_df_unique.empty else []
        
        if not tokuchu_prods: st.info("マスタに「特注品」として設定されている製品がありません。マスタ管理画面から設定してください。")
        else:
            tokuchu_orders = orders_df[(orders_df["製品名"].isin(tokuchu_prods)) & (orders_df["納品予定日"] >= pd.Timestamp(today)) & (orders_df["不良廃棄フラグ"] == False)].copy()
            if tokuchu_orders.empty: st.info("今後の特注品の出荷予定はありません。")
            else:
                tokuchu_orders = tokuchu_orders.sort_values("納品予定日")
                disp_t = tokuchu_orders[["ID", "納品予定日", "顧客名", "製品名", "ケース数", "備考"]].copy()
                disp_t["納品予定日"] = disp_t["納品予定日"].dt.date
                
                st.info("💡 日付やケース数、備考を直接編集して保存できます。")
                edited_t = st.data_editor(disp_t, use_container_width=True, hide_index=True, column_config={"ID": None, "納品予定日": st.column_config.DateColumn("納品予定日", format="YYYY-MM-DD"), "顧客名": st.column_config.TextColumn("顧客名", disabled=True), "製品名": st.column_config.TextColumn("製品名", disabled=True), "ケース数": st.column_config.NumberColumn("ケース数", min_value=1, step=1, format="%d"), "備考": st.column_config.TextColumn("備考")}, key="edit_tokuchu")
                if st.button("💾 特注品の変更を保存", type="primary"):
                    updated_orders = orders_df.copy().astype(object)
                    for idx, row in edited_t.iterrows():
                        row_mask = updated_orders["ID"] == row["ID"]
                        if row_mask.any():
                            updated_orders.loc[row_mask, "納品予定日"] = pd.to_datetime(row["納品予定日"])
                            updated_orders.loc[row_mask, "ケース数"] = to_int(row["ケース数"])
                            updated_orders.loc[row_mask, "備考"] = str(row.get("備考", ""))
                    save_and_sync("orders", updated_orders)
                    st.toast("✅ 特注品のスケジュールを更新しました！", icon="✅")
                    st.rerun()

# --- 📦 資材・原料管理 ---
elif page == "📦 資材・原料管理":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #B45309 0%, #D97706 100%);"><h1>📦 資材・原料 統合管理</h1></div>', unsafe_allow_html=True)
    
    shortage_packs = [p_name for p_name, d in mat_summary.items() if d["現在庫"] < d["発注点"]]
    if shortage_packs:
        st.error(f"🚨 **要発注アラート（現在庫が発注点未満）:**\n\n" + "、".join(shortage_packs))
        st.write("---")

    t_p1, t_p2, t_p3 = st.tabs(["📊 状況サマリ＆分析", "📝 単体入出庫・棚卸", "✏️ 履歴・かんたん修正"])

    with t_p1:
        st.markdown("### 📊 資材・原料の在庫推移サマリ")
        if not mat_summary: st.info("⚙️ マスタ管理から資材・原料を登録してください。")
        else:
            df_pack = pd.DataFrame([{"アイテム名": k, **v} for k, v in mat_summary.items()])
            def highlight_pack(row):
                if to_int(row.get("現在庫",0)) < to_int(row.get("発注点",0)): return ['background-color: #FFEDD5; color: #C2410C; font-weight: bold;'] * len(row)
                return [''] * len(row)
            display_cols = ["アイテム名", "区分", "品番", "規格", "仕入先", "保管場所", "現在庫", "発注点", "状態", "単位"]
            out_pack_df = df_pack[[c for c in display_cols if c in df_pack.columns]]
            st.download_button("📥 サマリをCSV出力", data=out_pack_df.to_csv(index=False, encoding="utf-8-sig"), file_name=f"資材原料状況_{date.today()}.csv", use_container_width=True)
            st.dataframe(out_pack_df.style.apply(highlight_pack, axis=1), use_container_width=True, hide_index=True)

    with t_p2:
        st.markdown("### 📝 単体入出庫・棚卸調整")
        p_date = st.date_input("📅 処理日", value=date.today())
        sc1, sc2 = st.columns([1.5, 2.5])
        search_pack = sc1.text_input("🔍 アイテム名検索", placeholder="検索...")
        all_items = list(mat_summary.keys())
        filtered_packs = [p for p in all_items if search_pack in p] if search_pack else all_items
        sel_pack = sc2.selectbox("📦 対象アイテム", options=filtered_packs, index=None, placeholder="選択してください")
        
        p_type = st.radio("処理区分", options=["📥 入庫 (在庫を増やす)", "📤 出庫・廃棄 (在庫を減らす)", "📋 棚卸 (現在の実在庫を入力)"], horizontal=True)
        
        if "棚卸" in p_type:
            p_qty = st.number_input("現在の実在庫数 (正の数)", min_value=0.0, step=1.0, value=None)
            reason_options = ["棚卸調整"]
        else:
            p_qty = st.number_input("処理する数量 (常に正の数で入力)", min_value=0.1, step=1.0, value=None)
            reason_options = ["仕入（購入）", "返品受付", "その他入庫"] if "入庫" in p_type else ["破損・廃棄", "サンプル出荷", "その他出庫"]
            
        p_reason = st.selectbox("詳細な理由", options=reason_options)
        p_rem = st.text_input("📝 備考")
        
        if st.button("➕ ログを登録", type="primary", use_container_width=True):
            if not sel_pack or p_qty is None: 
                st.error("⚠️ アイテム名と数量は必須です。")
            else:
                log_qty = to_float(p_qty)
                final_p_type = "入庫" if "入庫" in p_type else "出庫"
                if "棚卸" in p_type:
                    current_calc_stock = mat_summary[sel_pack]["現在庫"]
                    diff = log_qty - current_calc_stock
                    if diff >= 0: final_p_type, log_qty = "入庫", diff
                    else: final_p_type, log_qty = "出庫", abs(diff)
                
                if log_qty > 0: 
                    item_cat = mat_summary[sel_pack].get("区分", "資材")
                    new_pack = pd.DataFrame([{
                        "ID": str(uuid.uuid4())[:6].upper(), "登録日": pd.to_datetime(p_date),
                        "アイテム名": sel_pack, "区分": item_cat, "処理区分": final_p_type, "数量": log_qty, "理由": p_reason, 
                        "関連製品名": "", "理論在庫": "", "備考": p_rem, "登録日時": datetime.now()
                    }])
                    append_and_sync("material_logs", new_pack)
                    st.toast(f"✨ 登録しました: {sel_pack} ({final_p_type} {log_qty})", icon="✅")
                    st.rerun()
                else: st.info("現在の計算在庫と一致しているため、調整は不要です。")

    with t_p3:
        st.markdown('### ✏️ 登録データのかんたん修正・削除')
        if not mat_log_df.empty:
            disp_pack = mat_log_df.sort_values("登録日時", ascending=False).copy()
            disp_pack["登録日(表示)"] = disp_pack["登録日"].apply(format_date_jp)
            disp_cols = ["ID", "登録日(表示)", "アイテム名", "区分", "処理区分", "数量", "理由", "関連製品名", "備考"]
            
            recent_p = disp_pack.head(10).copy()
            edited_p = st.data_editor(
                recent_p[disp_cols], num_rows="dynamic", use_container_width=True, hide_index=True, 
                column_config={"登録日(表示)": st.column_config.TextColumn("登録日(表示)", disabled=True), "処理区分": st.column_config.SelectboxColumn("処理区分", options=["入庫", "出庫", "製造連動", "出荷連動"]), "ID": None}, 
                key="edit_p"
            )
            if st.button("💾 直近データを修正・削除保存", key="btn_edit_p"):
                save_df = edited_p.copy()
                save_df["登録日"] = pd.to_datetime(save_df["登録日(表示)"].str.split(" ").str[0], errors="coerce")
                merged_df = pd.merge(save_df, mat_log_df[["ID", "理論在庫", "登録日時"]], on="ID", how="left")
                save_and_sync("material_logs", pd.concat([mat_log_df[~mat_log_df["ID"].isin(recent_p["ID"])], merged_df], ignore_index=True))
                st.toast("✅ ログの修正を保存しました", icon="✅")
                st.rerun()

# --- 🤖 自動生産スケジューラ ---
elif page == "🤖 自動生産スケジューラ":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #4F46E5 0%, #10B981 100%);"><h1>🤖 自動生産スケジューラ (MRP/APS)</h1></div>', unsafe_allow_html=True)
    st.markdown("💡 **受注残・安全在庫・リードタイム・製造ロット** を基に、システムが自動計算した「最適な製造計画」を提案します。")
    
    if not proposed_schedules:
        st.success("✅ 向こう60日間、安全在庫を下回る製品はありません。追加の製造は不要です。")
    else:
        df_prop = pd.DataFrame(proposed_schedules).sort_values("製造予定日")
        st.warning(f"🚨 今後、安全在庫を下回る製品が **{len(df_prop)}件** 予測されています。以下のスケジュールでの製造を提案します。")
        
        st.markdown("### 📝 製造スケジュール案の確認・調整")
        st.info("提案された『ケース数』や『使用設備』は、現場の状況に合わせて直接書き換えることができます。")
        
        edited_prop = st.data_editor(
            df_prop, num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={
                "製造予定日": st.column_config.DateColumn("着手(製造)日", format="YYYY-MM-DD"),
                "大カテゴリ": st.column_config.TextColumn("大カテゴリ", disabled=True),
                "製品名": st.column_config.TextColumn("製品名", disabled=True),
                "ケース数": st.column_config.NumberColumn("提案CS数 (ロット計算済)", min_value=1, step=1, format="%d"),
                "使用設備": st.column_config.TextColumn("使用設備"),
                "想定所要時間(分)": st.column_config.NumberColumn("所要時間目安", disabled=True),
                "理由": st.column_config.TextColumn("提案理由", disabled=True)
            }, key="edit_proposal"
        )
        
        if st.button("💾 このスケジュールを『🏭 製造登録』に一括で反映させる", type="primary", use_container_width=True):
            new_manus = []
            for _, r in edited_prop.iterrows():
                new_manus.append({
                    "ID": str(uuid.uuid4())[:6].upper(), "製造予定日": pd.to_datetime(r["製造予定日"]), 
                    "大カテゴリ": r["大カテゴリ"], "製品名": r["製品名"], "ケース数": to_int(r["ケース数"]), 
                    "出来高数": 0, "賞味期限": "", "担当者": "システム自動提案", "リパックフラグ": False, 
                    "備考": f"【自動作成】 {r['理由']}", "登録日時": datetime.now()
                })
            
            if new_manus:
                new_manus_df = pd.DataFrame(new_manus)
                for i in range(len(new_manus_df)):
                    append_and_sync("manufactures", new_manus_df.iloc[[i]])
                st.success("✅ 提案されたスケジュールを『製造登録』に一括登録しました！")
                st.rerun()
                
        st.write("---")
        st.markdown("### 📊 設備別の負荷予測（ガントチャート風サマリ）")
        equip_load = edited_prop.groupby(["製造予定日", "使用設備"])["想定所要時間(分)"].sum().reset_index()
        if not equip_load.empty:
            fig = px.bar(equip_load, x="製造予定日", y="想定所要時間(分)", color="使用設備", title="日別・設備別の想定稼働時間", text="想定所要時間(分)")
            st.plotly_chart(fig, use_container_width=True)

# --- 📑 登録一覧 ---
elif page == "📑 登録一覧":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #0F766E 0%, #14B8A6 100%);"><h1>📑 登録データ一覧・出力</h1></div>', unsafe_allow_html=True)
    t_list1, t_list2, t_list3 = st.tabs(["📋 受注・出荷データ", "🏭 製造データ", "📦 原料・資材利用ログ"])
    
    with t_list1:
        if orders_df.empty: st.info("登録データがありません。")
        else:
            edit_df = orders_df.sort_values("登録日時", ascending=False).copy()
            edit_df["納品予定日(表示)"] = edit_df["納品予定日"].apply(format_date_jp)
            cols = ["ID", "登録日時", "大カテゴリ", "顧客名", "納品予定日(表示)", "製品名", "ケース数", "運送会社", "備考", "荷姿チェック", "発送備考", "不良廃棄フラグ"]
            edit_df = edit_df[[c for c in cols if c in edit_df.columns]]
            
            def get_stock_status(row):
                try:
                    d_str = str(row["納品予定日(表示)"]).split(" ")[0]
                    d, p, qty = pd.Timestamp(d_str).normalize(), row["製品名"], to_int(row.get("ケース数", 0))
                    stock = future_stocks[p][d] if d >= today and p in future_stocks and d in future_stocks[p] else current_stocks.get(p, 0)
                    if stock < 0: return f"在庫不足 ({stock})"
                    else: return f"OK (+{stock})"
                except: return "不明"

            edit_df.insert(7, "在庫状況", edit_df.apply(get_stock_status, axis=1))

            def highlight_row(row):
                is_irregular = row.get("不良廃棄フラグ") == True or str(row.get("不良廃棄フラグ")).upper() == "TRUE"
                is_shortage = "不足" in str(row.get("在庫状況", ""))
                is_checked = row.get("荷姿チェック") == True or str(row.get("荷姿チェック")).upper() == "TRUE"
                
                if is_checked: return ['background-color: #D1FAE5; color: #065F46;'] * len(row)
                if is_shortage and is_irregular: return ['background-color: #FEF08A; color: #DC2626; font-weight: bold;'] * len(row)
                if is_shortage: return ['background-color: #FEE2E2; color: #DC2626; font-weight: bold;'] * len(row)
                if is_irregular: return ['background-color: #FEF08A; color: #854D0E; font-weight: bold;'] * len(row)
                return [''] * len(row)

            out_df = edit_df.drop(columns=["ID", "在庫状況", "不良廃棄フラグ", "登録日時"], errors='ignore')
            csv_data = out_df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button("📥 見やすいレイアウトでCSV出力", data=csv_data, file_name=f"受注一覧_{date.today()}.csv", use_container_width=True)
            st.markdown("""<div style="font-size:14px; margin-bottom:10px;">
                <b>🎨 色：</b> <span style="background-color:#FEE2E2; color:#DC2626; padding:2px 6px;">在庫不足（赤字）</span> / <span style="background-color:#FEF08A; color:#854D0E; padding:2px 6px;">不良廃棄（黄色）</span> / <span style="background-color:#D1FAE5; color:#065F46; padding:2px 6px;">✅ 荷姿完了（緑色）</span>
            </div>""", unsafe_allow_html=True)
            st.dataframe(edit_df.style.apply(highlight_row, axis=1), use_container_width=True, hide_index=True, height=600)

    with t_list2:
        if manus_df.empty: st.info("製造データがありません。")
        else:
            m_df = manus_df.sort_values("登録日時", ascending=False).copy()
            m_df["製造予定日(表示)"] = m_df["製造予定日"].apply(format_date_jp)
            
            def highlight_repack(row):
                is_repack = row.get("リパックフラグ") == True or str(row.get("リパックフラグ")).upper() == "TRUE"
                if is_repack: return ['background-color: #DBEAFE; color: #1E3A8A; font-weight: bold;'] * len(row)
                return [''] * len(row)
                
            out_m_df = m_df[["製造予定日(表示)", "製品名", "ケース数", "出来高数", "担当者", "備考"]].copy()
            st.download_button("📥 見やすいレイアウトでCSV出力", data=out_m_df.to_csv(index=False, encoding="utf-8-sig"), file_name=f"製造一覧_{date.today()}.csv", use_container_width=True)
            st.markdown("""<div style="font-size:14px; margin-bottom:10px;">
                <b>🎨 色：</b> <span style="background-color:#DBEAFE; color:#1E3A8A; padding:2px 6px;">リパック製造（青色）</span>
            </div>""", unsafe_allow_html=True)
            st.dataframe(m_df[["ID", "製造予定日(表示)", "製品名", "ケース数", "出来高数", "担当者", "リパックフラグ", "備考"]].style.apply(highlight_repack, axis=1), use_container_width=True, hide_index=True, height=600)

    with t_list3:
        if mat_log_df.empty: st.info("原料・資材ログがありません。")
        else:
            e_pack = mat_log_df.sort_values("登録日時", ascending=False).copy()
            e_pack["登録日(表示)"] = e_pack["登録日"].apply(format_date_jp)
            out_p_df = e_pack[["登録日(表示)", "アイテム名", "区分", "処理区分", "数量", "理由", "関連製品名", "備考"]].copy()
            st.download_button("📥 見やすいレイアウトでCSV出力", data=out_p_df.to_csv(index=False, encoding="utf-8-sig"), file_name=f"原料資材ログ_{date.today()}.csv", use_container_width=True)
            st.dataframe(e_pack[["ID", "登録日(表示)", "アイテム名", "区分", "処理区分", "数量", "理由", "関連製品名", "備考"]], use_container_width=True, hide_index=True, height=600)

# --- 📊 在庫・スケジュール ---
elif page == "📊 在庫・スケジュール":
    st.markdown('<div class="slim-header"><h1>📊 在庫予測 ＆ カレンダー</h1></div>', unsafe_allow_html=True)
    
    t1, t2, t3 = st.tabs(["📉 1ヶ月在庫予測", "📅 週間カレンダー", "🔍 製品別詳細ビュー"])
    with t1:
        if master_df_unique.empty: st.info("製品マスタが空です。")
        else:
            inv_list = []
            show_dates = pd.date_range(today, today + timedelta(days=30))
            for _, r in master_df_unique.iterrows():
                p = r["製品名"]
                curr_stock = current_stocks.get(p, 0)
                row = {"カテゴリ": r["大カテゴリ"], "製品名": format_name(p), "現在庫": curr_stock}
                for d in show_dates: row[format_date_jp(d)] = future_stocks.get(p, {}).get(d, curr_stock)
                inv_list.append(row)
            st.dataframe(pd.DataFrame(inv_list).sort_values("カテゴリ").style.map(lambda x: 'color: #dc2626; font-weight: bold; background-color: #fee2e2;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True, height=600)

    with t2:
        cal_data = []
        html = '<table class="sched-table"><tr><th style="width:120px;">日付</th><th style="width:40%;">製造 / リパック</th><th style="width:40%;">出荷 / 不良廃棄</th></tr>'
        for i in range(7):
            d = today + timedelta(days=i)
            m_h = ""
            for _, r in manus_df[manus_df["製造予定日"]==d].iterrows():
                p, qty = r["製品名"], to_int(r.get("ケース数", 0))
                is_repack = r.get("リパックフラグ") in [True, "TRUE"]
                if is_repack:
                    qty_html = f'<span style="color:#1E3A8A; font-weight:900;">{qty}cs (リパック)</span>'
                    bg_color, border_color = "#DBEAFE", "#1E3A8A"
                else:
                    qty_html = f'<span style="color:#059669; font-weight:900;">{qty}cs</span>'
                    bg_color, border_color = "#F0FFF4", "#10B981"
                m_h += f'<div style="background:{bg_color}; border-left:4px solid {border_color}; padding:6px; margin-bottom:4px; border-radius:4px;"><span style="font-weight:700;">{format_name(p)}</span> <span style="float:right;">{qty_html}</span></div>'
            
            o_h = ""
            for _, r in orders_df[orders_df["納品予定日"] == d].iterrows():
                p, qty = r["製品名"], to_int(r.get("ケース数", 0))
                stock_on_day = future_stocks.get(p, {}).get(d, 0)
                is_checked = r.get("荷姿チェック") in [True, "TRUE"]
                is_irregular = r.get("不良廃棄フラグ") in [True, "TRUE"]
                
                if is_checked: qty_html, bg_color, border_color = f'<span style="color:#065F46; font-weight:900; text-decoration:line-through;">{qty}cs</span>', "#D1FAE5", "#059669"
                elif is_irregular: qty_html, bg_color, border_color = f'<span style="color:#B45309; font-weight:900;">{qty}cs (不良)</span>', "#FEF3C7", "#D97706"
                elif stock_on_day < 0: qty_html, bg_color, border_color = f'<span style="color:#DC2626; font-weight:900;">{qty}cs (不足)</span>', "#FEE2E2", "#DC2626"
                else: qty_html, bg_color, border_color = f'<span style="color:#1D4ED8; font-weight:900;">{qty}cs</span>', "#F0F7FF", "#2563EB"
                o_h += f'<div style="background:{bg_color}; border-left:4px solid {border_color}; padding:6px; margin-bottom:4px; border-radius:4px;"><span style="font-weight:700;">{r["顧客名"]}: {format_name(p)}</span> <span style="float:right;">{qty_html}</span></div>'
            html += f'<tr><td><b>{format_date_jp(d)}</b></td><td>{m_h}</td><td>{o_h}</td></tr>'
            
            m_txt = " / ".join([f"{r['製品名']} ({to_int(r['ケース数'])}cs)" for _, r in manus_df[manus_df["製造予定日"]==d].iterrows()]) if not manus_df.empty else ""
            o_txt = " / ".join([f"{r['顧客名']} : {r['製品名']} ({to_int(r['ケース数'])}cs)" for _, r in orders_df[orders_df["納品予定日"]==d].iterrows()]) if not orders_df.empty else ""
            cal_data.append({"日付": format_date_jp(d), "製造予定": m_txt, "出荷予定": o_txt})
            
        st.download_button("🖨️ カレンダーCSV出力", data=pd.DataFrame(cal_data).to_csv(index=False, encoding="utf-8-sig"), file_name=f"カレンダー_{today.strftime('%Y%m%d')}.csv", type="primary", use_container_width=True)
        st.markdown(html + '</table>', unsafe_allow_html=True)

    with t3:
        st.markdown('### 🔍 製品別 在庫推移と詳細スケジュール')
        if master_df_unique.empty: st.info("製品が登録されていません。")
        else:
            cat_full_det = st.pills("カテゴリ詳細", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed", key="pills_det")
            cat_det = cat_full_det.split(" ", 1)[1] if cat_full_det else CATEGORIES[0].split(" ", 1)[1]
            sc1_det, sc2_det = st.columns([1.5, 2.5])
            search_p_det = sc1_det.text_input("🔍 製品名検索", placeholder="検索...", key="search_det")
            prods_det = [p for p in master_df_unique["製品名"].tolist() if search_p_det in p] if search_p_det else (master_df_unique[master_df_unique["大カテゴリ"] == cat_det]["製品名"].tolist() if not master_df_unique.empty else [])
            sel_prod = sc2_det.selectbox("確定製品", options=prods_det, index=None, format_func=format_name, key="sel_det", placeholder="選択してください")
            
            if sel_prod:
                p_o_ev = orders_df[(orders_df["製品名"] == sel_prod) & (orders_df["納品予定日"] >= today)][["納品予定日", "顧客名", "ケース数"]] if not orders_df.empty else pd.DataFrame(columns=["納品予定日", "顧客名", "ケース数"])
                p_m_ev = manus_df[(manus_df["製品名"] == sel_prod) & (manus_df["製造予定日"] >= today)][["製造予定日", "備考", "ケース数"]] if not manus_df.empty else pd.DataFrame(columns=["製造予定日", "備考", "ケース数"])
                
                detail_list = []
                temp_stock = current_stocks.get(sel_prod, 0)
                for d in pd.date_range(today, today + timedelta(days=30)):
                    day_o = p_o_ev[p_o_ev["納品予定日"].dt.date == d.date()]
                    out_qty = sum(to_int(r['ケース数']) for _, r in day_o.iterrows()) if not day_o.empty else 0
                    out_detail = " / ".join([f"{r['顧客名']}({to_int(r['ケース数'])}cs)" for _, r in day_o.iterrows()]) if not day_o.empty else "-"
                    day_m = p_m_ev[p_m_ev["製造予定日"].dt.date == d.date()]
                    in_qty = sum(to_int(r['ケース数']) for _, r in day_m.iterrows()) if not day_m.empty else 0
                    in_detail = " / ".join([f"製造({to_int(r['ケース数'])}cs)" for _, r in day_m.iterrows()]) if not day_m.empty else "-"
                    temp_stock = temp_stock + in_qty - out_qty
                    detail_list.append({"日付": format_date_jp(d), "製造 (入)": in_qty, "製造詳細": in_detail, "出荷 (出)": out_qty, "出荷詳細": out_detail, "予定在庫": temp_stock})
                
                df_detail = pd.DataFrame(detail_list)
                fig = px.line(df_detail, x="日付", y="予定在庫", title=f"【{sel_prod}】 1ヶ月の予定在庫推移", markers=True)
                fig.add_bar(x=df_detail["日付"], y=df_detail["製造 (入)"], name="製造", marker_color="#10B981", opacity=0.6)
                fig.add_bar(x=df_detail["日付"], y=-df_detail["出荷 (出)"], name="出荷", marker_color="#F43F5E", opacity=0.6)
                st.plotly_chart(fig.update_layout(hovermode="x unified", margin=dict(l=20, r=20, t=40, b=20)), use_container_width=True)
                st.dataframe(df_detail.style.map(lambda x: 'color: #DC2626; font-weight: bold; background-color: #FEE2E2;' if isinstance(x, int) and x < 0 else '', subset=["予定在庫"]), use_container_width=True, hide_index=True)

# --- ⚙️ マスタ・データ分析 ---
elif page == "⚙️ マスタ・分析":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #475569 0%, #1E293B 100%);"><h1>⚙️ マスタ・データ分析 (PMS統合版)</h1></div>', unsafe_allow_html=True)
    st.info("💡 下のタブを切り替えて、製品、原料、BOM（レシピ）、設備などの各種マスタデータを編集できます。")
    
    t_m1, t_m2, t_m3, t_m4, t_m5, t_m6, t_m7 = st.tabs(["📦 製品マスタ", "🧪 原料マスタ", "📜 BOM(レシピ)マスタ", "⚙️ 設備マスタ", "🏢 顧客マスタ", "🚚 運送会社・従業員", "📊 歩留・原価・ABC分析"])
    
    with t_m1:
        st.markdown("### 製品マスタ（自動生産スケジューラ連動）")
        pack_names = pack_mst_unique["資材名"].tolist() if not pack_mst_unique.empty else []
        edited_master = st.data_editor(
            master_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={
                "大カテゴリ": st.column_config.SelectboxColumn("大カテゴリ", options=[c.split(" ", 1)[1] for c in CATEGORIES], required=True),
                "製品名": st.column_config.TextColumn("製品名", required=True),
                "初期在庫数": st.column_config.NumberColumn("初期在庫数", min_value=-9999, step=1, format="%d", default=0),
                "使用資材名": st.column_config.SelectboxColumn("使用資材名 (旧式)", options=pack_names),
                "資材使用数": st.column_config.NumberColumn("資材使用数 (旧式)", min_value=0, step=1, format="%d", default=1),
                "入数": st.column_config.NumberColumn("入数", min_value=1, step=1, format="%d", default=1),
                "安全在庫数": st.column_config.NumberColumn("安全在庫数(CS)", min_value=0, step=1, format="%d", default=0),
                "製造ロット数": st.column_config.NumberColumn("製造ロット数(CS)", min_value=1, step=1, format="%d", default=1),
                "リードタイム日": st.column_config.NumberColumn("リードタイム(日)", min_value=0, step=1, format="%d", default=0),
                "バッチ製造時間分": st.column_config.NumberColumn("製造時間(分/Lot)", min_value=0, step=1, format="%d", default=60),
                "使用設備": st.column_config.SelectboxColumn("使用設備", options=equip_df["設備名"].tolist() if not equip_df.empty else []),
                "特注品": st.column_config.CheckboxColumn("特注品", default=False)
            }, key="edit_master"
        )
        if st.button("💾 製品マスタを保存・同期", type="primary", use_container_width=True):
            save_and_sync("master", edited_master); st.toast("製品マスタを更新しました！", icon="✅"); st.rerun()
            
    with t_m2:
        st.markdown("### 原料・資材マスタ")
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            st.write("▼ 原料マスタ (こんにゃく粉等)")
            edited_raw = st.data_editor(raw_mst_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"原料名": st.column_config.TextColumn("原料名", required=True), "初期在庫": st.column_config.NumberColumn("初期在庫", step=1, format="%d", default=0), "発注点": st.column_config.NumberColumn("発注点", step=1, format="%d", default=0), "単価": st.column_config.NumberColumn("単価(円)", step=0.1, format="%.2f", default=0.0)}, key="edit_raw")
            if st.button("💾 原料マスタ保存", type="primary"): save_and_sync("raw_materials", edited_raw); st.toast("更新完了", icon="✅"); st.rerun()
        with col_r2:
            st.write("▼ 資材マスタ (段ボール等)")
            edited_pack = st.data_editor(pack_mst_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"資材名": st.column_config.TextColumn("資材名", required=True), "初期在庫": st.column_config.NumberColumn("初期在庫", step=1, format="%d", default=0), "発注点": st.column_config.NumberColumn("発注点", step=1, format="%d", default=100)}, key="edit_pack")
            if st.button("💾 資材マスタ保存", type="primary"): save_and_sync("packaging_master", edited_pack); st.toast("更新完了", icon="✅"); st.rerun()

    with t_m3:
        st.markdown("### 📜 BOM (部品構成・レシピ) マスタ")
        st.info("製品1ケース(CS)を作るために必要な原料や資材の量を登録します。ここで登録されたデータは、製造登録時に自動的に在庫から引き落とされます。")
        all_items = raw_mst_df["原料名"].tolist() + pack_mst_df["資材名"].tolist() if not raw_mst_df.empty and not pack_mst_df.empty else []
        edited_bom = st.data_editor(
            bom_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={
                "製品名": st.column_config.SelectboxColumn("対象製品", options=master_df_unique["製品名"].tolist() if not master_df_unique.empty else [], required=True),
                "アイテム名": st.column_config.SelectboxColumn("原料/資材名", options=all_items, required=True),
                "区分": st.column_config.SelectboxColumn("区分", options=["原料", "資材"], required=True),
                "1CS使用量": st.column_config.NumberColumn("1CSあたりの使用量", min_value=0.0, step=0.01, format="%.3f", required=True)
            }, key="edit_bom"
        )
        if st.button("💾 BOMマスタを保存・同期", type="primary", use_container_width=True):
            save_and_sync("bom_master", edited_bom); st.toast("BOMマスタを更新しました！", icon="✅"); st.rerun()

    with t_m4:
        st.markdown("### ⚙️ 設備マスタ")
        edited_equip = st.data_editor(equip_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"設備名": st.column_config.TextColumn("設備名(ライン名)", required=True), "1日稼働上限時間": st.column_config.NumberColumn("1日最大稼働時間(分)", min_value=0, step=30, format="%d", default=480)}, key="edit_equip")
        if st.button("💾 設備マスタを保存・同期", type="primary", use_container_width=True):
            save_and_sync("equipment_master", edited_equip); st.toast("更新完了", icon="✅"); st.rerun()

    with t_m5:
        st.markdown("### 顧客リストの編集")
        edited_cust = st.data_editor(cust_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"顧客名": st.column_config.TextColumn("顧客名", required=True), "ふりがな": st.column_config.TextColumn("ふりがな")}, key="edit_cust")
        if st.button("💾 顧客マスタを保存・同期", type="primary", use_container_width=True):
            save_and_sync("customers", edited_cust); st.toast("更新完了", icon="✅"); st.rerun()

    with t_m6:
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.write("▼ 運送会社")
            edited_ship = st.data_editor(ship_mst_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"運送会社名": st.column_config.TextColumn("運送会社名", required=True)}, key="edit_ship")
            if st.button("💾 運送会社保存", type="primary"): save_and_sync("shipping_master", edited_ship); st.toast("更新完了", icon="✅"); st.rerun()
        with col_s2:
            st.write("▼ 従業員名簿")
            edited_emp = st.data_editor(emp_mst_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"従業員名": st.column_config.TextColumn("従業員名", required=True)}, key="edit_emp")
            if st.button("💾 従業員保存", type="primary"): save_and_sync("employees_master", edited_emp); st.toast("更新完了", icon="✅"); st.rerun()

    with t_m7:
        st.markdown("### 📊 出荷トレンドとABC分析")
        if not orders_df.empty:
            thirty_days_ago = today - timedelta(days=30)
            recent_orders = orders_df[(orders_df["納品予定日"] >= pd.Timestamp(thirty_days_ago)) & (orders_df["不良廃棄フラグ"] == False)].copy()
            if not recent_orders.empty:
                recent_orders["ケース数"] = recent_orders["ケース数"].apply(to_int)
                recent_orders["納品予定日"] = recent_orders["納品予定日"].dt.date
                trend_data = recent_orders.groupby(["納品予定日", "大カテゴリ"])["ケース数"].sum().reset_index()
                fig_trend = px.line(trend_data, x="納品予定日", y="ケース数", color="大カテゴリ", title="過去30日間のカテゴリ別 出荷数トレンド", markers=True)
                st.plotly_chart(fig_trend, use_container_width=True)
            
            st.write("---")
            st.markdown("#### 顧客別・製品別 累積データ")
            o_stat = orders_df.copy()
            o_stat["ケース数"] = o_stat["ケース数"].apply(to_int)
            abc = o_stat.groupby("製品名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False)
            if abc["ケース数"].sum() > 0:
                abc["累計比率"] = abc["ケース数"].cumsum() / abc["ケース数"].sum() * 100
                abc["ランク"] = pd.cut(abc["累計比率"], bins=[0, 70, 90, 100], labels=["A (主力)", "B (中堅)", "C (その他)"])
                st.dataframe(abc.style.map(lambda v: 'background-color: #FEE2E2; font-weight: 900;' if "A" in str(v) else '', subset=["ランク"]), use_container_width=True, hide_index=True)
                cust_abc = o_stat[o_stat["顧客名"]!="未指定"].groupby("顧客名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False).head(15)
                if not cust_abc.empty: st.plotly_chart(px.bar(cust_abc, x="ケース数", y="顧客名", orientation='h', title="主要顧客TOP15"), use_container_width=True)
            
            # 簡易歩留まり計算表示
            st.write("---")
            st.markdown("#### 簡易 製造歩留まり分析 (直近30日)")
            if not manus_df.empty and not master_df_unique.empty:
                recent_manus = manus_df[manus_df["製造予定日"] >= pd.Timestamp(thirty_days_ago)].copy()
                recent_manus["出来高数"] = recent_manus["出来高数"].apply(to_int)
                recent_manus["ケース数"] = recent_manus["ケース数"].apply(to_int)
                
                m_info = master_df_unique.set_index("製品名")["入数"].to_dict()
                y_data = []
                for _, r in recent_manus.iterrows():
                    p = r["製品名"]
                    cs = r["ケース数"]
                    deki = r["出来高数"]
                    if p in m_info and cs > 0 and deki > 0:
                        theory = cs * to_int(m_info[p])
                        yield_rate = (deki / theory) * 100 if theory > 0 else 0
                        y_data.append({"製造日": r["製造予定日"].date(), "製品名": p, "予定出来高": theory, "実出来高": deki, "歩留まり(%)": round(yield_rate, 1)})
                
                if y_data:
                    df_yield = pd.DataFrame(y_data)
                    st.dataframe(df_yield.style.map(lambda x: 'color: #DC2626; font-weight: bold;' if isinstance(x, float) and x < 95 else '', subset=["歩留まり(%)"]), use_container_width=True, hide_index=True)
                    if y_data:
                    df_yield = pd.DataFrame(y_data)
                    # 95%を下回る歩留まりは赤文字で警告
                    st.dataframe(df_yield.style.map(lambda x: 'color: #DC2626; font-weight: bold; background-color: #FEE2E2;' if isinstance(x, (int, float)) and x < 95 else '', subset=["歩留まり(%)"]), use_container_width=True, hide_index=True)
                    
                    # 歩留まりトレンドグラフ
                    fig_yield = px.scatter(df_yield, x="製造日", y="歩留まり(%)", color="製品名", title="直近30日間の製造歩留まり(%) 推移", hover_data=["予定出来高", "実出来高"])
                    fig_yield.add_hline(y=100, line_dash="dash", line_color="green", annotation_text="100% (基準)")
                    fig_yield.add_hline(y=95, line_dash="dash", line_color="red", annotation_text="95% (警告ライン)")
                    st.plotly_chart(fig_yield, use_container_width=True)
                else:
                    st.info("直近30日間の製造データ（出来高入力済み）がありません。")
