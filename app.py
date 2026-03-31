"""
丸実屋 受注・製造・在庫管理アプリ (完全復活・視認性強化版)
=========================================
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid
from datetime import datetime, timedelta, date
import warnings
import gspread
from google.oauth2.service_account import Credentials
import numpy as np

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# 1. ページ設定 & パスワード保護
# ─────────────────────────────────────────────
st.set_page_config(page_title="丸実屋 受注・在庫管理", page_icon="🏭", layout="wide", initial_sidebar_state="expanded")

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align: center; color:#1a6fc4; font-family:sans-serif;'>🏭 丸実屋システム ログイン</h2>", unsafe_allow_html=True)
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
# 2. 強力なCSS設定 (文字消失を絶対に防ぐ)
# ─────────────────────────────────────────────
st.markdown("""
<style>
/* フォントと全体の色（黒に固定） */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    background-color: #f0f3f8 !important;
}

/* すべてのテキストを強制的に濃い色にする */
.stMarkdown, p, label, span, div, h1, h2, h3, .stSelectbox, .stTextInput, .stNumberInput {
    color: #1c2a3a !important;
    font-family: 'Noto Sans JP', sans-serif !important;
}

/* ヘッダーデザイン */
.app-header {
    background: linear-gradient(135deg, #1a6fc4 0%, #0e4d8a 100%) !important;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.app-header h1 {
    color: #ffffff !important; /* ヘッダー内だけは白文字 */
    margin: 0 !important;
    font-size: 24px !important;
    font-weight: 900 !important;
}
.app-header.manu-header {
    background: linear-gradient(135deg, #0e8c5a 0%, #0a6641 100%) !important;
}

/* カードデザイン */
.card {
    background: #ffffff !important;
    border: 1px solid #d0d7e3;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
.card-title {
    font-size: 16px;
    font-weight: 700;
    color: #1a6fc4 !important;
    border-bottom: 2px solid #1a6fc4;
    padding-bottom: 8px;
    margin-bottom: 15px;
}

/* サイドバー */
[data-testid="stSidebar"] {
    background-color: #0b2239 !important;
}
[data-testid="stSidebar"] * {
    color: #ffffff !important;
}
[data-testid="stSidebarNav"] {
    background-color: transparent !important;
}

/* Pills (ラジオボタンをボタン風に) */
div.stRadio > div[role="radiogroup"] {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
}
div.stRadio > div[role="radiogroup"] > label {
    background-color: #ffffff !important;
    border: 1px solid #d0d7e3 !important;
    border-radius: 20px !important;
    padding: 6px 16px !important;
    color: #1c2a3a !important;
    font-weight: 600 !important;
}
div.stRadio > div[role="radiogroup"] label[data-baseweb="radio"] div:first-child {
    display: none !important;
}

/* スケジュール表 */
.sched-table {
    width: 100%;
    border-collapse: collapse;
    background: white;
}
.sched-table th {
    background: #1a6fc4;
    color: white !important;
    padding: 10px;
    border: 1px solid #0e4d8a;
}
.sched-table td {
    border: 1px solid #d8e2ef;
    padding: 8px;
    color: #1c2a3a !important;
}
.sched-entry {
    border-left: 4px solid #1a6fc4;
    background: #eef4fd;
    padding: 5px 8px;
    margin-bottom: 5px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 700;
}
.sched-entry.manu-entry {
    border-left-color: #0e8c5a;
    background: #e8f5f0;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. Googleスプレッドシート接続
# ─────────────────────────────────────────────
@st.cache_resource
def init_connection():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(creds)

client = init_connection()
sheet = client.open_by_url(st.secrets["spreadsheet_url"])

EXPECTED_COLS = {
    "orders": ["ID", "納品予定日", "顧客名", "大カテゴリ", "製品名", "ケース数", "登録日時"],
    "manufactures": ["ID", "製造予定日", "備考", "大カテゴリ", "製品名", "ケース数", "登録日時"],
    "master": ["大カテゴリ", "製品名", "初期在庫数"],
    "customers": ["顧客名", "ふりがな"]
}

@st.cache_data(ttl=10)
def load_data(sheet_name):
    try:
        ws = sheet.worksheet(sheet_name)
        data = ws.get_all_values()
        cols = EXPECTED_COLS[sheet_name]
        if len(data) <= 1: return pd.DataFrame(columns=cols)
        df = pd.DataFrame(data[1:], columns=data[0])
        for c in cols:
            if c not in df.columns: df[c] = ""
        if "ケース数" in df.columns: df["ケース数"] = pd.to_numeric(df["ケース数"], errors="coerce").fillna(0).astype(int)
        if "初期在庫数" in df.columns: df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors="coerce").fillna(0).astype(int)
        if "納品予定日" in df.columns: df["納品予定日"] = pd.to_datetime(df["納品予定日"], errors="coerce")
        if "製造予定日" in df.columns: df["製造予定日"] = pd.to_datetime(df["製造予定日"], errors="coerce")
        return df[cols]
    except:
        return pd.DataFrame(columns=EXPECTED_COLS[sheet_name])

def save_data(sheet_name, df):
    ws = sheet.worksheet(sheet_name)
    ws.clear()
    df_str = df.copy()
    for col in df_str.columns:
        if pd.api.types.is_datetime64_any_dtype(df_str[col]):
            df_str[col] = df_str[col].dt.strftime('%Y-%m-%d')
    df_str = df_str.fillna("").astype(str)
    ws.update(values=[df_str.columns.values.tolist()] + df_str.values.tolist(), range_name='A1')
    st.cache_data.clear()

# ─────────────────────────────────────────────
# 4. マスタ・ロジック
# ─────────────────────────────────────────────
CATEGORIES = ["平こん", "つきこん", "糸こん・しらたき", "三角こん", "玉こん", "ダイスこん", "短冊", "国産", "ちぎりこん", "大黒屋", "かねこ", "冷凍耐性", "その他"]
CAT_COLORS = {"平こん": "#8b5a2b", "つきこん": "#0e8c5a", "糸こん・しらたき": "#7c3db8", "三角こん": "#d97706", "玉こん": "#6b4226", "ダイスこん": "#0e7c8c", "短冊": "#1a6fc4", "国産": "#c41a3a", "ちぎりこん": "#d96606", "大黒屋": "#333333", "かねこ": "#2563a8", "冷凍耐性": "#4a90e2", "その他": "#6b7280"}

def format_product_name(p_name):
    if not p_name: return ""
    p_str = str(p_name)
    if "黒" in p_str: return f"⚫️ {p_str}"
    if "白" in p_str: return f"⚪️ {p_str}"
    return f"📦 {p_str}"

@st.cache_data(ttl=10)
def simulate_inventory(orders_df, manus_df, master_df):
    today = pd.Timestamp.today().normalize()
    date_range = pd.date_range(today, today + timedelta(days=30))
    inv_records, alerts = [], []
    for _, row in master_df.iterrows():
        prod, cat = row["製品名"], row["大カテゴリ"]
        curr_inv = int(row.get("初期在庫数", 0))
        # 過去集計
        curr_inv += manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] < today)]["ケース数"].sum()
        curr_inv -= orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] < today)]["ケース数"].sum()
        for d in date_range:
            curr_inv += manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] == d)]["ケース数"].sum()
            curr_inv -= orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] == d)]["ケース数"].sum()
            inv_records.append({"日付": d, "日付_str": d.strftime("%m/%d"), "大カテゴリ": cat, "製品名": prod, "在庫数": curr_inv})
            if curr_inv < 0: alerts.append({"日付": d, "製品名": prod, "不足数": abs(curr_inv)})
    return pd.DataFrame(inv_records), pd.DataFrame(alerts)

