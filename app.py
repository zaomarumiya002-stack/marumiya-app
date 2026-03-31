import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import uuid
from datetime import datetime, timedelta, date
import warnings
import gspread
from google.oauth2.service_account import Credentials

# 警告を無視
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# 1. ページ設定 & パスワード保護
# ─────────────────────────────────────────────
st.set_page_config(page_title="丸実屋 受注・在庫管理", page_icon="🏭", layout="wide", initial_sidebar_state="expanded")

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align: center; margin-top: 80px; color:#1a6fc4;'>🏭 丸実屋システム ログイン</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            pwd = st.text_input("パスワードを入力", type="password")
            if st.button("ログイン", type="primary", use_container_width=True):
                if pwd == st.secrets["app_password"]:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("❌ パスワードが違います")
        st.stop()

check_password()

# ─────────────────────────────────────────────
# 2. カスタムCSS (デザイン完全復元・文字消失防止)
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');
:root {
    --clr-primary: #1a6fc4; --clr-primary-dk: #0e4d8a;
    --clr-manu: #0e8c5a; --clr-manu-dk: #0a6641;
    --clr-accent: #f0a500; --clr-danger: #d93025; --clr-success: #1e8c45;
    --clr-bg: #f0f3f8; --clr-card: #ffffff; --clr-border: #d0d7e3;
    --clr-text: #1c2a3a; --clr-subtext: #5a6a7e;
    --radius: 10px; --shadow: 0 2px 12px rgba(0,0,0,0.08);
}
/* 基本文字設定 */
html, body, [class*="css"], .stMarkdown, p, span, label { 
    font-family: 'Noto Sans JP', sans-serif !important; 
    color: var(--clr-text) !important; 
}
/* ヘッダー */
.app-header { background: linear-gradient(135deg, #1a6fc4 0%, #0e4d8a 100%); border-radius: var(--radius); padding: 14px 24px; margin-bottom: 16px; display: flex; align-items: center; gap: 12px; box-shadow: var(--shadow); }
.app-header.manu-header { background: linear-gradient(135deg, #0e8c5a 0%, #0a6641 100%); }
.app-header.guide-header { background: linear-gradient(135deg, #7c3db8 0%, #5a2a8c 100%); }
.app-header h1 { margin: 0 !important; font-size: 20px !important; font-weight: 900 !important; color: #ffffff !important; }

/* カード */
.card { background: var(--clr-card); border: 1px solid var(--clr-border); border-radius: var(--radius); padding: 18px 22px; margin-bottom: 16px; box-shadow: var(--shadow); }
.card-title { font-size: 15px; font-weight: 700; color: var(--clr-primary); border-bottom: 2px solid var(--clr-primary); padding-bottom: 8px; margin-bottom: 14px; }

/* サイドバー */
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0b2239 0%, #14365d 100%) !important; }
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) { background: #0e8c5a !important; border-radius: 8px; }

/* ラジオボタン(Pills) */
div.stRadio > div[role="radiogroup"] { display: flex; flex-direction: row; flex-wrap: wrap; gap: 8px; }
div.stRadio > div[role="radiogroup"] > label { background-color: #ffffff !important; border: 1.5px solid #d0d7e3 !important; border-radius: 20px !important; padding: 6px 14px !important; cursor: pointer !important; }
div.stRadio > div[role="radiogroup"] > label p { color: #374a5e !important; font-weight: 600 !important; }
div.stRadio > div[role="radiogroup"] label[data-baseweb="radio"] div:first-child { display: none !important; }

/* スケジュール表 */
.sched-table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 800px; background: #fff; }
.sched-table th { background: #1a6fc4; color: #fff !important; font-weight: 700; padding: 8px; border: 1px solid #0e4d8a; }
.sched-table td { border: 1px solid #d8e2ef; padding: 6px; vertical-align: top; }
.sched-entry { border-radius: 6px; padding: 6px 8px; margin-bottom: 4px; font-size: 12px; border-left: 4px solid #1a6fc4; background: #eef4fd; }
.sched-entry.manu-entry { border-left-color: #0e8c5a; background: #e8f5f0; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. ☁️ Googleスプレッドシート接続 (高速化: cacheを使用)
# ─────────────────────────────────────────────
@st.cache_resource
def init_connection():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(creds)

client = init_connection()
sheet = client.open_by_url(st.secrets["spreadsheet_url"])

SHEET_COLUMNS = {
    "orders": ["ID", "納品予定日", "顧客名", "大カテゴリ", "製品名", "ケース数", "登録日時"],
    "manufactures": ["ID", "製造予定日", "備考", "大カテゴリ", "製品名", "ケース数", "登録日時"],
    "master": ["大カテゴリ", "製品名", "初期在庫数"],
    "customers": ["顧客名", "ふりがな"]
}

@st.cache_data(ttl=60) # 1分間はシートを読みに行かずキャッシュを利用(高速化)
def load_data(sheet_name):
    try:
        ws = sheet.worksheet(sheet_name)
        data = ws.get_all_values()
        expected = SHEET_COLUMNS[sheet_name]
        if len(data) <= 1: return pd.DataFrame(columns=expected)
        df = pd.DataFrame(data[1:], columns=data[0])
        # 型変換
        if "ケース数" in df.columns: df["ケース数"] = pd.to_numeric(df["ケース数"], errors="coerce").fillna(0).astype(int)
        if "初期在庫数" in df.columns: df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors="coerce").fillna(0).astype(int)
        if "納品予定日" in df.columns: df["納品予定日"] = pd.to_datetime(df["納品予定日"], errors="coerce")
        if "製造予定日" in df.columns: df["製造予定日"] = pd.to_datetime(df["製造予定日"], errors="coerce")
        return df
    except:
        return pd.DataFrame(columns=SHEET_COLUMNS[sheet_name])

def save_data(sheet_name, df):
    ws = sheet.worksheet(sheet_name)
    ws.clear()
    df_str = df.copy()
    for col in df_str.columns:
        if pd.api.types.is_datetime64_any_dtype(df_str[col]):
            df_str[col] = df_str[col].dt.strftime('%Y-%m-%d')
    df_str = df_str.fillna("")
    ws.update(values=[df_str.columns.values.tolist()] + df_str.values.tolist(), range_name='A1')
    st.cache_data.clear() # 保存後はキャッシュをリフレッシュ

# ─────────────────────────────────────────────
# 4. マスタ定義
# ─────────────────────────────────────────────
CATEGORIES = ["平こん", "つきこん", "糸こん・しらたき", "三角こん", "玉こん", "ダイスこん", "短冊", "国産", "ちぎりこん", "大黒屋", "かねこ", "冷凍耐性", "その他"]
CAT_ICONS = {"平こん": "🟫", "つきこん": "🍝", "糸こん・しらたき": "🍜", "三角こん": "🔺", "玉こん": "🟤", "ダイスこん": "🎲", "短冊": "🏷️", "国産": "🇯🇵", "ちぎりこん": "🤲", "大黒屋": "🏮", "かねこ": "🏭", "冷凍耐性": "❄️", "その他": "📦"}
CAT_COLORS = {"平こん": "#8b5a2b", "つきこん": "#0e8c5a", "糸こん・しらたき": "#7c3db8", "三角こん": "#d97706", "玉こん": "#6b4226", "ダイスこん": "#0e7c8c", "短冊": "#1a6fc4", "国産": "#c41a3a", "ちぎりこん": "#d96606", "大黒屋": "#333333", "かねこ": "#2563a8", "冷凍耐性": "#4a90e2", "その他": "#6b7280"}

def format_product_name(p_name):
    if not p_name: return ""
    p_str = str(p_name)
    if "（黒）" in p_str or "黒" in p_str: return f"⚫️ {p_str}"
    if "（白）" in p_str or "白" in p_str: return f"⚪️ {p_str}"
    return f"📦 {p_str}"

# 在庫シミュレーション
@st.cache_data(ttl=60)
def simulate_inventory(orders_df, manus_df, master_df):
    today = pd.Timestamp.today().normalize()
    date_range = pd.date_range(today, today + timedelta(days=30))
    inv_records, alerts = [], []
    for _, row in master_df.iterrows():
        prod, cat = row["製品名"], row["大カテゴリ"]
        curr_inv = int(row.get("初期在庫数", 0))
        # 過去の変動分
        curr_inv += manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] < today)]["ケース数"].sum()
        curr_inv -= orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] < today)]["ケース数"].sum()
        for d in date_range:
            curr_inv += manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] == d)]["ケース数"].sum()
            curr_inv -= orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] == d)]["ケース数"].sum()
            inv_records.append({"日付": d, "日付_str": d.strftime("%m/%d"), "大カテゴリ": cat, "製品名": prod, "在庫数": curr_inv})
            if curr_inv < 0: alerts.append({"日付": d, "製品名": prod, "不足数": abs(curr_inv)})
    return pd.DataFrame(inv_records), pd.DataFrame(alerts)

