"""
丸実屋 受注・製造・在庫管理アプリ (クラウド・デザイン完全版)
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
# カスタムCSS (最高のUIデザインを復活)
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

/* サイドバー (紺色 & グリーン) */
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0b2239 0%, #14365d 100%) !important; }
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stSidebar"] div[role="radiogroup"] label { background-color: transparent !important; border: none !important; padding: 12px 16px !important; border-radius: 8px !important; margin-bottom: 4px !important; transition: background 0.2s, color 0.2s; cursor: pointer; }
[data-testid="stSidebar"] div[role="radiogroup"] label:hover { background: rgba(255, 255, 255, 0.1) !important; }
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) { background: #0e8c5a !important; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p { color: #ffffff !important; font-weight: 900 !important; }
[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child { display: none !important; }

/* Pills型カテゴリ選択 */
div.stRadio > div[role="radiogroup"] { display: flex; flex-direction: row; flex-wrap: wrap; gap: 8px; }
div.stRadio > div[role="radiogroup"] > label { background-color: #ffffff !important; border: 1.5px solid #d0d7e3 !important; border-radius: 20px !important; padding: 6px 14px !important; margin: 0 !important; cursor: pointer !important; box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important; transition: all 0.2s ease-in-out !important; }
div.stRadio > div[role="radiogroup"] > label:hover { background-color: #f0f4f8 !important; border-color: #b0bec5 !important; }
div.stRadio > div[role="radiogroup"] > label > div:first-child { display: none !important; }
div.stRadio > div[role="radiogroup"] > label p { font-size: 14px !important; font-weight: 600 !important; margin: 0 !important; color: #374a5e !important; }

/* スケジュール表 */
.sched-wrap { overflow-x: auto; border-radius: 8px; box-shadow: var(--shadow); }
.sched-table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 800px; background: #fff; }
.sched-table th { background: #1a6fc4; color: #fff !important; font-weight: 700; padding: 8px; text-align: center; white-space: nowrap; border: 1px solid #0e4d8a; }
.sched-table td { border: 1px solid #d8e2ef; padding: 6px; vertical-align: top; }
.sched-table td.col-label { background: #f4f7fc; font-weight: 700; text-align: center; white-space: nowrap; width: 80px; }
.sched-table td.col-today { background: #fffbee; border-left: 2px solid #f0a500; border-right: 2px solid #f0a500; }
.sched-entry { border-radius: 6px; padding: 6px 8px; margin-bottom: 6px; font-size: 12px; line-height: 1.4; border-left: 4px solid #1a6fc4; background: #eef4fd; }
.sched-entry.manu-entry { border-left: 4px solid #0e8c5a; background: #e8f5f0; }
.sched-entry .s-prod { color: #374a5e; font-size: 12px; font-weight: 700; margin-bottom: 2px; }
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
        st.error(f"Google API接続エラー: {e}")
        st.stop()

client = init_connection()
try:
    sheet = client.open_by_url(st.secrets["spreadsheet_url"])
except Exception:
    st.error("❌ スプレッドシートが開けません。SecretsのURLが正しいか、シートをサービスアカウントに共有したか確認してください。")
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
        expected_cols = SHEET_COLUMNS.get(sheet_name, [])
        if not data or len(data) == 0:
            return pd.DataFrame(columns=expected_cols)
        headers = data.pop(0)
        df = pd.DataFrame(data, columns=headers)
        if "ケース数" in df.columns: df["ケース数"] = pd.to_numeric(df["ケース数"], errors="coerce").fillna(0).astype(int)
        if "初期在庫数" in df.columns: df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors="coerce").fillna(0).astype(int)
        if "納品予定日" in df.columns: df["納品予定日"] = pd.to_datetime(df["納品予定日"], errors="coerce")
        if "製造予定日" in df.columns: df["製造予定日"] = pd.to_datetime(df["製造予定日"], errors="coerce")
        return df
    except Exception:
        # シートがない場合は作成を試みる
        try:
            sheet.add_worksheet(title=sheet_name, rows=100, cols=10)
        except: pass
        return pd.DataFrame(columns=SHEET_COLUMNS.get(sheet_name, []))

def save_data(sheet_name, df):
    try:
        ws = sheet.worksheet(sheet_name)
        ws.clear()
        df_str = df.copy()
        for col in df_str.select_dtypes(include=['datetime64[ns]']).columns:
            df_str[col] = df_str[col].dt.strftime('%Y-%m-%d')
        df_str = df_str.fillna("")
        ws.update(values=[df_str.columns.values.tolist()] + df_str.values.tolist(), range_name='A1')
        load_data.clear(); simulate_inventory.clear()
    except Exception as e:
        st.error(f"保存エラー: {e}")

# ─────────────────────────────────────────────
# デザイン・機能関連の定数
# ─────────────────────────────────────────────
CATEGORIES = ["平こん", "つきこん", "糸こん・しらたき", "三角こん", "玉こん", "ダイスこん", "短冊", "国産", "ちぎりこん", "大黒屋", "かねこ", "冷凍耐性", "その他"]
CAT_ICONS = {"平こん": "🟫", "つきこん": "🍝", "糸こん・しらたき": "🍜", "三角こん": "🔺", "玉こん": "🟤", "ダイスこん": "🎲", "短冊": "🏷️", "国産": "🇯🇵", "ちぎりこん": "🤲", "大黒屋": "🏮", "かねこ": "🏭", "冷凍耐性": "❄️", "その他": "📦"}
CAT_COLORS = {"平こん": "#8b5a2b", "つきこん": "#0e8c5a", "糸こん・しらたき": "#7c3db8", "三角こん": "#d97706", "玉こん": "#6b4226", "ダイスこん": "#0e7c8c", "短冊": "#1a6fc4", "国産": "#c41a3a", "ちぎりこん": "#d96606", "大黒屋": "#333333", "かねこ": "#2563a8", "冷凍耐性": "#4a90e2", "その他": "#6b7280"}

def format_product_name(p_name):
    if not p_name: return ""
    if "（黒）" in str(p_name) or "黒" in str(p_name): return f"⚫️ {p_name}"
    if "（白）" in str(p_name) or "白" in str(p_name): return f"⚪️ {p_name}"
    return f"📦 {p_name}"

# ─────────────────────────────────────────────
# 在庫シミュレーション
# ─────────────────────────────────────────────
@st.cache_data(ttl=5)
def simulate_inventory(orders_df, manus_df, master_df, forecast_days=60):
    o_tmp = pd.DataFrame(columns=["日付", "製品名", "変動"])
    m_tmp = pd.DataFrame(columns=["日付", "製品名", "変動"])
    if not orders_df.empty:
        o_tmp = orders_df[["納品予定日", "製品名", "ケース数"]].copy().dropna(subset=["製品名"])
        o_tmp.columns = ["日付", "製品名", "変動"]
        o_tmp["変動"] = -o_tmp["変動"]
    if not manus_df.empty:
        m_tmp = manus_df[["製造予定日", "製品名", "ケース数"]].copy().dropna(subset=["製品名"])
        m_tmp.columns = ["日付", "製品名", "変動"]
    
    events = pd.concat([o_tmp, m_tmp])
    if events.empty: return pd.DataFrame(), pd.DataFrame()
    
    events["日付"] = pd.to_datetime(events["日付"]).dt.normalize()
    today = pd.Timestamp.today().normalize()
    date_range = pd.date_range(today, today + timedelta(days=forecast_days))
    inv_records, alerts = [], []
    
    for _, row in master_df.iterrows():
        prod, cat = row["製品名"], row["大カテゴリ"]
        init_inv = int(row.get("初期在庫数", 0))
        prod_events = events[events["製品名"] == prod]
        past_v = prod_events[prod_events["日付"] < today]["変動"].sum()
        current_inv = init_inv + past_v
        future_events = prod_events[prod_events["日付"] >= today].groupby("日付")["変動"].sum()
        
        for d in date_range:
            current_inv += future_events.get(d, 0)
            inv_records.append({"日付": d, "日付_str": d.strftime("%m/%d"), "大カテゴリ": cat, "製品名": prod, "在庫数": current_inv})
            if current_inv < 0:
                alerts.append({"日付": d, "製品名": prod, "不足数": abs(current_inv), "カテゴリ": cat})
    return pd.DataFrame(inv_records), pd.DataFrame(alerts)

# ─────────────────────────────────────────────
# メイン処理開始
# ─────────────────────────────────────────────
if "order_key" not in st.session_state: st.session_state.order_key = 0
if "manu_key" not in st.session_state: st.session_state.manu_key = 0
if "order_success_msg" not in st.session_state: st.session_state.order_success_msg = ""
if "manu_success_msg" not in st.session_state: st.session_state.manu_success_msg = ""

# ロード
orders_df = load_data("orders")
manus_df = load_data("manufactures")
master_df = load_data("master")
cust_df = load_data("customers")

# マスタが空なら初期データ
if master_df.empty:
    master_df = pd.DataFrame([{"大カテゴリ":"平こん", "製品名":"板こん（黒）1kg", "初期在庫数":0}])
    save_data("master", master_df)

inv_df, alerts_df = simulate_inventory(orders_df, manus_df, master_df)
cat_options = ["➖ 未選択"] + [f"{CAT_ICONS.get(c, '📦')} {c}" for c in CATEGORIES]

# ─────────────────────────────────────────────
# UI描画
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""<div style="text-align:center; padding:18px 10px; border-bottom:1px solid rgba(255,255,255,0.12);">
      <span style="font-size:38px; line-height:1;">🏭</span>
      <div style="font-size:17px; font-weight:900; margin-top:8px; color:#fff;">丸実屋</div>
    </div>""", unsafe_allow_html=True)
    page = st.radio("メニュー", ["📋 受注登録 (出庫)", "🏭 製造登録 (入庫)", "📦 スケジュール・在庫確認", "📊 統計・分析", "⚙️ マスタ管理", "📖 使い方ガイド"], label_visibility="collapsed")
    if not alerts_df.empty:
        st.error(f"⚠️ 欠品アラート ({len(alerts_df.groupby('製品名'))}品目)")
    else:
        st.success("✅ 欠品の予定なし")

