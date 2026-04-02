import os
# テーマ強制設定（視認性固定・文字消失防止）
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
import numpy as np

# ─────────────────────────────────────────────
# 0. 共通の絶対安全な数値変換関数（Seriesエラー完全防止）
# ─────────────────────────────────────────────
def to_int(v):
    try:
        if isinstance(v, pd.Series):
            v = v.sum() # Seriesなら合計を取る（重複エラー防止）
        if pd.isna(v):
            return 0
        return int(float(v))
    except:
        return 0

# ─────────────────────────────────────────────
# 1. ページ基本設定
# ─────────────────────────────────────────────
st.set_page_config(page_title="丸実屋 受注・在庫管理", page_icon="🏭", layout="wide", initial_sidebar_state="expanded")

# ─────────────────────────────────────────────
# 2. UIデザインCSS (文字消失防止・特大ボタン)
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&display=swap');
    html, body, [data-testid="stAppViewContainer"] { font-family: 'Noto Sans JP', sans-serif !important; font-size: 16px !important; }
    p, span, label, div { color: #0F172A !important; }
    
    [data-testid="stSidebar"] { background-color: #F8FAFC !important; border-right: 1px solid #E2E8F0; }
    [data-testid="stSidebar"] .stButton > button { height: 45px !important; font-size: 15px !important; border-radius: 8px !important; font-weight: 600 !important; }

    .block-container { padding-top: 1rem !important; }
    .slim-header { background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%); padding: 12px 24px; border-radius: 10px; color: white !important; margin-bottom: 12px; }
    .slim-header h1 { color: white !important; margin: 0 !important; font-size: 20px !important; font-weight: 800 !important; }
    .header-manu { background: linear-gradient(135deg, #064E3B 0%, #10B981 100%); }

    /* ★ カテゴリ特大ボタン ★ */
    [data-testid="stPills"] button { 
        padding: 16px 32px !important; font-size: 20px !important; font-weight: 900 !important; 
        border-radius: 12px !important; border: 2px solid #CBD5E1 !important; margin: 6px !important; 
    }
    [data-testid="stPills"] button[aria-selected="true"] { 
        background-color: #2563EB !important; color: #FFFFFF !important; 
        box-shadow: 0 6px 15px rgba(37, 99, 235, 0.4) !important; 
    }

    .sched-table { width: 100%; border-collapse: collapse; background: white; font-size: 15px; border-radius: 10px; overflow: hidden; }
    .sched-table th { background: #F8FAFC; padding: 10px; border-bottom: 2px solid #E2E8F0; }
    .sched-table td { padding: 10px; border-bottom: 1px solid #F1F5F9; vertical-align: top; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. ログイン認証
# ─────────────────────────────────────────────
def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.markdown("<div style='text-align:center; margin-top:50px;'><span style='font-size:80px;'>🏭</span><h2 style='color:#1E3A8A;'>丸実屋システム ログイン</h2></div>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            pwd = st.text_input("パスワードを入力", type="password")
            if st.button("ログイン", use_container_width=True, type="primary"):
                if pwd == st.secrets["app_password"]: st.session_state["password_correct"] = True; st.rerun()
                else: st.error("❌ 違います")
        st.stop()
check_password()

# ─────────────────────────────────────────────
# 4. Googleスプレッドシート連携 ＆ 最強の同期ロジック
# ─────────────────────────────────────────────
@st.cache_resource
def get_client():
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

client = get_client()
sheet = client.open_by_url(st.secrets["spreadsheet_url"])

def load_data_from_cloud(name):
    try:
        ws = sheet.worksheet(name)
        data = ws.get_all_values()
        cols = {
            "orders": ["ID","納品予定日","顧客名","大カテゴリ","製品名","ケース数","備考","登録日時"],
            "manufactures": ["ID","製造予定日","備考","大カテゴリ","製品名","ケース数","登録日時"],
            "master": ["大カテゴリ","製品名","初期在庫数","使用資材名","資材使用数"],
            "customers": ["顧客名","ふりがな"],
            "packaging_master": ["資材名","初期在庫","適正在庫"],
            "packaging_logs": ["ID","登録日","資材名","数量","理由","備考","登録日時"]
        }[name]
        
        if len(data) <= 1: return pd.DataFrame(columns=cols)
        df = pd.DataFrame(data[1:], columns=data[0])
        
        # 【重要】列名の重複排除（Seriesエラー防止の要）
        df = df.loc[:, ~df.columns.duplicated()]
        
        for c in cols:
            if c not in df.columns: df[c] = ""
        
        num_cols = ["ケース数", "初期在庫数", "資材使用数", "初期在庫", "適正在庫", "数量"]
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).apply(to_int)
                
        date_cols = ["納品予定日", "製造予定日", "登録日", "登録日時"]
        for c in date_cols:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], errors='coerce')
        return df[cols]
    except Exception as e: 
        return pd.DataFrame(columns={"orders": ["ID","納品予定日","顧客名","大カテゴリ","製品名","ケース数","備考","登録日時"],"manufactures": ["ID","製造予定日","備考","大カテゴリ","製品名","ケース数","登録日時"],"master": ["大カテゴリ","製品名","初期在庫数","使用資材名","資材使用数"],"customers": ["顧客名","ふりがな"],"packaging_master": ["資材名","初期在庫","適正在庫"],"packaging_logs": ["ID","登録日","資材名","数量","理由","備考","登録日時"]}[name])

def save_and_sync(name, df):
    try: ws = sheet.worksheet(name)
    except: ws = sheet.add_worksheet(title=name, rows="1000", cols="20")
    ws.clear()
    df_save = df.copy()
    for col in df_save.columns:
        if pd.api.types.is_datetime64_any_dtype(df_save[col]):
            df_save[col] = df_save[col].dt.strftime('%Y-%m-%d %H:%M:%S').replace('NaT', '')
        elif pd.api.types.is_numeric_dtype(df_save[col]):
            df_save[col] = df_save[col].fillna(0).apply(to_int).astype(str)
    df_save = df_save.fillna("").astype(str).replace(["nan", "None", "NaT"], "")
    ws.update(values=[df_save.columns.values.tolist()] + df_save.values.tolist(), range_name='A1')
    st.cache_data.clear()
    st.session_state[f"{name}_df"] = load_data_from_cloud(name)

def append_and_sync(name, new_row_df):
    try: ws = sheet.worksheet(name)
    except: ws = sheet.add_worksheet(title=name, rows="1000", cols="20"); ws.append_row(new_row_df.columns.tolist())
    row_copy = new_row_df.copy()
    for col in row_copy.columns:
        if pd.api.types.is_datetime64_any_dtype(row_copy[col]):
            row_copy[col] = row_copy[col].dt.strftime('%Y-%m-%d %H:%M:%S').replace('NaT', '')
    row_to_send = row_copy.fillna("").astype(str).replace(["nan", "None", "NaT"], "").values[0].tolist()
    ws.append_row(row_to_send)
    st.cache_data.clear()
    st.session_state[f"{name}_df"] = pd.concat([st.session_state[f"{name}_df"], new_row_df], ignore_index=True)

# ─────────────────────────────────────────────
# 5. セッション初期化
# ─────────────────────────────────────────────
for sheet_name in ["orders", "manufactures", "master", "customers", "packaging_master", "packaging_logs"]:
    if f"{sheet_name}_df" not in st.session_state:
        st.session_state[f"{sheet_name}_df"] = load_data_from_cloud(sheet_name)

if "current_page" not in st.session_state: st.session_state.current_page = "📋 受注登録"
if "success_msg" not in st.session_state: st.session_state.success_msg = None

orders_df = st.session_state.orders_df
manus_df = st.session_state.manufactures_df
master_df = st.session_state.master_df
cust_df = st.session_state.customers_df
pack_mst_df = st.session_state.packaging_master_df
pack_log_df = st.session_state.packaging_logs_df

CATEGORIES = ["🍝 つきこん", "🟫 平こん", "🍜 糸こん・しらたき", "🔺 三角こん", "🟤 玉こん", "🎲 ダイスこん", "🏷️ 短冊", "🇯🇵 国産", "🤲 ちぎりこん", "🏮 大黒屋", "🏭 かねこ", "❄️ 冷凍耐性", "📦 その他"]

def format_name(name):
    if not name: return ""
    n = str(name)
    return f"⚫️ {n}" if "黒" in n else f"⚪️ {n}" if "白" in n else f"📦 {n}"

# ─────────────────────────────────────────────
# ★ 共通在庫計算エンジン（製品 ＆ 資材連動）絶対安全版
# ─────────────────────────────────────────────
today = pd.Timestamp.today().normalize()
dates = pd.date_range(today, today + timedelta(days=60))

# --- 1. 製品在庫計算 ---
current_stocks = {}
future_stocks = {}

# 重複を排除してインデックスエラーを防止
master_df_unique = master_df.drop_duplicates(subset=["製品名"]) if not master_df.empty else pd.DataFrame()

if not master_df_unique.empty:
    o_ev = orders_df[["納品予定日", "製品名", "ケース数"]].copy() if not orders_df.empty else pd.DataFrame(columns=["納品予定日", "製品名", "ケース数"])
    if not o_ev.empty:
        o_ev = o_ev.rename(columns={"納品予定日":"日付", "ケース数":"qty"})
        o_ev["qty"] = -pd.to_numeric(o_ev["qty"], errors='coerce').fillna(0)
    
    m_ev = manus_df[["製造予定日", "製品名", "ケース数"]].copy() if not manus_df.empty else pd.DataFrame(columns=["製造予定日", "製品名", "ケース数"])
    if not m_ev.empty:
        m_ev = m_ev.rename(columns={"製造予定日":"日付", "ケース数":"qty"})
        m_ev["qty"] = pd.to_numeric(m_ev["qty"], errors='coerce').fillna(0)
    
    all_ev = pd.concat([o_ev, m_ev]).dropna(subset=["製品名", "日付"])
    all_ev["qty"] = all_ev["qty"].apply(to_int)
    
    past_ev = all_ev[all_ev["日付"] < today].groupby("製品名")["qty"].sum()
    future_ev = all_ev[all_ev["日付"] >= today]
    
    pivot_ev = future_ev.pivot_table(index="製品名", columns="日付", values="qty", aggfunc="sum") if not future_ev.empty else pd.DataFrame()
    
    for _, r in master_df_unique.iterrows():
        p = r["製品名"]
        p_past = to_int(past_ev.get(p, 0))
        curr_stock = to_int(r.get("初期在庫数", 0)) + p_past
        current_stocks[p] = curr_stock
        
        if p in pivot_ev.index:
            p_future_row = pivot_ev.loc[p]
            if isinstance(p_future_row, pd.DataFrame):
                p_future_row = p_future_row.sum(axis=0)
        else:
            p_future_row = pd.Series(0, index=dates)
            
        p_future_row = p_future_row.reindex(dates, fill_value=0)
        p_future_cumsum = p_future_row.fillna(0).cumsum()
        
        future_stocks[p] = {}
        for d in dates:
            future_stocks[p][d] = curr_stock + to_int(p_future_cumsum.get(d, 0))

# --- 2. 資材（段ボール）在庫計算 ---
pack_stocks = {}
pack_mst_unique = pack_mst_df.drop_duplicates(subset=["資材名"]) if not pack_mst_df.empty else pd.DataFrame()

if not pack_mst_unique.empty:
    for _, r in pack_mst_unique.iterrows():
        pack_stocks[r["資材名"]] = {
            "現在庫": to_int(r.get("初期在庫", 0)),
            "適正在庫": to_int(r.get("適正在庫", 0))
        }

if not pack_log_df.empty:
    p_logs = pack_log_df.copy()
    p_logs["数量"] = pd.to_numeric(p_logs["数量"], errors='coerce').fillna(0).apply(to_int)
    log_sum = p_logs.groupby("資材名")["数量"].sum()
    for p_name, val in log_sum.items():
        if p_name in pack_stocks:
            pack_stocks[p_name]["現在庫"] -= to_int(val) # 出庫はプラス、入庫はマイナス入力されるため引く

if not orders_df.empty and not master_df_unique.empty:
    master_pack_info = master_df_unique.set_index("製品名")[["使用資材名", "資材使用数"]].to_dict('index')
    for _, r in orders_df.iterrows():
        prod = r["製品名"]
        qty = to_int(r.get("ケース数", 0))
        if prod in master_pack_info:
            pack_name = master_pack_info[prod].get("使用資材名", "")
            pack_usage = to_int(master_pack_info[prod].get("資材使用数", 0))
            if pack_name and pack_usage > 0 and pack_name in pack_stocks:
                pack_stocks[pack_name]["現在庫"] -= (qty * pack_usage)

# ─────────────────────────────────────────────
# 6. サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<p style='font-size:20px; font-weight:900; color:#1E3A8A; margin-bottom:20px;'>🏭 丸実屋システム</p>", unsafe_allow_html=True)
    st.write("---")
    menu_items = ["📋 受注登録", "🏭 製造登録", "📦 資材・段ボール管理", "📑 登録一覧・編集", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"]
    for item in menu_items:
        if st.button(item, key=f"menu_{item}", use_container_width=True, type="primary" if st.session_state.current_page == item else "secondary"):
            st.session_state.current_page = item; st.rerun()

page = st.session_state.current_page

# ─────────────────────────────────────────────
# 7. 各画面描画
# ─────────────────────────────────────────────

# --- 受注登録 ---
if page == "📋 受注登録":
    st.markdown('<div class="slim-header"><h1>📋 受注（出荷予定）登録</h1></div>', unsafe_allow_html=True)
    with st.container():
        c1, c2, c3 = st.columns([1, 2, 1])
        o_date = c1.date_input("📅 納品日", value=date.today() + timedelta(days=1))
        cust_list = sorted(cust_df[cust_df["顧客名"].str.strip() != ""]["顧客名"].unique().tolist()) if not cust_df.empty else []
        c_name = c2.selectbox("🏢 顧客名", options=cust_list, index=None, placeholder="検索...")
        
        # 負数入力の許可（min_valueなし）
        qty = c3.number_input("📦 ケース数", value=None, placeholder="数字(-で復帰)...") 
        
        cat_full = st.pills("カテゴリ", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
        cat = cat_full.split(" ", 1)[1] if cat_full else CATEGORIES[0].split(" ", 1)[1]
        
        sc1, sc2 = st.columns([1.5, 2.5])
        search_p = sc1.text_input("🔍 製品検索", placeholder="名称の一部を入力...")
        prods = [p for p in master_df_unique["製品名"].tolist() if search_p in p] if search_p else (master_df_unique[master_df_unique["大カテゴリ"] == cat]["製品名"].tolist() if not master_df_unique.empty else [])
        prod = sc2.selectbox("確定製品", options=prods, index=None, placeholder="選択してください", format_func=format_name)
        rem = sc2.text_input("📝 備考")
        
        col_chk1, col_chk2 = sc2.columns(2)
        is_substitute = col_chk1.checkbox("🔄 代替品として送付")
        is_irregular = col_chk2.checkbox("⚠️ イレギュラー(水漏れ等)")
        
        st.write("---")

        if prod and qty is not None:
            cur_stock = current_stocks.get(prod, 0)
            if qty > 0 and cur_stock < qty:
                st.warning(f"⚠️ 在庫が不足します（現在庫: **{cur_stock}** cs / 不足: **{qty - cur_stock}** cs）", icon="🚨")

        submit_btn = st.button("✅ 受注を登録する", type="primary", use_container_width=True)
        msg_slot = st.empty()

        if submit_btn:
            if not prod or qty is None: 
                msg_slot.error("⚠️ 【製品・ケース数】は必須です。")
            else:
                prefix = ""
                if is_substitute: prefix += "【代替品】"
                if is_irregular:
                    if qty < 0: prefix += "【イレギュラー・在庫復帰】"
                    else: prefix += "【イレギュラー】"
                elif qty < 0:
                    prefix += "【在庫復帰】"
                
                final_rem = f"{prefix} {rem}".strip()
                
                new_row = pd.DataFrame([{
                    "ID": str(uuid.uuid4())[:6].upper(), 
                    "納品予定日": pd.to_datetime(o_date), 
                    "顧客名": c_name if c_name else "未指定", 
                    "大カテゴリ": cat, 
                    "製品名": prod, 
                    "ケース数": to_int(qty), 
                    "備考": final_rem, 
                    "登録日時": datetime.now()
                }])
                append_and_sync("orders", new_row)
                st.session_state.success_msg = f"✨ 登録完了：{prod}"
                st.rerun()

        if st.session_state.success_msg:
            msg_slot.success(st.session_state.success_msg)
            st.session_state.success_msg = None

    # 直近5件のかんたん修正
    st.markdown('<h2 style="font-size:18px; margin-top:20px;">✏️ かんたん修正（直近5件）</h2>', unsafe_allow_html=True)
    if not orders_df.empty:
        recent = orders_df.sort_values("登録日時", ascending=False).head(5).copy()
        recent["納品予定日"] = recent["納品予定日"].dt.date
        edited = st.data_editor(recent, use_container_width=True, hide_index=True, column_config={
            "納品予定日": st.column_config.DateColumn("納品日", format="YYYY-MM-DD"), 
            "ケース数": st.column_config.NumberColumn("ケース数"),
            "登録日時": None
        }, key="edit_o")
        if st.button("💾 修正保存", key="btn_edit_o"):
            others = orders_df[~orders_df["ID"].isin(recent["ID"])]
            save_and_sync("orders", pd.concat([others, edited], ignore_index=True))
            st.rerun()

# --- 🏭 製造登録 ---
elif page == "🏭 製造登録":
    st.markdown('<div class="slim-header header-manu"><h1>🏭 製造データ登録</h1></div>', unsafe_allow_html=True)
    with st.container():
        col1, col2 = st.columns([1, 1])
        m_date = col1.date_input("📅 製造日", value=date.today())
        # マイナス入力も可能に
        m_qty = col2.number_input("📦 製造ケース数", value=None, placeholder="数字を入力...")
        cat_full_m = st.pills("カテゴリ製造", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
        cat_m = cat_full_m.split(" ", 1)[1] if cat_full_m else CATEGORIES[0].split(" ", 1)[1]
        sc1_m, sc2_m = st.columns([1.5, 2.5])
        search_p_m = sc1_m.text_input("🔍 製品名検索", placeholder="検索...", key="sm")
        prods_m = [p for p in master_df_unique["製品名"].tolist() if search_p_m in p] if search_p_m else (master_df_unique[master_df_unique["大カテゴリ"] == cat_m]["製品名"].tolist() if not master_df_unique.empty else [])
        prod_m = sc2_m.selectbox("確定製品", options=prods_m, index=None, format_func=format_name, key="selm")
        
        m_submit_btn = st.button("➕ 製造を記録する", type="primary", use_container_width=True)
        m_msg_slot = st.empty()

        if m_submit_btn:
            if not prod_m or m_qty is None: 
                m_msg_slot.error("⚠️ 【製品・数量】は必須です。")
            else:
                new_row = pd.DataFrame([{"ID": str(uuid.uuid4())[:6].upper(), "製造予定日": pd.to_datetime(m_date), "備考": "", "大カテゴリ": cat_m, "製品名": prod_m, "ケース数": to_int(m_qty), "登録日時": datetime.now()}])
                append_and_sync("manufactures", new_row)
                st.session_state.success_msg = f"✨ 登録完了：{prod_m}"
                st.rerun()
        
        if st.session_state.success_msg:
            m_msg_slot.success(st.session_state.success_msg)
            st.session_state.success_msg = None

    st.markdown('<h2 style="font-size:18px; margin-top:20px;">✏️ かんたん修正（直近5件）</h2>', unsafe_allow_html=True)
    if not manus_df.empty:
        recent_m = manus_df.sort_values("登録日時", ascending=False).head(5).copy()
        recent_m["製造予定日"] = recent_m["製造予定日"].dt.date
        edited_m = st.data_editor(recent_m, use_container_width=True, hide_index=True, column_config={
            "製造予定日": st.column_config.DateColumn("製造日", format="YYYY-MM-DD"), 
            "ケース数": st.column_config.NumberColumn("ケース数"),
            "登録日時": None
        }, key="edit_m")
        if st.button("💾 修正を保存", key="smb"):
            others_m = manus_df[~manus_df["ID"].isin(recent_m["ID"])]
            save_and_sync("manufactures", pd.concat([others_m, edited_m], ignore_index=True))
            st.rerun()

# --- 📦 資材・段ボール管理 ---
elif page == "📦 資材・段ボール管理":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #B45309 0%, #D97706 100%);"><h1>📦 資材・段ボール管理</h1></div>', unsafe_allow_html=True)
    
    st.markdown("### 📊 資材の現在庫状況")
    if pack_mst_df.empty:
        st.info("⚙️ マスタ管理から資材を登録してください。")
    else:
        pack_list = []
        for p_name, data in pack_stocks.items():
            pack_list.append({"資材名": p_name, "現在庫": data["現在庫"], "適正在庫": data["適正在庫"]})
        
        df_pack = pd.DataFrame(pack_list)
        # オレンジ色ハイライト（適正在庫未満）
        def highlight_pack(row):
            if row["現在庫"] < row["適正在庫"]: return ['background-color: #FFEDD5; color: #C2410C; font-weight: bold;'] * len(row)
            return [''] * len(row)
            
        st.dataframe(df_pack.style.apply(highlight_pack, axis=1), use_container_width=True, hide_index=True)
    
    st.write("---")
    st.markdown("### 📝 資材の単体登録・調整 (一括入庫)")
    st.info("💡 納品された段ボールの**入庫**は、数量を「**マイナス（例：-500）**」で入力してください。（在庫が増えます）\n\n製品に紐付かないサンプル出荷や破損廃棄（出庫）は「プラス」で入力します。")
    
    with st.container():
        p_date = st.date_input("📅 処理日", value=date.today())
        pack_names = pack_mst_unique["資材名"].tolist() if not pack_mst_unique.empty else []
        
        col_p1, col_p2, col_p3 = st.columns([2, 1, 1.5])
        sel_pack = col_p1.selectbox("📦 対象資材", options=pack_names, index=None, placeholder="選択...")
        p_qty = col_p2.number_input("数量 (-で入庫)", value=None)
        p_reason = col_p3.selectbox("理由", options=["入庫（購入）", "サンプル出荷", "破損・廃棄", "棚卸調整", "その他"])
        p_rem = st.text_input("📝 備考 (任意)")
        
        if st.button("➕ 資材ログを登録", type="primary"):
            if not sel_pack or p_qty is None:
                st.error("⚠️ 資材名と数量は必須です。")
            else:
                new_pack = pd.DataFrame([{
                    "ID": str(uuid.uuid4())[:6].upper(), "登録日": pd.to_datetime(p_date),
                    "資材名": sel_pack, "数量": to_int(p_qty), "理由": p_reason, "備考": p_rem, "登録日時": datetime.now()
                }])
                append_and_sync("packaging_logs", new_pack)
                st.success(f"✨ 登録完了：{sel_pack}")
                st.rerun()

    st.markdown('<h2 style="font-size:18px; margin-top:20px;">✏️ 直近の資材ログ（かんたん修正）</h2>', unsafe_allow_html=True)
    if not pack_log_df.empty:
        recent_p = pack_log_df.sort_values("登録日時", ascending=False).head(5).copy()
        recent_p["登録日"] = recent_p["登録日"].dt.date
        edited_p = st.data_editor(recent_p, use_container_width=True, hide_index=True, column_config={
            "登録日": st.column_config.DateColumn("登録日", format="YYYY-MM-DD"), 
            "数量": st.column_config.NumberColumn("数量"),
            "登録日時": None
        }, key="edit_p")
        if st.button("💾 資材ログを修正保存", key="btn_edit_p"):
            others_p = pack_log_df[~pack_log_df["ID"].isin(recent_p["ID"])]
            save_and_sync("packaging_logs", pd.concat([others_p, edited_p], ignore_index=True))
            st.rerun()


# --- 📑 登録一覧・編集 ---
elif page == "📑 登録一覧・編集":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #0F766E 0%, #14B8A6 100%);"><h1>📑 登録一覧・データ編集・出力</h1></div>', unsafe_allow_html=True)
    
    t_list1, t_list2 = st.tabs(["📋 受注・出荷データ", "📦 資材利用ログ"])
    
    with t_list1:
        if orders_df.empty: st.info("登録データがありません。")
        else:
            edit_df = orders_df.sort_values("登録日時", ascending=False).copy()
            edit_df["納品予定日"] = edit_df["納品予定日"].dt.date
            cols = ["ID", "登録日時", "大カテゴリ", "顧客名", "納品予定日", "製品名", "ケース数", "備考"]
            edit_df = edit_df[[c for c in cols if c in edit_df.columns]]
            
            def get_stock_status(row):
                try:
                    d = pd.Timestamp(row["納品予定日"]).normalize()
                    p = row["製品名"]
                    qty = to_int(row.get("ケース数", 0))
                    
                    if d >= today and p in future_stocks and d in future_stocks[p]:
                        stock = future_stocks[p][d]
                    else:
                        stock = current_stocks.get(p, 0)
                    
                    if qty < 0: return f"⤴️ 復帰 (+{-qty})"
                    elif stock < 0: return f"在庫不足 ({stock})"
                    else: return f"OK (+{stock})"
                except: return "不明"

            edit_df.insert(7, "在庫状況", edit_df.apply(get_stock_status, axis=1))

            def highlight_row(row):
                color_style = ''
                is_return = to_int(row.get("ケース数", 0)) < 0
                is_irregular = "【イレギュラー】" in str(row.get("備考", ""))
                is_shortage = "不足" in str(row.get("在庫状況", ""))
                
                if is_return: color_style = 'background-color: #DBEAFE; color: #1E3A8A; font-weight: bold;'
                elif is_shortage and is_irregular: color_style = 'background-color: #FEF08A; color: #DC2626; font-weight: bold;'
                elif is_shortage: color_style = 'background-color: #FEE2E2; color: #DC2626; font-weight: bold;'
                elif is_irregular: color_style = 'background-color: #FEF08A; color: #854D0E; font-weight: bold;'
                return [color_style] * len(row)

            col_btn1, col_btn2 = st.columns([3, 1])
            with col_btn2:
                csv = edit_df.to_csv(index=False, encoding="utf-8-sig")
                st.download_button("📥 Excel/CSV ダウンロード", data=csv, file_name=f"受注一覧_{date.today()}.csv", use_container_width=True)

            st.markdown("""<div style="font-size:14px; margin-bottom:10px;">
                <b>🎨 色の見方：</b> <span style="background-color:#FEE2E2; color:#DC2626; padding:2px 6px;">在庫不足（赤字）</span> / 
                <span style="background-color:#FEF08A; color:#854D0E; padding:2px 6px;">イレギュラー対応（黄色）</span> / 
                <span style="background-color:#DBEAFE; color:#1E3A8A; padding:2px 6px;">⤴️ 在庫復帰（青色）</span>
            </div>""", unsafe_allow_html=True)
            
            edited = st.data_editor(
                edit_df.style.apply(highlight_row, axis=1),
                use_container_width=True, hide_index=True, height=600,
                column_config={
                    "ID": None, "登録日時": None, "大カテゴリ": None,
                    "納品予定日": st.column_config.DateColumn("納品日", format="YYYY-MM-DD", required=True),
                    "ケース数": st.column_config.NumberColumn("ケース数", required=True), 
                    "在庫状況": st.column_config.TextColumn("在庫状況 (出庫後)", disabled=True)
                },
                key="edit_all_orders"
            )
            
            if st.button("💾 受注データを保存", type="primary", use_container_width=True):
                save_df = edited.drop(columns=["在庫状況"], errors='ignore')
                save_and_sync("orders", save_df)
                st.success("✅ 受注データを更新し、在庫の再計算を行いました！")
                st.rerun()

    with t_list2:
        if pack_log_df.empty: st.info("資材ログがありません。")
        else:
            e_pack = pack_log_df.sort_values("登録日時", ascending=False).copy()
            e_pack["登録日"] = e_pack["登録日"].dt.date
            edited_pl = st.data_editor(e_pack, use_container_width=True, hide_index=True, column_config={"ID":None, "登録日時":None, "登録日":st.column_config.DateColumn("登録日", format="YYYY-MM-DD")}, key="edit_plogs")
            if st.button("💾 資材ログを一括保存", type="primary", use_container_width=True):
                save_and_sync("packaging_logs", edited_pl)
                st.success("✅ 資材ログを更新しました！")
                st.rerun()

# --- 📦 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="slim-header"><h1>📦 在庫予測 ＆ 週間カレンダー</h1></div>', unsafe_allow_html=True)
    t1, t2, t3, t4 = st.tabs(["📉 1ヶ月在庫予測", "📅 週間カレンダー", "🔍 製品別詳細ビュー", "👤 顧客別スケジュール"])
    
    with t1:
        if master_df_unique.empty: st.info("製品マスタが空です。")
        else:
            inv_list = []
            show_dates = pd.date_range(today, today + timedelta(days=30))
            for _, r in master_df_unique.iterrows():
                p = r["製品名"]
                curr_stock = current_stocks.get(p, 0)
                row = {"カテゴリ": r["大カテゴリ"], "製品名": format_name(p), "現在庫": curr_stock}
                for d in show_dates:
                    row[d.strftime("%m/%d")] = future_stocks.get(p, {}).get(d, curr_stock)
                inv_list.append(row)
                
            inv_df = pd.DataFrame(inv_list).sort_values("カテゴリ")
            st.dataframe(inv_df.style.map(lambda x: 'color: #dc2626; font-weight: bold; background-color: #fee2e2;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True, height=600)

    with t2:
        cal_data = []
        for i in range(7):
            d = today + timedelta(days=i)
            m_txt = "\n".join([f"製: {r['製品名']} ({to_int(r['ケース数'])}cs)" for _, r in manus_df[manus_df["製造予定日"]==d].iterrows()]) if not manus_df.empty else ""
            o_txt = "\n".join([f"出: {r['顧客名']} : {r['製品名']} ({to_int(r['ケース数'])}cs)" for _, r in orders_df[orders_df["納品予定日"]==d].iterrows()]) if not orders_df.empty else ""
            cal_data.append({"日付": d.strftime("%m/%d"), "製造": m_txt, "出荷": o_txt})
        st.download_button("🖨️ カレンダーExcel出力", data=pd.DataFrame(cal_data).to_csv(index=False, encoding="utf-8-sig"), file_name=f"予定_{today.strftime('%Y%m%d')}.csv", type="primary", use_container_width=True)
        
        html = '<table class="sched-table"><tr><th style="width:100px;">日付</th><th style="width:45%;">製造</th><th style="width:45%;">出荷/返品</th></tr>'
        for i in range(7):
            d = today + timedelta(days=i)
            
            m_h = "".join([f'<div style="background:#F0FFF4; border-left:4px solid #10B981; padding:6px; margin-bottom:4px; border-radius:4px;"><span style="font-weight:700;">{format_name(r["製品名"])}</span> <span style="float:right; font-weight:900; color:#059669;">{to_int(r["ケース数"])}cs</span></div>' for _,r in manus_df[manus_df["製造予定日"]==d].iterrows()]) if not manus_df.empty else ""
            
            o_h = ""
            for _, r in orders_df[orders_df["納品予定日"] == d].iterrows():
                p = r["製品名"]
                qty = to_int(r.get("ケース数", 0))
                stock_on_day = future_stocks.get(p, {}).get(d, 0)
                
                if qty < 0:
                    qty_html = f'<span style="color:#1E3A8A; font-weight:900;">⤴️ {-qty}cs 復帰</span>'
                    bg_color, border_color = "#DBEAFE", "#1E3A8A"
                elif stock_on_day < 0:
                    qty_html = f'<span style="color:#DC2626; font-weight:900;">{qty}cs (不足)</span>'
                    bg_color, border_color = "#FEE2E2", "#DC2626"
                else:
                    qty_html = f'<span style="color:#1D4ED8; font-weight:900;">{qty}cs</span>'
                    bg_color, border_color = "#F0F7FF", "#2563EB"
                    
                o_h += f'<div style="background:{bg_color}; border-left:4px solid {border_color}; padding:6px; margin-bottom:4px; border-radius:4px;"><span style="font-weight:700;">{r["顧客名"]}: {format_name(p)}</span> <span style="float:right;">{qty_html}</span></div>'
                
            html += f'<tr><td><b>{d.strftime("%m/%d")}</b><br>{["月","火","水","木","金","土","日"][d.dayofweek]}曜</td><td>{m_h}</td><td>{o_h}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)

    with t3:
        st.markdown('### 🔍 製品別 在庫推移と詳細スケジュール')
        if master_df_unique.empty: st.info("製品が登録されていません。")
        else:
            cat_full_det = st.pills("カテゴリ詳細", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed", key="pills_det")
            cat_det = cat_full_det.split(" ", 1)[1] if cat_full_det else CATEGORIES[0].split(" ", 1)[1]
            sc1_det, sc2_det = st.columns([1.5, 2.5])
            search_p_det = sc1_det.text_input("🔍 製品名検索", placeholder="検索...", key="search_det")
            prods_det = [p for p in master_df_unique["製品名"].tolist() if search_p_det in p] if search_p_det else (master_df_unique[master_df_unique["大カテゴリ"] == cat_det]["製品名"].tolist() if not master_df_unique.empty else [])
            sel_prod = sc2_det.selectbox("確定製品", options=prods_det, index=None, format_func=format_name, key="sel_det", placeholder="選択してください")
            
            if sel_prod:
                prod_cur_stock = current_stocks.get(sel_prod, 0)
                p_o_ev = orders_df[(orders_df["製品名"] == sel_prod) & (orders_df["納品予定日"] >= today)][["納品予定日", "顧客名", "ケース数"]] if not orders_df.empty else pd.DataFrame(columns=["納品予定日", "顧客名", "ケース数"])
                p_m_ev = manus_df[(manus_df["製品名"] == sel_prod) & (manus_df["製造予定日"] >= today)][["製造予定日", "備考", "ケース数"]] if not manus_df.empty else pd.DataFrame(columns=["製造予定日", "備考", "ケース数"])
                
                detail_list = []
                temp_stock = prod_cur_stock
                show_dates = pd.date_range(today, today + timedelta(days=30))
                for d in show_dates:
                    day_o = p_o_ev[p_o_ev["納品予定日"].dt.date == d.date()]
                    out_qty = sum(to_int(r['ケース数']) for _, r in day_o.iterrows()) if not day_o.empty else 0
                    out_detail = " / ".join([f"{r['顧客名']}({to_int(r['ケース数'])}cs)" for _, r in day_o.iterrows()]) if not day_o.empty else "-"
                    
                    day_m = p_m_ev[p_m_ev["製造予定日"].dt.date == d.date()]
                    in_qty = sum(to_int(r['ケース数']) for _, r in day_m.iterrows()) if not day_m.empty else 0
                    in_detail = " / ".join([f"製造({to_int(r['ケース数'])}cs)" for _, r in day_m.iterrows()]) if not day_m.empty else "-"
                    
                    temp_stock = temp_stock + in_qty - out_qty
                    detail_list.append({"日付": d.strftime("%m/%d"), "曜日": ["月","火","水","木","金","土","日"][d.dayofweek], "製造 (入)": in_qty, "製造詳細": in_detail, "出荷 (出)": out_qty, "出荷詳細": out_detail, "予定在庫": temp_stock})
                
                df_detail = pd.DataFrame(detail_list)
                fig = px.line(df_detail, x="日付", y="予定在庫", title=f"【{sel_prod}】 1ヶ月の予定在庫推移", markers=True)
                fig.add_bar(x=df_detail["日付"], y=df_detail["製造 (入)"], name="製造", marker_color="#10B981", opacity=0.6)
                fig.add_bar(x=df_detail["日付"], y=-df_detail["出荷 (出)"], name="出荷", marker_color="#F43F5E", opacity=0.6)
                fig.update_layout(hovermode="x unified", yaxis_title="ケース数", margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df_detail.style.map(lambda x: 'color: #DC2626; font-weight: bold; background-color: #FEE2E2;' if isinstance(x, int) and x < 0 else '', subset=["予定在庫"]), use_container_width=True, hide_index=True)

    with t4:
        st.markdown('### 👤 顧客別 今後の発送スケジュール')
        cust_list_sch = sorted(orders_df[orders_df["顧客名"].str.strip() != ""]["顧客名"].unique().tolist()) if not orders_df.empty else []
        sc1_cust, sc2_cust = st.columns([1.5, 2.5])
        search_c = sc1_cust.text_input("🔍 顧客検索", placeholder="名前の一部を入力...")
        filtered_custs = [c for c in cust_list_sch if search_c in c] if search_c else cust_list_sch
        sel_cust = sc2_cust.selectbox("対象顧客を選択", options=filtered_custs, index=None, placeholder="選択してください")
        
        if sel_cust:
            cust_orders = orders_df[(orders_df["顧客名"] == sel_cust) & (orders_df["納品予定日"] >= today)].copy()
            if cust_orders.empty:
                st.info("今後の納品予定はありません。")
            else:
                cust_orders = cust_orders.sort_values("納品予定日")
                def check_shortage(row):
                    d = pd.Timestamp(row["納品予定日"]).normalize()
                    p = row["製品名"]
                    if d in dates and p in future_stocks:
                        if future_stocks[p][d] < 0: return f"❌ 欠品注意 ({future_stocks[p][d]})"
                    return "✅ OK"

                cust_orders["在庫状況"] = cust_orders.apply(check_shortage, axis=1)
                cust_orders["納品予定日"] = cust_orders["納品予定日"].dt.strftime("%Y-%m-%d")
                display_cols = ["納品予定日", "製品名", "ケース数", "在庫状況", "備考"]
                
                st.dataframe(
                    cust_orders[display_cols].style.map(lambda v: 'color: #DC2626; font-weight: bold; background-color: #FEE2E2;' if "❌" in str(v) else '', subset=["在庫状況"]),
                    use_container_width=True, hide_index=True
                )

# --- 📊 統計・分析 ---
elif page == "📊 統計・分析":
    st.markdown('<div class="slim-header" style="background:#4C1D95;"><h1>📊 ABC分析 ＆ 顧客ランキング</h1></div>', unsafe_allow_html=True)
    if not orders_df.empty:
        # 確実に数値化して集計
        o_stat = orders_df.copy()
        o_stat["ケース数"] = o_stat["ケース数"].apply(to_int)
        abc = o_stat.groupby("製品名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False)
        total_sum = abc["ケース数"].sum()
        if total_sum > 0:
            abc["累計比率"] = abc["ケース数"].cumsum() / total_sum * 100
            abc["ランク"] = pd.cut(abc["累計比率"], bins=[0, 70, 90, 100], labels=["A (主力)", "B (中堅)", "C (その他)"])
            st.dataframe(abc.style.map(lambda v: 'background-color: #FEE2E2; font-weight: 900;' if "A" in str(v) else '', subset=["ランク"]), use_container_width=True, hide_index=True)
            cust_abc = o_stat[o_stat["顧客名"]!="未指定"].groupby("顧客名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False).head(15)
            if not cust_abc.empty:
                st.plotly_chart(px.bar(cust_abc, x="ケース数", y="顧客名", orientation='h', title="主要顧客TOP15"), use_container_width=True)

# --- ⚙️ マスタ管理 ---
elif page == "⚙️ マスタ管理":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #475569 0%, #1E293B 100%);"><h1>⚙️ マスタ・顧客データ管理</h1></div>', unsafe_allow_html=True)
    st.info("💡 ここでデータを追加・修正すると、アプリ全体の設定（ドロップダウン等）に即座に反映されます。表の下にある「＋」を押して行を追加できます。")
    
    tab_m1, tab_m2, tab_m3 = st.tabs(["📦 製品マスタ (資材紐付け)", "🏢 顧客マスタ", "📦 資材マスタ (段ボール等)"])
    
    with tab_m1:
        st.markdown("### 製品カテゴリ・初期在庫・資材連動の編集")
        pack_names = pack_mst_unique["資材名"].tolist() if not pack_mst_unique.empty else []
        edited_master = st.data_editor(
            master_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={
                "大カテゴリ": st.column_config.SelectboxColumn("大カテゴリ", options=[c.split(" ", 1)[1] for c in CATEGORIES], required=True),
                "製品名": st.column_config.TextColumn("製品名", required=True),
                "初期在庫数": st.column_config.NumberColumn("初期在庫数", min_value=-9999, default=0, required=True),
                "使用資材名": st.column_config.SelectboxColumn("使用資材名 (紐付け)", options=pack_names),
                "資材使用数": st.column_config.NumberColumn("1ケースあたりの資材数", min_value=0, default=1)
            },
            key="edit_master"
        )
        if st.button("💾 製品マスタを保存・同期", type="primary", use_container_width=True):
            save_and_sync("master", edited_master); st.success("✅ 製品マスタを更新しました！"); st.rerun()
            
    with tab_m2:
        st.markdown("### 顧客リストの編集")
        edited_cust = st.data_editor(
            cust_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={"顧客名": st.column_config.TextColumn("顧客名", required=True), "ふりがな": st.column_config.TextColumn("ふりがな")},
            key="edit_cust"
        )
        if st.button("💾 顧客マスタを保存・同期", type="primary", use_container_width=True):
            save_and_sync("customers", edited_cust); st.success("✅ 顧客マスタを更新しました！"); st.rerun()

    with tab_m3:
        st.markdown("### 段ボール等 資材の編集")
        edited_pack = st.data_editor(
            pack_mst_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={
                "資材名": st.column_config.TextColumn("資材名 (段ボール名等)", required=True),
                "初期在庫": st.column_config.NumberColumn("初期在庫", default=0, required=True),
                "適正在庫": st.column_config.NumberColumn("適正在庫 (警告ライン)", default=100)
            },
            key="edit_pack_mst"
        )
        if st.button("💾 資材マスタを保存・同期", type="primary", use_container_width=True):
            save_and_sync("packaging_master", edited_pack); st.success("✅ 資材マスタを更新しました！"); st.rerun()
