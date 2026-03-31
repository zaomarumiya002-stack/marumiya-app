"""
丸実屋 受注・製造・在庫管理アプリ (テーマ強制固定・絶対文字消えない版)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import uuid
from datetime import datetime, timedelta, date
import gspread
from google.oauth2.service_account import Credentials
import io
import os

# ─────────────────────────────────────────────
# 1. ページ基本設定（絶対にライトテーマにする）
# ─────────────────────────────────────────────
# ※ユーザーのブラウザ設定を無視し、強制的に白背景・黒文字にする裏技
os.environ["STREAMLIT_THEME_BASE"] = "light"
os.environ["STREAMLIT_THEME_PRIMARY_COLOR"] = "#1a6fc4"
os.environ["STREAMLIT_THEME_BACKGROUND_COLOR"] = "#e2e8f0" # 背景は少し色を付ける（薄いブルーグレー）
os.environ["STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR"] = "#ffffff"
os.environ["STREAMLIT_THEME_TEXT_COLOR"] = "#0f172a" # 文字は限りなく黒に近い紺

st.set_page_config(page_title="丸実屋 受注・在庫管理", page_icon="🏭", layout="wide", initial_sidebar_state="expanded")

# ─────────────────────────────────────────────
# 2. 安全なCSS（レイアウトとボタンの巨大化のみ）
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* フォント設定 */
    html, body, [class*="css"] {
        font-family: 'Noto Sans JP', sans-serif !important;
    }

    /* ウィンドウ（カード）を真っ白にして浮き立たせる */
    .white-window {
        background-color: #ffffff;
        border: 2px solid #cbd5e1;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }

    /* カラフルで大きなヘッダー */
    .main-header {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 24px;
        border-radius: 12px;
        margin-bottom: 24px;
        box-shadow: 0 4px 10px rgba(59, 130, 246, 0.3);
    }
    .main-header h1 { color: #ffffff !important; margin: 0; font-size: 28px; font-weight: 900; }
    .header-manu { background: linear-gradient(135deg, #064e3b 0%, #10b981 100%); box-shadow: 0 4px 10px rgba(16, 185, 129, 0.3); }

    /* =========================================
       カテゴリの「巨大ボタン」化（絶対に文字が消えない安全な書き方）
       ========================================= */
    div.stRadio > div[role="radiogroup"] {
        display: flex; flex-direction: row; flex-wrap: wrap; gap: 12px;
    }
    div.stRadio > div[role="radiogroup"] > label {
        background-color: #ffffff;
        border: 2px solid #94a3b8;
        border-radius: 8px;
        padding: 14px 20px;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    div.stRadio > div[role="radiogroup"] > label:hover {
        border-color: #3b82f6;
        background-color: #f8fafc;
    }
    /* 選択中の色反転 */
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) {
        background-color: #2563eb !important;
        border-color: #1d4ed8 !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
    }
    /* 選択中の文字を白にする */
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) p,
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) span {
        color: #ffffff !important;
        font-weight: bold !important;
    }
    /* ラジオボタンの丸いポチを消す */
    div.stRadio > div[role="radiogroup"] label[data-baseweb="radio"] div:first-child { display: none !important; }

    /* =========================================
       スケジュール表（プログレスバー）のデザイン
       ========================================= */
    .sched-table { width: 100%; border-collapse: separate; border-spacing: 0; background: #ffffff; border-radius: 8px; border: 1px solid #cbd5e1; }
    .sched-table th { background-color: #1e293b; color: #ffffff !important; padding: 14px; text-align: left; font-size: 15px; font-weight: bold; }
    .sched-table td { padding: 12px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }
    
    .event-bar-container { position: relative; background-color: #f1f5f9; border-left: 5px solid #3b82f6; border-radius: 6px; padding: 10px; margin-bottom: 8px; z-index: 1; }
    .event-bar-container.manu { border-left-color: #10b981; }
    .event-bg { position: absolute; top: 0; left: 0; height: 100%; background-color: #dbeafe; z-index: -1; }
    .event-bar-container.manu .event-bg { background-color: #d1fae5; }
    .event-text { font-size: 14px; font-weight: 700; color: #0f172a; }
    .event-qty { float: right; font-weight: 900; color: #1d4ed8; font-size: 16px; }
    .event-bar-container.manu .event-qty { color: #047857; }
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
            with st.container():
                st.markdown('<div class="white-window">', unsafe_allow_html=True)
                pwd = st.text_input("パスワード", type="password")
                if st.button("ログイン", use_container_width=True, type="primary"):
                    if pwd == st.secrets["app_password"]:
                        st.session_state["password_correct"] = True
                        st.rerun()
                    else:
                        st.error("❌ パスワードが違います")
                st.markdown('</div>', unsafe_allow_html=True)
        st.stop()

check_password()

# ─────────────────────────────────────────────
# 4. Googleスプレッドシート連携（独立キャッシュで爆速化）
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

if "success_msg" not in st.session_state:
    st.session_state.success_msg = None

# ─────────────────────────────────────────────
# 6. サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.title("🏭 丸実屋システム")
    st.write("---")
    page = st.radio(
        "メニュー", 
        ["📋 受注登録 (出庫)", "🏭 製造登録 (入庫)", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"],
        label_visibility="collapsed"
    )

# ─────────────────────────────────────────────
# 7. 各画面の描画
# ─────────────────────────────────────────────

# --- 受注登録 ---
if page == "📋 受注登録 (出庫)":
    st.markdown('<div class="main-header"><h1>📋 受注（出荷予定）の連続登録</h1></div>', unsafe_allow_html=True)
    
    st.markdown('<div class="white-window">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    
    o_date = col1.date_input("📅 納品予定日", value=date.today() + timedelta(days=1))
    
    # 顧客名：ひらがな検索・空欄可能
    cust_names = sorted(cust_df[cust_df["顧客名"].str.strip() != ""]["顧客名"].unique().tolist())
    c_name = col2.selectbox("🏢 顧客名（入力して検索）", options=cust_names, index=None, placeholder="空白（クリックして検索・入力）")
    
    qty = col3.number_input("📦 出荷ケース数", min_value=1, value=None, step=1, placeholder="数字を入力")

    st.write("---")
    st.markdown("### 📂 カテゴリを選択（クリック）")
    
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
        
    st.markdown('</div>', unsafe_allow_html=True)

    with st.expander("🕒 直近の登録履歴を確認・削除"):
        st.dataframe(orders_df.tail(10).sort_values("登録日時", ascending=False), use_container_width=True, hide_index=True)
        del_id = st.text_input("削除するIDを入力（例: O-XXXXXX）")
        if st.button("🗑️ このIDのデータを削除", type="secondary"):
            if del_id:
                save_data("orders", orders_df[orders_df["ID"] != del_id.strip()]); st.success("削除しました"); st.rerun()

# --- 製造登録 ---
elif page == "🏭 製造登録 (入庫)":
    st.markdown('<div class="main-header header-manu"><h1>🏭 製造（入庫）実績の登録</h1></div>', unsafe_allow_html=True)
    
    st.markdown('<div class="white-window">', unsafe_allow_html=True)
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
    st.markdown('<div class="main-header"><h1>📦 在庫推移とカレンダー</h1></div>', unsafe_allow_html=True)
    
    today = pd.Timestamp.today().normalize()
    dates = pd.date_range(today, today + timedelta(days=14))
    
    t1, t2 = st.tabs(["📅 カレンダー＆リストDL", "📉 在庫予測マトリクス"])
    
    with t1:
        st.markdown('<div class="white-window">', unsafe_allow_html=True)
        st.subheader("📥 ピッキングリスト（出荷予定）のダウンロード")
        col_dl1, col_dl2 = st.columns(2)
        
        # 当日DL
        today_orders = orders_df[orders_df["納品予定日"] == today]
        if not today_orders.empty:
            export_df1 = today_orders[["顧客名", "大カテゴリ", "製品名", "ケース数"]].sort_values(["顧客名", "大カテゴリ"])
            csv1 = export_df1.to_csv(index=False, encoding="utf-8-sig")
            col_dl1.download_button("📝 今日の出荷予定を保存 (CSV)", data=csv1, file_name=f"出荷_{today.strftime('%Y%m%d')}.csv", mime="text/csv", type="primary")
        else:
            col_dl1.info("今日の出荷予定はありません。")
            
        # 1週間DL
        week_orders = orders_df[(orders_df["納品予定日"] >= today) & (orders_df["納品予定日"] <= today + timedelta(days=6))]
        if not week_orders.empty:
            export_df2 = week_orders[["納品予定日", "顧客名", "大カテゴリ", "製品名", "ケース数"]].sort_values(["納品予定日", "顧客名"])
            export_df2["納品予定日"] = export_df2["納品予定日"].dt.strftime('%Y/%m/%d')
            csv2 = export_df2.to_csv(index=False, encoding="utf-8-sig")
            col_dl2.download_button("📅 1週間の出荷予定を保存 (CSV)", data=csv2, file_name=f"出荷_1週間_{today.strftime('%Y%m%d')}.csv", mime="text/csv")
        else:
            col_dl2.info("1週間の出荷予定はありません。")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="white-window">', unsafe_allow_html=True)
        st.write("バーの長さは **最大500ケース** を基準にしています。")
        MAX_CASES = 500 # ★500ケース想定
        
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
        st.markdown('<div class="white-window">', unsafe_allow_html=True)
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
        st.markdown('</div>', unsafe_allow_html=True)

# --- 統計分析 ---
elif page == "📊 統計・分析":
    st.markdown('<div class="main-header"><h1>📊 分析ダッシュボード</h1></div>', unsafe_allow_html=True)
    
    if orders_df.empty:
        st.info("データがありません。")
    else:
        st.markdown('<div class="white-window">', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        col1.metric("📦 総出荷ケース数", f"{orders_df['ケース数'].sum():,} cs")
        col2.metric("📋 総受注件数", f"{len(orders_df):,} 件")
        col3.metric("🏢 取引先数", f"{orders_df[orders_df['顧客名'] != '未指定']['顧客名'].nunique()} 社")
        st.markdown('</div>', unsafe_allow_html=True)
        
        orders_df["年月"] = orders_df["納品予定日"].dt.strftime("%Y-%m")
        
        c_left, c_right = st.columns(2)
        with c_left:
            st.markdown('<div class="white-window">', unsafe_allow_html=True)
            st.write("📈 **月別・カテゴリ別の出荷数トレンド**")
            trend_df = orders_df.groupby(["年月","大カテゴリ"])["ケース数"].sum().reset_index()
            fig = px.bar(trend_df, x="年月", y="ケース数", color="大カテゴリ", barmode="stack")
            st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with c_right:
            st.markdown('<div class="white-window">', unsafe_allow_html=True)
            st.write("🏆 **お得意様ランキング (TOP 10)**")
            cust_stat = orders_df[orders_df["顧客名"] != "未指定"].groupby("顧客名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False).head(10)
            fig2 = px.bar(cust_stat, x="ケース数", y="顧客名", orientation='h')
            fig2.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig2, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

# --- マスタ管理 ---
elif page == "⚙️ マスタ管理":
    st.markdown('<div class="main-header" style="background:linear-gradient(135deg, #475569 0%, #1E293B 100%);"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["📦 製品マスタ（棚卸・初期在庫）", "🏢 顧客マスタ（ふりがな）"])
    with t1:
        st.markdown('<div class="white-window">', unsafe_allow_html=True)
        st.info("💡 実際の在庫数を「初期在庫数」に入力して保存すると、そこを起点に在庫計算がリセットされます。")
        ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 製品マスタを保存する", type="primary"):
            save_master_data("master", ed_m)
            st.success("製品情報を更新しました")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
            
    with t2:
        st.markdown('<div class="white-window">', unsafe_allow_html=True)
        st.write("「ふりがな」を登録しておくと、顧客名の一覧に表示されなくても検索のキーとして機能させることができます。")
        ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 顧客マスタを保存する", type="primary"):
            save_master_data("customers", ed_c)
            st.success("顧客情報を更新しました")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
