import streamlit as st
import pandas as pd
import plotly.express as px
import uuid
from datetime import datetime, timedelta, date
import gspread
from google.oauth2.service_account import Credentials
import numpy as np

# ─────────────────────────────────────────────
# 1. ページ設定（一番最初に記述）
# ─────────────────────────────────────────────
st.set_page_config(page_title="丸実屋 受注・在庫管理", page_icon="🏭", layout="wide")

# ─────────────────────────────────────────────
# 2. 強制スタイル設定（文字消失を絶対に防ぐ）
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* 全体の色設定を「白背景・黒文字」に強制固定 */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #ffffff !important;
        color: #000000 !important;
    }
    /* 全てのテキスト要素の色を黒に上書き */
    .stMarkdown, p, label, span, h1, h2, h3, h4, .stSelectbox, .stTextInput, .stNumberInput, div {
        color: #111111 !important;
    }
    /* ヘッダーのデザインのみリッチに */
    .main-header {
        background: linear-gradient(135deg, #1a6fc4 0%, #0e4d8a 100%);
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 25px;
        color: white !important;
    }
    .main-header h1 { color: white !important; margin: 0; }
    
    /* カードの枠線 */
    .custom-card {
        border: 1px solid #d1d5db;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        background-color: #ffffff;
    }
    
    /* スケジュール表 */
    .styled-table { width: 100%; border-collapse: collapse; }
    .styled-table th { background: #1a6fc4; color: white !important; padding: 10px; border: 1px solid #ddd; }
    .styled-table td { border: 1px solid #ddd; padding: 10px; vertical-align: top; }
    
    /* バッジ */
    .badge {
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: bold;
        border-left: 4px solid #1a6fc4;
        background: #f1f5f9;
        margin-bottom: 4px;
    }
    .badge-manu { border-left-color: #0e8c5a; background: #f0fdf4; }
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
# 4. Googleスプレッドシート連携
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

@st.cache_data(ttl=5)
def load_data(sheet_name):
    try:
        ws = sheet.worksheet(sheet_name)
        data = ws.get_all_values()
        cols = EXPECTED_COLS[sheet_name]
        if len(data) <= 1:
            return pd.DataFrame(columns=cols)
        df = pd.DataFrame(data[1:], columns=data[0])
        # 型の修正
        if "ケース数" in df.columns: df["ケース数"] = pd.to_numeric(df["ケース数"], errors='coerce').fillna(0).astype(int)
        if "初期在庫数" in df.columns: df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors='coerce').fillna(0).astype(int)
        if "納品予定日" in df.columns: df["納品予定日"] = pd.to_datetime(df["納品予定日"], errors='coerce')
        if "製造予定日" in df.columns: df["製造予定日"] = pd.to_datetime(df["製造予定日"], errors='coerce')
        return df
    except:
        return pd.DataFrame(columns=EXPECTED_COLS[sheet_name])

def save_data(sheet_name, df):
    ws = sheet.worksheet(sheet_name)
    ws.clear()
    df_str = df.astype(str).replace("NaT", "").replace("nan", "")
    ws.update(values=[df_str.columns.values.tolist()] + df_str.values.tolist(), range_name='A1')
    st.cache_data.clear()

# ─────────────────────────────────────────────
# 5. マスタとアイコン設定
# ─────────────────────────────────────────────
CATEGORIES = ["平こん", "つきこん", "糸こん・しらたき", "三角こん", "玉こん", "ダイスこん", "短冊", "国産", "ちぎりこん", "大黒屋", "かねこ", "冷凍耐性", "その他"]
CAT_ICONS = {"平こん": "🟫", "つきこん": "🍝", "糸こん・しらたき": "🍜", "三角こん": "🔺", "玉こん": "🟤", "ダイスこん": "🎲", "短冊": "🏷️", "国産": "🇯🇵", "ちぎりこん": "🤲", "大黒屋": "🏮", "かねこ": "🏭", "冷凍耐性": "❄️", "その他": "📦"}

def format_name(name):
    if not name: return ""
    n = str(name)
    if "黒" in n: return f"⚫️ {n}"
    if "白" in n: return f"⚪️ {n}"
    return f"📦 {n}"

# データロード
orders_df = load_data("orders")
manus_df = load_data("manufactures")
master_df = load_data("master")
cust_df = load_data("customers")

# ─────────────────────────────────────────────
# 6. メインUI表示
# ─────────────────────────────────────────────
with st.sidebar:
    st.title("🏭 丸実屋システム")
    page = st.radio("メニュー", ["📋 受注登録", "🏭 製造登録", "📦 在庫・スケジュール", "📊 統計分析", "⚙️ マスタ管理"])

# --- 受注登録 ---
if page == "📋 受注登録":
    st.markdown('<div class="main-header"><h1>📋 受注（出荷）登録</h1></div>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        o_date = col1.date_input("納品予定日", value=date.today() + timedelta(days=1))
        c_name = col2.selectbox("顧客名", sorted(cust_df["顧客名"].unique().tolist()) if not cust_df.empty else ["直販"])
        qty = col3.number_input("ケース数", min_value=1, value=1)
        
        cat = st.selectbox("カテゴリ", CATEGORIES)
        prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
        prod = st.selectbox("製品名", prods, format_func=format_name)
        
        if st.button("✅ 受注を登録する", type="primary", use_container_width=True):
            new_row = pd.DataFrame([{
                "ID": str(uuid.uuid4())[:6].upper(),
                "納品予定日": str(o_date),
                "顧客名": c_name,
                "大カテゴリ": cat,
                "製品名": prod,
                "ケース数": int(qty),
                "登録日時": datetime.now().strftime("%Y-%m-%d %H:%M")
            }])
            save_data("orders", pd.concat([orders_df, new_row], ignore_index=True))
            st.toast(f"✅ 受注を登録しました：{c_name} 様宛", icon="📋")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.subheader("直近の受注一覧")
    st.dataframe(orders_df.tail(10), use_container_width=True)

# --- 製造登録 ---
elif page == "🏭 製造登録":
    st.markdown('<div class="main-header" style="background:linear-gradient(135deg, #0e8c5a 0%, #0a6641 100%);"><h1>🏭 製造（入庫）登録</h1></div>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        m_date = col1.date_input("製造日", value=date.today())
        m_qty = col2.number_input("製造ケース数", min_value=1, value=50)
        
        cat = st.selectbox("カテゴリを選択", CATEGORIES)
        prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
        prod = st.selectbox("製品名", prods, format_func=format_name)
        
        if st.button("➕ 製造を記録する", type="primary", use_container_width=True):
            new_row = pd.DataFrame([{
                "ID": str(uuid.uuid4())[:6].upper(),
                "製造予定日": str(m_date),
                "大カテゴリ": cat,
                "製品名": prod,
                "ケース数": int(m_qty),
                "登録日時": datetime.now().strftime("%Y-%m-%d %H:%M")
            }])
            save_data("manufactures", pd.concat([manus_df, new_row], ignore_index=True))
            st.toast(f"🏭 製造を登録しました：{prod}", icon="✅")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="main-header"><h1>📦 在庫推移と予定</h1></div>', unsafe_allow_html=True)
    
    today = pd.Timestamp.today().normalize()
    dates = pd.date_range(today, today + timedelta(days=14))
    
    # 在庫計算
    st.subheader("📊 14日間の在庫予測")
    inv_list = []
    for _, m in master_df.iterrows():
        prod = m["製品名"]
        curr = int(m["初期在庫数"])
        # 過去集計
        curr += manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] < today)]["ケース数"].sum()
        curr -= orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] < today)]["ケース数"].sum()
        
        row = {"製品名": format_name(prod)}
        for d in dates:
            in_qty = manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] == d)]["ケース数"].sum()
            out_qty = orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] == d)]["ケース数"].sum()
            curr += (in_qty - out_qty)
            row[d.strftime("%m/%d")] = curr
        inv_list.append(row)
    
    if inv_list:
        st.dataframe(pd.DataFrame(inv_list).style.applymap(lambda x: 'color: red; font-weight: bold;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True)

    st.subheader("📆 週間カレンダー")
    html = '<table class="styled-table"><tr><th>日付</th><th>製造予定</th><th>出荷予定</th></tr>'
    for d in [today + timedelta(days=i) for i in range(7)]:
        m_items = manus_df[manus_df["製造予定日"] == d]
        o_items = orders_df[orders_df["納品予定日"] == d]
        m_html = "".join([f'<div class="badge badge-manu">{format_name(r["製品名"])} ({r["ケース数"]}cs)</div>' for _,r in m_items.iterrows()])
        o_html = "".join([f'<div class="badge">{r["顧客名"]}: {format_name(r["製品名"])} ({r["ケース数"]}cs)</div>' for _,r in o_items.iterrows()])
        html += f'<tr><td><b>{d.strftime("%m/%d")}</b></td><td>{m_html}</td><td>{o_html}</td></tr>'
    st.markdown(html + '</table>', unsafe_allow_html=True)

# --- 統計分析 ---
elif page == "📊 統計分析":
    st.markdown('<div class="main-header"><h1>📊 出荷実績の分析</h1></div>', unsafe_allow_html=True)
    if not orders_df.empty:
        orders_df["年月"] = orders_df["納品予定日"].dt.strftime("%Y-%m")
        fig = px.bar(orders_df.groupby(["年月","大カテゴリ"])["ケース数"].sum().reset_index(), x="年月", y="ケース数", color="大カテゴリ", title="月別出荷推移")
        st.plotly_chart(fig, use_container_width=True)

# --- マスタ管理 ---
elif page == "⚙️ マスタ管理":
    st.markdown('<div class="main-header" style="background:#555;"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["📦 製品マスタ", "🏢 顧客マスタ"])
    with t1:
        ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 製品情報を保存"):
            save_data("master", ed_m)
            st.success("保存しました")
    with t2:
        ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 顧客情報を保存"):
            save_data("customers", ed_c)
            st.success("保存しました")
