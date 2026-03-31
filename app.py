import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid
from datetime import datetime, timedelta, date
import gspread
from google.oauth2.service_account import Credentials
import numpy as np

# ─────────────────────────────────────────────
# 1. ページ設定
# ─────────────────────────────────────────────
st.set_page_config(page_title="丸実屋 受注在庫管理", page_icon="🏭", layout="wide")

# ─────────────────────────────────────────────
# 2. 強制表示用CSS（文字を見えるようにし、UIを固定する）
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* 全体の背景色と文字色を強制固定 */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #f8f9fa !important;
        color: #1c2a3a !important;
    }

    /* サイドバーの背景色と文字色 */
    [data-testid="stSidebar"] {
        background-color: #0b2239 !important;
    }
    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }

    /* 全ての入力ラベルとテキストを見えるようにする */
    label, p, span, div, .stMarkdown {
        color: #1c2a3a !important;
        font-weight: 500;
    }

    /* ヘッダーデザイン */
    .header-box {
        background: linear-gradient(135deg, #1a6fc4 0%, #0e4d8a 100%);
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    .header-box h1 {
        color: white !important;
        margin: 0;
        font-size: 24px;
    }

    /* カードデザイン */
    .card-box {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #d0d7e3;
        margin-bottom: 20px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }

    /* スケジュールテーブル */
    .sched-table {
        width: 100%;
        border-collapse: collapse;
        background: white;
        color: #1c2a3a;
    }
    .sched-table th {
        background: #1a6fc4;
        color: white !important;
        padding: 8px;
        border: 1px solid #ddd;
    }
    .sched-table td {
        border: 1px solid #ddd;
        padding: 8px;
        vertical-align: top;
    }
    .sched-entry {
        background: #eef4fd;
        border-left: 4px solid #1a6fc4;
        padding: 5px;
        margin-bottom: 5px;
        font-size: 12px;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. パスワード保護
# ─────────────────────────────────────────────
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    
    if not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align:center;'>🏭 丸実屋システム ログイン</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            pwd = st.text_input("パスワードを入力してください", type="password")
            if st.button("ログイン", use_container_width=True, type="primary"):
                if pwd == st.secrets["app_password"]:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("パスワードが正しくありません")
        st.stop()

check_password()

# ─────────────────────────────────────────────
# 4. スプレッドシート接続とデータロード
# ─────────────────────────────────────────────
@st.cache_resource
def get_gspread_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(creds)

client = get_gspread_client()
sheet = client.open_by_url(st.secrets["spreadsheet_url"])

EXPECTED_COLS = {
    "orders": ["ID", "納品予定日", "顧客名", "大カテゴリ", "製品名", "ケース数", "登録日時"],
    "manufactures": ["ID", "製造予定日", "備考", "大カテゴリ", "製品名", "ケース数", "登録日時"],
    "master": ["大カテゴリ", "製品名", "初期在庫数"],
    "customers": ["顧客名", "ふりがな"]
}

@st.cache_data(ttl=10)
def load_all_data(sheet_name):
    try:
        ws = sheet.worksheet(sheet_name)
        data = ws.get_all_values()
        cols = EXPECTED_COLS[sheet_name]
        if len(data) <= 1:
            return pd.DataFrame(columns=cols)
        df = pd.DataFrame(data[1:], columns=data[0])
        # 欠落列の補完
        for c in cols:
            if c not in df.columns: df[c] = ""
        # 型の変換
        if "ケース数" in df.columns: df["ケース数"] = pd.to_numeric(df["ケース数"], errors="coerce").fillna(0).astype(int)
        if "初期在庫数" in df.columns: df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors="coerce").fillna(0).astype(int)
        if "納品予定日" in df.columns: df["納品予定日"] = pd.to_datetime(df["納品予定日"], errors="coerce")
        if "製造予定日" in df.columns: df["製造予定日"] = pd.to_datetime(df["製造予定日"], errors="coerce")
        return df[cols]
    except:
        return pd.DataFrame(columns=EXPECTED_COLS[sheet_name])

def save_to_sheet(sheet_name, df):
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
# 5. メインロジック
# ─────────────────────────────────────────────
orders_df = load_all_data("orders")
manus_df = load_all_data("manufactures")
master_df = load_all_data("master")
cust_df = load_all_data("customers")

CATEGORIES = ["平こん", "つきこん", "糸こん・しらたき", "三角こん", "玉こん", "ダイスこん", "短冊", "国産", "ちぎりこん", "大黒屋", "かねこ", "冷凍耐性", "その他"]

# サイドバーメニュー
with st.sidebar:
    st.markdown("## 🏭 メニュー")
    page = st.radio("画面を選択", ["📋 受注登録", "🏭 製造登録", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"], label_visibility="collapsed")

# ─────────────────────────────────────────────
# 6. 画面描画
# ─────────────────────────────────────────────

# --- 受注登録 ---
if page == "📋 受注登録":
    st.markdown('<div class="header-box"><h1>📋 受注（出荷）登録</h1></div>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="card-box">', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        d_date = col1.date_input("納品予定日", value=date.today() + timedelta(days=1))
        c_name = col2.selectbox("顧客名", sorted(cust_df["顧客名"].unique().tolist()) if not cust_df.empty else ["新規取引"])
        qty = col3.number_input("ケース数", min_value=1, value=1)
        
        sel_cat = st.radio("大カテゴリを選択", CATEGORIES, horizontal=True)
        prods = master_df[master_df["大カテゴリ"] == sel_cat]["製品名"].tolist()
        prod = st.selectbox("製品名を選択", prods if prods else ["該当なし"])
        
        if st.button("✅ 受注を登録する", type="primary", use_container_width=True):
            if prod != "該当なし":
                new_row = pd.DataFrame([{
                    "ID": str(uuid.uuid4())[:6].upper(),
                    "納品予定日": pd.Timestamp(d_date),
                    "顧客名": c_name,
                    "大カテゴリ": sel_cat,
                    "製品名": prod,
                    "ケース数": int(qty),
                    "登録日時": datetime.now().strftime("%Y-%m-%d %H:%M")
                }])
                save_to_sheet("orders", pd.concat([orders_df, new_row], ignore_index=True))
                st.success("登録完了！")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- 製造登録 ---
elif page == "🏭 製造登録":
    st.markdown('<div class="header-box" style="background:linear-gradient(135deg, #0e8c5a 0%, #0a6641 100%);"><h1>🏭 製造（入庫）登録</h1></div>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="card-box">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        m_date = col1.date_input("製造日", value=date.today())
        m_qty = col2.number_input("製造ケース数", min_value=1, value=50)
        
        sel_cat = st.radio("カテゴリを選択", CATEGORIES, horizontal=True)
        prods = master_df[master_df["大カテゴリ"] == sel_cat]["製品名"].tolist()
        prod = st.selectbox("製品を選択", prods if prods else ["該当なし"])
        
        if st.button("➕ 製造データを登録", type="primary", use_container_width=True):
            if prod != "該当なし":
                new_row = pd.DataFrame([{
                    "ID": str(uuid.uuid4())[:6].upper(),
                    "製造予定日": pd.Timestamp(m_date),
                    "備考": "",
                    "大カテゴリ": sel_cat,
                    "製品名": prod,
                    "ケース数": int(m_qty),
                    "登録日時": datetime.now().strftime("%Y-%m-%d %H:%M")
                }])
                save_to_sheet("manufactures", pd.concat([manus_df, new_row], ignore_index=True))
                st.success("製造記録を保存しました。")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- 在庫確認 ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="header-box"><h1>📦 在庫推移とスケジュール</h1></div>', unsafe_allow_html=True)
    
    # 在庫計算ロジック
    today = pd.Timestamp.today().normalize()
    date_range = pd.date_range(today, today + timedelta(days=14))
    
    st.markdown('<div class="card-box">', unsafe_allow_html=True)
    st.subheader("📊 14日間の在庫予測")
    
    # 計算用マトリクス
    inv_data = []
    for _, m in master_df.iterrows():
        prod = m["製品名"]
        curr_inv = int(m["初期在庫数"])
        # 過去分の相殺
        curr_inv += manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] < today)]["ケース数"].sum()
        curr_inv -= orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] < today)]["ケース数"].sum()
        
        row = {"製品名": prod}
        for d in date_range:
            in_q = manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] == d)]["ケース数"].sum()
            out_q = orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] == d)]["ケース数"].sum()
            curr_inv += (in_q - out_q)
            row[d.strftime("%m/%d")] = curr_inv
        inv_data.append(row)
    
    if inv_data:
        id_df = pd.DataFrame(inv_data)
        st.dataframe(id_df.style.applymap(lambda x: 'color: red; font-weight: bold;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# --- 統計分析 ---
elif page == "📊 統計・分析":
    st.markdown('<div class="header-box"><h1>📊 出荷統計分析</h1></div>', unsafe_allow_html=True)
    if not orders_df.empty:
        orders_df["年月"] = orders_df["納品予定日"].dt.strftime("%Y-%m")
        chart_data = orders_df.groupby(["年月", "大カテゴリ"])["ケース数"].sum().reset_index()
        fig = px.bar(chart_data, x="年月", y="ケース数", color="大カテゴリ", title="月別出荷数推移")
        st.plotly_chart(fig, use_container_width=True)

# --- マスタ管理 ---
elif page == "⚙️ マスタ管理":
    st.markdown('<div class="header-box" style="background:#555;"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["📦 製品マスタ", "🏢 顧客マスタ"])
    with t1:
        st.write("製品の初期在庫（棚卸数値）を編集できます。")
        edited_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 製品情報を更新"):
            save_to_sheet("master", edited_m)
            st.success("保存しました。")
    with t2:
        edited_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 顧客情報を更新"):
            save_to_sheet("customers", edited_c)
            st.success("保存しました。")
