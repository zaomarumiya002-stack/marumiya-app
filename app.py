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
# 2. 強力なCSS設定 (文字消失防止・ボタンUI・フォント)
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');

    /* 全体の背景と文字色を強制固定 */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #f4f7f9 !important;
        color: #1a202c !important;
    }

    /* 全テキストを黒く固定 */
    .stMarkdown, p, label, span, h1, h2, h3, h4, div {
        color: #1a202c !important;
        font-family: 'Noto Sans JP', sans-serif !important;
    }

    /* ヘッダー */
    .main-header {
        background: linear-gradient(135deg, #1a6fc4 0%, #0e4d8a 100%);
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .main-header h1 { color: white !important; margin: 0 !important; font-size: 24px !important; }

    /* カード */
    .custom-card {
        background-color: #ffffff !important;
        padding: 25px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        margin-bottom: 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }

    /* カテゴリ選択（ボタン形式・選択中の色反転） */
    div.stRadio > div[role="radiogroup"] {
        display: flex;
        flex-direction: row;
        flex-wrap: wrap;
        gap: 10px;
    }
    div.stRadio > div[role="radiogroup"] > label {
        background-color: #ffffff !important;
        border: 2px solid #1a6fc4 !important;
        border-radius: 10px !important;
        padding: 8px 20px !important;
        color: #1a6fc4 !important;
        font-weight: 700 !important;
        cursor: pointer !important;
        transition: all 0.3s;
    }
    /* 選択中のボタンの見た目 */
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) {
        background-color: #1a6fc4 !important;
        color: #ffffff !important;
        box-shadow: 0 4px 10px rgba(26,111,196,0.3);
    }
    div.stRadio > div[role="radiogroup"] label[data-baseweb="radio"] div:first-child {
        display: none !important;
    }

    /* テーブル */
    .styled-table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; }
    .styled-table th { background: #1a6fc4; color: white !important; padding: 12px; text-align: left; }
    .styled-table td { border-bottom: 1px solid #e2e8f0; padding: 12px; }
    
    /* 連続入力用の成功メッセージ用トースト等の調整 */
    .stToast { background-color: #1e8c45 !important; color: white !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. スプレッドシート連携
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

@st.cache_data(ttl=5)
def load_data(sheet_name):
    ws = sheet.worksheet(sheet_name)
    data = ws.get_all_values()
    if len(data) <= 1:
        cols = {"orders":["ID","納品予定日","顧客名","大カテゴリ","製品名","ケース数","登録日時"],
                "manufactures":["ID","製造予定日","備考","大カテゴリ","製品名","ケース数","登録日時"],
                "master":["大カテゴリ","製品名","初期在庫数"],
                "customers":["顧客名","ふりがな"]}[sheet_name]
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(data[1:], columns=data[0])
    if "ケース数" in df.columns: df["ケース数"] = pd.to_numeric(df["ケース数"], errors='coerce').fillna(0).astype(int)
    if "初期在庫数" in df.columns: df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors='coerce').fillna(0).astype(int)
    if "納品予定日" in df.columns: df["納品予定日"] = pd.to_datetime(df["納品予定日"], errors='coerce')
    if "製造予定日" in df.columns: df["製造予定日"] = pd.to_datetime(df["製造予定日"], errors='coerce')
    return df

def save_data(sheet_name, df):
    ws = sheet.worksheet(sheet_name)
    ws.clear()
    df_str = df.astype(str).replace("NaT", "").replace("nan", "")
    ws.update(values=[df_str.columns.values.tolist()] + df_str.values.tolist(), range_name='A1')
    st.cache_data.clear()

# ─────────────────────────────────────────────
# 4. マスタ・設定
# ─────────────────────────────────────────────
CATEGORIES = [
    "🍝 つきこん", "🟫 平こん", "🍜 糸こん", "🔺 三角こん", 
    "🟤 玉こん", "🎲 ダイス", "🏷️ 短冊", "🇯🇵 国産", 
    "🤲 ちぎり", "🏮 大黒屋", "🏭 かねこ", "❄️ 冷凍耐性", "📦 その他"
]

def format_name(name):
    if not name: return ""
    n = str(name)
    if "黒" in n: return f"⚫️ {n}"
    if "白" in n: return f"⚪️ {n}"
    return f"📦 {n}"

# セッション状態の初期化
if "last_registered" not in st.session_state:
    st.session_state.last_registered = None

# データロード
orders_df = load_data("orders")
manus_df = load_data("manufactures")
master_df = load_data("master")
cust_df = load_data("customers")

# ─────────────────────────────────────────────
# 5. メインUI
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h2 style='color:white;'>🏭 丸実屋システム</h2>", unsafe_allow_html=True)
    page = st.radio("メニュー", ["📋 受注登録", "🏭 製造登録", "📦 在庫・スケジュール", "📊 統計分析", "⚙️ マスタ管理"])

# --- 受注登録画面 ---
if page == "📋 受注登録":
    st.markdown('<div class="main-header"><h1>📋 受注（出荷予定）の連続登録</h1></div>', unsafe_allow_html=True)
    
    # 直前の登録結果を表示
    if st.session_state.last_registered:
        st.success(f"✨ 登録完了：{st.session_state.last_registered}")
        st.session_state.last_registered = None

    with st.container():
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1.2, 2, 0.8])
        
        o_date = col1.date_input("📅 納品予定日", value=date.today() + timedelta(days=1))
        
        # 顧客名（ひらがな検索・空欄可能・ドロップダウン）
        cust_list = ["(空欄)"] + [f"{r['顧客名']} ({r['ふりがな']})" for _, r in cust_df.iterrows()]
        sel_c_raw = col2.selectbox("🏢 顧客名を選択（ひらがな検索可）", cust_list, index=0)
        c_name = sel_c_raw.split(" (")[0] if sel_c_raw != "(空欄)" else ""
        
        qty = col3.number_input("📦 ケース数", min_value=1, value=1, step=1)

        st.markdown("### 📂 カテゴリを選択（ボタン）")
        # カテゴリ選択（アイコン付きボタン）
        sel_cat_icon = st.radio("カテゴリ", CATEGORIES, horizontal=True, label_visibility="collapsed")
        sel_cat = sel_cat_icon.split(" ")[1] # アイコンを除去

        # 製品選択（カテゴリで絞り込み）
        prods = master_df[master_df["大カテゴリ"] == sel_cat]["製品名"].tolist()
        prod = st.selectbox("📦 製品名を選択", prods, format_func=format_name, placeholder="製品を選んでください")
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✅ 受注を登録する (続けて入力できます)", type="primary", use_container_width=True):
            if prod:
                new_row = pd.DataFrame([{
                    "ID": str(uuid.uuid4())[:6].upper(),
                    "納品予定日": str(o_date),
                    "顧客名": c_name if c_name else "未指定",
                    "大カテゴリ": sel_cat,
                    "製品名": prod,
                    "ケース数": int(qty),
                    "登録日時": datetime.now().strftime("%Y-%m-%d %H:%M")
                }])
                save_data("orders", pd.concat([orders_df, new_row], ignore_index=True))
                
                # ポップアップ通知
                st.toast(f"登録しました：{c_name if c_name else '未指定'} / {prod}", icon="✅")
                st.session_state.last_registered = f"{o_date} | {c_name if c_name else '未指定'} | {prod} | {qty}ケース"
                st.rerun()
            else:
                st.error("製品を選択してください")
        st.markdown('</div>', unsafe_allow_html=True)

    # 下部に簡易履歴
    st.markdown("### 🕒 最近の登録状況")
    st.dataframe(orders_df.tail(5).sort_values("登録日時", ascending=False), use_container_width=True, hide_index=True)

