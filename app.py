"""
丸実屋 受注・製造・在庫管理アプリ (完全復活・高視認性・コンパクト版)
"""

import os
# テーマ強制設定：ライトモードベースで視認性を固定
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
# 2. 絶対に文字を消さないための安全なCSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&display=swap');
    
    /* 基本設定 */
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Noto Sans JP', sans-serif !important;
        background-color: #F8FAFC !important;
    }

    /* --- サイドバー：濃紺背景 ＆ 巨大メニュー --- */
    [data-testid="stSidebar"] {
        background-color: #0F172A !important;
        border-right: 1px solid #1E293B;
    }
    .sidebar-title {
        color: #FFFFFF !important;
        font-size: 26px !important;
        font-weight: 900 !important;
        margin-bottom: 20px;
        text-align: center;
        display: block;
    }
    /* サイドバーのラジオボタンをボタン風に大きく */
    [data-testid="stSidebar"] div.stRadio > div[role="radiogroup"] > label {
        background-color: #1E293B !important;
        border: 1px solid #334155 !important;
        border-radius: 10px !important;
        padding: 12px 15px !important;
        margin-bottom: 10px !important;
        width: 100% !important;
    }
    [data-testid="stSidebar"] div.stRadio > div[role="radiogroup"] > label:has(input:checked) {
        background-color: #2563EB !important;
        border-color: #3B82F6 !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
    }
    [data-testid="stSidebar"] div.stRadio > div[role="radiogroup"] > label p {
        color: #FFFFFF !important;
        font-size: 18px !important;
        font-weight: 700 !important;
    }

    /* --- レイアウトのコンパクト化 --- */
    .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; }
    
    .compact-header {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        padding: 10px 20px; border-radius: 8px; color: white !important; margin-bottom: 10px;
    }
    .compact-header h1 { color: white !important; font-size: 20px !important; margin: 0 !important; }
    .header-manu { background: linear-gradient(135deg, #064E3B 0%, #10B981 100%); }

    /* 入力エリアの窓（カード） */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF !important;
        border-radius: 10px !important;
        padding: 15px !important;
        border: 1px solid #E2E8F0 !important;
        margin-bottom: 10px !important;
    }

    /* スケジュール表の文字化け・KeyError防止 */
    .sched-table { width: 100%; border-collapse: collapse; background: white; font-size: 14px; }
    .sched-table th { background: #F8FAFC; padding: 8px; border: 1px solid #E2E8F0; text-align: left; }
    .sched-table td { padding: 8px; border: 1px solid #F1F5F9; vertical-align: top; }
    
    .bar-item { position: relative; background: #F1F5F9; border-left: 4px solid #3B82F6; padding: 6px 10px; margin-bottom: 4px; border-radius: 4px; }
    .bar-item.manu { border-left-color: #10B981; }
    .bar-text { font-size: 13px; font-weight: 700; color: #1E293B; }
    .bar-qty { float: right; font-weight: 800; color: #2563EB; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. パスワード認証
# ─────────────────────────────────────────────
def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align:center; color:#1E3A8A; margin-top:50px;'>🏭 丸実屋システム ログイン</h2>", unsafe_allow_html=True)
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
# 4. Googleスプレッドシート連携（爆速・安定ロジック）
# ─────────────────────────────────────────────
@st.cache_resource
def get_client():
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

client = get_client()
sheet = client.open_by_url(st.secrets["spreadsheet_url"])

@st.cache_data(ttl=600)
def load_data(name):
    try:
        ws = sheet.worksheet(name)
        data = ws.get_all_values()
        cols = {"orders":["ID","納品予定日","顧客名","大カテゴリ","製品名","ケース数","備考","登録日時"],
                "manufactures":["ID","製造予定日","備考","大カテゴリ","製品名","ケース数","登録日時"],
                "master":["大カテゴリ","製品名","初期在庫数"],
                "customers":["顧客名","ふりがな"]}[name]
        if len(data) <= 1: return pd.DataFrame(columns=cols)
        df = pd.DataFrame(data[1:], columns=data[0])
        if "ケース数" in df.columns: df["ケース数"] = pd.to_numeric(df["ケース数"], errors='coerce').fillna(0).astype(int)
        if "初期在庫数" in df.columns: df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors='coerce').fillna(0).astype(int)
        for c in ["納品予定日", "製造予定日", "登録日時"]:
            if c in df.columns: df[c] = pd.to_datetime(df[c], errors='coerce')
        return df
    except: return pd.DataFrame()

def save_data(name, df):
    ws = sheet.worksheet(name)
    ws.clear()
    df_str = df.fillna("").astype(str)
    ws.update(values=[df_str.columns.values.tolist()] + df_str.values.tolist(), range_name='A1')
    st.cache_data.clear()

def append_row(name, row_data):
    sheet.worksheet(name).append_row(row_data)
    st.cache_data.clear()

# ─────────────────────────────────────────────
# 5. マスタ ＆ 便利関数
# ─────────────────────────────────────────────
CATEGORIES = ["🍝 つきこん", "🟫 平こん", "🍜 糸こん・しらたき", "🔺 三角こん", "🟤 玉こん", "🎲 ダイスこん", "🏷️ 短冊", "🇯🇵 国産", "🤲 ちぎりこん", "🏮 大黒屋", "🏭 かねこ", "❄️ 冷凍耐性", "📦 その他"]

def format_name(name):
    if not name: return ""
    n = str(name)
    return f"⚫️ {n}" if "黒" in n else f"⚪️ {n}" if "白" in n else f"📦 {n}"

# データロード
orders_df = load_data("orders")
manus_df = load_data("manufactures")
master_df = load_data("master")
cust_df = load_data("customers")

if "success_msg" not in st.session_state: st.session_state.success_msg = None

# ─────────────────────────────────────────────
# 6. サイドバー（巨大メニュー ＆ 濃紺背景）
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown('<span class="sidebar-title">🏭 丸実屋システム</span>', unsafe_allow_html=True)
    page = st.radio("メニュー", ["📋 受注登録 (出庫)", "🏭 製造登録 (入庫)", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"], label_visibility="collapsed")

# ─────────────────────────────────────────────
# 7. 各画面表示
# ─────────────────────────────────────────────

# --- 📋 受注登録 ---
if page == "📋 受注登録 (出庫)":
    st.markdown('<div class="compact-header"><h1>📋 受注（出荷予定）の連続登録</h1></div>', unsafe_allow_html=True)
    with st.container():
        c1, c2, c3 = st.columns([1, 2, 1])
        o_date = c1.date_input("📅 納品日", value=date.today() + timedelta(days=1))
        # 顧客名検索（ひらがななし、漢字変換のみ）
        cust_list = sorted(cust_df["顧客名"].unique().tolist()) if not cust_df.empty else []
        c_name = c2.selectbox("🏢 顧客名（検索）", options=cust_list, index=None, placeholder="検索または選択...")
        qty = c3.number_input("📦 ケース数", min_value=1, value=None, placeholder="数字...")
        
        # 製品検索 ＆ カテゴリ
        search_p = st.text_input("🔍 製品名で検索 (空欄ならカテゴリ優先)", placeholder="製品名の一部を入力...")
        cat_full = st.radio("📂 カテゴリ", CATEGORIES, horizontal=True)
        cat = cat_full.split(" ", 1)[1]
        
        if search_p:
            prods = [p for p in master_df["製品名"].tolist() if search_p in p]
        else:
            prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist() if not master_df.empty else []
            
        prod = st.selectbox("確定製品", options=prods, index=None, placeholder="製品を選んでください", format_func=format_name)
        rem = st.text_input("📝 備考")
        
        if st.button("✅ 受注を登録する", type="primary", use_container_width=True):
            if not prod or not qty: st.error("⚠️ 製品とケース数は必須です")
            else:
                row = [str(uuid.uuid4())[:6].upper(), o_date.strftime('%Y-%m-%d'), c_name if c_name else "未指定", cat, prod, int(qty), rem, datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                append_row("orders", row)
                st.session_state.success_msg = f"✅ 登録完了: {prod} ({qty}cs)"; st.rerun()
        if st.session_state.success_msg: st.success(st.session_state.success_msg); st.session_state.success_msg = None

    st.markdown("### ✏️ かんたん修正（直近5件）")
    if not orders_df.empty:
        recent = orders_df.sort_values("登録日時", ascending=False).head(5)
        edited = st.data_editor(recent, use_container_width=True, hide_index=True, column_config={"納品予定日": st.column_config.DateColumn(format="YYYY-MM-DD"), "登録日時": None}, key="edit_o")
        if st.button("💾 受注修正を保存", type="secondary"):
            save_data("orders", pd.concat([orders_df[~orders_df["ID"].isin(recent["ID"])], edited], ignore_index=True)); st.rerun()

# --- 🏭 製造登録 ---
elif page == "🏭 製造登録 (入庫)":
    st.markdown('<div class="compact-header header-manu"><h1>🏭 製造（入庫）実績の登録</h1></div>', unsafe_allow_html=True)
    with st.container():
        col1, col2 = st.columns(2)
        m_date = col1.date_input("📅 製造日", value=date.today())
        m_qty = col2.number_input("📦 製造数", min_value=1, value=None, placeholder="数字...")
        
        search_p_m = st.text_input("🔍 製品名で検索", placeholder="製品名の一部を入力...")
        cat_full_m = st.radio("📂 カテゴリ", CATEGORIES, horizontal=True, key="m_cat")
        cat_m = cat_full_m.split(" ", 1)[1]
        
        if search_p_m:
            prods_m = [p for p in master_df["製品名"].tolist() if search_p_m in p]
        else:
            prods_m = master_df[master_df["大カテゴリ"] == cat_m]["製品名"].tolist() if not master_df.empty else []
            
        prod_m = st.selectbox("確定製品", options=prods_m, index=None, placeholder="選択してください", format_func=format_name, key="m_prod")
        
        if st.button("➕ 製造を記録する", type="primary", use_container_width=True):
            if not prod_m or not m_qty: st.error("⚠️ 製品と数量は必須です")
            else:
                row_m = [str(uuid.uuid4())[:6].upper(), m_date.strftime('%Y-%m-%d'), "", cat_m, prod_m, int(m_qty), datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                append_row("manufactures", row_m)
                st.session_state.success_msg = f"✅ 製造記録: {prod_m}"; st.rerun()
        if st.session_state.success_msg: st.success(st.session_state.success_msg); st.session_state.success_msg = None

    st.markdown("### ✏️ かんたん修正（直近5件）")
    if not manus_df.empty:
        recent_m = manus_df.sort_values("登録日時", ascending=False).head(5)
        edited_m = st.data_editor(recent_m, use_container_width=True, hide_index=True, column_config={"製造予定日": st.column_config.DateColumn(format="YYYY-MM-DD"), "登録日時": None}, key="edit_m")
        if st.button("💾 製造修正を保存", type="secondary"):
            save_data("manufactures", pd.concat([manus_df[~manus_df["ID"].isin(recent_m["ID"])], edited_m], ignore_index=True)); st.rerun()

# --- 📦 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="compact-header"><h1>📦 在庫推移とスケジュール</h1></div>', unsafe_allow_html=True)
    today = pd.Timestamp.today().normalize()
    
    # KeyError防止のための安全な集計
    o_sum = orders_df.groupby("製品名")["ケース数"].sum() if not orders_df.empty else pd.Series(dtype=int)
    m_sum = manus_df.groupby("製品名")["ケース数"].sum() if not manus_df.empty else pd.Series(dtype=int)
    
    t1, t2 = st.tabs(["📉 現在の在庫数 ＆ 予測", "📅 週間カレンダー ＆ 出力"])
    with t1:
        inv_data = []
        if not master_df.empty:
            for _, r in master_df.iterrows():
                p = r["製品名"]
                cur = int(r["初期在庫数"]) + m_sum.get(p, 0) - o_sum.get(p, 0)
                inv_data.append({"カテゴリ": r["大カテゴリ"], "製品名": format_name(p), "現在庫": cur})
            st.dataframe(pd.DataFrame(inv_data), use_container_width=True, hide_index=True, height=500)

    with t2:
        col_dl1, col_dl2 = st.columns(2)
        today_o = orders_df[orders_df["納品予定日"] == today] if not orders_df.empty else pd.DataFrame()
        if not today_o.empty:
            csv1 = today_o[["顧客名", "製品名", "ケース数", "備考"]].to_csv(index=False, encoding="utf-8-sig")
            col_dl1.download_button("📝 今日の出荷リスト (Excel形式)", data=csv1, file_name=f"出荷_{today.strftime('%Y%m%d')}.csv", type="primary", use_container_width=True)
        
        MAX_CS = 500
        html = '<table class="sched-table"><tr><th style="width:100px;">日付</th><th style="width:45%;">製造</th><th style="width:45%;">出荷</th></tr>'
        for i in range(7):
            d = today + timedelta(days=i)
            m_items = manus_df[manus_df["製造予定日"] == d] if not manus_df.empty else pd.DataFrame()
            o_items = orders_df[orders_df["納品予定日"] == d] if not orders_df.empty else pd.DataFrame()
            m_h = "".join([f'<div class="bar-item manu"><span class="bar-text">{format_name(r["製品名"])}</span><span class="bar-qty">{r["ケース数"]}cs</span></div>' for _,r in m_items.iterrows()])
            o_h = "".join([f'<div class="bar-item"><span class="bar-text">{r["顧客名"]}: {format_name(r["製品名"])}</span><span class="bar-qty">{r["ケース数"]}cs</span></div>' for _,r in o_items.iterrows()])
            html += f'<tr><td><b>{d.strftime("%m/%d")}</b></td><td>{m_h}</td><td>{o_h}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)

# 統計・マスタは前回の安定版を継承
elif page == "📊 統計・分析":
    st.markdown('<div class="compact-header" style="background:#4C1D95;"><h1>📊 出荷傾向分析</h1></div>', unsafe_allow_html=True)
    if not orders_df.empty:
        st.plotly_chart(px.bar(orders_df.groupby("顧客名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False).head(15), x="ケース数", y="顧客名", orientation='h', title="主要顧客TOP15"), use_container_width=True)

elif page == "⚙️ マスタ管理":
    st.markdown('<div class="compact-header" style="background:#374151;"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["📦 製品マスタ", "🏢 顧客マスタ"])
    with t1:
        ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 マスタを保存"): save_data("master", ed_m); st.rerun()
    with t2:
        ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 顧客を保存"): save_data("customers", ed_c); st.rerun()
