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

# ─────────────────────────────────────────────
# 共通関数
# ─────────────────────────────────────────────
def to_int(v):
    try:
        if isinstance(v, pd.Series): v = v.sum()
        if pd.isna(v) or str(v).strip() == "": return 0
        return int(float(v))
    except: return 0

def format_date_jp(d):
    if d is None: return ""
    try:
        if pd.isna(d) or d == "": return ""
    except: pass
    try:
        if isinstance(d, str): d = pd.to_datetime(d.split(" ")[0])
        return f"{d.strftime('%Y/%m/%d')} ({['月','火','水','木','金','土','日'][d.weekday()]})"
    except: return str(d).split(" ")[0]

def safe_dt_date(s):
    """日付列を date 型に安全変換。タイムゾーン・二重変換ずれを防ぐ"""
    try:
        converted = pd.to_datetime(s, errors='coerce')
        # タイムゾーン付きの場合はローカル時刻に変換してから date 取得
        if hasattr(converted, 'dt'):
            if converted.dt.tz is not None:
                converted = converted.dt.tz_convert(None)
            return converted.dt.normalize().dt.date
        return converted.date() if not pd.isna(converted) else None
    except Exception:
        return pd.Series([None] * len(s) if hasattr(s, '__len__') else [None])
def is_special_order(r): return "特注" in str(r) or "チャーター便" in str(r)
def make_csv_bytes(df): return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

