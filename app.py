"""
丸実屋 受注・製造・在庫管理アプリ (文字消失完全防止・公式機能ボタン化・爆速版)
"""

import os
# Streamlitのテーマを強制的に「見やすいライトモード」に固定（安全な配色設定）
os.environ["STREAMLIT_THEME_BASE"] = "light"
os.environ["STREAMLIT_THEME_PRIMARY_COLOR"] = "#2563EB"
os.environ["STREAMLIT_THEME_BACKGROUND_COLOR"] = "#E2E8F0" # 全体の背景は淡いグレー
os.environ["STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR"] = "#FFFFFF" # サイドバーなどは白

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
# 2. 超安全なCSS（絶対に文字やボタンを隠さない）
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* 全体のフォント */
    html, body, [class*="css"] {
        font-family: 'Noto Sans JP', sans-serif !important;
    }

    /* メインヘッダー（青グラデーション） */
    .main-header {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        padding: 24px;
        border-radius: 12px;
        color: white;
        margin-bottom: 24px;
        box-shadow: 0 4px 10px rgba(59, 130, 246, 0.3);
    }
    .main-header h1 { color: white !important; margin: 0; font-size: 26px; font-weight: bold; }
    .manu-header { background: linear-gradient(135deg, #064E3B 0%, #10B981 100%); box-shadow: 0 4px 10px rgba(16, 185, 129, 0.3); }

    /* サイドバーの色を紺色に上書き */
    [data-testid="stSidebar"] {
        background-color: #0F172A !important;
    }
    [data-testid="stSidebar"] * {
        color: #F8FAFC !important;
    }

    /* 視覚的スケジュール表 */
    .sched-table { width: 100%; border-collapse: separate; border-spacing: 0; background: #FFFFFF; border-radius: 8px; border: 1px solid #CBD5E1; overflow: hidden;}
    .sched-table th { background: #F1F5F9; color: #334155 !important; padding: 12px; text-align: left; border-bottom: 2px solid #E2E8F0; }
    .sched-table td { padding: 12px; border-bottom: 1px solid #E2E8F0; vertical-align: top; }
    
    .event-bar { position: relative; background: #F1F5F9; border-left: 5px solid #3B82F6; border-radius: 6px; padding: 10px; margin-bottom: 8px; z-index: 1; }
    .event-bar.manu { border-left-color: #10B981; }
    .event-bg { position: absolute; top: 0; left: 0; height: 100%; background: #DBEAFE; z-index: -1; }
    .event-bar.manu .event-bg { background: #D1FAE5; }
    .event-text { font-size: 14px; font-weight: 700; color: #0F172A; }
    .event-qty { float: right; font-weight: 900; color: #1D4ED8; font-size: 15px; }
    .event-bar.manu .event-qty { color: #047857; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. パスワード認証
# ─────────────────────────────────────────────
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    
    if not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align:center; margin-top:50px;'>🏭 丸実屋システム ログイン</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.container(border=True):
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
# 4. スプレッドシート連携（独立キャッシュで爆速化）
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
    data = sheet.worksheet("orders").get_all_values()
    cols = ["ID", "納品予定日", "顧客名", "大カテゴリ", "製品名", "ケース数", "登録日時"]
    if len(data) <= 1: return pd.DataFrame(columns=cols)
    df = pd.DataFrame(data[1:], columns=data[0])
    df["ケース数"] = pd.to_numeric(df["ケース数"], errors='coerce').fillna(0).astype(int)
    df["納品予定日"] = pd.to_datetime(df["納品予定日"], errors='coerce')
    return df

@st.cache_data(ttl=600)
def load_manus():
    data = sheet.worksheet("manufactures").get_all_values()
    cols = ["ID", "製造予定日", "備考", "大カテゴリ", "製品名", "ケース数", "登録日時"]
    if len(data) <= 1: return pd.DataFrame(columns=cols)
    df = pd.DataFrame(data[1:], columns=data[0])
    df["ケース数"] = pd.to_numeric(df["ケース数"], errors='coerce').fillna(0).astype(int)
    df["製造予定日"] = pd.to_datetime(df["製造予定日"], errors='coerce')
    return df

@st.cache_data(ttl=3600)
def load_master():
    data = sheet.worksheet("master").get_all_values()
    cols = ["大カテゴリ", "製品名", "初期在庫数"]
    if len(data) <= 1: return pd.DataFrame(columns=cols)
    df = pd.DataFrame(data[1:], columns=data[0])
    df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors='coerce').fillna(0).astype(int)
    return df

@st.cache_data(ttl=3600)
def load_cust():
    data = sheet.worksheet("customers").get_all_values()
    cols = ["顧客名", "ふりがな"]
    if len(data) <= 1: return pd.DataFrame(columns=cols)
    return pd.DataFrame(data[1:], columns=data[0])

def append_order(row_data):
    sheet.worksheet("orders").append_row(row_data)
    load_orders.clear()

def append_manu(row_data):
    sheet.worksheet("manufactures").append_row(row_data)
    load_manus.clear()

def save_master_data(sheet_name, df):
    ws = sheet.worksheet(sheet_name)
    ws.clear()
    df_str = df.fillna("").astype(str)
    ws.update(values=[df_str.columns.values.tolist()] + df_str.values.tolist(), range_name='A1')
    if sheet_name == "master": load_master.clear()
    if sheet_name == "customers": load_cust.clear()

# ─────────────────────────────────────────────
# 5. マスタデータ・関数
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

# セッション状態の初期化
if "success_msg" not in st.session_state: st.session_state.success_msg = None
if "current_page" not in st.session_state: st.session_state.current_page = "📋 受注登録"

def change_page(page_name):
    st.session_state.current_page = page_name

# ─────────────────────────────────────────────
# 6. サイドバー（本物のボタンを使ったメニュー）
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h2 style='font-weight:900;'>🏭 丸実屋システム</h2>", unsafe_allow_html=True)
    st.write("---")
    
    pages = ["📋 受注登録", "🏭 製造登録", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"]
    for p in pages:
        # 選ばれているメニューは「Primary(青色)」、それ以外は「Secondary」のボタンにする
        if st.session_state.current_page == p:
            st.button(f"▶ {p}", key=f"btn_{p}", use_container_width=True, type="primary")
        else:
            st.button(p, key=f"btn_{p}", use_container_width=True, on_click=change_page, args=(p,))

page = st.session_state.current_page

# ─────────────────────────────────────────────
# 7. 画面の描画
# ─────────────────────────────────────────────

# --- 受注登録 ---
if page == "📋 受注登録":
    st.markdown('<div class="main-header"><h1>📋 受注（出荷予定）の連続登録</h1></div>', unsafe_allow_html=True)
    
    with st.container(border=True): # 白背景・枠線付きのカード
        col1, col2, col3 = st.columns([1, 2, 1])
        
        o_date = col1.date_input("📅 納品予定日", value=date.today() + timedelta(days=1))
        
        # 顧客名：ひらがな検索・空欄可能
        cust_names = sorted(cust_df[cust_df["顧客名"].str.strip() != ""]["顧客名"].unique().tolist())
        c_name = col2.selectbox("🏢 顧客名（クリックして入力・検索）", options=cust_names, index=None, placeholder="空欄（未指定）")
        
        qty = col3.number_input("📦 出荷ケース数", min_value=1, value=None, step=1, placeholder="数字を入力")

        st.write("---")
        st.write("### 📂 カテゴリを選択（クリック）")
        
        # ★【新機能】Streamlit公式の文字全体ボタン（絶対に壊れない）
        try:
            cat_full = st.pills("カテゴリ", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
            if not cat_full: cat_full = CATEGORIES[0]
        except AttributeError:
            cat_full = st.radio("カテゴリ", CATEGORIES, horizontal=True, label_visibility="collapsed")
            
        cat = cat_full.split(" ", 1)[1]
        
        prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
        prod = st.selectbox("📦 製品名を選択", options=prods, index=None, placeholder="製品を選んでください", format_func=format_name)
        
        st.write("")
        submit_btn = st.button("✅ 受注を登録する (続けて入力できます)", type="primary", use_container_width=True)
        msg_area = st.empty()
        
        if submit_btn:
            if not prod or not qty:
                msg_area.error("⚠️ 製品とケース数を入力してください。")
            else:
                c_val = c_name if c_name else "未指定"
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                row_data = [str(uuid.uuid4())[:6].upper(), o_date.strftime('%Y-%m-%d'), c_val, cat, prod, int(qty), now_str]
                append_order(row_data)
                
                st.session_state.success_msg = f"✨ 登録完了： {o_date.strftime('%m/%d')} 出荷 ｜ {c_val} 様宛 ｜ {prod} ({qty}cs)"
                st.rerun()
                
    if st.session_state.success_msg:
        st.success(st.session_state.success_msg)
        st.session_state.success_msg = None

    with st.expander("🕒 直近の登録履歴を確認・削除"):
        st.dataframe(orders_df.tail(10).sort_values("登録日時", ascending=False), use_container_width=True, hide_index=True)
        del_id = st.text_input("削除するIDを入力（例: O-XXXXXX）")
        if st.button("🗑️ このIDのデータを削除", type="secondary"):
            if del_id:
                save_data("orders", orders_df[orders_df["ID"] != del_id.strip()]); st.success("削除しました"); st.rerun()

# --- 製造登録 ---
elif page == "🏭 製造登録":
    st.markdown('<div class="main-header manu-header"><h1>🏭 製造（入庫）の登録</h1></div>', unsafe_allow_html=True)
    
    with st.container(border=True):
        col1, col2 = st.columns(2)
        m_date = col1.date_input("📅 製造日", value=date.today())
        m_qty = col2.number_input("📦 製造ケース数", min_value=1, value=None, step=10, placeholder="数字を入力")
        
        st.write("---")
        st.write("### 📂 カテゴリを選択（クリック）")
        
        try:
            cat_full = st.pills("カテゴリ", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
            if not cat_full: cat_full = CATEGORIES[0]
        except AttributeError:
            cat_full = st.radio("カテゴリ", CATEGORIES, horizontal=True, label_visibility="collapsed")
            
        cat = cat_full.split(" ", 1)[1]
        
        prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
        prod = st.selectbox("📦 製品名を選択", options=prods, index=None, placeholder="製品を選んでください", format_func=format_name)
        
        st.write("")
        submit_btn = st.button("➕ 製造データを記録する", type="primary", use_container_width=True)
        msg_area = st.empty()
        
        if submit_btn:
            if not prod or not m_qty:
                msg_area.error("⚠️ 製品と製造ケース数を入力してください。")
            else:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                row_data = [str(uuid.uuid4())[:6].upper(), m_date.strftime('%Y-%m-%d'), "", cat, prod, int(m_qty), now_str]
                append_manu(row_data)
                st.session_state.success_msg = f"✨ 登録完了： {m_date.strftime('%m/%d')} 製造 ｜ {prod} ({m_qty}cs)"
                st.rerun()

    if st.session_state.success_msg:
        st.success(st.session_state.success_msg)
        st.session_state.success_msg = None

# --- 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="main-header"><h1>📦 在庫推移とスケジュール</h1></div>', unsafe_allow_html=True)
    
    today = pd.Timestamp.today().normalize()
    dates = pd.date_range(today, today + timedelta(days=14))
    
    t1, t2 = st.tabs(["📅 直近スケジュール (出力・バー表示)", "📉 在庫予測マトリクス"])
    
    with t1:
        with st.container(border=True):
            st.write("📥 **ピッキングリストのダウンロード**")
            col_dl1, col_dl2 = st.columns(2)
            today_orders = orders_df[orders_df["納品予定日"] == today]
            if not today_orders.empty:
                csv1 = today_orders[["顧客名", "大カテゴリ", "製品名", "ケース数"]].sort_values(["顧客名"]).to_csv(index=False, encoding="utf-8-sig")
                col_dl1.download_button("📝 今日の出荷予定 (CSV)", data=csv1, file_name=f"出荷_{today.strftime('%Y%m%d')}.csv", mime="text/csv", type="primary")
            
            week_orders = orders_df[(orders_df["納品予定日"] >= today) & (orders_df["納品予定日"] <= today + timedelta(days=6))]
            if not week_orders.empty:
                exp_df2 = week_orders[["納品予定日", "顧客名", "大カテゴリ", "製品名", "ケース数"]].sort_values(["納品予定日", "顧客名"])
                exp_df2["納品予定日"] = exp_df2["納品予定日"].dt.strftime('%Y/%m/%d')
                csv2 = exp_df2.to_csv(index=False, encoding="utf-8-sig")
                col_dl2.download_button("📅 1週間の出荷予定 (CSV)", data=csv2, file_name=f"出荷_1週間_{today.strftime('%Y%m%d')}.csv", mime="text/csv")
        
        with st.container(border=True):
            st.write("バーの長さは **最大500ケース** を基準にしています。")
            MAX_CASES = 500 # ★500ケース対応
            
            html = '<table class="sched-table"><tr><th style="width:100px;">日付</th><th style="width:45%;">🏭 製造予定 (入庫)</th><th style="width:45%;">📋 出荷予定 (出庫)</th></tr>'
            for i in range(7):
                d = today + timedelta(days=i)
                m_items = manus_df[manus_df["製造予定日"] == d]
                o_items = orders_df[orders_df["納品予定日"] == d]
                
                m_html = ""
                for _, r in m_items.iterrows():
                    pct = min(100, int((r["ケース数"] / MAX_CASES) * 100))
                    m_html += f"""<div class="event-bar manu"><div class="event-bg"></div><span class="event-text">{format_name(r["製品名"])}</span><span class="event-qty">{r["ケース数"]} cs</span><div style="background:#10b981; height:4px; width:{pct}%; border-radius:2px; margin-top:4px;"></div></div>"""
                    
                o_html = ""
                for _, r in o_items.iterrows():
                    pct = min(100, int((r["ケース数"] / MAX_CASES) * 100))
                    o_html += f"""<div class="event-bar"><div class="event-bg"></div><span class="event-text">{r["顧客名"]}: {format_name(r["製品名"])}</span><span class="event-qty">{r["ケース数"]} cs</span><div style="background:#3b82f6; height:4px; width:{pct}%; border-radius:2px; margin-top:4px;"></div></div>"""
                    
                html += f'<tr><td><b style="font-size:18px;">{d.strftime("%m/%d")}</b></td><td>{m_html}</td><td>{o_html}</td></tr>'
            st.markdown(html + '</table>', unsafe_allow_html=True)

    with t2:
        with st.container(border=True):
            st.write("マイナス（欠品）になる日は赤字・赤背景で強調表示されます。")
            inv_list = []
            for _, m in master_df.iterrows():
                prod = m["製品名"]
                curr = int(m["初期在庫数"])
                curr += manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] < today)]["ケース数"].sum()
                curr -= orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] < today)]["ケース数"].sum()
                
                row = {"大カテゴリ": m["大カテゴリ"], "製品名": format_name(prod)}
                for d in dates:
                    in_q = manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] == d)]["ケース数"].sum()
                    out_q = orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] == d)]["ケース数"].sum()
                    curr += (in_q - out_q)
                    row[d.strftime("%m/%d")] = curr
                inv_list.append(row)
            
            if inv_list:
                inv_df = pd.DataFrame(inv_list)
                cat_order = [c.split(" ", 1)[1] for c in CATEGORIES]
                inv_df["カテゴリ順"] = inv_df["大カテゴリ"].apply(lambda x: cat_order.index(x) if x in cat_order else 99)
                inv_df = inv_df.sort_values(["カテゴリ順", "製品名"]).drop(columns=["カテゴリ順", "大カテゴリ"])
                st.dataframe(inv_df.style.map(lambda x: 'color: #DC2626; font-weight: 900; background-color: #FEE2E2;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True, height=600)

# --- 統計分析 ---
elif page == "📊 統計・分析":
    st.markdown('<div class="main-header stat-header"><h1>📊 出荷データの傾向分析</h1></div>', unsafe_allow_html=True)
    
    if orders_df.empty:
        st.info("データがありません。")
    else:
        with st.container(border=True):
            col1, col2, col3 = st.columns(3)
            col1.metric("📦 総出荷ケース数", f"{orders_df['ケース数'].sum():,} cs")
            col2.metric("📋 総受注件数", f"{len(orders_df):,} 件")
            col3.metric("🏢 取引先数", f"{orders_df[orders_df['顧客名'] != '未指定']['顧客名'].nunique()} 社")
        
        orders_df["年月"] = orders_df["納品予定日"].dt.strftime("%Y-%m")
        
        c_left, c_right = st.columns(2)
        with c_left:
            with st.container(border=True):
                st.write("📈 **月別・カテゴリ別トレンド**")
                trend_df = orders_df.groupby(["年月","大カテゴリ"])["ケース数"].sum().reset_index()
                fig = px.bar(trend_df, x="年月", y="ケース数", color="大カテゴリ", barmode="stack")
                st.plotly_chart(fig, use_container_width=True)
        with c_right:
            with st.container(border=True):
                st.write("🏆 **お得意様ランキング (TOP 10)**")
                cust_stat = orders_df[orders_df["顧客名"] != "未指定"].groupby("顧客名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False).head(10)
                fig2 = px.bar(cust_stat, x="ケース数", y="顧客名", orientation='h')
                fig2.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig2, use_container_width=True)

# --- マスタ管理 ---
elif page == "⚙️ マスタ管理":
    st.markdown('<div class="main-header" style="background:linear-gradient(135deg, #475569 0%, #1e293b 100%);"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["📦 製品マスタ（棚卸・初期在庫）", "🏢 顧客マスタ"])
    with t1:
        with st.container(border=True):
            st.info("💡 棚卸時の在庫数を「初期在庫数」に入力して保存してください。")
            ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True, height=500)
            if st.button("💾 製品マスタを保存", type="primary"):
                save_master_data("master", ed_m)
                st.success("更新しました")
                st.rerun()
    with t2:
        with st.container(border=True):
            st.write("「ふりがな」を登録しておくと、ひらがな検索ができるようになります。")
            ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True, height=500)
            if st.button("💾 顧客マスタを保存", type="primary"):
                save_master_data("customers", ed_c)
                st.success("更新しました")
                st.rerun()
