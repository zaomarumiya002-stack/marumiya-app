"""
丸実屋 受注・製造・在庫管理アプリ (クラウド・完全安定版)
"""

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

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# ページ設定 & パスワード保護
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
# カスタムCSS (UIデザイン復活版)
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
html, body, [class*="css"] { font-family: 'Noto Sans JP', sans-serif !important; color: var(--clr-text); background-color: var(--clr-bg); }
.app-header { background: linear-gradient(135deg, var(--clr-primary) 0%, var(--clr-primary-dk) 100%); border-radius: var(--radius); padding: 14px 24px; margin-bottom: 16px; display: flex; align-items: center; gap: 12px; box-shadow: var(--shadow); }
.app-header.manu-header { background: linear-gradient(135deg, var(--clr-manu) 0%, var(--clr-manu-dk) 100%); }
.app-header.guide-header { background: linear-gradient(135deg, #7c3db8 0%, #5a2a8c 100%); }
.app-header h1 { margin: 0 !important; padding: 0; font-size: 20px; font-weight: 900; color: #ffffff !important; }
.card { background: var(--clr-card); border: 1px solid var(--clr-border); border-radius: var(--radius); padding: 18px 22px; margin-bottom: 16px; box-shadow: var(--shadow); }
.card-title { font-size: 15px; font-weight: 700; color: var(--clr-primary); border-bottom: 2px solid var(--clr-primary); padding-bottom: 8px; margin-bottom: 14px; }

/* サイドバー */
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0b2239 0%, #14365d 100%) !important; }
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stSidebarNav"] { padding-top: 0 !important; }

/* ラジオボタンをボタン風にする */
div.stRadio > div[role="radiogroup"] { display: flex; flex-direction: row; flex-wrap: wrap; gap: 8px; }
div.stRadio > div[role="radiogroup"] > label { background-color: #ffffff !important; border: 1.5px solid #d0d7e3 !important; border-radius: 20px !important; padding: 6px 14px !important; cursor: pointer !important; transition: all 0.2s; }
div.stRadio > div[role="radiogroup"] > label:hover { background-color: #f0f4f8 !important; }
div.stRadio > div[role="radiogroup"] > label[data-baseweb="radio"] div:first-child { display: none !important; }
div.stRadio > div[role="radiogroup"] > label p { font-size: 14px !important; font-weight: 600 !important; margin: 0 !important; color: #374a5e !important; }

/* スケジュール表 */
.sched-wrap { overflow-x: auto; border-radius: 8px; }
.sched-table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 800px; background: #fff; }
.sched-table th { background: #1a6fc4; color: #fff !important; font-weight: 700; padding: 8px; border: 1px solid #0e4d8a; }
.sched-table td { border: 1px solid #d8e2ef; padding: 6px; vertical-align: top; }
.col-today { background: #fffbee !important; }
.sched-entry { border-radius: 6px; padding: 6px 8px; margin-bottom: 4px; font-size: 11px; border-left: 4px solid #1a6fc4; background: #eef4fd; }
.sched-entry.manu-entry { border-left-color: #0e8c5a; background: #e8f5f0; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# ☁️ Googleスプレッドシート接続
# ─────────────────────────────────────────────
@st.cache_resource
def init_connection():
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"接続エラー: {e}")
        st.stop()

client = init_connection()

try:
    sheet = client.open_by_url(st.secrets["spreadsheet_url"])
except Exception as e:
    st.error(f"スプレッドシートが開けません。権限を確認してください。{e}")
    st.stop()

SHEET_COLUMNS = {
    "orders": ["ID", "納品予定日", "顧客名", "大カテゴリ", "製品名", "ケース数", "登録日時"],
    "manufactures": ["ID", "製造予定日", "備考", "大カテゴリ", "製品名", "ケース数", "登録日時"],
    "master": ["大カテゴリ", "製品名", "初期在庫数"],
    "customers": ["顧客名", "ふりがな"]
}

@st.cache_data(ttl=5)
def load_data(sheet_name):
    try:
        ws = sheet.worksheet(sheet_name)
        data = ws.get_all_values()
        expected = SHEET_COLUMNS[sheet_name]
        if not data or len(data) <= 1:
            return pd.DataFrame(columns=expected)
        headers = data[0]
        df = pd.DataFrame(data[1:], columns=headers)
        
        # 数値・日付型の変換
        if "ケース数" in df.columns: df["ケース数"] = pd.to_numeric(df["ケース数"], errors="coerce").fillna(0).astype(int)
        if "初期在庫数" in df.columns: df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors="coerce").fillna(0).astype(int)
        if "納品予定日" in df.columns: df["納品予定日"] = pd.to_datetime(df["納品予定日"], errors="coerce")
        if "製造予定日" in df.columns: df["製造予定日"] = pd.to_datetime(df["製造予定日"], errors="coerce")
        if "登録日時" in df.columns: df["登録日時"] = pd.to_datetime(df["登録日時"], errors="coerce")
        return df
    except:
        return pd.DataFrame(columns=SHEET_COLUMNS[sheet_name])

def save_data(sheet_name, df):
    try:
        ws = sheet.worksheet(sheet_name)
        ws.clear()
        df_save = df.copy()
        # スプレッドシート保存用に全データを文字列に安全変換
        for col in df_save.columns:
            if pd.api.types.is_datetime64_any_dtype(df_save[col]):
                df_save[col] = df_save[col].dt.strftime('%Y-%m-%d')
        df_save = df_save.fillna("")
        data_to_update = [df_save.columns.values.tolist()] + df_save.values.tolist()
        ws.update(values=data_to_update, range_name='A1')
        load_data.clear() # キャッシュを即時クリア
        return True
    except Exception as e:
        st.error(f"保存に失敗しました: {e}")
        return False

# ─────────────────────────────────────────────
# 共通ロジック
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

@st.cache_data(ttl=5)
def simulate_inventory(orders_df, manus_df, master_df):
    today = pd.Timestamp.today().normalize()
    date_range = pd.date_range(today, today + timedelta(days=60))
    
    inv_records, alerts = [], []
    
    for _, row in master_df.iterrows():
        prod, cat = row["製品名"], row["大カテゴリ"]
        init_inv = int(row.get("初期在庫数", 0))
        
        # 過去〜現在の変動計算
        o_prod = orders_df[orders_df["製品名"] == prod]
        m_prod = manus_df[manus_df["製品名"] == prod]
        
        current_inv = init_inv
        # 過去の製造・出荷を反映（もしデータにある場合）
        current_inv += m_prod[m_prod["製造予定日"] < today]["ケース数"].sum()
        current_inv -= o_prod[o_prod["納品予定日"] < today]["ケース数"].sum()
        
        for d in date_range:
            daily_m = m_prod[m_prod["製造予定日"] == d]["ケース数"].sum()
            daily_o = o_prod[o_prod["納品予定日"] == d]["ケース数"].sum()
            current_inv += (daily_m - daily_o)
            
            inv_records.append({"日付": d, "日付_str": d.strftime("%m/%d"), "大カテゴリ": cat, "製品名": prod, "在庫数": current_inv})
            if current_inv < 0:
                alerts.append({"日付": d, "製品名": prod, "不足数": abs(current_inv), "カテゴリ": cat})
                
    return pd.DataFrame(inv_records), pd.DataFrame(alerts)

# データのロード
orders_df = load_data("orders")
manus_df = load_data("manufactures")
master_df = load_data("master")
cust_df = load_data("customers")
inv_df, alerts_df = simulate_inventory(orders_df, manus_df, master_df)

# ─────────────────────────────────────────────
# サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<div style='text-align:center; padding:20px 0;'><h2 style='color:white; margin:0;'>🏭 丸実屋</h2><p style='color:#a0aec0; font-size:12px;'>受注・在庫管理システム</p></div>", unsafe_allow_html=True)
    page = st.radio("メニュー", ["📋 受注登録 (出庫)", "🏭 製造登録 (入庫)", "📦 在庫・スケジュール確認", "📊 分析", "⚙️ マスタ管理"], label_visibility="collapsed")
    
    if not alerts_df.empty:
        st.error(f"🚨 欠品警告: {len(alerts_df['製品名'].unique())}品目")
    else:
        st.success("✅ 在庫は安定しています")

# ─────────────────────────────────────────────
# ページ表示：受注登録
# ─────────────────────────────────────────────
if page == "📋 受注登録 (出庫)":
    st.markdown('<div class="app-header"><h1>📋 受注登録 (出荷予定入力)</h1></div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["➕ 新規登録", "✏️ 登録済み一覧・修正"])
    
    with tab1:
        st.markdown('<div class="card"><div class="card-title">📝 受注情報を入力してください</div>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1: d_date = st.date_input("納品予定日", value=date.today() + timedelta(days=1))
        with col2:
            cust_options = ["✏️ 直接入力"] + sorted(cust_df["顧客名"].unique().tolist())
            sel_cust = st.selectbox("顧客名", cust_options)
            cust_name = st.text_input("顧客名を入力") if sel_cust == "✏️ 直接入力" else sel_cust
        with col3: cases = st.number_input("ケース数", min_value=1, value=1)
        
        cat_labels = ["➖ 未選択"] + [f"{CAT_ICONS.get(c)} {c}" for c in CATEGORIES]
        sel_cat_label = st.radio("カテゴリ選択", cat_labels, horizontal=True)
        sel_cat = sel_cat_label.split(" ", 1)[1] if " " in sel_cat_label else ""
        
        prods = master_df[master_df["大カテゴリ"] == sel_cat]["製品名"].tolist() if sel_cat else []
        sel_prod = st.selectbox("製品を選択", prods, format_func=format_product_name)
        
        if st.button("✅ この内容で登録する", type="primary", use_container_width=True):
            if sel_prod and cust_name:
                new_data = pd.DataFrame([{
                    "ID": "O-" + str(uuid.uuid4())[:6].upper(),
                    "納品予定日": pd.Timestamp(d_date),
                    "顧客名": cust_name,
                    "大カテゴリ": sel_cat,
                    "製品名": sel_prod,
                    "ケース数": int(cases),
                    "登録日時": pd.Timestamp.now()
                }])
                if save_data("orders", pd.concat([orders_df, new_data], ignore_index=True)):
                    st.success("登録完了！")
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.dataframe(orders_df.sort_values("納品予定日", ascending=False), use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────
# ページ表示：製造登録
# ─────────────────────────────────────────────
elif page == "🏭 製造登録 (入庫)":
    st.markdown('<div class="app-header manu-header"><h1>🏭 製造登録 (入庫予定入力)</h1></div>', unsafe_allow_html=True)
    st.markdown('<div class="card"><div class="card-title" style="color:var(--clr-manu);">📝 製造情報を入力</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1: m_date = st.date_input("製造日", value=date.today())
    with col2: m_cases = st.number_input("製造数 (ケース)", min_value=1, value=50)
    with col3: m_note = st.text_input("備考 (ロット等)")
    
    cat_labels = ["➖ 未選択"] + [f"{CAT_ICONS.get(c)} {c}" for c in CATEGORIES]
    sel_cat_label = st.radio("カテゴリ選択", cat_labels, horizontal=True, key="m_cat")
    sel_cat = sel_cat_label.split(" ", 1)[1] if " " in sel_cat_label else ""
    
    prods = master_df[master_df["大カテゴリ"] == sel_cat]["製品名"].tolist() if sel_cat else []
    sel_prod = st.selectbox("製品を選択", prods, format_func=format_product_name, key="m_prod")
    
    if st.button("➕ 製造予定を登録", type="primary", use_container_width=True):
        if sel_prod:
            new_data = pd.DataFrame([{
                "ID": "M-" + str(uuid.uuid4())[:6].upper(),
                "製造予定日": pd.Timestamp(m_date),
                "備考": m_note,
                "大カテゴリ": sel_cat,
                "製品名": sel_prod,
                "ケース数": int(m_cases),
                "登録日時": pd.Timestamp.now()
            }])
            if save_data("manufactures", pd.concat([manus_df, new_data], ignore_index=True)):
                st.success("製造予定を登録しました。")
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
# ページ表示：在庫・スケジュール
# ─────────────────────────────────────────────
elif page == "📦 在庫・スケジュール確認":
    st.markdown('<div class="app-header"><h1>📦 在庫・スケジュール確認</h1></div>', unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["📊 在庫推移表", "📆 入出庫カレンダー"])
    
    with t1:
        st.markdown('<div class="card"><div class="card-title">📅 向こう14日間の在庫予測</div>', unsafe_allow_html=True)
        if not inv_df.empty:
            target_days = (pd.Timestamp.today().normalize() + timedelta(days=14))
            view_df = inv_df[inv_df["日付"] <= target_days].pivot_table(index=["大カテゴリ", "製品名"], columns="日付_str", values="在庫数", aggfunc="last").reset_index()
            
            def highlight_neg(val):
                if isinstance(val, (int, float)) and val < 0: return 'color: red; font-weight: bold; background-color: #ffebee;'
                return ''
            
            st.dataframe(view_df.style.applymap(highlight_neg), use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with t2:
        st.markdown('<div class="card"><div class="card-title">📆 直近7日間のスケジュール</div>', unsafe_allow_html=True)
        today = pd.Timestamp.today().normalize()
        days = [today + timedelta(days=i) for i in range(7)]
        
        rows_html = ""
        for d in days:
            d_str = d.strftime("%m/%d")
            # 製造
            m_items = manus_df[manus_df["製造予定日"] == d]
            m_html = "".join([f'<div class="sched-entry manu-entry"><b>製造:</b> {r["製品名"]} ({r["ケース数"]}cs)</div>' for _, r in m_items.iterrows()])
            # 受注
            o_items = orders_df[orders_df["納品予定日"] == d]
            o_html = "".join([f'<div class="sched-entry"><b>出荷:</b> {r["顧客名"]} / {r["製品名"]} ({r["ケース数"]}cs)</div>' for _, r in o_items.iterrows()])
            
            is_today = "col-today" if d == today else ""
            rows_html += f'<tr><td class="col-label {is_today}">{d_str}</td><td class="{is_today}">{m_html}</td><td class="{is_today}">{o_html}</td></tr>'
            
        st.markdown(f'<div class="sched-wrap"><table class="sched-table"><tr><th>日付</th><th>🏭 製造予定</th><th>📋 出荷予定</th></tr>{rows_html}</table></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
# ページ表示：マスタ管理
# ─────────────────────────────────────────────
elif page == "⚙️ マスタ管理":
    st.markdown('<div class="app-header"><h1>⚙️ マスタ・初期在庫管理</h1></div>', unsafe_allow_html=True)
    
    st.info("💡 初期在庫数を変更すると、その数値を起点に未来の在庫が再計算されます。")
    ed_master = st.data_editor(master_df, num_rows="dynamic", use_container_width=True)
    if st.button("💾 製品マスタを保存", type="primary"):
        save_data("master", ed_master)
        st.success("保存しました。")
        st.rerun()

    st.markdown("---")
    st.markdown("### 🏢 顧客リスト管理")
    ed_cust = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True)
    if st.button("💾 顧客マスタを保存"):
        save_data("customers", ed_cust)
        st.success("保存しました。")
        st.rerun()
