"""
丸実屋 受注・製造・在庫管理アプリ (視認性極限重視・コンパクトUI・完全安定版)
"""

import os
# テーマをライトモードに強制固定し、視認性を最大化
os.environ["STREAMLIT_THEME_BASE"] = "light"
os.environ["STREAMLIT_THEME_PRIMARY_COLOR"] = "#2563EB"
os.environ["STREAMLIT_THEME_BACKGROUND_COLOR"] = "#F1F5F9"
os.environ["STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR"] = "#FFFFFF"
os.environ["STREAMLIT_THEME_TEXT_COLOR"] = "#0F172A"

import streamlit as st
import pandas as pd
import plotly.express as px
import uuid
from datetime import datetime, timedelta, date
import gspread
from google.oauth2.service_account import Credentials

# ─────────────────────────────────────────────
# 1. ページ基本設定
# ─────────────────────────────────────────────
st.set_page_config(page_title="丸実屋 受注・在庫管理", page_icon="🏭", layout="wide", initial_sidebar_state="expanded")

# ─────────────────────────────────────────────
# 2. 視認性 ＆ コンパクトレイアウトCSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');
    
    /* 全体のフォントと背景色 */
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Noto Sans JP', sans-serif !important;
        background-color: #F8FAFC !important;
    }

    /* --- サイドバーのデザイン修正（超・重要） --- */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF !important; /* 背景を白にして視認性を最高にする */
        border-right: 1px solid #E2E8F0;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: #1E3A8A !important; /* ロゴ・タイトルを濃い紺色に */
        font-size: 22px !important;
        font-weight: 900 !important;
    }
    [data-testid="stSidebar"] .stRadio label p {
        color: #334155 !important; /* メニューの文字色をハッキリさせる */
        font-size: 16px !important;
        font-weight: 700 !important;
    }
    /* サイドバーの選択中メニューを強調 */
    [data-testid="stSidebar"] .stRadio label:has(input:checked) {
        background-color: #EFF6FF !important;
        border-radius: 8px;
        border: 1px solid #3B82F6;
    }

    /* --- メインコンテンツのコンパクト化 --- */
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0rem !important; }
    
    /* ヘッダーをスリムに */
    .main-header {
        background: linear-gradient(135deg, #1E40AF 0%, #3B82F6 100%);
        padding: 12px 24px;
        border-radius: 10px;
        color: white !important;
        margin-bottom: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .main-header h1 { color: white !important; font-size: 20px !important; font-weight: 800; margin: 0 !important; }
    .manu-header { background: linear-gradient(135deg, #059669 0%, #10B981 100%); }

    /* 入力エリア（カード）の余白を削減 */
    .stContainer {
        background-color: #FFFFFF !important;
        border-radius: 12px !important;
        padding: 16px !important;
        border: 1px solid #E2E8F0 !important;
    }

    /* カテゴリ選択ボタン（巨大化・色反転） */
    div.stRadio > div[role="radiogroup"] { gap: 8px !important; }
    div.stRadio > div[role="radiogroup"] > label {
        background-color: #F8FAFC !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 8px !important;
        padding: 6px 12px !important;
        transition: all 0.2s;
    }
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) {
        background-color: #2563EB !important;
        border-color: #2563EB !important;
    }
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) p {
        color: #FFFFFF !important;
        font-weight: bold;
    }

    /* スケジュール表 */
    .sched-table { width: 100%; border-collapse: collapse; font-size: 14px; background: white; border-radius: 8px; overflow: hidden; }
    .sched-table th { background: #F8FAFC; color: #475569 !important; padding: 8px; border-bottom: 2px solid #E2E8F0; }
    .sched-table td { padding: 8px; border-bottom: 1px solid #F1F5F9; vertical-align: top; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. パスワード認証
# ─────────────────────────────────────────────
def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align:center; margin-top:50px; color:#1E3A8A;'>🏭 丸実屋システム ログイン</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.container():
                pwd = st.text_input("パスワード", type="password")
                if st.button("ログイン", use_container_width=True, type="primary"):
                    if pwd == st.secrets["app_password"]:
                        st.session_state["password_correct"] = True
                        st.rerun()
                    else: st.error("❌ パスワードが違います")
        st.stop()

check_password()

# ─────────────────────────────────────────────
# 4. Googleスプレッドシート連携（爆速キャッシュ）
# ─────────────────────────────────────────────
@st.cache_resource
def get_client():
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

client = get_client()
sheet = client.open_by_url(st.secrets["spreadsheet_url"])

@st.cache_data(ttl=600)
def load_data(sheet_name):
    ws = sheet.worksheet(sheet_name)
    data = ws.get_all_values()
    cols = {"orders":["ID","納品予定日","顧客名","大カテゴリ","製品名","ケース数","備考","登録日時"],
            "manufactures":["ID","製造予定日","備考","大カテゴリ","製品名","ケース数","登録日時"],
            "master":["大カテゴリ","製品名","初期在庫数"],
            "customers":["顧客名","ふりがな"]}[sheet_name]
    if len(data) <= 1: return pd.DataFrame(columns=cols)
    df = pd.DataFrame(data[1:], columns=data[0])
    if "ケース数" in df.columns: df["ケース数"] = pd.to_numeric(df["ケース数"], errors='coerce').fillna(0).astype(int)
    if "初期在庫数" in df.columns: df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors='coerce').fillna(0).astype(int)
    if "納品予定日" in df.columns: df["納品予定日"] = pd.to_datetime(df["納品予定日"], errors='coerce')
    if "製造予定日" in df.columns: df["製造予定日"] = pd.to_datetime(df["製造予定日"], errors='coerce')
    return df

def save_data(sheet_name, df):
    ws = sheet.worksheet(sheet_name)
    ws.clear()
    df_str = df.fillna("").astype(str)
    ws.update(values=[df_str.columns.values.tolist()] + df_str.values.tolist(), range_name='A1')
    st.cache_data.clear()

def append_row(sheet_name, row_data):
    sheet.worksheet(sheet_name).append_row(row_data)
    st.cache_data.clear()

# ─────────────────────────────────────────────
# 5. マスタ定義
# ─────────────────────────────────────────────
CATEGORIES = ["🍝 つきこん", "🟫 平こん", "🍜 糸こん・しらたき", "🔺 三角こん", "🟤 玉こん", "🎲 ダイスこん", "🏷️ 短冊", "🇯🇵 国産", "🤲 ちぎりこん", "🏮 大黒屋", "🏭 かねこ", "❄️ 冷凍耐性", "📦 その他"]

def format_name(name):
    if not name: return ""
    n = str(name)
    if "黒" in n: return f"⚫️ {n}"
    if "白" in n: return f"⚪️ {n}"
    return f"📦 {n}"

orders_df = load_data("orders")
manus_df = load_data("manufactures")
master_df = load_master = load_data("master")
cust_df = load_data("customers")

if "success_msg" not in st.session_state: st.session_state.success_msg = None

# ─────────────────────────────────────────────
# 6. サイドバー（視認性最高設定）
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<p>🏭 丸実屋システム</p>", unsafe_allow_html=True)
    st.write("---")
    page = st.radio("メニュー", ["📋 受注登録 (出庫)", "🏭 製造登録 (入庫)", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"])

# ─────────────────────────────────────────────
# 7. 各画面の描画
# ─────────────────────────────────────────────

# --- 受注登録 ---
if page == "📋 受注登録 (出庫)":
    st.markdown('<div class="main-header"><h1>📋 受注（出荷予定）の連続登録</h1></div>', unsafe_allow_html=True)
    
    with st.container():
        c1, c2, c3 = st.columns([1, 2, 1])
        o_date = c1.date_input("📅 納品日", value=date.today() + timedelta(days=1))
        # 漢字のみリスト。変換して検索。
        cust_names = sorted(cust_df[cust_df["顧客名"].str.strip() != ""]["顧客名"].unique().tolist())
        c_name = c2.selectbox("🏢 顧客名（変換して検索）", options=cust_names, index=None, placeholder="空欄（クリックして検索）")
        qty = c3.number_input("📦 ケース数", min_value=1, value=None, step=1, placeholder="数字を入力")

        remarks = st.text_input("📝 備考（任意・空欄OK）", placeholder="例：午前着、特記事項など")

        st.write("📂 **カテゴリ**")
        cat_full = st.radio("カテゴリ", CATEGORIES, horizontal=True, label_visibility="collapsed")
        cat = cat_full.split(" ", 1)[1]
        
        prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
        prod = st.selectbox("📦 製品名", options=prods, index=None, placeholder="製品を選んでください", format_func=format_name)
        
        if st.button("✅ 受注を登録する", type="primary", use_container_width=True):
            if prod and qty:
                row_data = [str(uuid.uuid4())[:6].upper(), o_date.strftime('%Y-%m-%d'), c_name if c_name else "未指定", cat, prod, int(qty), remarks, datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                append_row("orders", row_data)
                st.session_state.success_msg = f"✨ 登録完了： {o_date.strftime('%m/%d')} ｜ {c_name if c_name else '未指定'} ｜ {prod}"
                st.rerun()

        if st.session_state.success_msg:
            st.success(st.session_state.success_msg)
            st.session_state.success_msg = None

    # ★ かんたん修正機能（直近5件）
    st.markdown("### ✏️ かんたん修正（直近5件）")
    recent_o = orders_df.sort_values("登録日時", ascending=False).head(5)
    edited_recent = st.data_editor(recent_o, use_container_width=True, hide_index=True, key="edit_recent_o")
    if st.button("💾 修正内容を保存する", type="secondary"):
        others = orders_df[~orders_df["ID"].isin(recent_o["ID"])]
        save_data("orders", pd.concat([others, edited_recent], ignore_index=True))
        st.success("データを更新しました"); st.rerun()

# --- 製造登録 ---
elif page == "🏭 製造登録 (入庫)":
    st.markdown('<div class="main-header manu-header"><h1>🏭 製造（入庫）の管理</h1></div>', unsafe_allow_html=True)
    with st.container():
        col1, col2 = st.columns(2)
        m_date = col1.date_input("📅 製造日", value=date.today())
        m_qty = col2.number_input("📦 ケース数", min_value=1, value=None, placeholder="数字を入力")
        cat_full = st.radio("カテゴリ", CATEGORIES, horizontal=True)
        cat = cat_full.split(" ", 1)[1]
        prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
        prod = st.selectbox("📦 製品名", options=prods, index=None, placeholder="製品選択", format_func=format_name)
        if st.button("➕ 製造を記録する", type="primary", use_container_width=True):
            if prod and m_qty:
                row_data = [str(uuid.uuid4())[:6].upper(), m_date.strftime('%Y-%m-%d'), "", cat, prod, int(m_qty), datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                append_row("manufactures", row_data)
                st.session_state.success_msg = f"✅ 登録完了：{prod} ({m_qty}cs)"; st.rerun()
        if st.session_state.success_msg: st.success(st.session_state.success_msg); st.session_state.success_msg = None

    st.markdown("### ✏️ かんたん修正（直近5件）")
    recent_m = manus_df.sort_values("登録日時", ascending=False).head(5)
    edited_m = st.data_editor(recent_m, use_container_width=True, hide_index=True, key="edit_recent_m")
    if st.button("💾 修正内容を保存", type="secondary"):
        others = manus_df[~manus_df["ID"].isin(recent_m["ID"])]
        save_data("manufactures", pd.concat([others, edited_m], ignore_index=True))
        st.success("更新しました"); st.rerun()

# --- 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="main-header"><h1>📦 在庫推移と週間出荷予定</h1></div>', unsafe_allow_html=True)
    today = pd.Timestamp.today().normalize()
    
    col_dl1, col_dl2 = st.columns(2)
    today_orders = orders_df[orders_df["納品予定日"] == today].sort_values("顧客名")
    if not today_orders.empty:
        csv1 = today_orders[["顧客名", "製品名", "ケース数", "備考"]].to_csv(index=False, encoding="utf-8-sig")
        col_dl1.download_button("📝 今日の出荷予定(CSV)", data=csv1, file_name=f"出荷_{today.strftime('%Y%m%d')}.csv", type="primary", use_container_width=True)
    week_orders = orders_df[(orders_df["納品予定日"] >= today) & (orders_df["納品予定日"] <= today + timedelta(days=6))]
    if not week_orders.empty:
        csv2 = week_orders.sort_values(["納品予定日", "顧客名"])[["納品予定日", "顧客名", "製品名", "ケース数", "備考"]].to_csv(index=False, encoding="utf-8-sig")
        col_dl2.download_button("📅 1週間の出荷予定(CSV)", data=csv2, file_name=f"週間出荷_{today.strftime('%Y%m%d')}.csv", use_container_width=True)

    t1, t2 = st.tabs(["📅 週間カレンダー", "📉 在庫予測マトリクス"])
    with t1:
        MAX_CASES = 500
        html = '<table class="sched-table"><tr><th style="width:100px;">日付</th><th style="width:45%;">🏭 製造</th><th style="width:45%;">📋 出荷</th></tr>'
        for i in range(7):
            d = today + timedelta(days=i)
            m_items = manus_df[manus_df["製造予定日"] == d]
            o_items = orders_df[orders_df["納品予定日"] == d]
            m_h = "".join([f'<div class="event-bar manu"><span class="event-text">{format_name(r["製品名"])}</span><span class="event-qty">{r["ケース数"]}cs</span><div style="background:#10b981; height:4px; width:{min(100, int(r["ケース数"]/MAX_CASES*100))}%; margin-top:4px;"></div></div>' for _,r in m_items.iterrows()])
            o_h = "".join([f'<div class="event-bar"><span class="event-text">{r["顧客名"]}: {format_name(r["製品名"])}</span><span class="event-qty">{r["ケース数"]}cs</span><div style="background:#3b82f6; height:4px; width:{min(100, int(r["ケース数"]/MAX_CASES*100))}%; margin-top:4px;"></div></div>' for _,r in o_items.iterrows()])
            html += f'<tr><td><b style="font-size:18px;">{d.strftime("%m/%d")}</b><br>{["月","火","水","木","金","土","日"][d.dayofweek]}曜</td><td>{m_h}</td><td>{o_h}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)
    with t2:
        inv_list = []
        for _, m in master_df.iterrows():
            prod = m["製品名"]
            curr = int(m["初期在庫数"])
            curr += manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] < today)]["ケース数"].sum()
            curr -= orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] < today)]["ケース数"].sum()
            row = {"製品名": format_name(prod)}
            for i in range(14):
                d = today + timedelta(days=i)
                curr += manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] == d)]["ケース数"].sum()
                curr -= orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] == d)]["ケース数"].sum()
                row[d.strftime("%m/%d")] = curr
            inv_list.append(row)
        if inv_list:
            st.dataframe(pd.DataFrame(inv_list).style.map(lambda x: 'color: #dc2626; font-weight: 900; background-color: #fee2e2;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True, height=600)

# その他、統計・マスタはこれまでの安定版を維持
elif page == "📊 統計・分析":
    st.markdown('<div class="main-header" style="background:linear-gradient(135deg, #4C1D95 0%, #8B5CF6 100%);"><h1>📊 分析ダッシュボード</h1></div>', unsafe_allow_html=True)
    if not orders_df.empty:
        col1, col2 = st.columns(2)
        orders_df["年月"] = orders_df["納品予定日"].dt.strftime("%Y-%m")
        col1.plotly_chart(px.bar(orders_df.groupby(["年月","大カテゴリ"])["ケース数"].sum().reset_index(), x="年月", y="ケース数", color="大カテゴリ", barmode="stack", title="出荷推移"), use_container_width=True)
        col2.plotly_chart(px.bar(orders_df.groupby("顧客名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False).head(10), x="ケース数", y="顧客名", orientation='h', title="得意先TOP10"), use_container_width=True)

elif page == "⚙️ マスタ管理":
    st.markdown('<div class="main-header" style="background:#475569;"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["📦 製品マスタ", "🏢 顧客マスタ"])
    with t1:
        ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 製品マスタ保存"): save_data("master", ed_m); st.rerun()
    with t2:
        ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 顧客マスタ保存"): save_data("customers", ed_c); st.rerun()