# ロード
orders_df = load_data("orders")
manus_df = load_data("manufactures")
master_df = load_data("master")
cust_df = load_data("customers")
inv_df, alerts_df = simulate_inventory(orders_df, manus_df, master_df)

# ─────────────────────────────────────────────
# 5. UI描画 (初期構成を完全復元)
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h2 style='color:white; font-weight:900;'>🏭 丸実屋システム</h2>", unsafe_allow_html=True)
    page = st.radio("メニュー", ["📋 受注登録", "🏭 製造登録", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"])
    if not alerts_df.empty:
        st.error(f"⚠️ 欠品注意: {len(alerts_df['製品名'].unique())}品目")

# 受注登録
if page == "📋 受注登録":
    st.markdown('<div class="app-header"><h1>📋 受注（出荷）予定の登録</h1></div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["➕ 新規受注を登録", "✏️ 受注データ一覧・削除"])
    with tab1:
        st.markdown('<div class="card"><div class="card-title">📝 受注入力フォーム</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 1, 1])
        d_date = c1.date_input("納品予定日", value=date.today() + timedelta(days=1))
        c_list = ["✏️ 新規・直接入力"] + sorted(cust_df["顧客名"].unique().tolist())
        sel_c = c2.selectbox("顧客名を選択", c_list)
        c_name = c2.text_input("📝 直接入力時のみ") if sel_c == "✏️ 新規・直接入力" else sel_c
        qty = c3.number_input("ケース数", min_value=1, value=1)
        
        sel_cat = st.radio("カテゴリを選択", CATEGORIES, horizontal=True)
        prods = master_df[master_df["大カテゴリ"] == sel_cat]["製品名"].tolist()
        prod = st.selectbox("製品名を選択", prods, format_func=format_product_name)
        
        if st.button("✅ この内容で登録する", type="primary", use_container_width=True):
            if prod and c_name:
                new_row = pd.DataFrame([{"ID": str(uuid.uuid4())[:6].upper(), "納品予定日": pd.Timestamp(d_date), "顧客名": c_name, "大カテゴリ": sel_cat, "製品名": prod, "ケース数": int(qty), "登録日時": datetime.now()}])
                save_data("orders", pd.concat([orders_df, new_row], ignore_index=True))
                st.success(f"登録しました: {c_name} 様宛 {prod}")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with tab2:
        st.dataframe(orders_df.sort_values("納品予定日", ascending=False), use_container_width=True)

# 製造登録
elif page == "🏭 製造登録":
    st.markdown('<div class="app-header manu-header"><h1>🏭 製造（入庫）予定の登録</h1></div>', unsafe_allow_html=True)
    st.markdown('<div class="card"><div class="card-title">📝 製造入力フォーム</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    m_date = c1.date_input("製造予定日", value=date.today())
    m_qty = c2.number_input("製造ケース数", min_value=1, value=50)
    m_note = c3.text_input("備考（ロット等）")
    
    sel_cat = st.radio("カテゴリを選択", CATEGORIES, horizontal=True, key="m_cat")
    prods = master_df[master_df["大カテゴリ"] == sel_cat]["製品名"].tolist()
    prod = st.selectbox("製品名を選択", prods, format_func=format_product_name, key="m_prod")
    
    if st.button("➕ 製造を登録する", type="primary", use_container_width=True):
        if prod:
            new_row = pd.DataFrame([{"ID": str(uuid.uuid4())[:6].upper(), "製造予定日": pd.Timestamp(m_date), "備考": m_note, "大カテゴリ": sel_cat, "製品名": prod, "ケース数": int(m_qty), "登録日時": datetime.now()}])
            save_data("manufactures", pd.concat([manus_df, new_row], ignore_index=True))
            st.success("製造予定を記録しました。")
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# 在庫・スケジュール
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="app-header"><h1>📦 在庫・スケジュール確認</h1></div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["📊 在庫推移表 (14日間)", "📆 週間入出庫スケジュール"])
    with t1:
        st.markdown('<div class="card"><div class="card-title">📅 日別在庫予測</div>', unsafe_allow_html=True)
        if not inv_df.empty:
            pv = inv_df[inv_df["日付"] <= pd.Timestamp.today().normalize() + timedelta(days=14)].pivot_table(index=["大カテゴリ", "製品名"], columns="日付_str", values="在庫数", aggfunc="last").reset_index()
            st.dataframe(pv.style.applymap(lambda x: 'color:red;font-weight:bold;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with t2:
        st.markdown('<div class="card"><div class="card-title">📆 向こう1週間の予定</div>', unsafe_allow_html=True)
        days = [pd.Timestamp.today().normalize() + timedelta(days=i) for i in range(7)]
        html = '<table class="sched-table"><tr><th>日付</th><th>🏭 製造予定 (入庫)</th><th>📋 出荷予定 (出庫)</th></tr>'
        for d in days:
            m_items = manus_df[manus_df["製造予定日"] == d]
            o_items = orders_df[orders_df["納品予定日"] == d]
            m_html = "".join([f'<div class="sched-entry manu-entry">{r["製品名"]} ({r["ケース数"]}cs)</div>' for _,r in m_items.iterrows()])
            o_html = "".join([f'<div class="sched-entry">{r["顧客名"]}: {r["製品名"]} ({r["ケース数"]}cs)</div>' for _,r in o_items.iterrows()])
            html += f'<tr><td>{d.strftime("%m/%d")}</td><td>{m_html}</td><td>{o_html}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# 分析
elif page == "📊 統計・分析":
    st.markdown('<div class="app-header"><h1>📊 出荷実績の分析</h1></div>', unsafe_allow_html=True)
    if not orders_df.empty:
        orders_df["年月"] = orders_df["納品予定日"].dt.strftime("%Y-%m")
        fig = px.bar(orders_df.groupby(["年月","大カテゴリ"])["ケース数"].sum().reset_index(), x="年月", y="ケース数", color="大カテゴリ", color_discrete_map=CAT_COLORS, title="月別出荷数")
        st.plotly_chart(fig, use_container_width=True)

# マスタ
elif page == "⚙️ マスタ管理":
    st.markdown('<div class="app-header" style="background:#444;"><h1>⚙️ マスタ・設定管理</h1></div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["📦 製品・在庫マスタ", "🏢 顧客リスト"])
    with t1:
        st.info("棚卸在庫は「初期在庫数」に記入して保存してください。")
        ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 製品情報を保存"): save_data("master", ed_m); st.rerun()
    with t2:
        ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 顧客リストを保存"): save_data("customers", ed_c); st.rerun()
