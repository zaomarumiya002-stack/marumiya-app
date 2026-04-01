"""
丸実屋 受注・製造・在庫管理アプリ (デザイン刷新・メニュー復旧・完全版)
"""

import os
# Streamlitの基本テーマを強制ライトモードに固定
os.environ["STREAMLIT_THEME_BASE"] = "light"
os.environ["STREAMLIT_THEME_PRIMARY_COLOR"] = "#2563EB"
os.environ["STREAMLIT_THEME_BACKGROUND_COLOR"] = "#F8FAFC"
os.environ["STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR"] = "#FFFFFF"
os.environ["STREAMLIT_THEME_TEXT_COLOR"] = "#1E293B"

import streamlit as st
import pandas as pd
import plotly.express as px
import uuid
from datetime import datetime, timedelta, date
import gspread
from google.oauth2.service_account import Credentials
import io

# ─────────────────────────────────────────────
# 1. ページ基本設定
# ─────────────────────────────────────────────
st.set_page_config(page_title="丸実屋 受注・在庫管理", page_icon="🏭", layout="wide", initial_sidebar_state="expanded")

# ─────────────────────────────────────────────
# 2. 視認性重視・現代的グラデーションCSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');
    
    /* 文字が消えないように全要素の文字色を強制指定 */
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Noto Sans JP', sans-serif !important;
        background-color: #F1F5F9 !important;
    }
    
    /* 濃い紺色で文字をハッキリさせる */
    p, span, label, h1, h2, h3, h4, [data-testid="stMarkdownContainer"] {
        color: #0F172A !important;
    }

    /* メインヘッダー：爽やかなグラデーション */
    .main-header {
        background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%);
        padding: 24px 32px;
        border-radius: 16px;
        color: white !important;
        margin-bottom: 24px;
        box-shadow: 0 10px 15px -3px rgba(37, 99, 235, 0.2);
    }
    .main-header h1 { color: white !important; font-size: 26px !important; font-weight: 900; margin: 0 !important; }
    .manu-header { background: linear-gradient(135deg, #10B981 0%, #059669 100%); box-shadow: 0 10px 15px -3px rgba(16, 185, 129, 0.2); }

    /* サイドバーのカスタマイズ */
    [data-testid="stSidebar"] {
        background-color: #1E293B !important; /* 濃い紺色背景 */
    }
    /* サイドバー内の文字を白に固定 */
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
        color: #F8FAFC !important;
        font-size: 16px !important;
        font-weight: 600 !important;
    }
    
    /* カード風ウィンドウ */
    .content-card {
        background-color: #FFFFFF !important;
        padding: 24px;
        border-radius: 16px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 24px;
    }

    /* カテゴリ選択（巨大ボタン・色反転） */
    div.stRadio > div[role="radiogroup"] {
        display: flex; flex-direction: row; flex-wrap: wrap; gap: 10px;
    }
    div.stRadio > div[role="radiogroup"] > label {
        background-color: #FFFFFF !important;
        border: 2px solid #E2E8F0 !important;
        border-radius: 12px !important;
        padding: 10px 18px !important;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    div.stRadio > div[role="radiogroup"] > label:hover {
        border-color: #3B82F6 !important;
        background-color: #F8FAFC !important;
    }
    /* 選択中のスタイル */
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) {
        background-color: #3B82F6 !important;
        border-color: #3B82F6 !important;
        box-shadow: 0 4px 10px rgba(59, 130, 246, 0.3) !important;
    }
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) p {
        color: #FFFFFF !important;
    }
    /* 丸いポチだけを安全に隠す */
    div.stRadio > div[role="radiogroup"] label div[data-testid="stSelectionControlValue"] {
        display: none !important;
    }

    /* スケジュール表 */
    .sched-table { width: 100%; border-collapse: separate; border-spacing: 0; background: #FFFFFF; border-radius: 12px; overflow: hidden; border: 1px solid #E2E8F0; }
    .sched-table th { background: #F8FAFC; color: #475569 !important; padding: 14px; text-align: left; border-bottom: 2px solid #E2E8F0; }
    .sched-table td { padding: 12px; border-bottom: 1px solid #F1F5F9; vertical-align: top; }
    
    /* 500ケース対応バー */
    .bar-container { position: relative; background: #F1F5F9; border-left: 4px solid #3B82F6; border-radius: 6px; padding: 8px 12px; margin-bottom: 6px; }
    .bar-container.manu { border-left-color: #10B981; }
    .bar-text { font-size: 14px; font-weight: 700; color: #1E293B !important; }
    .bar-qty { float: right; font-weight: 900; color: #2563EB !important; }
    .progress-line { height: 4px; border-radius: 2px; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. パスワード認証
# ─────────────────────────────────────────────
def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align:center; margin-top:50px;'>🏭 丸実屋システム ログイン</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.container():
                pwd = st.text_input("パスワードを入力してください", type="password")
                if st.button("ログイン", use_container_width=True, type="primary"):
                    if pwd == st.secrets["app_password"]:
                        st.session_state["password_correct"] = True
                        st.rerun()
                    else: st.error("❌ パスワードが違います")
        st.stop()

check_password()

# ─────────────────────────────────────────────
# 4. Googleスプレッドシート連携（独立キャッシュ・爆速）
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

@st.cache_data(ttl=600)
def load_orders():
    ws = sheet.worksheet("orders")
    data = ws.get_all_values()
    cols = ["ID", "納品予定日", "顧客名", "大カテゴリ", "製品名", "ケース数", "備考", "登録日時"]
    if len(data) <= 1: return pd.DataFrame(columns=cols)
    df = pd.DataFrame(data[1:], columns=data[0])
    if "備考" not in df.columns: df["備考"] = ""
    df["ケース数"] = pd.to_numeric(df["ケース数"], errors='coerce').fillna(0).astype(int)
    df["納品予定日"] = pd.to_datetime(df["納品予定日"], errors='coerce')
    return df[cols]

@st.cache_data(ttl=600)
def load_manus():
    ws = sheet.worksheet("manufactures")
    data = ws.get_all_values()
    cols = ["ID", "製造予定日", "備考", "大カテゴリ", "製品名", "ケース数", "登録日時"]
    if len(data) <= 1: return pd.DataFrame(columns=cols)
    df = pd.DataFrame(data[1:], columns=data[0])
    df["ケース数"] = pd.to_numeric(df["ケース数"], errors='coerce').fillna(0).astype(int)
    df["製造予定日"] = pd.to_datetime(df["製造予定日"], errors='coerce')
    return df

@st.cache_data(ttl=3600)
def load_master():
    ws = sheet.worksheet("master")
    data = ws.get_all_values()
    if len(data) <= 1: return pd.DataFrame(columns=["大カテゴリ", "製品名", "初期在庫数"])
    df = pd.DataFrame(data[1:], columns=data[0])
    df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors='coerce').fillna(0).astype(int)
    return df

@st.cache_data(ttl=3600)
def load_cust():
    ws = sheet.worksheet("customers")
    data = ws.get_all_values()
    if len(data) <= 1: return pd.DataFrame(columns=["顧客名", "ふりがな"])
    return pd.DataFrame(data[1:], columns=data[0])

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
CATEGORIES = [
    "🍝 つきこん", "🟫 平こん", "🍜 糸こん・しらたき", "🔺 三角こん", 
    "🟤 玉こん", "🎲 ダイスこん", "🏷️ 短冊", "🇯🇵 国産", 
    "🤲 ちぎりこん", "🏮 大黒屋", "🏭 かねこ", "❄️ 冷凍耐性", "📦 その他"
]

def format_name(name):
    if not name: return ""
    n = str(name)
    if "黒" in n: return f"⚫️ {n}"
    if "白" in n: return f"⚪️ {n}"
    return f"📦 {n}"

orders_df = load_orders()
manus_df = load_manus()
master_df = load_master()
cust_df = load_cust()

if "success_msg" not in st.session_state: st.session_state.success_msg = None

# ─────────────────────────────────────────────
# 6. サイドバー（メニュー復旧）
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h2 style='color:white; font-size:24px;'>🏭 丸実屋システム</h2>", unsafe_allow_html=True)
    st.write("---")
    # 安全な標準ラジオボタンを使用
    page = st.radio(
        "メニューを選択", 
        ["📋 受注登録 (出庫)", "🏭 製造登録 (入庫)", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"]
    )

# ─────────────────────────────────────────────
# 7. 各画面の描画
# ─────────────────────────────────────────────

# --- 受注登録 ---
if page == "📋 受注登録 (出庫)":
    st.markdown('<div class="main-header"><h1>📋 受注（出荷予定）の連続登録</h1></div>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1.2, 2.5, 1])
        o_date = col1.date_input("📅 納品予定日", value=date.today() + timedelta(days=1))
        
        # 顧客名：入力して漢字に変換すると候補が出る方式
        cust_names = sorted(cust_df[cust_df["顧客名"].str.strip() != ""]["顧客名"].unique().tolist())
        c_name = col2.selectbox("🏢 顧客名（入力・変換して検索）", options=cust_names, index=None, placeholder="空欄（未指定）")
        qty = col3.number_input("📦 出荷ケース数", min_value=1, value=None, step=1, placeholder="数字を入力")

        remarks = st.text_input("📝 備考（任意・空欄OK）", placeholder="午前着、特記事項など")

        st.write("---")
        st.write("📂 **カテゴリを選択**")
        cat_full = st.radio("カテゴリ", CATEGORIES, horizontal=True, label_visibility="collapsed")
        cat = cat_full.split(" ", 1)[1]
        
        prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
        prod = st.selectbox("📦 製品名を選択", options=prods, index=None, placeholder="製品を選んでください", format_func=format_name)
        
        st.write("")
        if st.button("✅ 受注を登録する", type="primary", use_container_width=True):
            if not prod or not qty:
                st.error("⚠️ 製品とケース数を入力してください。")
            else:
                row_data = [str(uuid.uuid4())[:6].upper(), o_date.strftime('%Y-%m-%d'), c_name if c_name else "未指定", cat, prod, int(qty), remarks, datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                append_row("orders", row_data)
                st.session_state.success_msg = f"✨ 登録完了： {o_date.strftime('%m/%d')} ｜ {c_name if c_name else '未指定'} ｜ {prod} ({qty}cs)"
                st.rerun()

        if st.session_state.success_msg:
            st.success(st.session_state.success_msg)
            st.session_state.success_msg = None
        st.markdown('</div>', unsafe_allow_html=True)

    # ★ 直近5件のかんたん修正機能（ボタンのすぐ下）
    st.markdown("### ✏️ かんたん修正（直近登録5件）")
    recent_o = orders_df.sort_values("登録日時", ascending=False).head(5)
    edited_recent = st.data_editor(recent_o, use_container_width=True, hide_index=True, key="edit_recent_o")
    if st.button("💾 修正内容を保存する", type="primary"):
        # 既存データを削除して新しいデータで上書き
        others = orders_df[~orders_df["ID"].isin(recent_o["ID"])]
        save_data("orders", pd.concat([others, edited_recent], ignore_index=True))
        st.success("データを更新しました"); st.rerun()

# --- 製造登録 ---
elif page == "🏭 製造登録 (入庫)":
    st.markdown('<div class="main-header manu-header"><h1>🏭 製造（入庫）実績の登録</h1></div>', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        m_date = col1.date_input("📅 製造日", value=date.today())
        m_qty = col2.number_input("📦 製造ケース数", min_value=1, value=None, step=10, placeholder="数字を入力")
        st.write("---")
        cat_full = st.radio("カテゴリを選択", CATEGORIES, horizontal=True)
        cat = cat_full.split(" ", 1)[1]
        prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
        prod = st.selectbox("📦 製品名を選択", options=prods, index=None, placeholder="製品を選んでください", format_func=format_name)
        if st.button("➕ 製造データを記録する", type="primary", use_container_width=True):
            if prod and m_qty:
                row_data = [str(uuid.uuid4())[:6].upper(), m_date.strftime('%Y-%m-%d'), "", cat, prod, int(m_qty), datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                append_row("manufactures", row_data)
                st.session_state.success_msg = f"✨ 登録完了：{prod} ({m_qty}cs)"; st.rerun()
        if st.session_state.success_msg:
            st.success(st.session_state.success_msg); st.session_state.success_msg = None
        st.markdown('</div>', unsafe_allow_html=True)

# --- 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="main-header"><h1>📦 在庫推移と週間出荷予定</h1></div>', unsafe_allow_html=True)
    today = pd.Timestamp.today().normalize()
    t1, t2 = st.tabs(["📅 週間カレンダー ＆ 出力", "📉 在庫予測マトリクス"])
    with t1:
        with st.container():
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("📥 ピッキングリスト出力 (Excel対応)")
            col_dl1, col_dl2 = st.columns(2)
            today_orders = orders_df[orders_df["納品予定日"] == today].sort_values("顧客名")
            if not today_orders.empty:
                csv1 = today_orders[["顧客名", "製品名", "ケース数", "備考"]].to_csv(index=False, encoding="utf-8-sig")
                col_dl1.download_button("📝 今日の出荷予定を保存 (CSV)", data=csv1, file_name=f"出荷_{today.strftime('%Y%m%d')}.csv", type="primary")
            week_end = today + timedelta(days=6)
            week_orders = orders_df[(orders_df["納品予定日"] >= today) & (orders_df["納品予定日"] <= week_end)]
            if not week_orders.empty:
                csv2 = week_orders.sort_values(["納品予定日", "顧客名"])[["納品予定日", "顧客名", "製品名", "ケース数", "備考"]].to_csv(index=False, encoding="utf-8-sig")
                col_dl2.download_button("📅 1週間の出荷予定を保存 (CSV)", data=csv2, file_name=f"週間出荷_{today.strftime('%Y%m%d')}.csv")
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.subheader("📆 週間スケジュール")
        MAX_CASES = 500
        html = '<table class="sched-table"><tr><th style="width:120px;">日付</th><th style="width:45%;">🏭 製造</th><th style="width:45%;">📋 出荷</th></tr>'
        for i in range(7):
            d = today + timedelta(days=i)
            m_items = manus_df[manus_df["製造予定日"] == d]
            o_items = orders_df[orders_df["納品予定日"] == d]
            m_h = "".join([f'<div class="bar-container manu"><span class="bar-text">{format_name(r["製品名"])}</span><span class="bar-qty">{r["ケース数"]} cs</span><div class="progress-line" style="background:#10b981; width:{min(100, int(r["ケース数"]/MAX_CASES*100))}%;"></div></div>' for _,r in m_items.iterrows()])
            o_h = "".join([f'<div class="bar-container"><span class="bar-text">{r["顧客名"]}: {format_name(r["製品名"])}</span><span class="bar-qty">{r["ケース数"]} cs</span><div class="progress-line" style="background:#3b82f6; width:{min(100, int(r["ケース数"]/MAX_CASES*100))}%;"></div></div>' for _,r in o_items.iterrows()])
            html += f'<tr><td><b style="font-size:18px;">{d.strftime("%m/%d")}</b><br>{["月","火","水","木","金","土","日"][d.dayofweek]}曜</td><td>{m_h}</td><td>{o_h}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)

    with t2:
        inv_list = []
        for _, m in master_df.iterrows():
            prod = m["製品名"]
            curr = int(m["初期在庫数"])
            curr += manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] < today)]["ケース数"].sum()
            curr -= orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] < today)]["ケース数"].sum()
            row = {"大カテゴリ": m["大カテゴリ"], "製品名": format_name(prod)}
            for i in range(14):
                d = today + timedelta(days=i)
                curr += manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] == d)]["ケース数"].sum()
                curr -= orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] == d)]["ケース数"].sum()
                row[d.strftime("%m/%d")] = curr
            inv_list.append(row)
        if inv_list:
            inv_df = pd.DataFrame(inv_list).sort_values("大カテゴリ")
            st.dataframe(inv_df.style.map(lambda x: 'color: #dc2626; font-weight: 900; background-color: #fee2e2;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True, height=600)

# 他の統計・マスタは既存のまま
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
