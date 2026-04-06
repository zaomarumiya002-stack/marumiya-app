import os
import io
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
from datetime import datetime, timedelta, date, time
import gspread
from google.oauth2.service_account import Credentials
import numpy as np

# ─────────────────────────────────────────────
# 0. 絶対安全な数値変換関数 ＆ 曜日フォーマット関数
# ─────────────────────────────────────────────
def to_int(v):
    """ SeriesエラーやNaNを完全に防ぎ、単一の整数を返す堅牢な関数 """
    try:
        if isinstance(v, pd.Series): v = v.sum()
        if pd.isna(v) or str(v).strip() == "": return 0
        return int(float(v))
    except: return 0

def format_date_jp(d):
    """ 日付に曜日を追加してフォーマットする関数 (例: 2026/04/06 (月)) """
    if pd.isna(d) or d == "": return ""
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    try:
        if isinstance(d, str): d = pd.to_datetime(d)
        return f"{d.strftime('%Y/%m/%d')} ({weekdays[d.weekday()]})"
    except: return str(d)

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
# 3. GSpread 同期ロジック & 自動シート・列作成
# ─────────────────────────────────────────────
@st.cache_resource
def get_client():
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

client = get_client()
sheet = client.open_by_url(st.secrets["spreadsheet_url"])

def load_data_from_cloud(name):
    cols_def = {
        "orders": ["ID","納品予定日","顧客名","大カテゴリ","製品名","ケース数","運送会社","備考","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考","不良廃棄フラグ","登録日時"],
        "manufactures": ["ID","製造予定日","大カテゴリ","製品名","ケース数","出来高数","賞味期限","担当者","品質チェック","品質コメント","リパックフラグ","備考","登録日時"],
        "master": ["大カテゴリ","製品名","初期在庫数","使用資材名","資材使用数","入数"],
        "customers": ["顧客名","ふりがな"],
        "packaging_master": ["資材名","品番","規格","仕入先","保管場所","単位","初期在庫","発注点"],
        "packaging_logs": ["ID","登録日","資材名","処理区分","数量","理由","備考","関連製品名","理論在庫","登録日時"],
        "shipping_master": ["運送会社名"],
        "employees_master": ["従業員名"],
        "labor_logs": ["ID","作業日","従業員名","終業時間","残業時間","作業内容","作業詳細","登録日時"]
    }
    target_cols = cols_def[name]
    
    try: ws = sheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=name, rows="1000", cols="30")
        if name == "shipping_master": ws.update(values=[target_cols, ["ヤマト運輸"], ["佐川急便"], ["自社配送"]], range_name="A1")
        elif name == "employees_master": ws.update(values=[target_cols, ["山田太郎"], ["鈴木一郎"]], range_name="A1")
        else: ws.update(values=[target_cols], range_name="A1")
    
    try:
        data = ws.get_all_values()
        if len(data) <= 1: return pd.DataFrame(columns=target_cols)
        df = pd.DataFrame(data[1:], columns=data[0])
        df.columns = df.columns.str.strip().str.replace(' ', '').str.replace('　', '')
        df = df.loc[:, ~df.columns.duplicated()]
        
        needs_update = False
        for c in target_cols:
            if c not in df.columns: 
                df[c] = ""
                needs_update = True
        if needs_update and len(df) > 0:
            try: ws.update(values=[df.columns.tolist()], range_name="A1")
            except: pass
            
        num_cols = ["ケース数", "初期在庫数", "資材使用数", "初期在庫", "発注点", "数量", "理論在庫", "入数", "出来高数", "残業時間"]
        for c in num_cols:
            if c in df.columns: 
                if c == "残業時間": df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(float)
                else: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).apply(to_int)
        
        date_cols = ["納品予定日", "製造予定日", "登録日", "登録日時", "賞味期限1", "賞味期限2", "賞味期限3", "賞味期限4", "賞味期限5", "賞味期限", "作業日"]
        for c in date_cols:
            if c in df.columns: df[c] = pd.to_datetime(df[c], errors='coerce')
            
        bool_cols = ["荷姿チェック", "不良廃棄フラグ", "リパックフラグ"]
        for c in bool_cols:
            if c in df.columns: df[c] = df[c].astype(str).str.upper() == "TRUE"
            
        return df[target_cols]
    except Exception: 
        return pd.DataFrame(columns=target_cols)

def save_and_sync(name, df):
    try: ws = sheet.worksheet(name)
    except: ws = sheet.add_worksheet(title=name, rows="1000", cols="30")
    ws.clear()
    df_save = df.copy()
    
    for col in df_save.columns:
        if pd.api.types.is_datetime64_any_dtype(df_save[col]): df_save[col] = df_save[col].dt.strftime('%Y-%m-%d %H:%M:%S').replace('NaT', '')
        elif pd.api.types.is_bool_dtype(df_save[col]): df_save[col] = df_save[col].astype(str).str.upper()
        elif col in ["残業時間"]: df_save[col] = df_save[col].fillna(0).astype(str)
        elif pd.api.types.is_numeric_dtype(df_save[col]): df_save[col] = df_save[col].fillna(0).apply(to_int).astype(str)
        else: df_save[col] = df_save[col].astype(str)
            
    df_save = df_save.fillna("").replace(["nan", "None", "NaT"], "")
    ws.update(values=[df_save.columns.values.tolist()] + df_save.values.tolist(), range_name='A1')
    st.cache_data.clear()
    st.session_state[f"{name}_df"] = load_data_from_cloud(name)

def append_and_sync(name, new_row_df):
    try: ws = sheet.worksheet(name)
    except: ws = sheet.add_worksheet(title=name, rows="1000", cols="30"); ws.append_row(new_row_df.columns.tolist())
    row_copy = new_row_df.copy()
    
    existing_cols = pd.DataFrame(ws.get("A1:Z1")).values[0].tolist() if len(ws.get("A1:Z1")) > 0 else []
    for c in row_copy.columns:
        if c not in existing_cols: existing_cols.append(c)
    for c in existing_cols:
        if c not in row_copy.columns: row_copy[c] = ""
    row_copy = row_copy[existing_cols]

    for col in row_copy.columns:
        if pd.api.types.is_datetime64_any_dtype(row_copy[col]): row_copy[col] = row_copy[col].dt.strftime('%Y-%m-%d %H:%M:%S').replace('NaT', '')
        elif pd.api.types.is_bool_dtype(row_copy[col]): row_copy[col] = row_copy[col].astype(str).str.upper()
            
    row_to_send = row_copy.fillna("").astype(str).replace(["nan", "None", "NaT"], "").values[0].tolist()
    ws.append_row(row_to_send)
    st.cache_data.clear()
    st.session_state[f"{name}_df"] = pd.concat([st.session_state[f"{name}_df"], new_row_df], ignore_index=True)

