import os
import io
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
from datetime import datetime, timedelta, date
import gspread
from google.oauth2.service_account import Credentials
import numpy as np

# ─────────────────────────────────────────────
# 0. 絶対安全な数値変換関数 ＆ 曜日フォーマット関数
# ─────────────────────────────────────────────
def to_int(v):
    """ SeriesエラーやNaNを完全に防ぎ、単一の整数を返す堅牢な関数 """
    try:
        if isinstance(v, pd.Series): v = v.sum()
        if pd.isna(v) or str(v).strip() == "": return 0
        return int(float(v))
    except: return 0

def format_date_jp(d):
    """ 時間を排除し、日付に曜日を追加してフォーマットする関数 """
    if pd.isna(d) or d == "": return ""
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    try:
        if isinstance(d, str): d = pd.to_datetime(d.split(" ")[0])
        return f"{d.strftime('%Y/%m/%d')} ({weekdays[d.weekday()]})"
    except: return str(d).split(" ")[0]

# ─────────────────────────────────────────────
# 1. ページ基本設定 & CSS
# ─────────────────────────────────────────────
st.set_page_config(page_title="丸実屋 統合管理システム", page_icon="🏭", layout="wide", initial_sidebar_state="expanded")

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
    
    /* ★ 特大カテゴリボタン ★ */
    [data-testid="stPills"] button { 
        padding: 20px 40px !important; font-size: 24px !important; font-weight: 900 !important; 
        border-radius: 14px !important; border: 2px solid #CBD5E1 !important; margin: 8px !important; 
        min-height: 70px !important;
    }
    [data-testid="stPills"] button span { font-size: 24px !important; font-weight: 900 !important; white-space: nowrap !important; }
    [data-testid="stPills"] button[aria-selected="true"] { background-color: #2563EB !important; color: #FFFFFF !important; box-shadow: 0 6px 15px rgba(37, 99, 235, 0.4) !important; }
    
    .sched-table { width: 100%; border-collapse: collapse; background: white; font-size: 15px; border-radius: 10px; overflow: hidden; }
    .sched-table th { background: #F8FAFC; padding: 10px; border-bottom: 2px solid #E2E8F0; }
    .sched-table td { padding: 10px; border-bottom: 1px solid #F1F5F9; vertical-align: top; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 2. ログイン認証
# ─────────────────────────────────────────────
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
# 3. GSpread 同期ロジック（高速化 ＆ 安定化）
# ─────────────────────────────────────────────
@st.cache_resource
def get_client():
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

client = get_client()
sheet = client.open_by_url(st.secrets["spreadsheet_url"])

# ★ 高速化：データをキャッシュし、再描画時の遅延を防止
@st.cache_data(ttl=600)
def load_data_from_cloud(name):
    try:
        ws = sheet.worksheet(name)
        data = ws.get_all_values()
        cols_def = {
            "orders": ["ID","納品予定日","顧客名","大カテゴリ","製品名","ケース数","運送会社","備考","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考","不良廃棄フラグ","登録日時"],
            "manufactures": ["ID","製造予定日","大カテゴリ","製品名","ケース数","リパックフラグ","備考","登録日時"],
            "master": ["大カテゴリ","製品名","初期在庫数","使用資材名","資材使用数"],
            "customers": ["顧客名","ふりがな"],
            "packaging_master": ["資材名","品番","規格","仕入先","保管場所","単位","初期在庫","発注点"],
            "packaging_logs": ["ID","登録日","資材名","処理区分","数量","理由","備考","関連製品名","理論在庫","登録日時"],
            "shipping_master": ["運送会社名"]
        }
        target_cols = cols_def.get(name, [])
        if len(data) <= 1: return pd.DataFrame(columns=target_cols)
        df = pd.DataFrame(data[1:], columns=data[0])
        
        # ★ 安定化：列名の正規化と不足列の自動補完 (KeyError回避)
        df.columns = df.columns.str.strip().str.replace(' ', '').str.replace('　', '')
        df = df.loc[:, ~df.columns.duplicated()]
        df = df.reindex(columns=target_cols, fill_value="")
        
        # 数値型変換
        for c in ["ケース数", "初期在庫数", "資材使用数", "初期在庫", "発注点", "数量", "理論在庫"]:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).apply(to_int)
        # 日付型変換
        for c in ["納品予定日", "製造予定日", "登録日", "登録日時", "賞味期限1", "賞味期限2", "賞味期限3", "賞味期限4", "賞味期限5"]:
            if c in df.columns: df[c] = pd.to_datetime(df[c], errors='coerce')
        return df[target_cols]
    except Exception: return pd.DataFrame()

def save_and_sync(name, df):
    try: ws = sheet.worksheet(name)
    except: ws = sheet.add_worksheet(title=name, rows="1000", cols="30")
    ws.clear()
    df_save = df.copy()
    for col in df_save.columns:
        if pd.api.types.is_datetime64_any_dtype(df_save[col]): df_save[col] = df_save[col].dt.strftime('%Y-%m-%d %H:%M:%S').replace('NaT', '')
        elif pd.api.types.is_bool_dtype(df_save[col]): df_save[col] = df_save[col].astype(str).str.upper()
        elif pd.api.types.is_numeric_dtype(df_save[col]): df_save[col] = df_save[col].fillna(0).apply(to_int).astype(str)
        else: df_save[col] = df_save[col].astype(str)
    df_save = df_save.fillna("").replace(["nan", "None", "NaT"], "")
    ws.update(values=[df_save.columns.values.tolist()] + df_save.values.tolist(), range_name='A1')
    st.cache_data.clear() # ★ 更新後はキャッシュをクリアして最新を読み込ませる
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
    row_to_send = row_copy.fillna("").astype(str).replace(["nan", "None", "NaT"], "").values[0].tolist()
    ws.append_row(row_to_send)
    st.cache_data.clear() # ★ キャッシュクリア
    st.session_state[f"{name}_df"] = load_data_from_cloud(name)

# ─────────────────────────────────────────────
# セッション初期化
# ─────────────────────────────────────────────
sheet_names = ["orders", "manufactures", "master", "customers", "packaging_master", "packaging_logs", "shipping_master"]
for sheet_name in sheet_names:
    if f"{sheet_name}_df" not in st.session_state: st.session_state[f"{sheet_name}_df"] = load_data_from_cloud(sheet_name)
if "current_page" not in st.session_state: st.session_state.current_page = "📋 受注登録"

orders_df = st.session_state.orders_df
manus_df = st.session_state.manufactures_df
master_df = st.session_state.master_df
cust_df = st.session_state.customers_df
pack_mst_df = st.session_state.packaging_master_df
pack_log_df = st.session_state.packaging_logs_df
ship_mst_df = st.session_state.shipping_master_df

CATEGORIES = ["🍝 つきこん", "🟫 平こん", "🍜 糸こん・しらたき", "🔺 三角こん", "🟤 玉こん", "🎲 ダイスこん", "🏷️ 短冊", "🇯🇵 国産", "🤲 ちぎりこん", "🏮 大黒屋", "🏭 かねこ", "🍱 ショクカイ", "❄️ 冷凍耐性", "📦 その他"]
def format_name(n): return f"⚫️ {n}" if "黒" in str(n) else f"⚪️ {n}" if "白" in str(n) else f"📦 {n}"

# ─────────────────────────────────────────────
# 4. 在庫計算エンジン
# ─────────────────────────────────────────────
today = pd.Timestamp.today().normalize()
dates = pd.date_range(today, today + timedelta(days=60))

current_stocks = {}
future_stocks = {}
master_df_unique = master_df.drop_duplicates(subset=["製品名"]) if not master_df.empty else pd.DataFrame(columns=["大カテゴリ","製品名","初期在庫数","使用資材名","資材使用数"])

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

# --- 資材推移サマリ ---
pack_summary = {}
pack_mst_unique = pack_mst_df.drop_duplicates(subset=["資材名"]) if not pack_mst_df.empty else pd.DataFrame(columns=["資材名","品番","規格","仕入先","保管場所","単位","初期在庫","発注点"])
if not pack_mst_unique.empty:
    for _, r in pack_mst_unique.iterrows():
        pack_summary[r["資材名"]] = {"品番": str(r.get("品番", "")), "規格": str(r.get("規格", "")), "現在庫": to_int(r.get("初期在庫", 0)), "発注点": to_int(r.get("発注点", 0))}

# ─────────────────────────────────────────────
# 5. 画面描画
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<p style='font-size:20px; font-weight:900; color:#1E3A8A; margin-bottom:20px;'>🏭 丸実屋システム</p>", unsafe_allow_html=True)
    st.write("---")
    menu_items = ["📋 受注登録", "🏭 製造登録", "🚚 出荷・発送管理", "📦 資材・入出庫", "📑 登録一覧", "📊 在庫・スケジュール", "⚙️ マスタ・分析"]
    for item in menu_items:
        if st.button(item, key=f"menu_{item}", use_container_width=True, type="primary" if st.session_state.current_page == item else "secondary"):
            st.session_state.current_page = item; st.rerun()
page = st.session_state.current_page

# --- 📋 受注登録 ---
if page == "📋 受注登録":
    st.markdown('<div class="slim-header"><h1>📋 受注 登録</h1></div>', unsafe_allow_html=True)
    with st.container():
        c1, c2, c3 = st.columns([1, 2, 1])
        o_date = c1.date_input("📅 納品日", value=date.today() + timedelta(days=1))
        c_name = c2.selectbox("🏢 顧客名", options=sorted(cust_df["顧客名"].unique()) if not cust_df.empty else [], index=None, placeholder="検索...")
        qty = c3.number_input("📦 ケース数", min_value=1, step=1, format="%d", value=None)
        
        cat_full = st.pills("カテゴリ", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
        cat = cat_full.split(" ", 1)[1] if cat_full else CATEGORIES[0].split(" ", 1)[1]
        sc1, sc2 = st.columns([1.5, 2.5])
        search_p = sc1.text_input("🔍 製品検索", placeholder="名称の一部を入力...")
        prods = [p for p in master_df_unique["製品名"].tolist() if search_p in p] if search_p else (master_df_unique[master_df_unique["大カテゴリ"] == cat]["製品名"].tolist() if not master_df_unique.empty else [])
        prod = sc2.selectbox("確定製品", options=prods, index=None, placeholder="選択してください", format_func=format_name)
        rem = sc2.text_input("📝 備考")
        
        col_chk1, col_chk2 = sc2.columns(2)
        is_substitute = col_chk1.checkbox("🔄 代替品として送付")
        is_irregular = col_chk2.checkbox("⚠️ 水漏れ・不良廃棄 (在庫減)")
        st.write("---")

        if prod and qty is not None:
            cur_stock = current_stocks.get(prod, 0)
            if cur_stock < qty:
                st.markdown(f"<div style='background-color:#FEE2E2; padding:12px; border-radius:8px; color:#DC2626;'>🚨 <b>製品在庫が不足します！</b> （現在庫: <b>{cur_stock}</b> cs / <span style='font-size:1.1em; font-weight:bold; color:#FF0000;'>不足分: -{qty - cur_stock} cs</span>）</div>", unsafe_allow_html=True)

        msg_slot = st.empty() # ★ 通知をボタン直下に固定
        if st.button("✅ 登録する", type="primary", use_container_width=True):
            if not prod or qty is None: msg_slot.error("⚠️ 製品と数量は必須です。")
            else:
                prefix = "【代替品】" if is_substitute else ""
                if is_irregular: prefix += "【不良廃棄】"
                new_row = pd.DataFrame([{"ID": str(uuid.uuid4())[:6].upper(), "納品予定日": pd.to_datetime(o_date), "顧客名": c_name if c_name else "未指定", "大カテゴリ": cat, "製品名": prod, "ケース数": to_int(qty), "備考": f"{prefix} {rem}".strip(), "不良廃棄フラグ": is_irregular, "登録日時": datetime.now()}])
                append_and_sync("orders", new_row)
                msg_slot.success(f"✨ 登録を完了しました: {prod} ({qty}cs)")
                st.rerun()

    st.markdown('<h2 style="font-size:18px; margin-top:30px;">✏️ 直近の登録データ</h2>', unsafe_allow_html=True)
    if not orders_df.empty:
        disp_o = orders_df.sort_values("登録日時", ascending=False).head(5).copy()
        disp_o["納品予定日"] = disp_o["納品予定日"].apply(format_date_jp)
        st.dataframe(disp_o.drop(columns=["ID", "登録日時"], errors='ignore'), use_container_width=True, hide_index=True)

# --- 📊 在庫・スケジュール ---
elif page == "📊 在庫・スケジュール":
    st.markdown('<div class="slim-header"><h1>📊 在庫予測 ＆ カレンダー</h1></div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["📉 1ヶ月在庫予測", "📅 週間カレンダー"])
    
    with t1:
        if master_df_unique.empty: st.info("マスタが空です。")
        else:
            inv_list = []
            show_dates = pd.date_range(today, today + timedelta(days=30))
            for _, r in master_df_unique.iterrows():
                p = r["製品名"]
                curr_stock = current_stocks.get(p, 0)
                row = {"カテゴリ": r["大カテゴリ"], "製品名": format_name(p), "現在庫": curr_stock}
                for d in show_dates: row[format_date_jp(d)] = future_stocks.get(p, {}).get(d, curr_stock)
                inv_list.append(row)
            st.dataframe(pd.DataFrame(inv_list).style.map(lambda x: 'color: #dc2626; font-weight: bold; background-color: #fee2e2;' if isinstance(x, int) and x < 0 else ''), use_container_width=True, hide_index=True)

    with t2:
        cal_data = []
        html = '<table class="sched-table"><tr><th>日付</th><th>製造</th><th>出荷</th></tr>'
        for i in range(7):
            d = today + timedelta(days=i)
            m_txt = " / ".join([f"{r['製品名']}({to_int(r['ケース数'])}cs)" for _, r in manus_df[manus_df["製造予定日"]==d].iterrows()])
            o_txt = " / ".join([f"{r['顧客名']}:{r['製品名']}({to_int(r['ケース数'])}cs)" for _, r in orders_df[orders_df["納品予定日"]==d].iterrows()])
            html += f'<tr><td><b>{format_date_jp(d)}</b></td><td>{m_txt}</td><td>{o_txt}</td></tr>'
            cal_data.append({"日付": format_date_jp(d), "製造予定": m_txt, "出荷予定": o_txt})
            
        # ★ 文字化け完全解消：utf-8-sig を指定
        csv_cal = pd.DataFrame(cal_data).to_csv(index=False, encoding="utf-8-sig")
        st.download_button("📥 週間カレンダーをCSV出力 (Excel対応)", data=csv_cal, file_name=f"calendar_{date.today()}.csv", use_container_width=True)
        st.markdown(html + '</table>', unsafe_allow_html=True)

# --- 📑 登録一覧 ---
elif page == "📑 登録一覧":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #0F766E 0%, #14B8A6 100%);"><h1>📑 登録データ一覧・出力</h1></div>', unsafe_allow_html=True)
    if orders_df.empty: st.info("データがありません。")
    else:
        disp_all = orders_df.sort_values("登録日時", ascending=False).copy()
        disp_all["納品予定日"] = disp_all["納品予定日"].apply(format_date_jp)
        # ★ 文字化け完全解消
        csv_all = disp_all.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("📥 全受注データをCSV出力 (Excel対応)", data=csv_all, file_name=f"orders_all_{date.today()}.csv", use_container_width=True)
        st.dataframe(disp_all, use_container_width=True, hide_index=True)

# --- 🏭 製造登録 --- (シンプル版)
elif page == "🏭 製造登録":
    st.markdown('<div class="slim-header header-manu"><h1>🏭 製造 登録</h1></div>', unsafe_allow_html=True)
    with st.container():
        col1, col2 = st.columns(2)
        m_date = col1.date_input("📅 製造日", value=date.today())
        m_qty = col2.number_input("📦 製造ケース数", min_value=1, step=1, format="%d", value=None)
        cat_full_m = st.pills("カテゴリ製造", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
        cat_m = cat_full_m.split(" ", 1)[1] if cat_full_m else CATEGORIES[0].split(" ", 1)[1]
        prod_m = st.selectbox("確定製品", options=[p for p in master_df_unique["製品名"].tolist() if master_df_unique[master_df_unique["製品名"]==p]["大カテゴリ"].iloc[0]==cat_m], index=None, placeholder="選択...", format_func=format_name)
        
        msg_slot_m = st.empty()
        if st.button("➕ 登録する", type="primary", use_container_width=True):
            if not prod_m or m_qty is None: msg_slot_m.error("⚠️ 入力漏れがあります。")
            else:
                new_m = pd.DataFrame([{"ID": str(uuid.uuid4())[:6].upper(), "製造予定日": pd.to_datetime(m_date), "大カテゴリ": cat_m, "製品名": prod_m, "ケース数": to_int(m_qty), "登録日時": datetime.now()}])
                append_and_sync("manufactures", new_m)
                msg_slot_m.success(f"✨ 製造登録完了: {prod_m}")
                st.rerun()
