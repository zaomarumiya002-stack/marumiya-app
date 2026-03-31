"""
丸実屋 受注・製造・在庫管理アプリ (クラウド完全対応版)
=========================================
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import uuid
from datetime import datetime, timedelta, date
import warnings
import gspread
from google.oauth2.service_account import Credentials

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# ページ設定 & パスワード保護
# ─────────────────────────────────────────────
st.set_page_config(page_title="丸実屋 受注・在庫管理", page_icon="🏭", layout="wide", initial_sidebar_state="expanded")

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align: center; margin-top: 80px; color:#1a6fc4;'>🏭 丸実屋システム ログイン</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            pwd = st.text_input("パスワードを入力", type="password")
            if st.button("ログイン", type="primary", use_container_width=True):
                if pwd == st.secrets["app_password"]:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("❌ パスワードが違います")
        st.stop()

check_password()

# ─────────────────────────────────────────────
# ☁️ Googleスプレッドシート接続
# ─────────────────────────────────────────────
@st.cache_resource
def init_connection():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(creds)

client = init_connection()
spreadsheet_url = st.secrets["spreadsheet_url"]
sheet = client.open_by_url(spreadsheet_url)

# 各シートで必要な項目名の定義（エラー防止用）
SHEET_COLUMNS = {
    "orders": ["ID", "納品予定日", "顧客名", "大カテゴリ", "製品名", "ケース数", "登録日時"],
    "manufactures": ["ID", "製造予定日", "備考", "大カテゴリ", "製品名", "ケース数", "登録日時"],
    "master": ["大カテゴリ", "製品名", "初期在庫数"],
    "customers": ["顧客名", "ふりがな"]
}

@st.cache_data(ttl=5)
def load_data(sheet_name):
    try:
        ws = sheet.worksheet(sheet_name)
        data = ws.get_all_values()
        expected_cols = SHEET_COLUMNS.get(sheet_name, [])
        
        # シートが空、または項目名すらない場合は定義通りの空DataFrameを返す
        if not data or len(data) == 0:
            return pd.DataFrame(columns=expected_cols)
        
        headers = data.pop(0)
        df = pd.DataFrame(data, columns=headers)
        
        # 型変換（データがある場合のみ実行）
        if not df.empty:
            if "ケース数" in df.columns: df["ケース数"] = pd.to_numeric(df["ケース数"], errors="coerce").fillna(0).astype(int)
            if "初期在庫数" in df.columns: df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors="coerce").fillna(0).astype(int)
            if "納品予定日" in df.columns: df["納品予定日"] = pd.to_datetime(df["納品予定日"], errors="coerce")
            if "製造予定日" in df.columns: df["製造予定日"] = pd.to_datetime(df["製造予定日"], errors="coerce")
            if "登録日時" in df.columns: df["登録日時"] = pd.to_datetime(df["登録日時"], errors="coerce")
        
        # 必要な列が欠落している場合に備えて補正
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
                
        return df[expected_cols]
    except Exception:
        return pd.DataFrame(columns=SHEET_COLUMNS.get(sheet_name, []))

def save_data(sheet_name, df):
    ws = sheet.worksheet(sheet_name)
    ws.clear()
    df_str = df.copy()
    # 日付型を文字列に変換
    for col in df_str.select_dtypes(include=['datetime64[ns]']).columns:
        df_str[col] = df_str[col].dt.strftime('%Y-%m-%d')
    df_str = df_str.fillna("")
    ws.update(values=[df_str.columns.values.tolist()] + df_str.values.tolist(), range_name='A1')
    load_data.clear()
    simulate_inventory.clear()

# ─────────────────────────────────────────────
# マスタ定義 & 共通関数
# ─────────────────────────────────────────────
CATEGORIES = ["平こん", "つきこん", "糸こん・しらたき", "三角こん", "玉こん", "ダイスこん", "短冊", "国産", "ちぎりこん", "大黒屋", "かねこ", "冷凍耐性", "その他"]
CAT_ICONS = {"平こん": "🟫", "つきこん": "🍝", "糸こん・しらたき": "🍜", "三角こん": "🔺", "玉こん": "🟤", "ダイスこん": "🎲", "短冊": "🏷️", "国産": "🇯🇵", "ちぎりこん": "🤲", "大黒屋": "🏮", "かねこ": "🏭", "冷凍耐性": "❄️", "その他": "📦"}
CAT_COLORS = {"平こん": "#8b5a2b", "つきこん": "#0e8c5a", "糸こん・しらたき": "#7c3db8", "三角こん": "#d97706", "玉こん": "#6b4226", "ダイスこん": "#0e7c8c", "短冊": "#1a6fc4", "国産": "#c41a3a", "ちぎりこん": "#d96606", "大黒屋": "#333333", "かねこ": "#2563a8", "冷凍耐性": "#4a90e2", "その他": "#6b7280"}

def format_product_name(p_name):
    if not p_name: return ""
    if "（黒）" in str(p_name) or "黒" in str(p_name): return f"⚫️ {p_name}"
    if "（白）" in str(p_name) or "白" in str(p_name): return f"⚪️ {p_name}"
    return f"📦 {p_name}"

@st.cache_data(ttl=5)
def simulate_inventory(orders_df, manus_df, master_df, forecast_days=60):
    # データが空の場合の初期化
    o_tmp = pd.DataFrame(columns=["日付", "製品名", "変動"])
    m_tmp = pd.DataFrame(columns=["日付", "製品名", "変動"])

    if not orders_df.empty:
        o_tmp = orders_df[["納品予定日", "製品名", "ケース数"]].copy().dropna(subset=["製品名"])
        o_tmp.columns = ["日付", "製品名", "ケース数"]
        o_tmp["変動"] = -o_tmp["ケース数"]

    if not manus_df.empty:
        m_tmp = manus_df[["製造予定日", "製品名", "ケース数"]].copy().dropna(subset=["製品名"])
        m_tmp.columns = ["日付", "製品名", "ケース数"]
        m_tmp["変動"] = m_tmp["ケース数"]

    events = pd.concat([o_tmp[["日付", "製品名", "変動"]], m_tmp[["日付", "製品名", "変動"]]])
    events["日付"] = pd.to_datetime(events["日付"]).dt.normalize()

    today = pd.Timestamp.today().normalize()
    date_range = pd.date_range(today, today + timedelta(days=forecast_days))

    inv_records, alerts = [], []

    # マスタが空の場合は処理をスキップ
    if master_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    for _, row in master_df.iterrows():
        prod, cat = row["製品名"], row["大カテゴリ"]
        init_inv = int(row.get("初期在庫数", 0))
        prod_events = events[events["製品名"] == prod]
        past_events = prod_events[prod_events["日付"] < today]
        current_inv = init_inv + past_events["変動"].sum()
        future_events = prod_events[prod_events["日付"] >= today].groupby("日付")["変動"].sum()

        for d in date_range:
            chg = future_events.get(d, 0)
            current_inv += chg
            inv_records.append({"日付": d, "日付_str": d.strftime("%m/%d"), "大カテゴリ": cat, "製品名": prod, "在庫数": current_inv})
            if current_inv < 0:
                alerts.append({"日付": d, "製品名": prod, "不足数": abs(current_inv), "カテゴリ": cat})

    return pd.DataFrame(inv_records), pd.DataFrame(alerts)

# ── データのロード ──
orders_df = load_data("orders")
manus_df = load_data("manufactures")
master_df = load_data("master")
cust_df = load_data("customers")

# 製品マスタが空なら初期化（初回起動用）
if master_df.empty:
    default_prods = {"つきこん": ["つきこん（黒）1kg"], "平こん": ["板こん（黒）1kg"]}
    master_df = pd.DataFrame([{"大カテゴリ": k, "製品名": p, "初期在庫数": 0} for k, v in default_prods.items() for p in v])
    save_data("master", master_df)

inv_df, alerts_df = simulate_inventory(orders_df, manus_df, master_df)

# ─────────────────────────────────────────────
# メイン UI
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<div style='text-align:center; padding:10px;'><h3>🏭 丸実屋 システム</h3></div>", unsafe_allow_html=True)
    page = st.radio("メニュー", ["📋 受注登録 (出庫)", "🏭 製造登録 (入庫)", "📦 スケジュール・在庫確認", "📊 統計・分析", "⚙️ マスタ管理", "📖 使い方ガイド"], label_visibility="collapsed")
    
    if not alerts_df.empty:
        st.error(f"⚠️ 欠品アラート: {len(alerts_df.groupby('製品名'))}品目")
    else:
        st.success("✅ 欠品の予定なし")

# --- 各ページの表示 (以下、前回のUIロジックと同様ですがデータ保存先をスプレッドシートに修正) ---

if page == "📋 受注登録 (出庫)":
    st.markdown('<div class="app-header"><h1>📋 受注登録</h1></div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["➕ 新規受注", "✏️ 個別編集"])
    
    with tab1:
        c1, c2, c3 = st.columns([1.5, 2, 1])
        d_date = c1.date_input("納品予定日", value=date.today() + timedelta(days=1))
        
        # 顧客選択
        cust_list = ["✏️ 直接入力"] + cust_df["顧客名"].tolist()
        sel_cust = c2.selectbox("顧客名", cust_list)
        c_name = c2.text_input("新規顧客名") if sel_cust == "✏️ 直接入力" else sel_cust
        
        cases = c3.number_input("ケース数", min_value=1, value=1)
        
        cat = st.radio("カテゴリ", CATEGORIES, horizontal=True)
        prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
        prod = st.selectbox("製品名", prods, format_func=format_product_name)
        
        if st.button("✅ 登録する", type="primary", use_container_width=True):
            if prod and c_name:
                new_id = "O-" + str(uuid.uuid4())[:6].upper()
                new_row = pd.DataFrame([{"ID": new_id, "納品予定日": pd.Timestamp(d_date), "顧客名": c_name, "大カテゴリ": cat, "製品名": prod, "ケース数": int(cases), "登録日時": pd.Timestamp.now()}])
                save_data("orders", pd.concat([orders_df, new_row], ignore_index=True))
                st.success(f"登録完了: {prod}")
                st.rerun()

    with tab2:
        st.write("直近の受注50件")
        st.dataframe(orders_df.tail(50), use_container_width=True)

elif page == "🏭 製造登録 (入庫)":
    st.markdown('<div class="app-header manu-header"><h1>🏭 製造登録</h1></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1.5, 1.2, 2.3])
    m_date = c1.date_input("製造予定日", value=date.today())
    m_cases = c2.number_input("ケース数", min_value=1, value=50)
    m_note = c3.text_input("備考")
    
    cat = st.radio("カテゴリ", CATEGORIES, horizontal=True)
    prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
    prod = st.selectbox("製品名", prods, format_func=format_product_name)
    
    if st.button("➕ 登録する", type="primary", use_container_width=True):
        new_id = "M-" + str(uuid.uuid4())[:6].upper()
        new_row = pd.DataFrame([{"ID": new_id, "製造予定日": pd.Timestamp(m_date), "備考": m_note, "大カテゴリ": cat, "製品名": prod, "ケース数": int(m_cases), "登録日時": pd.Timestamp.now()}])
        save_data("manufactures", pd.concat([manus_df, new_row], ignore_index=True))
        st.success(f"製造登録完了: {prod}")
        st.rerun()

elif page == "📦 スケジュール・在庫確認":
    st.markdown('<div class="app-header"><h1>📦 在庫・スケジュール確認</h1></div>', unsafe_allow_html=True)
    if inv_df.empty:
        st.warning("データがありません。受注または製造を登録してください。")
    else:
        st.write("### 向こう2週間の在庫推移")
        pivot_df = inv_df.pivot_table(index=["大カテゴリ", "製品名"], columns="日付_str", values="在庫数", aggfunc='last').reset_index()
        st.dataframe(pivot_df, use_container_width=True)

elif page == "📊 統計・分析":
    st.markdown('<div class="app-header"><h1>📊 月別出荷分析</h1></div>', unsafe_allow_html=True)
    if not orders_df.empty:
        orders_df["年月"] = orders_df["納品予定日"].dt.strftime("%Y-%m")
        monthly = orders_df.groupby("年月")["ケース数"].sum().reset_index()
        fig = px.bar(monthly, x="年月", y="ケース数", title="月別出荷合計")
        st.plotly_chart(fig, use_container_width=True)

elif page == "⚙️ マスタ管理":
    st.markdown('<div class="app-header"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    m_tab1, m_tab2 = st.tabs(["📦 製品マスタ", "🏢 顧客マスタ"])
    with m_tab1:
        edited_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True)
        if st.button("製品マスタを保存"): save_data("master", edited_m); st.rerun()
    with m_tab2:
        edited_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True)
        if st.button("顧客マスタを保存"): save_data("customers", edited_c); st.rerun()

elif page == "📖 使い方ガイド":
    st.markdown('<div class="app-header guide-header"><h1>📖 使い方ガイド</h1></div>', unsafe_allow_html=True)
    st.info("左メニューから操作を選んでください。受注＝在庫減、製造＝在庫増となります。")