# ─────────────────────────────────────────────
# セッション初期化
# ─────────────────────────────────────────────
sheet_names = ["orders", "manufactures", "master", "customers", "packaging_master", "packaging_logs", "shipping_master", "employees_master", "labor_logs"]
for sheet_name in sheet_names:
    if f"{sheet_name}_df" not in st.session_state: st.session_state[f"{sheet_name}_df"] = load_data_from_cloud(sheet_name)

if "current_page" not in st.session_state: st.session_state.current_page = "📋 受注登録"
if "m_last_date" not in st.session_state: st.session_state.m_last_date = date.today()
if "m_last_exp" not in st.session_state: st.session_state.m_last_exp = date.today() + timedelta(days=7)
if "m_last_worker" not in st.session_state: st.session_state.m_last_worker = None

orders_df = st.session_state.orders_df
manus_df = st.session_state.manufactures_df
master_df = st.session_state.master_df
cust_df = st.session_state.customers_df
pack_mst_df = st.session_state.packaging_master_df
pack_log_df = st.session_state.packaging_logs_df
ship_mst_df = st.session_state.shipping_master_df
emp_mst_df = st.session_state.employees_master_df
labor_df = st.session_state.labor_logs_df

CATEGORIES = ["🍝 つきこん", "🟫 平こん", "🍜 糸こん・しらたき", "🔺 三角こん", "🟤 玉こん", "🎲 ダイスこん", "🏷️ 短冊", "🇯🇵 国産", "🤲 ちぎりこん", "🏮 大黒屋", "🏭 かねこ", "❄️ 冷凍耐性", "📦 その他"]
def format_name(n): return f"⚫️ {n}" if "黒" in str(n) else f"⚪️ {n}" if "白" in str(n) else f"📦 {n}"

# ─────────────────────────────────────────────
# 4. 在庫計算エンジン (リパック適正化対応)
# ─────────────────────────────────────────────
today = pd.Timestamp.today().normalize()
dates = pd.date_range(today, today + timedelta(days=60))

current_stocks = {}
future_stocks = {}
master_df_unique = master_df.drop_duplicates(subset=["製品名"]) if not master_df.empty else pd.DataFrame(columns=["大カテゴリ","製品名","初期在庫数","使用資材名","資材使用数","入数"])

if not master_df_unique.empty:
    o_ev = orders_df[["納品予定日", "製品名", "ケース数", "不良廃棄フラグ"]].copy() if not orders_df.empty else pd.DataFrame(columns=["納品予定日", "製品名", "ケース数", "不良廃棄フラグ"])
    if not o_ev.empty:
        o_ev = o_ev.rename(columns={"納品予定日":"日付", "ケース数":"qty"})
        o_ev["qty"] = -pd.to_numeric(o_ev["qty"], errors='coerce').fillna(0).abs()
        
    m_ev = manus_df[["製造予定日", "製品名", "ケース数", "リパックフラグ"]].copy() if not manus_df.empty else pd.DataFrame(columns=["製造予定日", "製品名", "ケース数", "リパックフラグ"])
    if not m_ev.empty:
        m_ev = m_ev.rename(columns={"製造予定日":"日付", "ケース数":"qty"})
        m_ev["qty"] = pd.to_numeric(m_ev["qty"], errors='coerce').fillna(0).abs()
        
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

# --- 資材サマリ ---
pack_summary = {}
pack_mst_unique = pack_mst_df.drop_duplicates(subset=["資材名"]) if not pack_mst_df.empty else pd.DataFrame(columns=["資材名","品番","規格","仕入先","保管場所","単位","初期在庫","発注点"])

if not pack_mst_unique.empty:
    for _, r in pack_mst_unique.iterrows():
        pack_summary[r["資材名"]] = {
            "品番": str(r.get("品番", "")), "規格": str(r.get("規格", "")), "仕入先": str(r.get("仕入先", "")),
            "保管場所": str(r.get("保管場所", "")), "単位": str(r.get("単位", "")),
            "期首在庫": to_int(r.get("初期在庫", 0)), "発注点": to_int(r.get("発注点", 0)),
            "期間入庫累計": 0, "期間出庫消費": 0, "現在庫": 0
        }

if not pack_log_df.empty:
    for _, r in pack_log_df.iterrows():
        p_name, qty, p_type = r.get("資材名", ""), to_int(r.get("数量", 0)), str(r.get("処理区分", ""))
        if p_name in pack_summary:
            if "連動" in p_type: continue
            if "入庫" in p_type: pack_summary[p_name]["期間入庫累計"] += qty
            elif "出庫" in p_type: pack_summary[p_name]["期間出庫消費"] += qty

if not manus_df.empty and not master_df_unique.empty:
    master_pack_info = master_df_unique.set_index("製品名")[["使用資材名", "資材使用数"]].to_dict('index')
    for _, r in manus_df.iterrows():
        prod, qty, rem = str(r.get("製品名", "")), to_int(r.get("ケース数", 0)), str(r.get("備考", ""))
        if prod in master_pack_info and "【資材非連動】" not in rem:
            pack_name = master_pack_info[prod].get("使用資材名", "")
            pack_usage = to_int(master_pack_info[prod].get("資材使用数", 0))
            if pack_name and pack_usage > 0 and pack_name in pack_summary:
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
    menu_items = ["📋 受注登録", "🏭 製造・日報登録", "🚚 出荷・発送管理", "📦 資材・入出庫", "📑 登録一覧", "📊 在庫・スケジュール", "⚙️ マスタ・分析"]
    for item in menu_items:
        if st.button(item, key=f"menu_{item}", use_container_width=True, type="primary" if st.session_state.current_page == item else "secondary"):
            st.session_state.current_page = item; st.rerun()
page = st.session_state.current_page

# ─────────────────────────────────────────────
# 6. 画面描画
# ─────────────────────────────────────────────