# --- 製造登録画面 ---
elif page == "🏭 製造登録":
    st.markdown('<div class="main-header" style="background:linear-gradient(135deg, #0e8c5a 0%, #0a6641 100%);"><h1>🏭 製造（入庫）実績の登録</h1></div>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        m_date = col1.date_input("📅 製造日", value=date.today())
        m_qty = col2.number_input("📦 製造ケース数", min_value=1, value=50, step=10)
        
        st.markdown("### 📂 カテゴリを選択")
        sel_cat_icon = st.radio("カテゴリ", CATEGORIES, horizontal=True, label_visibility="collapsed", key="m_cat")
        sel_cat = sel_cat_icon.split(" ")[1]

        prods = master_df[master_df["大カテゴリ"] == sel_cat]["製品名"].tolist()
        prod = st.selectbox("📦 製品名を選択", prods, format_func=format_name, key="m_prod")
        
        if st.button("➕ 製造データを記録", type="primary", use_container_width=True):
            if prod:
                new_row = pd.DataFrame([{
                    "ID": str(uuid.uuid4())[:6].upper(),
                    "製造予定日": str(m_date),
                    "大カテゴリ": sel_cat,
                    "製品名": prod,
                    "ケース数": int(m_qty),
                    "登録日時": datetime.now().strftime("%Y-%m-%d %H:%M")
                }])
                save_data("manufactures", pd.concat([manus_df, new_row], ignore_index=True))
                st.toast(f"製造記録を保存しました：{prod}", icon="🏭")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- 在庫・スケジュール画面 ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="main-header"><h1>📦 在庫推移と週間カレンダー</h1></div>', unsafe_allow_html=True)
    
    today = pd.Timestamp.today().normalize()
    dates = pd.date_range(today, today + timedelta(days=14))
    
    st.markdown("### 📈 14日間の在庫予測（欠品チェック）")
    inv_list = []
    for _, m in master_df.iterrows():
        prod = m["製品名"]
        curr = int(m["初期在庫数"])
        # 過去集計
        curr += manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] < today)]["ケース数"].sum()
        curr -= orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] < today)]["ケース数"].sum()
        
        row = {"製品名": format_name(prod)}
        for d in dates:
            in_q = manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] == d)]["ケース数"].sum()
            out_q = orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] == d)]["ケース数"].sum()
            curr += (in_q - out_q)
            row[d.strftime("%m/%d")] = curr
        inv_list.append(row)
    
    if inv_list:
        st.dataframe(pd.DataFrame(inv_list).style.applymap(lambda x: 'color: red; font-weight: bold;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True)

    st.markdown("### 📅 週間スケジュール")
    html = '<table class="styled-table"><tr><th>日付</th><th>🏭 製造(入)</th><th>📋 出荷(出)</th></tr>'
    for i in range(7):
        d = today + timedelta(days=i)
        m_items = manus_df[manus_df["製造予定日"] == d]
        o_items = orders_df[orders_df["納品予定日"] == d]
        m_h = "".join([f'<div style="background:#f0fdf4; border-left:4px solid #0e8c5a; padding:4px; margin-bottom:4px; font-size:12px;">{format_name(r["製品名"])} ({r["ケース数"]}cs)</div>' for _,r in m_items.iterrows()])
        o_h = "".join([f'<div style="background:#f1f5f9; border-left:4px solid #1a6fc4; padding:4px; margin-bottom:4px; font-size:12px;">{r["顧客名"]}: {format_name(r["製品名"])} ({r["ケース数"]}cs)</div>' for _,r in o_items.iterrows()])
        html += f'<tr><td><b>{d.strftime("%m/%d")}</b></td><td>{m_h}</td><td>{o_h}</td></tr>'
    st.markdown(html + '</table>', unsafe_allow_html=True)

# --- 統計分析画面 ---
elif page == "📊 統計分析":
    st.markdown('<div class="main-header"><h1>📊 月別出荷実績分析</h1></div>', unsafe_allow_html=True)
    if not orders_df.empty:
        orders_df["年月"] = orders_df["納品予定日"].dt.strftime("%Y-%m")
        fig = px.bar(orders_df.groupby(["年月","大カテゴリ"])["ケース数"].sum().reset_index(), x="年月", y="ケース数", color="大カテゴリ", barmode="stack", title="出荷数トレンド")
        st.plotly_chart(fig, use_container_width=True)

# --- マスタ管理画面 ---
elif page == "⚙️ マスタ管理":
    st.markdown('<div class="main-header" style="background:#444;"><h1>⚙️ マスタ管理（製品・顧客）</h1></div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["📦 製品マスタ", "🏢 顧客マスタ"])
    with t1:
        ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 製品マスタを保存"):
            save_data("master", ed_m)
            st.success("製品情報を更新しました")
    with t2:
        st.write("ひらがなを入力しておくと受注登録時に検索しやすくなります。")
        ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 顧客マスタを保存"):
            save_data("customers", ed_c)
            st.success("顧客情報を更新しました")
