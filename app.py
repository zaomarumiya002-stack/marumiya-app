import os
os.environ["STREAMLIT_THEME_BASE"] = "light"
os.environ["STREAMLIT_THEME_PRIMARY_COLOR"] = "#2563EB"
os.environ["STREAMLIT_THEME_BACKGROUND_COLOR"] = "#F8FAFC"
os.environ["STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR"] = "#F1F5F9"
os.environ["STREAMLIT_THEME_TEXT_COLOR"] = "#0F172A"

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid
from datetime import datetime, timedelta, date
import gspread
from google.oauth2.service_account import Credentials
import numpy as np
import io

# ─────────────────────────────────────────────
# 0. ユーティリティ関数
# ─────────────────────────────────────────────
def to_int(v):
    try:
        if isinstance(v, pd.Series): v = v.sum()
        if pd.isna(v) or str(v).strip() == "": return 0
        return int(float(v))
    except: return 0

def format_date_jp(d):
    if pd.isna(d) or d == "": return ""
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    try:
        if isinstance(d, str): d = pd.to_datetime(d.split(" ")[0])
        return f"{d.strftime('%Y/%m/%d')} ({weekdays[d.weekday()]})"
    except: return str(d).split(" ")[0]

def is_special_order(rem):
    """備考に「特注」または「チャーター便」が含まれるか判定"""
    return "特注" in str(rem) or "チャーター便" in str(rem)

