"""
丸実屋 受注・製造・在庫管理アプリ (視認性・機能性 完全保証版)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import uuid
from datetime import datetime, timedelta, date
import gspread
from google.oauth2.service_account import Credentials
import numpy as np

# ─────────────────────────────────────────────
# 1. ページ基本設定
# ─────────────────────────────────────────────
st.set_page_config(page_title="丸実屋 受注・在庫管理", page_icon="🏭", layout="wide")

# ─────────────────────────────────────────────
# 2. 【最重要】文字消失を防ぐための強制スタイル設定
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* 全体の背景と文字色を強制固定（ダークモード対策） */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #f0f2f6 !important;
        color: #000000 !important;
    }

    /* 全てのテキスト要素を黒くする */
    .stMarkdown, p, label, span, h1, h2, h3, h4, h5, h6, .stSelectbox, .stTextInput, .stNumberInput, div {
        color: #111111 !important;
        font-family: 'Noto Sans JP', sans-serif !important;
    }

    /* ヘッダー */
    .main-header {
        background: linear-gradient(135deg, #1a6fc4 0%, #0e4d8a 100%);
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .main-header h1 {
        color: #ffffff !important; /* ヘッダー内のみ白 */
        margin: 0 !important;
    }

    /* カード */
    .custom-card {
        background-color: #ffffff !important;
        padding: 25px;
        border-radius: 12px;
        border: 1px solid #d1d5db;
        margin-bottom: 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }

    /* サイドバー */
    [data-testid="stSidebar"] {
        background-color: #0b2239 !important;
    }
    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }

    /* カテゴリ選択ボタン風（Pills） */
    div.stRadio > div[role="radiogroup"] {
        display: flex;
        flex-direction: row;
        flex-wrap: wrap;
        gap: 10px;
    }
    div.stRadio > div[role="radiogroup"] > label {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 25px !important;
        padding: 6px 16px !important;
        color: #1e293b !important;
        cursor: pointer !important;
    }
    div.stRadio > div[role="radiogroup"] label[data-baseweb="radio"] div:first-child {
        display: none !important;
    }

    /* テーブル */
    .styled-table {
        width: 100%;
        border-collapse: collapse;
        background: #fff;
    }
    .styled-table th {
        background: #1a6fc4;
        color: white !important;
        padding: 12px;
        border: 1px solid #0e4d8a;
    }
    .styled-table td {
        border: 1px solid #e2e8f0;
        padding: 10px;
    }
    .entry-badge {
        background: #f1f5f9;
        border-left: 5px solid #1a6fc4;
        padding: 5px 10px;
        margin-bottom: 5px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 13px;
    }
    .entry-badge-manu {
        border-left-color: #0e8c5a;
        background: #f0fdf4;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. パスワード認証
# ─────────────────────────────────────────────
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    
    if not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align:center;'>🏭 丸実屋システム ログイン</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            pwd = st.text_input("パスワード", type="password")
            if st.button("ログイン", use_container_width=True, type="primary"):
                if pwd == st.secrets["app_password"]:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("❌ パスワードが違います")
        st.stop()

check_password()

# ─────────────────────────────────────────────
# 4. スプレッドシート連携
# ─────────────────────────────────────────────
@st.cache_resource
def get_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(creds)

client = get_client()
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
        if len(data) <= 1:
            return pd.DataFrame(columns=cols)
        df = pd.DataFrame(data[1:], columns=data[0])
        for c in cols:
            if c not in df.columns: df[c] = ""
        # 数値・日付変換
        if "ケース数" in df.columns: df["ケース数"] = pd.to_numeric(df["ケース数"], errors='coerce').fillna(0).astype(int)
        if "初期在庫数" in df.columns: df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors='coerce').fillna(0).astype(int)
        if "納品予定日" in df.columns: df["納品予定日"] = pd.to_datetime(df["納品予定日"], errors='coerce')
        if "製造予定日" in df.columns: df["製造予定日"] = pd.to_datetime(df["製造予定日"], errors='coerce')
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
# 5. マスタとアイコン設定
# ─────────────────────────────────────────────
CATEGORIES = ["平こん", "つきこん", "糸こん・しらたき", "三角こん", "玉こん", "ダイスこん", "短冊", "国産", "ちぎりこん", "大黒屋", "かねこ", "冷凍耐性", "その他"]
CAT_ICONS = {"平こん": "🟫", "つきこん": "🍝", "糸こん・しらたき": "🍜", "三角こん": "🔺", "玉こん": "🟤", "ダイスこん": "🎲", "短冊": "🏷️", "国産": "🇯🇵", "ちぎりこん": "🤲", "大黒屋": "🏮", "かねこ": "🏭", "冷凍耐性": "❄️", "その他": "📦"}

def format_name(name):
    if not name: return ""
    name_str = str(name)
    if "黒" in name_str: return f"⚫️ {name_str}"
    if "白" in name_str: return f"⚪️ {name_str}"
    return f"📦 {name_str}"

# データのロード
orders_df = load_data("orders")
manus_df = load_data("manufactures")
master_df = load_data("master")
cust_df = load_data("customers")

# ─────────────────────────────────────────────
# 6. サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏭 丸実屋メニュー")
    page = st.radio("画面切り替え", ["📋 受注登録", "🏭 製造登録", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"], label_visibility="collapsed")

# ─────────────────────────────────────────────
# 7. 各画面の描画
# ─────────────────────────────────────────────

# --- 受注登録 ---
if page == "📋 受注登録":
    st.markdown('<div class="main-header"><h1>📋 受注（出荷）予定の登録</h1></div>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["➕ 新規受注入力", "✏️ 受注一覧・削除"])
    
    with tab1:
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 1, 1])
        o_date = col1.date_input("納品予定日", value=date.today() + timedelta(days=1))
        c_list = ["✏️ 直接入力"] + sorted(cust_df["顧客名"].unique().tolist())
        sel_c = col2.selectbox("顧客名を選択", c_list)
        c_name = col2.text_input("新規顧客名") if sel_c == "✏️ 直接入力" else sel_c
        qty = col3.number_input("出荷ケース数", min_value=1, value=1)
        
        st.write("**📂 カテゴリを選択**")
        cat = st.radio("カテゴリ", CATEGORIES, horizontal=True, label_visibility="collapsed")
        
        prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
        prod = st.selectbox("製品名を選択", prods, format_func=format_name)
        
        if st.button("✅ 受注を登録する", type="primary", use_container_width=True):
            if prod and c_name:
                new_row = pd.DataFrame([{
                    "ID": str(uuid.uuid4())[:6].upper(),
                    "納品予定日": pd.Timestamp(o_date),
                    "顧客名": c_name,
                    "大カテゴリ": cat,
                    "製品名": prod,
                    "ケース数": int(qty),
                    "登録日時": datetime.now().strftime("%Y-%m-%d %H:%M")
                }])
                save_data("orders", pd.concat([orders_df, new_row], ignore_index=True))
                st.toast(f"✅ 登録しました: {c_name} 様宛", icon="📋")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- 製造登録 ---
elif page == "🏭 製造登録":
    st.markdown('<div class="main-header" style="background:linear-gradient(135deg, #0e8c5a 0%, #0a6641 100%);"><h1>🏭 製造（入庫）予定の登録</h1></div>', unsafe_allow_html=True)
    
    st.markdown('<div class="custom-card">', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    m_date = col1.date_input("製造日", value=date.today())
    m_qty = col2.number_input("製造ケース数", min_value=1, value=50)
    
    cat = st.radio("カテゴリ選択", CATEGORIES, horizontal=True)
    prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
    prod = st.selectbox("製品名を選択", prods, format_func=format_name, key="manu_p")
    
    if st.button("➕ 製造を記録する", type="primary", use_container_width=True):
        if prod:
            new_row = pd.DataFrame([{
                "ID": str(uuid.uuid4())[:6].upper(),
                "製造予定日": pd.Timestamp(m_date),
                "大カテゴリ": cat,
                "製品名": prod,
                "ケース数": int(m_qty),
                "登録日時": datetime.now().strftime("%Y-%m-%d %H:%M")
            }])
            save_data("manufactures", pd.concat([manus_df, new_row], ignore_index=True))
            st.toast(f"🏭 製造を登録しました: {prod}", icon="✅")
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# --- 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="main-header"><h1>📦 在庫推移と週間予定</h1></div>', unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["📈 在庫予測", "📅 週間カレンダー"])
    
    with t1:
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        today = pd.Timestamp.today().normalize()
        dates = pd.date_range(today, today + timedelta(days=14))
        
        inv_data = []
        for _, m in master_df.iterrows():
            prod = m["製品名"]
            curr = int(m["初期在庫数"])
            # 過去分計算
            curr += manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] < today)]["ケース数"].sum()
            curr -= orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] < today)]["ケース数"].sum()
            
            row = {"製品名": format_name(prod)}
            for d in dates:
                in_q = manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] == d)]["ケース数"].sum()
                out_q = orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] == d)]["ケース数"].sum()
                curr += (in_q - out_q)
                row[d.strftime("%m/%d")] = curr
            inv_data.append(row)
        
        if inv_data:
            df_inv = pd.DataFrame(inv_data)
            st.dataframe(df_inv.style.applymap(lambda x: 'color: red; font-weight: bold;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with t2:
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        days = [today + timedelta(days=i) for i in range(7)]
        html = '<table class="styled-table"><tr><th>日付</th><th>🏭 製造予定</th><th>📋 出荷予定</th></tr>'
        for d in days:
            m_items = manus_df[manus_df["製造予定日"] == d]
            o_items = orders_df[orders_df["納品予定日"] == d]
            m_h = "".join([f'<div class="entry-badge entry-badge-manu">{format_name(r["製品名"])} ({r["ケース数"]}cs)</div>' for _,r in m_items.iterrows()])
            o_h = "".join([f'<div class="entry-badge">{r["顧客名"]}: {format_name(r["製品名"])} ({r["ケース数"]}cs)</div>' for _,r in o_items.iterrows()])
            html += f'<tr><td><b>{d.strftime("%m/%d")}</b></td><td>{m_h if m_h else "—"}</td><td>{o_h if o_h else "—"}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# --- 統計分析 ---
elif page == "📊 統計・分析":
    st.markdown('<div class="main-header"><h1>📊 出荷実績の統計分析</h1></div>', unsafe_allow_html=True)
    if not orders_df.empty:
        orders_df["年月"] = orders_df["納品予定日"].dt.strftime("%Y-%m")
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        fig = px.bar(orders_df.groupby(["年月","大カテゴリ"])["ケース数"].sum().reset_index(), x="年月", y="ケース数", color="大カテゴリ", barmode="stack", title="月別出荷数推移")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

# --- マスタ管理 ---
elif page == "⚙️ マスタ管理":
    st.markdown('<div class="main-header" style="background:#555;"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["📦 製品・在庫マスタ", "🏢 顧客マスタ"])
    with t1:
        st.write("製品の初期在庫（棚卸数値）を編集できます。")
        ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 製品情報を保存"):
            save_data("master", ed_m)
            st.success("保存しました")
    with t2:
        ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 顧客情報を保存"):
            save_data("customers", ed_c)
            st.success("保存しました")
