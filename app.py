"""
丸実屋 受注・製造・在庫管理アプリ (巨大ボタン・視認性最高・安定版)
"""

import os
# テーマ強制設定：ライトモードで視認性を完全保証
os.environ["STREAMLIT_THEME_BASE"] = "light"
os.environ["STREAMLIT_THEME_PRIMARY_COLOR"] = "#2563EB"
os.environ["STREAMLIT_THEME_BACKGROUND_COLOR"] = "#F8FAFC"
os.environ["STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR"] = "#F1F5F9"
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
# 2. 究極の視認性CSS（巨大ボタン・文字サイズ調整）
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&display=swap');
    
    /* 1. 全体のフォントを大きく (PCで見やすいサイズ) */
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Noto Sans JP', sans-serif !important;
        font-size: 18px !important;
    }
    p, span, label, div { color: #0F172A !important; font-size: 18px !important; }
    h1 { font-size: 32px !important; }
    h2 { font-size: 24px !important; color: #1E3A8A !important; }
    h3 { font-size: 20px !important; color: #334155 !important; }

    /* 2. サイドバー：メニューボタンの調整 */
    [data-testid="stSidebar"] { background-color: #F8FAFC !important; border-right: 1px solid #E2E8F0; }
    [data-testid="stSidebar"] .stButton > button {
        height: 60px !important; font-size: 18px !important; border-radius: 12px !important;
    }

    /* 3. ヘッダー */
    .block-container { padding-top: 1.5rem !important; }
    .slim-header {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        padding: 15px 30px; border-radius: 12px; color: white !important; margin-bottom: 20px;
    }
    .slim-header h1 { color: white !important; font-size: 26px !important; font-weight: 900; margin: 0 !important; }

    /* 4. ★ カテゴリ巨大ボタン（マウス操作を楽に） ★ */
    [data-testid="stPills"] { padding: 10px 0 !important; }
    [data-testid="stPills"] button {
        padding: 16px 32px !important; /* 巨大化 */
        font-size: 20px !important; /* 文字を大きく */
        font-weight: 800 !important;
        border-radius: 14px !important;
        border: 2px solid #CBD5E1 !important;
        margin: 4px !important;
    }
    [data-testid="stPills"] button[aria-selected="true"] {
        background-color: #2563EB !important;
        color: #FFFFFF !important;
        border-color: #2563EB !important;
        box-shadow: 0 6px 15px rgba(37, 99, 235, 0.4) !important;
    }

    /* 5. 登録ボタンを下に配置するための余白 */
    .submit-space { margin-top: 40px !important; margin-bottom: 20px !important; }

    /* 6. かんたん修正のタイトル調整 */
    .edit-title { font-size: 22px !important; font-weight: 800; margin-top: 30px !important; display: flex; align-items: center; gap: 10px; }

    /* 7. スケジュール表 */
    .sched-table { width: 100%; border-collapse: collapse; background: white; font-size: 16px; border-radius: 12px; overflow: hidden; }
    .sched-table th { background: #F8FAFC; padding: 12px; border-bottom: 2px solid #E2E8F0; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. パスワード認証
# ─────────────────────────────────────────────
def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align:center; margin-top:80px; color:#1E3A8A;'>🏭 丸実屋システム ログイン</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            pwd = st.text_input("パスワードを入力してください", type="password")
            if st.button("ログイン", use_container_width=True, type="primary"):
                if pwd == st.secrets["app_password"]:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else: st.error("❌ パスワードが違います")
        st.stop()

check_password()

# ─────────────────────────────────────────────
# 4. Googleスプレッドシート連携（高速キャッシュ）
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
        # 型変換
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
if "current_page" not in st.session_state: st.session_state.current_page = "📋 受注登録"

def change_page(pname): st.session_state.current_page = pname

# ─────────────────────────────────────────────
# 6. サイドバー（文字が絶対消えない巨大ボタンメニュー）
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<p style='font-size:22px; font-weight:900; color:#1E3A8A; margin-bottom:20px;'>🏭 丸実屋システム</p>", unsafe_allow_html=True)
    st.write("---")
    menu_items = ["📋 受注登録", "🏭 製造登録", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"]
    for item in menu_items:
        is_active = st.session_state.current_page == item
        if st.button(item, key=f"menu_{item}", use_container_width=True, type="primary" if is_active else "secondary"):
            change_page(item)
            st.rerun()

# ─────────────────────────────────────────────
# 7. 各画面描画
# ─────────────────────────────────────────────
page = st.session_state.current_page

# --- 📋 受注登録 ---
if page == "📋 受注登録":
    st.markdown('<div class="slim-header"><h1>📋 受注（出荷予定）登録</h1></div>', unsafe_allow_html=True)
    with st.container():
        c1, c2, c3 = st.columns([1, 2, 1])
        o_date = c1.date_input("📅 納品日", value=date.today() + timedelta(days=1))
        cust_list = sorted(cust_df["顧客名"].unique().tolist()) if not cust_df.empty else []
        c_name = c2.selectbox("🏢 顧客名（検索）", options=cust_list, index=None, placeholder="空欄（クリックして検索）")
        qty = c3.number_input("📦 ケース数", min_value=1, value=None, step=1, placeholder="数字...")

        st.write("📂 **カテゴリを選択（巨大ボタン）**")
        cat_full = st.pills("カテゴリ", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
        cat = cat_full.split(" ", 1)[1] if cat_full else CATEGORIES[0].split(" ", 1)[1]
        
        sc1, sc2 = st.columns([1.5, 2])
        search_p = sc1.text_input("🔍 製品名検索", placeholder="名称の一部を入力...")
        if search_p:
            prods = [p for p in master_df["製品名"].tolist() if search_p in p]
        else:
            prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist() if not master_df.empty else []
            
        prod = sc2.selectbox("確定製品", options=prods, index=None, placeholder="製品を選んでください", format_func=format_name)
        rem = st.text_input("📝 備考（任意）", placeholder="備考を入力...")
        
        st.markdown('<div class="submit-space"></div>', unsafe_allow_html=True) # ボタンを下にずらす
        if st.button("✅ 受注を登録する", type="primary", use_container_width=True):
            if not prod or not qty: st.error("⚠️ 製品とケース数は必須です")
            else:
                row = [str(uuid.uuid4())[:6].upper(), o_date.strftime('%Y-%m-%d'), c_name if c_name else "未指定", cat, prod, int(qty), rem, datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                append_row("orders", row)
                st.session_state.success_msg = f"✅ 登録完了： {o_date.strftime('%m/%d')} ｜ {prod}"; st.rerun()

        if st.session_state.success_msg:
            st.success(st.session_state.success_msg); st.session_state.success_msg = None

    # かんたん修正（高さを制限してコンパクトに）
    st.markdown('<div class="edit-title">✏️ かんたん修正（直近3件を常時表示）</div>', unsafe_allow_html=True)
    if not orders_df.empty:
        # 表に渡す前に日付型に変換して None 表示を防止
        recent = orders_df.sort_values("登録日時", ascending=False).head(5).copy()
        recent["納品予定日"] = recent["納品予定日"].dt.date
        
        edited = st.data_editor(recent, use_container_width=True, hide_index=True, 
                               height=210, # 約3行分の高さに固定（スクロール発生）
                               column_config={"納品予定日": st.column_config.DateColumn(format="YYYY-MM-DD"), "登録日時": None, "ID": st.column_config.TextColumn(width="small")}, 
                               key="edit_o")
        if st.button("💾 修正内容を保存する"):
            others = orders_df[~orders_df["ID"].isin(recent["ID"])]
            save_data("orders", pd.concat([others, edited], ignore_index=True)); st.rerun()

# --- 🏭 製造登録 ---
elif page == "🏭 製造登録":
    st.markdown('<div class="slim-header" style="background:linear-gradient(135deg, #064E3B 0%, #10B981 100%);"><h1>🏭 製造データの登録</h1></div>', unsafe_allow_html=True)
    with st.container():
        col1, col2 = st.columns([1, 1])
        m_date = col1.date_input("📅 製造日", value=date.today())
        m_qty = col2.number_input("📦 製造ケース数", min_value=1, value=None, placeholder="数字...")
        
        st.write("📂 **カテゴリを選択（巨大ボタン）**")
        cat_full_m = st.pills("カテゴリ製造", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
        cat_m = cat_full_m.split(" ", 1)[1] if cat_full_m else CATEGORIES[0].split(" ", 1)[1]

        sc1_m, sc2_m = st.columns([1.5, 2])
        search_p_m = sc1_m.text_input("🔍 製品名検索", placeholder="名称の一部...", key="sm")
        if search_p_m:
            prods_m = [p for p in master_df["製品名"].tolist() if search_p_m in p]
        else:
            prods_m = master_df[master_df["大カテゴリ"] == cat_m]["製品名"].tolist() if not master_df.empty else []
            
        prod_m = sc2_m.selectbox("確定製品", options=prods_m, index=None, placeholder="選択してください", format_func=format_name, key="selm")
        
        st.markdown('<div class="submit-space"></div>', unsafe_allow_html=True)
        if st.button("➕ 製造を記録する", type="primary", use_container_width=True):
            if not prod_m or not m_qty: st.error("⚠️ 製品と数量は必須です")
            else:
                row_m = [str(uuid.uuid4())[:6].upper(), m_date.strftime('%Y-%m-%d'), "", cat_m, prod_m, int(m_qty), datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                append_row("manufactures", row_m)
                st.session_state.success_msg = f"✅ 登録完了：{prod_m}"; st.rerun()
        if st.session_state.success_msg: st.success(st.session_state.success_msg); st.session_state.success_msg = None

    st.markdown('<div class="edit-title">✏️ かんたん修正</div>', unsafe_allow_html=True)
    if not manus_df.empty:
        recent_m = manus_df.sort_values("登録日時", ascending=False).head(5).copy()
        recent_m["製造予定日"] = recent_m["製造予定日"].dt.date
        edited_m = st.data_editor(recent_m, use_container_width=True, hide_index=True, height=210, key="edit_m")
        if st.button("💾 修正を保存", key="smb"):
            others_m = manus_df[~manus_df["ID"].isin(recent_m["ID"])]
            save_data("manufactures", pd.concat([others_m, edited_m], ignore_index=True)); st.rerun()

# --- 📦 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="slim-header"><h1>📦 在庫予測とスケジュール</h1></div>', unsafe_allow_html=True)
    today = pd.Timestamp.today().normalize()
    t1, t2 = st.tabs(["📉 1ヶ月在庫予測マトリクス", "📅 週間カレンダー"])
    with t1:
        inv_list = []
        o_sum = orders_df.groupby("製品名")["ケース数"].sum() if not orders_df.empty else pd.Series(dtype=int)
        m_sum = manus_df.groupby("製品名")["ケース数"].sum() if not manus_df.empty else pd.Series(dtype=int)
        if not master_df.empty:
            for _, m in master_df.iterrows():
                prod = m["製品名"]
                curr = int(m["初期在庫数"]) + m_sum.get(prod, 0) - o_sum.get(prod, 0)
                row = {"カテゴリ": m["大カテゴリ"], "製品名": format_name(prod), "現在庫": curr}
                temp_stock = curr
                for i in range(1, 31):
                    d_fut = today + timedelta(days=i)
                    d_m = manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] == d_fut)]["ケース数"].sum() if not manus_df.empty else 0
                    d_o = orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] == d_fut)]["ケース数"].sum() if not orders_df.empty else 0
                    temp_stock += (d_m - d_o)
                    row[d_fut.strftime("%m/%d")] = temp_stock
                inv_list.append(row)
        if inv_list:
            inv_df = pd.DataFrame(inv_list).sort_values("カテゴリ")
            st.dataframe(inv_df.style.map(lambda x: 'color: #dc2626; font-weight: 900; background-color: #fee2e2;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True, height=600)
    with t2:
        MAX_CS = 500
        html = '<table class="sched-table"><tr><th style="width:120px;">日付</th><th style="width:45%;">製造</th><th style="width:45%;">出荷</th></tr>'
        for i in range(7):
            d = today + timedelta(days=i)
            m_items = manus_df[manus_df["製造予定日"] == d] if not manus_df.empty else pd.DataFrame()
            o_items = orders_df[orders_df["納品予定日"] == d] if not orders_df.empty else pd.DataFrame()
            m_h = "".join([f'<div style="background:#F0FFF4; border-left:4px solid #10B981; padding:8px; margin-bottom:4px; border-radius:6px;"><span style="font-weight:700;">{format_name(r["製品名"])}</span> <span style="float:right; font-weight:900;">{r["ケース数"]}cs</span></div>' for _,r in m_items.iterrows()])
            o_h = "".join([f'<div style="background:#F0F7FF; border-left:4px solid #2563EB; padding:8px; margin-bottom:4px; border-radius:6px;"><span style="font-weight:700;">{r["顧客名"]}: {format_name(r["製品名"])}</span> <span style="float:right; font-weight:900;">{r["ケース数"]}cs</span></div>' for _,r in o_items.iterrows()])
            html += f'<tr><td><b style="font-size:20px;">{d.strftime("%m/%d")}</b><br>{["月","火","水","木","金","土","日"][d.dayofweek]}曜</td><td>{m_h}</td><td>{o_h}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)

# 統計・マスタ
elif page == "📊 統計・分析":
    st.markdown('<div class="slim-header" style="background:#4C1D95;"><h1>📊 出荷傾向分析</h1></div>', unsafe_allow_html=True)
    if not orders_df.empty:
        st.plotly_chart(px.bar(orders_df.groupby("顧客名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False).head(15), x="ケース数", y="顧客名", orientation='h', title="主要顧客TOP15"), use_container_width=True)

elif page == "⚙️ マスタ管理":
    st.markdown('<div class="slim-header" style="background:#374151;"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["📦 製品マスタ", "🏢 顧客マスタ"])
    with t1:
        ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 保存", key="msave"): save_data("master", ed_m); st.rerun()
    with t2:
        ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 保存", key="csave"): save_data("customers", ed_c); st.rerun()
