"""
丸実屋 受注・製造・在庫管理アプリ (モダンデザイン・完全固定版)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import uuid
from datetime import datetime, timedelta, date
import gspread
from google.oauth2.service_account import Credentials

# ─────────────────────────────────────────────
# 1. ページ基本設定（ライトモード強制）
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="丸実屋 受注・在庫管理", 
    page_icon="🏭", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# 2. 究極のCSS設定（絶対に文字・ボタンを消させないモダンデザイン）
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* Google Fonts の読み込み */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+JP:wght@400;500;700;900&display=swap');

    /* アプリ全体の背景色を固定（Streamlitのダークモードを完全無効化） */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #F8FAFC !important;
        color: #0F172A !important;
        font-family: 'Inter', 'Noto Sans JP', sans-serif !important;
    }

    /* 全てのテキストを濃い色に強制 */
    .stMarkdown, p, span, h1, h2, h3, h4, label, div {
        color: #1E293B !important;
    }

    /* モダンなヘッダー（グラデーション＋シャドウ） */
    .modern-header {
        background: linear-gradient(135deg, #2563EB 0%, #1E40AF 100%);
        padding: 24px 32px;
        border-radius: 16px;
        margin-bottom: 24px;
        box-shadow: 0 10px 25px -5px rgba(37, 99, 235, 0.4);
        display: flex;
        align-items: center;
        gap: 16px;
    }
    .modern-header h1 {
        color: #FFFFFF !important;
        margin: 0 !important;
        font-size: 28px !important;
        font-weight: 900 !important;
        letter-spacing: 0.5px;
    }
    .modern-header.manu {
        background: linear-gradient(135deg, #059669 0%, #047857 100%);
        box-shadow: 0 10px 25px -5px rgba(5, 150, 105, 0.4);
    }

    /* モダンなカード（パネル） */
    .modern-card {
        background-color: #FFFFFF !important;
        padding: 32px;
        border-radius: 16px;
        border: 1px solid #E2E8F0;
        margin-bottom: 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    }

    /* --- ★重要★ カテゴリ選択ボタン（Pills）のデザイン --- */
    div.stRadio > div[role="radiogroup"] {
        display: flex;
        flex-direction: row;
        flex-wrap: wrap;
        gap: 12px;
        padding-top: 8px;
        padding-bottom: 16px;
    }
    /* 未選択状態のボタン */
    div.stRadio > div[role="radiogroup"] > label {
        background-color: #F1F5F9 !important;
        border: 2px solid #CBD5E1 !important;
        border-radius: 9999px !important; /* 完全な丸角 */
        padding: 8px 20px !important;
        color: #475569 !important;
        font-weight: 600 !important;
        cursor: pointer !important;
        transition: all 0.2s ease-in-out !important;
        box-shadow: none !important;
    }
    /* ホバー時（マウスを乗せた時） */
    div.stRadio > div[role="radiogroup"] > label:hover {
        background-color: #E2E8F0 !important;
        border-color: #94A3B8 !important;
        color: #1E293B !important;
    }
    /* ★選択中のボタン（色反転＋青い枠線＋影）★ */
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) {
        background-color: #2563EB !important;
        border-color: #2563EB !important;
        box-shadow: 0 4px 14px 0 rgba(37, 99, 235, 0.39) !important;
    }
    /* 選択中のテキストを白にする */
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) div,
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) p,
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) span {
        color: #FFFFFF !important;
    }
    /* デフォルトの丸いラジオボタン（●）を消す */
    div.stRadio > div[role="radiogroup"] label[data-baseweb="radio"] div:first-child {
        display: none !important;
    }

    /* サイドバーの色固定 */
    [data-testid="stSidebar"] {
        background-color: #0F172A !important;
    }
    [data-testid="stSidebar"] * {
        color: #F8FAFC !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
        background-color: #2563EB !important;
        border-radius: 8px;
    }

    /* モダンなテーブル */
    .modern-table { width: 100%; border-collapse: separate; border-spacing: 0; background: #FFF; border-radius: 12px; overflow: hidden; border: 1px solid #E2E8F0; }
    .modern-table th { background: #F8FAFC; color: #475569 !important; font-weight: 700; padding: 16px; text-align: left; border-bottom: 2px solid #E2E8F0; }
    .modern-table td { padding: 16px; border-bottom: 1px solid #E2E8F0; color: #1E293B !important; }
    
    /* スケジュールのバッジ */
    .badge {
        display: inline-block; padding: 6px 12px; border-radius: 6px;
        font-size: 13px; font-weight: 600; margin-bottom: 6px; margin-right: 6px;
        background: #EFF6FF; color: #1D4ED8 !important; border-left: 4px solid #3B82F6;
    }
    .badge.manu { background: #ECFDF5; color: #047857 !important; border-left-color: #10B981; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. Googleスプレッドシート連携
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
# 4. マスタデータ・アイコン定義
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

if "last_registered" not in st.session_state:
    st.session_state.last_registered = None

# データロード
orders_df = load_data("orders")
manus_df = load_data("manufactures")
master_df = load_data("master")
cust_df = load_data("customers")

# ─────────────────────────────────────────────
# 5. サイドバー (メニュー)
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h2 style='color:white; font-weight:900;'>🏭 丸実屋システム</h2>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    page = st.radio("メニュー", ["📋 受注登録 (出庫)", "🏭 製造登録 (入庫)", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"], label_visibility="collapsed")

# ─────────────────────────────────────────────
# 6. メイン画面の描画
# ─────────────────────────────────────────────

# --- 受注登録 ---
if page == "📋 受注登録 (出庫)":
    st.markdown('<div class="modern-header"><h1>📋 受注（出荷予定）の登録</h1></div>', unsafe_allow_html=True)
    
    if st.session_state.last_registered:
        st.success(f"✨ 直前の登録が完了しました：{st.session_state.last_registered}")
        st.session_state.last_registered = None

    st.markdown('<div class="modern-card">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    
    o_date = col1.date_input("📅 納品予定日", value=date.today() + timedelta(days=1))
    
    # 顧客名：ひらがな検索 ＆ 空欄（未指定）OK
    cust_list = ["(空欄)"] + [f"{r['顧客名']} ({r['ふりがな']})" for _, r in cust_df.iterrows()]
    sel_c_raw = col2.selectbox("🏢 顧客名（ひらがな検索可）", cust_list, index=0)
    c_name = sel_c_raw.split(" (")[0] if sel_c_raw != "(空欄)" else ""
    
    qty = col3.number_input("📦 ケース数", min_value=1, value=1, step=1)

    st.markdown("<h3 style='margin-top:20px; font-size:16px; color:#475569;'>📂 カテゴリを選択</h3>", unsafe_allow_html=True)
    
    # 🌟 カテゴリ選択（ボタン式・色反転）
    sel_cat_full = st.radio("カテゴリ", CATEGORIES, horizontal=True, label_visibility="collapsed")
    sel_cat = sel_cat_full.split(" ")[1] # 絵文字を除去して検索に使用

    prods = master_df[master_df["大カテゴリ"] == sel_cat]["製品名"].tolist()
    prod = st.selectbox("📦 製品名", prods, format_func=format_name)
    
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
            
            # 通知ポップアップ
            st.toast(f"✅ {c_name if c_name else '未指定'} 様宛 / {prod} を登録", icon="📦")
            st.session_state.last_registered = f"{o_date} | {c_name if c_name else '未指定'} | {prod} | {qty}ケース"
            st.rerun()
        else:
            st.error("製品が選択されていません。")
    st.markdown('</div>', unsafe_allow_html=True)

    # 直近の履歴
    st.markdown("### 🕒 最近の登録履歴")
    st.dataframe(orders_df.tail(5).sort_values("登録日時", ascending=False), use_container_width=True, hide_index=True)

# --- 製造登録 ---
elif page == "🏭 製造登録 (入庫)":
    st.markdown('<div class="modern-header manu"><h1>🏭 製造（入庫）実績の登録</h1></div>', unsafe_allow_html=True)
    
    st.markdown('<div class="modern-card">', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    m_date = col1.date_input("📅 製造日", value=date.today())
    m_qty = col2.number_input("📦 製造ケース数", min_value=1, value=50, step=10)
    
    st.markdown("<h3 style='margin-top:20px; font-size:16px; color:#475569;'>📂 カテゴリを選択</h3>", unsafe_allow_html=True)
    sel_cat_full = st.radio("カテゴリ", CATEGORIES, horizontal=True, label_visibility="collapsed", key="m_cat")
    sel_cat = sel_cat_full.split(" ")[1]

    prods = master_df[master_df["大カテゴリ"] == sel_cat]["製品名"].tolist()
    prod = st.selectbox("📦 製品名", prods, format_func=format_name, key="m_prod")
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("➕ 製造データを記録する", type="primary", use_container_width=True):
        if prod:
            new_row = pd.DataFrame([{
                "ID": str(uuid.uuid4())[:6].upper(),
                "製造予定日": str(m_date),
                "備考": "",
                "大カテゴリ": sel_cat,
                "製品名": prod,
                "ケース数": int(m_qty),
                "登録日時": datetime.now().strftime("%Y-%m-%d %H:%M")
            }])
            save_data("manufactures", pd.concat([manus_df, new_row], ignore_index=True))
            st.toast(f"🏭 製造登録完了: {prod}", icon="✅")
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# --- 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="modern-header"><h1>📦 在庫推移・スケジュール</h1></div>', unsafe_allow_html=True)
    
    today = pd.Timestamp.today().normalize()
    dates = pd.date_range(today, today + timedelta(days=14))
    
    st.markdown("### 📉 向こう14日間の在庫予測 (マイナスは赤字)")
    inv_list = []
    for _, m in master_df.iterrows():
        prod = m["製品名"]
        curr = int(m["初期在庫数"])
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
        st.dataframe(pd.DataFrame(inv_list).style.applymap(lambda x: 'color: #DC2626; font-weight: 900; background-color: #FEE2E2;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True)

    st.markdown("### 📅 直近1週間の入出庫カレンダー")
    html = '<table class="modern-table"><tr><th>日付</th><th>🏭 製造予定 (入庫)</th><th>📋 出荷予定 (出庫)</th></tr>'
    for i in range(7):
        d = today + timedelta(days=i)
        m_items = manus_df[manus_df["製造予定日"] == d]
        o_items = orders_df[orders_df["納品予定日"] == d]
        m_h = "".join([f'<div class="badge manu">{format_name(r["製品名"])} ({r["ケース数"]}cs)</div>' for _,r in m_items.iterrows()])
        o_h = "".join([f'<div class="badge">{r["顧客名"]}: {format_name(r["製品名"])} ({r["ケース数"]}cs)</div>' for _,r in o_items.iterrows()])
        html += f'<tr><td><b>{d.strftime("%m/%d")}</b></td><td>{m_h}</td><td>{o_h}</td></tr>'
    st.markdown(html + '</table>', unsafe_allow_html=True)

# --- 統計分析 ---
elif page == "📊 統計・分析":
    st.markdown('<div class="modern-header"><h1>📊 月別出荷実績分析</h1></div>', unsafe_allow_html=True)
    if not orders_df.empty:
        orders_df["年月"] = orders_df["納品予定日"].dt.strftime("%Y-%m")
        fig = px.bar(orders_df.groupby(["年月","大カテゴリ"])["ケース数"].sum().reset_index(), x="年月", y="ケース数", color="大カテゴリ", barmode="stack", title="カテゴリ別 出荷数トレンド")
        st.plotly_chart(fig, use_container_width=True)

# --- マスタ管理 ---
elif page == "⚙️ マスタ管理":
    st.markdown('<div class="modern-header" style="background:linear-gradient(135deg, #475569 0%, #1E293B 100%);"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["📦 製品マスタ（棚卸・初期在庫）", "🏢 顧客マスタ（ふりがな）"])
    with t1:
        st.info("💡 実際の在庫数を「初期在庫数」に入力して保存すると、そこを起点に在庫計算がリセットされます。")
        ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 製品マスタを保存する", type="primary"):
            save_data("master", ed_m)
            st.toast("✅ 製品情報を更新しました")
            st.rerun()
    with t2:
        st.write("「ふりがな」を登録しておくと、受注登録時のドロップダウンでひらがな検索ができるようになります。")
        ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 顧客マスタを保存する", type="primary"):
            save_data("customers", ed_c)
            st.toast("✅ 顧客情報を更新しました")
            st.rerun()