# データの読み込み
orders_df = load_data("orders")
manus_df = load_data("manufactures")
master_df = load_data("master")
cust_df = load_data("customers")
inv_df, alerts_df = simulate_inventory(orders_df, manus_df, master_df)

# ─────────────────────────────────────────────
# 5. メインUI
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h2 style='color:white;'>🏭 丸実屋</h2>", unsafe_allow_html=True)
    page = st.radio("メニュー", ["📋 受注登録", "🏭 製造登録", "📦 在庫・スケジュール", "📊 統計分析", "⚙️ マスタ管理", "📖 ガイド"])
    if not alerts_df.empty: st.error(f"⚠️ 欠品警告: {len(alerts_df['製品名'].unique())}件")
    else: st.success("✅ 在庫正常")

# --- 受注登録 ---
if page == "📋 受注登録":
    st.markdown('<div class="app-header"><h1>📋 受注登録 (出庫)</h1></div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["➕ 新規受注", "✏️ 編集・削除"])
    with t1:
        st.markdown('<div class="card"><div class="card-title">📝 受注入力フォーム</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 2, 1])
        d_date = c1.date_input("納品予定日", value=date.today() + timedelta(days=1))
        c_list = ["✏️ 直接入力"] + sorted(cust_df["顧客名"].unique().tolist())
        sel_c = c2.selectbox("顧客名", c_list)
        c_name = c2.text_input("📝 顧客名を直接入力") if sel_c == "✏️ 直接入力" else sel_c
        qty = c3.number_input("ケース数", min_value=1, value=1)
        
        sel_cat_label = st.radio("大カテゴリ", ["➖ 未選択"] + [f"{CAT_ICONS.get(c)} {c}" for c in CATEGORIES], horizontal=True)
        sel_cat = sel_cat_label.split(" ", 1)[1] if " " in sel_cat_label else ""
        prods = master_df[master_df["大カテゴリ"] == sel_cat]["製品名"].tolist() if sel_cat else []
        prod = st.selectbox("製品を選択", prods, format_func=format_product_name)
        
        if st.button("✅ 受注を登録する", type="primary", use_container_width=True):
            if prod and c_name:
                new_row = pd.DataFrame([{"ID": "O-"+str(uuid.uuid4())[:6].upper(), "納品予定日": pd.Timestamp(d_date), "顧客名": c_name, "大カテゴリ": sel_cat, "製品名": prod, "ケース数": int(qty), "登録日時": pd.Timestamp.now()}])
                save_data("orders", pd.concat([orders_df, new_row], ignore_index=True))
                st.success(f"登録完了: {c_name}")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with t2:
        st.dataframe(orders_df.sort_values("納品予定日", ascending=False), use_container_width=True)

# --- 製造登録 ---
elif page == "🏭 製造登録":
    st.markdown('<div class="app-header manu-header"><h1>🏭 製造登録 (入庫)</h1></div>', unsafe_allow_html=True)
    st.markdown('<div class="card"><div class="card-title" style="color:var(--clr-manu);">📝 製造入力フォーム</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 2])
    m_date = c1.date_input("製造日", value=date.today())
    m_qty = c2.number_input("製造数", min_value=1, value=50)
    m_note = c3.text_input("備考")
    sel_cat_label = st.radio("大カテゴリ", ["➖ 未選択"] + [f"{CAT_ICONS.get(c)} {c}" for c in CATEGORIES], horizontal=True, key="m_cat")
    sel_cat = sel_cat_label.split(" ", 1)[1] if " " in sel_cat_label else ""
    prods = master_df[master_df["大カテゴリ"] == sel_cat]["製品名"].tolist() if sel_cat else []
    prod = st.selectbox("製品を選択", prods, format_func=format_product_name, key="m_prod")
    if st.button("➕ 製造を記録する", type="primary", use_container_width=True):
        if prod:
            new_row = pd.DataFrame([{"ID": "M-"+str(uuid.uuid4())[:6].upper(), "製造予定日": pd.Timestamp(m_date), "備考": m_note, "大カテゴリ": sel_cat, "製品名": prod, "ケース数": int(m_qty), "登録日時": pd.Timestamp.now()}])
            save_data("manufactures", pd.concat([manus_df, new_row], ignore_index=True))
            st.success("製造記録完了")
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# --- 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="app-header"><h1>📦 在庫推移・スケジュール</h1></div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📊 在庫予測 (14日間)", "📆 週刊入出庫表"])
    with tab1:
        st.markdown('<div class="card"><div class="card-title">📅 向こう2週間の在庫数推移</div>', unsafe_allow_html=True)
        if not inv_df.empty:
            view_inv = inv_df[inv_df["日付"] <= pd.Timestamp.today().normalize() + timedelta(days=14)]
            pivot = view_inv.pivot_table(index=["大カテゴリ", "製品名"], columns="日付_str", values="在庫数", aggfunc="last").reset_index()
            st.dataframe(pivot.style.map(lambda x: 'color:red;font-weight:900;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with tab2:
        st.markdown('<div class="card"><div class="card-title">📆 直近7日間の動き</div>', unsafe_allow_html=True)
        today = pd.Timestamp.today().normalize()
        days = [today + timedelta(days=i) for i in range(7)]
        html = '<table class="sched-table"><tr><th>日付</th><th>製造予定(入庫)</th><th>出荷予定(出庫)</th></tr>'
        for d in days:
            m_list = manus_df[manus_df["製造予定日"] == d]
            o_list = orders_df[orders_df["納品予定日"] == d]
            m_html = "".join([f'<div class="sched-entry manu-entry">{r["製品名"]} ({r["ケース数"]}cs)</div>' for _,r in m_list.iterrows()])
            o_html = "".join([f'<div class="sched-entry">{r["顧客名"]}: {r["製品名"]} ({r["ケース数"]}cs)</div>' for _,r in o_list.iterrows()])
            html += f'<tr><td>{d.strftime("%m/%d")}</td><td>{m_html}</td><td>{o_html}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# --- 統計分析 ---
elif page == "📊 統計分析":
    st.markdown('<div class="app-header"><h1>📊 出荷統計・分析</h1></div>', unsafe_allow_html=True)
    if not orders_df.empty:
        orders_df["年月"] = orders_df["納品予定日"].dt.strftime("%Y-%m")
        fig = px.bar(orders_df.groupby(["年月", "大カテゴリ"])["ケース数"].sum().reset_index(), x="年月", y="ケース数", color="大カテゴリ", color_discrete_map=CAT_COLORS, title="月別カテゴリ別出荷数")
        st.plotly_chart(fig, use_container_width=True)

# --- マスタ管理 ---
elif page == "⚙️ マスタ管理":
    st.markdown('<div class="app-header" style="background:#555;"><h1>⚙️ マスタ・初期在庫管理</h1></div>', unsafe_allow_html=True)
    st.info("💡 棚卸時の在庫数は「初期在庫数」を書き換えて保存してください。")
    t1, t2 = st.tabs(["📦 製品マスタ", "🏢 顧客マスタ"])
    with t1:
        ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 製品マスタ保存"): save_data("master", ed_m); st.rerun()
    with t2:
        ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 顧客マスタ保存"): save_data("customers", ed_c); st.rerun()

# --- 使い方ガイド ---
elif page == "📖 ガイド":
    st.markdown('<div class="app-header guide-header"><h1>📖 システムの使い方</h1></div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="card">
    <h3>1. 受注・製造の登録</h3>
    <p>日々の注文は「受注登録」、作った分は「製造登録」から入力します。</p>
    <h3>2. 在庫の確認</h3>
    <p>入力されたデータをもとに、未来30日間の在庫を自動計算します。マイナスになる場合は赤字で表示されます。</p>
    </div>
    """, unsafe_allow_html=True)
