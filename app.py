"""
丸実屋 受注・製造・在庫管理アプリ (プロ仕様・超絶UI・爆速版)
"""

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
# 2. 堅牢かつモダンなCSS（ボタンの巨大化・見やすさ特化）
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');

    /* 全体の背景色（薄いグレー）と文字色（黒）を強制固定 */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #EEF2F6 !important;
        color: #1A202C !important;
        font-family: 'Noto Sans JP', sans-serif !important;
    }
    
    /* テキスト要素の保護 */
    p, span, div, h1, h2, h3, h4, label { color: #1A202C !important; }

    /* =========================================
       メインエリアのラジオボタン（カテゴリ等）の巨大ボタン化
       ========================================= */
    div.stRadio > div[role="radiogroup"] {
        display: flex; flex-direction: row; flex-wrap: wrap; gap: 12px;
    }
    div.stRadio > div[role="radiogroup"] > label {
        background-color: #FFFFFF !important;
        border: 2px solid #CBD5E1 !important;
        border-radius: 8px !important;
        padding: 12px 24px !important; /* ボタンを大きく */
        cursor: pointer !important;
        transition: all 0.2s ease !important;
    }
    div.stRadio > div[role="radiogroup"] > label:hover {
        border-color: #3B82F6 !important;
        background-color: #F8FAFC !important;
    }
    /* 選択中の色反転 */
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) {
        background-color: #3B82F6 !important;
        border-color: #3B82F6 !important;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4) !important;
    }
    /* 文字サイズと色の調整 */
    div.stRadio > div[role="radiogroup"] > label p {
        font-size: 16px !important; font-weight: 700 !important; color: #334155 !important; margin: 0 !important;
    }
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) p {
        color: #FFFFFF !important;
    }
    /* 丸ポチを消す */
    div.stRadio > div[role="radiogroup"] label[data-baseweb="radio"] div:first-child { display: none !important; }

    /* =========================================
       サイドバー（深い紺色 ＋ 巨大メニューボタン）
       ========================================= */
    [data-testid="stSidebar"] {
        background-color: #0F172A !important; /* 紺色 */
    }
    [data-testid="stSidebar"] * { color: #F8FAFC !important; }
    
    /* サイドバー内のラジオボタン（メニュー） */
    [data-testid="stSidebar"] div.stRadio > div[role="radiogroup"] {
        flex-direction: column; gap: 16px;
    }
    [data-testid="stSidebar"] div.stRadio > div[role="radiogroup"] > label {
        background-color: #1E293B !important;
        border: 2px solid #334155 !important;
        border-radius: 12px !important;
        padding: 16px 20px !important;
        width: 100%;
    }
    [data-testid="stSidebar"] div.stRadio > div[role="radiogroup"] > label:hover {
        border-color: #60A5FA !important; background-color: #2D3748 !important;
    }
    [data-testid="stSidebar"] div.stRadio > div[role="radiogroup"] > label:has(input:checked) {
        background-color: #2563EB !important; border-color: #60A5FA !important;
        box-shadow: 0 4px 15px rgba(37, 99, 235, 0.5) !important;
    }
    [data-testid="stSidebar"] div.stRadio > div[role="radiogroup"] > label p {
        font-size: 18px !important; font-weight: 900 !important; color: #FFFFFF !important;
    }

    /* =========================================
       装飾コンポーネント（白カード、ヘッダー、表）
       ========================================= */
    .card-box {
        background-color: #FFFFFF !important;
        padding: 30px;
        border-radius: 16px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        margin-bottom: 24px;
    }
    .header-box {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        padding: 24px 32px; border-radius: 16px; margin-bottom: 24px;
        box-shadow: 0 10px 20px -5px rgba(59, 130, 246, 0.4);
    }
    .header-box h1 { color: #FFFFFF !important; font-size: 28px !important; font-weight: 900 !important; margin: 0 !important; }
    .header-manu { background: linear-gradient(135deg, #064E3B 0%, #10B981 100%); box-shadow: 0 10px 20px -5px rgba(16, 185, 129, 0.4); }

    /* スケジュール表 */
    .sched-table { width: 100%; border-collapse: separate; border-spacing: 0; background: transparent; }
    .sched-table th { background-color: #F8FAFC; color: #475569 !important; font-weight: 700; padding: 14px; text-align: left; border-bottom: 2px solid #E2E8F0; font-size: 15px; }
    .sched-table td { padding: 14px; border-bottom: 1px solid #E2E8F0; vertical-align: top; }
    
    .event-bar-container { position: relative; background-color: #F1F5F9; border-left: 5px solid #3B82F6; border-radius: 8px; padding: 10px 14px; margin-bottom: 8px; overflow: hidden; z-index: 1; }
    .event-bar-container.manu { border-left-color: #10B981; }
    .event-bg { position: absolute; top: 0; left: 0; height: 100%; background-color: #DBEAFE; z-index: -1; }
    .event-bar-container.manu .event-bg { background-color: #D1FAE5; }
    .event-text { font-size: 14px; font-weight: 700; color: #1E293B !important; }
    .event-qty { float: right; font-weight: 900; color: #1D4ED8 !important; font-size: 16px; }
    .event-bar-container.manu .event-qty { color: #047857 !important; }
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

# データロード
orders_df = load_orders()
manus_df = load_manus()
master_df = load_master()
cust_df = load_cust()

if "success_msg" not in st.session_state:
    st.session_state.success_msg = None

# ─────────────────────────────────────────────
# 6. サイドバー（専用メニュー）
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h2 style='font-size:24px; font-weight:900; margin-bottom:20px;'>🏭 丸実屋システム</h2>", unsafe_allow_html=True)
    # 文字全体がボタンになるラジオボタン（CSSで装飾済み）
    page = st.radio("メニュー", ["📋 受注登録 (出庫)", "🏭 製造登録 (入庫)", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"], label_visibility="collapsed")

# ─────────────────────────────────────────────
# 7. 各画面の描画
# ─────────────────────────────────────────────

# --- 受注登録 ---
if page == "📋 受注登録 (出庫)":
    st.markdown('<div class="header-box"><h1>📋 受注（出荷予定）の連続登録</h1></div>', unsafe_allow_html=True)
    
    st.markdown('<div class="card-box">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    
    o_date = col1.date_input("📅 納品予定日", value=date.today() + timedelta(days=1))
    
    # 顧客名：IMEのひらがな入力で漢字に変換してもらう方式（リストは空欄からスタート）
    cust_names = sorted(cust_df[cust_df["顧客名"].str.strip() != ""]["顧客名"].unique().tolist())
    c_name = col2.selectbox("🏢 顧客名（入力して検索）", options=cust_names, index=None, placeholder="空白（クリックして検索・入力）")
    
    qty = col3.number_input("📦 出荷ケース数", min_value=1, value=None, step=1, placeholder="数字を入力")

    st.write("---")
    st.markdown("### 📂 カテゴリを選択（クリック）")
    # 巨大なボタン群
    cat_full = st.radio("カテゴリ", CATEGORIES, horizontal=True, label_visibility="collapsed")
    cat = cat_full.split(" ", 1)[1]
    
    prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
    prod = st.selectbox("📦 製品名を選択", options=prods, index=None, placeholder="製品を選んでください", format_func=format_name)
    
    st.write("")
    submit_btn = st.button("✅ 受注を登録する (続けて入力できます)", type="primary", use_container_width=True)
    
    # ボタンの直下にメッセージ表示
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
        
    st.markdown('</div>', unsafe_allow_html=True)

    with st.expander("🕒 直近の登録履歴を確認・削除"):
        st.dataframe(orders_df.tail(10).sort_values("登録日時", ascending=False), use_container_width=True, hide_index=True)
        del_id = st.text_input("削除するIDを入力（例: O-XXXXXX）")
        if st.button("🗑️ このIDのデータを削除", type="secondary"):
            if del_id:
                save_data("orders", orders_df[orders_df["ID"] != del_id.strip()]); st.success("削除しました"); st.rerun()

# --- 製造登録 ---
elif page == "🏭 製造登録 (入庫)":
    st.markdown('<div class="header-box header-manu"><h1>🏭 製造（入庫）実績の登録</h1></div>', unsafe_allow_html=True)
    
    st.markdown('<div class="card-box">', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    m_date = col1.date_input("📅 製造日", value=date.today())
    m_qty = col2.number_input("📦 製造ケース数", min_value=1, value=None, step=10, placeholder="数字を入力")
    
    st.write("---")
    st.markdown("### 📂 カテゴリを選択（クリック）")
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
        
    st.markdown('</div>', unsafe_allow_html=True)

# --- 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="header-box"><h1>📦 在庫推移とカレンダー</h1></div>', unsafe_allow_html=True)
    
    today = pd.Timestamp.today().normalize()
    dates = pd.date_range(today, today + timedelta(days=14))
    
    t1, t2 = st.tabs(["📅 カレンダー＆リストDL", "📉 在庫予測マトリクス"])
    
    with t1:
        st.markdown('<div class="card-box">', unsafe_allow_html=True)
        st.subheader("📥 ピッキングリスト（出荷予定）のダウンロード")
        
        col_dl1, col_dl2 = st.columns(2)
        # 当日の出荷予定CSV出力
        today_orders = orders_df[orders_df["納品予定日"] == today]
        if not today_orders.empty:
            export_df1 = today_orders[["顧客名", "大カテゴリ", "製品名", "ケース数"]].sort_values(["顧客名", "大カテゴリ"])
            csv1 = export_df1.to_csv(index=False, encoding="utf-8-sig")
            col_dl1.download_button(label="📝 今日の出荷予定リストを保存 (CSV)", data=csv1, file_name=f"出荷予定_{today.strftime('%Y%m%d')}.csv", mime="text/csv", type="primary")
        else:
            col_dl1.info("今日の出荷予定はありません。")
            
        # 1週間の出荷予定CSV出力
        week_orders = orders_df[(orders_df["納品予定日"] >= today) & (orders_df["納品予定日"] <= today + timedelta(days=6))]
        if not week_orders.empty:
            export_df2 = week_orders[["納品予定日", "顧客名", "大カテゴリ", "製品名", "ケース数"]].sort_values(["納品予定日", "顧客名"])
            export_df2["納品予定日"] = export_df2["納品予定日"].dt.strftime('%Y/%m/%d')
            csv2 = export_df2.to_csv(index=False, encoding="utf-8-sig")
            col_dl2.download_button(label="📅 1週間の出荷予定リストを保存 (CSV)", data=csv2, file_name=f"出荷予定_1週間_{today.strftime('%Y%m%d')}.csv", mime="text/csv")
        else:
            col_dl2.info("1週間の出荷予定はありません。")
            
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card-box">', unsafe_allow_html=True)
        st.write("1日の出入りを視覚的に表現しています（バーの長さは **500ケース** を最大値としています）。")
        MAX_CASES = 500 # ★500ケース想定に引き上げ
        
        html = '<table class="sched-table"><tr><th style="width:100px;">日付</th><th style="width:45%;">🏭 製造予定 (入庫)</th><th style="width:45%;">📋 出荷予定 (出庫)</th></tr>'
        for i in range(7):
            d = today + timedelta(days=i)
            m_items = manus_df[manus_df["製造予定日"] == d]
            o_items = orders_df[orders_df["納品予定日"] == d]
            
            m_html = ""
            for _, r in m_items.iterrows():
                pct = min(100, int((r["ケース数"] / MAX_CASES) * 100))
                m_html += f"""
                <div class="event-bar-container manu">
                    <div class="event-bg" style="width: {pct}%;"></div>
                    <span class="event-text">{format_name(r["製品名"])}</span>
                    <span class="event-qty">{r["ケース数"]} cs</span>
                </div>"""
                
            o_html = ""
            for _, r in o_items.iterrows():
                pct = min(100, int((r["ケース数"] / MAX_CASES) * 100))
                o_html += f"""
                <div class="event-bar-container">
                    <div class="event-bg" style="width: {pct}%;"></div>
                    <span class="event-text">{r["顧客名"]}: {format_name(r["製品名"])}</span>
                    <span class="event-qty">{r["ケース数"]} cs</span>
                </div>"""
                
            html += f'<tr><td><b style="font-size:18px;">{d.strftime("%m/%d")}</b></td><td>{m_html}</td><td>{o_html}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with t2:
        st.markdown('<div class="card-box">', unsafe_allow_html=True)
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
            # 大カテゴリ順に並び替え
            cat_order = [c.split(" ", 1)[1] for c in CATEGORIES]
            inv_df["カテゴリ順"] = inv_df["大カテゴリ"].apply(lambda x: cat_order.index(x) if x in cat_order else 99)
            inv_df = inv_df.sort_values(["カテゴリ順", "製品名"]).drop(columns=["カテゴリ順", "大カテゴリ"])
            
            st.dataframe(inv_df.style.map(lambda x: 'color: #DC2626; font-weight: 900; background-color: #FEE2E2;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True, height=600)
        st.markdown('</div>', unsafe_allow_html=True)

# --- 統計分析 ---
elif page == "📊 統計・分析":
    st.markdown('<div class="header-box"><h1>📊 分析ダッシュボード</h1></div>', unsafe_allow_html=True)
    
    if orders_df.empty:
        st.info("データがありません。")
    else:
        st.markdown('<div class="card-box">', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        col1.metric("📦 総出荷ケース数", f"{orders_df['ケース数'].sum():,} cs")
        col2.metric("📋 総受注件数", f"{len(orders_df):,} 件")
        col3.metric("🏢 取引先数", f"{orders_df[orders_df['顧客名'] != '未指定']['顧客名'].nunique()} 社")
        st.markdown('</div>', unsafe_allow_html=True)
        
        orders_df["年月"] = orders_df["納品予定日"].dt.strftime("%Y-%m")
        
        c_left, c_right = st.columns(2)
        with c_left:
            st.markdown('<div class="card-box">', unsafe_allow_html=True)
            st.write("📈 **月別・カテゴリ別の出荷数トレンド**")
            trend_df = orders_df.groupby(["年月","大カテゴリ"])["ケース数"].sum().reset_index()
            fig = px.bar(trend_df, x="年月", y="ケース数", color="大カテゴリ", barmode="stack")
            st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with c_right:
            st.markdown('<div class="card-box">', unsafe_allow_html=True)
            st.write("🏆 **お得意様ランキング (TOP 10)**")
            cust_stat = orders_df[orders_df["顧客名"] != "未指定"].groupby("顧客名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False).head(10)
            fig2 = px.bar(cust_stat, x="ケース数", y="顧客名", orientation='h')
            fig2.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig2, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

# --- マスタ管理 ---
elif page == "⚙️ マスタ管理":
    st.markdown('<div class="header-box" style="background:linear-gradient(135deg, #475569 0%, #1E293B 100%);"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["📦 製品マスタ（棚卸・初期在庫）", "🏢 顧客マスタ（ふりがな）"])
    with t1:
        st.markdown('<div class="card-box">', unsafe_allow_html=True)
        st.info("💡 実際の在庫数を「初期在庫数」に入力して保存すると、そこを起点に在庫計算がリセットされます。")
        ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 製品マスタを保存する", type="primary"):
            save_master_data("master", ed_m)
            st.success("製品情報を更新しました")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
            
    with t2:
        st.markdown('<div class="card-box">', unsafe_allow_html=True)
        st.write("「ふりがな」を登録しておくと、顧客名の一覧に表示されなくても検索のキーとして機能させることができます。")
        ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 顧客マスタを保存する", type="primary"):
            save_master_data("customers", ed_c)
            st.success("顧客情報を更新しました")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
