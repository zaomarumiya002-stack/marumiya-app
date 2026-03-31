"""
丸実屋 受注・製造・在庫管理アプリ (クラウド・デザイン復元＆高速安定版)
=========================================
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
import numpy as np

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# ページ設定 & パスワード保護（ログイン画面）
# ─────────────────────────────────────────────
st.set_page_config(page_title="丸実屋 受注・在庫管理", page_icon="🏭", layout="wide", initial_sidebar_state="expanded")

def check_password():
    """パスワードが合っているかチェックする"""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align: center; margin-top: 80px; color:#1a6fc4;'>🏭 丸実屋システム ログイン</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color:#5a6a7e;'>アクセスにはパスワードが必要です。</p>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            pwd = st.text_input("パスワードを入力", type="password")
            if st.button("ログイン", type="primary", use_container_width=True):
                # 金庫(Secrets)に設定したパスワードと一致するか確認
                if pwd == st.secrets["app_password"]:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("❌ パスワードが違います")
        st.stop() # パスワードが合うまで、これより下の画面は表示しない

check_password()

# ─────────────────────────────────────────────
# カスタムCSS (初期のものを完全復元)
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
html, body,[class*="css"] { font-family: 'Noto Sans JP', sans-serif !important; color: var(--clr-text); background-color: var(--clr-bg); }
.app-header { background: linear-gradient(135deg, var(--clr-primary) 0%, var(--clr-primary-dk) 100%); border-radius: var(--radius); padding: 14px 24px; margin-bottom: 16px; display: flex; align-items: center; gap: 12px; box-shadow: var(--shadow); }
.app-header.manu-header { background: linear-gradient(135deg, var(--clr-manu) 0%, var(--clr-manu-dk) 100%); }
.app-header.guide-header { background: linear-gradient(135deg, #7c3db8 0%, #5a2a8c 100%); }
.app-header h1 { margin: 0; padding: 0; font-size: 20px; font-weight: 900; color: #ffffff !important; letter-spacing: 0.04em; }
.card { background: var(--clr-card); border: 1px solid var(--clr-border); border-radius: var(--radius); padding: 18px 22px; margin-bottom: 16px; box-shadow: var(--shadow); }
.card-title { font-size: 15px; font-weight: 700; color: var(--clr-primary); border-bottom: 2px solid var(--clr-primary); padding-bottom: 8px; margin-bottom: 14px; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0b2239 0%, #14365d 100%) !important; }[data-testid="stSidebar"] * { color: #e2e8f0 !important; }[data-testid="stSidebar"] div[role="radiogroup"] label { background-color: transparent !important; border: none !important; padding: 12px 16px !important; border-radius: 8px !important; margin-bottom: 4px !important; transition: background 0.2s, color 0.2s; cursor: pointer; }[data-testid="stSidebar"] div[role="radiogroup"] label:hover { background: rgba(255, 255, 255, 0.1) !important; }[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) { background: #0e8c5a !important; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p { color: #ffffff !important; font-weight: 900 !important; }[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child { display: none !important; }
div.stRadio > div[role="radiogroup"] { display: flex; flex-direction: row; flex-wrap: wrap; gap: 8px; }
div.stRadio > div[role="radiogroup"] > label { background-color: #ffffff !important; border: 1.5px solid #d0d7e3 !important; border-radius: 20px !important; padding: 6px 14px !important; margin: 0 !important; cursor: pointer !important; box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important; transition: all 0.2s ease-in-out !important; }
div.stRadio > div[role="radiogroup"] > label:hover { background-color: #f0f4f8 !important; border-color: #b0bec5 !important; }
div.stRadio > div[role="radiogroup"] > label > div:first-child { display: none !important; }
div.stRadio > div[role="radiogroup"] > label p { font-size: 14px !important; font-weight: 600 !important; margin: 0 !important; color: #374a5e !important; }
.stSelectbox label, .stTextInput label, .stNumberInput label, .stDateInput label { font-size: 13px !important; font-weight: 700 !important; color: #1c2a3a !important; }
.sched-wrap { overflow-x: auto; border-radius: 8px; box-shadow: var(--shadow); }
.sched-table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 800px; background: #fff; }
.sched-table th { background: #1a6fc4; color: #fff !important; font-weight: 700; padding: 8px; text-align: center; white-space: nowrap; border: 1px solid #0e4d8a; }
.sched-table td { border: 1px solid #d8e2ef; padding: 6px; vertical-align: top; }
.sched-table td.col-label { background: #f4f7fc; font-weight: 700; text-align: center; white-space: nowrap; width: 80px; }
.sched-table td.col-today { background: #fffbee; border-left: 2px solid #f0a500; border-right: 2px solid #f0a500; }
.sched-entry { border-radius: 6px; padding: 6px 8px; margin-bottom: 6px; font-size: 12px; line-height: 1.4; border-left: 4px solid #1a6fc4; background: #eef4fd; }
.sched-entry.manu-entry { border-left: 4px solid #0e8c5a; background: #e8f5f0; }
.sched-entry .s-prod { color: #374a5e; font-size: 12px; font-weight: 700; margin-bottom: 2px; }
.sched-empty { color: #b0bec5; font-size: 12px; text-align: center; padding: 8px 0; }
.alert-banner { background-color: #fce8e6; border-left: 6px solid #d93025; padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; display: flex; align-items: center; gap: 12px; }
.alert-banner-icon { font-size: 24px; }
.alert-banner-text { color: #d93025; font-weight: 700; font-size: 14px; }
div[data-testid="stAlert"] { border-radius: 10px !important; border: 1.5px solid #1e8c45 !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# ☁️ Googleスプレッドシート接続設定
# ─────────────────────────────────────────────
@st.cache_resource
def init_connection():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(creds)

client = init_connection()
spreadsheet_url = st.secrets["spreadsheet_url"]
sheet = client.open_by_url(spreadsheet_url)

# ─────────────────────────────────────────────
# データアクセス関数 (高速化とバグ修正)
# ─────────────────────────────────────────────
def get_empty_df(sheet_name):
    if sheet_name == "orders": return pd.DataFrame(columns=["ID", "納品予定日", "顧客名", "大カテゴリ", "製品名", "ケース数", "登録日時"])
    elif sheet_name == "manufactures": return pd.DataFrame(columns=["ID", "製造予定日", "備考", "大カテゴリ", "製品名", "ケース数", "登録日時"])
    elif sheet_name == "master": return pd.DataFrame(columns=["大カテゴリ", "製品名", "初期在庫数"])
    elif sheet_name == "customers": return pd.DataFrame(columns=["顧客名", "ふりがな"])
    return pd.DataFrame()

# ttl=600 で 10分間キャッシュを維持し、動作を爆速にする
@st.cache_data(ttl=600)
def load_data(sheet_name):
    try:
        ws = sheet.worksheet(sheet_name)
        data = ws.get_all_values()
        if not data: return get_empty_df(sheet_name)
        headers = data.pop(0)
        df = pd.DataFrame(data, columns=headers)
        
        # 型の変換 (スプレッドシートの空文字を適切に処理)
        if "ケース数" in df.columns: df["ケース数"] = pd.to_numeric(df["ケース数"], errors="coerce").fillna(0).astype(int)
        if "初期在庫数" in df.columns: df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors="coerce").fillna(0).astype(int)
        if "納品予定日" in df.columns: df["納品予定日"] = pd.to_datetime(df["納品予定日"], errors="coerce")
        if "製造予定日" in df.columns: df["製造予定日"] = pd.to_datetime(df["製造予定日"], errors="coerce")
        if "登録日時" in df.columns: df["登録日時"] = pd.to_datetime(df["登録日時"], errors="coerce")
        return df
    except Exception as e:
        st.error(f"データの読み込みに失敗しました ({sheet_name}): {e}")
        return get_empty_df(sheet_name)

def save_data(sheet_name, df):
    try:
        ws = sheet.worksheet(sheet_name)
        ws.clear()
        df_str = df.copy()
        
        # 登録・保存バグの最大の原因：Datetime型の NaN/NaT がスプレッドシート書き込み時にエラーを起こすのを防ぐ
        for col in df_str.select_dtypes(include=['datetime64[ns]', 'datetime64[ns, UTC]']).columns:
            df_str[col] = df_str[col].dt.strftime('%Y-%m-%d %H:%M:%S').replace('NaT', '')
        
        df_str = df_str.fillna("")
        df_str = df_str.replace({np.nan: ""}) # 完全な空文字処理
        
        ws.update(values=[df_str.columns.values.tolist()] + df_str.values.tolist(), range_name='A1')
        
        # 保存完了時にキャッシュをクリアして、最新のデータを表示させる
        load_data.clear()
        simulate_inventory.clear()
    except Exception as e:
        st.error(f"データの保存に失敗しました ({sheet_name}): {e}")

# マスタ系の保存用ラップ関数
def save_customers(df: pd.DataFrame): save_data("customers", df)
def save_orders(df: pd.DataFrame): save_data("orders", df)
def save_manufactures(df: pd.DataFrame): save_data("manufactures", df)
def save_master(df: pd.DataFrame): save_data("master", df)

# ─────────────────────────────────────────────
# マスタ定義
# ─────────────────────────────────────────────
CATEGORIES =["平こん", "つきこん", "糸こん・しらたき", "三角こん", "玉こん", "ダイスこん", "短冊", "国産", "ちぎりこん", "大黒屋", "かねこ", "冷凍耐性", "その他"]
CAT_ICONS = {"平こん": "🟫", "つきこん": "🍝", "糸こん・しらたき": "🍜", "三角こん": "🔺", "玉こん": "🟤", "ダイスこん": "🎲", "短冊": "🏷️", "国産": "🇯🇵", "ちぎりこん": "🤲", "大黒屋": "🏮", "かねこ": "🏭", "冷凍耐性": "❄️", "その他": "📦"}
CAT_COLORS = {"平こん": "#8b5a2b", "つきこん": "#0e8c5a", "糸こん・しらたき": "#7c3db8", "三角こん": "#d97706", "玉こん": "#6b4226", "ダイスこん": "#0e7c8c", "短冊": "#1a6fc4", "国産": "#c41a3a", "ちぎりこん": "#d96606", "大黒屋": "#333333", "かねこ": "#2563a8", "冷凍耐性": "#4a90e2", "その他": "#6b7280"}
WEEKDAYS_JA =["月","火","水","木","金","土","日"]

@st.cache_data(ttl=600)
def simulate_inventory(orders_df, manus_df, master_df, forecast_days=60):
    o_tmp = orders_df[["納品予定日", "製品名", "ケース数"]].copy().dropna()
    o_tmp.rename(columns={"納品予定日": "日付"}, inplace=True)
    o_tmp["変動"] = -o_tmp["ケース数"]

    m_tmp = manus_df[["製造予定日", "製品名", "ケース数"]].copy().dropna()
    m_tmp.rename(columns={"製造予定日": "日付"}, inplace=True)
    m_tmp["変動"] = m_tmp["ケース数"]

    events = pd.concat([o_tmp[["日付", "製品名", "変動"]], m_tmp[["日付", "製品名", "変動"]]])
    if not events.empty:
        events["日付"] = pd.to_datetime(events["日付"]).dt.normalize()

    today = pd.Timestamp.today().normalize()
    date_range = pd.date_range(today, today + timedelta(days=forecast_days))

    inv_records, alerts = [],[]

    for _, row in master_df.iterrows():
        prod, cat = row["製品名"], row["大カテゴリ"]
        init_inv = int(row.get("初期在庫数", 0))

        if not events.empty:
            prod_events = events[events["製品名"] == prod]
            past_events = prod_events[prod_events["日付"] < today]
            current_inv = init_inv + past_events["変動"].sum()
            future_events = prod_events[prod_events["日付"] >= today].groupby("日付")["変動"].sum()
        else:
            current_inv = init_inv
            future_events = {}

        for d in date_range:
            chg = future_events.get(d, 0) if isinstance(future_events, pd.Series) else 0
            current_inv += chg
            inv_records.append({"日付": d, "日付_str": d.strftime("%m/%d"), "大カテゴリ": cat, "製品名": prod, "在庫数": current_inv})
            if current_inv < 0:
                alerts.append({"日付": d, "製品名": prod, "不足数": abs(current_inv), "カテゴリ": cat})

    inv_df = pd.DataFrame(inv_records)
    alerts_df = pd.DataFrame(alerts)
    if not alerts_df.empty:
        alerts_df = alerts_df.sort_values("日付").groupby("製品名").first().reset_index().sort_values("日付")

    return inv_df, alerts_df

# --- 初期化 ---
if "order_key" not in st.session_state: st.session_state.order_key = 0
if "manu_key" not in st.session_state: st.session_state.manu_key = 0
if "order_success_msg" not in st.session_state: st.session_state.order_success_msg = ""
if "manu_success_msg" not in st.session_state: st.session_state.manu_success_msg = ""

def format_product_name(p_name):
    if pd.isna(p_name): return ""
    if "（黒）" in p_name or "黒" in p_name: return f"⚫️ {p_name}"
    if "（白）" in p_name or "白" in p_name: return f"⚪️ {p_name}"
    return f"📦 {p_name}"

orders_df = load_data("orders")
manus_df = load_data("manufactures")
master_df = load_data("master")
cust_df = load_data("customers")
inv_df, alerts_df = simulate_inventory(orders_df, manus_df, master_df)
cat_options = ["➖ 未選択"] +[f"{CAT_ICONS.get(c, '📦')} {c}" for c in CATEGORIES]

# ─────────────────────────────────────────────
# サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding:18px 10px; border-bottom:1px solid rgba(255,255,255,0.12);">
      <span style="font-size:38px; line-height:1;">🏭</span>
      <div style="font-size:17px; font-weight:900; margin-top:8px; color:#fff;">丸実屋</div>
      <div style="font-size:12px; opacity:.65; margin-top:3px; color:#dce8f8;">製造・在庫管理システム</div>
    </div>
    """, unsafe_allow_html=True)

    page = st.radio("メニュー",["📋 受注登録 (出庫)", "🏭 製造登録 (入庫)", "📦 スケジュール・在庫確認", "📊 統計・分析", "⚙️ マスタ管理", "📖 使い方ガイド"], label_visibility="collapsed")
    st.markdown("<hr style='border-color:rgba(255,255,255,0.12); margin:14px 0;'>", unsafe_allow_html=True)
    
    if not alerts_df.empty:
        st.markdown(f'<div style="background:rgba(217,48,37,0.15); border:1px solid #d93025; border-radius:8px; padding:10px;"><div style="color:#ff6b6b; font-weight:900; font-size:14px; margin-bottom:8px;">⚠️ 欠品アラート ({len(alerts_df)}件)</div>', unsafe_allow_html=True)
        for _, r in alerts_df.iterrows():
            st.markdown(f'<div style="font-size:12px; color:#f0f3f8; margin-bottom:4px;"><span style="color:#ff6b6b; font-weight:bold;">{r["日付"].strftime("%m/%d")}</span>: {r["製品名"]} <span style="color:#ffc107;">(-{r["不足数"]})</span></div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown('<div style="background:rgba(30,140,69,0.15); border:1px solid #1e8c45; border-radius:8px; padding:10px; text-align:center; color:#4ade80; font-weight:900; font-size:13px;">✅ 欠品の予定はありません</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 各画面の描画
# ─────────────────────────────────────────────
if page == "📋 受注登録 (出庫)":
    st.markdown("<style>div.stRadio > div[role='radiogroup'] > label:has(input:checked) { background-color: var(--clr-primary) !important; border-color: var(--clr-primary) !important; box-shadow: 0 3px 8px rgba(26,111,196,0.3) !important; } div.stRadio > div[role='radiogroup'] > label:has(input:checked) p { color: #ffffff !important; font-weight: 700 !important; }</style>", unsafe_allow_html=True)
    st.markdown('<div class="app-header"><span class="hicon">📋</span><h1>受注登録 (出荷予定)</h1></div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["➕ 新規受注", "✏️ データ一覧・個別編集"])
    
    with tab1:
        st.markdown('<div class="card"><div class="card-title">📝 受注情報 (在庫からマイナス)</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1.5, 2, 1])
        okey = st.session_state.order_key
        with c1: delivery_date = st.date_input("📅 納品予定日 ＊", value=date.today() + timedelta(days=1), key=f"o_date_{okey}")
        with c2: 
            cust_opts =["✏️ 新規・直接入力"] + [f"{r['顧客名']} ({r['ふりがな']})" if r['ふりがな'] else r['顧客名'] for _, r in cust_df.iterrows()]
            selected_cust_opt = st.selectbox("🏢 顧客名を選択 (ふりがな検索可)", cust_opts, key=f"o_cust_sel_{okey}")
            if selected_cust_opt == "✏️ 新規・直接入力": customer_name = st.text_input("📝 新規顧客名を入力 (任意)", placeholder="例：〇〇スーパー", key=f"o_cust_txt_{okey}")
            else: customer_name = selected_cust_opt.rsplit(" (", 1)[0] if " (" in selected_cust_opt and selected_cust_opt.endswith(")") else selected_cust_opt
        with c3: cases = st.number_input("📦 ケース数 ＊", min_value=1, max_value=9999, value=1, step=1, key=f"o_cases_{okey}")
        st.markdown("<hr style='border-top:1px dashed #d0d7e3; margin:14px 0;'>", unsafe_allow_html=True)
        st.write("📂 **大カテゴリを選択**")
        selected_label = st.radio("大カテゴリ", cat_options, horizontal=True, label_visibility="collapsed", key=f"o_cat_{okey}")
        selected_cat = selected_label.split(" ", 1)[1] if selected_label != "➖ 未選択" else ""
        st.markdown("<hr style='border-top:1px dashed #d0d7e3; margin:14px 0;'>", unsafe_allow_html=True)
        products_all = master_df[master_df["大カテゴリ"] == selected_cat]["製品名"].tolist() if selected_cat else master_df["製品名"].tolist()
        sc1, sc2 = st.columns([1.5, 2.5])
        with sc1: prod_search = st.text_input("🔍 絞り込み検索", placeholder="キーワード...", key=f"o_search_{okey}")
        products_filtered =[p for p in products_all if prod_search in p] if prod_search else products_all
        with sc2:
            selected_product = st.selectbox("📦 製品を選択 ＊", products_filtered, format_func=format_product_name, key=f"o_prod_{okey}") if products_filtered and selected_cat else ""
            if not selected_cat: st.info("⬆️ まず上のカテゴリボタンを押してください")
        st.markdown('<br>', unsafe_allow_html=True)
        
        if st.button("✅ 受注を登録する", type="primary", use_container_width=True):
            if not selected_cat or not selected_product:
                st.error("⚠️ カテゴリと製品名は必須です。")
            else:
                c_name = customer_name.strip() if customer_name.strip() else "未指定"
                if c_name != "未指定" and c_name not in cust_df["顧客名"].values:
                    # コピーを渡すことでキャッシュ編集エラーを回避
                    new_cust = pd.DataFrame([{"顧客名": c_name, "ふりがな": ""}])
                    save_customers(pd.concat([cust_df.copy(), new_cust], ignore_index=True))
                
                new_row = pd.DataFrame([{"ID": "O-" + str(uuid.uuid4())[:6].upper(), "納品予定日": pd.Timestamp(delivery_date), "顧客名": c_name, "大カテゴリ": selected_cat, "製品名": selected_product, "ケース数": int(cases), "登録日時": pd.Timestamp.now()}])
                save_orders(pd.concat([orders_df.copy(), new_row], ignore_index=True))
                
                st.session_state.order_success_msg = f"✅ 【{c_name}】 {format_product_name(selected_product)} × {cases}ケース を登録しました！引き続き入力できます。"
                st.session_state.order_key += 1
                st.rerun()

        if st.session_state.order_success_msg:
            st.success(st.session_state.order_success_msg)
            st.session_state.order_success_msg = ""
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="card"><div class="card-title">🔍 直近の受注データ一覧</div>', unsafe_allow_html=True)
        st.dataframe(orders_df.sort_values("納品予定日", ascending=False).head(50), use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="card"><div class="card-title" style="color:var(--clr-accent); border-bottom-color:var(--clr-accent);">✏️ データの個別編集・削除</div>', unsafe_allow_html=True)
        edit_target = st.selectbox("📝 編集・削除するデータ (ID) を選択",["➖ 選択してください"] + orders_df["ID"].tolist())
        if edit_target != "➖ 選択してください":
            target_row = orders_df[orders_df["ID"] == edit_target].iloc[0]
            ec1, ec2, ec3 = st.columns([1.5, 2, 1])
            e_date = ec1.date_input("納品予定日", value=target_row["納品予定日"])
            cust_opts_edit =["✏️ 新規・直接入力"] +[f"{r['顧客名']} ({r['ふりがな']})" if r['ふりがな'] else r['顧客名'] for _, r in cust_df.iterrows()]
            t_cust = target_row["顧客名"]
            def_idx = 0
            if t_cust != "未指定":
                for i, opt in enumerate(cust_opts_edit):
                    if opt.startswith(t_cust + " (") or opt == t_cust: def_idx = i; break
            sel_e_cust = ec2.selectbox("顧客名を選択", cust_opts_edit, index=def_idx)
            if sel_e_cust == "✏️ 新規・直接入力": e_cust = ec2.text_input("📝 新規顧客名を入力", value=t_cust if t_cust != "未指定" else "")
            else: e_cust = sel_e_cust.rsplit(" (", 1)[0] if " (" in sel_e_cust and sel_e_cust.endswith(")") else sel_e_cust
            e_cases = ec3.number_input("ケース数", value=int(target_row["ケース数"]), min_value=1)
            e_cat = st.selectbox("大カテゴリ", CATEGORIES, index=CATEGORIES.index(target_row["大カテゴリ"]) if target_row["大カテゴリ"] in CATEGORIES else 0)
            e_mode = st.radio("製品名の入力方法",["リストから選択", "直接入力 (特注・リスト外)"], horizontal=True)
            if e_mode == "リストから選択":
                p_list = master_df[master_df["大カテゴリ"] == e_cat]["製品名"].tolist()
                if target_row["製品名"] not in p_list: p_list = [target_row["製品名"]] + p_list
                e_prod = st.selectbox("製品名", p_list, index=p_list.index(target_row["製品名"]) if target_row["製品名"] in p_list else 0, format_func=format_product_name)
            else: e_prod = st.text_input("製品名を直接入力", value=target_row["製品名"])
            
            col_u, col_d = st.columns(2)
            if col_u.button("💾 この内容で更新", type="primary", use_container_width=True):
                c_name_edited = e_cust.strip() if e_cust.strip() else "未指定"
                if c_name_edited != "未指定" and c_name_edited not in cust_df["顧客名"].values:
                    new_cust = pd.DataFrame([{"顧客名": c_name_edited, "ふりがな": ""}])
                    save_customers(pd.concat([cust_df.copy(), new_cust], ignore_index=True))
                
                # コピーを作成して編集エラーを回避
                temp_orders = orders_df.copy()
                idx = temp_orders[temp_orders["ID"] == edit_target].index[0]
                temp_orders.at[idx, "納品予定日"] = pd.Timestamp(e_date)
                temp_orders.at[idx, "顧客名"] = c_name_edited
                temp_orders.at[idx, "大カテゴリ"] = e_cat
                temp_orders.at[idx, "製品名"] = e_prod
                temp_orders.at[idx, "ケース数"] = int(e_cases)
                save_orders(temp_orders)
                st.rerun()
                
            if col_d.button("🗑️ このデータを削除", use_container_width=True):
                temp_orders = orders_df.copy()
                save_orders(temp_orders[temp_orders["ID"] != edit_target])
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

elif page == "🏭 製造登録 (入庫)":
    st.markdown("<style>div.stRadio > div[role='radiogroup'] > label:has(input:checked) { background-color: var(--clr-manu) !important; border-color: var(--clr-manu) !important; box-shadow: 0 3px 8px rgba(14,140,90,0.3) !important; } div.stRadio > div[role='radiogroup'] > label:has(input:checked) p { color: #ffffff !important; font-weight: 700 !important; }</style>", unsafe_allow_html=True)
    st.markdown('<div class="app-header manu-header"><span class="hicon">🏭</span><h1>製造登録 (入庫予定)</h1></div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["➕ 新規製造", "✏️ データ一覧・個別編集"])
    
    with tab1:
        st.markdown('<div class="card"><div class="card-title" style="color:var(--clr-manu); border-bottom-color:var(--clr-manu);">📝 製造情報 (在庫にプラス)</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1.5, 1.2, 2.3])
        mkey = st.session_state.manu_key
        with c1: manu_date = st.date_input("📅 製造予定日 ＊", value=date.today(), key=f"m_date_{mkey}")
        with c2: cases = st.number_input("📦 製造ケース数 ＊", min_value=1, max_value=9999, value=50, step=10, key=f"m_cases_{mkey}")
        with c3: note = st.text_input("📝 備考 (ロット等)", placeholder="任意", key=f"m_note_{mkey}")
        st.markdown("<hr style='border-top:1px dashed #d0d7e3; margin:14px 0;'>", unsafe_allow_html=True)
        st.write("📂 **大カテゴリを選択**")
        selected_label = st.radio("大カテゴリ", cat_options, horizontal=True, label_visibility="collapsed", key=f"m_cat_{mkey}")
        selected_cat = selected_label.split(" ", 1)[1] if selected_label != "➖ 未選択" else ""
        st.markdown("<hr style='border-top:1px dashed #d0d7e3; margin:14px 0;'>", unsafe_allow_html=True)
        products_all = master_df[master_df["大カテゴリ"] == selected_cat]["製品名"].tolist() if selected_cat else master_df["製品名"].tolist()
        sc1, sc2 = st.columns([1.5, 2.5])
        with sc1: prod_search = st.text_input("🔍 絞り込み検索", placeholder="キーワード...", key=f"m_search_{mkey}")
        products_filtered =[p for p in products_all if prod_search in p] if prod_search else products_all
        with sc2:
            selected_product = st.selectbox("📦 製品を選択 ＊", products_filtered, format_func=format_product_name, key=f"m_prod_{mkey}") if products_filtered and selected_cat else ""
            if not selected_cat: st.info("⬆️ まず上のカテゴリボタンを押してください")
        st.markdown('<br>', unsafe_allow_html=True)

        if st.button("➕ 製造を登録する", type="primary", use_container_width=True):
            if not selected_cat or not selected_product:
                st.error("⚠️ カテゴリと製品名は必須です。")
            else:
                new_row = pd.DataFrame([{"ID": "M-" + str(uuid.uuid4())[:6].upper(), "製造予定日": pd.Timestamp(manu_date), "備考": note.strip(), "大カテゴリ": selected_cat, "製品名": selected_product, "ケース数": int(cases), "登録日時": pd.Timestamp.now()}])
                save_manufactures(pd.concat([manus_df.copy(), new_row], ignore_index=True))
                st.session_state.manu_success_msg = f"✅ 【製造予定】 {format_product_name(selected_product)} × {cases}ケース を登録しました！引き続き入力できます。"
                st.session_state.manu_key += 1
                st.rerun()

        if st.session_state.manu_success_msg:
            st.success(st.session_state.manu_success_msg)
            st.session_state.manu_success_msg = ""
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="card"><div class="card-title" style="color:var(--clr-manu); border-bottom-color:var(--clr-manu);">🔍 直近の製造データ一覧</div>', unsafe_allow_html=True)
        st.dataframe(manus_df.sort_values("製造予定日", ascending=False).head(50), use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="card"><div class="card-title" style="color:var(--clr-accent); border-bottom-color:var(--clr-accent);">✏️ データの個別編集・削除</div>', unsafe_allow_html=True)
        edit_target = st.selectbox("📝 編集・削除するデータ (ID) を選択", ["➖ 選択してください"] + manus_df["ID"].tolist())
        if edit_target != "➖ 選択してください":
            target_row = manus_df[manus_df["ID"] == edit_target].iloc[0]
            ec1, ec2, ec3 = st.columns([1.5, 1.2, 2.3])
            e_date = ec1.date_input("製造予定日", value=target_row["製造予定日"])
            e_cases = ec2.number_input("製造ケース数", value=int(target_row["ケース数"]), min_value=1)
            e_note = ec3.text_input("備考", value=target_row["備考"] if pd.notna(target_row["備考"]) else "")
            e_cat = st.selectbox("大カテゴリ", CATEGORIES, index=CATEGORIES.index(target_row["大カテゴリ"]) if target_row["大カテゴリ"] in CATEGORIES else 0)
            e_mode = st.radio("製品名の入力方法",["リストから選択", "直接入力 (特注・リスト外)"], horizontal=True)
            if e_mode == "リストから選択":
                p_list = master_df[master_df["大カテゴリ"] == e_cat]["製品名"].tolist()
                if target_row["製品名"] not in p_list: p_list =[target_row["製品名"]] + p_list
                e_prod = st.selectbox("製品名", p_list, index=p_list.index(target_row["製品名"]) if target_row["製品名"] in p_list else 0, format_func=format_product_name)
            else: e_prod = st.text_input("製品名を直接入力", value=target_row["製品名"])
            
            col_u, col_d = st.columns(2)
            if col_u.button("💾 この内容で更新", type="primary", use_container_width=True):
                temp_manus = manus_df.copy()
                idx = temp_manus[temp_manus["ID"] == edit_target].index[0]
                temp_manus.at[idx, "製造予定日"] = pd.Timestamp(e_date)
                temp_manus.at[idx, "備考"] = e_note.strip()
                temp_manus.at[idx, "大カテゴリ"] = e_cat
                temp_manus.at[idx, "製品名"] = e_prod
                temp_manus.at[idx, "ケース数"] = int(e_cases)
                save_manufactures(temp_manus)
                st.rerun()
            if col_d.button("🗑️ このデータを削除", use_container_width=True):
                temp_manus = manus_df.copy()
                save_manufactures(temp_manus[temp_manus["ID"] != edit_target])
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

elif page == "📦 スケジュール・在庫確認":
    st.markdown('<div class="app-header"><span class="hicon">📦</span><h1>スケジュール・在庫確認</h1></div>', unsafe_allow_html=True)
    if not alerts_df.empty: st.markdown('<div class="alert-banner"><div class="alert-banner-icon">🚨</div><div class="alert-banner-text">注意：以下の製品で在庫がマイナス（欠品）になる予定です。至急、製造登録を行ってください。</div></div>', unsafe_allow_html=True)

    tab_inv, tab_alert, tab_sched = st.tabs(["📊 在庫推移", f"⚠️ アラート ({len(alerts_df)})", "📆 直近スケジュール (入出庫)"])
    with tab_inv:
        st.markdown('<div class="card"><div class="card-title">📅 向こう2週間の日別在庫推移</div><div style="font-size:13px; margin-bottom:10px;">※ 数量がマイナスになる日は赤字で表示されます。（初期在庫 ＋ 累積製造 － 累積出荷）</div>', unsafe_allow_html=True)
        display_days = 14
        end_date = pd.Timestamp.today().normalize() + timedelta(days=display_days)
        inv_view = inv_df[inv_df["日付"] <= end_date]
        if not inv_view.empty:
            pivot_df = inv_view.pivot_table(index=["大カテゴリ", "製品名"], columns="日付_str", values="在庫数", aggfunc='last').reset_index()
            def highlight_negative(val):
                if isinstance(val, (int, float)) and val < 0: return 'color: #d93025; font-weight: 900; background-color: #fce8e6;'
                return ''
            pivot_df['cat_order'] = pivot_df['大カテゴリ'].apply(lambda x: CATEGORIES.index(x) if x in CATEGORIES else 99)
            pivot_df = pivot_df.sort_values(['cat_order', '製品名']).drop('cat_order', axis=1)
            pivot_df["製品名"] = pivot_df["製品名"].apply(format_product_name)
            st.dataframe(pivot_df.style.map(highlight_negative), use_container_width=True, hide_index=True, height=500)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_alert:
        st.markdown('<div class="card"><div class="card-title" style="color:var(--clr-danger); border-bottom-color:var(--clr-danger);">🚨 欠品が予定されている製品一覧</div>', unsafe_allow_html=True)
        if alerts_df.empty: st.success("素晴らしい！現在、欠品予定の製品はありません。")
        else:
            show_al = alerts_df.copy()
            show_al["欠品発生日"] = show_al["日付"].apply(lambda x: x.strftime("%Y/%m/%d"))
            show_al["製品名"] = show_al["製品名"].apply(format_product_name)
            st.dataframe(show_al[["欠品発生日", "カテゴリ", "製品名", "不足数"]], use_container_width=True, hide_index=True)
            st.info("💡 解決方法：左のメニュー「🏭 製造登録」から、対象製品の製造予定（入庫）を追加してください。")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_sched:
        st.markdown('<div class="card"><div class="card-title">📆 直近1週間（入出庫 マトリクス）</div>', unsafe_allow_html=True)
        today = pd.Timestamp.today().normalize()
        day_list =[today + timedelta(days=i) for i in range(7)]
        header = '<tr><th style="min-width:110px;">種類</th>'
        for d in day_list:
            is_t = (d == today)
            td_badge = '<br><span style="background:#fff3; font-size:9px; padding:1px 5px; border-radius:3px;">TODAY</span>' if is_t else ""
            header += f'<th class="{"col-today" if is_t else ""}">{d.strftime("%m/%d")}（{WEEKDAYS_JA[d.dayofweek]}）{td_badge}</th>'
        header += "</tr>"
        max_order = orders_df["ケース数"].max() if not orders_df.empty else 1
        max_manu = manus_df["ケース数"].max() if not manus_df.empty else 1
        max_cases_val = max(300, max_order, max_manu)
        def get_bar_html(val, color_hex, is_plus=True):
            pct = min(100, int((val / max_cases_val) * 100))
            if pct < 2: pct = 2
            sign = "+" if is_plus else "-"
            return f"""<div style="position:relative; background:#e0e6ed; border-radius:4px; height:18px; margin-top:4px; overflow:hidden;"><div style="width:{pct}%; background:{color_hex}; height:100%; border-radius:4px; opacity:0.85;"></div><div style="position:absolute; top:0; right:4px; line-height:18px; font-size:11px; font-weight:900; color:#1c2a3a;">{sign}{val}</div></div>"""

        body = ""
        body += '<tr><td class="col-label" style="color:var(--clr-manu);">🏭 製造予定<br><span style="font-size:10px">(入庫)</span></td>'
        for d in day_list:
            day_manus = manus_df[manus_df["製造予定日"] == d]
            cell = ""
            for _, r in day_manus.iterrows():
                p_disp = format_product_name(r["製品名"])
                cell += f'<div class="sched-entry manu-entry"><div class="s-prod">{p_disp}</div>{get_bar_html(int(r["ケース数"]), "#0e8c5a", True)}</div>'
            body += f'<td class="{"col-today" if d == today else ""}">{cell if cell else "<div class=sched-empty>—</div>"}</td>'
        body += "</tr>"

        body += '<tr><td class="col-label" style="color:var(--clr-primary);">📋 出荷予定<br><span style="font-size:10px">(出庫)</span></td>'
        for d in day_list:
            day_orders = orders_df[orders_df["納品予定日"] == d]
            cell = ""
            for _, r in day_orders.iterrows():
                cat_c = CAT_COLORS.get(r["大カテゴリ"], "#1a6fc4")
                p_disp = format_product_name(r["製品名"])
                cell += f'<div class="sched-entry" style="border-left-color:{cat_c};"><div class="s-prod">{p_disp}</div>{get_bar_html(int(r["ケース数"]), cat_c, False)}</div>'
            body += f'<td class="{"col-today" if d == today else ""}">{cell if cell else "<div class=sched-empty>—</div>"}</td>'
        body += "</tr>"
        st.markdown(f'<div class="sched-wrap"><table class="sched-table"><thead>{header}</thead><tbody>{body}</tbody></table></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

elif page == "📊 統計・分析":
    st.markdown('<div class="app-header"><span class="hicon">📊</span><h1>統計・分析 (発注の癖・繁忙期)</h1></div>', unsafe_allow_html=True)
    if orders_df.empty: st.warning("分析する受注データがありません。")
    else:
        ana_df = orders_df.copy()
        ana_df["年月"] = ana_df["納品予定日"].dt.strftime("%Y-%m")
        ana_df["曜日"] = ana_df["納品予定日"].dt.dayofweek.map({0:"月", 1:"火", 2:"水", 3:"木", 4:"金", 5:"土", 6:"日"})
        ana_df["曜日"] = pd.Categorical(ana_df["曜日"], categories=["月","火","水","木","金","土","日"], ordered=True)
        total_cases  = int(ana_df["ケース数"].sum())
        total_orders = len(ana_df)
        total_custs  = ana_df[ana_df["顧客名"] != "未指定"]["顧客名"].nunique()

        st.markdown(f"""
        <div style="display:flex; gap:12px; flex-wrap:wrap; margin-bottom:18px;">
          <div class="card" style="flex:1; min-width:150px; text-align:center; border-left:5px solid var(--clr-primary);"><div style="font-size:11px; font-weight:bold; color:var(--clr-subtext);">総受注件数</div><div style="font-size:24px; font-weight:900;">{total_orders:,} <span style="font-size:12px;">件</span></div></div>
          <div class="card" style="flex:1; min-width:150px; text-align:center; border-left:5px solid var(--clr-accent);"><div style="font-size:11px; font-weight:bold; color:var(--clr-subtext);">総出荷ケース数</div><div style="font-size:24px; font-weight:900;">{total_cases:,} <span style="font-size:12px;">ケース</span></div></div>
          <div class="card" style="flex:1; min-width:150px; text-align:center; border-left:5px solid var(--clr-success);"><div style="font-size:11px; font-weight:bold; color:var(--clr-subtext);">取引顧客数</div><div style="font-size:24px; font-weight:900;">{total_custs} <span style="font-size:12px;">社</span></div></div>
        </div>
        """, unsafe_allow_html=True)

        tab_trend, tab_habit = st.tabs(["📅 月別トレンド・繁忙期", "🔄 発注の癖・傾向分析"])
        with tab_trend:
            st.markdown('<div class="card"><div class="card-title">📈 月別 出荷ケース数推移</div>', unsafe_allow_html=True)
            monthly = ana_df.groupby("年月").agg(ケース数=("ケース数", "sum"), 件数=("ID", "count")).reset_index()
            fig1 = make_subplots(specs=[[{"secondary_y": True}]])
            fig1.add_trace(go.Bar(x=monthly["年月"], y=monthly["ケース数"], name="出荷ケース数", marker_color="#1a6fc4"), secondary_y=False)
            fig1.add_trace(go.Scatter(x=monthly["年月"], y=monthly["件数"], name="受注件数", mode="lines+markers", line=dict(color="#f0a500", width=3), marker=dict(size=8)), secondary_y=True)
            fig1.update_layout(margin=dict(t=20, b=10, l=10, r=10), legend=dict(orientation="h", y=1.1), height=350, plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig1, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="card"><div class="card-title">📦 カテゴリ別・月別の繁忙期分析</div>', unsafe_allow_html=True)
            cat_monthly = ana_df.groupby(["年月", "大カテゴリ"])["ケース数"].sum().reset_index()
            fig2 = px.bar(cat_monthly, x="年月", y="ケース数", color="大カテゴリ", color_discrete_map=CAT_COLORS)
            fig2.update_layout(barmode="stack", margin=dict(t=20, b=10, l=10, r=10), legend=dict(orientation="h", y=-0.2), height=400, plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig2, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with tab_habit:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown('<div class="card"><div class="card-title">📊 曜日別の出荷ケース数 (発注の癖)</div>', unsafe_allow_html=True)
                dow = ana_df.groupby("曜日")["ケース数"].sum().reset_index()
                fig3 = px.bar(dow, x="曜日", y="ケース数", color="ケース数", color_continuous_scale="Blues")
                fig3.update_layout(margin=dict(t=20, b=10, l=10, r=10), height=350, coloraxis_showscale=False, plot_bgcolor="white", paper_bgcolor="white")
                st.plotly_chart(fig3, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
            with c2:
                st.markdown('<div class="card"><div class="card-title">🏢 主要顧客の月別発注ヒートマップ</div>', unsafe_allow_html=True)
                cust_df_ana = ana_df[ana_df["顧客名"] != "未指定"]
                top_custs = cust_df_ana.groupby("顧客名")["ケース数"].sum().nlargest(10).index
                if len(top_custs) > 0:
                    heat_df = cust_df_ana[cust_df_ana["顧客名"].isin(top_custs)].groupby(["顧客名", "年月"])["ケース数"].sum().reset_index()
                    pivot_heat = heat_df.pivot(index="顧客名", columns="年月", values="ケース数").fillna(0)
                    fig4 = px.imshow(pivot_heat, text_auto=True, aspect="auto", color_continuous_scale="Greens")
                    fig4.update_layout(margin=dict(t=20, b=10, l=10, r=10), height=350)
                    st.plotly_chart(fig4, use_container_width=True)
                else: st.info("顧客名が入力されたデータがありません。")
                st.markdown('</div>', unsafe_allow_html=True)

elif page == "⚙️ マスタ管理":
    st.markdown('<div class="app-header"><span class="hicon">⚙️</span><h1>マスタ管理 (製品・初期在庫・顧客)</h1></div>', unsafe_allow_html=True)
    tab_e, tab_a, tab_d, tab_c = st.tabs(["✏️ 製品 一覧・編集", "➕ 製品 追加", "🗑️ 製品 削除", "🏢 顧客マスタ (ふりがな)"])
    with tab_e:
        st.markdown('<div class="card"><div class="card-title">✏️ 製品マスタ＆初期在庫 編集</div>', unsafe_allow_html=True)
        st.info("💡 **初期在庫数**：現在の実際の在庫数（または棚卸時の数値）を入力してください。これをもとに未来の在庫が計算されます。")
        edited_master = st.data_editor(master_df, use_container_width=True, num_rows="dynamic", column_config={"大カテゴリ": st.column_config.SelectboxColumn("大カテゴリ", options=CATEGORIES, required=True), "製品名": st.column_config.TextColumn("製品名", required=True), "初期在庫数": st.column_config.NumberColumn("初期在庫数 (ケース)", min_value=0, required=True)})
        if st.button("💾 製品マスタを保存", type="primary"): 
            save_master(edited_master)
            st.toast("💾 製品マスタを保存しました", icon="✅")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with tab_a:
        st.markdown('<div class="card"><div class="card-title">➕ 新規製品の追加</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1: new_cat = st.selectbox("大カテゴリ ＊",[""] + CATEGORIES)
        with c2: new_product = st.text_input("製品名 ＊")
        with c3: new_inv = st.number_input("初期在庫数", min_value=0, value=0, step=10)
        if st.button("➕ 追加する", type="primary"):
            if not new_cat or not new_product.strip(): st.error("⚠️ カテゴリと製品名は必須です。")
            else: 
                save_master(pd.concat([master_df.copy(), pd.DataFrame([{"大カテゴリ": new_cat, "製品名": new_product.strip(), "初期在庫数": int(new_inv)}])], ignore_index=True))
                st.toast(f"✅ 追加しました", icon="✅")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with tab_d:
        st.markdown('<div class="card"><div class="card-title">🗑️ 製品の削除</div>', unsafe_allow_html=True)
        del_cat = st.selectbox("カテゴリを選択", [""] + CATEGORIES)
        del_prods = master_df[master_df["大カテゴリ"] == del_cat]["製品名"].tolist() if del_cat else[]
        del_product = st.selectbox("削除する製品", [""] + del_prods, disabled=(not del_cat))
        if del_product and st.button("🗑️ 削除する", type="primary"): 
            temp_master = master_df.copy()
            save_master(temp_master[~((temp_master["大カテゴリ"] == del_cat) & (temp_master["製品名"] == del_product))])
            st.toast(f"🗑️ 削除しました", icon="✅")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with tab_c:
        st.markdown('<div class="card"><div class="card-title">🏢 顧客マスタ (検索・サジェスト用)</div>', unsafe_allow_html=True)
        st.info("💡 **ふりがな** を入力しておくと、受注登録時のドロップダウンで「ひらがな検索」ができるようになります。")
        edited_cust = st.data_editor(cust_df, use_container_width=True, num_rows="dynamic", column_config={"顧客名": st.column_config.TextColumn("顧客名", required=True), "ふりがな": st.column_config.TextColumn("ふりがな")})
        if st.button("💾 顧客マスタを保存", type="primary"): 
            save_customers(edited_cust)
            st.toast("💾 顧客マスタを保存しました", icon="✅")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

elif page == "📖 使い方ガイド":
    st.markdown('<div class="app-header guide-header"><span class="hicon">📖</span><h1>使い方ガイド (マニュアル)</h1></div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="card">
      <div style="font-size:16px; font-weight:700; color:#5a2a8c; margin-bottom:10px;">🏭 丸実屋 受注・在庫管理システムへようこそ</div>
      <p>このシステムは、「これから出荷する予定（受注）」と「これから作る予定（製造）」を入力するだけで、<b>未来の在庫が足りなくなる日（欠品）を自動で教えてくれる</b>便利なアプリです。</p>
    </div>
    <div class="card">
      <div class="card-title">1. 📋 注文が入ったら？（受注登録）</div>
      <p>お客様からの注文（出荷予定）を入力します。ここに入力した分、在庫が減ります。</p>
      <ol><li>左メニューから <b>「📋 受注登録 (出庫)」</b> をクリック。</li><li><b>納品予定日</b> と <b>ケース数</b> を入力。</li><li><b>顧客名</b> を選ぶ。<i>(※ひらがな検索可能。新規は「✏️ 新規・直接入力」を選択)</i></li><li><b>大カテゴリ</b>と<b>製品</b> を選ぶ。<i>(※白黒は自動で「⚪️」「⚫️」マークがつきます)</i></li><li><b>「✅ 受注を登録する」</b> ボタンを押せば完了！</li></ol>
    </div>
    <div class="card">
      <div class="card-title">2. 🏭 こんにゃくを作ったら？（製造登録）</div>
      <p>工場で製造する予定を入力します。ここに入力した分、在庫が増えます。</p>
      <ol><li>左メニューから <b>「🏭 製造登録 (入庫)」</b> をクリック。</li><li><b>製造予定日</b> と <b>製造ケース数</b> を入力。（備考も入力可）</li><li><b>大カテゴリ</b> と <b>製品</b> を選び、<b>「➕ 製造を登録する」</b> を押せば完了！</li></ol>
    </div>
    <div class="card">
      <div class="card-title">3. 🚨 欠品しないか確認するには？（在庫確認）</div>
      <ul><li><b>左のメニューの下をチェック！</b><br>在庫が足りなくなる予定が入ると、ここが <b>「⚠️ 欠品アラート」</b> に変わります。</li>
      <li>左メニューの <b>「📦 スケジュール・在庫確認」</b> を開くと、いつ・何が足りないか表で確認できます。</li>
      <li><b>👉 解決方法：</b>足りない製品がわかったら、「🏭 製造登録」から製造予定を入力してください。警告が消えます！</li></ul>
    </div>
    <div class="card">
      <div class="card-title">4. ✏️ 入力間違いの修正や、マスタの登録（棚卸し）</div>
      <ul><li><b>データの修正：</b>各登録画面の上の<b>「✏️ データ一覧・個別編集」</b>タブから直せます。</li>
      <li><b>初期在庫の入力：</b>「⚙️ マスタ管理」の「✏️ 製品一覧・編集」タブで、現在倉庫にある実際の数を入力し<b>保存</b>してください。</li>
      <li><b>新しい顧客のふりがな：</b>「⚙️ マスタ管理」の「🏢 顧客マスタ」タブから登録できます。</li></ul>
    </div>
    """, unsafe_allow_html=True)