# ─────────────────────────────────────────────
# 1. ページ設定 & CSS
# ─────────────────────────────────────────────
st.set_page_config(page_title="丸実屋 統合管理システム", page_icon="🏭", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&display=swap');
    html, body, [data-testid="stAppViewContainer"] { font-family: 'Noto Sans JP', sans-serif !important; font-size: 16px !important; }
    p, span, label, div { color: #0F172A !important; }
    [data-testid="stSidebar"] { background-color: #F8FAFC !important; border-right: 1px solid #E2E8F0; }
    [data-testid="stSidebar"] .stButton > button { height: 48px !important; font-size: 15px !important; border-radius: 8px !important; font-weight: 600 !important; }
    .block-container { padding-top: 1rem !important; }
    .slim-header { background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%); padding: 12px 24px; border-radius: 10px; color: white !important; margin-bottom: 12px; }
    .slim-header h1 { color: white !important; margin: 0 !important; font-size: 20px !important; font-weight: 800 !important; }
    .header-manu { background: linear-gradient(135deg, #064E3B 0%, #10B981 100%); }

    /* ★ カテゴリPillsのアイコン・テキストを大きく */
    [data-testid="stPills"] button {
        padding: 18px 36px !important;
        font-size: 22px !important;
        font-weight: 900 !important;
        border-radius: 14px !important;
        border: 2px solid #CBD5E1 !important;
        margin: 8px !important;
        min-height: 64px !important;
        line-height: 1.4 !important;
    }
    [data-testid="stPills"] button[aria-selected="true"] {
        background-color: #2563EB !important;
        color: #FFFFFF !important;
        box-shadow: 0 6px 15px rgba(37,99,235,0.4) !important;
    }

    /* スケジュールテーブル */
    .sched-table { width:100%; border-collapse:collapse; background:white; font-size:15px; border-radius:10px; overflow:hidden; }
    .sched-table th { background:#F8FAFC; padding:10px; border-bottom:2px solid #E2E8F0; }
    .sched-table td { padding:10px; border-bottom:1px solid #F1F5F9; vertical-align:top; }

    /* ★ 欠品マイナス数 赤文字専用クラス */
    .shortage-red { color: #DC2626 !important; font-weight: 900 !important; font-size: 1.1em; }

    /* 出荷管理の発送ステータスカード */
    .ship-card { border-radius:10px; padding:12px 16px; margin-bottom:8px; border-left:5px solid #2563EB; background:#F0F7FF; }
    .ship-card.done { border-left-color:#059669; background:#D1FAE5; }
    .ship-card.shortage { border-left-color:#DC2626; background:#FEE2E2; }
    .ship-card.irregular { border-left-color:#D97706; background:#FEF3C7; }

    /* 特注バッジ */
    .badge-special { background:#7C3AED; color:white !important; padding:2px 8px; border-radius:12px; font-size:12px; font-weight:700; margin-left:6px; }
    .badge-charter { background:#0891B2; color:white !important; padding:2px 8px; border-radius:12px; font-size:12px; font-weight:700; margin-left:6px; }

    /* KPIカード */
    .kpi-card { background:white; border-radius:12px; padding:16px 20px; box-shadow:0 2px 8px rgba(0,0,0,0.08); border-top:4px solid #2563EB; }
    .kpi-value { font-size:28px; font-weight:900; color:#1E3A8A; }
    .kpi-label { font-size:13px; color:#64748B; margin-top:4px; }
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
# 3. GSpread 同期ロジック
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
        "manufactures": ["ID","製造予定日","大カテゴリ","製品名","ケース数","リパックフラグ","備考","登録日時"],
        "master": ["大カテゴリ","製品名","初期在庫数","使用資材名","資材使用数"],
        "customers": ["顧客名","ふりがな"],
        "packaging_master": ["資材名","品番","規格","仕入先","保管場所","単位","初期在庫","発注点"],
        "packaging_logs": ["ID","登録日","資材名","処理区分","数量","理由","備考","関連製品名","理論在庫","登録日時"],
        "shipping_master": ["運送会社名"],
        "special_schedule": ["ID","受注ID","製品名","顧客名","納品予定日","出荷予定日","備考","更新日時"]
    }
    target_cols = cols_def.get(name, [])
    if not target_cols: return pd.DataFrame()

    try: ws = sheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=name, rows="1000", cols="30")
        if name == "shipping_master": ws.update(values=[target_cols, ["ヤマト運輸"], ["佐川急便"], ["自社配送"]], range_name="A1")
        else: ws.update(values=[target_cols], range_name="A1")

    try:
        data = ws.get_all_values()
        if len(data) <= 1: return pd.DataFrame(columns=target_cols)
        df = pd.DataFrame(data[1:], columns=data[0])
        df.columns = df.columns.str.strip().str.replace(' ', '').str.replace('　', '')
        df = df.loc[:, ~df.columns.duplicated()]
        df = df.reindex(columns=target_cols, fill_value="")

        num_cols = ["ケース数","初期在庫数","資材使用数","初期在庫","発注点","数量","理論在庫"]
        for c in num_cols:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).apply(to_int)
        date_cols = ["納品予定日","製造予定日","登録日","登録日時","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","出荷予定日","更新日時"]
        for c in date_cols:
            if c in df.columns: df[c] = pd.to_datetime(df[c], errors='coerce')
        bool_cols = ["荷姿チェック","不良廃棄フラグ","リパックフラグ"]
        for c in bool_cols:
            if c in df.columns: df[c] = df[c].astype(str).str.upper() == "TRUE"
        return df[target_cols]
    except Exception: return pd.DataFrame(columns=target_cols)

def save_and_sync(name, df):
    try: ws = sheet.worksheet(name)
    except: ws = sheet.add_worksheet(title=name, rows="1000", cols="30")
    ws.clear()
    df_save = df.copy()
    for col in df_save.columns:
        if pd.api.types.is_datetime64_any_dtype(df_save[col]):
            df_save[col] = df_save[col].dt.strftime('%Y-%m-%d %H:%M:%S')
            df_save[col] = df_save[col].replace('NaT', '').fillna('')
        elif pd.api.types.is_bool_dtype(df_save[col]): df_save[col] = df_save[col].astype(str).str.upper()
        elif pd.api.types.is_numeric_dtype(df_save[col]): df_save[col] = df_save[col].fillna(0).apply(to_int).astype(str)
        else: df_save[col] = df_save[col].astype(str)
    df_save = df_save.fillna("").replace(["nan", "None", "NaT", "NaN"], "")
    ws.update(values=[df_save.columns.values.tolist()] + df_save.values.tolist(), range_name='A1')
    st.cache_data.clear()
    st.session_state[f"{name}_df"] = load_data_from_cloud(name)

def append_and_sync(name, new_row_df):
    try: ws = sheet.worksheet(name)
    except:
        ws = sheet.add_worksheet(title=name, rows="1000", cols="30")
        ws.append_row(new_row_df.columns.tolist())
    row_copy = new_row_df.copy()
    existing_cols = pd.DataFrame(ws.get("A1:Z1")).values[0].tolist() if len(ws.get("A1:Z1")) > 0 else []
    for c in row_copy.columns:
        if c not in existing_cols: existing_cols.append(c)
    for c in existing_cols:
        if c not in row_copy.columns: row_copy[c] = ""
    row_copy = row_copy[existing_cols]
    for col in row_copy.columns:
        if pd.api.types.is_datetime64_any_dtype(row_copy[col]):
            row_copy[col] = row_copy[col].dt.strftime('%Y-%m-%d %H:%M:%S')
            row_copy[col] = row_copy[col].replace('NaT', '').fillna('')
        elif pd.api.types.is_bool_dtype(row_copy[col]): row_copy[col] = row_copy[col].astype(str).str.upper()
    row_to_send = row_copy.fillna("").astype(str).replace(["nan", "None", "NaT", "NaN"], "").values[0].tolist()
    ws.append_row(row_to_send)
    st.cache_data.clear()
    st.session_state[f"{name}_df"] = pd.concat([st.session_state[f"{name}_df"], new_row_df], ignore_index=True)

# CSV出力ヘルパー（文字化け対策）
def make_csv_bytes(df):
    """BOM付きUTF-8でCSVバイト列を生成"""
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

# ─────────────────────────────────────────────
# セッション初期化
# ─────────────────────────────────────────────
sheet_names = ["orders","manufactures","master","customers","packaging_master","packaging_logs","shipping_master","special_schedule"]
for sheet_name in sheet_names:
    if f"{sheet_name}_df" not in st.session_state:
        st.session_state[f"{sheet_name}_df"] = load_data_from_cloud(sheet_name)
if "current_page" not in st.session_state: st.session_state.current_page = "📋 受注登録"

orders_df      = st.session_state.orders_df
manus_df       = st.session_state.manufactures_df
master_df      = st.session_state.master_df
cust_df        = st.session_state.customers_df
pack_mst_df    = st.session_state.packaging_master_df
pack_log_df    = st.session_state.packaging_logs_df
ship_mst_df    = st.session_state.shipping_master_df
special_df     = st.session_state.special_schedule_df

CATEGORIES = ["🍝 つきこん","🟫 平こん","🍜 糸こん・しらたき","🔺 三角こん","🟤 玉こん","🎲 ダイスこん","🏷️ 短冊","🇯🇵 国産","🤲 ちぎりこん","🏮 大黒屋","🏭 かねこ","🍱 ショクカイ","❄️ 冷凍耐性","📦 その他"]
def format_name(n): return f"⚫️ {n}" if "黒" in str(n) else f"⚪️ {n}" if "白" in str(n) else f"📦 {n}"

# ─────────────────────────────────────────────
# 4. 在庫計算エンジン
# ─────────────────────────────────────────────
today = pd.Timestamp.today().normalize()
dates = pd.date_range(today, today + timedelta(days=60))

current_stocks = {}
future_stocks  = {}
master_df_unique = master_df.drop_duplicates(subset=["製品名"]) if not master_df.empty else pd.DataFrame(columns=["大カテゴリ","製品名","初期在庫数","使用資材名","資材使用数"])

if not master_df_unique.empty:
    # 受注イベント（常に 日付/製品名/qty の列を持つ空DFで統一）
    _EMPTY_EV = pd.DataFrame(columns=["日付","製品名","qty"])
    if not orders_df.empty:
        o_ev = orders_df[["納品予定日","製品名","ケース数"]].copy()
        o_ev = o_ev.rename(columns={"納品予定日":"日付","ケース数":"qty"})
        o_ev["qty"] = -pd.to_numeric(o_ev["qty"], errors='coerce').fillna(0).abs()
    else:
        o_ev = _EMPTY_EV.copy()
    # 製造イベント
    if not manus_df.empty:
        m_ev = manus_df[["製造予定日","製品名","ケース数"]].copy()
        m_ev = m_ev.rename(columns={"製造予定日":"日付","ケース数":"qty"})
        m_ev["qty"] = pd.to_numeric(m_ev["qty"], errors='coerce').fillna(0).abs()
    else:
        m_ev = _EMPTY_EV.copy()
    all_ev = pd.concat([o_ev, m_ev], ignore_index=True)
    # 列が確実に存在する状態でdropna
    for _c in ["日付","製品名","qty"]:
        if _c not in all_ev.columns: all_ev[_c] = None
    all_ev = all_ev.dropna(subset=["製品名","日付"])
    all_ev["qty"] = all_ev["qty"].apply(to_int)
    past_ev  = all_ev[all_ev["日付"] < today].groupby("製品名")["qty"].sum()
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

# 資材推移
pack_summary = {}
pack_mst_unique = pack_mst_df.drop_duplicates(subset=["資材名"]) if not pack_mst_df.empty else pd.DataFrame(columns=["資材名","品番","規格","仕入先","保管場所","単位","初期在庫","発注点"])
if not pack_mst_unique.empty:
    for _, r in pack_mst_unique.iterrows():
        pack_summary[r["資材名"]] = {"品番": str(r.get("品番","")), "規格": str(r.get("規格","")), "仕入先": str(r.get("仕入先","")), "保管場所": str(r.get("保管場所","")), "単位": str(r.get("単位","")), "期首在庫": to_int(r.get("初期在庫",0)), "発注点": to_int(r.get("発注点",0)), "期間入庫累計": 0, "期間出庫消費": 0, "現在庫": 0}
if not pack_log_df.empty:
    for _, r in pack_log_df.iterrows():
        p_name, qty, p_type = r.get("資材名",""), to_int(r.get("数量",0)), str(r.get("処理区分",""))
        if p_name in pack_summary:
            if "連動" in p_type: continue
            if "入庫" in p_type: pack_summary[p_name]["期間入庫累計"] += qty
            elif "出庫" in p_type: pack_summary[p_name]["期間出庫消費"] += qty
if not manus_df.empty and not master_df_unique.empty:
    master_pack_info = master_df_unique.set_index("製品名")[["使用資材名","資材使用数"]].to_dict('index')
    for _, r in manus_df.iterrows():
        prod, qty, rem = str(r.get("製品名","")), to_int(r.get("ケース数",0)), str(r.get("備考",""))
        if prod in master_pack_info and "【資材非連動】" not in rem:
            pack_name = master_pack_info[prod].get("使用資材名","")
            pack_usage = to_int(master_pack_info[prod].get("資材使用数",0))
            if pack_name and pack_usage > 0 and pack_name in pack_summary:
                pack_summary[pack_name]["期間出庫消費"] += (qty * pack_usage)
for d in pack_summary.values():
    d["現在庫"] = d["期首在庫"] + d["期間入庫累計"] - d["期間出庫消費"]
    d["状態"] = "⚠️ 注意" if d["現在庫"] < d["発注点"] else "✅ 正常"

# ─────────────────────────────────────────────
# 5. サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<p style='font-size:20px; font-weight:900; color:#1E3A8A; margin-bottom:8px;'>🏭 丸実屋システム</p>", unsafe_allow_html=True)

    # KPIサマリをサイドバーに表示
    today_orders = orders_df[orders_df["納品予定日"].dt.date == date.today()] if not orders_df.empty else pd.DataFrame()
    shortage_count = sum(1 for p, fs in future_stocks.items() if any(v < 0 for v in list(fs.values())[:7]))
    st.markdown(f"""
    <div style="background:#EFF6FF; border-radius:8px; padding:10px 14px; margin-bottom:10px; font-size:13px;">
        📦 本日出荷: <b>{len(today_orders)}件</b> &nbsp;|&nbsp; ⚠️ 欠品予測: <b style="color:#DC2626;">{shortage_count}品目</b>
    </div>
    """, unsafe_allow_html=True)

    st.write("---")
    menu_items = ["📋 受注登録","🏭 製造登録","🚚 出荷・発送管理","📦 資材・入出庫","📑 登録一覧","📊 在庫・スケジュール","⭐ 特注・チャータースケジュール","📈 経営・分析ダッシュボード","⚙️ マスタ・分析"]
    for item in menu_items:
        if st.button(item, key=f"menu_{item}", use_container_width=True, type="primary" if st.session_state.current_page == item else "secondary"):
            st.session_state.current_page = item; st.rerun()

page = st.session_state.current_page

# ─────────────────────────────────────────────
# 6. 受注登録
# ─────────────────────────────────────────────
if page == "📋 受注登録":
    st.markdown('<div class="slim-header"><h1>📋 受注 登録</h1></div>', unsafe_allow_html=True)
    with st.container():
        c1, c2, c3 = st.columns([1, 2, 1])
        o_date = c1.date_input("📅 納品日", value=date.today() + timedelta(days=1))
        c_name = c2.selectbox("🏢 顧客名", options=sorted(cust_df["顧客名"].unique()) if not cust_df.empty else [], index=None, placeholder="検索...")
        qty = c3.number_input("📦 ケース数", min_value=1, step=1, format="%d", value=None)

        cat_full = st.pills("カテゴリ", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
        cat = cat_full.split(" ", 1)[1] if cat_full else CATEGORIES[0].split(" ", 1)[1]
        sc1, sc2 = st.columns([1.5, 2.5])
        search_p = sc1.text_input("🔍 製品検索", placeholder="名称の一部を入力...")
        prods = [p for p in master_df_unique["製品名"].tolist() if search_p in p] if search_p else (master_df_unique[master_df_unique["大カテゴリ"] == cat]["製品名"].tolist() if not master_df_unique.empty else [])
        prod = sc2.selectbox("確定製品", options=prods, index=None, placeholder="選択してください", format_func=format_name)

        r1, r2 = sc2.columns([1, 2])
        ship_list = ship_mst_df["運送会社名"].tolist() if not ship_mst_df.empty else []
        ship_comp = r1.selectbox("🚚 運送会社", options=ship_list, index=None, placeholder="未定")
        rem = r2.text_input("📝 備考（「特注」「チャーター便」と入力すると特注扱いになります）")

        col_chk1, col_chk2 = sc2.columns(2)
        is_substitute = col_chk1.checkbox("🔄 代替品として送付")
        is_irregular  = col_chk2.checkbox("⚠️ 水漏れ・不良廃棄")
        st.write("---")

        # 欠品チェック（マイナス数は赤文字）
        if prod and qty is not None and qty > 0:
            cur_stock = current_stocks.get(prod, 0)
            if cur_stock < qty:
                shortage_num = qty - cur_stock
                st.markdown(f"""
                <div style='background-color:#FEE2E2; padding:12px; border-radius:8px; border:1px solid #FCA5A5;'>
                    🚨 <b>製品在庫が不足します！</b>（現在庫: <b>{cur_stock}</b> cs）
                    &nbsp;／&nbsp; 不足分: <span class="shortage-red">-{shortage_num} cs</span>
                </div>
                """, unsafe_allow_html=True)
                st.write("")

        # 特注・チャーター便の自動認識表示
        if is_special_order(rem):
            kind = "特注" if "特注" in rem else "チャーター便"
            badge_cls = "badge-special" if kind == "特注" else "badge-charter"
            st.markdown(f"<span class='{badge_cls}'>⭐ {kind}として登録されます</span>", unsafe_allow_html=True)

        msg_slot_add = st.empty()
        if st.session_state.get("msg_order_add"):
            msg_slot_add.success(st.session_state.msg_order_add)
            st.session_state.msg_order_add = None

        if st.button("✅ 登録する", type="primary", use_container_width=True):
            if not prod or qty is None: msg_slot_add.error("⚠️ 【製品・ケース数】は必須です。")
            else:
                prefix = ""
                if is_substitute: prefix += "【代替品】"
                if is_irregular:  prefix += "【不良廃棄】"
                new_id = str(uuid.uuid4())[:6].upper()
                new_row = pd.DataFrame([{
                    "ID": new_id, "納品予定日": pd.to_datetime(o_date), "顧客名": c_name if c_name else "未指定",
                    "大カテゴリ": cat, "製品名": prod, "ケース数": to_int(qty), "運送会社": ship_comp if ship_comp else "",
                    "備考": f"{prefix} {rem}".strip(), "荷姿チェック": False,
                    "賞味期限1": "", "賞味期限2": "", "賞味期限3": "", "賞味期限4": "", "賞味期限5": "",
                    "発送備考": "", "不良廃棄フラグ": is_irregular, "登録日時": datetime.now()
                }])
                append_and_sync("orders", new_row)

                # 特注・チャーター便の場合はspecial_scheduleにも自動追加
                if is_special_order(rem):
                    new_sp = pd.DataFrame([{
                        "ID": str(uuid.uuid4())[:6].upper(), "受注ID": new_id,
                        "製品名": prod, "顧客名": c_name if c_name else "未指定",
                        "納品予定日": pd.to_datetime(o_date),
                        "出荷予定日": pd.to_datetime(o_date) - timedelta(days=1),
                        "備考": rem, "更新日時": datetime.now()
                    }])
                    append_and_sync("special_schedule", new_sp)

                st.session_state.msg_order_add = f"✨ 登録完了: {prod} ({qty}cs)"
                st.rerun()

    st.markdown('<h2 style="font-size:18px; margin-top:30px;">✏️ 直近データの修正・削除</h2>', unsafe_allow_html=True)
    if not orders_df.empty:
        disp_orders = orders_df.sort_values("登録日時", ascending=False).copy()
        disp_orders["納品予定日(表示)"] = disp_orders["納品予定日"].apply(format_date_jp)
        disp_cols = ["ID","納品予定日(表示)","顧客名","製品名","ケース数","運送会社","備考","不良廃棄フラグ"]
        recent = disp_orders.head(5).copy()
        edited = st.data_editor(
            recent[disp_cols], num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={"ケース数": st.column_config.NumberColumn("ケース数", min_value=1, step=1, format="%d"), "ID": None},
            key="edit_o"
        )
        msg_slot_edit = st.empty()
        if st.session_state.get("msg_order_edit"):
            msg_slot_edit.success(st.session_state.msg_order_edit); st.session_state.msg_order_edit = None
        if st.button("💾 直近データを修正・削除保存", key="btn_edit_o"):
            save_df = edited.copy()
            save_df["納品予定日"] = pd.to_datetime(save_df["納品予定日(表示)"].str.split(" ").str[0], errors="coerce")
            merged_df = pd.merge(save_df, orders_df[["ID","大カテゴリ","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考","登録日時"]], on="ID", how="left")
            updated_orders = pd.concat([orders_df[~orders_df["ID"].isin(recent["ID"])], merged_df], ignore_index=True)
            save_and_sync("orders", updated_orders)
            st.session_state.msg_order_edit = "✅ 受注データを修正しました"
            st.rerun()

        with st.expander("📂 全データ一括編集・削除（クリックで展開）", expanded=False):
            st.info("💡 セルをクリックで修正。左端チェックボックス→Deleteで行削除。")
            edited_all = st.data_editor(
                disp_orders[disp_cols], num_rows="dynamic", use_container_width=True, hide_index=True,
                column_config={"ケース数": st.column_config.NumberColumn("ケース数", min_value=1, step=1, format="%d"), "ID": None},
                key="edit_all_o", height=400
            )
            msg_slot_all = st.empty()
            if st.session_state.get("msg_order_all"):
                msg_slot_all.success(st.session_state.msg_order_all); st.session_state.msg_order_all = None
            if st.button("💾 全データを上書き保存", key="btn_edit_all_o"):
                save_df_all = edited_all.copy()
                save_df_all["納品予定日"] = pd.to_datetime(save_df_all["納品予定日(表示)"].str.split(" ").str[0], errors="coerce")
                merged_all = pd.merge(save_df_all, orders_df[["ID","大カテゴリ","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考","登録日時"]], on="ID", how="left")
                save_and_sync("orders", merged_all)
                st.session_state.msg_order_all = "✅ 全データの更新完了"
                st.rerun()

# ─────────────────────────────────────────────
# 出荷・発送管理（大幅改善版）
# ─────────────────────────────────────────────
elif page == "🚚 出荷・発送管理":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #047857 0%, #10B981 100%);"><h1>🚚 出荷・発送 消込管理</h1></div>', unsafe_allow_html=True)

    tab_ship1, tab_ship2, tab_ship3 = st.tabs(["📋 日次消込", "📅 週間出荷一覧", "📥 出荷CSV出力"])

    with tab_ship1:
        st.markdown("**運送会社の変更・賞味期限の記録・荷姿確認の消込** が行えます。")
        target_date = st.date_input("📅 対象日を選択", value=date.today(), key="ship_date")
        day_orders = orders_df[(orders_df["納品予定日"].dt.date == target_date) & (orders_df["不良廃棄フラグ"] == False)].copy() if not orders_df.empty else pd.DataFrame()

        if day_orders.empty:
            st.info(f"{format_date_jp(target_date)} の出荷予定はありません。")
        else:
            done = day_orders[day_orders["荷姿チェック"] == True]
            undone = day_orders[day_orders["荷姿チェック"] == False]

            col_k1, col_k2, col_k3 = st.columns(3)
            col_k1.metric("出荷件数", f"{len(day_orders)} 件")
            col_k2.metric("✅ 消込済", f"{len(done)} 件", delta=f"{len(done)} 完了")
            col_k3.metric("⏳ 未消込", f"{len(undone)} 件", delta=f"-{len(undone)} 残" if undone.empty is False else "0 残", delta_color="inverse")

            if not undone.empty and target_date <= date.today():
                st.error(f"🚨 **出荷漏れ（荷姿未チェック）が {len(undone)} 件あります！**")

            edit_cols = ["ID","顧客名","製品名","ケース数","運送会社","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考"]
            disp_df = day_orders[edit_cols].copy()
            for c in ["賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5"]:
                disp_df[c] = pd.to_datetime(disp_df[c], errors="coerce").dt.date

            def highlight_shipped(row):
                chk = str(row.get("荷姿チェック", False)).upper()
                if chk == "TRUE": return ['background-color:#D1FAE5; color:#065F46; text-decoration:line-through;'] * len(row)
                return [''] * len(row)

            edited_ship = st.data_editor(
                disp_df.style.apply(highlight_shipped, axis=1),
                use_container_width=True, hide_index=True,
                column_config={
                    "ID": None,
                    "顧客名": st.column_config.TextColumn("顧客名", disabled=True),
                    "製品名": st.column_config.TextColumn("製品名", disabled=True),
                    "ケース数": st.column_config.NumberColumn("ケース数", disabled=True),
                    "運送会社": st.column_config.SelectboxColumn("🚚 運送会社", options=ship_mst_df["運送会社名"].tolist() if not ship_mst_df.empty else []),
                    "荷姿チェック": st.column_config.CheckboxColumn("✅ 荷姿", default=False),
                    "賞味期限1": st.column_config.DateColumn("賞味1", format="YYYY-MM-DD"),
                    "賞味期限2": st.column_config.DateColumn("賞味2", format="YYYY-MM-DD"),
                    "賞味期限3": st.column_config.DateColumn("賞味3", format="YYYY-MM-DD"),
                    "賞味期限4": st.column_config.DateColumn("賞味4", format="YYYY-MM-DD"),
                    "賞味期限5": st.column_config.DateColumn("賞味5", format="YYYY-MM-DD"),
                    "発送備考": st.column_config.TextColumn("発送備考")
                }, key="edit_shipping"
            )

            msg_slot_ship = st.empty()
            if st.session_state.get("msg_ship_edit"):
                msg_slot_ship.success(st.session_state.msg_ship_edit); st.session_state.msg_ship_edit = None

            if st.button("💾 発送・消込データを保存", type="primary", use_container_width=True):
                updated_orders = orders_df.copy().astype(object)
                for idx, row in edited_ship.iterrows():
                    row_mask = updated_orders["ID"] == row["ID"]
                    if row_mask.any():
                        updated_orders.loc[row_mask, "運送会社"] = str(row.get("運送会社", ""))
                        updated_orders.loc[row_mask, "荷姿チェック"] = str(row.get("荷姿チェック", False)).upper()
                        for c in ["賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5"]:
                            val = row.get(c)
                            updated_orders.loc[row_mask, c] = val.strftime("%Y-%m-%d") if pd.notnull(val) and val else ""
                        updated_orders.loc[row_mask, "発送備考"] = str(row.get("発送備考", ""))
                save_and_sync("orders", updated_orders)
                st.session_state.msg_ship_edit = "✅ 発送・消込データを保存しました！"
                st.rerun()

    with tab_ship2:
        st.markdown("### 📅 週間出荷一覧（7日間）")
        start_wk = st.date_input("開始日", value=date.today(), key="wk_start")
        for i in range(7):
            d = pd.Timestamp(start_wk) + timedelta(days=i)
            wk_orders = orders_df[orders_df["納品予定日"].dt.date == d.date()] if not orders_df.empty else pd.DataFrame()
            if wk_orders.empty: continue
            done_cnt = len(wk_orders[wk_orders["荷姿チェック"] == True])
            label = f"**{format_date_jp(d)}**  ｜ {len(wk_orders)}件  ✅{done_cnt}件完了"
            with st.expander(label, expanded=(d.date() == date.today())):
                disp_wk = wk_orders[["顧客名","製品名","ケース数","運送会社","荷姿チェック","発送備考"]].copy()
                def hl_wk(row):
                    if row.get("荷姿チェック") == True: return ['background-color:#D1FAE5;'] * len(row)
                    return [''] * len(row)
                st.dataframe(disp_wk.style.apply(hl_wk, axis=1), use_container_width=True, hide_index=True)

    with tab_ship3:
        st.markdown("### 📥 出荷データCSV出力")
        col_e1, col_e2 = st.columns(2)
        exp_start = col_e1.date_input("出力開始日", value=date.today().replace(day=1), key="exp_s")
        exp_end   = col_e2.date_input("出力終了日", value=date.today(), key="exp_e")
        if not orders_df.empty:
            mask_exp = (orders_df["納品予定日"].dt.date >= exp_start) & (orders_df["納品予定日"].dt.date <= exp_end)
            exp_df = orders_df[mask_exp].copy()
            exp_df["納品予定日"] = exp_df["納品予定日"].apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "")
            for c in ["賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5"]:
                if c in exp_df.columns:
                    exp_df[c] = pd.to_datetime(exp_df[c], errors='coerce').apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "")
            exp_df["荷姿チェック"] = exp_df["荷姿チェック"].map({True:"済", False:"未", "TRUE":"済", "FALSE":"未"}).fillna("")
            out_cols = ["納品予定日","顧客名","製品名","ケース数","運送会社","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考","備考"]
            out_cols = [c for c in out_cols if c in exp_df.columns]
            st.metric("対象件数", f"{len(exp_df)} 件")
            st.download_button(
                "📥 出荷データをCSV出力（BOM付きUTF-8）",
                data=make_csv_bytes(exp_df[out_cols]),
                file_name=f"出荷データ_{exp_start}_{exp_end}.csv",
                mime="text/csv",
                type="primary", use_container_width=True
            )
        else:
            st.info("出荷データがありません。")

# ─────────────────────────────────────────────
# 製造登録
# ─────────────────────────────────────────────
elif page == "🏭 製造登録":
    st.markdown('<div class="slim-header header-manu"><h1>🏭 製造・リパック 登録</h1></div>', unsafe_allow_html=True)
    with st.container():
        col1, col2 = st.columns([1, 1])
        m_date = col1.date_input("📅 製造日", value=date.today())
        m_qty  = col2.number_input("📦 製造ケース数", min_value=1, step=1, format="%d", value=None)

        cat_full_m = st.pills("カテゴリ製造", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
        cat_m = cat_full_m.split(" ", 1)[1] if cat_full_m else CATEGORIES[0].split(" ", 1)[1]
        sc1_m, sc2_m = st.columns([1.5, 2.5])
        search_p_m = sc1_m.text_input("🔍 製品名検索", placeholder="検索...", key="sm")
        prods_m = [p for p in master_df_unique["製品名"].tolist() if search_p_m in p] if search_p_m else (master_df_unique[master_df_unique["大カテゴリ"] == cat_m]["製品名"].tolist() if not master_df_unique.empty else [])
        prod_m = sc2_m.selectbox("確定製品", options=prods_m, index=None, format_func=format_name, key="selm")
        m_rem = sc2_m.text_input("📝 備考（製造）")

        is_repack = st.checkbox("🔄 リパック製造（在庫加算）")
        is_pack_link = True
        if is_repack:
            is_pack_link = st.checkbox("📦 紐づく資材の在庫も同時に減らす", value=True)

        # 欠品数を赤文字で表示
        if prod_m and m_qty is not None:
            cur_stock = current_stocks.get(prod_m, 0)
            future_stock_after = cur_stock + to_int(m_qty)
            related_orders_soon = orders_df[(orders_df["製品名"] == prod_m) & (orders_df["納品予定日"] >= today) & (orders_df["納品予定日"] <= today + timedelta(days=14))]["ケース数"].sum() if not orders_df.empty else 0
            net_after = future_stock_after - to_int(related_orders_soon)
            if cur_stock <= 0:
                st.markdown(f"<div style='background:#FEE2E2; padding:10px; border-radius:8px;'>現在庫: <span class='shortage-red'>{cur_stock} cs</span>　→　製造後: <b>{future_stock_after} cs</b>（14日以内の出荷予定: {to_int(related_orders_soon)} cs）</div>", unsafe_allow_html=True)

        st.write("---")
        msg_slot_m_add = st.empty()
        if st.session_state.get("msg_manu_add"):
            msg_slot_m_add.success(st.session_state.msg_manu_add); st.session_state.msg_manu_add = None

        if st.button("➕ 製造データを記録する", type="primary", use_container_width=True):
            if not prod_m or m_qty is None:
                msg_slot_m_add.error("⚠️ 【製品・数量】は必須です。")
            else:
                rem_text = "【リパック】" if is_repack else ""
                if not is_pack_link: rem_text += " 【資材非連動】"
                rem_text = f"{rem_text} {m_rem}".strip()
                new_m_id = str(uuid.uuid4())[:6].upper()
                new_row = pd.DataFrame([{
                    "ID": new_m_id, "製造予定日": pd.to_datetime(m_date), "大カテゴリ": cat_m, "製品名": prod_m,
                    "ケース数": to_int(m_qty), "リパックフラグ": is_repack, "備考": rem_text, "登録日時": datetime.now()
                }])
                append_and_sync("manufactures", new_row)
                if is_pack_link and not master_df_unique.empty:
                    master_pack_info = master_df_unique.set_index("製品名")[["使用資材名","資材使用数"]].to_dict('index')
                    if prod_m in master_pack_info:
                        p_name = master_pack_info[prod_m].get("使用資材名","")
                        p_usage = to_int(master_pack_info[prod_m].get("資材使用数",0))
                        if p_name and p_usage > 0:
                            used_qty = to_int(m_qty) * p_usage
                            current_pack_stock = pack_summary.get(p_name, {}).get("現在庫", 0)
                            theory_stock = current_pack_stock - used_qty
                            new_pack_log = pd.DataFrame([{
                                "ID": str(uuid.uuid4())[:6].upper(), "登録日": pd.to_datetime(m_date),
                                "資材名": p_name, "処理区分": "製造連動", "数量": abs(used_qty),
                                "理由": f"製造ID:{new_m_id}", "関連製品名": prod_m, "理論在庫": theory_stock,
                                "備考": "自動記録", "登録日時": datetime.now()
                            }])
                            append_and_sync("packaging_logs", new_pack_log)
                st.session_state.msg_manu_add = f"✨ 製造登録完了: {prod_m}"
                st.rerun()

    st.markdown('<h2 style="font-size:18px; margin-top:30px;">✏️ 直近データの修正・削除</h2>', unsafe_allow_html=True)
    if not manus_df.empty:
        disp_manus = manus_df.sort_values("登録日時", ascending=False).copy()
        disp_manus["製造予定日(表示)"] = disp_manus["製造予定日"].apply(format_date_jp)
        disp_cols = ["ID","製造予定日(表示)","製品名","ケース数","リパックフラグ","備考"]
        recent_m = disp_manus.head(5).copy()
        edited_m = st.data_editor(recent_m[disp_cols], num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={"ケース数": st.column_config.NumberColumn("CS数", min_value=1, step=1, format="%d"), "ID": None}, key="edit_m")
        msg_slot_m_edit = st.empty()
        if st.session_state.get("msg_manu_edit"):
            msg_slot_m_edit.success(st.session_state.msg_manu_edit); st.session_state.msg_manu_edit = None
        if st.button("💾 直近データを修正・削除保存", key="smb"):
            save_df_m = edited_m.copy()
            save_df_m["製造予定日"] = pd.to_datetime(save_df_m["製造予定日(表示)"].str.split(" ").str[0], errors="coerce")
            merged_m = pd.merge(save_df_m, manus_df[["ID","大カテゴリ","登録日時"]], on="ID", how="left")
            save_and_sync("manufactures", pd.concat([manus_df[~manus_df["ID"].isin(recent_m["ID"])], merged_m], ignore_index=True))
            st.session_state.msg_manu_edit = "✅ 製造データの修正を保存しました"
            st.rerun()
        with st.expander("📂 全データ一括編集・削除"):
            edited_all_m = st.data_editor(disp_manus[disp_cols], num_rows="dynamic", use_container_width=True, hide_index=True,
                column_config={"ケース数": st.column_config.NumberColumn("CS数", min_value=1, step=1, format="%d"), "ID": None}, key="edit_all_m", height=400)
            msg_slot_m_all = st.empty()
            if st.session_state.get("msg_manu_all"):
                msg_slot_m_all.success(st.session_state.msg_manu_all); st.session_state.msg_manu_all = None
            if st.button("💾 全データを上書き保存", key="btn_edit_all_m"):
                save_df_all_m = edited_all_m.copy()
                save_df_all_m["製造予定日"] = pd.to_datetime(save_df_all_m["製造予定日(表示)"].str.split(" ").str[0], errors="coerce")
                merged_all_m = pd.merge(save_df_all_m, manus_df[["ID","大カテゴリ","登録日時"]], on="ID", how="left")
                save_and_sync("manufactures", merged_all_m)
                st.session_state.msg_manu_all = "✅ 全データの更新を完了しました"
                st.rerun()

# ─────────────────────────────────────────────
# 資材管理
# ─────────────────────────────────────────────
elif page == "📦 資材・入出庫":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #B45309 0%, #D97706 100%);"><h1>📦 資材・段ボール入出庫</h1></div>', unsafe_allow_html=True)
    shortage_packs = [p_name for p_name, d in pack_summary.items() if d["現在庫"] < d["発注点"]]
    if shortage_packs:
        st.error(f"🚨 **要発注アラート（現在庫が発注点未満）:**\n\n" + "、".join(shortage_packs))
        st.write("---")
    t_p1, t_p2, t_p3 = st.tabs(["📊 状況サマリ＆分析", "📝 単体入出庫・棚卸", "✏️ 履歴・かんたん修正"])
    with t_p1:
        st.markdown("### 📊 資材の在庫推移サマリ")
        if pack_mst_unique.empty: st.info("⚙️ マスタ管理から資材を登録してください。")
        else:
            df_pack = pd.DataFrame([{"資材名": k, **v} for k, v in pack_summary.items()])
            def highlight_pack(row):
                if to_int(row.get("現在庫",0)) < to_int(row.get("発注点",0)): return ['background-color:#FFEDD5; color:#C2410C; font-weight:bold;'] * len(row)
                return [''] * len(row)
            display_cols = ["資材名","品番","規格","仕入先","保管場所","現在庫","発注点","状態","単位"]
            st.dataframe(df_pack[display_cols].style.apply(highlight_pack, axis=1), use_container_width=True, hide_index=True)
            st.download_button("📥 サマリCSV出力", data=make_csv_bytes(df_pack), file_name=f"資材状況_{date.today()}.csv", use_container_width=True)
        st.write("---")
        st.markdown("### 📈 資材使用分析（期間指定）")
        col_d1, col_d2 = st.columns(2)
        start_d = col_d1.date_input("開始日", value=date.today().replace(day=1))
        end_d   = col_d2.date_input("終了日", value=date.today())
        if not manus_df.empty and not master_df_unique.empty:
            master_pack_info = master_df_unique.set_index("製品名")[["使用資材名","資材使用数"]].to_dict('index')
            mask = (manus_df["製造予定日"].dt.date >= start_d) & (manus_df["製造予定日"].dt.date <= end_d)
            period_manus = manus_df[mask].copy()
            analysis_data = []
            for _, r in period_manus.iterrows():
                prod, qty, rem = str(r.get("製品名","")), to_int(r.get("ケース数",0)), str(r.get("備考",""))
                if prod in master_pack_info and "【資材非連動】" not in rem:
                    p_name = master_pack_info[prod].get("使用資材名","")
                    p_usage = to_int(master_pack_info[prod].get("資材使用数",0))
                    if p_name and p_usage > 0:
                        analysis_data.append({"資材名": p_name, "製品名": prod, "使用総数": qty * p_usage})
            if analysis_data:
                df_analysis = pd.DataFrame(analysis_data)
                pivot_analysis = df_analysis.pivot_table(index="製品名", columns="資材名", values="使用総数", aggfunc="sum", fill_value=0)
                st.write("▼ 製品別・資材別の製造時消費実績")
                st.dataframe(pivot_analysis, use_container_width=True)
            else: st.info("指定期間内の実績はありません。")
        if not pack_log_df.empty:
            mask_log = (pack_log_df["登録日"].dt.date >= start_d) & (pack_log_df["登録日"].dt.date <= end_d)
            abnormal_logs = pack_log_df[mask_log & (pack_log_df["処理区分"].str.contains("出庫")) & (~pack_log_df["処理区分"].str.contains("連動"))]
            if not abnormal_logs.empty:
                st.write("▼ 異常消費・手動出庫履歴")
                st.dataframe(abnormal_logs[["登録日","資材名","数量","理由","備考"]], hide_index=True, use_container_width=True)
    with t_p2:
        st.markdown("### 📝 資材の単体入出庫・棚卸調整")
        p_date = st.date_input("📅 処理日", value=date.today())
        sc1, sc2 = st.columns([1.5, 2.5])
        search_pack = sc1.text_input("🔍 資材名検索", placeholder="検索...")
        filtered_packs = [p for p in pack_mst_unique["資材名"].tolist() if search_pack in p] if search_pack else pack_mst_unique["資材名"].tolist()
        sel_pack = sc2.selectbox("📦 対象資材", options=filtered_packs, index=None, placeholder="選択してください")
        p_type = st.radio("処理区分", options=["📥 入庫（在庫を増やす）","📤 出庫・廃棄（在庫を減らす）","📋 棚卸（実在庫を入力）"], horizontal=True)
        if "棚卸" in p_type:
            p_qty = st.number_input("現在の実在庫数（正の数）", min_value=0, step=1, format="%d", value=None)
            reason_options = ["棚卸調整"]
        else:
            p_qty = st.number_input("処理する数量（常に正の数で入力）", min_value=1, step=1, format="%d", value=None)
            reason_options = ["仕入（購入）","返品受付","その他入庫"] if "入庫" in p_type else ["破損・廃棄","サンプル出荷","その他出庫"]
        p_reason = st.selectbox("詳細な理由", options=reason_options)
        p_rem = st.text_input("📝 備考")
        msg_slot_p_add = st.empty()
        if st.session_state.get("msg_pack_add"):
            msg_slot_p_add.success(st.session_state.msg_pack_add); st.session_state.msg_pack_add = None
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
                    st.session_state.msg_pack_add = f"✨ 資材ログ登録: {sel_pack} ({final_p_type} {log_qty})"
                    st.rerun()
                else: msg_slot_p_add.info("現在の計算在庫と一致しているため調整不要です。")
    with t_p3:
        st.markdown("### ✏️ 登録データのかんたん修正・削除")
        if not pack_log_df.empty:
            disp_pack = pack_log_df.sort_values("登録日時", ascending=False).copy()
            disp_pack["登録日(表示)"] = disp_pack["登録日"].apply(format_date_jp)
            disp_cols = ["ID","登録日(表示)","資材名","処理区分","数量","理由","関連製品名","備考"]
            recent_p = disp_pack.head(5).copy()
            edited_p = st.data_editor(recent_p[disp_cols], num_rows="dynamic", use_container_width=True, hide_index=True,
                column_config={"登録日(表示)": st.column_config.TextColumn("登録日", disabled=True), "処理区分": st.column_config.SelectboxColumn("処理区分", options=["入庫","出庫","製造連動"]), "数量": st.column_config.NumberColumn("数量", min_value=1, step=1, format="%d"), "ID": None}, key="edit_p")
            msg_slot_p_edit = st.empty()
            if st.session_state.get("msg_pack_edit"):
                msg_slot_p_edit.success(st.session_state.msg_pack_edit); st.session_state.msg_pack_edit = None
            if st.button("💾 直近データを修正・削除保存", key="btn_edit_p"):
                save_df = edited_p.copy()
                save_df["登録日"] = pd.to_datetime(save_df["登録日(表示)"].str.split(" ").str[0], errors="coerce")
                merged_df = pd.merge(save_df, pack_log_df[["ID","理論在庫","登録日時"]], on="ID", how="left")
                save_and_sync("packaging_logs", pd.concat([pack_log_df[~pack_log_df["ID"].isin(recent_p["ID"])], merged_df], ignore_index=True))
                st.session_state.msg_pack_edit = "✅ 資材ログの修正を保存しました"
                st.rerun()
            with st.expander("📂 全データ一括編集・削除"):
                edited_all_p = st.data_editor(disp_pack[disp_cols], num_rows="dynamic", use_container_width=True, hide_index=True,
                    column_config={"登録日(表示)": st.column_config.TextColumn("登録日", disabled=True), "処理区分": st.column_config.SelectboxColumn("処理区分", options=["入庫","出庫","製造連動"]), "数量": st.column_config.NumberColumn("数量", min_value=1, step=1, format="%d"), "ID": None}, key="edit_all_p", height=500)
                msg_slot_all_p = st.empty()
                if st.session_state.get("msg_pack_all"):
                    msg_slot_all_p.success(st.session_state.msg_pack_all); st.session_state.msg_pack_all = None
                if st.button("💾 全データを上書き保存", key="btn_edit_all_p"):
                    save_df_all = edited_all_p.copy()
                    save_df_all["登録日"] = pd.to_datetime(save_df_all["登録日(表示)"].str.split(" ").str[0], errors="coerce")
                    merged_all = pd.merge(save_df_all, pack_log_df[["ID","理論在庫","登録日時"]], on="ID", how="left")
                    save_and_sync("packaging_logs", merged_all)
                    st.session_state.msg_pack_all = "✅ 全データの更新完了！"
                    st.rerun()

# ─────────────────────────────────────────────
# 登録一覧
# ─────────────────────────────────────────────
elif page == "📑 登録一覧":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #0F766E 0%, #14B8A6 100%);"><h1>📑 登録データ一覧・出力</h1></div>', unsafe_allow_html=True)
    t_list1, t_list2, t_list3 = st.tabs(["📋 受注・出荷データ", "🏭 製造データ", "📦 資材利用ログ"])
    with t_list1:
        if orders_df.empty: st.info("登録データがありません。")
        else:
            edit_df = orders_df.sort_values("登録日時", ascending=False).copy()
            edit_df["納品予定日(表示)"] = edit_df["納品予定日"].apply(format_date_jp)
            cols = ["ID","登録日時","大カテゴリ","顧客名","納品予定日(表示)","製品名","ケース数","運送会社","備考","荷姿チェック","発送備考","不良廃棄フラグ"]
            edit_df = edit_df[[c for c in cols if c in edit_df.columns]]
            def get_stock_status(row):
                try:
                    d_str = str(row["納品予定日(表示)"]).split(" ")[0]
                    d, p, qty = pd.Timestamp(d_str).normalize(), row["製品名"], to_int(row.get("ケース数",0))
                    stock = future_stocks[p][d] if d >= today and p in future_stocks and d in future_stocks[p] else current_stocks.get(p, 0)
                    if stock < 0: return f"在庫不足 ({stock})"
                    else: return f"OK (+{stock})"
                except: return "不明"
            edit_df.insert(7, "在庫状況", edit_df.apply(get_stock_status, axis=1))
            def highlight_row(row):
                is_irregular = row.get("不良廃棄フラグ") == True or str(row.get("不良廃棄フラグ")).upper() == "TRUE"
                is_shortage  = "不足" in str(row.get("在庫状況",""))
                is_checked   = row.get("荷姿チェック") == True or str(row.get("荷姿チェック")).upper() == "TRUE"
                if is_checked: return ['background-color:#D1FAE5; color:#065F46;'] * len(row)
                if is_shortage and is_irregular: return ['background-color:#FEF08A; color:#DC2626; font-weight:bold;'] * len(row)
                if is_shortage: return ['background-color:#FEE2E2; color:#DC2626; font-weight:bold;'] * len(row)
                if is_irregular: return ['background-color:#FEF08A; color:#854D0E; font-weight:bold;'] * len(row)
                return [''] * len(row)
            # CSV出力（文字化け対策：BOM付きUTF-8、日付整形）
            out_df = edit_df.drop(columns=["ID","在庫状況","不良廃棄フラグ","登録日時"], errors='ignore').copy()
            if "登録日時" in orders_df.columns:
                out_df2 = orders_df.sort_values("登録日時", ascending=False).copy()
                out_df2["納品予定日"] = out_df2["納品予定日"].apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "")
                for c in ["賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5"]:
                    if c in out_df2.columns:
                        out_df2[c] = pd.to_datetime(out_df2[c], errors='coerce').apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "")
                out_df2["荷姿チェック"] = out_df2["荷姿チェック"].map({True:"済", False:"未"}).fillna("")
                out_df2["不良廃棄フラグ"] = out_df2["不良廃棄フラグ"].map({True:"○", False:""}).fillna("")
                csv_cols = ["納品予定日","顧客名","大カテゴリ","製品名","ケース数","運送会社","備考","荷姿チェック","発送備考","不良廃棄フラグ"]
                csv_cols = [c for c in csv_cols if c in out_df2.columns]
                csv_data = make_csv_bytes(out_df2[csv_cols])
            else:
                csv_data = make_csv_bytes(out_df)
            st.download_button("📥 受注一覧をCSV出力", data=csv_data, file_name=f"受注一覧_{date.today()}.csv", mime="text/csv", use_container_width=True)
            st.markdown("""<div style="font-size:14px; margin-bottom:10px;">
                <b>🎨 色：</b>
                <span style="background-color:#FEE2E2; color:#DC2626; padding:2px 6px;">在庫不足（赤字）</span> /
                <span style="background-color:#FEF08A; color:#854D0E; padding:2px 6px;">不良廃棄（黄色）</span> /
                <span style="background-color:#D1FAE5; color:#065F46; padding:2px 6px;">✅ 荷姿完了（緑色）</span>
            </div>""", unsafe_allow_html=True)
            st.dataframe(edit_df.style.apply(highlight_row, axis=1), use_container_width=True, hide_index=True, height=600)
    with t_list2:
        if manus_df.empty: st.info("製造データがありません。")
        else:
            m_df = manus_df.sort_values("登録日時", ascending=False).copy()
            m_df["製造予定日(表示)"] = m_df["製造予定日"].apply(format_date_jp)
            def highlight_repack(row):
                if row.get("リパックフラグ") == True or str(row.get("リパックフラグ")).upper() == "TRUE":
                    return ['background-color:#DBEAFE; color:#1E3A8A; font-weight:bold;'] * len(row)
                return [''] * len(row)
            out_m = m_df.copy()
            out_m["製造予定日"] = out_m["製造予定日"].apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "")
            out_m["リパック"] = out_m["リパックフラグ"].map({True:"○", False:""}).fillna("")
            csv_m = make_csv_bytes(out_m[["製造予定日","製品名","ケース数","リパック","備考"]])
            st.download_button("📥 製造一覧をCSV出力", data=csv_m, file_name=f"製造一覧_{date.today()}.csv", mime="text/csv", use_container_width=True)
            st.dataframe(m_df[["ID","製造予定日(表示)","製品名","ケース数","リパックフラグ","備考"]].style.apply(highlight_repack, axis=1), use_container_width=True, hide_index=True, height=600)
    with t_list3:
        if pack_log_df.empty: st.info("資材ログがありません。")
        else:
            e_pack = pack_log_df.sort_values("登録日時", ascending=False).copy()
            e_pack["登録日(表示)"] = e_pack["登録日"].apply(format_date_jp)
            out_p = e_pack.copy()
            out_p["登録日"] = out_p["登録日"].apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "")
            csv_p = make_csv_bytes(out_p[["登録日","資材名","処理区分","数量","理由","関連製品名","備考"]])
            st.download_button("📥 資材ログをCSV出力", data=csv_p, file_name=f"資材ログ_{date.today()}.csv", mime="text/csv", use_container_width=True)
            st.dataframe(e_pack[["ID","登録日(表示)","資材名","処理区分","数量","理由","関連製品名","備考"]], use_container_width=True, hide_index=True, height=600)

# ─────────────────────────────────────────────
# 在庫・スケジュール
# ─────────────────────────────────────────────
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
            def style_stock(v):
                if isinstance(v, (int, float)) and v < 0:
                    return 'color:#DC2626; font-weight:bold; background-color:#FEE2E2;'
                return ''
            st.dataframe(pd.DataFrame(inv_list).sort_values("カテゴリ").style.map(style_stock), use_container_width=True, hide_index=True, height=600)
            # CSV出力
            inv_csv_df = pd.DataFrame(inv_list).sort_values("カテゴリ")
            st.download_button("📥 在庫予測CSVを出力", data=make_csv_bytes(inv_csv_df), file_name=f"在庫予測_{date.today()}.csv", mime="text/csv", use_container_width=True)
    with t2:
        cal_data = []
        html = '<table class="sched-table"><tr><th style="width:120px;">日付</th><th style="width:40%;">製造 / リパック</th><th style="width:40%;">出荷 / 不良廃棄</th></tr>'
        for i in range(7):
            d = today + timedelta(days=i)
            m_h = ""
            for _, r in manus_df[manus_df["製造予定日"] == d].iterrows() if not manus_df.empty else []:
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
            for _, r in orders_df[orders_df["納品予定日"] == d].iterrows() if not orders_df.empty else []:
                p, qty = r["製品名"], to_int(r.get("ケース数", 0))
                stock_on_day = future_stocks.get(p, {}).get(d, 0)
                is_checked  = r.get("荷姿チェック") in [True, "TRUE"]
                is_irregular= r.get("不良廃棄フラグ") in [True, "TRUE"]
                is_special  = is_special_order(str(r.get("備考","")))
                sp_badge = '<span style="background:#7C3AED;color:white;padding:1px 5px;border-radius:8px;font-size:11px;">特注</span>' if "特注" in str(r.get("備考","")) else '<span style="background:#0891B2;color:white;padding:1px 5px;border-radius:8px;font-size:11px;">チャーター</span>' if "チャーター便" in str(r.get("備考","")) else ""
                if is_checked: qty_html, bg_color, border_color = f'<span style="color:#065F46; font-weight:900; text-decoration:line-through;">{qty}cs</span>', "#D1FAE5", "#059669"
                elif is_irregular: qty_html, bg_color, border_color = f'<span style="color:#B45309; font-weight:900;">{qty}cs (不良)</span>', "#FEF3C7", "#D97706"
                elif stock_on_day < 0: qty_html, bg_color, border_color = f'<span style="color:#DC2626; font-weight:900;">{qty}cs (不足)</span>', "#FEE2E2", "#DC2626"
                else: qty_html, bg_color, border_color = f'<span style="color:#1D4ED8; font-weight:900;">{qty}cs</span>', "#F0F7FF", "#2563EB"
                o_h += f'<div style="background:{bg_color}; border-left:4px solid {border_color}; padding:6px; margin-bottom:4px; border-radius:4px;"><span style="font-weight:700;">{r["顧客名"]}: {format_name(p)}</span>{sp_badge} <span style="float:right;">{qty_html}</span></div>'
            html += f'<tr><td><b>{format_date_jp(d)}</b></td><td>{m_h}</td><td>{o_h}</td></tr>'
            m_txt = " / ".join([f"{r['製品名']}({to_int(r['ケース数'])}cs)" for _, r in (manus_df[manus_df["製造予定日"]==d].iterrows() if not manus_df.empty else [])]) if not manus_df.empty else ""
            o_txt = " / ".join([f"{r['顧客名']}:{r['製品名']}({to_int(r['ケース数'])}cs)" for _, r in (orders_df[orders_df["納品予定日"]==d].iterrows() if not orders_df.empty else [])]) if not orders_df.empty else ""
            cal_data.append({"日付": format_date_jp(d), "製造予定": m_txt, "出荷予定": o_txt})
        st.download_button("🖨️ カレンダーCSVを出力", data=make_csv_bytes(pd.DataFrame(cal_data)), file_name=f"カレンダー_{today.strftime('%Y%m%d')}.csv", type="primary", use_container_width=True)
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
                p_o_ev = orders_df[(orders_df["製品名"] == sel_prod) & (orders_df["納品予定日"] >= today)][["納品予定日","顧客名","ケース数"]] if not orders_df.empty else pd.DataFrame(columns=["納品予定日","顧客名","ケース数"])
                p_m_ev = manus_df[(manus_df["製品名"] == sel_prod) & (manus_df["製造予定日"] >= today)][["製造予定日","備考","ケース数"]] if not manus_df.empty else pd.DataFrame(columns=["製造予定日","備考","ケース数"])
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
                st.plotly_chart(fig.update_layout(hovermode="x unified", margin=dict(l=20,r=20,t=40,b=20)), use_container_width=True)
                # 欠品行は赤文字（shortage-red相当）
                def style_detail(v):
                    if isinstance(v, (int,float)) and v < 0:
                        return 'color:#DC2626; font-weight:bold; background-color:#FEE2E2;'
                    return ''
                st.dataframe(df_detail.style.map(style_detail, subset=["予定在庫"]), use_container_width=True, hide_index=True)
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
                def cust_stock_status(r):
                    stock = future_stocks.get(r['製品名'], {}).get(pd.Timestamp(r['納品予定日']).normalize(), 0)
                    if stock < 0:
                        return f"❌ 欠品 ({stock})"
                    return "✅ OK"
                cust_orders["在庫状況"] = cust_orders.apply(cust_stock_status, axis=1)
                cust_orders["納品予定日"] = cust_orders["納品予定日"].apply(format_date_jp)
                def hl_cust(v):
                    if "❌" in str(v): return 'color:#DC2626; font-weight:bold; background-color:#FEE2E2;'
                    return ''
                st.dataframe(cust_orders[["納品予定日","製品名","ケース数","在庫状況","備考"]].style.map(hl_cust, subset=["在庫状況"]), use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────
# ⭐ 特注・チャータースケジュール（新機能）
# ─────────────────────────────────────────────
elif page == "⭐ 特注・チャータースケジュール":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #5B21B6 0%, #8B5CF6 100%);"><h1>⭐ 特注・チャーター便 スケジュール管理</h1></div>', unsafe_allow_html=True)
    st.info("💡 備考に「特注」または「チャーター便」を含む受注が自動で表示されます。出荷予定日を編集・保存できます。")

    # 受注データから特注・チャーター便を抽出
    if not orders_df.empty:
        sp_orders = orders_df[orders_df["備考"].apply(is_special_order)].copy()
    else:
        sp_orders = pd.DataFrame()

    tab_sp1, tab_sp2, tab_sp3 = st.tabs(["📋 特注・チャーター便一覧", "📅 製品別 出荷日スケジュール", "✏️ スケジュール編集・保存"])

    with tab_sp1:
        if sp_orders.empty:
            st.info("特注・チャーター便の受注データがありません。\n受注登録の備考欄に「特注」または「チャーター便」と入力すると自動で表示されます。")
        else:
            # 種別バッジを付与
            def get_kind(rem):
                if "特注" in str(rem) and "チャーター便" in str(rem): return "特注+チャーター便"
                if "特注" in str(rem): return "特注"
                return "チャーター便"
            sp_orders["種別"] = sp_orders["備考"].apply(get_kind)
            sp_orders["納品予定日(表示)"] = sp_orders["納品予定日"].apply(format_date_jp)

            # special_scheduleの出荷予定日を紐付け
            if not special_df.empty:
                sp_merged = pd.merge(sp_orders, special_df[["受注ID","出荷予定日","備考"]].rename(columns={"備考":"出荷備考","受注ID":"ID"}), on="ID", how="left")
                sp_merged["出荷予定日"] = pd.to_datetime(sp_merged["出荷予定日"], errors='coerce').apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "（未設定）")
            else:
                sp_merged = sp_orders.copy()
                sp_merged["出荷予定日"] = "（未設定）"
                sp_merged["出荷備考"] = ""

            show_cols = ["種別","顧客名","納品予定日(表示)","出荷予定日","製品名","ケース数","備考"]
            show_cols = [c for c in show_cols if c in sp_merged.columns]

            def hl_sp(row):
                kind = str(row.get("種別",""))
                if "特注" in kind and "チャーター" in kind: return ['background-color:#F3E8FF; font-weight:bold;'] * len(row)
                if "特注" in kind: return ['background-color:#EDE9FE; font-weight:bold;'] * len(row)
                return ['background-color:#E0F2FE; font-weight:bold;'] * len(row)

            st.dataframe(sp_merged[show_cols].style.apply(hl_sp, axis=1), use_container_width=True, hide_index=True)
            st.metric("特注・チャーター件数（全期間）", f"{len(sp_merged)} 件")

    with tab_sp2:
        st.markdown("### 📅 製品別 出荷日スケジュール一覧")
        if sp_orders.empty:
            st.info("特注・チャーター便の受注データがありません。")
        else:
            prod_list_sp = sorted(sp_orders["製品名"].unique().tolist())
            sel_sp_prod = st.selectbox("製品を選択", options=["（全製品）"] + prod_list_sp, index=0, key="sel_sp_prod")

            if sel_sp_prod == "（全製品）":
                filtered_sp = sp_orders.copy()
            else:
                filtered_sp = sp_orders[sp_orders["製品名"] == sel_sp_prod].copy()

            filtered_sp = filtered_sp.sort_values("納品予定日")
            filtered_sp["納品予定日(表示)"] = filtered_sp["納品予定日"].apply(format_date_jp)

            # special_scheduleの出荷予定日を紐付け
            if not special_df.empty:
                sp_f_merged = pd.merge(filtered_sp, special_df[["受注ID","出荷予定日"]].rename(columns={"受注ID":"ID"}), on="ID", how="left")
                sp_f_merged["出荷予定日"] = pd.to_datetime(sp_f_merged["出荷予定日"], errors='coerce').apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "（未設定）")
            else:
                sp_f_merged = filtered_sp.copy()
                sp_f_merged["出荷予定日"] = "（未設定）"

            show_f = ["製品名","顧客名","納品予定日(表示)","出荷予定日","ケース数","備考"]
            show_f = [c for c in show_f if c in sp_f_merged.columns]
            st.dataframe(sp_f_merged[show_f], use_container_width=True, hide_index=True)

            # CSV出力
            csv_sp = sp_f_merged[show_f].copy()
            st.download_button("📥 特注スケジュールをCSV出力", data=make_csv_bytes(csv_sp), file_name=f"特注スケジュール_{date.today()}.csv", mime="text/csv", use_container_width=True)

    with tab_sp3:
        st.markdown("### ✏️ 出荷予定日の編集・保存")
        st.markdown("スプレッドシートの `special_schedule` シートと連動しています。出荷予定日・備考を編集して保存してください。")

        if sp_orders.empty:
            st.info("特注・チャーター便の受注データがありません。")
        else:
            # special_dfにない受注を自動補完
            existing_order_ids = special_df["受注ID"].tolist() if not special_df.empty else []
            new_sp_rows = []
            for _, r in sp_orders.iterrows():
                if r["ID"] not in existing_order_ids:
                    new_sp_rows.append({
                        "ID": str(uuid.uuid4())[:6].upper(),
                        "受注ID": r["ID"],
                        "製品名": r["製品名"],
                        "顧客名": r["顧客名"],
                        "納品予定日": r["納品予定日"],
                        "出荷予定日": r["納品予定日"] - timedelta(days=1) if pd.notnull(r["納品予定日"]) else None,
                        "備考": r.get("備考",""),
                        "更新日時": datetime.now()
                    })
            if new_sp_rows:
                new_sp_df = pd.DataFrame(new_sp_rows)
                special_df_work = pd.concat([special_df, new_sp_df], ignore_index=True)
            else:
                special_df_work = special_df.copy()

            # 表示用に受注情報をマージ
            sp_edit = pd.merge(
                special_df_work,
                orders_df[["ID","備考"]].rename(columns={"ID":"受注ID","備考":"受注備考"}),
                on="受注ID", how="left"
            )
            sp_edit["種別"] = sp_edit["受注備考"].apply(lambda x: "特注" if "特注" in str(x) else "チャーター便")
            sp_edit["納品予定日(表示)"] = pd.to_datetime(sp_edit["納品予定日"], errors='coerce').apply(format_date_jp)

            # 出荷予定日をdate型に
            sp_edit["出荷予定日_edit"] = pd.to_datetime(sp_edit["出荷予定日"], errors='coerce').dt.date

            edit_sp_cols = ["ID","種別","製品名","顧客名","納品予定日(表示)","出荷予定日_edit","備考"]
            edit_sp_cols = [c for c in edit_sp_cols if c in sp_edit.columns]

            edited_sp = st.data_editor(
                sp_edit[edit_sp_cols],
                use_container_width=True, hide_index=True,
                column_config={
                    "ID": None,
                    "種別": st.column_config.TextColumn("種別", disabled=True),
                    "製品名": st.column_config.TextColumn("製品名", disabled=True),
                    "顧客名": st.column_config.TextColumn("顧客名", disabled=True),
                    "納品予定日(表示)": st.column_config.TextColumn("納品予定日", disabled=True),
                    "出荷予定日_edit": st.column_config.DateColumn("📅 出荷予定日（編集可）", format="YYYY/MM/DD"),
                    "備考": st.column_config.TextColumn("備考（メモ）"),
                }, key="edit_sp_sched"
            )

            msg_slot_sp = st.empty()
            if st.session_state.get("msg_sp_save"):
                msg_slot_sp.success(st.session_state.msg_sp_save); st.session_state.msg_sp_save = None

            if st.button("💾 特注スケジュールを保存・同期", type="primary", use_container_width=True):
                save_sp = special_df_work.copy()
                for idx, row in edited_sp.iterrows():
                    id_val = sp_edit.iloc[idx]["ID"] if idx < len(sp_edit) else None
                    if id_val:
                        mask = save_sp["ID"] == id_val
                        new_date = row.get("出荷予定日_edit")
                        if new_date:
                            save_sp.loc[mask, "出荷予定日"] = pd.to_datetime(new_date)
                        save_sp.loc[mask, "備考"] = str(row.get("備考", ""))
                        save_sp.loc[mask, "更新日時"] = datetime.now()
                save_and_sync("special_schedule", save_sp)
                st.session_state.msg_sp_save = "✅ 特注スケジュールを保存しました！"
                st.rerun()

# ─────────────────────────────────────────────
# 📈 経営・分析ダッシュボード（新機能）
# ─────────────────────────────────────────────
elif page == "📈 経営・分析ダッシュボード":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #0C4A6E 0%, #0EA5E9 100%);"><h1>📈 経営・製造管理 ダッシュボード</h1></div>', unsafe_allow_html=True)

    tab_d1, tab_d2, tab_d3, tab_d4 = st.tabs(["🏠 経営サマリ", "📦 製品・ABC分析", "🏭 製造効率分析", "📅 月次トレンド"])

    with tab_d1:
        st.markdown("### 📊 経営 KPI サマリ")
        col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
        if not orders_df.empty:
            this_month = date.today().replace(day=1)
            orders_this_month = orders_df[(orders_df["納品予定日"].dt.date >= this_month) & (orders_df["不良廃棄フラグ"] == False)]
            total_cs_month = orders_this_month["ケース数"].apply(to_int).sum()
            total_cust_month = orders_this_month["顧客名"].nunique()
            irregular_this_month = orders_df[(orders_df["納品予定日"].dt.date >= this_month) & (orders_df["不良廃棄フラグ"] == True)]["ケース数"].apply(to_int).sum()
            checked_rate = int(len(orders_df[orders_df["荷姿チェック"] == True]) / max(len(orders_df), 1) * 100)
            col_kpi1.metric("今月 出荷総数", f"{total_cs_month:,} cs", delta=f"{total_cust_month} 顧客")
            col_kpi2.metric("今月 不良廃棄", f"{irregular_this_month:,} cs", delta_color="inverse")
            col_kpi3.metric("荷姿チェック率（全期間）", f"{checked_rate} %")
            shortage_prod = sum(1 for v in current_stocks.values() if v <= 0)
            col_kpi4.metric("現在 欠品品目数", f"{shortage_prod} 品目", delta_color="inverse")
        else:
            st.info("受注データがありません。")

        st.write("---")
        st.markdown("### 🚚 運送会社別 出荷構成")
        if not orders_df.empty:
            ship_stats = orders_df[orders_df["運送会社"].str.strip() != ""]["運送会社"].value_counts().reset_index()
            ship_stats.columns = ["運送会社", "件数"]
            if not ship_stats.empty:
                fig_ship = px.pie(ship_stats, names="運送会社", values="件数", title="運送会社別 出荷件数構成", hole=0.4)
                st.plotly_chart(fig_ship, use_container_width=True)

        st.markdown("### ⚠️ 欠品予測アラート一覧（7日以内）")
        alert_list = []
        for prod, fs in future_stocks.items():
            for d, v in fs.items():
                if d <= today + timedelta(days=7) and v < 0:
                    alert_list.append({"製品名": prod, "日付": format_date_jp(d), "予測在庫": v})
        if alert_list:
            df_alert = pd.DataFrame(alert_list).drop_duplicates()
            def hl_alert(v):
                if isinstance(v, (int,float)) and v < 0:
                    return 'color:#DC2626; font-weight:900; background-color:#FEE2E2;'
                return ''
            st.dataframe(df_alert.style.map(hl_alert, subset=["予測在庫"]), use_container_width=True, hide_index=True)
        else:
            st.success("✅ 7日以内の欠品予測はありません。")

    with tab_d2:
        st.markdown("### 📦 製品 ABC分析")
        if not orders_df.empty:
            o_stat = orders_df[orders_df["不良廃棄フラグ"] == False].copy()
            o_stat["ケース数"] = o_stat["ケース数"].apply(to_int)
            abc = o_stat.groupby("製品名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False)
            if abc["ケース数"].sum() > 0:
                abc["累計比率"] = abc["ケース数"].cumsum() / abc["ケース数"].sum() * 100
                abc["ランク"] = pd.cut(abc["累計比率"], bins=[0,70,90,100], labels=["A（主力）","B（中堅）","C（その他）"])
                fig_abc = px.bar(abc.head(20), x="製品名", y="ケース数", color="ランク",
                    color_discrete_map={"A（主力）":"#DC2626","B（中堅）":"#F59E0B","C（その他）":"#6B7280"},
                    title="製品ABC分析 TOP20", labels={"ケース数":"総出荷CS数"})
                fig_abc.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_abc, use_container_width=True)
                def hl_abc(v):
                    if "A" in str(v): return 'background-color:#FEE2E2; font-weight:900;'
                    if "B" in str(v): return 'background-color:#FEF3C7;'
                    return ''
                st.dataframe(abc.style.map(hl_abc, subset=["ランク"]), use_container_width=True, hide_index=True)

        st.write("---")
        st.markdown("### 🏢 顧客別 出荷量 TOP15")
        if not orders_df.empty:
            cust_abc = orders_df[orders_df["顧客名"] != "未指定"].groupby("顧客名")["ケース数"].apply(lambda x: x.apply(to_int).sum()).reset_index().sort_values("ケース数", ascending=False).head(15)
            if not cust_abc.empty:
                st.plotly_chart(px.bar(cust_abc, x="ケース数", y="顧客名", orientation='h', title="主要顧客 TOP15 出荷量", color="ケース数", color_continuous_scale="Blues"), use_container_width=True)

    with tab_d3:
        st.markdown("### 🏭 製造効率・実績分析")
        if not manus_df.empty:
            col_me1, col_me2 = st.columns(2)
            mf = date.today().replace(day=1)
            manu_this_month = manus_df[manus_df["製造予定日"].dt.date >= mf]
            total_manu_cs = manu_this_month["ケース数"].apply(to_int).sum()
            repack_cs = manu_this_month[manu_this_month["リパックフラグ"] == True]["ケース数"].apply(to_int).sum()
            col_me1.metric("今月 製造総数", f"{total_manu_cs:,} cs")
            col_me2.metric("今月 リパック", f"{repack_cs:,} cs", delta=f"製造比 {int(repack_cs/max(total_manu_cs,1)*100)}%")

            fig_manu = px.histogram(manus_df, x="製造予定日", y="ケース数", color="大カテゴリ", title="製造量推移（カテゴリ別）", barmode="stack")
            st.plotly_chart(fig_manu, use_container_width=True)

            # カテゴリ別製造比率
            cat_manu = manus_df.groupby("大カテゴリ")["ケース数"].apply(lambda x: x.apply(to_int).sum()).reset_index()
            if not cat_manu.empty:
                st.plotly_chart(px.pie(cat_manu, names="大カテゴリ", values="ケース数", title="カテゴリ別 製造比率", hole=0.4), use_container_width=True)
        else:
            st.info("製造データがありません。")

        st.write("---")
        st.markdown("### 📦 資材 消費ペース（発注判断）")
        if pack_summary:
            df_pack_stat = pd.DataFrame([{"資材名": k, "現在庫": v["現在庫"], "発注点": v["発注点"], "月間消費推計": v["期間出庫消費"], "状態": v["状態"]} for k, v in pack_summary.items()])
            def hl_pack_stat(row):
                if to_int(row.get("現在庫",0)) < to_int(row.get("発注点",0)):
                    return ['background-color:#FFEDD5; color:#C2410C; font-weight:bold;'] * len(row)
                return [''] * len(row)
            st.dataframe(df_pack_stat.style.apply(hl_pack_stat, axis=1), use_container_width=True, hide_index=True)

    with tab_d4:
        st.markdown("### 📅 月次 出荷トレンド")
        if not orders_df.empty:
            trend_df = orders_df[orders_df["不良廃棄フラグ"] == False].copy()
            trend_df["年月"] = trend_df["納品予定日"].dt.to_period("M").astype(str)
            monthly = trend_df.groupby(["年月","大カテゴリ"])["ケース数"].apply(lambda x: x.apply(to_int).sum()).reset_index()
            if not monthly.empty:
                fig_trend = px.bar(monthly, x="年月", y="ケース数", color="大カテゴリ", title="月次 カテゴリ別 出荷量推移", barmode="stack")
                st.plotly_chart(fig_trend, use_container_width=True)

            # 月次サマリ表
            monthly_sum = trend_df.groupby("年月").agg(出荷件数=("ID","count"), 総CS数=("ケース数", lambda x: x.apply(to_int).sum()), 顧客数=("顧客名","nunique")).reset_index()
            st.dataframe(monthly_sum, use_container_width=True, hide_index=True)
            st.download_button("📥 月次サマリCSV出力", data=make_csv_bytes(monthly_sum), file_name=f"月次サマリ_{date.today()}.csv", mime="text/csv", use_container_width=True)
        else:
            st.info("受注データがありません。")

# ─────────────────────────────────────────────
# ⚙️ マスタ・分析
# ─────────────────────────────────────────────
elif page == "⚙️ マスタ・分析":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #475569 0%, #1E293B 100%);"><h1>⚙️ マスタ・データ分析</h1></div>', unsafe_allow_html=True)
    st.info("💡 ここでデータを追加・修正すると、アプリ全体の設定（ドロップダウン等）に即座に反映されます。")
    t_m1, t_m2, t_m3, t_m4, t_m5 = st.tabs(["📦 製品マスタ","🏢 顧客マスタ","📦 資材マスタ","🚚 運送会社マスタ","📊 ABC分析"])
    with t_m1:
        st.markdown("### 製品カテゴリ・初期在庫・資材連動の編集")
        pack_names = pack_mst_unique["資材名"].tolist() if not pack_mst_unique.empty else []
        edited_master = st.data_editor(
            master_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={
                "大カテゴリ": st.column_config.SelectboxColumn("大カテゴリ", options=[c.split(" ", 1)[1] for c in CATEGORIES], required=True),
                "製品名": st.column_config.TextColumn("製品名", required=True),
                "初期在庫数": st.column_config.NumberColumn("初期在庫数", min_value=-9999, step=1, format="%d", default=0, required=True),
                "使用資材名": st.column_config.SelectboxColumn("使用資材名", options=pack_names),
                "資材使用数": st.column_config.NumberColumn("1ケースあたりの資材数", min_value=0, step=1, format="%d", default=1)
            }, key="edit_master"
        )
        msg_slot_m_mst = st.empty()
        if st.session_state.get("msg_mst_prod"):
            msg_slot_m_mst.success(st.session_state.msg_mst_prod); st.session_state.msg_mst_prod = None
        if st.button("💾 製品マスタを保存・同期", type="primary", use_container_width=True):
            save_and_sync("master", edited_master)
            st.session_state.msg_mst_prod = "✅ 製品マスタを更新しました！"
            st.rerun()
    with t_m2:
        st.markdown("### 顧客リストの編集")
        edited_cust = st.data_editor(cust_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"顧客名": st.column_config.TextColumn("顧客名", required=True), "ふりがな": st.column_config.TextColumn("ふりがな")}, key="edit_cust")
        msg_slot_c_mst = st.empty()
        if st.session_state.get("msg_mst_cust"):
            msg_slot_c_mst.success(st.session_state.msg_mst_cust); st.session_state.msg_mst_cust = None
        if st.button("💾 顧客マスタを保存・同期", type="primary", use_container_width=True):
            save_and_sync("customers", edited_cust)
            st.session_state.msg_mst_cust = "✅ 顧客マスタを更新しました！"
            st.rerun()
    with t_m3:
        st.markdown("### 資材マスタの編集")
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
                "発注点": st.column_config.NumberColumn("発注点", step=1, format="%d", default=100)
            }, key="edit_pack_mst"
        )
        msg_slot_p_mst = st.empty()
        if st.session_state.get("msg_mst_pack"):
            msg_slot_p_mst.success(st.session_state.msg_mst_pack); st.session_state.msg_mst_pack = None
        if st.button("💾 資材マスタを保存・同期", type="primary", use_container_width=True):
            save_and_sync("packaging_master", edited_pack)
            st.session_state.msg_mst_pack = "✅ 資材マスタを更新しました！"
            st.rerun()
    with t_m4:
        st.markdown("### 運送会社リストの編集")
        edited_ship_mst = st.data_editor(ship_mst_df.copy(), num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"運送会社名": st.column_config.TextColumn("運送会社名", required=True)}, key="edit_ship_mst")
        msg_slot_s_mst = st.empty()
        if st.session_state.get("msg_mst_ship"):
            msg_slot_s_mst.success(st.session_state.msg_mst_ship); st.session_state.msg_mst_ship = None
        if st.button("💾 運送会社マスタを保存・同期", type="primary", use_container_width=True):
            save_and_sync("shipping_master", edited_ship_mst)
            st.session_state.msg_mst_ship = "✅ 運送会社マスタを更新しました！"
            st.rerun()
    with t_m5:
        if not orders_df.empty:
            o_stat = orders_df[orders_df["不良廃棄フラグ"] == False].copy()
            o_stat["ケース数"] = o_stat["ケース数"].apply(to_int)
            abc = o_stat.groupby("製品名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False)
            if abc["ケース数"].sum() > 0:
                abc["累計比率"] = abc["ケース数"].cumsum() / abc["ケース数"].sum() * 100
                abc["ランク"] = pd.cut(abc["累計比率"], bins=[0,70,90,100], labels=["A (主力)","B (中堅)","C (その他)"])
                st.dataframe(abc.style.map(lambda v: 'background-color:#FEE2E2; font-weight:900;' if "A" in str(v) else '', subset=["ランク"]), use_container_width=True, hide_index=True)
                cust_abc = o_stat[o_stat["顧客名"] != "未指定"].groupby("顧客名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False).head(15)
                if not cust_abc.empty:
                    st.plotly_chart(px.bar(cust_abc, x="ケース数", y="顧客名", orientation='h', title="主要顧客 TOP15"), use_container_width=True)