# ─────────────────────────────────────────────
# ページ設定 & CSS
# ─────────────────────────────────────────────
st.set_page_config(page_title="丸実屋 統合管理", page_icon="🏭", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');
html, body, [data-testid="stAppViewContainer"] { font-family: 'Noto Sans JP', sans-serif !important; font-size: 15px !important; background: #F8FAFC !important; }
p, span, label, div { color: #0F172A !important; }
[data-testid="stSidebar"] { background: linear-gradient(180deg,#1E293B 0%,#0F172A 100%) !important; border-right: none !important; }
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label, [data-testid="stSidebar"] div { color: #CBD5E1 !important; }
[data-testid="stSidebar"] .stButton > button { height: 46px !important; font-size: 14px !important; border-radius: 8px !important; font-weight: 600 !important; background: rgba(255,255,255,0.07) !important; color: #E2E8F0 !important; border: 1px solid rgba(255,255,255,0.1) !important; transition: all .2s !important; }
[data-testid="stSidebar"] .stButton > button:hover { background: rgba(37,99,235,0.4) !important; border-color: #3B82F6 !important; color: #fff !important; }
[data-testid="stSidebar"] .stButton > button[kind="primary"] { background: #2563EB !important; color: #fff !important; border-color: #1D4ED8 !important; }
.page-header { padding: 14px 24px; border-radius: 12px; margin-bottom: 16px; background: linear-gradient(135deg,#1E3A8A 0%,#3B82F6 100%); }
.page-header h1 { color: white !important; margin: 0 !important; font-size: 19px !important; font-weight: 800 !important; }
[data-testid="stPills"] button { padding: 16px 30px !important; font-size: 20px !important; font-weight: 900 !important; border-radius: 12px !important; border: 2px solid #CBD5E1 !important; margin: 6px !important; min-height: 60px !important; line-height: 1.4 !important; transition: all .15s !important; }
[data-testid="stPills"] button[aria-selected="true"] { background: #2563EB !important; color: #fff !important; box-shadow: 0 4px 14px rgba(37,99,235,0.4) !important; border-color: #1D4ED8 !important; }
.info-card { background: white; border-radius: 12px; padding: 16px 20px; box-shadow: 0 1px 6px rgba(0,0,0,0.07); border-left: 5px solid #2563EB; margin-bottom: 10px; }
.info-card.green { border-left-color: #059669; } .info-card.red { border-left-color: #DC2626; } .info-card.yellow { border-left-color: #D97706; }
.sched-table { width:100%; border-collapse:collapse; background:white; font-size:14px; border-radius:10px; overflow:hidden; }
.sched-table th { background:#1E293B; color:white; padding:10px 12px; text-align:left; } .sched-table td { padding:9px 12px; border-bottom:1px solid #F1F5F9; vertical-align:top; }
.badge { display:inline-block; padding:2px 8px; border-radius:20px; font-size:11px; font-weight:700; }
.badge-special { background:#7C3AED; color:white !important; } .badge-charter { background:#0891B2; color:white !important; }
.shortage-red { color:#DC2626 !important; font-weight:900 !important; }
.drill-panel { background:#F0F7FF; border-radius:12px; padding:18px 20px; border:2px solid #BFDBFE; margin-top:12px; }
.task-card { background:white; border-radius:10px; padding:14px 16px; box-shadow:0 2px 8px rgba(0,0,0,0.08); border-left:5px solid #2563EB; margin-bottom:10px; }
.task-card.critical { border-left-color:#DC2626; background:#FFF5F5; } .task-card.warning { border-left-color:#D97706; background:#FFFBEB; } .task-card.ok { border-left-color:#059669; background:#F0FDF4; }
.section-title { font-size:15px; font-weight:800; color:#1E293B; border-left:4px solid #2563EB; padding-left:10px; margin:18px 0 10px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# ログイン処理
# ─────────────────────────────────────────────
if "password_correct" not in st.session_state: st.session_state.password_correct = False
if not st.session_state.password_correct:
    st.markdown("<div style='text-align:center;margin-top:60px;'><span style='font-size:72px;'>🏭</span><h2 style='color:#1E3A8A;'>丸実屋 受発注管理 ログイン</h2></div>", unsafe_allow_html=True)
    _, c, _ = st.columns([1, 2, 1])
    with c:
        pwd = st.text_input("パスワードを入力", type="password")
        if st.button("ログイン", use_container_width=True, type="primary"):
            if pwd == st.secrets["app_password"]: st.session_state.password_correct = True; st.rerun()
            else: st.error("❌ パスワードが違います")
    st.stop()

# ─────────────────────────────────────────────
# Google SpreadSheet連携
# ─────────────────────────────────────────────
@st.cache_resource
def get_client(): 
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

client = get_client(); sheet = client.open_by_url(st.secrets["spreadsheet_url"])

def load_data(name):
    c_def = {"orders":["ID","納品予定日","顧客名","大カテゴリ","製品名","ケース数","運送会社","備考","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考","不良廃棄フラグ","日付未定フラグ","登録日時"], "manufactures":["ID","製造予定日","大カテゴリ","製品名","ケース数","リパックフラグ","備考","登録日時"], "master":["大カテゴリ","製品名","初期在庫数","使用資材名","資材使用数","入数","単位区分","特注フラグ","チャーターフラグ","時間あたり生産量","歩留まり率","リードタイム時間","安全在庫数","段取りグループ"], "customers":["顧客名","ふりがな","帳合先","支店名"], "packaging_master":["資材名","品番","規格","仕入先","保管場所","単位","初期在庫","発注点","発注リードタイム"], "packaging_logs":["ID","登録日","資材名","処理区分","数量","理由","備考","関連製品名","理論在庫","登録日時"], "shipping_master":["運送会社名"], "special_schedule":["ID","受注ID","製品名","顧客名","納品予定日","出荷予定日","備考","更新日時"]}
    tc = c_def.get(name, [])
    if not tc: return pd.DataFrame()
    try: ws = sheet.worksheet(name)
    except:
        ws = sheet.add_worksheet(title=name, rows="1000", cols="30")
        ws.update(values=[tc,["ヤマト運輸"],["佐川急便"],["自社配送"]] if name=="shipping_master" else [tc], range_name="A1")
    try:
        data = ws.get_all_values()
        if len(data)<=1: return pd.DataFrame(columns=tc)
        df = pd.DataFrame(data[1:], columns=data[0])
        df.columns = df.columns.str.strip().str.replace(' ','').str.replace('　','')
        df = df.loc[:, ~df.columns.duplicated()].reindex(columns=tc, fill_value="")
        for c in ["ケース数","初期在庫数","資材使用数","初期在庫","発注点","数量","理論在庫"]:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).apply(to_int)
        for c in ["納品予定日","製造予定日","登録日","登録日時","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","出荷予定日","更新日時"]:
            if c in df.columns: df[c] = pd.to_datetime(df[c], errors='coerce')
        for c in ["荷姿チェック","不良廃棄フラグ","リパックフラグ","日付未定フラグ","特注フラグ","チャーターフラグ"]:
            if c in df.columns: df[c] = df[c].astype(str).str.upper() == "TRUE"
        return df[tc]
    except: return pd.DataFrame(columns=tc)

def save_sync(name, df):
    try: ws = sheet.worksheet(name)
    except: ws = sheet.add_worksheet(title=name, rows="1000", cols="30")
    ws.clear(); ds = df.copy()
    for col in ds.columns:
        if pd.api.types.is_datetime64_any_dtype(ds[col]): ds[col] = ds[col].dt.strftime('%Y-%m-%d %H:%M:%S').fillna('').replace('NaT','')
        elif pd.api.types.is_bool_dtype(ds[col]): ds[col] = ds[col].astype(str).str.upper()
        elif pd.api.types.is_numeric_dtype(ds[col]): ds[col] = ds[col].fillna(0).apply(to_int).astype(str)
        else: ds[col] = ds[col].astype(str)
    ws.update(values=[ds.columns.tolist()] + ds.fillna("").replace(["nan","None","NaT","NaN"],"").values.tolist(), range_name='A1')
    st.cache_data.clear(); st.session_state[f"{name}_df"] = load_data(name)

def app_sync(name, nr):
    try: ws = sheet.worksheet(name)
    except: ws = sheet.add_worksheet(title=name, rows="1000", cols="30"); ws.append_row(nr.columns.tolist())
    rc = nr.copy(); ec = pd.DataFrame(ws.get("A1:Z1")).values[0].tolist() if len(ws.get("A1:Z1"))>0 else []
    for c in rc.columns:
        if c not in ec: ec.append(c)
    rc = rc.reindex(columns=ec, fill_value="")
    for col in rc.columns:
        if pd.api.types.is_datetime64_any_dtype(rc[col]): rc[col] = rc[col].dt.strftime('%Y-%m-%d %H:%M:%S').fillna('').replace('NaT','')
        elif pd.api.types.is_bool_dtype(rc[col]): rc[col] = rc[col].astype(str).str.upper()
    ws.append_row(rc.fillna("").astype(str).replace(["nan","None","NaT","NaN"],"").values[0].tolist())
    st.cache_data.clear(); st.session_state[f"{name}_df"] = pd.concat([st.session_state[f"{name}_df"], nr], ignore_index=True)

# セッション初期化
for _s in ["orders","manufactures","master","customers","packaging_master","packaging_logs","shipping_master","special_schedule"]:
    if f"{_s}_df" not in st.session_state: st.session_state[f"{_s}_df"] = load_data(_s)
if "current_page" not in st.session_state: st.session_state.current_page = "📋 受注登録"
if "drill_product" not in st.session_state: st.session_state.drill_product = None
if "_flash" not in st.session_state: st.session_state._flash = None  # {"type":"success"|"error"|"info", "msg":"..."}

# フラッシュメッセージ（rerun後もボタン近くに表示）
def flash(type_, msg):
    st.session_state._flash = {"type": type_, "msg": msg}

def show_flash():
    """ページヘッダー直後（互換のため残すが何もしない）"""
    pass

def show_flash_inline(placeholder=None):
    """ボタン直下のプレースホルダーに表示して即消去"""
    f = st.session_state.get("_flash")
    if f:
        st.session_state._flash = None
        target = placeholder if placeholder else st
        if f["type"] == "success":
            target.success(f["msg"])
        elif f["type"] == "error":
            target.error(f["msg"])
        elif f["type"] == "warning":
            target.warning(f["msg"])
        else:
            target.info(f["msg"])

odf = st.session_state.orders_df; mdf = st.session_state.manufactures_df; mst = st.session_state.master_df; cdf = st.session_state.customers_df
pk_m = st.session_state.packaging_master_df; pk_l = st.session_state.packaging_logs_df; sh_m = st.session_state.shipping_master_df; sp_s = st.session_state.special_schedule_df

CATS = ["🍝 つきこん","🟫 平こん","🍜 糸こん・しらたき","🔺 三角こん","🟤 玉こん","🎲 ダイスこん","🏷️ 短冊","🇯🇵 国産","🤲 ちぎりこん","🏮 大黒屋","🏭 かねこ","🍱 ショクカイ","❄️ 冷凍耐性","📦 その他"]
SP_T = ["（なし）","⭐ 特注","🚌 チャーター便"]

def fn(n): return f"⚫️ {n}" if "黒" in str(n) else f"⚪️ {n}" if "白" in str(n) else f"📦 {n}"
def pui(pn):
    if mst.empty or not pn: return 1, "ケース"
    r = mst[mst["製品名"] == pn]
    if r.empty: return 1, "ケース"
    return max(1, to_int(r.iloc[0].get("入数", 1))), str(r.iloc[0].get("単位区分", "ケース")).strip() or "ケース"

def get_toriatsuki_list(): return sorted(cdf["帳合先" if "帳合先" in cdf.columns else "顧客名"].dropna().unique().tolist()) if not cdf.empty else []
def get_shiten_list(tori): return sorted(cdf[cdf["帳合先"] == tori]["支店名"].dropna().replace("","").unique().tolist()) if not cdf.empty and tori and "帳合先" in cdf.columns else []

today = pd.Timestamp.today().normalize(); dates = pd.date_range(today, today + timedelta(days=60))
cs = {}; fs = {}; mst_u = mst.drop_duplicates(subset=["製品名"]) if not mst.empty else pd.DataFrame(columns=["大カテゴリ","製品名","初期在庫数","使用資材名","資材使用数","入数","単位区分","時間あたり生産量","歩留まり率","リードタイム時間","安全在庫数","段取りグループ"])

# ─────────────────────────────────────────────
# 在庫計算・資材計算エンジン
# ─────────────────────────────────────────────
if not mst_u.empty:
    ev_o = odf[["納品予定日","製品名","ケース数"]].copy().rename(columns={"納品予定日":"日付","ケース数":"qty"}) if not odf.empty else pd.DataFrame(columns=["日付","製品名","qty"])
    if not ev_o.empty: ev_o["qty"] = -pd.to_numeric(ev_o["qty"], errors='coerce').fillna(0).abs()
    vm = mdf[~mdf["備考"].fillna("").str.contains("【在庫非反映】")] if not mdf.empty else pd.DataFrame()
    ev_m = vm[["製造予定日","製品名","ケース数"]].copy().rename(columns={"製造予定日":"日付","ケース数":"qty"}) if not vm.empty else pd.DataFrame(columns=["日付","製品名","qty"])
    if not ev_m.empty: ev_m["qty"] = pd.to_numeric(ev_m["qty"], errors='coerce').fillna(0).abs()
    ae = pd.concat([ev_o, ev_m], ignore_index=True).dropna(subset=["製品名","日付"]); ae["qty"] = ae["qty"].apply(to_int)
    pe = ae[ae["日付"] < today].groupby("製品名")["qty"].sum(); fe = ae[ae["日付"] >= today]
    piv = fe.pivot_table(index="製品名", columns="日付", values="qty", aggfunc="sum") if not fe.empty else pd.DataFrame()
    for _, r in mst_u.iterrows():
        p = r["製品名"]; c_s = to_int(r.get("初期在庫数",0)) + to_int(pe.get(p,0)); cs[p] = c_s
        pr = piv.loc[p] if p in piv.index else pd.Series(0, index=dates)
        if isinstance(pr, pd.DataFrame): pr = pr.sum(axis=0)
        pc = pr.reindex(dates, fill_value=0).fillna(0).cumsum()
        fs[p] = {d: c_s + to_int(pc.get(d,0)) for d in dates}

p_sum = {}
if not pk_m.empty:
    for _, r in pk_m.drop_duplicates(subset=["資材名"]).iterrows(): p_sum[r["資材名"]] = {"品番":str(r.get("品番","")), "規格":str(r.get("規格","")), "仕入先":str(r.get("仕入先","")), "保管場所":str(r.get("保管場所","")), "単位":str(r.get("単位","")), "期首在庫":to_int(r.get("初期在庫",0)), "発注点":to_int(r.get("発注点",0)), "発注リードタイム":to_int(r.get("発注リードタイム",7)), "入庫":0, "出庫":0, "現在庫":0}
if not pk_l.empty:
    for _, r in pk_l.iterrows():
        pn, q, pt = r.get("資材名",""), to_int(r.get("数量",0)), str(r.get("処理区分",""))
        if pn in p_sum and "連動" not in pt:
            if "入庫" in pt: p_sum[pn]["入庫"] += q
            elif "出庫" in pt: p_sum[pn]["出庫"] += q
if not mdf.empty and not mst_u.empty:
    mpi = mst_u.set_index("製品名")[["使用資材名","資材使用数"]].to_dict('index')
    for _, r in mdf.iterrows():
        prod, q, rem = str(r.get("製品名","")), to_int(r.get("ケース数",0)), str(r.get("備考",""))
        if prod in mpi and "【資材非連動】" not in rem:
            pn, pu = mpi[prod].get("使用資材名",""), to_int(mpi[prod].get("資材使用数",0))
            if pn and pu>0 and pn in p_sum: p_sum[pn]["出庫"] += (q*pu)
for d in p_sum.values(): d["現在庫"] = d["期首在庫"] + d["入庫"] - d["出庫"]; d["状態"] = "⚠️ 注意" if d["現在庫"] < d["発注点"] else "✅ 正常"

# ─────────────────────────────────────────────
# サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<div style='padding:16px 8px 8px;'><span style='font-size:22px;'>🏭</span><span style='font-size:16px; font-weight:900; color:#F1F5F9; margin-left:8px;'>丸実屋システム</span></div>", unsafe_allow_html=True)
    _today = date.today()
    if not odf.empty and "納品予定日" in odf.columns and "不良廃棄フラグ" in odf.columns:
        _nd = pd.to_datetime(odf["納品予定日"], errors='coerce')
        if hasattr(_nd, 'dt') and _nd.dt.tz is not None:
            _nd = _nd.dt.tz_convert(None)
        toc = int((_nd.dt.normalize().dt.date == _today).sum())
    else:
        toc = 0
    scnt = sum(1 for f in fs.values() if any(v < 0 for v in list(f.values())[:7]))
    st.markdown(f'<div style="margin:8px 0 12px; background:rgba(255,255,255,0.07); border-radius:8px; padding:10px 14px;"><div style="font-size:12px; color:#94A3B8; margin-bottom:4px;">本日状況</div><div style="display:flex; gap:12px;"><div><span style="font-size:20px; font-weight:900; color:#60A5FA;">{toc}</span><span style="font-size:11px; color:#94A3B8;"> 出荷</span></div><div><span style="font-size:20px; font-weight:900; color:#F87171;">{scnt}</span><span style="font-size:11px; color:#94A3B8;"> 欠品予測</span></div></div></div><div style="height:1px; background:rgba(255,255,255,0.1); margin:0 0 10px;"></div>', unsafe_allow_html=True)
    
    menus = ["📋 受注登録","🏭 製造登録","🚚 出荷・発送管理","📦 資材・入出庫","📑 登録一覧","📊 在庫・スケジュール","🏗️ 製造スケジューラー","⭐ 特注・チャータースケジュール","📈 経営・分析ダッシュボード","⚙️ マスタ・分析"]
    for m in menus:
        if st.button(m, use_container_width=True, type="primary" if st.session_state.current_page == m else "secondary"):
            st.session_state.current_page = m; st.session_state.drill_product = None; st.rerun()

pg = st.session_state.current_page
hc = {"📋 受注登録": "#1E3A8A, #3B82F6", "🏭 製造登録": "#064E3B, #10B981", "🚚 出荷・発送管理": "#047857, #34D399", "📦 資材・入出庫": "#B45309, #F59E0B", "📑 登録一覧": "#0F766E, #14B8A6", "📊 在庫・スケジュール": "#1E3A8A, #6366F1", "🏗️ 製造スケジューラー": "#1C1917, #78350F", "⭐ 特注・チャータースケジュール": "#5B21B6, #8B5CF6", "📈 経営・分析ダッシュボード": "#0C4A6E, #0EA5E9", "⚙️ マスタ・分析": "#475569, #1E293B"}
def page_header(t):
    st.markdown(f'<div class="page-header" style="background:linear-gradient(135deg,{hc.get(t,"#1E3A8A, #3B82F6")});"><h1>{t}</h1></div>', unsafe_allow_html=True)
    show_flash()
def sec(t): st.markdown(f'<div class="section-title">{t}</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 📋 受注登録
# ─────────────────────────────────────────────
if pg == "📋 受注登録":
    page_header("📋 受注 登録")
    idu = st.checkbox("📅 納品日を後で決める（日付未定で登録）", value=False)
    od = None if idu else st.date_input("📅 納品日", value=date.today() + timedelta(days=1))
    if idu: st.markdown('<div class="info-card yellow" style="background:#FFFBEB;padding:10px 16px;">🟡 <b>日付未定</b> として登録されます。</div>', unsafe_allow_html=True)
    sl = sh_m["運送会社名"].tolist() if not sh_m.empty else []; tl = get_toriatsuki_list()
    t1,t2,t3 = st.columns([2, 2, 1])
    stor = t1.selectbox("🏢 帳合先", options=tl, index=None, placeholder="選択…")
    scands = get_shiten_list(stor)
    sv = t2.selectbox("🏬 支店・店舗名", options=["（なし）"]+scands, index=0) if scands else t2.text_input("🏬 支店・店舗名（直接入力）")
    sv = "" if sv=="（なし）" else sv
    sc = t3.selectbox("🚚 運送会社", options=sl, index=None, placeholder="未定")
    c_full = st.pills("カテゴリ", CATS, default=CATS[0], label_visibility="collapsed"); cat = c_full.split(" ",1)[1] if c_full else CATS[0].split(" ",1)[1]
    s1,s2,s3 = st.columns([1.5, 2.5, 1.5]); s_p = s1.text_input("🔍 製品検索", placeholder="名称一部...")
    p_lst = [p for p in mst_u["製品名"].tolist() if s_p in p] if s_p else (mst_u[mst_u["大カテゴリ"]==cat]["製品名"].tolist() if not mst_u.empty else [])
    prod = s2.selectbox("確定製品", options=p_lst, index=None, placeholder="選択", format_func=fn)
    pr = mst_u[mst_u["製品名"]==prod] if not mst_u.empty and prod else pd.DataFrame()
    spf = str(pr.iloc[0].get("特注フラグ","")).upper() in ["TRUE","1","YES"] if not pr.empty else False
    chf = str(pr.iloc[0].get("チャーターフラグ","")).upper() in ["TRUE","1","YES"] if not pr.empty else False
    stype = s3.selectbox("⭐ 種別", options=SP_T, index=SP_T.index("⭐ 特注" if spf else ("🚌 チャーター便" if chf else "（なし）")))
    nu, tan = pui(prod)
    if tan not in ["ケース","","nan","None"] and nu > 1:
        q1, q2 = st.columns([1, 2]); im = q1.radio(f"入力単位（1cs＝{nu}{tan}）", ["個数で入力", "ケース数で入力"], horizontal=True)
        if "個数" in im:
            rq = q2.number_input(f"📦 個数（{tan}）", min_value=1, step=1, value=None)
            qty = (int(rq)//nu) if rq and int(rq)>0 else None
            if rq: q2.markdown(f"<div style='font-size:13px;color:#475569;'>➡ <b>{qty} cs</b>" + (f" <span style='color:#F59E0B;'>(端数 {int(rq)%nu}{tan}切捨)</span>" if int(rq)%nu>0 else "") + "</div>", unsafe_allow_html=True)
        else:
            qty = q2.number_input("📦 ケース数", min_value=1, step=1, value=None)
            if qty: q2.markdown(f"<div style='font-size:13px;color:#475569;'>≒ <b>{to_int(qty)*nu} {tan}</b></div>", unsafe_allow_html=True)
    else: qty = st.number_input("📦 ケース数", min_value=1, step=1, value=None)
    r1, r2 = st.columns([2, 2]); rem = r1.text_input("📝 備考"); c1, c2 = r2.columns(2); isub = c1.checkbox("🔄 代替品"); iirr = c2.checkbox("⚠️ 不良廃棄")
    
    if prod and qty and to_int(qty)>0 and cs.get(prod,0) < to_int(qty):
        st.markdown(f'<div class="info-card red" style="background:#FEF2F2;">🚨 <b>製品在庫不足！</b> 現在庫: <b>{cs.get(prod,0)} cs</b> ／ 不足: <span class="shortage-red">－{to_int(qty)-cs.get(prod,0)} cs</span></div>', unsafe_allow_html=True)
    
    m_add = st.empty()
    if st.button("✅ 受注を登録", type="primary", use_container_width=True):
        if not prod or not qty or to_int(qty)<1:
            m_add.error("⚠️ 製品・ケース数は必須です。")
        else:
            frem = f"{'【代替品】' if isub else ''}{'【不良廃棄】' if iirr else ''} {'特注' if '特注' in stype else ('チャーター便' if 'チャーター' in stype else '')} {rem}".strip()
            cn = f"{stor} {sv}".strip() if sv else (stor if stor else "未指定")
            nid = str(uuid.uuid4())[:6].upper(); ddt = pd.to_datetime(od) if od else pd.NaT
            app_sync("orders", pd.DataFrame([{"ID":nid,"納品予定日":ddt,"顧客名":cn,"大カテゴリ":cat,"製品名":prod,"ケース数":to_int(qty),"運送会社":sc or "","備考":frem,"荷姿チェック":False,"発送備考":"","不良廃棄フラグ":iirr,"日付未定フラグ":idu,"登録日時":datetime.now()}]))
            if ("特注" in stype or "チャーター" in stype) and od:
                app_sync("special_schedule", pd.DataFrame([{"ID":str(uuid.uuid4())[:6].upper(),"受注ID":nid,"製品名":prod,"顧客名":cn,"納品予定日":ddt,"出荷予定日":ddt-timedelta(days=1),"備考":frem,"更新日時":datetime.now()}]))
            # 在庫状況を判定してフラッシュメッセージ
            _cur = cs.get(prod, 0)
            _d_key = pd.Timestamp(od).normalize() if od else None
            _proj = fs.get(prod, {}).get(_d_key, _cur) if _d_key else _cur
            _after = _proj - to_int(qty)
            if idu:
                _stk_msg = f"📦 現在庫: {_cur:,} cs（日付未定のため在庫影響は確定後に反映）"
                _ftype = "info"
            elif _after < 0:
                _stk_msg = f"📦 現在庫: {_cur:,} cs ／ 納品日予測在庫: {_proj:,} cs → 登録後: **{_after:,} cs** 🚨 在庫不足！"
                _ftype = "error"
            else:
                _stk_msg = f"📦 現在庫: {_cur:,} cs ／ 納品日予測在庫: {_proj:,} cs → 登録後: {_after:,} cs ✅ 充足"
                _ftype = "success"
            flash(_ftype, f"✨ 登録完了！【{fn(prod)}】 {to_int(qty):,}cs  納品日: {format_date_jp(od) if od else '日付未定'}  顧客: {cn}\n{_stk_msg}")
            st.rerun()
    show_flash_inline(m_add)

    u_df = odf[odf["日付未定フラグ"]==True].copy().reset_index(drop=True) if not odf.empty and "日付未定フラグ" in odf.columns else pd.DataFrame()
    if not u_df.empty:
        with st.expander(f"🟡 日付未定受注を確定する ({len(u_df)}件)", expanded=True):
            udsp = u_df[["ID","製品名","ケース数","備考","顧客名","運送会社"]].copy(); udsp.insert(4,"納品予定日(確定)",None); udsp.insert(5,"帳合先(確定)",""); udsp.insert(6,"支店名(確定)","")
            ed_u = st.data_editor(udsp, use_container_width=True, hide_index=True, column_config={"ID":None,"製品名":st.column_config.TextColumn(disabled=True),"ケース数":st.column_config.NumberColumn(disabled=True),"備考":st.column_config.TextColumn(disabled=True),"顧客名":st.column_config.TextColumn(disabled=True),"納品予定日(確定)":st.column_config.DateColumn("📅 納品日",format="YYYY/MM/DD"),"帳合先(確定)":st.column_config.SelectboxColumn("🏢 帳合先",options=tl),"運送会社":st.column_config.SelectboxColumn("🚚 運送会社",options=sl)})
            _udf_msg = st.empty()
            if st.button("✅ 日付確定保存", type="primary", use_container_width=True):
                upd = odf.copy(); cnt=0
                for i, r in ed_u.iterrows():
                    oid = u_df.iloc[i]["ID"] if i<len(u_df) else None
                    if not oid or pd.isnull(r.get("納品予定日(確定)")): continue
                    m = upd["ID"]==oid
                    upd.loc[m,"納品予定日"] = pd.to_datetime(r.get("納品予定日(確定)")); upd.loc[m,"日付未定フラグ"] = False
                    if r.get("帳合先(確定)"): upd.loc[m,"顧客名"] = f"{r.get('帳合先(確定)')} {r.get('支店名(確定)','')}".strip()
                    if r.get("運送会社"): upd.loc[m,"運送会社"] = str(r.get("運送会社")).strip()
                    cnt+=1
                if cnt>0:
                    save_sync("orders", upd)
                    flash("success", f"✅ {cnt}件の納品日を確定しました。")
                    st.rerun()
                else:
                    _udf_msg.warning("⚠️ 確定する日付が入力されていません。")
            show_flash_inline(_udf_msg)

    sec("✏️ 直近データの修正・削除")
    if not odf.empty:
        do = odf.sort_values("登録日時",ascending=False).copy()
        do["納品予定日(表示)"] = do.apply(lambda r: "🟡 日付未定" if r.get("日付未定フラグ") is True else format_date_jp(r["納品予定日"]), axis=1) if "日付未定フラグ" in do.columns else do["納品予定日"].apply(format_date_jp)
        _odf_limit = st.selectbox("編集件数", [5,10,20,50], format_func=lambda x: f"直近 {x} 件", index=0, key="odf_edit_limit")
        ed_o = st.data_editor(do.head(_odf_limit)[["ID","納品予定日(表示)","顧客名","製品名","ケース数","運送会社","備考","不良廃棄フラグ"]], num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"ID":None,"ケース数":st.column_config.NumberColumn(min_value=1,step=1,format="%d")})
        _o_save_msg = st.empty()
        if st.button("💾 直近データ保存"):
            sv = ed_o.copy(); sv["納品予定日"] = pd.to_datetime(sv["納品予定日(表示)"].str.replace("🟡 日付未定","").str.replace("🟡 ","").str.split(" ").str[0], errors="coerce")
            _o_ids = do.head(_odf_limit)["ID"].tolist()
            save_sync("orders", pd.concat([odf[~odf["ID"].isin(_o_ids)], pd.merge(sv, odf[[c for c in ["ID","大カテゴリ","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考","日付未定フラグ","登録日時"] if c in odf.columns]], on="ID", how="left")], ignore_index=True))
            flash("success", "✅ 受注データを保存しました。"); st.rerun()
        show_flash_inline(_o_save_msg)
        with st.expander("📂 全データ一括編集"):
            ea_o = st.data_editor(do[["ID","納品予定日(表示)","顧客名","製品名","ケース数","運送会社","備考","不良廃棄フラグ"]], num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"ID":None,"ケース数":st.column_config.NumberColumn(min_value=1,step=1,format="%d")}, height=400)
            _o_all_msg = st.empty()
            if st.button("💾 全データ保存"):
                sva = ea_o.copy(); sva["納品予定日"] = pd.to_datetime(sva["納品予定日(表示)"].str.replace("🟡 日付未定","").str.replace("🟡 ","").str.split(" ").str[0], errors="coerce")
                save_sync("orders", pd.merge(sva, odf[[c for c in ["ID","大カテゴリ","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考","日付未定フラグ","登録日時"] if c in odf.columns]], on="ID", how="left"))
                flash("success", "✅ 受注全データを保存しました。"); st.rerun()
            show_flash_inline(_o_all_msg)

# ─────────────────────────────────────────────
# 🚚 出荷・発送管理
# ─────────────────────────────────────────────
elif pg == "🚚 出荷・発送管理":
    page_header("🚚 出荷・発送 消込管理")
    ts1, ts2, ts3 = st.tabs(["📋 日次消込", "📅 週間出荷一覧", "📥 出荷CSV出力"])
    with ts1:
        td = st.date_input("📅 対象日", value=date.today())
        if not odf.empty:
            _nd2 = pd.to_datetime(odf["納品予定日"], errors='coerce')
            if hasattr(_nd2, 'dt') and _nd2.dt.tz is not None:
                _nd2 = _nd2.dt.tz_convert(None)
            _mask = (_nd2.dt.normalize().dt.date == td) & (odf["不良廃棄フラグ"] == False)
            d_ord = odf[_mask].copy()
        else:
            d_ord = pd.DataFrame()
        if d_ord.empty: st.info(f"📭 {format_date_jp(td)} の予定なし")
        else:
            dn = d_ord[d_ord["荷姿チェック"]==True]; udn = d_ord[d_ord["荷姿チェック"]==False]
            c1,c2,c3 = st.columns(3); c1.metric("出荷件数", f"{len(d_ord)} 件"); c2.metric("✅ 消込済", f"{len(dn)} 件"); c3.metric("⏳ 未消込", f"{len(udn)} 件", delta_color="inverse")
            if not udn.empty and td <= date.today(): st.error(f"🚨 出荷漏れ（荷姿未チェック）が **{len(udn)} 件** あります！")
            ddf = d_ord[["ID","顧客名","製品名","ケース数","運送会社","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考"]].copy()
            for c in ["賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5"]: ddf[c] = pd.to_datetime(ddf[c], errors="coerce").dt.date
            ed_s = st.data_editor(ddf.style.apply(lambda r: ['background-color:#D1FAE5;color:#065F46;text-decoration:line-through;']*len(r) if str(r.get("荷姿チェック",False)).upper()=="TRUE" else ['']*len(r), axis=1), use_container_width=True, hide_index=True, column_config={"ID":None,"顧客名":st.column_config.TextColumn(disabled=True),"製品名":st.column_config.TextColumn(disabled=True),"ケース数":st.column_config.NumberColumn(disabled=True),"運送会社":st.column_config.SelectboxColumn(options=sh_m["運送会社名"].tolist() if not sh_m.empty else []),"賞味期限1":st.column_config.DateColumn("賞味1",format="YYYY-MM-DD")})
            _ship_msg = st.empty()
            if st.button("💾 保存", type="primary", use_container_width=True):
                u = odf.copy().astype(object)
                for i, r in ed_s.iterrows():
                    m = u["ID"]==r["ID"]
                    if m.any():
                        u.loc[m,"運送会社"] = str(r.get("運送会社","")); u.loc[m,"荷姿チェック"] = str(r.get("荷姿チェック",False)).upper(); u.loc[m,"発送備考"] = str(r.get("発送備考",""))
                        for c in ["賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5"]: v=r.get(c); u.loc[m,c] = v.strftime("%Y-%m-%d") if pd.notnull(v) and v else ""
                save_sync("orders", u)
                flash("success", "✅ 出荷情報を保存しました。"); st.rerun()
            show_flash_inline(_ship_msg)

    with ts2:
        c1, c2 = st.columns([2, 2]); sw = c1.date_input("開始日", value=date.today()); wd = c2.number_input("表示日数", min_value=1, max_value=30, value=7)
        def _ord_for_date(df, target_date):
            if df.empty: return pd.DataFrame()
            _nd = pd.to_datetime(df["納品予定日"], errors='coerce')
            if hasattr(_nd,'dt') and _nd.dt.tz is not None: _nd = _nd.dt.tz_convert(None)
            return df[_nd.dt.normalize().dt.date == target_date].copy()
        if st.radio("モード", ["📋 日別折りたたみ", "📊 全件一覧"], horizontal=True) == "📋 日別折りたたみ":
            for i in range(int(wd)):
                d = pd.Timestamp(sw)+timedelta(days=i)
                wo = _ord_for_date(odf, d.date())
                if not wo.empty:
                    with st.expander(f"**{format_date_jp(d)}**　{len(wo)}件 ✅{len(wo[wo['荷姿チェック']==True])}件完了", expanded=(d.date()==date.today())):
                        st.dataframe(wo[["顧客名","製品名","ケース数","運送会社","荷姿チェック","発送備考"]].style.apply(lambda r: ['background-color:#D1FAE5;']*len(r) if r.get("荷姿チェック")==True else ['']*len(r), axis=1), use_container_width=True, hide_index=True)
        else:
            frames = [_ord_for_date(odf, (pd.Timestamp(sw)+timedelta(days=i)).date()).assign(納品日=format_date_jp(pd.Timestamp(sw)+timedelta(days=i))) for i in range(int(wd))]
            aw = pd.concat([f for f in frames if not f.empty], ignore_index=True) if any(not f.empty for f in frames) else pd.DataFrame()
            if aw.empty: st.info("予定なし")
            else:
                c1,c2,c3=st.columns(3); c1.metric("件数",f"{len(aw)}件"); c2.metric("✅ 消込済",f"{len(aw[aw['荷姿チェック']==True])}件"); c3.metric("総数",f"{aw['ケース数'].apply(to_int).sum():,}cs")
                sc = [c for c in ["納品日","顧客名","製品名","ケース数","運送会社","荷姿チェック","発送備考","備考"] if c in aw.columns]
                st.dataframe(aw[sc].style.apply(lambda r: ['background-color:#D1FAE5;color:#065F46;']*len(r) if r.get("荷姿チェック")==True else ['']*len(r), axis=1), use_container_width=True, hide_index=True, height=min(600, max(300, len(aw)*38+60)))
                st.download_button("📥 CSV出力", data=make_csv_bytes(aw[sc]), file_name=f"週間出荷_{sw}.csv", mime="text/csv", use_container_width=True)

    with ts3:
        ce1, ce2 = st.columns(2); es = ce1.date_input("開始", value=date.today().replace(day=1)); ee = ce2.date_input("終了", value=date.today())
        if not odf.empty:
            _nd3 = pd.to_datetime(odf["納品予定日"], errors='coerce')
            if hasattr(_nd3,'dt') and _nd3.dt.tz is not None: _nd3 = _nd3.dt.tz_convert(None)
            _nd3_date = _nd3.dt.normalize().dt.date
            edf = odf[(_nd3_date >= es) & (_nd3_date <= ee)].copy()
            for c in ["納品予定日","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5"]:
                if c in edf.columns: edf[c] = pd.to_datetime(edf[c],errors='coerce').apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "")
            edf["荷姿チェック"] = edf["荷姿チェック"].map({True:"済",False:"未"}).fillna("")
            st.metric("対象件数", f"{len(edf)} 件")
            st.download_button("📥 CSV出力", data=make_csv_bytes(edf[[c for c in ["納品予定日","顧客名","製品名","ケース数","運送会社","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考","備考"] if c in edf.columns]]), file_name=f"出荷データ_{es}_{ee}.csv", mime="text/csv", type="primary", use_container_width=True)

# ─────────────────────────────────────────────
# 🏭 製造登録
# ─────────────────────────────────────────────
elif pg == "🏭 製造登録":
    page_header("🏭 製造・リパック 登録")
    c1, c2 = st.columns([1,1])
    mdt = c1.date_input("📅 製造日", value=date.today()); mq = c2.number_input("📦 製造ケース数", min_value=1, step=1, value=None)
    cf = st.pills("カテゴリ", CATS, default=CATS[0], label_visibility="collapsed"); c_m = cf.split(" ",1)[1] if cf else CATS[0].split(" ",1)[1]
    s1, s2 = st.columns([1.5, 2.5]); sp = s1.text_input("🔍 製品名検索", placeholder="検索...")
    pl = [p for p in mst_u["製品名"].tolist() if sp in p] if sp else (mst_u[mst_u["大カテゴリ"]==c_m]["製品名"].tolist() if not mst_u.empty else [])
    pm = s2.selectbox("確定製品", options=pl, index=None, format_func=fn); mr = s2.text_input("📝 備考（製造）")
    irp = st.checkbox("🔄 リパック製造（在庫加算）"); ipl = st.checkbox("📦 紐づく資材の在庫も同時に減らす", value=True) if irp else True
    if pm and mq and cs.get(pm,0)<=0: st.markdown(f"<div class='info-card red' style='background:#FEF2F2; padding:10px;'>現在庫: <span class='shortage-red'>{cs.get(pm,0)} cs</span> → 製造後: <b>{cs.get(pm,0)+to_int(mq)} cs</b></div>", unsafe_allow_html=True)
    st.write("---")
    _mfg_reg_msg = st.empty()
    if st.button("➕ 製造データを記録", type="primary", use_container_width=True):
        if not pm or not mq: st.error("⚠️ 製品・数量は必須")
        else:
            rt = f"{'【リパック】' if irp else ''} {'【資材非連動】' if irp and not ipl else ''} {mr}".strip(); nid = str(uuid.uuid4())[:6].upper()
            app_sync("manufactures", pd.DataFrame([{"ID":nid,"製造予定日":pd.to_datetime(mdt),"大カテゴリ":c_m,"製品名":pm,"ケース数":to_int(mq),"リパックフラグ":irp,"備考":rt,"登録日時":datetime.now()}]))
            _mfg_mat_msg = ""
            if ipl and not mst_u.empty and pm in mst_u.set_index("製品名")[["使用資材名","資材使用数"]].to_dict('index'):
                mpi = mst_u.set_index("製品名")[["使用資材名","資材使用数"]].to_dict('index')
                _pnn = mpi[pm].get("使用資材名",""); _puu = to_int(mpi[pm].get("資材使用数",0))
                if _pnn and _puu>0:
                    app_sync("packaging_logs", pd.DataFrame([{"ID":str(uuid.uuid4())[:6].upper(),"登録日":pd.to_datetime(mdt),"資材名":_pnn,"処理区分":"製造連動","数量":abs(to_int(mq)*_puu),"理由":f"製造ID:{nid}","関連製品名":pm,"理論在庫":p_sum.get(_pnn,{}).get("現在庫",0)-(to_int(mq)*_puu),"備考":"自動記録","登録日時":datetime.now()}]))
                    _mfg_mat_msg = f"  ＋【{_pnn}】 {abs(to_int(mq)*_puu):,}枚 自動減算"
            flash("success", f"✅ 登録しました！【{fn(pm)}】 {to_int(mq):,}cs  製造日: {mdt.strftime('%Y/%m/%d')}{_mfg_mat_msg}")
            st.rerun()
    show_flash_inline(_mfg_reg_msg)

    sec("✏️ 直近データの修正・削除")
    if not mdf.empty:
        dm = mdf.sort_values("登録日時", ascending=False).copy(); dm["製造予定日(表示)"] = dm["製造予定日"].apply(format_date_jp)
        _mdf_limit = st.selectbox("編集件数", [5,10,20,50], format_func=lambda x: f"直近 {x} 件", index=0, key="mdf_edit_limit")
        edm = st.data_editor(dm.head(_mdf_limit)[["ID","製造予定日(表示)","製品名","ケース数","リパックフラグ","備考"]], num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"ID":None,"ケース数":st.column_config.NumberColumn(min_value=1,step=1,format="%d")})
        _mfg_save_msg = st.empty()
        if st.button("💾 直近データ保存"):
            sm = edm.copy(); sm["製造予定日"] = pd.to_datetime(sm["製造予定日(表示)"].str.split(" ").str[0], errors="coerce")
            sm_ids = dm.head(_mdf_limit)["ID"].tolist()
            save_sync("manufactures", pd.concat([mdf[~mdf["ID"].isin(sm_ids)], pd.merge(sm, mdf[["ID","大カテゴリ","登録日時"]], on="ID", how="left")], ignore_index=True))
            flash("success", "✅ 製造データを保存しました。"); st.rerun()
        show_flash_inline(_mfg_save_msg)
        with st.expander("📂 全データ一括編集・削除"):
            ea_m = st.data_editor(dm[["ID","製造予定日(表示)","製品名","ケース数","リパックフラグ","備考"]], num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"ID":None,"ケース数":st.column_config.NumberColumn(min_value=1,step=1,format="%d")}, height=400)
            _mfg_all_msg = st.empty()
            if st.button("💾 全データ保存", key="btn_ea_m"):
                sma = ea_m.copy(); sma["製造予定日"] = pd.to_datetime(sma["製造予定日(表示)"].str.split(" ").str[0], errors="coerce")
                save_sync("manufactures", pd.merge(sma, mdf[["ID","大カテゴリ","登録日時"]], on="ID", how="left"))
                flash("success", "✅ 製造全データを保存しました。"); st.rerun()
            show_flash_inline(_mfg_all_msg)

# ─────────────────────────────────────────────
# 📦 資材・入出庫
# ─────────────────────────────────────────────
elif pg == "📦 資材・入出庫":
    page_header("📦 資材・段ボール入出庫")
    s_pks = [pn for pn,d in p_sum.items() if d["現在庫"] < d["発注点"]]
    if s_pks: st.error("🚨 **要発注アラート:** " + "、".join(s_pks))
    tp1, tp2, tp3, tp4 = st.tabs(["📦 発注予測","📊 サマリ","📝 入出庫","✏️ 履歴"])

    with tp1:
        if pk_m.empty: st.warning("マスタに資材がありません。")
        else:
            fd = 90; pf = {}
            if not mst_u.empty and not odf.empty:
                mpi = mst_u.set_index("製品名")[["使用資材名","資材使用数"]].to_dict("index")
                for _, r in odf.iterrows():
                    p, q, dt = str(r.get("製品名","")), to_int(r.get("ケース数",0)), pd.to_datetime(r.get("納品予定日"),errors="coerce")
                    if pd.isna(dt) or dt.date()<date.today() or dt>today+timedelta(days=fd) or p not in mpi: continue
                    pn, pu = str(mpi[p].get("使用資材名","")), to_int(mpi[p].get("資材使用数",0))
                    if pn and pu>0: pf.setdefault(pn, {})[dt.normalize()] = pf.get(pn,{}).get(dt.normalize(),0) + q*pu
            for p in p_sum.keys(): pf.setdefault(p, {})
            
            oa = []
            for pn, du in pf.items():
                lt = p_sum.get(pn,{}).get("発注リードタイム",7) or 7; ci = p_sum.get(pn,{}).get("現在庫",0); pt = p_sum.get(pn,{}).get("発注点",0)
                ri = ci; ro_d = None; z_d = None; io = None; cu = 0
                for d_lt in pd.date_range(today, today+timedelta(days=fd)):
                    u = du.get(d_lt,0); ri-=u; cu+=u
                    if ri<=pt and ro_d is None: ro_d=d_lt; io=ri
                    if ri<=0 and z_d is None: z_d=d_lt
                
                if ro_d:
                    od = ro_d - timedelta(days=lt); dl = (od.date() - date.today()).days
                    urg, uc, bc = ("🔴 今すぐ発注！","#FEE2E2","#DC2626") if dl<=0 else (f"🟠 {dl}日以内","#FFF7ED","#EA580C") if dl<=3 else (f"🟡 {dl}日以内","#FFFBEB","#D97706") if dl<=7 else (f"🔵 {dl}日後","#EFF6FF","#2563EB")
                else: od=None; io=None; dl=999; urg, uc, bc = "✅ 問題なし", "#F0FDF4", "#059669"
                
                oa.append({"資材名":pn,"現在庫":ci,"発注点":pt,"LT":lt,"90日消費":int(cu),"発注推奨日":od.strftime("%Y/%m/%d") if od else "―","到達日":ro_d.strftime("%Y/%m/%d") if ro_d else "なし","枯渇予測":z_d.strftime("%Y/%m/%d") if z_d else "―","予測在庫":f"{io:,}" if io is not None else "―","緊急度":urg,"_s":dl,"_c":uc,"_b":bc})
            
            df_a = pd.DataFrame(oa).sort_values("_s").reset_index(drop=True)
            u_df = df_a[df_a["_s"]<=7]
            if not u_df.empty:
                st.markdown("### 🚨 直近7日以内に発注手配が必要")
                for _, r in u_df.iterrows(): st.markdown(f'<div style="background:{r["_c"]};border-left:6px solid {r["_b"]};border-radius:10px;padding:14px;margin-bottom:10px;"><b>📦 {r["資材名"]}</b> <span style="float:right;font-weight:900;">{r["緊急度"]}</span><br><span style="font-size:13px;">現在庫: {r["現在庫"]:,} | 発注点: {r["発注点"]:,} | LT: {r["LT"]}日<br>⏰ <b>発注点到達: {r["到達日"]}</b><br>📉 <b>枯渇予測: {r["枯渇予測"]}</b></span></div>', unsafe_allow_html=True)
            
            st.dataframe(df_a[["資材名","現在庫","発注点","LT","90日消費","発注推奨日","到達日","予測在庫","枯渇予測","緊急度"]].style.apply(lambda r: ['background-color:#FEE2E2;font-weight:bold;']*len(r) if "今すぐ" in str(r.get("緊急度","")) else (['background-color:#FFF7ED;']*len(r) if "🟠" in str(r.get("緊急度","")) else (['background-color:#FFFBEB;']*len(r) if "🟡" in str(r.get("緊急度","")) else (['background-color:#EFF6FF;']*len(r) if "🔵" in str(r.get("緊急度","")) else ['background-color:#F0FDF4;']*len(r)))), axis=1), use_container_width=True, hide_index=True, height=500)

            pack_mst_unique = pk_m.drop_duplicates(subset=["資材名"]) if not pk_m.empty else pd.DataFrame(columns=["資材名"])
            spg = st.selectbox("グラフ表示", options=[r["資材名"] for _, r in pack_mst_unique.iterrows()])
            if spg:
                ri = p_sum.get(spg,{}).get("現在庫",0); gd, gs, gu = [], [], []
                for d_g in pd.date_range(today, today+timedelta(days=fd)):
                    ug = pf.get(spg,{}).get(d_g,0); ri-=ug; gd.append(d_g.strftime("%m/%d")); gs.append(ri); gu.append(ug)
                fig = go.Figure()
                fig.add_trace(go.Bar(x=gd, y=gu, name="日別消費", marker_color="#F43F5E", opacity=0.55))
                fig.add_trace(go.Scatter(x=gd, y=gs, name="予測在庫", mode="lines+markers", line=dict(color="#2563EB", width=2.5)))
                fig.add_hline(y=p_sum.get(spg,{}).get("発注点",0), line_dash="dash", line_color="#F59E0B", annotation_text="発注点")
                fig.add_hline(y=0, line_dash="dot", line_color="#DC2626", annotation_text="ゼロ")
                fig.update_layout(title=f"【{spg}】 在庫推移予測", hovermode="x unified", barmode="relative", margin=dict(l=10,r=10,t=55,b=10), height=380); st.plotly_chart(fig, use_container_width=True)

    with tp2:
        if not p_sum:
            st.info("資材マスタが登録されていません。")
        else:
            _sum_df = pd.DataFrame([{"資材名":k,**v} for k,v in p_sum.items()])
            _sum_cols = [c for c in ["資材名","品番","規格","仕入先","保管場所","現在庫","発注点","状態","単位"] if c in _sum_df.columns]
            st.dataframe(_sum_df[_sum_cols].style.apply(lambda r: ['background-color:#FFEDD5;color:#C2410C;font-weight:bold;']*len(r) if to_int(r.get("現在庫",0))<to_int(r.get("発注点",0)) else ['']*len(r),axis=1), use_container_width=True, hide_index=True)

    with tp3:
        pd_t = st.date_input("📅 処理日", value=date.today())
        pack_mst_unique = pk_m.drop_duplicates(subset=["資材名"]) if not pk_m.empty else pd.DataFrame(columns=["資材名"])
        c1,c2 = st.columns([1.5,2.5]); s_pk = c1.text_input("🔍 検索"); f_pk = [p for p in pack_mst_unique["資材名"].tolist() if s_pk in p] if s_pk else pack_mst_unique["資材名"].tolist()
        sl_pk = c2.selectbox("📦 資材", options=f_pk, index=None)
        pt = st.radio("区分", ["📥 入庫","📤 出庫","📋 棚卸"], horizontal=True)
        if "棚卸" in pt: pq = st.number_input("実在庫数", min_value=0, step=1, value=None); ro = ["棚卸調整"]
        else: pq = st.number_input("数量", min_value=1, step=1, value=None); ro = ["仕入","返品","その他入庫"] if "入庫" in pt else ["破損","サンプル","その他出庫"]
        pr = st.selectbox("理由", options=ro); prm = st.text_input("📝 備考")
        _pk_msg = st.empty()
        if st.button("➕ 登録", type="primary", use_container_width=True):
            if not sl_pk or pq is None:
                _pk_msg.error("⚠️ 資材と数量は必須です")
            else:
                lq = to_int(pq); fpt = "入庫" if "入庫" in pt else "出庫"
                if "棚卸" in pt:
                    diff = lq - p_sum.get(sl_pk,{}).get("現在庫",0)
                    if diff == 0:
                        _pk_msg.info(f"ℹ️ 【{sl_pk}】 在庫数に変更なし（棚卸一致）")
                    else:
                        fpt, lq = ("入庫", diff) if diff > 0 else ("出庫", abs(diff))
                        app_sync("packaging_logs", pd.DataFrame([{"ID":str(uuid.uuid4())[:6].upper(),"登録日":pd.to_datetime(pd_t),"資材名":sl_pk,"処理区分":fpt,"数量":lq,"理由":pr,"関連製品名":"","理論在庫":"","備考":prm,"登録日時":datetime.now()}]))
                        _pk_msg.success(f"✅ 登録しました！【{sl_pk}】 棚卸調整 {'+' if fpt=='入庫' else '-'}{lq} ({fpt})")
                        st.rerun()
                elif lq > 0:
                    app_sync("packaging_logs", pd.DataFrame([{"ID":str(uuid.uuid4())[:6].upper(),"登録日":pd.to_datetime(pd_t),"資材名":sl_pk,"処理区分":fpt,"数量":lq,"理由":pr,"関連製品名":"","理論在庫":"","備考":prm,"登録日時":datetime.now()}]))
                    disp_type = "入庫" if "入庫" in pt else "出庫"
                    _pk_msg.success(f"✅ 登録しました！【{sl_pk}】 {disp_type} {lq:,} 枚 / {pr}")
                    st.rerun()
                else:
                    _pk_msg.error("⚠️ 数量は1以上を入力してください")

    with tp4:
        if pk_l.empty:
            st.info("履歴がありません。")
        else:
            dpk = pk_l.sort_values("登録日時", ascending=False).copy() if "登録日時" in pk_l.columns else pk_l.copy()
            dpk["登録日(表示)"] = dpk["登録日"].apply(format_date_jp) if "登録日" in dpk.columns else ""
            _tp4_cols = [c for c in ["ID","登録日(表示)","資材名","処理区分","数量","理由","関連製品名","備考"] if c in dpk.columns]

            c_lim, c_del_mode = st.columns([2, 2])
            _h_limit = c_lim.selectbox("表示・編集件数", options=[10, 20, 50, 100, len(dpk)],
                format_func=lambda x: f"直近 {x} 件" if x < len(dpk) else f"全件 ({x} 件)",
                index=0, key="pk_hist_limit")
            _del_mode = c_del_mode.toggle("🗑️ 削除モード", value=False, key="pk_del_mode")
            _dpk_show = dpk.head(_h_limit).reset_index(drop=True)

            if _del_mode:
                # ── 削除モード：チェックボックスで選択削除
                st.markdown('<div style="background:#FEF2F2;border:1.5px solid #FCA5A5;border-radius:8px;padding:8px 14px;margin-bottom:8px;font-size:13px;color:#991B1B;">⚠️ <b>削除モード</b>：削除したい行にチェックを入れて「選択行を削除」ボタンを押してください。削除は取り消せません。</div>', unsafe_allow_html=True)
                _del_df = _dpk_show[_tp4_cols].copy()
                _del_df.insert(0, "削除", False)
                _del_editor = st.data_editor(
                    _del_df, hide_index=True, use_container_width=True,
                    height=min(600, _h_limit * 38 + 60),
                    column_config={
                        "削除": st.column_config.CheckboxColumn("🗑️ 削除", width="small"),
                        "ID": None,
                        "処理区分": st.column_config.SelectboxColumn(options=["入庫","出庫","製造連動"]),
                        "数量": st.column_config.NumberColumn(min_value=1, step=1, format="%d"),
                    }
                )
                _del_ids = []
                for i, row in _del_editor.iterrows():
                    if row.get("削除", False):
                        _del_ids.append(_dpk_show.iloc[i]["ID"])

                _del_msg = st.empty()
                _del_col1, _del_col2 = st.columns([1, 3])
                if _del_col1.button(f"🗑️ 選択行を削除（{len(_del_ids)}件）", type="primary", disabled=(len(_del_ids)==0)):
                    if _del_ids:
                        new_pk = pk_l[~pk_l["ID"].isin(_del_ids)].copy()
                        save_sync("packaging_logs", new_pk)
                        flash("success" if len(_del_ids) > 0 else "info",
                              f"🗑️ {len(_del_ids)}件の履歴を削除しました。")
                        st.rerun()
                show_flash_inline(_del_msg)
                _del_col2.caption(f"{'⚠️ ' + str(len(_del_ids)) + '件が選択されています' if _del_ids else '削除したい行の「削除」にチェックを入れてください'}")

            else:
                # ── 編集モード：通常の編集UI
                edp = st.data_editor(
                    _dpk_show[_tp4_cols], hide_index=True,
                    use_container_width=True,
                    height=min(600, _h_limit * 38 + 60),
                    column_config={
                        "ID": None,
                        "処理区分": st.column_config.SelectboxColumn(options=["入庫","出庫","製造連動"]),
                        "数量": st.column_config.NumberColumn(min_value=1, step=1, format="%d"),
                    }
                )
                _hist_save_msg = st.empty()
                if st.button("💾 履歴を保存", key="btn_spk", type="primary"):
                    edited_ids = _dpk_show["ID"].tolist()
                    rest = pk_l[~pk_l["ID"].isin(edited_ids)].copy()
                    edp_with_id = edp.copy()
                    edp_with_id["ID"] = _dpk_show["ID"].values
                    edp_with_id["登録日"] = pd.to_datetime(
                        edp_with_id["登録日(表示)"].str.split(" ").str[0], errors="coerce"
                    )
                    keep_cols = [c for c in ["ID","理論在庫","登録日時"] if c in pk_l.columns]
                    merged = pd.merge(edp_with_id.drop(columns=["登録日(表示)"], errors="ignore"),
                                      pk_l[keep_cols], on="ID", how="left")
                    save_sync("packaging_logs", pd.concat([rest, merged], ignore_index=True))
                    flash("success", "✅ 資材履歴を保存しました。")
                    st.rerun()
                show_flash_inline(_hist_save_msg)

# ─────────────────────────────────────────────
# 📑 登録一覧
# ─────────────────────────────────────────────
elif pg == "📑 登録一覧":
    page_header("📑 登録データ一覧・出力")
    tl1, tl2, tl3 = st.tabs(["📋 受注・出荷","🏭 製造","📦 資材"])
    with tl1:
        if not odf.empty:
            eo = odf.sort_values("登録日時", ascending=False).copy(); eo["納品日"] = eo["納品予定日"].apply(format_date_jp)
            def _zaiko_status(r):
                try:
                    d = pd.Timestamp(str(r["納品予定日"])).normalize()
                    v = fs.get(r["製品名"],{}).get(d, 0)
                    return f"不足 ({v})" if v < 0 else "OK"
                except Exception:
                    return "―"
            eo["在庫状況"] = eo.apply(_zaiko_status, axis=1)
            st.dataframe(eo[["ID","納品日","顧客名","製品名","ケース数","運送会社","備考","荷姿チェック","在庫状況","不良廃棄フラグ"]].style.apply(lambda r: ['background-color:#D1FAE5;']*len(r) if str(r.get("荷姿チェック")).upper()=="TRUE" else (['background-color:#FEE2E2;font-weight:bold;']*len(r) if "不足" in str(r.get("在庫状況","")) else ['']*len(r)), axis=1), hide_index=True, height=600)
    with tl2:
        if not mdf.empty:
            em = mdf.sort_values("登録日時",ascending=False).copy(); em["製造日"] = em["製造予定日"].apply(format_date_jp)
            st.dataframe(em[["ID","製造日","製品名","ケース数","リパックフラグ","備考"]].style.apply(lambda r: ['background-color:#DBEAFE;font-weight:bold;']*len(r) if str(r.get("リパックフラグ")).upper()=="TRUE" else (['background-color:#F8FAFC;color:#64748B;']*len(r) if "【在庫非反映】" in str(r.get("備考","")) else ['']*len(r)), axis=1), hide_index=True, height=600)
    with tl3:
        if not pk_l.empty:
            el = pk_l.sort_values("登録日時",ascending=False).copy(); el["日"] = el["登録日"].apply(format_date_jp)
            st.dataframe(el[["ID","日","資材名","処理区分","数量","理由","関連製品名","備考"]], hide_index=True, height=600)

# ─────────────────────────────────────────────
# 📊 在庫・スケジュール
# ─────────────────────────────────────────────
elif pg == "📊 在庫・スケジュール":
    page_header("📊 在庫予測 ＆ スケジュール")
    t1, t0, t2, t3, t4 = st.tabs(["📉 1ヶ月在庫予測", "⚠️ 7日以内欠品予測", "📅 週間カレンダー", "🔍 製品別詳細ビュー", "👤 顧客別スケジュール"])

    with t0:
        al = []
        for p, d_fs in fs.items():
            for d in pd.date_range(today, today+timedelta(days=7)):
                if d_fs.get(d,0)<0:
                    do = odf[(odf["製品名"]==p)&(safe_dt_date(odf["納品予定日"])==d.date())&(odf["不良廃棄フラグ"]==False)] if not odf.empty else pd.DataFrame()
                    al.append({"日付":format_date_jp(d),"製品名":p,"予測在庫":d_fs.get(d,0),"現在庫":cs.get(p,0),"顧客名":" / ".join(do["顧客名"].dropna().unique()) if not do.empty else "―","備考":" / ".join(do["備考"].dropna().unique()) if not do.empty else ""})
        if al:
            da = pd.DataFrame(al).drop_duplicates()
            st.dataframe(da.style.map(lambda v: 'color:#DC2626;font-weight:900;background-color:#FEE2E2;' if isinstance(v,(int,float)) and v<0 else '', subset=["予測在庫"]), use_container_width=True, hide_index=True)
        else: st.success("✅ 欠品予測なし")

    with t1:
        if mst_u.empty: st.info("マスタ空")
        else:
            sd = pd.date_range(today, today+timedelta(days=30))
            iv = [{"カテゴリ":r["大カテゴリ"],"製品名":r["製品名"],"現在庫":cs.get(r["製品名"],0), **{format_date_jp(d):fs.get(r["製品名"],{}).get(d,cs.get(r["製品名"],0)) for d in sd}} for _,r in mst_u.iterrows()]
            idf = pd.DataFrame(iv).sort_values("カテゴリ").reset_index(drop=True)
            c1, c2 = st.columns([3, 1]); c1.markdown('<div style="font-size:13px;color:#64748B;">💡 行クリックで詳細展開</div>', unsafe_allow_html=True)
            if c2.button("🔄 閉じる"): st.session_state.drill_product = None; st.rerun()
            se = st.dataframe(idf.style.map(lambda v: 'color:#DC2626;font-weight:bold;background-color:#FEE2E2;' if isinstance(v,(int,float)) and v<0 else ''), use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
            if se.selection.get("rows"): st.session_state.drill_product = idf.iloc[se.selection.get("rows")[0]]["製品名"]

            dp = st.session_state.drill_product
            if dp:
                st.markdown(f'<div class="drill-panel">### 📦 {fn(dp)} 詳細', unsafe_allow_html=True)
                oy = today - timedelta(days=365)
                ph = odf[(odf["製品名"]==dp)&(pd.to_datetime(odf["納品予定日"],errors='coerce')>=oy)&(pd.to_datetime(odf["納品予定日"],errors='coerce')<today)].copy() if not odf.empty else pd.DataFrame()
                mh = mdf[(mdf["製品名"]==dp)&(pd.to_datetime(mdf["製造予定日"],errors='coerce')>=oy)&(pd.to_datetime(mdf["製造予定日"],errors='coerce')<today)].copy() if not mdf.empty else pd.DataFrame()
                
                with st.expander("📜 過去1年履歴", expanded=True):
                    tho = ph["ケース数"].apply(to_int).sum() if not ph.empty else 0; thm = mh["ケース数"].apply(to_int).sum() if not mh.empty else 0
                    k1,k2,k3,k4 = st.columns(4)
                    k1.metric("出荷合計",f"{tho:,} cs"); k2.metric("製造合計",f"{thm:,} cs"); k3.metric("差引",f"{thm-tho:+,} cs"); k4.metric("現在庫",f"{cs.get(dp,0):,} cs")
                    ch1, ch2 = st.columns(2)
                    with ch1:
                        st.markdown('<div style="font-size:13px;font-weight:800;color:#DC2626;border-left:4px solid #DC2626;padding-left:8px;">🚚 出荷履歴</div>', unsafe_allow_html=True)
                        if not ph.empty: st.dataframe(ph.assign(日付=ph["納品予定日"].apply(format_date_jp))[["日付","顧客名","ケース数","備考"]].sort_values("日付",ascending=False), hide_index=True)
                    with ch2:
                        st.markdown('<div style="font-size:13px;font-weight:800;color:#059669;border-left:4px solid #059669;padding-left:8px;">🏭 製造履歴</div>', unsafe_allow_html=True)
                        if not mh.empty: st.dataframe(mh.assign(日付=mh["製造予定日"].apply(format_date_jp))[["日付","ケース数","備考"]].sort_values("日付",ascending=False).style.apply(lambda r: ["background:#F8FAFC;color:#64748B;"]*len(r) if "【在庫非反映】" in str(r.get("備考","")) else [""]*len(r), axis=1), hide_index=True)

                st.markdown('<div class="section-title">📅 今後60日間スケジュール</div>', unsafe_allow_html=True)
                pof = odf[(odf["製品名"]==dp)&(pd.to_datetime(odf["納品予定日"],errors='coerce')>=today)] if not odf.empty else pd.DataFrame()
                pmf = mdf[(mdf["製品名"]==dp)&(pd.to_datetime(mdf["製造予定日"],errors='coerce')>=today)&(~mdf["備考"].fillna("").str.contains("【在庫非反映】"))] if not mdf.empty else pd.DataFrame()
                dtl = []; ts = cs.get(dp,0)
                for d2 in pd.date_range(today, today+timedelta(days=59)):
                    do = pof[safe_dt_date(pof["納品予定日"])==d2.date()] if not pof.empty else pd.DataFrame()
                    oq = to_int(do["ケース数"].sum()) if not do.empty else 0
                    dm = pmf[safe_dt_date(pmf["製造予定日"])==d2.date()] if not pmf.empty else pd.DataFrame()
                    iq = to_int(dm["ケース数"].sum()) if not dm.empty else 0
                    ts += (iq-oq)
                    if iq>0 or oq>0 or ts<0: dtl.append({"日付":format_date_jp(d2),"製造(入)":iq or "","出荷(出)":oq or "","予定在庫":ts})
                if dtl:
                    dfd = pd.DataFrame(dtl)
                    fig = go.Figure()
                    fig.add_trace(go.Bar(x=dfd["日付"],y=[r["製造(入)"] if r["製造(入)"]!="" else 0 for _,r in dfd.iterrows()],name="製造",marker_color="#10B981"))
                    fig.add_trace(go.Bar(x=dfd["日付"],y=[-(r["出荷(出)"] if r["出荷(出)"]!="" else 0) for _,r in dfd.iterrows()],name="出荷",marker_color="#F43F5E"))
                    fig.add_trace(go.Scatter(x=dfd["日付"],y=dfd["予定在庫"],name="予定在庫",mode="lines+markers",line=dict(color="#2563EB",width=2.5)))
                    fig.update_layout(barmode="relative",hovermode="x unified",margin=dict(l=10,r=10,t=30,b=10),height=320); st.plotly_chart(fig, use_container_width=True)
                    st.dataframe(dfd.style.map(lambda v: 'color:#DC2626;font-weight:900;background-color:#FEE2E2;' if isinstance(v,(int,float)) and v<0 else '',subset=["予定在庫"]), hide_index=True)
                else: st.info("予定なし")
                st.markdown('</div>', unsafe_allow_html=True)

    with t2:
        html = '<table class="sched-table"><tr><th style="width:130px;">日付</th><th style="width:38%;">🏭 製造 / リパック</th><th style="width:44%;">🚚 出荷 / 不良廃棄</th></tr>'
        for i in range(7):
            d2 = today+timedelta(days=i); mh=""; oh=""
            if not mdf.empty:
                for _,r in mdf[pd.to_datetime(mdf["製造予定日"],errors='coerce').dt.normalize()==d2].iterrows():
                    bg,bc = ("#DBEAFE","#1E3A8A") if r.get("リパックフラグ") in [True,"TRUE"] else ("#F0FFF4","#10B981")
                    mh+=f'<div style="background:{bg};border-left:4px solid {bc};padding:6px;margin-bottom:4px;"><b>{fn(r["製品名"])}</b><span style="float:right;">{to_int(r.get("ケース数",0))}cs</span></div>'
            if not odf.empty:
                for _,r in odf[pd.to_datetime(odf["納品予定日"],errors='coerce').dt.normalize()==d2].iterrows():
                    sod=fs.get(r["製品名"],{}).get(d2,0)
                    if r.get("荷姿チェック") in [True,"TRUE"]: qh,bg,bc = f'<span style="text-decoration:line-through;">{to_int(r.get("ケース数",0))}cs</span>',"#D1FAE5","#059669"
                    elif sod<0: qh,bg,bc = f'<span class="shortage-red">{to_int(r.get("ケース数",0))}cs(不足)</span>',"#FEE2E2","#DC2626"
                    else: qh,bg,bc = f'<span style="color:#1D4ED8;font-weight:900;">{to_int(r.get("ケース数",0))}cs</span>',"#F0F7FF","#2563EB"
                    oh+=f'<div style="background:{bg};border-left:4px solid {bc};padding:6px;margin-bottom:4px;"><b>{r["顧客名"]}: {fn(r["製品名"])}</b><span style="float:right;">{qh}</span></div>'
            html+=f'<tr><td><b>{format_date_jp(d2)}</b></td><td>{mh or "なし"}</td><td>{oh or "なし"}</td></tr>'
        st.markdown(html+'</table>', unsafe_allow_html=True)

    with t3:
        sec("🔍 製品別 詳細ビュー")
        cfd = st.pills("カテ詳細", CATS, default=CATS[0], label_visibility="collapsed"); c_det = cfd.split(" ",1)[1] if cfd else CATS[0].split(" ",1)[1]
        sc1, sc2 = st.columns([1.5,2.5]); s_d = sc1.text_input("🔍 検索", key="sd")
        p_d = [p for p in mst_u["製品名"].tolist() if s_d in p] if s_d else mst_u[mst_u["大カテゴリ"]==c_det]["製品名"].tolist() if not mst_u.empty else []
        sp = sc2.selectbox("製品", options=p_d, index=None, format_func=fn)
        if sp:
            oy = today-timedelta(days=365)
            poa = odf[(odf["製品名"]==sp)&(pd.to_datetime(odf["納品予定日"],errors='coerce')>=oy)&(pd.to_datetime(odf["納品予定日"],errors='coerce')<today)] if not odf.empty else pd.DataFrame()
            pma = mdf[(mdf["製品名"]==sp)&(pd.to_datetime(mdf["製造予定日"],errors='coerce')>=oy)&(pd.to_datetime(mdf["製造予定日"],errors='coerce')<today)] if not mdf.empty else pd.DataFrame()
            k1,k2,k3,k4 = st.columns(4); k1.metric("現在庫",f"{cs.get(sp,0):,} cs"); k2.metric("過去1年 出荷",f"{poa['ケース数'].apply(to_int).sum() if not poa.empty else 0:,} cs"); k3.metric("過去1年 製造",f"{pma['ケース数'].apply(to_int).sum() if not pma.empty else 0:,} cs"); k4.metric("7日以内 欠品日数",f"{sum(1 for d in pd.date_range(today,today+timedelta(days=7)) if fs.get(sp,{}).get(d,0)<0)} 日")
            dth, dtf, dtg = st.tabs(["📜 履歴", "📅 予定", "📈 月次グラフ"])
            with dth:
                with st.expander("➕ 過去の製造実績を登録（在庫非反映）", expanded=False):
                    h1,h2,h3 = st.columns([1,1,2]); hd = h1.date_input("日", value=today-timedelta(days=1)); hq = h2.number_input("数", min_value=1, step=1); hr = h3.text_input("備考", placeholder="過去実績")
                    if st.button("💾 登録（非反映）"): app_sync("manufactures", pd.DataFrame([{"ID":str(uuid.uuid4())[:6].upper(),"製造予定日":pd.to_datetime(hd),"大カテゴリ":c_det,"製品名":sp,"ケース数":to_int(hq),"リパックフラグ":False,"備考":f"【在庫非反映】 {hr}".strip(),"登録日時":datetime.now()}])); st.rerun()
                tc1, tc2 = st.columns(2)
                with tc1:
                    st.markdown('<div style="font-weight:800;color:#DC2626;border-left:4px solid #DC2626;padding-left:8px;">🚚 出荷履歴</div>', unsafe_allow_html=True)
                    if not poa.empty: st.dataframe(poa.assign(日付=poa["納品予定日"].apply(format_date_jp))[["日付","顧客名","ケース数","備考"]].sort_values("日付",ascending=False), hide_index=True)
                with tc2:
                    st.markdown('<div style="font-weight:800;color:#059669;border-left:4px solid #059669;padding-left:8px;">🏭 製造履歴</div>', unsafe_allow_html=True)
                    if not pma.empty: st.dataframe(pma.assign(日付=pma["製造予定日"].apply(format_date_jp))[["日付","ケース数","備考"]].sort_values("日付",ascending=False).style.apply(lambda r: ["background:#F8FAFC;color:#64748B;"]*len(r) if "【在庫非反映】" in str(r.get("備考","")) else [""]*len(r), axis=1), hide_index=True)
            with dtg:
                gr = []
                if not poa.empty:
                    po_m = poa.copy(); po_m["年月"] = pd.to_datetime(po_m["納品予定日"],errors='coerce').dt.to_period("M").astype(str)
                    for ym, g in po_m.groupby("年月"): gr.append({"年月": ym, "種別": "出荷(実績)", "ケース数": g["ケース数"].apply(to_int).sum()})
                if not pma.empty:
                    pm_m = pma.copy(); pm_m["年月"] = pd.to_datetime(pm_m["製造予定日"],errors='coerce').dt.to_period("M").astype(str)
                    for ym, g in pm_m.groupby("年月"): gr.append({"年月": ym, "種別": "製造(実績)", "ケース数": g["ケース数"].apply(to_int).sum()})
                fo = odf[(odf["製品名"]==sp)&(pd.to_datetime(odf["納品予定日"],errors='coerce')>=today)] if not odf.empty else pd.DataFrame()
                vm3 = mdf[~mdf["備考"].fillna("").str.contains("【在庫非反映】")] if not mdf.empty else pd.DataFrame()
                fm = vm3[(vm3["製品名"]==sp)&(pd.to_datetime(vm3["製造予定日"],errors='coerce')>=today)] if not vm3.empty else pd.DataFrame()
                if not fo.empty:
                    fom = fo.copy(); fom["年月"] = pd.to_datetime(fom["納品予定日"],errors='coerce').dt.to_period("M").astype(str)
                    for ym, g in fom.groupby("年月"): gr.append({"年月": ym, "種別": "出荷(予定)", "ケース数": g["ケース数"].apply(to_int).sum()})
                if not fm.empty:
                    fmm = fm.copy(); fmm["年月"] = pd.to_datetime(fmm["製造予定日"],errors='coerce').dt.to_period("M").astype(str)
                    for ym, g in fmm.groupby("年月"): gr.append({"年月": ym, "種別": "製造(予定)", "ケース数": g["ケース数"].apply(to_int).sum()})
                if gr:
                    dg = pd.DataFrame(gr).sort_values("年月")
                    fig = px.bar(dg, x="年月", y="ケース数", color="種別", barmode="group", color_discrete_map={"出荷(実績)":"#F43F5E","出荷(予定)":"#FCA5A5","製造(実績)":"#10B981","製造(予定)":"#6EE7B7"}, title=f"【{sp}】 月次 製造・出荷量 / 今月: {today.strftime('%Y-%m')}")
                    st.plotly_chart(fig, use_container_width=True)

    with t4:
        sec("👤 顧客別 今後の予定")
        cl = sorted(odf[odf["顧客名"].str.strip()!=""]["顧客名"].unique().tolist()) if not odf.empty else []
        sc1c,sc2c = st.columns([1.5,2.5]); sc_c = sc1c.text_input("🔍 顧客検索"); sl_c = sc2c.selectbox("顧客", options=[c for c in cl if sc_c in c] if sc_c else cl, index=None)
        if sl_c:
            co = odf[(odf["顧客名"]==sl_c)&(pd.to_datetime(odf["納品予定日"],errors='coerce')>=today)].copy()
            if co.empty: st.info("予定なし")
            else:
                co=co.sort_values("納品予定日"); co["在庫状況"]=co.apply(lambda r: f"❌ 欠品 ({fs.get(r['製品名'],{}).get(pd.Timestamp(r['納品予定日']).normalize(),0)})" if fs.get(r['製品名'],{}).get(pd.Timestamp(r['納品予定日']).normalize(),0)<0 else "✅ OK",axis=1)
                co["納品予定日"]=co["納品予定日"].apply(format_date_jp)
                st.dataframe(co[["納品予定日","製品名","ケース数","在庫状況","備考"]].style.map(lambda v: 'color:#DC2626;font-weight:bold;background-color:#FEE2E2;' if "❌" in str(v) else '', subset=["在庫状況"]), hide_index=True)

# ─────────────────────────────────────────────
# ⭐ 特注・チャータースケジュール
# ─────────────────────────────────────────────
elif pg == "⭐ 特注・チャータースケジュール":
    page_header("⭐ 特注・チャータースケジュール")
    spo = odf[odf["備考"].apply(is_special_order)].copy() if not odf.empty else pd.DataFrame()
    ts1, ts2, ts3 = st.tabs(["📋 一覧","📅 製品別スケジュール","✏️ 編集・保存"])
    with ts1:
        if spo.empty: st.info("なし")
        else:
            spo["種別"] = spo["備考"].apply(lambda r: "特注+チャーター便" if "特注" in str(r) and "チャーター便" in str(r) else ("特注" if "特注" in str(r) else "チャーター便"))
            spo["納品予定日(表示)"] = spo["納品予定日"].apply(format_date_jp)
            sm = pd.merge(spo, sp_s[["受注ID","出荷予定日"]].rename(columns={"受注ID":"ID"}), on="ID", how="left") if not sp_s.empty else spo.assign(出荷予定日="（未設定）")
            if "出荷予定日" in sm and pd.api.types.is_datetime64_any_dtype(sm["出荷予定日"]): sm["出荷予定日"] = sm["出荷予定日"].apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "（未設定）")
            sc = [c for c in ["種別","顧客名","納品予定日(表示)","出荷予定日","製品名","ケース数","備考"] if c in sm.columns]
            st.dataframe(sm[sc].style.apply(lambda r: ['background-color:#F3E8FF;font-weight:bold;']*len(r) if "特注" in str(r.get("種別","")) and "チャーター" in str(r.get("種別","")) else (['background-color:#EDE9FE;font-weight:bold;']*len(r) if "特注" in str(r.get("種別","")) else ['background-color:#E0F2FE;font-weight:bold;']*len(r)), axis=1), hide_index=True)
    with ts2:
        if not spo.empty:
            pl = sorted(spo["製品名"].unique().tolist()); sl = st.selectbox("製品", ["（全製品）"]+pl)
            fsp = (spo.copy() if sl=="（全製品）" else spo[spo["製品名"]==sl].copy()).sort_values("納品予定日")
            fsp["納品予定日(表示)"] = fsp["納品予定日"].apply(format_date_jp)
            fsm = pd.merge(fsp, sp_s[["受注ID","出荷予定日"]].rename(columns={"受注ID":"ID"}), on="ID", how="left") if not sp_s.empty else fsp.assign(出荷予定日="（未設定）")
            if "出荷予定日" in fsm and pd.api.types.is_datetime64_any_dtype(fsm["出荷予定日"]): fsm["出荷予定日"] = fsm["出荷予定日"].apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "（未設定）")
            st.dataframe(fsm[[c for c in ["製品名","顧客名","納品予定日(表示)","出荷予定日","ケース数","備考"] if c in fsm.columns]], hide_index=True)
    with ts3:
        if not spo.empty:
            ex = sp_s["受注ID"].tolist() if not sp_s.empty else []; nr = [{"ID":str(uuid.uuid4())[:6].upper(),"受注ID":r["ID"],"製品名":r["製品名"],"顧客名":r["顧客名"],"納品予定日":r["納品予定日"],"出荷予定日":r["納品予定日"]-timedelta(days=1) if pd.notnull(r["納品予定日"]) else None,"備考":r.get("備考",""),"更新日時":datetime.now()} for _,r in spo.iterrows() if r["ID"] not in ex]
            sw = pd.concat([sp_s, pd.DataFrame(nr)], ignore_index=True) if nr else sp_s.copy()
            se = pd.merge(sw, odf[["ID","備考"]].rename(columns={"ID":"受注ID","備考":"受注備考"}), on="受注ID", how="left")
            se["種別"] = se["受注備考"].apply(lambda x: "特注" if "特注" in str(x) else "チャーター便"); se["納品予定日(表示)"] = pd.to_datetime(se["納品予定日"],errors='coerce').apply(format_date_jp); se["出荷予定日_edit"] = pd.to_datetime(se["出荷予定日"],errors='coerce').dt.date
            ed = st.data_editor(se[[c for c in ["ID","種別","製品名","顧客名","納品予定日(表示)","出荷予定日_edit","備考"] if c in se.columns]], hide_index=True, column_config={"ID":None,"種別":st.column_config.TextColumn(disabled=True),"製品名":st.column_config.TextColumn(disabled=True),"顧客名":st.column_config.TextColumn(disabled=True),"納品予定日(表示)":st.column_config.TextColumn(disabled=True),"出荷予定日_edit":st.column_config.DateColumn("📅 出荷予定日",format="YYYY/MM/DD")})
            _sp_save_msg = st.empty()
            if st.button("💾 保存", type="primary"):
                for i, r in ed.iterrows():
                    m = sw["ID"]==se.iloc[i]["ID"]
                    if r.get("出荷予定日_edit"): sw.loc[m,"出荷予定日"] = pd.to_datetime(r.get("出荷予定日_edit"))
                    sw.loc[m,"備考"] = str(r.get("備考","")); sw.loc[m,"更新日時"] = datetime.now()
                save_sync("special_schedule", sw)
                flash("success", "✅ 特注スケジュールを保存しました。"); st.rerun()
            show_flash_inline(_sp_save_msg)

# ─────────────────────────────────────────────
# 📈 経営・分析ダッシュボード
# ─────────────────────────────────────────────
elif pg == "📈 経営・分析ダッシュボード":
    page_header("📈 経営・製造管理 ダッシュボード")
    td1,td2,td3,td4 = st.tabs(["🏠 経営サマリ","📦 製品・ABC分析","🏭 製造効率分析","📅 月次トレンド"])
    with td1:
        if not odf.empty:
            tm = date.today().replace(day=1); om = odf[(safe_dt_date(odf["納品予定日"])>=tm)&(odf["不良廃棄フラグ"]==False)]
            c1,c2,c3,c4 = st.columns(4); c1.metric("今月 出荷", f"{om['ケース数'].apply(to_int).sum():,} cs", delta=f"{om['顧客名'].nunique()} 顧客"); c2.metric("今月 不良", f"{odf[(safe_dt_date(odf['納品予定日'])>=tm)&(odf['不良廃棄フラグ']==True)]['ケース数'].apply(to_int).sum():,} cs", delta_color="inverse"); c3.metric("荷姿チェック率", f"{int(len(odf[odf['荷姿チェック']==True])/max(len(odf),1)*100)} %"); c4.metric("欠品品目数", f"{sum(1 for v in cs.values() if v<=0)} 品目", delta_color="inverse")
            ca,cb = st.columns(2)
            with ca:
                ss = odf[odf["運送会社"].str.strip()!=""]["運送会社"].value_counts().reset_index()
                if not ss.empty: ss.columns=["運","件"]; st.plotly_chart(px.pie(ss,names="運",values="件",title="運送会社別"), use_container_width=True)
            with cb:
                cua = odf[odf["顧客名"]!="未指定"].groupby("顧客名")["ケース数"].apply(lambda x: x.apply(to_int).sum()).reset_index().sort_values("ケース数",ascending=False).head(5)
                if not cua.empty: st.plotly_chart(px.bar(cua,x="ケース数",y="顧客名",orientation='h',title="主要顧客 TOP5"), use_container_width=True)
    with td2:
        if not odf.empty:
            o2 = odf[odf["不良廃棄フラグ"]==False].copy(); o2["ケース数"] = o2["ケース数"].apply(to_int); abc = o2.groupby("製品名")["ケース数"].sum().reset_index().sort_values("ケース数",ascending=False)
            if abc["ケース数"].sum()>0:
                abc["累計比率"] = abc["ケース数"].cumsum()/abc["ケース数"].sum()*100; abc["ランク"] = pd.cut(abc["累計比率"],bins=[0,70,90,100],labels=["A(主力)","B(中堅)","C(その他)"])
                st.plotly_chart(px.bar(abc.head(20),x="製品名",y="ケース数",color="ランク",title="ABC TOP20"), use_container_width=True)
    with td3:
        if not mdf.empty:
            mt = mdf[safe_dt_date(mdf["製造予定日"])>=date.today().replace(day=1)]; tc = mt["ケース数"].apply(to_int).sum(); rc = mt[mt["リパックフラグ"]==True]["ケース数"].apply(to_int).sum()
            c1,c2 = st.columns(2); c1.metric("今月 製造",f"{tc:,} cs"); c2.metric("今月 リパック",f"{rc:,} cs",delta=f"{int(rc/max(tc,1)*100)}%")
            st.plotly_chart(px.histogram(mdf,x="製造予定日",y="ケース数",color="大カテゴリ",barmode="stack",title="推移"), use_container_width=True)
        if p_sum: st.dataframe(pd.DataFrame([{"資材":k,"庫":v["現在庫"],"点":v["発注点"],"出":v["出庫"]} for k,v in p_sum.items()]).style.apply(lambda r: ['background-color:#FFEDD5;color:#C2410C;']*len(r) if to_int(r.get("庫",0))<to_int(r.get("点",0)) else ['']*len(r), axis=1), hide_index=True)
    with td4:
        if not odf.empty:
            tdf = odf[odf["不良廃棄フラグ"]==False].copy(); tdf["年月"] = pd.to_datetime(tdf["納品予定日"],errors='coerce').dt.to_period("M").astype(str)
            mn = tdf.groupby(["年月","大カテゴリ"])["ケース数"].apply(lambda x: x.apply(to_int).sum()).reset_index()
            if not mn.empty: st.plotly_chart(px.bar(mn,x="年月",y="ケース数",color="大カテゴリ",barmode="stack",title="月次カテ別"), use_container_width=True)

# ─────────────────────────────────────────────
# ⚙️ マスタ・分析
# ─────────────────────────────────────────────
elif pg == "⚙️ マスタ・分析":
    page_header("⚙️ マスタ")
    tm1,tm2,tm3,tm4 = st.tabs(["📦 製品","🏢 顧客","📦 資材","🚚 運送会社"])
    with tm1:
        em = st.data_editor(mst.copy(), num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"大カテゴリ":st.column_config.SelectboxColumn(options=[c.split(" ",1)[1] for c in CATS]),"使用資材名":st.column_config.SelectboxColumn(options=pk_m["資材名"].tolist() if not pk_m.empty else [])}, height=500)
        _m1_msg = st.empty()
        if st.button("💾 製品マスタ保存", type="primary"): save_sync("master", em); flash("success", "✅ 製品マスタを保存しました。"); st.rerun()
        show_flash_inline(_m1_msg)
    with tm2:
        ec = st.data_editor(cdf.copy(), num_rows="dynamic", use_container_width=True, hide_index=True)
        _m2_msg = st.empty()
        if st.button("💾 顧客マスタ保存", type="primary"): save_sync("customers", ec); flash("success", "✅ 顧客マスタを保存しました。"); st.rerun()
        show_flash_inline(_m2_msg)
    with tm3:
        ep = st.data_editor(pk_m.copy(), num_rows="dynamic", use_container_width=True, hide_index=True)
        _m3_msg = st.empty()
        if st.button("💾 資材マスタ保存", type="primary"): save_sync("packaging_master", ep); flash("success", "✅ 資材マスタを保存しました。"); st.rerun()
        show_flash_inline(_m3_msg)
    with tm4:
        es = st.data_editor(sh_m.copy(), num_rows="dynamic", use_container_width=True, hide_index=True)
        _m4_msg = st.empty()
        if st.button("💾 運送会社保存", type="primary"): save_sync("shipping_master", es); flash("success", "✅ 運送会社マスタを保存しました。"); st.rerun()
        show_flash_inline(_m4_msg)


# ══════════════════════════════════════════════════════════════════════════════
# 🏗️ 製造スケジューラー v3 ― ASPROVA級 こんにゃく工場特化エンジン
#
#  ■ 実装機能一覧
#  [A] 有限能力フォワード / バックワード スケジューリング
#  [B] TSP貪欲法 + 2-opt改善 による段取り順序最適化
#  [C] シフト別・時間帯別 人員配置（マスタ管理）
#  [D] 休憩 / 清掃 / メンテ 自動挿入（break_master）
#  [E] 製造ライン別 有限能力管理（facility_master）
#  [F] 段取りマトリクスDB（changeover_matrix）黒→白コンタミ強制90分
#  [G] 4工程展開（調合→成形→包装→レトルト）工程比率・人員マスタ化
#  [H] 確定スケジュール保存・版管理（schedule_confirmed）
#  [I] 日別タイムラインビュー（手動インライン調整）
#  [J] 納期遵守率 / 稼働率 / 段取りロス率 KPI
#  [K] 累積稼働グラフ / 人員山積み / 工程別負荷グラフ
#  [L] ドリルダウン：製品別スケジュール詳細
#  [M] アラート：納期遅れ / コンタミリスク / 人員不足 / ボトルネック
#  [N] スケジュール差分比較（現行版 vs 前回確定版）
#  [O] 製品パラメータ設定（マスタ拡張列を含む完全編集UI）
# ══════════════════════════════════════════════════════════════════════════════
elif pg == "🏗️ 製造スケジューラー":
    page_header("🏗️ 製造スケジューラー")

    # ─────────────────────────────────────────────────────────────────────
    # CSS
    # ─────────────────────────────────────────────────────────────────────
    st.markdown("""<style>
    .sched-kpi{background:white;border-radius:12px;padding:14px 18px;
      box-shadow:0 2px 8px rgba(0,0,0,.08);text-align:center;min-height:78px;}
    .sched-kpi .val{font-size:26px;font-weight:900;line-height:1.1;}
    .sched-kpi .lbl{font-size:11px;color:#64748B;margin-top:2px;}
    .warn-banner{background:#FEF3C7;border:1.5px solid #F59E0B;border-radius:10px;
      padding:9px 14px;margin-bottom:8px;font-weight:700;color:#92400E;}
    .ok-banner{background:#D1FAE5;border:1.5px solid #059669;border-radius:10px;
      padding:9px 14px;margin-bottom:8px;font-weight:700;color:#065F46;}
    .danger-banner{background:#FEE2E2;border:1.5px solid #DC2626;border-radius:10px;
      padding:9px 14px;margin-bottom:8px;font-weight:700;color:#991B1B;}
    .info-tip{background:#EFF6FF;border-radius:8px;padding:8px 13px;
      font-size:13px;color:#1E40AF;margin-bottom:8px;}
    .day-hdr{background:linear-gradient(90deg,#1E3A8A,#3B82F6);color:white;
      padding:7px 14px;border-radius:7px;font-weight:700;font-size:13px;margin:6px 0;}
    .diff-add{background:#D1FAE5;border-left:4px solid #059669;}
    .diff-del{background:#FEE2E2;border-left:4px solid #DC2626;text-decoration:line-through;}
    .diff-chg{background:#FEF3C7;border-left:4px solid #F59E0B;}
    </style>""", unsafe_allow_html=True)

    # ─────────────────────────────────────────────────────────────────────
    # ① 定数
    # ─────────────────────────────────────────────────────────────────────
    _PROCESSES = ["調合・練り", "成形・糊付け", "包装・充填", "レトルト・冷却"]
    _PCOLOR = {
        "調合・練り": "#7C3AED", "成形・糊付け": "#2563EB",
        "包装・充填": "#059669", "レトルト・冷却": "#0891B2",
        "段取り・洗浄": "#DC2626", "段取り": "#EA580C",
        "準備": "#D97706", "休憩": "#CBD5E1", "清掃": "#94A3B8", "メンテ": "#475569",
    }
    _KONJAC_TYPES = ["黒","白","糸","板","玉","三角","ダイス","冷凍","その他"]
    _SHIFT_COLS = ["シフトID","シフト名","曜日区分","開始時刻","終了時刻","出勤人数","うちキーマン数","優先ライン"]
    _BREAK_COLS = ["ルールID","種別","開始時刻","終了時刻","適用曜日","対象ライン","繰り返し"]
    _FACIL_COLS = ["ラインID","ライン名","ライン種別","最大能力(cs/h)","同時製造可否","適合段取りタイプ","稼働率(%)","優先順位"]
    _CO_COLS    = ["前工程タイプ","後工程タイプ","段取り時間(分)","コンタミリスク","適用ライン","備考"]
    _CONF_COLS  = ["版ID","スケジュールID","製品名","ライン","工程","開始日時","終了日時",
                   "製造量(cs)","配置人数","段取り時間(分)","コンタミリスク","ステータス","確定日時","確定者"]

    # ─────────────────────────────────────────────────────────────────────
    # ② マスタ読み込み（シート存在しない場合は初期データで自動作成）
    # ─────────────────────────────────────────────────────────────────────
    _SHIFT_INIT = [
        ["S01","早番","平日","08:00","12:00","5","1",""],
        ["S02","早番_午後","平日","13:00","17:00","8","2",""],
        ["S03","遅番","平日","17:00","21:00","4","1",""],
        ["S04","土曜","土曜","08:00","15:00","4","1",""],
    ]
    _BREAK_INIT = [
        ["BRK_L1","昼休憩","12:00","13:00","平日","全ライン","毎日"],
        ["BRK_CL","定時清掃","17:00","17:30","平日","全ライン","毎日"],
        ["BRK_LS","昼休憩","12:00","13:00","土曜","全ライン","毎週土"],
    ]
    _FACIL_INIT = [
        ["LINE_A","Aライン（糸・白）","糸","50","FALSE","糸,白,その他","85","1"],
        ["LINE_B","Bライン（板・玉）","板","40","FALSE","板,玉,三角,ダイス,その他","85","2"],
        ["LINE_C","Cライン（黒専用）","黒","35","FALSE","黒","85","3"],
        ["KAM_01","1号釜（レトルト）","レトルト","0","TRUE","全製品","90","4"],
    ]
    _CO_INIT = [
        ["黒","白","90","TRUE","全ライン","分解・徹底洗浄必須（コンタミ対策）"],
        ["黒","糸","90","TRUE","全ライン","分解・徹底洗浄必須"],
        ["黒","板","90","TRUE","全ライン","分解・徹底洗浄必須"],
        ["黒","玉","60","TRUE","全ライン","洗浄必須"],
        ["黒","三角","60","TRUE","全ライン","洗浄必須"],
        ["黒","ダイス","60","TRUE","全ライン","洗浄必須"],
        ["白","黒","30","FALSE","全ライン","通常洗浄"],
        ["白","糸","20","FALSE","全ライン","形状変更"],
        ["白","板","20","FALSE","全ライン","形状変更"],
        ["糸","板","30","FALSE","全ライン","成形機パーツ交換（30分）"],
        ["板","糸","30","FALSE","全ライン","成形機パーツ交換（30分）"],
        ["糸","白","30","FALSE","全ライン","通常洗浄"],
        ["板","白","30","FALSE","全ライン","通常洗浄"],
        ["冷凍","黒","45","TRUE","全ライン","温度対応+洗浄"],
        ["冷凍","白","45","TRUE","全ライン","温度対応+洗浄"],
        ["玉","糸","25","FALSE","全ライン","形状変更"],
        ["三角","板","20","FALSE","全ライン","形状変更"],
    ]

    @st.cache_data(ttl=120, show_spinner=False)
    def _load_sched_master(name, cols, init_rows):
        try:
            ws = sheet.worksheet(name)
            data = ws.get_all_values()
            if len(data) <= 1:
                df = pd.DataFrame(init_rows, columns=cols) if init_rows else pd.DataFrame(columns=cols)
                return df
            df = pd.DataFrame(data[1:], columns=data[0])
            df.columns = df.columns.str.strip()
            return df.reindex(columns=cols, fill_value="")
        except Exception:
            return pd.DataFrame(init_rows, columns=cols) if init_rows else pd.DataFrame(columns=cols)

    def _save_sched_master(name, df):
        try:
            try: ws = sheet.worksheet(name)
            except: ws = sheet.add_worksheet(title=name, rows="500", cols="25")
            ws.clear()
            ds = df.copy().fillna("").astype(str)
            ws.update(values=[ds.columns.tolist()] + ds.values.tolist(), range_name="A1")
            st.cache_data.clear()
        except Exception as e:
            st.error(f"保存エラー ({name}): {e}")

    # ── セッションキャッシュ（初回のみGSSアクセス）
    if "v3_initialized" not in st.session_state:
        st.session_state.v3_shift  = _load_sched_master("shift_master",    _SHIFT_COLS, _SHIFT_INIT)
        st.session_state.v3_break  = _load_sched_master("break_master",    _BREAK_COLS, _BREAK_INIT)
        st.session_state.v3_facil  = _load_sched_master("facility_master", _FACIL_COLS, _FACIL_INIT)
        st.session_state.v3_co     = _load_sched_master("changeover_matrix", _CO_COLS,  _CO_INIT)
        st.session_state.v3_conf   = _load_sched_master("schedule_confirmed", _CONF_COLS, [])
        st.session_state.v3_manual_order = []
        st.session_state.v3_initialized  = True

    _sdf  = st.session_state.v3_shift
    _bdf  = st.session_state.v3_break
    _fdf  = st.session_state.v3_facil
    _cdf  = st.session_state.v3_co
    _cfdf = st.session_state.v3_conf

    # ─────────────────────────────────────────────────────────────────────
    # ③ ヘルパー関数
    # ─────────────────────────────────────────────────────────────────────
    def _ktype(pn):
        """製品名 or マスタ段取りタイプ列からこんにゃくタイプを返す"""
        if not mst_u.empty:
            r = mst_u[mst_u["製品名"] == pn]
            if not r.empty and "段取りタイプ" in r.columns:
                t = str(r.iloc[0].get("段取りタイプ","")).strip()
                if t and t not in ("","nan"): return t
        n = str(pn)
        if "黒" in n or "海藻" in n: return "黒"
        if "白" in n or "生芋" in n or "精粉" in n: return "白"
        if "糸" in n or "しらたき" in n: return "糸"
        if "板" in n or "平" in n: return "板"
        if "玉" in n: return "玉"
        if "三角" in n or "△" in n: return "三角"
        if "ダイス" in n: return "ダイス"
        if "冷凍" in n: return "冷凍"
        return "その他"

    def _gpp(pn):
        """製品パラメータ取得（マスタ拡張列対応・ZeroDivision安全）"""
        d = {"時間あたり生産量":10,"歩留まり率":95,"リードタイム時間":1,"安全在庫数":0,
             "段取りグループ":"","段取りタイプ":"その他",
             "調合比率":0.15,"成形比率":0.35,"包装比率":0.35,"レトルト比率":0.15,
             "最少人員_調合":1,"最少人員_成形":2,"最少人員_包装":2,"最少人員_レトルト":1,
             "キーマン必要":True,"ラインID":"","最小製造ロット":1}
        if mst_u.empty or not pn: return d
        r = mst_u[mst_u["製品名"] == pn]
        if r.empty: return d
        row = r.iloc[0]
        def _fi(k, dv): return max(dv, to_int(row.get(k, dv)))
        def _ff(k, dv): 
            try: return max(0.01, float(str(row.get(k, dv*100) or dv*100)) / 100.0)
            except: return dv
        # 工程比率を正規化（合計が0なら均等配分）
        ratios = {
            "調合比率":  _ff("調合比率",  0.15),
            "成形比率":  _ff("成形比率",  0.35),
            "包装比率":  _ff("包装比率",  0.35),
            "レトルト比率": _ff("レトルト比率", 0.15),
        }
        rs = sum(ratios.values())
        if rs < 0.01: ratios = {k: 0.25 for k in ratios}
        else: ratios = {k: v/rs for k, v in ratios.items()}
        return {
            "時間あたり生産量": max(1, _fi("時間あたり生産量", 10)),
            "歩留まり率":       max(1, min(100, _fi("歩留まり率", 95))),
            "リードタイム時間": max(0, _fi("リードタイム時間", 0)),
            "安全在庫数":       max(0, _fi("安全在庫数", 0)),
            "段取りグループ":   str(row.get("段取りグループ","") or ""),
            "段取りタイプ":     _ktype(pn),
            "調合比率":  ratios["調合比率"],
            "成形比率":  ratios["成形比率"],
            "包装比率":  ratios["包装比率"],
            "レトルト比率": ratios["レトルト比率"],
            "最少人員_調合":    max(1, _fi("最少人員_調合",   1)),
            "最少人員_成形":    max(1, _fi("最少人員_成形",   2)),
            "最少人員_包装":    max(1, _fi("最少人員_包装",   2)),
            "最少人員_レトルト":max(1, _fi("最少人員_レトルト",1)),
            "キーマン必要":     str(row.get("キーマン必要","TRUE")).upper() != "FALSE",
            "ラインID":         str(row.get("ラインID","") or ""),
            "最小製造ロット":   max(1, _fi("最小製造ロット", 1)),
        }

    def _build_co(df):
        m = {}
        if df.empty: return m
        for _, r in df.iterrows():
            try:
                k = (str(r["前工程タイプ"]).strip(), str(r["後工程タイプ"]).strip())
                m[k] = max(0, int(float(str(r.get("段取り時間(分)",0) or 0))))
            except: pass
        return m

    def _co_time(pf, pt, matrix):
        if not pf or not pt: return 0
        tf = _ktype(pf); tt = _ktype(pt)
        if tf == tt: return 0
        return matrix.get((tf,tt), matrix.get((tt,tf), 15))

    def _is_contam(pf, pt, co_df):
        if not pf: return False
        tf = _ktype(pf); tt = _ktype(pt)
        if not co_df.empty:
            r = co_df[(co_df["前工程タイプ"]==tf)&(co_df["後工程タイプ"]==tt)]
            if not r.empty: return str(r.iloc[0].get("コンタミリスク","FALSE")).upper()=="TRUE"
        return tf=="黒" and tt in ("白","糸","板")

    def _staff_at(dt, sdf):
        """(出勤人数, キーマン数)"""
        if sdf.empty: return (8,1)
        wd = dt.weekday()
        ws = "土曜" if wd==5 else ("日曜" if wd==6 else "平日")
        t  = dt.strftime("%H:%M")
        bs,bk = 0,0
        for _,row in sdf.iterrows():
            wk = str(row.get("曜日区分","平日"))
            if wk not in ("全日",ws): continue
            try:
                s = str(row.get("開始時刻","08:00")); e = str(row.get("終了時刻","17:00"))
                if s <= t < e:
                    bs = max(bs, max(0, int(float(str(row.get("出勤人数",0) or 0)))))
                    bk = max(bk, max(0, int(float(str(row.get("うちキーマン数",0) or 0)))))
            except: pass
        return (bs,bk)

    def _break_end(dt, bdf):
        """休憩中なら(True, 休憩終了時刻)、そうでなければ(False,None)"""
        if bdf.empty: return (False,None)
        wd = dt.weekday()
        ws = "土曜" if wd==5 else ("日曜" if wd==6 else "平日")
        t  = dt.strftime("%H:%M")
        for _,row in bdf.iterrows():
            aw = str(row.get("適用曜日","平日"))
            if "全日" not in aw and ws not in aw: continue
            try:
                s = str(row.get("開始時刻","12:00")); e = str(row.get("終了時刻","13:00"))
                if s <= t < e:
                    be = dt.normalize() + timedelta(hours=int(e[:2]), minutes=int(e[3:5]))
                    return (True, be)
            except: pass
        return (False,None)

    def _next_break_start(cur, bdf, day_end):
        """cur以降の最初の休憩開始時刻を返す（なければday_end）"""
        result = day_end
        if bdf.empty: return result
        wd = cur.weekday()
        ws = "土曜" if wd==5 else ("日曜" if wd==6 else "平日")
        for _,row in bdf.iterrows():
            aw = str(row.get("適用曜日","平日"))
            if "全日" not in aw and ws not in aw: continue
            try:
                s = str(row.get("開始時刻","12:00"))
                bs = cur.normalize() + timedelta(hours=int(s[:2]), minutes=int(s[3:5]))
                if bs > cur: result = min(result, bs)
            except: pass
        return result

    def _snap(cur, ws_h, we_h, sdf, bdf, min_staff=1):
        """cur を次の稼働可能時刻に進める（最大30日探索・無限ループ防止）"""
        _min_staff_eff = min(min_staff, 1)  # シフト未設定時は1人で動作
        for _ in range(30 * 24):  # 最大30日 × 24回/日
            day = cur.normalize()
            ds  = day + timedelta(hours=ws_h)
            de  = day + timedelta(hours=we_h)
            if cur < ds:
                cur = ds; continue
            if cur >= de:
                cur = (day + timedelta(days=1)).normalize() + timedelta(hours=ws_h); continue
            # 休憩中スキップ
            ib, be = _break_end(cur, bdf)
            if ib and be:
                cur = be; continue
            # シフト人員チェック（シフト未設定=0人なら制約なし）
            sv, _ = _staff_at(cur, sdf)
            if sv > 0 and sv < _min_staff_eff:
                cur += timedelta(hours=1); continue  # 30分→1時間で高速スキップ
            return cur
        return cur  # タイムアウト時はそのまま返す

    def _advance(cur, hours, ws_h, we_h, sdf, bdf, min_staff=1):
        """cur から hours 時間を確保。休憩・日跨ぎを自動分割。(終了時刻, セグメント[])を返す"""
        remaining = float(max(0, hours))
        if remaining < 1e-6:
            return cur, []
        _min_staff_eff = min(min_staff, 1)
        c = _snap(cur, ws_h, we_h, sdf, bdf, _min_staff_eff)
        segments = []
        for _ in range(200):  # 500→200 に削減
            if remaining < 1e-6:
                break
            day = c.normalize()
            de  = day + timedelta(hours=we_h)
            nbs = _next_break_start(c, bdf, de)
            avail = max(0.0, (min(nbs, de) - c).total_seconds() / 3600.0)
            if avail < 1e-6:
                # 次の稼働開始へジャンプ
                next_c = _snap(min(nbs, de), ws_h, we_h, sdf, bdf, _min_staff_eff)
                if next_c <= c:  # 進まない場合は強制翌日
                    next_c = (c.normalize() + timedelta(days=1)).normalize() + timedelta(hours=ws_h)
                c = next_c
                continue
            # シフト人員チェック
            sv, _ = _staff_at(c, sdf)
            if sv > 0 and sv < _min_staff_eff:
                next_c = _snap(c + timedelta(hours=1), ws_h, we_h, sdf, bdf, _min_staff_eff)
                if next_c <= c:
                    next_c = c + timedelta(hours=1)
                c = next_c
                continue
            take = min(remaining, avail)
            seg_end = c + timedelta(hours=take)
            segments.append((c, seg_end))
            remaining -= take
            if remaining < 1e-6:
                break
            next_c = _snap(seg_end, ws_h, we_h, sdf, bdf, _min_staff_eff)
            if next_c <= seg_end:  # 進まない場合は強制翌日
                next_c = (seg_end.normalize() + timedelta(days=1)).normalize() + timedelta(hours=ws_h)
            c = next_c
        final = segments[-1][1] if segments else cur
        return final, segments

    # ─────────────────────────────────────────────────────────────────────
    # ④ TSP + 2-opt 段取り順序最適化
    # ─────────────────────────────────────────────────────────────────────
    def _tsp_2opt(tasks, co_matrix):
        """貪欲法で初期解 → 2-opt改善（品目数≤15かつ最大10回に制限）"""
        if len(tasks) <= 1: return tasks

        def _cost(a, b):
            co = _co_time(a["製品名"], b["製品名"], co_matrix)
            pr = b.get("優先度", 5)
            dl = (b["出荷日"] - pd.Timestamp.today().normalize()).days \
                 if isinstance(b["出荷日"], pd.Timestamp) else 30
            return co * 0.4 + pr * 8 + max(0, dl) * 0.3

        def _total_cost(order):
            return sum(_cost(order[i], order[i+1]) for i in range(len(order)-1))

        # 貪欲初期解
        rem = sorted(tasks, key=lambda t: (
            t.get("優先度", 5),
            t["出荷日"] if isinstance(t["出荷日"], pd.Timestamp) else pd.Timestamp.today()
        ))
        ordered = [rem.pop(0)]
        while rem:
            best = min(rem, key=lambda t: _cost(ordered[-1], t))
            rem.remove(best); ordered.append(best)

        # 2-opt改善（品目数15以下・最大10回のみ実施）
        if len(ordered) <= 15:
            for _ in range(10):
                improved = False
                for i in range(1, len(ordered) - 1):
                    for j in range(i + 1, len(ordered)):
                        new_order = ordered[:i] + ordered[i:j+1][::-1] + ordered[j+1:]
                        if _total_cost(new_order) < _total_cost(ordered) - 0.1:
                            ordered = new_order; improved = True
                if not improved:
                    break
        return ordered

    # ─────────────────────────────────────────────────────────────────────
    # ⑤ 受注 → 製造タスク変換
    # ─────────────────────────────────────────────────────────────────────
    def _calc_tasks(hd, ws_h, we_h):
        tasks=[]; n=pd.Timestamp.today().normalize()
        if odf.empty: return tasks
        wh = max(1, we_h - ws_h)
        fo = odf[(odf["不良廃棄フラグ"]==False) &
                 (pd.to_datetime(odf["納品予定日"],errors="coerce")>=n) &
                 (pd.to_datetime(odf["納品予定日"],errors="coerce")<=n+timedelta(days=hd))].copy()
        fo["納品予定日"] = pd.to_datetime(fo["納品予定日"],errors="coerce")
        fo = fo.dropna(subset=["納品予定日"]).sort_values("納品予定日")
        if fo.empty: return tasks
        for pn, grp in fo.groupby("製品名"):
            pa=_gpp(pn); c_s=cs.get(pn,0)
            for _,row in grp.iterrows():
                ship_d=pd.Timestamp(row["納品予定日"]).normalize()
                oq=to_int(row.get("ケース数",0))
                ps=fs.get(pn,{}).get(ship_d,c_s)
                sh=oq-max(0,ps-pa["安全在庫数"])
                dl=(ship_d-n).days
                if sh<=0:
                    tasks.append({"製品名":pn,"顧客名":str(row.get("顧客名","")),"出荷日":ship_d,
                        "受注数(cs)":oq,"製造必要量(cs)":0,"製造時間(h)":0.,
                        "製造開始期限":ship_d,"優先度":5,"ステータス":"✅ 在庫充足",
                        "段取りG":pa["段取りグループ"],"歩留まり率":pa["歩留まり率"],
                        "ライン":pa["ラインID"]}); continue
                yr=pa["歩留まり率"]/100.
                mq=int(np.ceil(max(1,sh)/max(0.01,yr)))
                # 最小ロット適用
                lot=pa["最小製造ロット"]
                if lot>1: mq=int(np.ceil(mq/lot)*lot)
                spd=max(1,pa["時間あたり生産量"])
                mh=round(mq/spd,1)
                wd=max(1,int(np.ceil((mh+pa["リードタイム時間"])/wh)))
                sdl=ship_d-timedelta(days=wd)
                pr=1 if dl<=1 else 2 if dl<=3 else 3 if dl<=7 else 4 if dl<=14 else 5
                stt=("🔴 緊急" if sdl<=n else "🟠 要注意" if dl<=3
                     else "🟡 注意" if dl<=7 else "🟢 計画内")
                tasks.append({"製品名":pn,"顧客名":str(row.get("顧客名","")),"出荷日":ship_d,
                    "受注数(cs)":oq,"製造必要量(cs)":mq,"製造時間(h)":mh,
                    "製造開始期限":sdl,"優先度":pr,"ステータス":stt,
                    "段取りG":pa["段取りグループ"],"歩留まり率":pa["歩留まり率"],
                    "ライン":pa["ラインID"]})
        needed=[t for t in tasks if t["製造必要量(cs)"]>0]
        needed.sort(key=lambda t:(t["段取りG"] or "ZZZ",t["優先度"],t["出荷日"]))
        return needed+[t for t in tasks if t["製造必要量(cs)"]==0]

    # ─────────────────────────────────────────────────────────────────────
    # ⑥ メインスケジューリングエンジン
    # ─────────────────────────────────────────────────────────────────────
    def _engine(tasks_in, mode, start_dt, ws_h, we_h, co_matrix, sdf, bdf, co_df, do_2opt=True):
        res=[]
        if not tasks_in: return res
        ordered = _tsp_2opt(tasks_in, co_matrix) if do_2opt else sorted(
            tasks_in, key=lambda t:(t.get("優先度",5),
                t["出荷日"] if isinstance(t["出荷日"],pd.Timestamp) else pd.Timestamp.today()))

        if mode=="forward":
            cursor = pd.Timestamp(start_dt).normalize()+timedelta(hours=ws_h)
        else:
            latest=max((t["出荷日"] for t in ordered if isinstance(t["出荷日"],pd.Timestamp)),
                       default=pd.Timestamp.today()+timedelta(days=7))
            wh=max(1,we_h-ws_h)
            tot_h=sum(to_int(t.get("製造必要量(cs)",0))/max(1,_gpp(t["製品名"])["時間あたり生産量"])
                      +_gpp(t["製品名"])["リードタイム時間"] for t in ordered)
            tot_co=sum(_co_time(ordered[i]["製品名"],ordered[i+1]["製品名"],co_matrix)/60.
                       for i in range(len(ordered)-1))
            days=max(1,int(np.ceil((tot_h+tot_co)/wh)))
            cursor=(latest-timedelta(days=days)).normalize()+timedelta(hours=ws_h)
            cursor=_snap(cursor,ws_h,we_h,sdf,bdf,1)

        prev_pn=None
        PROC_MIN={"調合・練り":"最少人員_調合","成形・糊付け":"最少人員_成形",
                  "包装・充填":"最少人員_包装","レトルト・冷却":"最少人員_レトルト"}
        PROC_RATIO={"調合・練り":"調合比率","成形・糊付け":"成形比率",
                    "包装・充填":"包装比率","レトルト・冷却":"レトルト比率"}

        for task in ordered:
            pn=task["製品名"]; pa=_gpp(pn)
            mq=max(1,to_int(task.get("製造必要量(cs)",0)))
            mh=round(mq/max(1,pa["時間あたり生産量"]),2)
            lt=float(pa["リードタイム時間"])
            ship=task.get("出荷日",pd.NaT)
            line=pa["段取りグループ"] or pa["ラインID"] or "未割当"

            # 段取り
            com=_co_time(prev_pn,pn,co_matrix) if prev_pn else 0
            coh=com/60.; con=_is_contam(prev_pn,pn,co_df)
            if coh>0:
                ce_, _segs_co = _advance(cursor, coh, ws_h, we_h, sdf, bdf, 1)
                res.append({"区分":"🔴 段取り・洗浄" if con else "🟠 段取り",
                    "製品名":f"【{com}分洗浄】{_ktype(prev_pn)}→{_ktype(pn)}" if con
                             else f"【段取り{com}分】→{pn}",
                    "工程":"段取り・洗浄" if con else "段取り","ライン":line,
                    "開始":cursor,"終了":ce_,"所要時間(h)":round(coh,2),"製造量(cs)":0,
                    "出荷日":ship,"顧客名":task.get("顧客名",""),
                    "段取り時間(分)":com,"コンタミリスク":con,
                    "優先度":task.get("優先度",5),
                    "ステータス":"⚠️ 黒→白 要徹底洗浄" if con else "段取り",
                    "最少人数":1,"キーマン必要":con,"_segs":[]})
                cursor=ce_

            # 準備（リードタイム）
            if lt>0:
                lt_e,lt_segs=_advance(cursor,lt,ws_h,we_h,sdf,bdf,pa["最少人員_調合"])
                res.append({"区分":"🟡 準備","製品名":pn,"工程":"準備","ライン":line,
                    "開始":cursor,"終了":lt_e,"所要時間(h)":round(lt,2),"製造量(cs)":0,
                    "出荷日":ship,"顧客名":task.get("顧客名",""),
                    "段取り時間(分)":0,"コンタミリスク":False,
                    "優先度":task.get("優先度",5),"ステータス":task.get("ステータス",""),
                    "最少人数":pa["最少人員_調合"],"キーマン必要":pa["キーマン必要"],"_segs":lt_segs})
                cursor=lt_e

            # 4工程展開
            for proc in _PROCESSES:
                ph=round(mh*pa[PROC_RATIO[proc]],2)
                ms=pa[PROC_MIN[proc]]
                if ph<1e-6: continue
                pe,segs=_advance(cursor,ph,ws_h,we_h,sdf,bdf,ms)
                dok=True
                if isinstance(ship,pd.Timestamp) and pd.notnull(ship):
                    dok=pe.normalize()<=ship
                res.append({"区分":f"🏭 {proc}","製品名":pn,"工程":proc,"ライン":line,
                    "開始":cursor,"終了":pe,"所要時間(h)":ph,
                    "製造量(cs)":max(0,round(mq*pa[PROC_RATIO[proc]])),
                    "出荷日":ship,"顧客名":task.get("顧客名",""),
                    "段取り時間(分)":0,"コンタミリスク":False,
                    "優先度":task.get("優先度",5),
                    "ステータス":"🚨 納期遅れ" if not dok else task.get("ステータス",""),
                    "最少人数":ms,"キーマン必要":pa["キーマン必要"] and proc=="調合・練り",
                    "_segs":segs})
                cursor=pe

            prev_pn=pn
        return res

    # ─────────────────────────────────────────────────────────────────────
    # ⑦ コントロールバー
    # ─────────────────────────────────────────────────────────────────────
    with st.expander("⚙️ スケジューリング設定", expanded=True):
        r1c1,r1c2,r1c3,r1c4 = st.columns([2,1.5,1,1])
        hd         = r1c1.slider("📅 対象期間（日）",7,60,30,7)
        sched_mode = r1c2.radio("🔄 モード",["フォワード（前詰め）","バックワード（後詰め）"])
        show_ok    = r1c3.checkbox("✅ 充足品も表示",False)
        do_2opt    = r1c4.checkbox("🔧 2-opt最適化",True,help="段取り順序をさらに2-opt法で改善（少し重くなります）")
        r2c1,r2c2,r2c3,r2c4 = st.columns(4)
        start_date  = r2c1.date_input("📅 製造開始日",value=date.today(),key="v3_start")
        ws_h        = r2c2.number_input("🌅 稼働開始(時)",4,12,8,1,key="v3_ws")
        we_h        = r2c3.number_input("🌆 稼働終了(時)",12,24,17,1,key="v3_we")
        if we_h<=ws_h: we_h=ws_h+1
        conf_user   = r2c4.text_input("👤 確定者名",value="",placeholder="確定時に記録",key="v3_user")

    # ─────────────────────────────────────────────────────────────────────
    # ⑧ マスタ設定エクスパンダー群
    # ─────────────────────────────────────────────────────────────────────
    with st.expander("👷 シフト・人員マスタ"):
        st.markdown('<div class="info-tip">💡 時間帯ごとに行を分けて登録可能（例: 早番8〜12は5人、13〜17は8人）。スプレッドシートへ保存されます。</div>',unsafe_allow_html=True)
        _sh_ed = st.data_editor(_sdf.copy(),num_rows="dynamic",hide_index=True,
            use_container_width=True,height=min(280,len(_sdf)*38+60),
            column_config={
                "曜日区分":st.column_config.SelectboxColumn(options=["平日","土曜","日曜","全日"]),
                "出勤人数":st.column_config.NumberColumn(min_value=0,max_value=50,step=1),
                "うちキーマン数":st.column_config.NumberColumn(min_value=0,step=1),
            },key="v3_sh_ed")
        _sh_msg=st.empty()
        if st.button("💾 シフトマスタ保存",key="v3_save_sh"):
            _save_sched_master("shift_master",_sh_ed)
            st.session_state.v3_shift=_sh_ed.copy(); _sdf=_sh_ed.copy()
            flash("success","✅ シフトマスタを保存しました。"); st.rerun()
        show_flash_inline(_sh_msg)

    with st.expander("☕ 休憩・停止ルール"):
        st.markdown('<div class="info-tip">💡 登録した時間帯はスケジューラーが自動スキップします（昼休憩・清掃・メンテ）。</div>',unsafe_allow_html=True)
        _br_ed = st.data_editor(_bdf.copy(),num_rows="dynamic",hide_index=True,
            use_container_width=True,height=min(240,len(_bdf)*38+60),
            column_config={
                "種別":st.column_config.SelectboxColumn(options=["昼休憩","清掃","メンテ","朝礼","その他"]),
                "適用曜日":st.column_config.SelectboxColumn(options=["平日","土曜","日曜","全日"]),
            },key="v3_br_ed")
        _br_msg=st.empty()
        if st.button("💾 休憩ルール保存",key="v3_save_br"):
            _save_sched_master("break_master",_br_ed)
            st.session_state.v3_break=_br_ed.copy(); _bdf=_br_ed.copy()
            flash("success","✅ 休憩ルールを保存しました。"); st.rerun()
        show_flash_inline(_br_msg)

    with st.expander("🏭 製造ラインマスタ"):
        _fa_ed = st.data_editor(_fdf.copy(),num_rows="dynamic",hide_index=True,
            use_container_width=True,height=min(240,len(_fdf)*38+60),
            column_config={
                "ライン種別":st.column_config.SelectboxColumn(options=["糸","板","黒","玉","レトルト","汎用"]),
                "最大能力(cs/h)":st.column_config.NumberColumn(min_value=0,step=5),
                "同時製造可否":st.column_config.SelectboxColumn(options=["TRUE","FALSE"]),
                "稼働率(%)":st.column_config.NumberColumn(min_value=0,max_value=100),
                "優先順位":st.column_config.NumberColumn(min_value=1,step=1),
            },key="v3_fa_ed")
        _fa_msg=st.empty()
        if st.button("💾 ラインマスタ保存",key="v3_save_fa"):
            _save_sched_master("facility_master",_fa_ed)
            st.session_state.v3_facil=_fa_ed.copy()
            flash("success","✅ 製造ラインマスタを保存しました。"); st.rerun()
        show_flash_inline(_fa_msg)

    with st.expander("🧩 段取りマトリクス（分）"):
        st.markdown('<div class="info-tip">🚨 <b>黒→白切り替えは90分の徹底洗浄が必要です（コンタミ対策）。</b>変更はスプレッドシートへ保存されます。</div>',unsafe_allow_html=True)
        _co_ed = st.data_editor(_cdf.copy(),num_rows="dynamic",hide_index=True,
            use_container_width=True,height=min(420,len(_cdf)*38+60),
            column_config={
                "前工程タイプ":st.column_config.SelectboxColumn(options=_KONJAC_TYPES),
                "後工程タイプ":st.column_config.SelectboxColumn(options=_KONJAC_TYPES),
                "段取り時間(分)":st.column_config.NumberColumn(min_value=0,max_value=300,step=5),
                "コンタミリスク":st.column_config.SelectboxColumn(options=["TRUE","FALSE"]),
            },key="v3_co_ed")
        _co_msg=st.empty()
        if st.button("💾 段取りマトリクス保存",key="v3_save_co"):
            _save_sched_master("changeover_matrix",_co_ed)
            st.session_state.v3_co=_co_ed.copy(); _cdf=_co_ed.copy()
            flash("success","✅ 段取りマトリクスを保存しました。"); st.rerun()
        show_flash_inline(_co_msg)

    # ── スケジュール計算実行（スピナー付き）
    _co_matrix = _build_co(st.session_state.v3_co)
    all_tasks    = _calc_tasks(hd, ws_h, we_h)
    needed_tasks = [t for t in all_tasks if t["製造必要量(cs)"]>0]
    display_tasks = all_tasks if show_ok else needed_tasks

    # 手動並び替えが指定されていれば適用
    if st.session_state.v3_manual_order:
        pn_order = st.session_state.v3_manual_order
        needed_sorted = sorted(needed_tasks,
            key=lambda t: pn_order.index(t["製品名"]) if t["製品名"] in pn_order else 999)
        _tasks_for_engine = needed_sorted
    else:
        _tasks_for_engine = needed_tasks

    if _tasks_for_engine:
        with st.spinner(f"⚙️ スケジュールを計算中… ({len(_tasks_for_engine)}品目{'・2-opt最適化あり' if do_2opt else ''})"):
            _sched = _engine(
                _tasks_for_engine,
                mode="forward" if "フォワード" in sched_mode else "backward",
                start_dt=datetime.combine(start_date, datetime.min.time()),
                ws_h=float(ws_h), we_h=float(we_h),
                co_matrix=_co_matrix,
                sdf=st.session_state.v3_shift,
                bdf=st.session_state.v3_break,
                co_df=st.session_state.v3_co,
                do_2opt=do_2opt,
            )
    else:
        _sched = []

    # ─────────────────────────────────────────────────────────────────────
    # ⑩ KPI バナー（アスプローバ型）
    # ─────────────────────────────────────────────────────────────────────
    cnt_urg = sum(1 for t in needed_tasks if t["優先度"]<=2)
    cnt_cau = sum(1 for t in needed_tasks if t["優先度"]==3)
    cnt_pln = sum(1 for t in needed_tasks if t["優先度"]>=4)
    tot_h   = sum(t["製造時間(h)"] for t in needed_tasks)
    tot_cs  = sum(t["製造必要量(cs)"] for t in needed_tasks)

    mfg_rows_all = [r for r in _sched if r["工程"] in _PROCESSES]
    co_rows_all  = [r for r in _sched if r["工程"] in ("段取り・洗浄","段取り")]
    tot_mfg_h    = sum(r["所要時間(h)"] for r in mfg_rows_all)
    tot_co_h     = sum(r["所要時間(h)"] for r in co_rows_all)
    tot_op_h     = tot_mfg_h + tot_co_h
    util_rate    = round(tot_mfg_h/max(tot_op_h,0.01)*100,1)
    co_loss_rate = round(tot_co_h/max(tot_op_h,0.01)*100,1)
    _late_items  = list(dict.fromkeys(r["製品名"] for r in _sched if "納期遅れ" in str(r.get("ステータス",""))))
    _conts       = [r for r in _sched if r.get("コンタミリスク",False)]

    # 納期遵守率
    total_items = len(needed_tasks)
    on_time = total_items - len(set(_late_items))
    ddr = round(on_time/max(total_items,1)*100,1)

    k1,k2,k3,k4,k5,k6,k7 = st.columns(7)
    k1.markdown(f'<div class="sched-kpi"><div class="val" style="color:#DC2626;">{cnt_urg}</div><div class="lbl">🔴 緊急・要注意</div></div>',unsafe_allow_html=True)
    k2.markdown(f'<div class="sched-kpi"><div class="val" style="color:#D97706;">{cnt_cau}</div><div class="lbl">🟡 注意（7日以内）</div></div>',unsafe_allow_html=True)
    k3.markdown(f'<div class="sched-kpi"><div class="val" style="color:#2563EB;">{cnt_pln}</div><div class="lbl">🟢 計画内</div></div>',unsafe_allow_html=True)
    k4.markdown(f'<div class="sched-kpi"><div class="val" style="color:#7C3AED;">{tot_cs:,}</div><div class="lbl">📦 製造必要量(cs)</div></div>',unsafe_allow_html=True)
    k5.markdown(f'<div class="sched-kpi"><div class="val" style="color:#0891B2;">{util_rate}%</div><div class="lbl">⚙️ 製造稼働率</div></div>',unsafe_allow_html=True)
    k6.markdown(f'<div class="sched-kpi"><div class="val" style="color:#EA580C;">{co_loss_rate}%</div><div class="lbl">🔄 段取りロス率</div></div>',unsafe_allow_html=True)
    k7.markdown(f'<div class="sched-kpi"><div class="val" style="color:{"#059669" if ddr>=95 else "#DC2626"}">{ddr}%</div><div class="lbl">📅 納期遵守率</div></div>',unsafe_allow_html=True)
    st.markdown("<div style='margin-top:6px;'></div>",unsafe_allow_html=True)

    if cnt_urg>0:
        st.markdown(f'<div class="danger-banner">🚨 緊急・要注意 <b>{cnt_urg}件</b> あります。今すぐ製造計画を確認してください。</div>',unsafe_allow_html=True)
    if _late_items:
        st.markdown(f'<div class="warn-banner">⚠️ 納期遅れリスク：{"、".join(_late_items[:5])}{"…" if len(_late_items)>5 else ""} — 人員増強または順序見直しを検討してください。</div>',unsafe_allow_html=True)
    if _conts:
        st.markdown(f'<div class="danger-banner">🦠 黒→白 コンタミリスク：{len(_conts)}件の徹底洗浄工程が自動挿入されています。必ず実施してください。</div>',unsafe_allow_html=True)
    if not needed_tasks:
        st.markdown('<div class="ok-banner">✅ 直近の製造必要品目はありません。全品目在庫充足です。</div>',unsafe_allow_html=True)

    # ─────────────────────────────────────────────────────────────────────
    # ⑪ タブ構成（10タブ）
    # ─────────────────────────────────────────────────────────────────────
    T1,T2,T3,T4,T5,T6,T7,T8,T9,T10 = st.tabs([
        "📋 製造指示一覧",
        "📅 日別タイムライン",
        "📊 ガントチャート",
        "🔧 段取り最適化",
        "👷 人員配置",
        "📈 負荷グラフ",
        "📦 在庫推移",
        "🔍 ドリルダウン",
        "💾 スケジュール確定・比較",
        "⚙️ パラメータ設定",
    ])

    # ══════════════════════════════════════════════════════════════════════
    # タブ1：製造指示一覧
    # ══════════════════════════════════════════════════════════════════════
    with T1:
        if not display_tasks:
            st.success("✅ 対象期間内に製造が必要な品目はありません。")
        else:
            dft=pd.DataFrame(display_tasks)
            for c in ["出荷日","製造開始期限"]:
                if c in dft.columns:
                    dft[c]=dft[c].apply(lambda x: x.strftime("%Y/%m/%d")
                        if isinstance(x,(pd.Timestamp,datetime)) and pd.notnull(x) else str(x)[:10])
            sc=[c for c in ["優先度","ステータス","製品名","段取りG","ライン","顧客名","出荷日",
                             "受注数(cs)","製造必要量(cs)","製造時間(h)","製造開始期限","歩留まり率"]
                if c in dft.columns]
            def _rc(r):
                p=r.get("優先度",5)
                if p<=1: return ['background-color:#FEE2E2;font-weight:bold;']*len(r)
                if p==2: return ['background-color:#FFEDD5;font-weight:bold;']*len(r)
                if p==3: return ['background-color:#FFFBEB;']*len(r)
                if "充足" in str(r.get("ステータス","")): return ['background-color:#F0FDF4;color:#6B7280;']*len(r)
                return ['']*len(r)
            st.dataframe(dft[sc].style.apply(_rc,axis=1),hide_index=True,
                use_container_width=True,
                column_config={"優先度":st.column_config.NumberColumn(width="small"),
                    "製造時間(h)":st.column_config.NumberColumn(format="%.1f"),
                    "歩留まり率":st.column_config.NumberColumn("歩留まり(%)",format="%d")},
                height=min(700,max(280,len(dft)*38+60)))

            # 手動並び替えUI
            with st.expander("🔀 製造順序を手動で変更"):
                st.markdown('<div class="info-tip">💡 製品を並び替えると、段取りマトリクスを考慮した上でその順序でスケジュールを再計算します。</div>',unsafe_allow_html=True)
                _pns=[t["製品名"] for t in needed_tasks]
                if _pns:
                    _ord_df=pd.DataFrame({"順序":list(range(1,len(_pns)+1)),"製品名":_pns})
                    _ord_ed=st.data_editor(_ord_df,hide_index=True,use_container_width=True,
                        column_config={"順序":st.column_config.NumberColumn(min_value=1,step=1)},
                        key="v3_order_ed")
                    if st.button("🔄 この順序で再計算",key="v3_reorder"):
                        ordered_pns=_ord_ed.sort_values("順序")["製品名"].tolist()
                        st.session_state.v3_manual_order=ordered_pns
                        st.rerun()
                    if st.session_state.v3_manual_order:
                        if st.button("↩️ 自動最適化に戻す",key="v3_reset_order"):
                            st.session_state.v3_manual_order=[]; st.rerun()

            st.download_button("📥 製造指示CSVダウンロード",
                data=make_csv_bytes(dft[sc]),
                file_name=f"製造指示_{date.today()}.csv",mime="text/csv",use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════
    # タブ2：日別タイムライン
    # ══════════════════════════════════════════════════════════════════════
    with T2:
        st.markdown('<div class="section-title">📅 日別タイムライン（1日ビュー）</div>',unsafe_allow_html=True)
        if not _sched:
            st.info("スケジュールがありません。受注データを登録してください。")
        else:
            _dates=sorted(set(r["開始"].normalize().date()
                for r in _sched if isinstance(r["開始"],pd.Timestamp) and pd.notnull(r["開始"])))
            if not _dates:
                st.warning("スケジュール日付が生成できませんでした。")
            else:
                dc1,dc2=st.columns([2,2])
                sel_day=dc1.date_input("📅 表示日",value=_dates[0],
                    min_value=_dates[0],max_value=_dates[-1],key="v3_day")
                view_mode=dc2.radio("表示モード",["タイムライン","テーブル"],horizontal=True,key="v3_dvm")
                sel_ts=pd.Timestamp(sel_day)
                day_tasks=[r for r in _sched
                           if isinstance(r["開始"],pd.Timestamp)
                           and r["開始"].normalize().date()==sel_day]

                if not day_tasks:
                    st.info(f"📅 {sel_day.strftime('%Y/%m/%d')} は製造タスクなし（休日・休憩のみ）。")
                else:
                    # ── シフト人員サマリ（その日）
                    sh_summ=[]
                    for h_slot in range(ws_h,we_h):
                        dt_check=sel_ts+timedelta(hours=h_slot,minutes=30)
                        sv,km=_staff_at(dt_check,st.session_state.v3_shift)
                        sh_summ.append({"時間帯":f"{h_slot:02d}:00〜{h_slot+1:02d}:00","出勤人数":sv,"うちキーマン":km})
                    if sh_summ:
                        with st.expander(f"👷 {sel_day.strftime('%m/%d')} のシフト人員"):
                            st.dataframe(pd.DataFrame(sh_summ),hide_index=True,use_container_width=True)

                    if view_mode=="タイムライン":
                        tl=[]
                        for r in day_tasks:
                            s=r["開始"]; e=r["終了"]
                            if not isinstance(e,pd.Timestamp) or pd.isna(e): e=s+timedelta(minutes=30)
                            if e<=s: e=s+timedelta(minutes=15)
                            ship_s=(r["出荷日"].strftime("%m/%d")
                                    if isinstance(r["出荷日"],pd.Timestamp) and pd.notnull(r["出荷日"]) else "―")
                            tl.append({"タスク":r["製品名"][:16],"工程":r["工程"],
                                "Start":s,"Finish":e,"出荷日":ship_s,
                                "製造量":r.get("製造量(cs)",0),
                                "コンタミ":"🚨" if r.get("コンタミリスク") else ""})
                        fig_tl=px.timeline(pd.DataFrame(tl),x_start="Start",x_end="Finish",
                            y="タスク",color="工程",color_discrete_map=_PCOLOR,
                            hover_data=["出荷日","製造量","コンタミ"],
                            title=f"{sel_day.strftime('%Y/%m/%d(%a)')} 製造タイムライン"
                                  f"  稼働:{ws_h:02d}:00〜{we_h:02d}:00")
                        fig_tl.update_yaxes(autorange="reversed",title="")
                        fig_tl.update_xaxes(tickformat="%H:%M",
                            range=[sel_ts+timedelta(hours=ws_h-0.3),
                                   sel_ts+timedelta(hours=we_h+0.3)])
                        # 休憩帯グレー矩形
                        wd=sel_day.weekday()
                        ws_str="土曜" if wd==5 else ("日曜" if wd==6 else "平日")
                        for _,br in st.session_state.v3_break.iterrows():
                            aw=str(br.get("適用曜日","平日"))
                            if "全日" not in aw and ws_str not in aw: continue
                            try:
                                bs2=str(br["開始時刻"]); be2=str(br["終了時刻"])
                                bs_dt=sel_ts+timedelta(hours=int(bs2[:2]),minutes=int(bs2[3:5]))
                                be_dt=sel_ts+timedelta(hours=int(be2[:2]),minutes=int(be2[3:5]))
                                fig_tl.add_vrect(x0=bs_dt,x1=be_dt,fillcolor="#CBD5E1",
                                    opacity=0.35,line_width=0,
                                    annotation_text=str(br.get("種別","休憩")),
                                    annotation_position="top left")
                            except: pass
                        if pd.Timestamp.today().date()==sel_day:
                            fig_tl.add_vline(x=datetime.now(),line_dash="dash",
                                line_color="#DC2626",annotation_text="現在")
                        fig_tl.update_layout(margin=dict(l=10,r=10,t=50,b=10),
                            height=max(320,len(set(r["タスク"] for r in tl))*46+80),
                            legend=dict(orientation="h",yanchor="bottom",y=1.02,x=0),
                            plot_bgcolor="white")
                        st.plotly_chart(fig_tl,use_container_width=True)

                    # ── インライン調整テーブル
                    st.markdown('<div class="section-title">✏️ 手動調整（配置人数・工程）</div>',unsafe_allow_html=True)
                    adj=[]
                    for r in day_tasks:
                        s=r["開始"]; e=r["終了"]
                        adj.append({"工程区分":r["区分"],"製品名":r["製品名"][:20],
                            "工程":r["工程"],
                            "開始":s.strftime("%H:%M") if isinstance(s,pd.Timestamp) else "",
                            "終了":e.strftime("%H:%M") if isinstance(e,pd.Timestamp) else "",
                            "時間(h)":r.get("所要時間(h)",0),"製造量(cs)":r.get("製造量(cs)",0),
                            "配置人数":r.get("最少人数",1),
                            "🚨":r.get("ステータス","")})
                    adj_df=pd.DataFrame(adj)
                    ea=st.data_editor(adj_df,hide_index=True,use_container_width=True,
                        height=min(500,len(adj_df)*38+60),
                        column_config={
                            "工程区分":st.column_config.TextColumn(disabled=True,width="small"),
                            "製品名":st.column_config.TextColumn(disabled=True),
                            "工程":st.column_config.SelectboxColumn(options=list(_PCOLOR.keys())),
                            "開始":st.column_config.TextColumn("開始(HH:MM)"),
                            "終了":st.column_config.TextColumn(disabled=True),
                            "時間(h)":st.column_config.NumberColumn(format="%.2f",disabled=True),
                            "製造量(cs)":st.column_config.NumberColumn(disabled=True),
                            "配置人数":st.column_config.NumberColumn(min_value=0,max_value=20,step=1),
                        },key=f"v3_adj_{sel_day}")
                    # リアルタイム人員チェック
                    ref_dt=sel_ts+timedelta(hours=ws_h)
                    sv0,_=_staff_at(ref_dt,st.session_state.v3_shift)
                    ov=ea[ea["配置人数"].apply(to_int)>sv0]
                    if not ov.empty:
                        st.markdown(f'<div class="danger-banner">🚨 配置人数がシフト人数({sv0}人)を超える工程が{len(ov)}件あります。</div>',unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="ok-banner">✅ 全工程でシフト人数({sv0}人)以内です。</div>',unsafe_allow_html=True)
                    st.download_button(f"📥 {sel_day} 計画CSV",
                        data=make_csv_bytes(ea),
                        file_name=f"日別計画_{sel_day}.csv",mime="text/csv")

    # ══════════════════════════════════════════════════════════════════════
    # タブ3：ガントチャート
    # ══════════════════════════════════════════════════════════════════════
    with T3:
        if not _sched:
            st.info("スケジュールがありません。")
        else:
            gr=[]
            for r in _sched:
                try:
                    s=r["開始"]; e=r["終了"]
                    if not isinstance(s,pd.Timestamp): s=pd.Timestamp(s)
                    if not isinstance(e,pd.Timestamp): e=pd.Timestamp(e)
                    if pd.isna(s) or pd.isna(e): continue
                    if e<=s: e=s+timedelta(minutes=15)
                    gr.append({"タスク":r["製品名"][:18],"工程":r["工程"],
                        "ライン":r.get("ライン",""),"Start":s,"Finish":e,
                        "製造量":r.get("製造量(cs)",0),
                        "出荷日":(r["出荷日"].strftime("%m/%d")
                                 if isinstance(r["出荷日"],pd.Timestamp) and pd.notnull(r["出荷日"]) else "―"),
                        "コンタミ":"🚨" if r.get("コンタミリスク") else "",
                        "ステータス":r.get("ステータス","")})
                except: continue
            if gr:
                gdf=pd.DataFrame(gr)
                # ライン別 or タスク別 切替
                g_axis=st.radio("縦軸",["製品（タスク）","ラインID"],horizontal=True,key="v3_gaxis")
                y_col="タスク" if g_axis=="製品（タスク）" else "ライン"
                fig_g=px.timeline(gdf,x_start="Start",x_end="Finish",y=y_col,
                    color="工程",color_discrete_map=_PCOLOR,
                    hover_data=["タスク","ライン","製造量","出荷日","コンタミ","ステータス"],
                    title=f"詳細ガントチャート（{sched_mode}）")
                fig_g.update_yaxes(autorange="reversed",title="")
                fig_g.update_xaxes(tickformat="%m/%d %H:%M")
                fig_g.add_vline(x=datetime.now(),line_dash="dash",
                    line_color="#94A3B8",annotation_text="今日")
                fig_g.update_layout(margin=dict(l=10,r=10,t=50,b=10),
                    height=max(420,len(set(r[y_col] for r in gr))*46+100),
                    legend=dict(orientation="h",yanchor="bottom",y=1.01,xanchor="right",x=1),
                    plot_bgcolor="white")
                st.plotly_chart(fig_g,use_container_width=True)
                st.markdown("""<div style="display:flex;gap:8px;flex-wrap:wrap;">
                <span style="background:#7C3AED;color:white;padding:2px 10px;border-radius:99px;font-size:12px;">調合・練り</span>
                <span style="background:#2563EB;color:white;padding:2px 10px;border-radius:99px;font-size:12px;">成形・糊付け</span>
                <span style="background:#059669;color:white;padding:2px 10px;border-radius:99px;font-size:12px;">包装・充填</span>
                <span style="background:#0891B2;color:white;padding:2px 10px;border-radius:99px;font-size:12px;">レトルト・冷却</span>
                <span style="background:#DC2626;color:white;padding:2px 10px;border-radius:99px;font-size:12px;">🚨 段取り・洗浄</span>
                <span style="background:#D97706;color:white;padding:2px 10px;border-radius:99px;font-size:12px;">準備</span>
                </div>""",unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════
    # タブ4：段取り最適化（TSP+2-opt）
    # ══════════════════════════════════════════════════════════════════════
    with T4:
        if not needed_tasks:
            st.info("製造が必要な品目がありません。")
        else:
            co_rs=[r for r in _sched if r["工程"] in ("段取り・洗浄","段取り","準備")]
            mfg_rs=[r for r in _sched if r["工程"] in _PROCESSES]
            tot_co2=sum(r["所要時間(h)"] for r in co_rs)
            tot_mf2=sum(r["所要時間(h)"] for r in mfg_rs)
            c_cnt=sum(1 for r in co_rs if r.get("コンタミリスク",False))
            c1,c2,c3,c4,c5=st.columns(5)
            c1.metric("製造時間 合計",f"{tot_mf2:.1f} h")
            c2.metric("段取り時間 合計",f"{tot_co2:.1f} h")
            c3.metric("🚨 コンタミ洗浄",f"{c_cnt} 回")
            c4.metric("実働時間 合計",f"{tot_mf2+tot_co2:.1f} h")
            c5.metric("稼働率",f"{round(tot_mf2/max(tot_mf2+tot_co2,0.01)*100,1)}%")

            st.markdown('<div class="info-tip">🔧 TSP貪欲法+2-opt最適化により、段取り切り替え回数（特に黒→白のコンタミリスク回数）を最小化しています。</div>',unsafe_allow_html=True)

            seq=[]
            for r in _sched:
                s=r["開始"]; e=r["終了"]
                seq.append({"工程区分":r["区分"],"品目":r["製品名"][:20],"工程":r["工程"],
                    "開始":s.strftime("%m/%d %H:%M") if isinstance(s,pd.Timestamp) and pd.notnull(s) else "",
                    "終了":e.strftime("%m/%d %H:%M") if isinstance(e,pd.Timestamp) and pd.notnull(e) else "",
                    "時間(h)":r["所要時間(h)"],
                    "🚨洗浄":"🚨 要徹底洗浄" if r.get("コンタミリスク") else "",
                    "出荷日":r["出荷日"].strftime("%m/%d") if isinstance(r["出荷日"],pd.Timestamp) and pd.notnull(r["出荷日"]) else ""})
            sq_df=pd.DataFrame(seq)
            def _sq_s(r):
                if "段取り・洗浄" in str(r.get("工程","")) and r.get("🚨洗浄",""):
                    return ['background-color:#FEE2E2;font-weight:bold;color:#991B1B;']*len(r)
                if "段取り" in str(r.get("工程","")): return ['background-color:#F3E8FF;']*len(r)
                if "準備" in str(r.get("工程","")): return ['background-color:#FEF3C7;']*len(r)
                return ['']*len(r)
            st.dataframe(sq_df.style.apply(_sq_s,axis=1),hide_index=True,
                use_container_width=True,height=min(700,len(sq_df)*38+60))
            st.download_button("📥 段取り計画CSV",data=make_csv_bytes(sq_df),
                file_name=f"段取り計画_{date.today()}.csv",mime="text/csv")

    # ══════════════════════════════════════════════════════════════════════
    # タブ5：工程別人員配置（シフト連携）
    # ══════════════════════════════════════════════════════════════════════
    with T5:
        st.markdown('<div class="section-title">👷 工程別・時間帯別 人員配置計画</div>',unsafe_allow_html=True)
        st.markdown('<div class="info-tip">シフトマスタの人員と比較。赤=人員不足、⭐=キーマン必要工程。</div>',unsafe_allow_html=True)
        if not _sched:
            st.info("スケジュールデータがありません。")
        else:
            asgn=[]
            for r in _sched:
                if r["工程"] not in _PROCESSES: continue
                try:
                    s=r["開始"]; e=r["終了"]
                    if not isinstance(s,pd.Timestamp): s=pd.Timestamp(s)
                    if pd.isna(s): continue
                    sv,km=_staff_at(s,st.session_state.v3_shift)
                    ms=r.get("最少人数",1)
                    sts=("🔴 人員不足" if sv<ms else "🟡 ギリギリ" if sv<ms*1.5 else "🟢 充足")
                    asgn.append({"日付":s.strftime("%m/%d"),
                        "時間帯":f"{s.strftime('%H:%M')}〜{e.strftime('%H:%M') if isinstance(e,pd.Timestamp) else ''}",
                        "製品名":r["製品名"][:16],"工程":r["工程"],
                        "最少人数":ms,"シフト人数":sv,"キーマン数":km,
                        "⭐":"⭐ 要熟練" if r.get("キーマン必要") else "―","状態":sts})
                except: continue

            if asgn:
                adf=pd.DataFrame(asgn)
                def _as2(r):
                    if "不足" in str(r.get("状態","")): return ['background-color:#FEE2E2;font-weight:bold;']*len(r)
                    if "ギリギリ" in str(r.get("状態","")): return ['background-color:#FFFBEB;']*len(r)
                    return ['']*len(r)
                adf["配置人数"]=adf["最少人数"]
                ea2=st.data_editor(adf,hide_index=True,use_container_width=True,
                    height=min(600,len(adf)*38+60),
                    column_config={
                        "配置人数":st.column_config.NumberColumn("配置人数",min_value=0,max_value=20,step=1),
                        "工程":st.column_config.SelectboxColumn(options=_PROCESSES),
                    })
                _und=ea2[ea2["配置人数"].apply(to_int)>ea2["シフト人数"].apply(to_int)]
                if not _und.empty:
                    st.markdown(f'<div class="danger-banner">🚨 {len(_und)}工程で配置人数がシフト人数を超過しています！</div>',unsafe_allow_html=True)
                else:
                    st.markdown('<div class="ok-banner">✅ 全工程で人員配置に問題ありません。</div>',unsafe_allow_html=True)
                # 日別工程サマリ
                st.markdown('<div class="section-title">📊 日別 工程サマリ</div>',unsafe_allow_html=True)
                day_summ=adf.groupby(["日付","工程"]).agg(
                    工程数=("製品名","count"),最大必要人数=("最少人数","max"),
                    最大シフト人数=("シフト人数","max")).reset_index()
                st.dataframe(day_summ,hide_index=True,use_container_width=True)
                # シフトマスタ参照
                if not _sdf.empty:
                    with st.expander("📋 シフトマスタ（参照）"):
                        st.dataframe(_sdf[["シフト名","曜日区分","開始時刻","終了時刻","出勤人数","うちキーマン数"]],
                            hide_index=True,use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════
    # タブ6：負荷グラフ
    # ══════════════════════════════════════════════════════════════════════
    with T6:
        st.markdown('<div class="section-title">📈 日別製造負荷 ＆ 人員山積みグラフ</div>',unsafe_allow_html=True)
        if not _sched:
            st.info("スケジュールデータがありません。")
        else:
            load_map={}; staff_map={}
            for r in _sched:
                if r["工程"] not in _PROCESSES: continue
                try:
                    s=r["開始"]; e=r["終了"]
                    if not isinstance(s,pd.Timestamp): s=pd.Timestamp(s)
                    if not isinstance(e,pd.Timestamp): e=pd.Timestamp(e)
                    if pd.isna(s) or pd.isna(e): continue
                    dk=s.normalize().strftime("%m/%d")
                    h=(e-s).total_seconds()/3600.
                    load_map.setdefault(dk,{}).setdefault(r["工程"],0)
                    load_map[dk][r["工程"]]+=h
                    sv,_=_staff_at(s,st.session_state.v3_shift)
                    staff_map.setdefault(dk,{}).setdefault(r["工程"],0)
                    staff_map[dk][r["工程"]]=max(staff_map[dk][r["工程"]],r.get("最少人数",1))
                except: continue

            wh_day=we_h-ws_h
            if load_map:
                lr=[]
                for d in sorted(load_map.keys()):
                    for proc,h in load_map[d].items():
                        lr.append({"日付":d,"工程":proc,"稼働時間(h)":round(h,2)})
                ldf=pd.DataFrame(lr)
                fig_l=px.bar(ldf,x="日付",y="稼働時間(h)",color="工程",barmode="stack",
                    title="日別 工程別稼働時間",color_discrete_map=_PCOLOR)
                fig_l.add_hline(y=wh_day,line_dash="dash",line_color="#DC2626",
                    annotation_text=f"稼働上限 {wh_day}h")
                fig_l.update_layout(margin=dict(l=10,r=10,t=50,b=10),height=350,plot_bgcolor="white")
                st.plotly_chart(fig_l,use_container_width=True)

                # 累積稼働グラフ（アスプローバ的特徴）
                st.markdown('<div class="section-title">📈 累積稼働グラフ</div>',unsafe_allow_html=True)
                cum_h=0; cum_rows=[]
                for d in sorted(load_map.keys()):
                    cum_h+=sum(load_map[d].values())
                    cum_rows.append({"日付":d,"累積製造時間(h)":round(cum_h,2)})
                cum_df=pd.DataFrame(cum_rows)
                fig_c=px.area(cum_df,x="日付",y="累積製造時間(h)",
                    title="累積製造時間（計画の進捗見通し）",
                    color_discrete_sequence=["#2563EB"])
                fig_c.update_layout(margin=dict(l=10,r=10,t=50,b=10),height=280,plot_bgcolor="white")
                st.plotly_chart(fig_c,use_container_width=True)

                # 人員山積みグラフ
                st.markdown('<div class="section-title">👷 人員山積みグラフ</div>',unsafe_allow_html=True)
                sr_list=[]
                for d in sorted(staff_map.keys()):
                    tot_n=sum(staff_map[d].values())
                    try:
                        d_dt=pd.Timestamp(f"{date.today().year}/{d}")+timedelta(hours=ws_h)
                        sv2,_=_staff_at(d_dt,st.session_state.v3_shift)
                    except: sv2=8
                    sr_list.append({"日付":d,"必要人数":tot_n,"出勤人数":sv2,"超過":max(0,tot_n-sv2)})
                sdf2=pd.DataFrame(sr_list)
                fig_s=go.Figure()
                fig_s.add_trace(go.Bar(x=sdf2["日付"],y=sdf2["出勤人数"],name="出勤人数",marker_color="#93C5FD"))
                fig_s.add_trace(go.Scatter(x=sdf2["日付"],y=sdf2["必要人数"],name="必要人数",
                    mode="lines+markers",line=dict(color="#DC2626",width=2.5)))
                for _,sr2 in sdf2[sdf2["超過"]>0].iterrows():
                    fig_s.add_vrect(x0=sr2["日付"],x1=sr2["日付"],fillcolor="red",opacity=0.15,line_width=0)
                fig_s.update_layout(title="人員山積みグラフ（赤ハイライト=人員不足）",
                    barmode="overlay",margin=dict(l=10,r=10,t=50,b=10),height=320,plot_bgcolor="white")
                st.plotly_chart(fig_s,use_container_width=True)

                # ボトルネック特定
                bn_proc=sorted(load_map.items(),key=lambda x:-sum(x[1].values()))
                if bn_proc:
                    bn_day,bn_loads=bn_proc[0]
                    bn_p=max(bn_loads,key=bn_loads.get)
                    st.markdown(f'<div class="warn-banner">⚠️ ボトルネック検出：<b>{bn_day}</b>  最高負荷工程 → <b>{bn_p}</b> ({bn_loads[bn_p]:.1f}h)</div>',unsafe_allow_html=True)

                ol=[d for d in load_map if sum(load_map[d].values())>wh_day]
                sl=[r["日付"] for _,r in sdf2.iterrows() if r["超過"]>0]
                if ol: st.markdown(f'<div class="warn-banner">⚠️ 稼働時間超過：{", ".join(ol[:6])}{"…" if len(ol)>6 else ""}</div>',unsafe_allow_html=True)
                if sl: st.markdown(f'<div class="danger-banner">🚨 人員不足：{", ".join(sl[:6])}{"…" if len(sl)>6 else ""}</div>',unsafe_allow_html=True)
                if not ol and not sl: st.markdown('<div class="ok-banner">✅ 全日程で稼働・人員が上限内です。</div>',unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════
    # タブ7：在庫推移
    # ══════════════════════════════════════════════════════════════════════
    with T7:
        st.markdown('<div class="section-title">📦 製品別 在庫推移プレビュー</div>',unsafe_allow_html=True)
        if not needed_tasks:
            st.info("製造が必要な品目がありません。")
        else:
            prods_n=list(dict.fromkeys(t["製品名"] for t in needed_tasks))
            sp=st.selectbox("製品を選択",options=prods_n,index=0,key="v3_inv_sel")
            if sp:
                inv_r=[]
                for d in pd.date_range(today,today+timedelta(days=hd)):
                    cur_s=fs.get(sp,{}).get(d,cs.get(sp,0))
                    inv_r.append({"日付":d.strftime("%m/%d"),"予測在庫(cs)":cur_s})
                inv_df=pd.DataFrame(inv_r)
                safe_s=_gpp(sp)["安全在庫数"]
                fig_i=go.Figure()
                fig_i.add_trace(go.Scatter(x=inv_df["日付"],y=inv_df["予測在庫(cs)"],
                    mode="lines+markers",name="予測在庫",
                    line=dict(color="#2563EB",width=2.5),
                    fill="tozeroy",fillcolor="rgba(37,99,235,0.08)"))
                fig_i.add_hline(y=safe_s,line_dash="dash",line_color="#F59E0B",
                    annotation_text=f"安全在庫 {safe_s}cs")
                fig_i.add_hline(y=0,line_dash="dot",line_color="#DC2626",annotation_text="ゼロ在庫")
                fig_i.update_layout(title=f"【{sp}】 在庫推移（{hd}日間）",
                    margin=dict(l=10,r=10,t=50,b=10),height=300,
                    plot_bgcolor="white",hovermode="x unified")
                st.plotly_chart(fig_i,use_container_width=True)

            st.markdown('<div class="section-title">全製品 在庫ステータス一覧</div>',unsafe_allow_html=True)
            inv_sum=[]
            for pn in prods_n:
                c_n=cs.get(pn,0); sf=_gpp(pn)["安全在庫数"]
                mn=min((fs.get(pn,{}).get(d,c_n) for d in pd.date_range(today,today+timedelta(days=30))),default=c_n)
                inv_sum.append({"製品名":pn,"現在庫(cs)":c_n,"安全在庫(cs)":sf,"30日内最低在庫":mn,
                    "状態":"🔴 欠品リスク" if mn<0 else ("🟡 安全在庫割れ" if mn<sf else "🟢 充足")})
            idf=pd.DataFrame(inv_sum)
            def _isy(r):
                if "欠品" in str(r.get("状態","")): return ['background-color:#FEE2E2;font-weight:bold;']*len(r)
                if "割れ" in str(r.get("状態","")): return ['background-color:#FFFBEB;']*len(r)
                return ['']*len(r)
            st.dataframe(idf.style.apply(_isy,axis=1),hide_index=True,use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════
    # タブ8：ドリルダウン（製品別詳細）
    # ══════════════════════════════════════════════════════════════════════
    with T8:
        st.markdown('<div class="section-title">🔍 製品別スケジュール詳細ドリルダウン</div>',unsafe_allow_html=True)
        if not _sched:
            st.info("スケジュールデータがありません。")
        else:
            pns_all=list(dict.fromkeys(r["製品名"] for r in _sched if r["工程"] in _PROCESSES))
            if not pns_all:
                st.info("製造工程の製品がありません。")
            else:
                dd_pn=st.selectbox("🔍 製品を選択",options=pns_all,key="v3_dd_pn")
                if dd_pn:
                    dd_rs=[r for r in _sched if r["製品名"]==dd_pn or dd_pn in r["製品名"]]
                    mfg_rs2=[r for r in dd_rs if r["工程"] in _PROCESSES]
                    co_rs2=[r for r in dd_rs if r["工程"] in ("段取り・洗浄","段取り","準備")]
                    pa2=_gpp(dd_pn)

                    # 製品サマリカード
                    dc1,dc2,dc3,dc4=st.columns(4)
                    dc1.metric("製造必要量",f"{sum(r.get('製造量(cs)',0) for r in mfg_rs2):,} cs")
                    dc2.metric("総製造時間",f"{sum(r.get('所要時間(h)',0) for r in mfg_rs2):.1f} h")
                    dc3.metric("段取り時間",f"{sum(r.get('所要時間(h)',0) for r in co_rs2):.1f} h")
                    dc4.metric("歩留まり率",f"{pa2['歩留まり率']}%")

                    # タイムライン
                    dd_tl=[]
                    for r in dd_rs:
                        s=r["開始"]; e=r["終了"]
                        if not isinstance(s,pd.Timestamp) or pd.isna(s): continue
                        if not isinstance(e,pd.Timestamp) or pd.isna(e): e=s+timedelta(minutes=30)
                        if e<=s: e=s+timedelta(minutes=15)
                        dd_tl.append({"工程":r["工程"],"Start":s,"Finish":e,
                            "製造量":r.get("製造量(cs)",0),"ステータス":r.get("ステータス","")})
                    if dd_tl:
                        dd_df=pd.DataFrame(dd_tl)
                        fig_dd=px.timeline(dd_df,x_start="Start",x_end="Finish",y="工程",
                            color="工程",color_discrete_map=_PCOLOR,
                            hover_data=["製造量","ステータス"],
                            title=f"【{dd_pn}】 製造工程タイムライン")
                        fig_dd.update_yaxes(autorange="reversed",title="")
                        fig_dd.update_xaxes(tickformat="%m/%d %H:%M")
                        fig_dd.update_layout(margin=dict(l=10,r=10,t=50,b=10),
                            height=300,plot_bgcolor="white",showlegend=False)
                        st.plotly_chart(fig_dd,use_container_width=True)

                    # 工程別詳細
                    dd_detail=[]
                    for r in dd_rs:
                        s=r["開始"]; e=r["終了"]
                        dd_detail.append({
                            "工程":r["工程"],"区分":r["区分"],
                            "開始":s.strftime("%m/%d %H:%M") if isinstance(s,pd.Timestamp) and pd.notnull(s) else "",
                            "終了":e.strftime("%m/%d %H:%M") if isinstance(e,pd.Timestamp) and pd.notnull(e) else "",
                            "時間(h)":r.get("所要時間(h)",0),
                            "製造量(cs)":r.get("製造量(cs)",0),
                            "ステータス":r.get("ステータス",""),
                            "コンタミ":"🚨 要洗浄" if r.get("コンタミリスク") else ""})
                    st.dataframe(pd.DataFrame(dd_detail),hide_index=True,use_container_width=True)

                    # 受注リスト（この製品）
                    if not odf.empty:
                        pn_orders=odf[odf["製品名"]==dd_pn][["納品予定日","顧客名","ケース数","備考"]].copy()
                        pn_orders["納品予定日"]=pn_orders["納品予定日"].apply(format_date_jp)
                        if not pn_orders.empty:
                            with st.expander(f"📋 {dd_pn} の受注一覧"):
                                st.dataframe(pn_orders,hide_index=True,use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════
    # タブ9：スケジュール確定・版比較
    # ══════════════════════════════════════════════════════════════════════
    with T9:
        st.markdown('<div class="section-title">💾 スケジュール確定・保存 ＆ 版比較</div>',unsafe_allow_html=True)
        st.markdown('<div class="info-tip">💡 確定ボタンを押すと現在のスケジュールが「schedule_confirmed」シートへ保存されます。版IDで過去版との比較が可能です。</div>',unsafe_allow_html=True)

        # 確定保存
        c9a,c9b=st.columns([2,2])
        with c9a:
            ver_id=f"VER_{date.today().strftime('%Y%m%d')}_{str(uuid.uuid4())[:4].upper()}"
            st.text_input("版ID（自動生成）",value=ver_id,disabled=True,key="v3_ver_id")
            _conf_msg=st.empty()
            if st.button("💾 このスケジュールを確定保存",type="primary",key="v3_confirm"):
                if not _sched:
                    _conf_msg.error("スケジュールがありません。")
                else:
                    conf_rows=[]
                    for r in _sched:
                        s=r["開始"]; e=r["終了"]
                        conf_rows.append({
                            "版ID":ver_id,
                            "スケジュールID":str(uuid.uuid4())[:8].upper(),
                            "製品名":r["製品名"][:30],
                            "ライン":r.get("ライン",""),
                            "工程":r["工程"],
                            "開始日時":s.strftime("%Y-%m-%d %H:%M") if isinstance(s,pd.Timestamp) and pd.notnull(s) else "",
                            "終了日時":e.strftime("%Y-%m-%d %H:%M") if isinstance(e,pd.Timestamp) and pd.notnull(e) else "",
                            "製造量(cs)":r.get("製造量(cs)",0),
                            "配置人数":r.get("最少人数",1),
                            "段取り時間(分)":r.get("段取り時間(分)",0),
                            "コンタミリスク":"TRUE" if r.get("コンタミリスク") else "FALSE",
                            "ステータス":r.get("ステータス",""),
                            "確定日時":datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "確定者":conf_user or "未設定",
                        })
                    conf_df=pd.DataFrame(conf_rows,columns=_CONF_COLS)
                    # 既存データに追加（版IDで区別）
                    existing=_load_sched_master("schedule_confirmed",_CONF_COLS,[])
                    merged_conf=pd.concat([existing,conf_df],ignore_index=True)
                    _save_sched_master("schedule_confirmed",merged_conf)
                    st.session_state.v3_conf=merged_conf
                    flash("success",f"✅ スケジュールを確定保存しました。版ID: {ver_id}")
                    st.rerun()
            show_flash_inline(_conf_msg)

        with c9b:
            st.markdown("**📋 確定済み版一覧**")
            if not _cfdf.empty and "版ID" in _cfdf.columns:
                ver_list=_cfdf["版ID"].unique().tolist()
                st.caption(f"保存済み版数：{len(ver_list)}件")
                for v in ver_list[-5:][::-1]:
                    v_rows=_cfdf[_cfdf["版ID"]==v]
                    conf_dt=v_rows["確定日時"].iloc[0] if not v_rows.empty else ""
                    user=v_rows["確定者"].iloc[0] if not v_rows.empty else ""
                    st.markdown(f"- `{v}` — {conf_dt} ({user}) / {len(v_rows)}件")
            else:
                st.info("確定済みスケジュールはありません。")

        # 版比較（差分表示）
        st.markdown('<div class="section-title">🔄 スケジュール差分比較</div>',unsafe_allow_html=True)
        if not _cfdf.empty and "版ID" in _cfdf.columns:
            ver_opts=_cfdf["版ID"].unique().tolist()
            if len(ver_opts)>=1:
                cmp_ver=st.selectbox("比較する確定版を選択",options=ver_opts,key="v3_cmp_ver")
                prev_df=_cfdf[_cfdf["版ID"]==cmp_ver][["製品名","工程","開始日時","終了日時","製造量(cs)"]].copy()
                curr_df=pd.DataFrame([{
                    "製品名":r["製品名"][:30],"工程":r["工程"],
                    "開始日時":r["開始"].strftime("%Y-%m-%d %H:%M") if isinstance(r["開始"],pd.Timestamp) and pd.notnull(r["開始"]) else "",
                    "終了日時":r["終了"].strftime("%Y-%m-%d %H:%M") if isinstance(r["終了"],pd.Timestamp) and pd.notnull(r["終了"]) else "",
                    "製造量(cs)":r.get("製造量(cs)",0)} for r in _sched])
                # 差分検出（製品+工程キーで比較）
                prev_df["_key"]=prev_df["製品名"]+"_"+prev_df["工程"]
                curr_df["_key"]=curr_df["製品名"]+"_"+curr_df["工程"]
                prev_keys=set(prev_df["_key"]); curr_keys=set(curr_df["_key"])
                added=curr_keys-prev_keys; removed=prev_keys-curr_keys; common=curr_keys&prev_keys
                diff_rows=[]
                for k in sorted(added): r2=curr_df[curr_df["_key"]==k].iloc[0]; diff_rows.append({"変更区分":"🟢 追加","製品名":r2["製品名"],"工程":r2["工程"],"開始":r2["開始日時"],"終了":r2["終了日時"],"製造量(cs)":r2["製造量(cs)"]})
                for k in sorted(removed): r2=prev_df[prev_df["_key"]==k].iloc[0]; diff_rows.append({"変更区分":"🔴 削除","製品名":r2["製品名"],"工程":r2["工程"],"開始":r2["開始日時"],"終了":r2["終了日時"],"製造量(cs)":r2["製造量(cs)"]})
                for k in sorted(common):
                    p2=prev_df[prev_df["_key"]==k].iloc[0]; c2=curr_df[curr_df["_key"]==k].iloc[0]
                    if p2["開始日時"]!=c2["開始日時"] or p2["製造量(cs)"]!=c2["製造量(cs)"]:
                        diff_rows.append({"変更区分":"🟡 変更","製品名":c2["製品名"],"工程":c2["工程"],
                            "開始":f'{p2["開始日時"]} → {c2["開始日時"]}',
                            "終了":f'{p2["終了日時"]} → {c2["終了日時"]}',
                            "製造量(cs)":f'{p2["製造量(cs)"]} → {c2["製造量(cs)"]}'})
                if diff_rows:
                    diff_df=pd.DataFrame(diff_rows)
                    def _dfs(r):
                        d=str(r.get("変更区分",""))
                        if "追加" in d: return ['background-color:#D1FAE5;']*len(r)
                        if "削除" in d: return ['background-color:#FEE2E2;text-decoration:line-through;']*len(r)
                        if "変更" in d: return ['background-color:#FEF3C7;']*len(r)
                        return ['']*len(r)
                    st.dataframe(diff_df.style.apply(_dfs,axis=1),hide_index=True,use_container_width=True)
                    st.caption(f"追加:{len(added)}件  削除:{len(removed)}件  変更:{len([r for r in diff_rows if '変更' in r['変更区分']])}件")
                else:
                    st.markdown('<div class="ok-banner">✅ 選択した確定版と現在のスケジュールに差分はありません。</div>',unsafe_allow_html=True)
        else:
            st.info("確定済みスケジュールがないため比較できません。まずスケジュールを確定保存してください。")

    # ══════════════════════════════════════════════════════════════════════
    # タブ10：パラメータ設定（マスタ拡張列）
    # ══════════════════════════════════════════════════════════════════════
    with T10:
        st.markdown('<div class="section-title">⚙️ 製品別 製造パラメータ設定</div>',unsafe_allow_html=True)
        st.markdown("""<div class="info-tip">
        💡 <b>入力ガイド：</b>生産量=cs/h。歩留まり=90〜98%程度。LT=調合・仕込み前処理時間(h)。
        段取りタイプ=段取りマトリクスとの照合キー（空欄=製品名から自動判定）。
        工程比率は合計が100%になるよう設定（空欄=自動按分）。最小製造ロット=ロット単位cs数。
        </div>""",unsafe_allow_html=True)
        if mst.empty:
            st.warning("製品マスタが未登録です。「⚙️ マスタ・分析」から登録してください。")
        else:
            base_c=["製品名","大カテゴリ","時間あたり生産量","歩留まり率","リードタイム時間","安全在庫数","段取りグループ"]
            ext_c=["段取りタイプ","ラインID","最小製造ロット",
                   "調合比率","成形比率","包装比率","レトルト比率",
                   "最少人員_調合","最少人員_成形","最少人員_包装","最少人員_レトルト","キーマン必要"]
            for ec in ext_c:
                if ec not in mst.columns: mst[ec]=""
            pc=[c for c in base_c+ext_c if c in mst.columns]
            ep=st.data_editor(mst[pc].copy(),hide_index=True,use_container_width=True,
                height=min(600,len(mst)*38+60),
                column_config={
                    "製品名":st.column_config.TextColumn(disabled=True),
                    "大カテゴリ":st.column_config.TextColumn("カテゴリ",disabled=True),
                    "時間あたり生産量":st.column_config.NumberColumn("生産量(cs/h)",min_value=1,step=1,format="%d"),
                    "歩留まり率":st.column_config.NumberColumn("歩留まり(%)",min_value=1,max_value=100,step=1,format="%d"),
                    "リードタイム時間":st.column_config.NumberColumn("LT準備(h)",min_value=0,step=1,format="%d"),
                    "安全在庫数":st.column_config.NumberColumn("安全在庫(cs)",min_value=0,step=1,format="%d"),
                    "段取りグループ":st.column_config.TextColumn("段取りG"),
                    "段取りタイプ":st.column_config.SelectboxColumn("段取りタイプ",
                        options=["","黒","白","糸","板","玉","三角","ダイス","冷凍","その他"]),
                    "ラインID":st.column_config.TextColumn("ラインID"),
                    "最小製造ロット":st.column_config.NumberColumn("最小ロット(cs)",min_value=1,step=1,format="%d"),
                    "調合比率":st.column_config.NumberColumn("調合比率(%)",min_value=0,max_value=100,step=5,format="%d"),
                    "成形比率":st.column_config.NumberColumn("成形比率(%)",min_value=0,max_value=100,step=5,format="%d"),
                    "包装比率":st.column_config.NumberColumn("包装比率(%)",min_value=0,max_value=100,step=5,format="%d"),
                    "レトルト比率":st.column_config.NumberColumn("レトルト比率(%)",min_value=0,max_value=100,step=5,format="%d"),
                    "最少人員_調合":st.column_config.NumberColumn("最少人員/調合",min_value=1,step=1,format="%d"),
                    "最少人員_成形":st.column_config.NumberColumn("最少人員/成形",min_value=1,step=1,format="%d"),
                    "最少人員_包装":st.column_config.NumberColumn("最少人員/包装",min_value=1,step=1,format="%d"),
                    "最少人員_レトルト":st.column_config.NumberColumn("最少人員/冷却",min_value=1,step=1,format="%d"),
                    "キーマン必要":st.column_config.SelectboxColumn("キーマン必要",options=["TRUE","FALSE"]),
                })
            _pm_msg=st.empty()
            if st.button("💾 パラメータを保存",type="primary",use_container_width=True,key="v3_save_param"):
                um=mst.copy()
                for ec in ext_c:
                    if ec not in um.columns: um[ec]=""
                for c in [col for col in base_c[2:]+ext_c if col in ep.columns and col in um.columns]:
                    try: um[c]=ep.set_index("製品名").reindex(um["製品名"])[c].values
                    except: pass
                save_sync("master",um)
                flash("success","✅ 製造パラメータを保存しました。"); st.rerun()
            show_flash_inline(_pm_msg)

            # 段取りマトリクス参照
            st.markdown('<div class="section-title">🧩 現在の段取りマトリクス（参照）</div>',unsafe_allow_html=True)
            if not _cdf.empty:
                def _co_sty(r):
                    if str(r.get("コンタミリスク","")).upper()=="TRUE":
                        return ['background-color:#FEE2E2;font-weight:bold;']*len(r)
                    return ['']*len(r)
                st.dataframe(_cdf.style.apply(_co_sty,axis=1),hide_index=True,use_container_width=True)
            else:
                st.info("段取りマトリクスは上部「🧩 段取りマトリクス設定」エクスパンダーから登録してください。")
