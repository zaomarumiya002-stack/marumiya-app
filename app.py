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
# 0. 絶対安全な数値変換関数（Seriesエラー・NaN完全防止）
# ─────────────────────────────────────────────
def to_int(v):
    try:
        if isinstance(v, pd.Series): v = v.sum()
        if pd.isna(v) or v == "": return 0
        return int(float(v))
    except: return 0

# ─────────────────────────────────────────────
# 1. ページ基本設定 & CSS
# ─────────────────────────────────────────────
st.set_page_config(page_title="丸実屋 統合管理システム", page_icon="🏭", layout="wide", initial_sidebar_state="expanded")

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
    /* ★ 特大ボタン ★ */
    [data-testid="stPills"] button { padding: 16px 32px !important; font-size: 20px !important; font-weight: 900 !important; border-radius: 12px !important; border: 2px solid #CBD5E1 !important; margin: 6px !important; }
    [data-testid="stPills"] button[aria-selected="true"] { background-color: #2563EB !important; color: #FFFFFF !important; box-shadow: 0 6px 15px rgba(37, 99, 235, 0.4) !important; }
    .sched-table { width: 100%; border-collapse: collapse; background: white; font-size: 15px; border-radius: 10px; overflow: hidden; }
    .sched-table th { background: #F8FAFC; padding: 10px; border-bottom: 2px solid #E2E8F0; }
    .sched-table td { padding: 10px; border-bottom: 1px solid #F1F5F9; vertical-align: top; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 2. ログイン認証
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
# 3. GSpread 同期ロジック (KeyError・列名正規化対応)
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
            "packaging_master": ["資材名","品番","規格","仕入先","保管場所","単位","初期在庫","発注点"],
            "packaging_logs": ["ID","登録日","資材名","処理区分","数量","理由","備考","登録日時"]
        }[name]
        
        if len(data) <= 1: return pd.DataFrame(columns=cols)
        df = pd.DataFrame(data[1:], columns=data[0])
        
        # 【最優先】列名の空白除去と重複排除（KeyError・Seriesエラーの物理的排除）
        df.columns = df.columns.str.strip().str.replace(' ', '').str.replace('　', '')
        df = df.loc[:, ~df.columns.duplicated()]
        
        # 足りない列を補完
        for c in cols:
            if c not in df.columns: df[c] = ""
            
        for c in ["ケース数", "初期在庫数", "資材使用数", "初期在庫", "発注点", "数量"]:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).apply(to_int)
        for c in ["納品予定日", "製造予定日", "登録日", "登録日時"]:
            if c in df.columns: df[c] = pd.to_datetime(df[c], errors='coerce')
        return df[cols]
    except Exception: 
        return pd.DataFrame(columns={"orders":["ID","納品予定日","顧客名","大カテゴリ","製品名","ケース数","備考","登録日時"],"manufactures":["ID","製造予定日","備考","大カテゴリ","製品名","ケース数","登録日時"],"master":["大カテゴリ","製品名","初期在庫数","使用資材名","資材使用数"],"customers":["顧客名","ふりがな"],"packaging_master":["資材名","品番","規格","仕入先","保管場所","単位","初期在庫","発注点"],"packaging_logs":["ID","登録日","資材名","処理区分","数量","理由","備考","登録日時"]}[name])

def save_and_sync(name, df):
    try: ws = sheet.worksheet(name)
    except: ws = sheet.add_worksheet(title=name, rows="1000", cols="20")
    ws.clear()
    df_save = df.copy()
    for col in df_save.columns:
        if pd.api.types.is_datetime64_any_dtype(df_save[col]): df_save[col] = df_save[col].dt.strftime('%Y-%m-%d %H:%M:%S').replace('NaT', '')
        elif pd.api.types.is_numeric_dtype(df_save[col]): df_save[col] = df_save[col].fillna(0).apply(to_int).astype(str)
    df_save = df_save.fillna("").astype(str).replace(["nan", "None", "NaT"], "")
    ws.update(values=[df_save.columns.values.tolist()] + df_save.values.tolist(), range_name='A1')
    st.cache_data.clear() # 即時キャッシュクリア（複数人対応）
    st.session_state[f"{name}_df"] = load_data_from_cloud(name)

def append_and_sync(name, new_row_df):
    try: ws = sheet.worksheet(name)
    except: ws = sheet.add_worksheet(title=name, rows="1000", cols="20"); ws.append_row(new_row_df.columns.tolist())
    row_copy = new_row_df.copy()
    for col in row_copy.columns:
        if pd.api.types.is_datetime64_any_dtype(row_copy[col]): row_copy[col] = row_copy[col].dt.strftime('%Y-%m-%d %H:%M:%S').replace('NaT', '')
    row_to_send = row_copy.fillna("").astype(str).replace(["nan", "None", "NaT"], "").values[0].tolist()
    ws.append_row(row_to_send)
    st.cache_data.clear() # 即時キャッシュクリア
    st.session_state[f"{name}_df"] = pd.concat([st.session_state[f"{name}_df"], new_row_df], ignore_index=True)

for sheet_name in ["orders", "manufactures", "master", "customers", "packaging_master", "packaging_logs"]:
    if f"{sheet_name}_df" not in st.session_state: st.session_state[f"{sheet_name}_df"] = load_data_from_cloud(sheet_name)
if "current_page" not in st.session_state: st.session_state.current_page = "📋 受注登録"
if "success_msg" not in st.session_state: st.session_state.success_msg = None

orders_df = st.session_state.orders_df
manus_df = st.session_state.manufactures_df
master_df = st.session_state.master_df
cust_df = st.session_state.customers_df
pack_mst_df = st.session_state.packaging_master_df
pack_log_df = st.session_state.packaging_logs_df

CATEGORIES = ["🍝 つきこん", "🟫 平こん", "🍜 糸こん・しらたき", "🔺 三角こん", "🟤 玉こん", "🎲 ダイスこん", "🏷️ 短冊", "🇯🇵 国産", "🤲 ちぎりこん", "🏮 大黒屋", "🏭 かねこ", "❄️ 冷凍耐性", "📦 その他"]
def format_name(n): return f"⚫️ {n}" if "黒" in str(n) else f"⚪️ {n}" if "白" in str(n) else f"📦 {n}"

# ─────────────────────────────────────────────
# 4. 在庫計算エンジン（製品 ＆ 資材の完全連動）
# ─────────────────────────────────────────────
today = pd.Timestamp.today().normalize()
dates = pd.date_range(today, today + timedelta(days=60))

# --- 製品在庫 ---
current_stocks = {}
future_stocks = {}
master_df_unique = master_df.drop_duplicates(subset=["製品名"]) if not master_df.empty else pd.DataFrame()

if not master_df_unique.empty:
    o_ev = orders_df[["納品予定日", "製品名", "ケース数"]].copy() if not orders_df.empty else pd.DataFrame(columns=["納品予定日", "製品名", "ケース数"])
    if not o_ev.empty:
        o_ev = o_ev.rename(columns={"納品予定日":"日付", "ケース数":"qty"})
        o_ev["qty"] = -pd.to_numeric(o_ev["qty"], errors='coerce').fillna(0) # 出荷はマイナス。負数入力（復帰）はプラス化
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
        curr_stock = to_int(r.get("初期在庫数", 0)) + to_int(past_ev.get(p, 0))
        current_stocks[p] = curr_stock
        p_future_row = pivot_ev.loc[p] if p in pivot_ev.index else pd.Series(0, index=dates)
        if isinstance(p_future_row, pd.DataFrame): p_future_row = p_future_row.sum(axis=0)
        p_future_cumsum = p_future_row.reindex(dates, fill_value=0).fillna(0).cumsum()
        future_stocks[p] = {d: curr_stock + to_int(p_future_cumsum.get(d, 0)) for d in dates}

# --- 資材推移サマリ ---
pack_summary = {}
pack_mst_unique = pack_mst_df.drop_duplicates(subset=["資材名"]) if not pack_mst_df.empty else pd.DataFrame()

if not pack_mst_unique.empty:
    for _, r in pack_mst_unique.iterrows():
        pack_summary[r["資材名"]] = {
            "品番": str(r.get("品番", "")), "規格": str(r.get("規格", "")), "仕入先": str(r.get("仕入先", "")),
            "保管場所": str(r.get("保管場所", "")), "単位": str(r.get("単位", "")),
            "期首在庫": to_int(r.get("初期在庫", 0)), "発注点": to_int(r.get("発注点", 0)),
            "期間入庫累計": 0, "期間出庫消費": 0, "現在庫": 0
        }

# 単体ログからの増減（数量は常に正の数で記録され、処理区分で判断）
if not pack_log_df.empty:
    for _, r in pack_log_df.iterrows():
        p_name, qty, p_type = r.get("資材名", ""), to_int(r.get("数量", 0)), str(r.get("処理区分", ""))
        if p_name in pack_summary:
            if "入庫" in p_type: pack_summary[p_name]["期間入庫累計"] += qty
            elif "出庫" in p_type: pack_summary[p_name]["期間出庫消費"] += qty

# 製品出荷との連動（非連動タグがある場合はスキップ）
if not orders_df.empty and not master_df_unique.empty:
    master_pack_info = master_df_unique.set_index("製品名")[["使用資材名", "資材使用数"]].to_dict('index')
    for _, r in orders_df.iterrows():
        prod, qty, rem = str(r.get("製品名", "")), to_int(r.get("ケース数", 0)), str(r.get("備考", ""))
        if prod in master_pack_info and "【資材非連動】" not in rem:
            pack_name = master_pack_info[prod].get("使用資材名", "")
            pack_usage = to_int(master_pack_info[prod].get("資材使用数", 0))
            if pack_name and pack_usage > 0 and pack_name in pack_summary:
                # qtyが正(出荷)なら資材消費(プラス)、qtyが負(復帰)なら資材戻る(マイナス消費)
                pack_summary[pack_name]["期間出庫消費"] += (qty * pack_usage)

for d in pack_summary.values():
    d["現在庫"] = d["期首在庫"] + d["期間入庫累計"] - d["期間出庫消費"]
    d["状態"] = "⚠️ 注意" if d["現在庫"] < d["発注点"] else "✅ 正常"

# ─────────────────────────────────────────────
# 5. サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<p style='font-size:20px; font-weight:900; color:#1E3A8A; margin-bottom:20px;'>🏭 丸実屋システム</p>", unsafe_allow_html=True)
    st.write("---")
    menu_items = ["📋 受注登録", "🏭 製造登録", "📦 資材・入出庫", "📑 登録一覧", "📊 在庫・スケジュール", "⚙️ マスタ・分析"]
    for item in menu_items:
        if st.button(item, key=f"menu_{item}", use_container_width=True, type="primary" if st.session_state.current_page == item else "secondary"):
            st.session_state.current_page = item; st.rerun()
page = st.session_state.current_page

# ─────────────────────────────────────────────
# 6. 画面描画
# ─────────────────────────────────────────────

# --- 受注登録 ---
if page == "📋 受注登録":
    st.markdown('<div class="slim-header"><h1>📋 受注・リパック 登録</h1></div>', unsafe_allow_html=True)
    with st.container():
        c1, c2, c3 = st.columns([1, 2, 1])
        o_date = c1.date_input("📅 納品日", value=date.today() + timedelta(days=1))
        c_name = c2.selectbox("🏢 顧客名", options=sorted(cust_df["顧客名"].unique()) if not cust_df.empty else [], index=None, placeholder="検索...")
        qty = c3.number_input("📦 ケース数", value=None, placeholder="負数(-10)で復帰")
        
        cat_full = st.pills("カテゴリ", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
        cat = cat_full.split(" ", 1)[1] if cat_full else CATEGORIES[0].split(" ", 1)[1]
        sc1, sc2 = st.columns([1.5, 2.5])
        search_p = sc1.text_input("🔍 製品検索", placeholder="名称の一部を入力...")
        prods = [p for p in master_df_unique["製品名"].tolist() if search_p in p] if search_p else (master_df_unique[master_df_unique["大カテゴリ"] == cat]["製品名"].tolist() if not master_df_unique.empty else [])
        prod = sc2.selectbox("確定製品", options=prods, index=None, placeholder="選択してください", format_func=format_name)
        rem = sc2.text_input("📝 備考")
        
        # イレギュラー時の資材非連動オプション
        col_chk1, col_chk2 = sc2.columns(2)
        is_substitute = col_chk1.checkbox("🔄 代替品として送付")
        is_irregular = col_chk2.checkbox("⚠️ イレギュラー(水漏れ等)")
        
        is_pack_link = True
        if is_irregular:
            is_pack_link = st.checkbox("📦 製品の復帰と同時に、段ボール(資材)の在庫も戻す", value=True)
            
        st.write("---")

        if prod and qty is not None and qty > 0 and current_stocks.get(prod, 0) < qty:
            st.warning(f"⚠️ 製品在庫が不足します（現在庫: **{current_stocks.get(prod, 0)}** cs）", icon="🚨")

        msg_slot = st.empty()
        if st.button("✅ 受注（出庫・復帰）を登録する", type="primary", use_container_width=True):
            if not prod or qty is None: msg_slot.error("⚠️ 【製品・ケース数】は必須です。")
            else:
                prefix = ""
                if is_substitute: prefix += "【代替品】"
                if is_irregular: prefix += "【イレギュラー】"
                if qty < 0: prefix += "【在庫復帰】"
                if not is_pack_link: prefix += "【資材非連動】"
                
                new_row = pd.DataFrame([{
                    "ID": str(uuid.uuid4())[:6].upper(), "納品予定日": pd.to_datetime(o_date), "顧客名": c_name if c_name else "未指定",
                    "大カテゴリ": cat, "製品名": prod, "ケース数": to_int(qty), "備考": f"{prefix} {rem}".strip(), "登録日時": datetime.now()
                }])
                append_and_sync("orders", new_row)
                st.session_state.success_msg = f"✨ 登録完了：{prod}"
                st.rerun()
        if st.session_state.success_msg:
            msg_slot.success(st.session_state.success_msg)
            st.session_state.success_msg = None

    st.markdown('<h2 style="font-size:18px; margin-top:20px;">✏️ かんたん修正（直近5件）</h2>', unsafe_allow_html=True)
    if not orders_df.empty:
        recent = orders_df.sort_values("登録日時", ascending=False).head(5).copy()
        recent["納品予定日"] = recent["納品予定日"].dt.date
        edited = st.data_editor(recent, use_container_width=True, hide_index=True, column_config={"納品予定日": st.column_config.DateColumn("納品日", format="YYYY-MM-DD"), "ケース数": st.column_config.NumberColumn("ケース数"), "登録日時": None}, key="edit_o")
        if st.button("💾 修正保存", key="btn_edit_o"):
            save_and_sync("orders", pd.concat([orders_df[~orders_df["ID"].isin(recent["ID"])], edited], ignore_index=True))
            st.rerun()

# --- 🏭 製造登録 ---
elif page == "🏭 製造登録":
    st.markdown('<div class="slim-header header-manu"><h1>🏭 製造データ登録</h1></div>', unsafe_allow_html=True)
    with st.container():
        col1, col2 = st.columns([1, 1])
        m_date = col1.date_input("📅 製造日", value=date.today())
        m_qty = col2.number_input("📦 製造ケース数", value=None, placeholder="数字を入力...")
        cat_full_m = st.pills("カテゴリ製造", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
        cat_m = cat_full_m.split(" ", 1)[1] if cat_full_m else CATEGORIES[0].split(" ", 1)[1]
        sc1_m, sc2_m = st.columns([1.5, 2.5])
        search_p_m = sc1_m.text_input("🔍 製品名検索", placeholder="検索...", key="sm")
        prods_m = [p for p in master_df_unique["製品名"].tolist() if search_p_m in p] if search_p_m else (master_df_unique[master_df_unique["大カテゴリ"] == cat_m]["製品名"].tolist() if not master_df_unique.empty else [])
        prod_m = sc2_m.selectbox("確定製品", options=prods_m, index=None, format_func=format_name, key="selm")
        
        m_msg_slot = st.empty()
        if st.button("➕ 製造を記録する", type="primary", use_container_width=True):
            if not prod_m or m_qty is None: m_msg_slot.error("⚠️ 【製品・数量】は必須です。")
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
        edited_m = st.data_editor(recent_m, use_container_width=True, hide_index=True, column_config={"製造予定日": st.column_config.DateColumn("製造日", format="YYYY-MM-DD"), "ケース数": st.column_config.NumberColumn("ケース数"), "登録日時": None}, key="edit_m")
        if st.button("💾 修正を保存", key="smb"):
            save_and_sync("manufactures", pd.concat([manus_df[~manus_df["ID"].isin(recent_m["ID"])], edited_m], ignore_index=True))
            st.rerun()

# --- 📦 資材管理 ---
elif page == "📦 資材・入出庫":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #B45309 0%, #D97706 100%);"><h1>📦 資材・段ボール入出庫</h1></div>', unsafe_allow_html=True)
    
    # ⚠️ 要発注アラート
    shortage_packs = [p_name for p_name, d in pack_summary.items() if d["現在庫"] < d["発注点"]]
    if shortage_packs:
        st.error(f"🚨 **要発注アラート（現在庫が発注点未満）:**\n\n" + "、".join(shortage_packs))
        st.write("---")

    st.markdown("### 📝 資材の単体入出庫・棚卸調整")
    with st.container():
        p_date = st.date_input("📅 処理日", value=date.today())
        
        sc1, sc2 = st.columns([1.5, 2.5])
        search_pack = sc1.text_input("🔍 資材名検索", placeholder="検索...")
        filtered_packs = [p for p in pack_mst_unique["資材名"].tolist() if search_pack in p] if search_pack else pack_mst_unique["資材名"].tolist()
        sel_pack = sc2.selectbox("📦 対象資材", options=filtered_packs, index=None, placeholder="選択してください")
        
        # 直感的な入出庫・棚卸UI
        p_type = st.radio("処理区分", options=["📥 入庫 (在庫を増やす)", "📤 出庫・廃棄 (在庫を減らす)", "📋 棚卸 (現在の実在庫を入力)"], horizontal=True)
        
        if "棚卸" in p_type:
            p_qty = st.number_input("現在の実在庫数 (正の数)", min_value=0, value=None)
            reason_options = ["棚卸調整"]
        else:
            p_qty = st.number_input("処理する数量 (常に正の数で入力)", min_value=1, value=None)
            reason_options = ["仕入（購入）", "返品受付", "その他入庫"] if "入庫" in p_type else ["破損・廃棄", "サンプル出荷", "その他出庫"]
            
        p_reason = st.selectbox("詳細な理由", options=reason_options)
        p_rem = st.text_input("📝 備考")
        
        if st.button("➕ 資材ログを登録", type="primary", use_container_width=True):
            if not sel_pack or p_qty is None: 
                st.error("⚠️ 資材名と数量は必須です。")
            else:
                log_qty = to_int(p_qty)
                final_p_type = "入庫" if "入庫" in p_type else "出庫"
                
                # 棚卸の場合は差分を計算
                if "棚卸" in p_type:
                    current_calc_stock = pack_summary[sel_pack]["現在庫"]
                    diff = log_qty - current_calc_stock
                    if diff >= 0:
                        final_p_type = "入庫"
                        log_qty = diff
                    else:
                        final_p_type = "出庫"
                        log_qty = abs(diff)
                
                if log_qty > 0: # 差分が0の場合は登録しない
                    new_pack = pd.DataFrame([{
                        "ID": str(uuid.uuid4())[:6].upper(), "登録日": pd.to_datetime(p_date),
                        "資材名": sel_pack, "処理区分": final_p_type, "数量": log_qty, "理由": p_reason, "備考": p_rem, "登録日時": datetime.now()
                    }])
                    append_and_sync("packaging_logs", new_pack)
                    st.success(f"✨ 登録完了：{sel_pack} ({final_p_type} {log_qty})")
                    st.rerun()
                else:
                    st.info("現在の計算在庫と一致しているため、調整は不要です。")

    st.markdown('<h2 style="font-size:18px; margin-top:20px;">📊 資材の在庫一覧サマリ</h2>', unsafe_allow_html=True)
    if pack_mst_unique.empty: st.info("⚙️ マスタ管理から資材を登録してください。")
    else:
        df_pack = pd.DataFrame([{"資材名": k, **v} for k, v in pack_summary.items()])
        def highlight_pack(row):
            if to_int(row.get("現在庫",0)) < to_int(row.get("発注点",0)): return ['background-color: #FFEDD5; color: #C2410C; font-weight: bold;'] * len(row)
            return [''] * len(row)
            
        display_cols = ["資材名", "品番", "規格", "仕入先", "保管場所", "現在庫", "発注点", "状態", "単位"]
        st.dataframe(df_pack[display_cols].style.apply(highlight_pack, axis=1), use_container_width=True, hide_index=True)
        st.download_button("📥 サマリをCSV出力", data=df_pack.to_csv(index=False, encoding="utf-8-sig"), file_name=f"資材状況_{date.today()}.csv", use_container_width=True)

    st.markdown('<h2 style="font-size:18px; margin-top:20px;">✏️ かんたん修正（直近5件）</h2>', unsafe_allow_html=True)
    if not pack_log_df.empty:
        recent_p = pack_log_df.sort_values("登録日時", ascending=False).head(5).copy()
        recent_p["登録日"] = recent_p["登録日"].dt.date
        edited_p = st.data_editor(recent_p, use_container_width=True, hide_index=True, column_config={
            "登録日": st.column_config.DateColumn("登録日", format="YYYY-MM-DD"), 
            "処理区分": st.column_config.SelectboxColumn("処理区分", options=["入庫", "出庫"]),
            "数量": st.column_config.NumberColumn("数量", min_value=1),
            "登録日時": None
        }, key="edit_p")
        if st.button("💾 資材ログを修正保存", key="btn_edit_p"):
            save_and_sync("packaging_logs", pd.concat([pack_log_df[~pack_log_df["ID"].isin(recent_p["ID"])], edited_p], ignore_index=True))
            st.rerun()

# --- 📑 登録一覧 ---
elif page == "📑 登録一覧":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #0F766E 0%, #14B8A6 100%);"><h1>📑 登録データ一覧・出力</h1></div>', unsafe_allow_html=True)
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
                    d, p, qty = pd.Timestamp(row["納品予定日"]).normalize(), row["製品名"], to_int(row.get("ケース数", 0))
                    stock = future_stocks[p][d] if d >= today and p in future_stocks and d in future_stocks[p] else current_stocks.get(p, 0)
                    if qty < 0: return f"⤴️ 復帰 (+{-qty})"
                    elif stock < 0: return f"在庫不足 ({stock})"
                    else: return f"OK (+{stock})"
                except: return "不明"

            edit_df.insert(7, "在庫状況", edit_df.apply(get_stock_status, axis=1))

            def highlight_row(row):
                is_return = to_int(row.get("ケース数", 0)) < 0
                is_irregular = "【イレギュラー】" in str(row.get("備考", ""))
                is_shortage = "不足" in str(row.get("在庫状況", ""))
                if is_return: return ['background-color: #DBEAFE; color: #1E3A8A; font-weight: bold;'] * len(row)
                if is_shortage and is_irregular: return ['background-color: #FEF08A; color: #DC2626; font-weight: bold;'] * len(row)
                if is_shortage: return ['background-color: #FEE2E2; color: #DC2626; font-weight: bold;'] * len(row)
                if is_irregular: return ['background-color: #FEF08A; color: #854D0E; font-weight: bold;'] * len(row)
                return [''] * len(row)

            st.download_button("📥 受注データをCSV出力", data=edit_df.to_csv(index=False, encoding="utf-8-sig"), file_name=f"受注一覧_{date.today()}.csv", use_container_width=True)
            st.markdown("""<div style="font-size:14px; margin-bottom:10px;">
                <b>🎨 色：</b> <span style="background-color:#FEE2E2; color:#DC2626; padding:2px 6px;">在庫不足（赤字）</span> / <span style="background-color:#FEF08A; color:#854D0E; padding:2px 6px;">イレギュラー対応（黄色）</span> / <span style="background-color:#DBEAFE; color:#1E3A8A; padding:2px 6px;">⤴️ 在庫復帰（青色）</span>
            </div>""", unsafe_allow_html=True)
            edited = st.data_editor(edit_df.style.apply(highlight_row, axis=1), use_container_width=True, hide_index=True, height=600, column_config={"ID": None, "登録日時": None, "大カテゴリ": None, "納品予定日": st.column_config.DateColumn("納品日", format="YYYY-MM-DD", required=True), "ケース数": st.column_config.NumberColumn("ケース数", required=True), "在庫状況": st.column_config.TextColumn("在庫状況", disabled=True)}, key="edit_all_orders")
            if st.button("💾 受注データを保存", type="primary", use_container_width=True):
                save_and_sync("orders", edited.drop(columns=["在庫状況"], errors='ignore'))
                st.success("✅ 更新しました！"); st.rerun()

    with t_list2:
        if pack_log_df.empty: st.info("資材ログがありません。")
        else:
            e_pack = pack_log_df.sort_values("登録日時", ascending=False).copy()
            e_pack["登録日"] = e_pack["登録日"].dt.date
            edited_pl = st.data_editor(e_pack, use_container_width=True, hide_index=True, column_config={"ID":None, "登録日時":None, "登録日":st.column_config.DateColumn("登録日", format="YYYY-MM-DD"), "数量": st.column_config.NumberColumn("数量", min_value=1), "処理区分": st.column_config.SelectboxColumn("処理区分", options=["入庫", "出庫"])}, key="edit_plogs")
            if st.button("💾 資材ログを一括保存", type="primary", use_container_width=True):
                save_and_sync("packaging_logs", edited_pl); st.success("✅ 更新しました！"); st.rerun()

# --- 📊 在庫・スケジュール ---
elif page == "📊 在庫・スケジュール":
    st.markdown('<div class="slim-header"><h1>📊 在庫予測 ＆ カレンダー</h1></div>', unsafe_allow_html=True)
    
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
                for d in show_dates: row[d.strftime("%m/%d")] = future_stocks.get(p, {}).get(d, curr_stock)
                inv_list.append(row)
            st.dataframe(pd.DataFrame(inv_list).sort_values("カテゴリ").style.map(lambda x: 'color: #dc2626; font-weight: bold; background-color: #fee2e2;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True, height=600)

    with t2:
        cal_data = []
        html = '<table class="sched-table"><tr><th style="width:100px;">日付</th><th style="width:45%;">製造</th><th style="width:45%;">出荷/復帰</th></tr>'
        for i in range(7):
            d = today + timedelta(days=i)
            m_h = "".join([f'<div style="background:#F0FFF4; border-left:4px solid #10B981; padding:6px; margin-bottom:4px; border-radius:4px;"><span style="font-weight:700;">{format_name(r["製品名"])}</span> <span style="float:right; font-weight:900; color:#059669;">{to_int(r["ケース数"])}cs</span></div>' for _,r in manus_df[manus_df["製造予定日"]==d].iterrows()]) if not manus_df.empty else ""
            o_h = ""
            for _, r in orders_df[orders_df["納品予定日"] == d].iterrows():
                p, qty = r["製品名"], to_int(r.get("ケース数", 0))
                stock_on_day = future_stocks.get(p, {}).get(d, 0)
                if qty < 0: qty_html, bg_color, border_color = f'<span style="color:#1E3A8A; font-weight:900;">⤴️ {-qty}cs 復帰</span>', "#DBEAFE", "#1E3A8A"
                elif stock_on_day < 0: qty_html, bg_color, border_color = f'<span style="color:#DC2626; font-weight:900;">{qty}cs (不足)</span>', "#FEE2E2", "#DC2626"
                else: qty_html, bg_color, border_color = f'<span style="color:#1D4ED8; font-weight:900;">{qty}cs</span>', "#F0F7FF", "#2563EB"
                o_h += f'<div style="background:{bg_color}; border-left:4px solid {border_color}; padding:6px; margin-bottom:4px; border-radius:4px;"><span style="font-weight:700;">{r["顧客名"]}: {format_name(p)}</span> <span style="float:right;">{qty_html}</span></div>'
            html += f'<tr><td><b>{d.strftime("%m/%d")}</b><br>{["月","火","水","木","金","土","日"][d.dayofweek]}曜</td><td>{m_h}</td><td>{o_h}</td></tr>'
            
            m_txt = "\n".join([f"製: {r['製品名']} ({to_int(r['ケース数'])}cs)" for _, r in manus_df[manus_df["製造予定日"]==d].iterrows()]) if not manus_df.empty else ""
            o_txt = "\n".join([f"出: {r['顧客名']} : {r['製品名']} ({to_int(r['ケース数'])}cs)" for _, r in orders_df[orders_df["納品予定日"]==d].iterrows()]) if not orders_df.empty else ""
            cal_data.append({"日付": d.strftime("%m/%d"), "製造": m_txt, "出荷": o_txt})
            
        st.download_button("🖨️ カレンダーCSV出力", data=pd.DataFrame(cal_data).to_csv(index=False, encoding="utf-8-sig"), file_name=f"カレンダー_{today.strftime('%Y%m%d')}.csv", type="primary", use_container_width=True)
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
                p_o_ev = orders_df[(orders_df["製品名"] == sel_prod) & (orders_df["納品予定日"] >= today)][["納品予定日", "顧客名", "ケース数"]] if not orders_df.empty else pd.DataFrame(columns=["納品予定日", "顧客名", "ケース数"])
                p_m_ev = manus_df[(manus_df["製品名"] == sel_prod) & (manus_df["製造予定日"] >= today)][["製造予定日", "備考", "ケース数"]] if not manus_df.empty else pd.DataFrame(columns=["製造予定日", "備考", "ケース数"])
                
                detail_list = []
                temp_stock = current_stocks.get(sel_prod, 0)
                for d in pd.date_range(today, today + timedelta(days=30)):
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
                st.plotly_chart(fig.update_layout(hovermode="x unified", margin=dict(l=20, r=20, t=40, b=20)), use_container_width=True)
                st.dataframe(df_detail.style.map(lambda x: 'color: #DC2626; font-weight: bold; background-color: #FEE2E2;' if isinstance(x, int) and x < 0 else '', subset=["予定在庫"]), use_container_width=True, hide_index=True)

    with t4:
        st.markdown('### 👤 顧客別 今後の発送スケジュール')
        cust_list_sch = sorted(orders_df[orders_df["顧客名"].str.strip() != ""]["顧客名"].unique().tolist()) if not orders_df.empty else []
        sc1_cust, sc2_cust = st.columns([1.5, 2.5])
        search_c = sc1_cust.text_input("🔍 顧客検索", placeholder="名前の一部を入力...")
        sel_cust = sc2_cust.selectbox("対象顧客を選択", options=[c for c in cust_list_sch if search_c in c] if search_c else cust_list_sch, index=None, placeholder="選択してください")
        if sel_cust:
            cust_orders = orders_df[(orders_df["顧客名"] == sel_cust) & (orders_df["納品予定日"] >= today)].copy()
            if cust_orders.empty: st.info("今後の納品予定はありません。")
            else:
                cust_orders = cust_orders.sort_values("納品予定日")
                cust_orders["在庫状況"] = cust_orders.apply(lambda r: f"❌ 欠品 ({future_stocks[r['製品名']][pd.Timestamp(r['納品予定日']).normalize()]})" if future_stocks.get(r['製品名'], {}).get(pd.Timestamp(r['納品予定日']).normalize(), 0) < 0 else "✅ OK", axis=1)
                cust_orders["納品予定日"] = cust_orders["納品予定日"].dt.strftime("%Y-%m-%d")
                st.dataframe(cust_orders[["納品予定日", "製品名", "ケース数", "在庫状況", "備考"]].style.map(lambda v: 'color: #DC2626; font-weight: bold; background-color: #FEE2E2;' if "❌" in str(v) else '', subset=["在庫状況"]), use_container_width=True, hide_index=True)

# --- ⚙️ マスタ・分析 ---
elif page == "⚙️ マスタ・分析":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #475569 0%, #1E293B 100%);"><h1>⚙️ マスタ・データ分析</h1></div>', unsafe_allow_html=True)
    st.info("💡 ここでデータを追加・修正すると、アプリ全体の設定（ドロップダウン等）に即座に反映されます。表の下にある「＋」を押して行を追加できます。")
    
    t_m1, t_m2, t_m3, t_m4 = st.tabs(["📦 製品マスタ (資材紐付け)", "🏢 顧客マスタ", "📦 資材マスタ (段ボール等)", "📊 ABC分析"])
    
    with t_m1:
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
            }, key="edit_master"
        )
        if st.button("💾 製品マスタを保存・同期", type="primary", use_container_width=True):
            save_and_sync("master", edited_master); st.success("✅ 更新しました！"); st.rerun()
            
    with t_m2:
        st.markdown("### 顧客リストの編集")
        edited_cust = st.data_editor(cust_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"顧客名": st.column_config.TextColumn("顧客名", required=True), "ふりがな": st.column_config.TextColumn("ふりがな")}, key="edit_cust")
        if st.button("💾 顧客マスタを保存・同期", type="primary", use_container_width=True):
            save_and_sync("customers", edited_cust); st.success("✅ 更新しました！"); st.rerun()

    with t_m3:
        st.markdown("### 段ボール等 資材マスタの編集")
        edited_pack = st.data_editor(
            pack_mst_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={
                "資材名": st.column_config.TextColumn("資材名", required=True),
                "品番": st.column_config.TextColumn("品番"),
                "規格": st.column_config.TextColumn("規格"),
                "仕入先": st.column_config.TextColumn("仕入先"),
                "保管場所": st.column_config.TextColumn("保管場所"),
                "単位": st.column_config.TextColumn("単位"),
                "初期在庫": st.column_config.NumberColumn("初期在庫", default=0, required=True),
                "発注点": st.column_config.NumberColumn("発注点 (警告ライン)", default=100)
            }, key="edit_pack_mst"
        )
        if st.button("💾 資材マスタを保存・同期", type="primary", use_container_width=True):
            save_and_sync("packaging_master", edited_pack); st.success("✅ 更新しました！"); st.rerun()

    with t_m4:
        if not orders_df.empty:
            o_stat = orders_df.copy()
            o_stat["ケース数"] = o_stat["ケース数"].apply(to_int)
            abc = o_stat.groupby("製品名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False)
            if abc["ケース数"].sum() > 0:
                abc["累計比率"] = abc["ケース数"].cumsum() / abc["ケース数"].sum() * 100
                abc["ランク"] = pd.cut(abc["累計比率"], bins=[0, 70, 90, 100], labels=["A (主力)", "B (中堅)", "C (その他)"])
                st.dataframe(abc.style.map(lambda v: 'background-color: #FEE2E2; font-weight: 900;' if "A" in str(v) else '', subset=["ランク"]), use_container_width=True, hide_index=True)
                cust_abc = o_stat[o_stat["顧客名"]!="未指定"].groupby("顧客名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False).head(15)
                if not cust_abc.empty: st.plotly_chart(px.bar(cust_abc, x="ケース数", y="顧客名", orientation='h', title="主要顧客TOP15"), use_container_width=True)