# --- 📋 受注登録 ---
if page == "📋 受注登録":
    st.markdown('<div class="slim-header"><h1>📋 受注 登録</h1></div>', unsafe_allow_html=True)
    with st.container():
        c1, c2, c3 = st.columns([1, 2, 1])
        o_date = c1.date_input("📅 納品日", value=date.today() + timedelta(days=1))
        c_name = c2.selectbox("🏢 顧客名", options=sorted(cust_df["顧客名"].unique()) if not cust_df.empty else [], index=None, placeholder="検索...")
        qty = c3.number_input("📦 ケース数 (常に正の数)", min_value=1, step=1, format="%d", value=None)
        
        cat_full = st.pills("カテゴリ", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
        cat = cat_full.split(" ", 1)[1] if cat_full else CATEGORIES[0].split(" ", 1)[1]
        sc1, sc2 = st.columns([1.5, 2.5])
        search_p = sc1.text_input("🔍 製品検索", placeholder="名称の一部を入力...")
        prods = [p for p in master_df_unique["製品名"].tolist() if search_p in p] if search_p else (master_df_unique[master_df_unique["大カテゴリ"] == cat]["製品名"].tolist() if not master_df_unique.empty else [])
        prod = sc2.selectbox("確定製品", options=prods, index=None, placeholder="選択してください", format_func=format_name)
        
        r1, r2 = sc2.columns([1, 2])
        ship_list = ship_mst_df["運送会社名"].tolist() if not ship_mst_df.empty else []
        ship_comp = r1.selectbox("🚚 運送会社", options=ship_list, index=None, placeholder="未定")
        rem = r2.text_input("📝 備考")
        
        col_chk1, col_chk2 = sc2.columns(2)
        is_substitute = col_chk1.checkbox("🔄 代替品として送付")
        is_irregular = col_chk2.checkbox("⚠️ 水漏れ・イレギュラーによる在庫減 (不良廃棄)")
        
        st.write("---")

        # ★ 在庫不足の視覚的強調（赤字太文字）
        if prod and qty is not None and qty > 0:
            cur_stock = current_stocks.get(prod, 0)
            if cur_stock < qty:
                st.markdown(f"""
                <div style='background-color:#FEE2E2; padding:12px; border-radius:8px; border:1px solid #FCA5A5; color:#DC2626; font-size:16px;'>
                    🚨 <b>製品在庫が不足します！</b> （現在庫: <b>{cur_stock}</b> cs / <span style='font-size:1.1em; font-weight:900; color:#FF0000;'>不足分: -{qty - cur_stock} cs</span>）
                </div>
                """, unsafe_allow_html=True)
                st.write("")

        msg_slot_add = st.empty()
        if st.button("✅ 登録する", type="primary", use_container_width=True):
            if not prod or qty is None: msg_slot_add.error("⚠️ 【製品・ケース数】は必須です。")
            else:
                prefix = ""
                if is_substitute: prefix += "【代替品】"
                if is_irregular: prefix += "【不良廃棄】"
                
                new_row = pd.DataFrame([{
                    "ID": str(uuid.uuid4())[:6].upper(), "納品予定日": pd.to_datetime(o_date), "顧客名": c_name if c_name else "未指定",
                    "大カテゴリ": cat, "製品名": prod, "ケース数": to_int(qty), "運送会社": ship_comp if ship_comp else "", 
                    "備考": f"{prefix} {rem}".strip(), "荷姿チェック": False, "賞味期限1": "", "賞味期限2": "", "賞味期限3": "", "賞味期限4": "", "賞味期限5": "", "発送備考": "",
                    "不良廃棄フラグ": is_irregular, "登録日時": datetime.now()
                }])
                append_and_sync("orders", new_row)
                msg_slot_add.success(f"✨ 登録を完了しました: {prod} ({qty}cs)")

    # ★ 「簡単修正」機能の拡張（削除・編集の一元化＆拡大表示）
    st.markdown('<h2 style="font-size:18px; margin-top:30px;">✏️ 登録データのかんたん修正・削除</h2>', unsafe_allow_html=True)
    if not orders_df.empty:
        disp_orders = orders_df.sort_values("登録日時", ascending=False).copy()
        disp_orders["納品予定日(表示)"] = disp_orders["納品予定日"].apply(format_date_jp)
        disp_cols = ["ID", "納品予定日(表示)", "顧客名", "製品名", "ケース数", "運送会社", "備考", "不良廃棄フラグ"]
        
        # expanderを使って拡大画面での全体確認・一括編集・削除を実現
        with st.expander("📂 過去の全データを一括編集・削除（クリックで拡大展開）", expanded=True):
            st.info("💡 **操作方法:** セルをクリックして直接文字や数字を打ち変えることができます。左端のチェックボックスを選択してキーボードの「Delete」を押すと行（データ）の削除が可能です。")
            edited_all_o = st.data_editor(
                disp_orders[disp_cols], num_rows="dynamic", use_container_width=True, hide_index=True, 
                column_config={"ケース数": st.column_config.NumberColumn("ケース数", min_value=1, step=1, format="%d")}, 
                key="edit_all_o", height=400
            )
            msg_slot_all_o = st.empty()
            if st.button("💾 上記の変更（修正・削除）をすべて保存する", key="btn_edit_all_o"):
                # 表示用カラムを本来の日付型に戻して保存
                save_df = edited_all_o.copy()
                save_df["納品予定日"] = pd.to_datetime(save_df["納品予定日(表示)"].str.split(" ").str[0], errors="coerce")
                
                # 欠落している列（賞味期限など）を元のorders_dfからマージ（復元）
                merged_df = pd.merge(save_df, orders_df[["ID", "大カテゴリ", "荷姿チェック", "賞味期限1", "賞味期限2", "賞味期限3", "賞味期限4", "賞味期限5", "発送備考", "登録日時"]], on="ID", how="left")
                save_and_sync("orders", merged_df)
                msg_slot_all_o.success("✅ 全データの更新・削除を完了しました！")

# --- 🚚 出荷・発送管理 ---
elif page == "🚚 出荷・発送管理":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #047857 0%, #10B981 100%);"><h1>🚚 出荷・発送 消込管理</h1></div>', unsafe_allow_html=True)
    st.markdown("💡 その日の出荷予定に対して、**運送会社の変更**、**賞味期限（最大5つ）の記録**、**荷姿確認の消込（チェック）** が行えます。")
    
    target_date = st.date_input("📅 表示する納品予定日を選択", value=date.today())
    day_orders = orders_df[(orders_df["納品予定日"].dt.date == target_date) & (orders_df["不良廃棄フラグ"] == False)].copy()
    
    if day_orders.empty:
        st.info(f"{format_date_jp(target_date)} の出荷予定データはありません。")
    else:
        unprocessed = day_orders[day_orders["荷姿チェック"] == False]
        if not unprocessed.empty and target_date <= date.today():
            st.error(f"🚨 **本日の出荷漏れ（荷姿未チェック）が {len(unprocessed)} 件あります！**")

        edit_cols = ["ID", "顧客名", "製品名", "ケース数", "運送会社", "荷姿チェック", "賞味期限1", "賞味期限2", "賞味期限3", "賞味期限4", "賞味期限5", "発送備考"]
        disp_df = day_orders[edit_cols].copy()
        for c in ["賞味期限1", "賞味期限2", "賞味期限3", "賞味期限4", "賞味期限5"]:
            disp_df[c] = pd.to_datetime(disp_df[c], errors="coerce").dt.date
            
        def highlight_shipped(row):
            if str(row.get("荷姿チェック", False)).upper() == "TRUE": return ['background-color: #D1FAE5; color: #065F46; text-decoration: line-through;'] * len(row)
            return [''] * len(row)
            
        edited_ship = st.data_editor(
            disp_df.style.apply(highlight_shipped, axis=1),
            use_container_width=True, hide_index=True,
            column_config={
                "ID": None, "顧客名": st.column_config.TextColumn("顧客名", disabled=True), "製品名": st.column_config.TextColumn("製品名", disabled=True),
                "ケース数": st.column_config.NumberColumn("ケース数", disabled=True),
                "運送会社": st.column_config.SelectboxColumn("運送会社", options=ship_mst_df["運送会社名"].tolist() if not ship_mst_df.empty else []),
                "荷姿チェック": st.column_config.CheckboxColumn("✅ 荷姿", default=False),
                "賞味期限1": st.column_config.DateColumn("賞味1", format="YYYY-MM-DD"), "賞味期限2": st.column_config.DateColumn("賞味2", format="YYYY-MM-DD"),
                "賞味期限3": st.column_config.DateColumn("賞味3", format="YYYY-MM-DD"), "賞味期限4": st.column_config.DateColumn("賞味4", format="YYYY-MM-DD"),
                "賞味期限5": st.column_config.DateColumn("賞味5", format="YYYY-MM-DD"), "発送備考": st.column_config.TextColumn("発送備考")
            }, key="edit_shipping"
        )
        
        msg_slot_ship = st.empty()
        if st.button("💾 発送・消込データを保存", type="primary", use_container_width=True):
            updated_orders = orders_df.copy().astype(object)
            for idx, row in edited_ship.iterrows():
                row_mask = updated_orders["ID"] == row["ID"]
                if row_mask.any():
                    updated_orders.loc[row_mask, "運送会社"] = str(row.get("運送会社", ""))
                    updated_orders.loc[row_mask, "荷姿チェック"] = str(row.get("荷姿チェック", False)).upper()
                    for c in ["賞味期限1", "賞味期限2", "賞味期限3", "賞味期限4", "賞味期限5"]:
                        val = row.get(c)
                        updated_orders.loc[row_mask, c] = val.strftime("%Y-%m-%d") if pd.notnull(val) else ""
                    updated_orders.loc[row_mask, "発送備考"] = str(row.get("発送備考", ""))
            save_and_sync("orders", updated_orders)
            msg_slot_ship.success("✅ 発送・消込データを保存しました！")

# --- 🏭 製造・日報登録 ---
elif page == "🏭 製造・日報登録":
    st.markdown('<div class="slim-header header-manu"><h1>🏭 製造・リパック・日報登録</h1></div>', unsafe_allow_html=True)
    
    t_m1, t_m2, t_m3 = st.tabs(["🏭 製造・リパック登録", "👷 労務データ登録", "📄 生産日報出力"])
    
    with t_m1:
        with st.container():
            c1, c2, c3 = st.columns([1, 1, 1])
            m_date = c1.date_input("📅 製造日", value=st.session_state.m_last_date)
            m_exp = c2.date_input("📅 賞味期限", value=st.session_state.m_last_exp)
            emp_list = emp_mst_df["従業員名"].tolist() if not emp_mst_df.empty else []
            m_worker = c3.selectbox("👷 担当者", options=emp_list, index=emp_list.index(st.session_state.m_last_worker) if st.session_state.m_last_worker in emp_list else None)
            
            cat_full_m = st.pills("カテゴリ製造", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
            cat_m = cat_full_m.split(" ", 1)[1] if cat_full_m else CATEGORIES[0].split(" ", 1)[1]
            
            sc1_m, sc2_m, sc3_m = st.columns([1.5, 2.5, 1])
            search_p_m = sc1_m.text_input("🔍 製品名検索", placeholder="検索...", key="sm")
            prods_m = [p for p in master_df_unique["製品名"].tolist() if search_p_m in p] if search_p_m else (master_df_unique[master_df_unique["大カテゴリ"] == cat_m]["製品名"].tolist() if not master_df_unique.empty else [])
            prod_m = sc2_m.selectbox("確定製品", options=prods_m, index=None, format_func=format_name, key="selm")
            m_qty = sc3_m.number_input("📦 CS数 (箱数)", min_value=1, step=1, format="%d", value=None)
            
            dekidaka = 0
            if prod_m and m_qty:
                master_info = master_df_unique[master_df_unique["製品名"] == prod_m]
                irisuu = to_int(master_info["入数"].iloc[0]) if not master_info.empty else 0
                dekidaka = to_int(m_qty) * irisuu
                st.info(f"💡 **自動計算**: {prod_m} (入数: {irisuu}個) × {m_qty}CS = 出来高 **{dekidaka}** 個")
                
            q1, q2 = st.columns([1, 2])
            m_q_check = q1.radio("✅ 品質・梱包チェック", options=["異常なし", "異常あり"], horizontal=True)
            m_q_rem = q2.text_input("📝 品質コメント", value="印字状況・外装状況に異常なし" if m_q_check == "異常なし" else "")
            
            r1, r2 = st.columns(2)
            is_repack = r1.checkbox("🔄 リパック製造 (在庫加算)")
            is_pack_link = r2.checkbox("📦 同時に、紐づく段ボール(資材)の在庫も減らす", value=True)
            st.write("---")

            # ★ 製造時の資材不足アラート（赤字太文字）
            if prod_m and m_qty is not None and m_qty > 0:
                master_pack_info = master_df_unique.set_index("製品名")[["使用資材名", "資材使用数"]].to_dict('index')
                if prod_m in master_pack_info:
                    p_name = master_pack_info[prod_m].get("使用資材名", "")
                    p_usage = to_int(master_pack_info[prod_m].get("資材使用数", 0))
                    if p_name and p_usage > 0:
                        req_pack_qty = m_qty * p_usage
                        cur_pack_stock = pack_summary.get(p_name, {}).get("現在庫", 0)
                        if cur_pack_stock < req_pack_qty:
                            st.markdown(f"""
                            <div style='background-color:#FEE2E2; padding:12px; border-radius:8px; border:1px solid #FCA5A5; color:#DC2626; font-size:16px;'>
                                🚨 <b>資材({p_name})が不足します！</b> （現在庫: <b>{cur_pack_stock}</b> / <span style='font-size:1.1em; font-weight:900; color:#FF0000;'>不足分: -{req_pack_qty - cur_pack_stock}</span>）
                            </div>
                            """, unsafe_allow_html=True)
                            st.write("")

            msg_slot_m_add = st.empty()
            if st.button("➕ 製造データを記録する", type="primary", use_container_width=True):
                if not prod_m or m_qty is None or not m_worker: 
                    msg_slot_m_add.error("⚠️ 【製品】【CS数】【担当者】は必須です。")
                else:
                    st.session_state.m_last_date = m_date
                    st.session_state.m_last_exp = m_exp
                    st.session_state.m_last_worker = m_worker
                    
                    rem = "【資材非連動】" if not is_pack_link else ""
                    new_m_id = str(uuid.uuid4())[:6].upper()
                    new_row = pd.DataFrame([{
                        "ID": new_m_id, "製造予定日": pd.to_datetime(m_date), "大カテゴリ": cat_m, "製品名": prod_m, "ケース数": to_int(m_qty), 
                        "出来高数": dekidaka, "賞味期限": pd.to_datetime(m_exp), "担当者": m_worker, "品質チェック": m_q_check, "品質コメント": m_q_rem, 
                        "リパックフラグ": is_repack, "備考": rem, "登録日時": datetime.now()
                    }])
                    append_and_sync("manufactures", new_row)
                    
                    if is_pack_link and not master_df_unique.empty:
                        if prod_m in master_pack_info:
                            p_name = master_pack_info[prod_m].get("使用資材名", "")
                            p_usage = to_int(master_pack_info[prod_m].get("資材使用数", 0))
                            if p_name and p_usage > 0:
                                used_qty = to_int(m_qty) * p_usage
                                theory_stock = pack_summary.get(p_name, {}).get("現在庫", 0) - used_qty
                                new_pack_log = pd.DataFrame([{
                                    "ID": str(uuid.uuid4())[:6].upper(), "登録日": pd.to_datetime(m_date),
                                    "資材名": p_name, "処理区分": "製造連動", "数量": abs(used_qty), 
                                    "理由": f"製造ID:{new_m_id}", "関連製品名": prod_m, "理論在庫": theory_stock,
                                    "備考": "自動記録", "登録日時": datetime.now()
                                }])
                                append_and_sync("packaging_logs", new_pack_log)
                    
                    msg_slot_m_add.success(f"✨ 製造登録を完了しました: {prod_m}")

        # ★ 拡張版：かんたん修正（一括編集・削除）
        st.markdown('<h2 style="font-size:18px; margin-top:30px;">✏️ 登録データのかんたん修正・削除</h2>', unsafe_allow_html=True)
        if not manus_df.empty:
            disp_manus = manus_df.sort_values("登録日時", ascending=False).copy()
            disp_manus["製造予定日(表示)"] = disp_manus["製造予定日"].apply(format_date_jp)
            disp_cols = ["ID", "製造予定日(表示)", "製品名", "ケース数", "出来高数", "担当者", "品質チェック", "リパックフラグ"]
            
            with st.expander("📂 過去の全データを一括編集・削除（クリックで拡大展開）", expanded=True):
                st.info("💡 **操作方法:** セルをクリックして直接文字や数字を打ち変えることができます。左端のチェックボックスを選択してキーボードの「Delete」を押すと行（データ）の削除が可能です。")
                edited_all_m = st.data_editor(
                    disp_manus[disp_cols], num_rows="dynamic", use_container_width=True, hide_index=True, 
                    column_config={"ケース数": st.column_config.NumberColumn("CS数", step=1, format="%d"), "出来高数": st.column_config.NumberColumn("出来高", step=1, format="%d")}, 
                    key="edit_all_m", height=400
                )
                msg_slot_all_m = st.empty()
                if st.button("💾 上記の変更（修正・削除）をすべて保存する", key="btn_edit_all_m"):
                    save_df = edited_all_m.copy()
                    save_df["製造予定日"] = pd.to_datetime(save_df["製造予定日(表示)"].str.split(" ").str[0], errors="coerce")
                    merged_df = pd.merge(save_df, manus_df[["ID", "大カテゴリ", "賞味期限", "品質コメント", "備考", "登録日時"]], on="ID", how="left")
                    save_and_sync("manufactures", merged_df)
                    msg_slot_all_m.success("✅ 全データの更新・削除を完了しました！")

    with t_m2:
        st.markdown("### 👷 労務・作業内容の登録")
        l1, l2 = st.columns(2)
        l_date = l1.date_input("📅 作業日", value=date.today())
        emp_list = emp_mst_df["従業員名"].tolist() if not emp_mst_df.empty else []
        l_worker = l2.selectbox("👷 担当者 (労務)", options=emp_list, index=emp_list.index(st.session_state.m_last_worker) if st.session_state.m_last_worker in emp_list else None)
        
        t_l1, t_l2 = st.columns(2)
        l_end_time = t_l1.time_input("🕒 終業時間", value=time(17, 30))
        l_overtime = t_l2.number_input("⏱️ 残業時間 (H)", min_value=0.0, step=0.5, value=0.0)
        
        l_task = st.selectbox("📋 作業内容 (メイン)", options=["OKM", "プラント", "箱詰め", "バケット", "5S", "その他"])
        l_detail = st.text_input("📝 作業詳細・連絡事項")
        
        msg_slot_labor = st.empty()
        if st.button("✅ 労務データを記録する", type="primary", use_container_width=True):
            if not l_worker: msg_slot_labor.error("⚠️ 担当者を選択してください。")
            else:
                new_labor = pd.DataFrame([{
                    "ID": str(uuid.uuid4())[:6].upper(), "作業日": pd.to_datetime(l_date), "従業員名": l_worker,
                    "終業時間": l_end_time.strftime("%H:%M"), "残業時間": l_overtime, "作業内容": l_task, "作業詳細": l_detail, "登録日時": datetime.now()
                }])
                append_and_sync("labor_logs", new_labor)
                msg_slot_labor.success(f"✨ 労務データを登録しました: {l_worker}")
                
        if not labor_df.empty:
            st.markdown("#### 直近の労務記録")
            recent_l = labor_df.sort_values("登録日時", ascending=False).head(5).copy()
            recent_l["作業日(表示)"] = recent_l["作業日"].apply(format_date_jp)
            st.dataframe(recent_l[["作業日(表示)", "従業員名", "終業時間", "残業時間", "作業内容"]], hide_index=True, use_container_width=True)

    with t_m3:
        st.markdown("### 📄 生産日報の作成・出力")
        st.info("💡 指定した日付の「製造実績」と「労務実績」をまとめ、Excelファイルとしてダウンロードできます。")
        report_date = st.date_input("📅 日報の対象日を選択", value=date.today(), key="rep_date")
        
        target_m = manus_df[manus_df["製造予定日"].dt.date == report_date].copy() if not manus_df.empty else pd.DataFrame()
        target_l = labor_df[labor_df["作業日"].dt.date == report_date].copy() if not labor_df.empty else pd.DataFrame()
        
        st.write(f"**対象日の実績:** 製造 {len(target_m)} 件 / 労務 {len(target_l)} 件")
        
        if st.button("📥 生産日報 (Excel) をダウンロード", type="primary", use_container_width=True):
            if target_m.empty and target_l.empty:
                st.warning("対象日のデータがありません。")
            else:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    if not target_m.empty:
                        out_m = target_m[["製品名", "ケース数", "出来高数", "賞味期限", "担当者", "品質チェック", "品質コメント", "リパックフラグ", "備考"]].copy()
                        out_m["賞味期限"] = out_m["賞味期限"].dt.strftime("%Y/%m/%d")
                        out_m.to_excel(writer, sheet_name="製造実績", index=False)
                    else: pd.DataFrame({"メッセージ":["製造データなし"]}).to_excel(writer, sheet_name="製造実績", index=False)
                    
                    if not target_l.empty:
                        out_l = target_l[["従業員名", "終業時間", "残業時間", "作業内容", "作業詳細"]].copy()
                        out_l.to_excel(writer, sheet_name="労務実績", index=False)
                    else: pd.DataFrame({"メッセージ":["労務データなし"]}).to_excel(writer, sheet_name="労務実績", index=False)
                
                st.download_button(label="ここをクリックして保存", data=output.getvalue(), file_name=f"生産日報_{report_date}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

# --- 📦 資材管理 ---
elif page == "📦 資材・入出庫":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #B45309 0%, #D97706 100%);"><h1>📦 資材・段ボール入出庫</h1></div>', unsafe_allow_html=True)
    
    shortage_packs = [p_name for p_name, d in pack_summary.items() if d["現在庫"] < d["発注点"]]
    if shortage_packs:
        st.error(f"🚨 **要発注アラート（現在庫が発注点未満）:**\n\n" + "、".join(shortage_packs))
        st.write("---")

    t_p1, t_p2 = st.tabs(["📝 単体入出庫・棚卸・分析", "✏️ 履歴・かんたん修正 (拡大表示)"])

    with t_p1:
        st.markdown("### 📊 資材の在庫推移サマリ")
        if pack_mst_unique.empty: st.info("⚙️ マスタ管理から資材を登録してください。")
        else:
            df_pack = pd.DataFrame([{"資材名": k, **v} for k, v in pack_summary.items()])
            def highlight_pack(row):
                if to_int(row.get("現在庫",0)) < to_int(row.get("発注点",0)): return ['background-color: #FFEDD5; color: #C2410C; font-weight: bold;'] * len(row)
                return [''] * len(row)
            display_cols = ["資材名", "品番", "規格", "仕入先", "保管場所", "現在庫", "発注点", "状態", "単位"]
            st.dataframe(df_pack[display_cols].style.apply(highlight_pack, axis=1), use_container_width=True, hide_index=True)
            st.download_button("📥 サマリをCSV出力", data=df_pack.to_csv(index=False, encoding="utf-8-sig"), file_name=f"資材状況_{date.today()}.csv", use_container_width=True)

        st.write("---")
        st.markdown("### 📝 資材の単体入出庫・棚卸調整")
        p_date = st.date_input("📅 処理日", value=date.today())
        sc1, sc2 = st.columns([1.5, 2.5])
        search_pack = sc1.text_input("🔍 資材名検索", placeholder="検索...")
        filtered_packs = [p for p in pack_mst_unique["資材名"].tolist() if search_pack in p] if search_pack else pack_mst_unique["資材名"].tolist()
        sel_pack = sc2.selectbox("📦 対象資材", options=filtered_packs, index=None, placeholder="選択してください")
        
        p_type = st.radio("処理区分", options=["📥 入庫 (在庫を増やす)", "📤 出庫・廃棄 (在庫を減らす)", "📋 棚卸 (現在の実在庫を入力)"], horizontal=True)
        
        if "棚卸" in p_type:
            p_qty = st.number_input("現在の実在庫数 (正の数)", min_value=0, step=1, format="%d", value=None)
            reason_options = ["棚卸調整"]
        else:
            p_qty = st.number_input("処理する数量 (常に正の数で入力)", min_value=1, step=1, format="%d", value=None)
            reason_options = ["仕入（購入）", "返品受付", "その他入庫"] if "入庫" in p_type else ["破損・廃棄", "サンプル出荷", "その他出庫"]
            
        p_reason = st.selectbox("詳細な理由", options=reason_options)
        p_rem = st.text_input("📝 備考")
        
        msg_slot_p_add = st.empty()
        if st.button("➕ 資材ログを登録", type="primary", use_container_width=True):
            if not sel_pack or p_qty is None: 
                msg_slot_p_add.error("⚠️ 資材名と数量は必須です。")
            else:
                log_qty = to_int(p_qty)
                final_p_type = "入庫" if "入庫" in p_type else "出庫"
                if "棚卸" in p_type:
                    current_calc_stock = pack_summary[sel_pack]["現在庫"]
                    diff = log_qty - current_calc_stock
                    if diff >= 0: final_p_type, log_qty = "入庫", diff
                    else: final_p_type, log_qty = "出庫", abs(diff)
                
                if log_qty > 0: 
                    new_pack = pd.DataFrame([{
                        "ID": str(uuid.uuid4())[:6].upper(), "登録日": pd.to_datetime(p_date),
                        "資材名": sel_pack, "処理区分": final_p_type, "数量": log_qty, "理由": p_reason, 
                        "関連製品名": "", "理論在庫": "", "備考": p_rem, "登録日時": datetime.now()
                    }])
                    append_and_sync("packaging_logs", new_pack)
                    msg_slot_p_add.success(f"✨ 資材ログを登録しました: {sel_pack} ({final_p_type} {log_qty})")
                else: msg_slot_p_add.info("現在の計算在庫と一致しているため、調整は不要です。")

    with t_p3:
        # ★ 拡張版：資材ログの一括編集・削除
        st.markdown('### ✏️ 登録データのかんたん修正・削除')
        if not pack_log_df.empty:
            disp_pack = pack_log_df.sort_values("登録日時", ascending=False).copy()
            disp_pack["登録日(表示)"] = disp_pack["登録日"].apply(format_date_jp)
            
            with st.expander("📂 過去の全データを一括編集・削除（クリックで拡大展開）", expanded=True):
                st.info("💡 **操作方法:** セルをクリックして直接文字や数字を打ち変えられます。左端のチェックボックスを選択してキーボードの「Delete」を押すと行（データ）の削除が可能です。")
                edited_all_p = st.data_editor(
                    disp_pack[["ID", "登録日(表示)", "資材名", "処理区分", "数量", "理由", "関連製品名", "備考"]], 
                    num_rows="dynamic", use_container_width=True, hide_index=True, 
                    column_config={"登録日(表示)": st.column_config.TextColumn("登録日 (表示用)", disabled=True), "処理区分": st.column_config.SelectboxColumn("処理区分", options=["入庫", "出庫", "製造連動"]), "数量": st.column_config.NumberColumn("数量", min_value=1, step=1, format="%d")}, 
                    key="edit_all_p", height=500
                )
                msg_slot_all_p = st.empty()
                if st.button("💾 上記の変更（修正・削除）をすべて保存する", key="btn_edit_all_p"):
                    save_df = edited_all_p.copy()
                    save_df["登録日"] = pd.to_datetime(save_df["登録日(表示)"].str.split(" ").str[0], errors="coerce")
                    merged_df = pd.merge(save_df, pack_log_df[["ID", "理論在庫", "登録日時"]], on="ID", how="left")
                    save_and_sync("packaging_logs", merged_df)
                    msg_slot_all_p.success("✅ 全データの更新・削除を完了しました！")

# --- 📑 登録一覧 ---
elif page == "📑 登録一覧":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #0F766E 0%, #14B8A6 100%);"><h1>📑 登録データ一覧・出力</h1></div>', unsafe_allow_html=True)
    t_list1, t_list2, t_list3 = st.tabs(["📋 受注・出荷データ", "🏭 製造・日報データ", "📦 資材利用ログ"])
    
    with t_list1:
        if orders_df.empty: st.info("登録データがありません。")
        else:
            edit_df = orders_df.sort_values("登録日時", ascending=False).copy()
            edit_df["納品予定日(表示)"] = edit_df["納品予定日"].apply(format_date_jp)
            cols = ["ID", "登録日時", "大カテゴリ", "顧客名", "納品予定日(表示)", "製品名", "ケース数", "運送会社", "備考", "荷姿チェック", "発送備考", "不良廃棄フラグ"]
            edit_df = edit_df[[c for c in cols if c in edit_df.columns]]
            
            def get_stock_status(row):
                try:
                    d_str = str(row["納品予定日(表示)"]).split(" ")[0]
                    d, p, qty = pd.Timestamp(d_str).normalize(), row["製品名"], to_int(row.get("ケース数", 0))
                    stock = future_stocks[p][d] if d >= today and p in future_stocks and d in future_stocks[p] else current_stocks.get(p, 0)
                    if qty < 0: return f"⤴️ 復帰 (+{-qty})"
                    elif stock < 0: return f"在庫不足 ({stock})"
                    else: return f"OK (+{stock})"
                except: return "不明"

            edit_df.insert(7, "在庫状況", edit_df.apply(get_stock_status, axis=1))

            def highlight_row(row):
                is_irregular = row.get("不良廃棄フラグ") == True or str(row.get("不良廃棄フラグ")).upper() == "TRUE"
                is_return = to_int(row.get("ケース数", 0)) < 0
                is_shortage = "不足" in str(row.get("在庫状況", ""))
                is_checked = row.get("荷姿チェック") == True or str(row.get("荷姿チェック")).upper() == "TRUE"
                
                if is_checked: return ['background-color: #D1FAE5; color: #065F46;'] * len(row)
                if is_return: return ['background-color: #DBEAFE; color: #1E3A8A; font-weight: bold;'] * len(row)
                if is_shortage and is_irregular: return ['background-color: #FEF08A; color: #DC2626; font-weight: bold;'] * len(row)
                if is_shortage: return ['background-color: #FEE2E2; color: #DC2626; font-weight: bold;'] * len(row)
                if is_irregular: return ['background-color: #FEF08A; color: #854D0E; font-weight: bold;'] * len(row)
                return [''] * len(row)

            st.download_button("📥 受注データをCSV出力", data=edit_df.to_csv(index=False, encoding="utf-8-sig"), file_name=f"受注一覧_{date.today()}.csv", use_container_width=True)
            st.markdown("""<div style="font-size:14px; margin-bottom:10px;">
                <b>🎨 色：</b> <span style="background-color:#FEE2E2; color:#DC2626; padding:2px 6px;">在庫不足（赤字）</span> / <span style="background-color:#FEF08A; color:#854D0E; padding:2px 6px;">不良廃棄（黄色）</span> / <span style="background-color:#DBEAFE; color:#1E3A8A; padding:2px 6px;">⤴️ 在庫復帰（青色）</span> / <span style="background-color:#D1FAE5; color:#065F46; padding:2px 6px;">✅ 荷姿完了（緑色）</span>
            </div>""", unsafe_allow_html=True)
            
            st.dataframe(edit_df.style.apply(highlight_row, axis=1), use_container_width=True, hide_index=True, height=600)

    with t_list2:
        if manus_df.empty: st.info("製造データがありません。")
        else:
            m_df = manus_df.sort_values("登録日時", ascending=False).copy()
            m_df["製造予定日(表示)"] = m_df["製造予定日"].apply(format_date_jp)
            m_df["賞味期限"] = m_df["賞味期限"].dt.strftime("%Y/%m/%d")
            
            def highlight_repack(row):
                is_repack = row.get("リパックフラグ") == True or str(row.get("リパックフラグ")).upper() == "TRUE"
                if is_repack: return ['background-color: #DBEAFE; color: #1E3A8A; font-weight: bold;'] * len(row)
                return [''] * len(row)
                
            st.download_button("📥 製造データをCSV出力", data=m_df.to_csv(index=False, encoding="utf-8-sig"), file_name=f"製造一覧_{date.today()}.csv", use_container_width=True)
            st.markdown("""<div style="font-size:14px; margin-bottom:10px;">
                <b>🎨 色：</b> <span style="background-color:#DBEAFE; color:#1E3A8A; padding:2px 6px;">リパック製造（青色）</span>
            </div>""", unsafe_allow_html=True)
            st.dataframe(m_df[["ID", "製造予定日(表示)", "製品名", "ケース数", "出来高数", "賞味期限", "担当者", "品質チェック", "リパックフラグ", "備考"]].style.apply(highlight_repack, axis=1), use_container_width=True, hide_index=True, height=600)

    with t_list3:
        if pack_log_df.empty: st.info("資材ログがありません。")
        else:
            e_pack = pack_log_df.sort_values("登録日時", ascending=False).copy()
            e_pack["登録日(表示)"] = e_pack["登録日"].apply(format_date_jp)
            st.download_button("📥 資材ログをCSV出力", data=e_pack.to_csv(index=False, encoding="utf-8-sig"), file_name=f"資材ログ_{date.today()}.csv", use_container_width=True)
            st.dataframe(e_pack[["ID", "登録日(表示)", "資材名", "処理区分", "数量", "理由", "関連製品名", "備考"]], use_container_width=True, hide_index=True, height=600)

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
                for d in show_dates: row[format_date_jp(d)] = future_stocks.get(p, {}).get(d, curr_stock)
                inv_list.append(row)
            st.dataframe(pd.DataFrame(inv_list).sort_values("カテゴリ").style.map(lambda x: 'color: #dc2626; font-weight: bold; background-color: #fee2e2;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True, height=600)

    with t2:
        cal_data = []
        html = '<table class="sched-table"><tr><th style="width:120px;">日付</th><th style="width:40%;">製造 / リパック</th><th style="width:40%;">出荷 / 不良廃棄</th></tr>'
        for i in range(7):
            d = today + timedelta(days=i)
            
            m_h = ""
            for _, r in manus_df[manus_df["製造予定日"]==d].iterrows():
                p, qty = r["製品名"], to_int(r.get("ケース数", 0))
                is_repack = r.get("リパックフラグ") in [True, "TRUE"]
                if is_repack:
                    qty_html = f'<span style="color:#1E3A8A; font-weight:900;">{qty}cs (リパック)</span>'
                    bg_color, border_color = "#DBEAFE", "#1E3A8A"
                else:
                    qty_html = f'<span style="color:#059669; font-weight:900;">{qty}cs</span>'
                    bg_color, border_color = "#F0FFF4", "#10B981"
                m_h += f'<div style="background:{bg_color}; border-left:4px solid {border_color}; padding:6px; margin-bottom:4px; border-radius:4px;"><span style="font-weight:700;">{format_name(p)}</span> <span style="float:right;">{qty_html}</span></div>'
            
            o_h = ""
            for _, r in orders_df[orders_df["納品予定日"] == d].iterrows():
                p, qty = r["製品名"], to_int(r.get("ケース数", 0))
                stock_on_day = future_stocks.get(p, {}).get(d, 0)
                is_checked = r.get("荷姿チェック") in [True, "TRUE"]
                is_irregular = r.get("不良廃棄フラグ") in [True, "TRUE"]
                
                if is_checked: qty_html, bg_color, border_color = f'<span style="color:#065F46; font-weight:900; text-decoration:line-through;">{qty}cs</span>', "#D1FAE5", "#059669"
                elif is_irregular: qty_html, bg_color, border_color = f'<span style="color:#B45309; font-weight:900;">{qty}cs (不良)</span>', "#FEF3C7", "#D97706"
                elif qty < 0: qty_html, bg_color, border_color = f'<span style="color:#1E3A8A; font-weight:900;">⤴️ {-qty}cs 復帰</span>', "#DBEAFE", "#1E3A8A"
                elif stock_on_day < 0: qty_html, bg_color, border_color = f'<span style="color:#DC2626; font-weight:900;">{qty}cs (不足)</span>', "#FEE2E2", "#DC2626"
                else: qty_html, bg_color, border_color = f'<span style="color:#1D4ED8; font-weight:900;">{qty}cs</span>', "#F0F7FF", "#2563EB"
                o_h += f'<div style="background:{bg_color}; border-left:4px solid {border_color}; padding:6px; margin-bottom:4px; border-radius:4px;"><span style="font-weight:700;">{r["顧客名"]}: {format_name(p)}</span> <span style="float:right;">{qty_html}</span></div>'
            html += f'<tr><td><b>{format_date_jp(d)}</b></td><td>{m_h}</td><td>{o_h}</td></tr>'
            
            m_txt = "\n".join([f"製: {r['製品名']} ({to_int(r['ケース数'])}cs)" for _, r in manus_df[manus_df["製造予定日"]==d].iterrows()]) if not manus_df.empty else ""
            o_txt = "\n".join([f"出: {r['顧客名']} : {r['製品名']} ({to_int(r['ケース数'])}cs)" for _, r in orders_df[orders_df["納品予定日"]==d].iterrows()]) if not orders_df.empty else ""
            cal_data.append({"日付": format_date_jp(d), "製造": m_txt, "出荷": o_txt})
            
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
                    detail_list.append({"日付": format_date_jp(d), "製造 (入)": in_qty, "製造詳細": in_detail, "出荷 (出)": out_qty, "出荷詳細": out_detail, "予定在庫": temp_stock})
                
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
                cust_orders["納品予定日"] = cust_orders["納品予定日"].apply(format_date_jp)
                st.dataframe(cust_orders[["納品予定日", "製品名", "ケース数", "在庫状況", "備考"]].style.map(lambda v: 'color: #DC2626; font-weight: bold; background-color: #FEE2E2;' if "❌" in str(v) else '', subset=["在庫状況"]), use_container_width=True, hide_index=True)

# --- ⚙️ マスタ・分析 ---
elif page == "⚙️ マスタ・分析":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #475569 0%, #1E293B 100%);"><h1>⚙️ マスタ・データ分析</h1></div>', unsafe_allow_html=True)
    st.info("💡 ここでデータを追加・修正すると、アプリ全体の設定（ドロップダウン等）に即座に反映されます。表の下にある「＋」を押して行を追加できます。")
    
    t_m1, t_m2, t_m3, t_m4, t_m5, t_m6 = st.tabs(["📦 製品マスタ (資材紐付け)", "🏢 顧客マスタ", "📦 資材マスタ (段ボール等)", "🚚 運送会社マスタ", "👷 従業員マスタ", "📊 ABC分析"])
    
    with t_m1:
        st.markdown("### 製品カテゴリ・初期在庫・資材連動の編集")
        pack_names = pack_mst_unique["資材名"].tolist() if not pack_mst_unique.empty else []
        edited_master = st.data_editor(
            master_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={
                "大カテゴリ": st.column_config.SelectboxColumn("大カテゴリ", options=[c.split(" ", 1)[1] for c in CATEGORIES], required=True),
                "製品名": st.column_config.TextColumn("製品名", required=True),
                "初期在庫数": st.column_config.NumberColumn("初期在庫数", min_value=-9999, step=1, format="%d", default=0, required=True),
                "使用資材名": st.column_config.SelectboxColumn("使用資材名 (紐付け)", options=pack_names),
                "資材使用数": st.column_config.NumberColumn("1ケースあたりの資材数", min_value=0, step=1, format="%d", default=1),
                "入数": st.column_config.NumberColumn("1ケースの入数(出来高計算用)", min_value=1, step=1, format="%d", default=1)
            }, key="edit_master"
        )
        msg_slot_m_mst = st.empty()
        if st.button("💾 製品マスタを保存・同期", type="primary", use_container_width=True):
            save_and_sync("master", edited_master)
            msg_slot_m_mst.success("✅ 製品マスタを更新しました！")
            
    with t_m2:
        st.markdown("### 顧客リストの編集")
        edited_cust = st.data_editor(cust_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"顧客名": st.column_config.TextColumn("顧客名", required=True), "ふりがな": st.column_config.TextColumn("ふりがな")}, key="edit_cust")
        msg_slot_c_mst = st.empty()
        if st.button("💾 顧客マスタを保存・同期", type="primary", use_container_width=True):
            save_and_sync("customers", edited_cust)
            msg_slot_c_mst.success("✅ 顧客マスタを更新しました！")

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
                "初期在庫": st.column_config.NumberColumn("初期在庫", step=1, format="%d", default=0, required=True),
                "発注点": st.column_config.NumberColumn("発注点 (警告ライン)", step=1, format="%d", default=100)
            }, key="edit_pack_mst"
        )
        msg_slot_p_mst = st.empty()
        if st.button("💾 資材マスタを保存・同期", type="primary", use_container_width=True):
            save_and_sync("packaging_master", edited_pack)
            msg_slot_p_mst.success("✅ 資材マスタを更新しました！")

    with t_m4:
        st.markdown("### 運送会社リストの編集")
        edited_ship = st.data_editor(ship_mst_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"運送会社名": st.column_config.TextColumn("運送会社名", required=True)}, key="edit_ship_mst")
        msg_slot_s_mst = st.empty()
        if st.button("💾 運送会社マスタを保存・同期", type="primary", use_container_width=True):
            save_and_sync("shipping_master", edited_ship)
            msg_slot_s_mst.success("✅ 運送会社マスタを更新しました！")

    with t_m5:
        st.markdown("### 従業員（担当者）リストの編集")
        edited_emp = st.data_editor(emp_mst_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"従業員名": st.column_config.TextColumn("従業員名", required=True)}, key="edit_emp_mst")
        msg_slot_e_mst = st.empty()
        if st.button("💾 従業員マスタを保存・同期", type="primary", use_container_width=True):
            save_and_sync("employees_master", edited_emp)
            msg_slot_e_mst.success("✅ 従業員マスタを更新しました！")

    with t_m6:
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