if page == "📋 受注登録 (出庫)":
    st.markdown("<style>div.stRadio > div[role='radiogroup'] > label:has(input:checked) { background-color: var(--clr-primary) !important; border-color: var(--clr-primary) !important; } div.stRadio > div[role='radiogroup'] > label:has(input:checked) p { color: #ffffff !important; font-weight: 700 !important; }</style>", unsafe_allow_html=True)
    st.markdown('<div class="app-header"><h1>📋 受注登録 (出庫)</h1></div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["➕ 新規受注", "✏️ データ個別修正"])
    with tab1:
        st.markdown('<div class="card"><div class="card-title">📝 受注情報入力</div>', unsafe_allow_html=True)
        okey = st.session_state.order_key
        c1, c2, c3 = st.columns([1.5, 2, 1])
        d_date = c1.date_input("納品予定日", value=date.today() + timedelta(days=1), key=f"o_d_{okey}")
        cust_list = ["✏️ 新規・直接入力"] + sorted(cust_df["顧客名"].unique().tolist()) if not cust_df.empty else ["✏️ 新規・直接入力"]
        sel_c = c2.selectbox("顧客名 (ふりがな検索可)", cust_list, key=f"o_c_{okey}")
        c_name = c2.text_input("📝 新規顧客名", key=f"o_ct_{okey}") if sel_c == "✏️ 新規・直接入力" else sel_c
        cases = c3.number_input("ケース数", min_value=1, value=1, key=f"o_cs_{okey}")
        st.markdown("<hr style='border-top:1px dashed #ddd; margin:15px 0;'>", unsafe_allow_html=True)
        sel_label = st.radio("大カテゴリを選択", cat_options, horizontal=True, key=f"o_cat_{okey}")
        sel_cat = sel_label.split(" ", 1)[1] if " " in sel_label else ""
        prods = master_df[master_df["大カテゴリ"]==sel_cat]["製品名"].tolist() if sel_cat else []
        prod = st.selectbox("製品名", prods, format_func=format_product_name, key=f"o_p_{okey}")
        if st.button("✅ 受注を登録する", type="primary", use_container_width=True):
            if prod and c_name:
                new_row = pd.DataFrame([{"ID": "O-"+str(uuid.uuid4())[:6].upper(), "納品予定日": pd.Timestamp(d_date), "顧客名": c_name, "大カテゴリ": sel_cat, "製品名": prod, "ケース数": int(cases), "登録日時": pd.Timestamp.now()}])
                save_data("orders", pd.concat([orders_df, new_row], ignore_index=True))
                st.session_state.order_success_msg = f"✅ 【{c_name}】 {prod} × {cases}ケース を登録しました。"
                st.session_state.order_key += 1; st.rerun()
        if st.session_state.order_success_msg: st.success(st.session_state.order_success_msg); st.session_state.order_success_msg = ""
        st.markdown('</div>', unsafe_allow_html=True)

if page == "🏭 製造登録 (入庫)":
    st.markdown("<style>div.stRadio > div[role='radiogroup'] > label:has(input:checked) { background-color: var(--clr-manu) !important; border-color: var(--clr-manu) !important; } div.stRadio > div[role='radiogroup'] > label:has(input:checked) p { color: #ffffff !important; font-weight: 700 !important; }</style>", unsafe_allow_html=True)
    st.markdown('<div class="app-header manu-header"><h1>🏭 製造登録 (入庫)</h1></div>', unsafe_allow_html=True)
    mkey = st.session_state.manu_key
    st.markdown('<div class="card"><div class="card-title" style="color:var(--clr-manu);">📝 製造情報入力</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1.5, 1.2, 2.3])
    m_date = c1.date_input("製造予定日", value=date.today(), key=f"m_d_{mkey}")
    m_cases = c2.number_input("製造ケース数", min_value=1, value=50, key=f"m_cs_{mkey}")
    m_note = c3.text_input("備考 (ロット等)", key=f"m_n_{mkey}")
    sel_label = st.radio("大カテゴリを選択", cat_options, horizontal=True, key=f"m_cat_{mkey}")
    sel_cat = sel_label.split(" ", 1)[1] if " " in sel_label else ""
    prods = master_df[master_df["大カテゴリ"]==sel_cat]["製品名"].tolist() if sel_cat else []
    prod = st.selectbox("製品名", prods, format_func=format_product_name, key=f"m_p_{mkey}")
    if st.button("➕ 製造を登録する", type="primary", use_container_width=True):
        if prod:
            new_row = pd.DataFrame([{"ID": "M-"+str(uuid.uuid4())[:6].upper(), "製造予定日": pd.Timestamp(m_date), "備考": m_note, "大カテゴリ": sel_cat, "製品名": prod, "ケース数": int(m_cases), "登録日時": pd.Timestamp.now()}])
            save_data("manufactures", pd.concat([manus_df, new_row], ignore_index=True))
            st.session_state.manu_success_msg = f"✅ 【製造】 {prod} × {m_cases}ケース を登録しました。"
            st.session_state.manu_key += 1; st.rerun()
    if st.session_state.manu_success_msg: st.success(st.session_state.manu_success_msg); st.session_state.manu_success_msg = ""
    st.markdown('</div>', unsafe_allow_html=True)

if page == "📦 スケジュール・在庫確認":
    st.markdown('<div class="app-header"><h1>📦 在庫・スケジュール確認</h1></div>', unsafe_allow_html=True)
    t1, t2, t3 = st.tabs(["📊 在庫推移", "🚨 欠品アラート", "📅 直近1週間の入出庫"])
    with t1:
        st.markdown('<div class="card"><div class="card-title">📅 向こう2週間の日別在庫推移</div>', unsafe_allow_html=True)
        if not inv_df.empty:
            pv = inv_df[inv_df["日付"] <= pd.Timestamp.today()+timedelta(days=14)].pivot_table(index=["大カテゴリ", "製品名"], columns="日付_str", values="在庫数", aggfunc='last').reset_index()
            st.dataframe(pv.style.map(lambda x: 'color:red; font-weight:bold;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with t3:
        # プログレスバーUIを復活
        today = pd.Timestamp.today().normalize(); day_list = [today + timedelta(days=i) for i in range(7)]
        max_v = max(300, orders_df["ケース数"].max() if not orders_df.empty else 0, manus_df["ケース数"].max() if not manus_df.empty else 0)
        def get_bar(val, color, sign):
            pct = min(100, int((val/max_v)*100)); return f'<div style="position:relative; background:#eee; border-radius:4px; height:18px; margin-top:4px;"><div style="width:{pct}%; background:{color}; height:100%; border-radius:4px; opacity:0.8;"></div><div style="position:absolute; top:0; right:4px; font-size:10px; font-weight:900;">{sign}{val}</div></div>'
        rows = ""
        for d in day_list:
            cls = "col-today" if d == today else ""
            m_cells = "".join([f'<div class="sched-entry manu-entry"><div class="s-prod">{format_product_name(r["製品名"])}</div>{get_bar(r["ケース数"], "#0e8c5a", "+")}</div>' for _,r in manus_df[manus_df["製造予定日"]==d].iterrows()])
            o_cells = "".join([f'<div class="sched-entry" style="border-left-color:{CAT_COLORS.get(r["大カテゴリ"],"#1a6fc4")};"><div class="s-prod">{format_product_name(r["製品名"])}</div>{get_bar(r["ケース数"], CAT_COLORS.get(r["大カテゴリ"],"#1a6fc4"), "-")}</div>' for _,r in orders_df[orders_df["納品予定日"]==d].iterrows()])
            rows += f'<tr><td class="col-label {cls}">{d.strftime("%m/%d")}({WEEKDAYS_JA[d.dayofweek]})</td><td class="{cls}">{m_cells if m_cells else "—"}</td><td class="{cls}">{o_cells if o_cells else "—"}</td></tr>'
        st.markdown(f'<div class="sched-wrap"><table class="sched-table"><thead><tr><th>日付</th><th>🏭 製造(入庫)</th><th>📋 出荷(出庫)</th></tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)

if page == "📊 統計・分析":
    st.markdown('<div class="app-header"><h1>📊 月別出荷・傾向分析</h1></div>', unsafe_allow_html=True)
    if not orders_df.empty:
        orders_df["年月"] = orders_df["納品予定日"].dt.strftime("%Y-%m")
        st.plotly_chart(px.bar(orders_df.groupby(["年月","大カテゴリ"])["ケース数"].sum().reset_index(), x="年月", y="ケース数", color="大カテゴリ", color_discrete_map=CAT_COLORS, barmode="stack", title="月別出荷トレンド"), use_container_width=True)

if page == "⚙️ マスタ管理":
    st.markdown('<div class="app-header"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["📦 製品マスタ・初期在庫", "🏢 顧客マスタ"])
    with t1:
        ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 製品マスタを保存"): save_data("master", ed_m); st.rerun()
    with t2:
        ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 顧客マスタを保存"): save_data("customers", ed_c); st.rerun()

if page == "📖 使い方ガイド":
    st.markdown('<div class="app-header guide-header"><h1>📖 使い方ガイド</h1></div>', unsafe_allow_html=True)
    st.info("左メニューから操作を選んでください。受注登録で在庫が減り、製造登録で在庫が増えます。欠品アラートが出たら製造予定を追加しましょう。")
