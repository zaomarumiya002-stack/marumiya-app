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

st.set_page_config(page_title="丸実屋 統合管理", page_icon="🏭", layout="wide", initial_sidebar_state="expanded")

# ─────────────────────────────────────────────
# 共通関数 & CSS
# ─────────────────────────────────────────────
def md(h): st.markdown(h, unsafe_allow_html=True)
def to_int(v):
    try: return int(float(v.sum() if isinstance(v, pd.Series) else v))
    except: return 0
def to_dt(x): return pd.to_datetime(x, errors='coerce')
def dt_str(d): return d.strftime('%Y/%m/%d') if pd.notnull(d) else ""
def format_date_jp(d):
    try:
        d = to_dt(d.split(" ")[0]) if isinstance(d, str) else d
        if pd.isnull(d): return ""
        return f"{d.strftime('%Y/%m/%d')} ({['月','火','水','木','金','土','日'][d.weekday()]})"
    except: return str(d).split(" ")[0] if d else ""

df_kws = dict(use_container_width=True, hide_index=True)

md("""
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
""")

if "pw_ok" not in st.session_state: st.session_state.pw_ok = False
if not st.session_state.pw_ok:
    md("<div style='text-align:center;margin-top:60px;'><span style='font-size:72px;'>🏭</span><h2 style='color:#1E3A8A;'>丸実屋 ログイン</h2></div>")
    _, c, _ = st.columns([1, 2, 1])
    with c:
        pwd = st.text_input("パスワード", type="password")
        if st.button("ログイン", use_container_width=True, type="primary"):
            if pwd == st.secrets["app_password"]: st.session_state.pw_ok = True; st.rerun()
            else: st.error("❌ パスワードが違います")
    st.stop()

@st.cache_resource
def get_gspread(): return gspread.authorize(Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"])).open_by_url(st.secrets["spreadsheet_url"])
sheet = get_gspread()

def load_df(name):
    c_def = {
        "orders":["ID","納品予定日","顧客名","大カテゴリ","製品名","ケース数","運送会社","備考","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考","不良廃棄フラグ","日付未定フラグ","登録日時"],
        "manufactures":["ID","製造予定日","大カテゴリ","製品名","ケース数","リパックフラグ","備考","登録日時"],
        "master":["大カテゴリ","製品名","初期在庫数","使用資材名","資材使用数","入数","単位区分","特注フラグ","チャーターフラグ","時間あたり生産量","歩留まり率","リードタイム時間","安全在庫数","段取りグループ"],
        "customers":["顧客名","ふりがな","帳合先","支店名"],
        "packaging_master":["資材名","品番","規格","仕入先","保管場所","単位","初期在庫","発注点","発注リードタイム"],
        "packaging_logs":["ID","登録日","資材名","処理区分","数量","理由","備考","関連製品名","理論在庫","登録日時"],
        "shipping_master":["運送会社名"],
        "special_schedule":["ID","受注ID","製品名","顧客名","納品予定日","出荷予定日","備考","更新日時"]
    }
    tc = c_def.get(name, [])
    try: ws = sheet.worksheet(name)
    except:
        ws = sheet.add_worksheet(title=name, rows="1000", cols="30")
        ws.update(values=[tc,["ヤマト運輸"],["佐川急便"]] if name=="shipping_master" else [tc], range_name="A1")
    data = ws.get_all_values()
    if len(data)<=1: return pd.DataFrame(columns=tc)
    df = pd.DataFrame(data[1:], columns=data[0])
    df.columns = df.columns.str.strip().str.replace(' ','').str.replace('　','')
    df = df.loc[:, ~df.columns.duplicated()].reindex(columns=tc, fill_value="")
    for c in ["ケース数","初期在庫数","資材使用数","初期在庫","発注点","数量","理論在庫","時間あたり生産量","歩留まり率","リードタイム時間","安全在庫数","入数"]:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).apply(to_int)
    for c in ["納品予定日","製造予定日","登録日","登録日時","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","出荷予定日","更新日時"]:
        if c in df.columns: df[c] = to_dt(df[c])
    for c in ["荷姿チェック","不良廃棄フラグ","リパックフラグ","日付未定フラグ","特注フラグ","チャーターフラグ"]:
        if c in df.columns: df[c] = df[c].astype(str).str.upper() == "TRUE"
    return df[tc]

def save_df(name, df):
    ws = sheet.worksheet(name); ws.clear(); ds = df.copy()
    for col in ds.columns:
        if pd.api.types.is_datetime64_any_dtype(ds[col]): ds[col] = ds[col].dt.strftime('%Y-%m-%d %H:%M:%S').fillna('').replace('NaT','')
        elif pd.api.types.is_bool_dtype(ds[col]): ds[col] = ds[col].astype(str).str.upper()
        elif pd.api.types.is_numeric_dtype(ds[col]): ds[col] = ds[col].fillna(0).apply(to_int).astype(str)
        else: ds[col] = ds[col].astype(str)
    ws.update(values=[ds.columns.tolist()] + ds.fillna("").replace(["nan","None","NaT","NaN"],"").values.tolist(), range_name='A1')
    st.cache_data.clear(); st.session_state[name] = load_df(name)

def app_df(name, nr):
    ws = sheet.worksheet(name); rc = nr.copy(); ec = pd.DataFrame(ws.get("A1:Z1")).values[0].tolist() if len(ws.get("A1:Z1"))>0 else []
    for c in rc.columns:
        if c not in ec: ec.append(c)
    rc = rc.reindex(columns=ec, fill_value="")
    for col in rc.columns:
        if pd.api.types.is_datetime64_any_dtype(rc[col]): rc[col] = rc[col].dt.strftime('%Y-%m-%d %H:%M:%S').fillna('').replace('NaT','')
        elif pd.api.types.is_bool_dtype(rc[col]): rc[col] = rc[col].astype(str).str.upper()
    ws.append_row(rc.fillna("").astype(str).replace(["nan","None","NaT","NaN"],"").values[0].tolist())
    st.cache_data.clear(); st.session_state[name] = pd.concat([st.session_state[name], nr], ignore_index=True)

names = ["orders","manufactures","master","customers","packaging_master","packaging_logs","shipping_master","special_schedule"]
for n in names:
    if n not in st.session_state: st.session_state[n] = load_df(n)
if "page" not in st.session_state: st.session_state.page = "📋 受注登録"
if "drill" not in st.session_state: st.session_state.drill = None

df_o = st.session_state.orders; df_m = st.session_state.manufactures; df_mst = st.session_state.master; df_c = st.session_state.customers
df_pm = st.session_state.packaging_master; df_pl = st.session_state.packaging_logs; df_sm = st.session_state.shipping_master; df_sp = st.session_state.special_schedule

CATS = ["🍝 つきこん","🟫 平こん","🍜 糸こん・しらたき","🔺 三角こん","🟤 玉こん","🎲 ダイスこん","🏷️ 短冊","🇯🇵 国産","🤲 ちぎりこん","🏮 大黒屋","🏭 かねこ","🍱 ショクカイ","❄️ 冷凍耐性","📦 その他"]
def fn(n): return f"⚫️ {n}" if "黒" in str(n) else f"⚪️ {n}" if "白" in str(n) else f"📦 {n}"
def pui(pn):
    r = df_mst[df_mst["製品名"]==pn] if not df_mst.empty else pd.DataFrame()
    return (max(1, to_int(r.iloc[0].get("入数", 1))), str(r.iloc[0].get("単位区分", "ケース")).strip() or "ケース") if not r.empty else (1, "ケース")

today = pd.Timestamp.today().normalize(); dts = pd.date_range(today, today + timedelta(days=60))
cs = {}; fs = {}; mst_u = df_mst.drop_duplicates(subset=["製品名"]) if not df_mst.empty else pd.DataFrame()

# 在庫計算
if not mst_u.empty:
    eo = df_o[["納品予定日","製品名","ケース数"]].copy().rename(columns={"納品予定日":"日付","ケース数":"qty"}) if not df_o.empty else pd.DataFrame(columns=["日付","製品名","qty"])
    if not eo.empty: eo["qty"] = -pd.to_numeric(eo["qty"], errors='coerce').fillna(0).abs()
    vm = df_m[~df_m["備考"].fillna("").str.contains("【在庫非反映】")] if not df_m.empty else pd.DataFrame()
    em = vm[["製造予定日","製品名","ケース数"]].copy().rename(columns={"製造予定日":"日付","ケース数":"qty"}) if not vm.empty else pd.DataFrame(columns=["日付","製品名","qty"])
    if not em.empty: em["qty"] = pd.to_numeric(em["qty"], errors='coerce').fillna(0).abs()
    ae = pd.concat([eo, em], ignore_index=True).dropna(subset=["製品名","日付"]); ae["qty"] = ae["qty"].apply(to_int)
    pe = ae[ae["日付"]<today].groupby("製品名")["qty"].sum(); fe = ae[ae["日付"]>=today]
    piv = fe.pivot_table(index="製品名", columns="日付", values="qty", aggfunc="sum") if not fe.empty else pd.DataFrame()
    for _, r in mst_u.iterrows():
        p = r["製品名"]; c_s = to_int(r.get("初期在庫数",0)) + to_int(pe.get(p,0)); cs[p] = c_s
        pr = piv.loc[p] if p in piv.index else pd.Series(0, index=dts)
        if isinstance(pr, pd.DataFrame): pr = pr.sum(axis=0)
        pc = pr.reindex(dts, fill_value=0).fillna(0).cumsum()
        fs[p] = {d: c_s + to_int(pc.get(d,0)) for d in dts}

# 資材計算
ps = {}
pm_u = df_pm.drop_duplicates(subset=["資材名"]) if not df_pm.empty else pd.DataFrame()
if not pm_u.empty:
    for _, r in pm_u.iterrows(): ps[r["資材名"]] = {"品番":str(r.get("品番","")), "規格":str(r.get("規格","")), "仕入先":str(r.get("仕入先","")), "保管場所":str(r.get("保管場所","")), "単位":str(r.get("単位","")), "期首":to_int(r.get("初期在庫",0)), "点":to_int(r.get("発注点",0)), "LT":to_int(r.get("発注リードタイム",7)), "入":0, "出":0, "現":0}
if not df_pl.empty:
    for _, r in df_pl.iterrows():
        pn, q, pt = r.get("資材名",""), to_int(r.get("数量",0)), str(r.get("処理区分",""))
        if pn in ps and "連動" not in pt:
            if "入庫" in pt: ps[pn]["入"] += q
            elif "出庫" in pt: ps[pn]["出"] += q
if not vm.empty and not mst_u.empty:
    mpi = mst_u.set_index("製品名")[["使用資材名","資材使用数"]].to_dict('index')
    for _, r in vm.iterrows():
        prod, q = str(r.get("製品名","")), to_int(r.get("ケース数",0))
        if prod in mpi:
            pn, pu = mpi[prod].get("使用資材名",""), to_int(mpi[prod].get("資材使用数",0))
            if pn and pu>0 and pn in ps: ps[pn]["出"] += (q*pu)
for d in ps.values(): d["現"] = d["期首"] + d["入"] - d["出"]; d["状態"] = "⚠️ 注意" if d["現"] < d["点"] else "✅ 正常"

# サイドバー
with st.sidebar:
    md("<div style='padding:16px 8px 8px;'><span style='font-size:22px;'>🏭</span><span style='font-size:16px; font-weight:900; color:#F1F5F9; margin-left:8px;'>丸実屋システム</span></div>")
    toc = int((to_dt(df_o["納品予定日"]).dt.date == date.today()).sum()) if not df_o.empty and "納品予定日" in df_o.columns else 0
    scnt = sum(1 for f in fs.values() if any(v<0 for v in list(f.values())[:7]))
    md(f'<div style="margin:8px 0 12px; background:rgba(255,255,255,0.07); border-radius:8px; padding:10px 14px;"><div style="font-size:12px; color:#94A3B8; margin-bottom:4px;">本日状況</div><div style="display:flex; gap:12px;"><div><span style="font-size:20px; font-weight:900; color:#60A5FA;">{toc}</span><span style="font-size:11px; color:#94A3B8;"> 出荷</span></div><div><span style="font-size:20px; font-weight:900; color:#F87171;">{scnt}</span><span style="font-size:11px; color:#94A3B8;"> 欠品予測</span></div></div></div><div style="height:1px; background:rgba(255,255,255,0.1); margin:0 0 10px;"></div>')
    for m in ["📋 受注登録","🏭 製造登録","🚚 出荷・発送管理","📦 資材・入出庫","📑 登録一覧","📊 在庫・スケジュール","🏗️ 製造スケジューラー","⭐ 特注・チャータースケジュール","📈 経営・分析ダッシュボード","⚙️ マスタ・分析"]:
        if st.button(m, use_container_width=True, type="primary" if st.session_state.page == m else "secondary"): st.session_state.page = m; st.session_state.drill = None; st.rerun()

pg = st.session_state.page
def hdr(t): md(f'<div class="page-header"><h1>{t}</h1></div>')
def sec(t): md(f'<div class="section-title">{t}</div>')

# ─────────────────────────────────────────────
# 📋 受注登録
# ─────────────────────────────────────────────
if pg == "📋 受注登録":
    hdr("📋 受注 登録")
    idu = st.checkbox("📅 納品日を後で決める（日付未定）", value=False)
    od = None if idu else st.date_input("📅 納品日", value=date.today() + timedelta(days=1))
    if idu: md('<div class="info-card yellow" style="background:#FFFBEB;padding:10px 16px;">🟡 <b>日付未定</b> として登録されます。</div>')
    tl = sorted(df_c["帳合先" if "帳合先" in df_c.columns else "顧客名"].dropna().unique().tolist()) if not df_c.empty else []
    t1,t2,t3 = st.columns([2, 2, 1]); stor = t1.selectbox("🏢 帳合先", options=tl, index=None, placeholder="選択…")
    scands = sorted(df_c[df_c["帳合先"]==stor]["支店名"].dropna().replace("","").unique().tolist()) if stor and not df_c.empty and "支店名" in df_c.columns else []
    sv = t2.selectbox("🏬 支店", options=["（なし）"]+scands, index=0) if scands else t2.text_input("🏬 支店（直接入力）")
    sv = "" if sv=="（なし）" else sv
    sc = t3.selectbox("🚚 運送", options=df_sm["運送会社名"].tolist() if not df_sm.empty else [], index=None)
    cf = st.pills("カテゴリ", CATS, default=CATS[0], label_visibility="collapsed"); cat = cf.split(" ",1)[1] if cf else CATS[0].split(" ",1)[1]
    s1,s2,s3 = st.columns([1.5, 2.5, 1.5]); s_p = s1.text_input("🔍 検索", placeholder="一部...")
    pl = [p for p in mst_u["製品名"].tolist() if s_p in p] if s_p else (mst_u[mst_u["大カテゴリ"]==cat]["製品名"].tolist() if not mst_u.empty else [])
    prod = s2.selectbox("製品", options=pl, index=None, format_func=fn)
    pr = mst_u[mst_u["製品名"]==prod] if not mst_u.empty and prod else pd.DataFrame()
    stype = s3.selectbox("⭐ 種別", ["（なし）","⭐ 特注","🚌 チャーター便"], index=1 if (not pr.empty and str(pr.iloc[0].get("特注フラグ","")).upper()=="TRUE") else (2 if (not pr.empty and str(pr.iloc[0].get("チャーターフラグ","")).upper()=="TRUE") else 0))
    nu, tan = pui(prod)
    if tan not in ["ケース","","nan","None"] and nu > 1:
        q1, q2 = st.columns([1, 2]); im = q1.radio(f"単位（1cs＝{nu}{tan}）", ["個数", "ケース数"], horizontal=True)
        if "個数" in im:
            rq = q2.number_input(f"📦 個数（{tan}）", min_value=1, step=1, value=None)
            qty = (int(rq)//nu) if rq and int(rq)>0 else None
            if rq: md(f"<div style='font-size:13px;color:#475569;'>➡ <b>{qty} cs</b>" + (f" <span style='color:#F59E0B;'>(端数切捨)</span>" if int(rq)%nu>0 else "") + "</div>")
        else:
            qty = q2.number_input("📦 ケース数", min_value=1, step=1, value=None)
            if qty: md(f"<div style='font-size:13px;color:#475569;'>≒ <b>{to_int(qty)*nu} {tan}</b></div>")
    else: qty = st.number_input("📦 ケース数", min_value=1, step=1, value=None)
    r1, r2 = st.columns([2, 2]); rem = r1.text_input("📝 備考"); c1, c2 = r2.columns(2); isub = c1.checkbox("🔄 代替品"); iirr = c2.checkbox("⚠️ 不良廃棄")
    
    if prod and qty and cs.get(prod,0) < to_int(qty):
        md(f'<div class="info-card red" style="background:#FEF2F2;">🚨 <b>在庫不足！</b> 現在庫: <b>{cs.get(prod,0)} cs</b> ／ 不足: <span class="shortage-red">－{to_int(qty)-cs.get(prod,0)} cs</span></div>')
    
    if st.session_state.get("msg_add"): st.success(st.session_state.msg_add); st.session_state.msg_add = None
    if st.button("✅ 登録", type="primary", use_container_width=True):
        if not prod or not qty: st.error("⚠️ 製品と数量は必須です。")
        else:
            frem = f"{'【代替品】' if isub else ''}{'【不良廃棄】' if iirr else ''} {'特注' if '特注' in stype else ('チャーター便' if 'チャーター' in stype else '')} {rem}".strip()
            cn = f"{stor} {sv}".strip() if sv else (stor if stor else "未指定")
            nid = str(uuid.uuid4())[:6].upper(); ddt = pd.to_datetime(od) if od else pd.NaT
            app_df("orders", pd.DataFrame([{"ID":nid,"納品予定日":ddt,"顧客名":cn,"大カテゴリ":cat,"製品名":prod,"ケース数":to_int(qty),"運送会社":sc or "","備考":frem,"荷姿チェック":False,"発送備考":"","不良廃棄フラグ":iirr,"日付未定フラグ":idu,"登録日時":datetime.now()}]))
            if ("特注" in stype or "チャーター" in stype) and od: app_df("special_schedule", pd.DataFrame([{"ID":str(uuid.uuid4())[:6].upper(),"受注ID":nid,"製品名":prod,"顧客名":cn,"納品予定日":ddt,"出荷予定日":ddt-timedelta(days=1),"備考":frem,"更新日時":datetime.now()}]))
            st.session_state.msg_add = f"✨ 登録完了: {prod} ({to_int(qty)}cs) {format_date_jp(od) if od else '日付未定'}"; st.rerun()

    udf = df_o[df_o["日付未定フラグ"]==True].copy().reset_index(drop=True) if not df_o.empty and "日付未定フラグ" in df_o.columns else pd.DataFrame()
    if not udf.empty:
        with st.expander(f"🟡 日付未定受注を確定する ({len(udf)}件)", expanded=True):
            udsp = udf[["ID","製品名","ケース数","備考","顧客名","運送会社"]].copy(); udsp.insert(4,"納品予定日(確定)",None); udsp.insert(5,"帳合先(確定)",""); udsp.insert(6,"支店名(確定)","")
            edu = st.data_editor(udsp, **df_kws, column_config={"ID":None,"製品名":st.column_config.TextColumn(disabled=True),"ケース数":st.column_config.NumberColumn(disabled=True),"備考":st.column_config.TextColumn(disabled=True),"顧客名":st.column_config.TextColumn(disabled=True),"納品予定日(確定)":st.column_config.DateColumn("📅 納品日",format="YYYY/MM/DD"),"帳合先(確定)":st.column_config.SelectboxColumn("🏢 帳合先",options=tl),"運送会社":st.column_config.SelectboxColumn("🚚 運送会社",options=df_sm["運送会社名"].tolist() if not df_sm.empty else [])})
            if st.button("✅ 日付確定保存", type="primary", use_container_width=True):
                upd = df_o.copy(); cnt=0
                for i, r in edu.iterrows():
                    oid = udf.iloc[i]["ID"] if i<len(udf) else None
                    if not oid or pd.isnull(r.get("納品予定日(確定)")): continue
                    m = upd["ID"]==oid
                    upd.loc[m,"納品予定日"] = pd.to_datetime(r.get("納品予定日(確定)")); upd.loc[m,"日付未定フラグ"] = False
                    if r.get("帳合先(確定)"): upd.loc[m,"顧客名"] = f"{r.get('帳合先(確定)')} {r.get('支店名(確定)','')}".strip()
                    if r.get("運送会社"): upd.loc[m,"運送会社"] = str(r.get("運送会社")).strip()
                    cnt+=1
                if cnt>0: save_df("orders",upd); st.rerun()

    sec("✏️ 直近データの修正・削除")
    if not df_o.empty:
        do = df_o.sort_values("登録日時",ascending=False).copy()
        do["納品予定日(表示)"] = do.apply(lambda r: "🟡 日付未定" if r.get("日付未定フラグ") is True else format_date_jp(r["納品予定日"]), axis=1) if "日付未定フラグ" in do.columns else do["納品予定日"].apply(format_date_jp)
        edo = st.data_editor(do.head(5)[["ID","納品予定日(表示)","顧客名","製品名","ケース数","運送会社","備考","不良廃棄フラグ"]], **df_kws, column_config={"ID":None,"ケース数":st.column_config.NumberColumn(min_value=1,step=1,format="%d")})
        if st.button("💾 直近データ保存"):
            sv = edo.copy(); sv["納品予定日"] = to_dt(sv["納品予定日(表示)"].str.replace("🟡 日付未定","").str.replace("🟡 ","").str.split(" ").str[0])
            save_df("orders", pd.concat([df_o[~df_o["ID"].isin(do.head(5)["ID"])], pd.merge(sv, df_o[[c for c in ["ID","大カテゴリ","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考","日付未定フラグ","登録日時"] if c in df_o.columns]], on="ID", how="left")], ignore_index=True)); st.rerun()
        with st.expander("📂 全データ一括編集"):
            eao = st.data_editor(do[["ID","納品予定日(表示)","顧客名","製品名","ケース数","運送会社","備考","不良廃棄フラグ"]], **df_kws, column_config={"ID":None,"ケース数":st.column_config.NumberColumn(min_value=1,step=1,format="%d")}, height=400)
            if st.button("💾 全データ保存"):
                sva = eao.copy(); sva["納品予定日"] = to_dt(sva["納品予定日(表示)"].str.replace("🟡 日付未定","").str.replace("🟡 ","").str.split(" ").str[0])
                save_df("orders", pd.merge(sva, df_o[[c for c in ["ID","大カテゴリ","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考","日付未定フラグ","登録日時"] if c in df_o.columns]], on="ID", how="left")); st.rerun()

# ─────────────────────────────────────────────
# 🚚 出荷・発送管理
# ─────────────────────────────────────────────
elif pg == "🚚 出荷・発送管理":
    hdr("🚚 出荷・発送 消込管理")
    t1, t2, t3 = st.tabs(["📋 日次消込", "📅 週間出荷一覧", "📥 CSV出力"])
    with t1:
        td = st.date_input("📅 対象日", value=date.today())
        dor = df_o[(safe_dt_date(df_o["納品予定日"])==td) & (df_o["不良廃棄フラグ"]==False)].copy() if not df_o.empty else pd.DataFrame()
        if dor.empty: st.info(f"📭 {format_date_jp(td)} の予定なし")
        else:
            dn = dor[dor["荷姿チェック"]==True]; udn = dor[dor["荷姿チェック"]==False]
            c1,c2,c3 = st.columns(3); c1.metric("出荷件数", f"{len(dor)} 件"); c2.metric("✅ 消込済", f"{len(dn)} 件"); c3.metric("⏳ 未消込", f"{len(udn)} 件", delta_color="inverse")
            if not udn.empty and td <= date.today(): st.error(f"🚨 出荷漏れ（荷姿未チェック）が **{len(udn)} 件** あります！")
            ddf = dor[["ID","顧客名","製品名","ケース数","運送会社","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考"]].copy()
            for c in ["賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5"]: ddf[c] = to_dt(ddf[c]).dt.date
            eds = st.data_editor(ddf.style.apply(lambda r: ['background-color:#D1FAE5;color:#065F46;text-decoration:line-through;']*len(r) if str(r.get("荷姿チェック",False)).upper()=="TRUE" else ['']*len(r), axis=1), **df_kws, column_config={"ID":None,"顧客名":st.column_config.TextColumn(disabled=True),"製品名":st.column_config.TextColumn(disabled=True),"ケース数":st.column_config.NumberColumn(disabled=True),"運送会社":st.column_config.SelectboxColumn(options=df_sm["運送会社名"].tolist() if not df_sm.empty else []),"賞味期限1":st.column_config.DateColumn("賞味1",format="YYYY-MM-DD")})
            if st.button("💾 保存", type="primary", use_container_width=True):
                u = df_o.copy().astype(object)
                for i, r in eds.iterrows():
                    m = u["ID"]==r["ID"]
                    if m.any():
                        u.loc[m,"運送会社"] = str(r.get("運送会社","")); u.loc[m,"荷姿チェック"] = str(r.get("荷姿チェック",False)).upper(); u.loc[m,"発送備考"] = str(r.get("発送備考",""))
                        for c in ["賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5"]: v=r.get(c); u.loc[m,c] = v.strftime("%Y-%m-%d") if pd.notnull(v) and v else ""
                save_df("orders", u); st.rerun()

    with t2:
        c1, c2 = st.columns([2, 2]); sw = c1.date_input("開始日", value=date.today()); wd = c2.number_input("日数", min_value=1, max_value=30, value=7)
        if st.radio("モード", ["📋 折りたたみ", "📊 全件"], horizontal=True) == "📋 折りたたみ":
            for i in range(int(wd)):
                d = pd.Timestamp(sw)+timedelta(days=i)
                wo = df_o[safe_dt_date(df_o["納品予定日"])==d.date()].copy() if not df_o.empty else pd.DataFrame()
                if not wo.empty:
                    with st.expander(f"**{format_date_jp(d)}**　{len(wo)}件 ✅{len(wo[wo['荷姿チェック']==True])}件完了", expanded=(d.date()==date.today())):
                        st.dataframe(wo[["顧客名","製品名","ケース数","運送会社","荷姿チェック","発送備考"]].style.apply(lambda r: ['background-color:#D1FAE5;']*len(r) if r.get("荷姿チェック")==True else ['']*len(r), axis=1), **df_kws)
        else:
            aw = pd.concat([df_o[safe_dt_date(df_o["納品予定日"])==(pd.Timestamp(sw)+timedelta(days=i)).date()].assign(納品日=format_date_jp(pd.Timestamp(sw)+timedelta(days=i))) for i in range(int(wd))], ignore_index=True) if not df_o.empty else pd.DataFrame()
            if aw.empty: st.info("予定なし")
            else:
                c1,c2,c3=st.columns(3); c1.metric("件数",f"{len(aw)}件"); c2.metric("✅ 消込済",f"{len(aw[aw['荷姿チェック']==True])}件"); c3.metric("総数",f"{aw['ケース数'].apply(to_int).sum():,}cs")
                sc = [c for c in ["納品日","顧客名","製品名","ケース数","運送会社","荷姿チェック","発送備考","備考"] if c in aw.columns]
                st.dataframe(aw[sc].style.apply(lambda r: ['background-color:#D1FAE5;color:#065F46;']*len(r) if r.get("荷姿チェック")==True else ['']*len(r), axis=1), **df_kws, height=min(600, max(300, len(aw)*38+60)))

    with t3:
        ce1, ce2 = st.columns(2); es = ce1.date_input("開始", value=date.today().replace(day=1)); ee = ce2.date_input("終了", value=date.today())
        if not df_o.empty:
            edf = df_o[(safe_dt_date(df_o["納品予定日"])>=es) & (safe_dt_date(df_o["納品予定日"])<=ee)].copy()
            for c in ["納品予定日","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5"]:
                if c in edf.columns: edf[c] = to_dt(edf[c]).apply(dt_str)
            edf["荷姿チェック"] = edf["荷姿チェック"].map({True:"済",False:"未"}).fillna("")
            st.metric("件数", f"{len(edf)} 件")
            st.download_button("📥 CSV", data=make_csv_bytes(edf[[c for c in ["納品予定日","顧客名","製品名","ケース数","運送会社","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考","備考"] if c in edf.columns]]), file_name=f"出荷_{es}_{ee}.csv", mime="text/csv", type="primary", use_container_width=True)

# ─────────────────────────────────────────────
# 🏭 製造登録
# ─────────────────────────────────────────────
elif pg == "🏭 製造登録":
    hdr("🏭 製造・リパック 登録")
    c1, c2 = st.columns([1,1])
    mdt = c1.date_input("📅 製造日", value=date.today()); mq = c2.number_input("📦 ケース数", min_value=1, step=1, value=None)
    cf = st.pills("カテゴリ", CATS, default=CATS[0], label_visibility="collapsed"); c_m = cf.split(" ",1)[1] if cf else CATS[0].split(" ",1)[1]
    s1, s2 = st.columns([1.5, 2.5]); sp = s1.text_input("🔍 検索", placeholder="一部...")
    pl = [p for p in mst_u["製品名"].tolist() if sp in p] if sp else (mst_u[mst_u["大カテゴリ"]==c_m]["製品名"].tolist() if not mst_u.empty else [])
    pm = s2.selectbox("製品", options=pl, index=None, format_func=fn); mr = s2.text_input("📝 備考")
    irp = st.checkbox("🔄 リパック（在庫加算）"); ipl = st.checkbox("📦 資材減らす", value=True) if irp else True
    if pm and mq and cs.get(pm,0)<=0: md(f"<div class='info-card red' style='background:#FEF2F2; padding:10px;'>現在庫: <span class='shortage-red'>{cs.get(pm,0)} cs</span> → 製造後: <b>{cs.get(pm,0)+to_int(mq)} cs</b></div>")
    
    m_add = st.empty()
    if st.session_state.get("msg_m_add"): m_add.success(st.session_state.msg_m_add); st.session_state.msg_m_add = None

    if st.button("➕ 記録", type="primary", use_container_width=True):
        if not pm or not mq: m_add.error("⚠️ 必須")
        else:
            rt = f"{'【リパック】' if irp else ''} {'【資材非連動】' if irp and not ipl else ''} {mr}".strip(); nid = str(uuid.uuid4())[:6].upper()
            app_df("manufactures", pd.DataFrame([{"ID":nid,"製造予定日":to_dt(mdt),"大カテゴリ":c_m,"製品名":pm,"ケース数":to_int(mq),"リパックフラグ":irp,"備考":rt,"登録日時":datetime.now()}]))
            if ipl and not mst_u.empty and pm in mst_u.set_index("製品名")[["使用資材名","資材使用数"]].to_dict('index'):
                mpi = mst_u.set_index("製品名")[["使用資材名","資材使用数"]].to_dict('index'); pnn = mpi[pm].get("使用資材名",""); puu = to_int(mpi[pm].get("資材使用数",0))
                if pnn and puu>0: app_df("packaging_logs", pd.DataFrame([{"ID":str(uuid.uuid4())[:6].upper(),"登録日":to_dt(mdt),"資材名":pnn,"処理区分":"製造連動","数量":abs(to_int(mq)*puu),"理由":f"製造ID:{nid}","関連製品名":pm,"理論在庫":ps.get(pnn,{}).get("現",0)-(to_int(mq)*puu),"備考":"自動記録","登録日時":datetime.now()}]))
            st.session_state.msg_m_add = f"✨ 完了: {pm} ({to_int(mq)}cs)"; st.rerun()

    sec("✏️ 修正・削除")
    if not df_m.empty:
        dm = df_m.sort_values("登録日時", ascending=False).copy(); dm["製造予定日(表示)"] = dm["製造予定日"].apply(format_date_jp)
        edm = st.data_editor(dm.head(5)[["ID","製造予定日(表示)","製品名","ケース数","リパックフラグ","備考"]], num_rows="dynamic", **df_kws, column_config={"ID":None,"ケース数":st.column_config.NumberColumn(min_value=1,step=1,format="%d")})
        if st.button("💾 直近保存"):
            sm = edm.copy(); sm["製造予定日"] = to_dt(sm["製造予定日(表示)"].str.split(" ").str[0])
            save_df("manufactures", pd.concat([df_m[~df_m["ID"].isin(dm.head(5)["ID"])], pd.merge(sm, df_m[["ID","大カテゴリ","登録日時"]], on="ID", how="left")], ignore_index=True)); st.rerun()
        with st.expander("📂 全件編集"):
            eam = st.data_editor(dm[["ID","製造予定日(表示)","製品名","ケース数","リパックフラグ","備考"]], num_rows="dynamic", **df_kws, column_config={"ID":None,"ケース数":st.column_config.NumberColumn(min_value=1,step=1,format="%d")}, height=400)
            if st.button("💾 全件保存"):
                sma = eam.copy(); sma["製造予定日"] = to_dt(sma["製造予定日(表示)"].str.split(" ").str[0])
                save_df("manufactures", pd.merge(sma, df_m[["ID","大カテゴリ","登録日時"]], on="ID", how="left")); st.rerun()

# ─────────────────────────────────────────────
# 📦 資材・入出庫
# ─────────────────────────────────────────────
elif pg == "📦 資材・入出庫":
    hdr("📦 資材・段ボール入出庫")
    s_pks = [pn for pn,d in ps.items() if d["現"] < d["点"]]
    if s_pks: st.error("🚨 **要発注:** " + "、".join(s_pks))
    t1, t2, t3, t4 = st.tabs(["📦 予測","📊 サマリ","📝 登録","✏️ 履歴"])

    with t1:
        if df_pm.empty: st.warning("マスタ空")
        else:
            fd = 90; pf = {}
            if not mst_u.empty and not df_o.empty:
                mpi = mst_u.set_index("製品名")[["使用資材名","資材使用数"]].to_dict("index")
                for _, r in df_o.iterrows():
                    p, q, dt = str(r.get("製品名","")), to_int(r.get("ケース数",0)), to_dt(r.get("納品予定日"))
                    if pd.isna(dt) or dt.date()<date.today() or dt>today+timedelta(days=fd) or p not in mpi: continue
                    pn, pu = str(mpi[p].get("使用資材名","")), to_int(mpi[p].get("資材使用数", 0))
                    if pn and pu>0: pf.setdefault(pn, {})[dt.normalize()] = pf.get(pn,{}).get(dt.normalize(), 0) + q*pu
            for p in ps.keys(): pf.setdefault(p, {})
            
            oa = []
            for pn, du in pf.items():
                lt = ps.get(pn,{}).get("LT",7) or 7; ci = ps.get(pn,{}).get("現",0); pt = ps.get(pn,{}).get("点",0)
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
                for _, r in u_df.iterrows(): md(f'<div style="background:{r["_c"]};border-left:6px solid {r["_b"]};border-radius:10px;padding:14px;margin-bottom:10px;"><b>📦 {r["資材名"]}</b> <span style="float:right;font-weight:900;">{r["緊急度"]}</span><br><span style="font-size:13px;">庫: {r["現在庫"]:,} | 点: {r["発注点"]:,} | LT: {r["LT"]}日<br>⏰ <b>到達: {r["到達日"]}</b><br>📉 <b>枯渇: {r["枯渇予測"]}</b></span></div>')
            st.dataframe(df_a[["資材名","現在庫","発注点","LT","90日消費","発注推奨日","到達日","予測在庫","枯渇予測","緊急度"]].style.apply(lambda r: ['background-color:#FEE2E2;font-weight:bold;']*len(r) if "今すぐ" in str(r.get("緊急度","")) else (['background-color:#FFF7ED;']*len(r) if "🟠" in str(r.get("緊急度","")) else (['background-color:#FFFBEB;']*len(r) if "🟡" in str(r.get("緊急度","")) else (['background-color:#EFF6FF;']*len(r) if "🔵" in str(r.get("緊急度","")) else ['background-color:#F0FDF4;']*len(r)))), axis=1), **df_kws, height=500)

            spg = st.selectbox("グラフ表示", options=[r["資材名"] for _, r in pm_u.iterrows()])
            if spg:
                ri = ps.get(spg,{}).get("現",0); gd, gs, gu = [], [], []
                for d_g in pd.date_range(today, today+timedelta(days=fd)):
                    ug = pf.get(spg,{}).get(d_g,0); ri-=ug; gd.append(d_g.strftime("%m/%d")); gs.append(ri); gu.append(ug)
                fig = go.Figure()
                fig.add_trace(go.Bar(x=gd, y=gu, name="消費", marker_color="#F43F5E", opacity=0.55))
                fig.add_trace(go.Scatter(x=gd, y=gs, name="在庫", mode="lines+markers", line=dict(color="#2563EB", width=2.5)))
                fig.add_hline(y=ps.get(spg,{}).get("点",0), line_dash="dash", line_color="#F59E0B", annotation_text="発注点")
                fig.add_hline(y=0, line_dash="dot", line_color="#DC2626", annotation_text="ゼロ")
                fig.update_layout(title=f"【{spg}】 在庫推移", hovermode="x unified", barmode="relative", margin=dict(l=10,r=10,t=55,b=10), height=380); st.plotly_chart(fig, use_container_width=True)

    with t2:
        st.dataframe(pd.DataFrame([{"資材名":k,"品番":v["品番"],"規格":v["規格"],"仕入先":v["仕入先"],"保管場所":v["保管場所"],"現在庫":v["現"],"発注点":v["点"],"状態":v["状態"],"単位":v["単位"]} for k,v in ps.items()]).style.apply(lambda r: ['background-color:#FFEDD5;color:#C2410C;font-weight:bold;']*len(r) if to_int(r.get("現在庫",0))<to_int(r.get("発注点",0)) else ['']*len(r),axis=1), **df_kws)

    with t3:
        pd_t = st.date_input("📅 処理日", value=date.today())
        c1,c2 = st.columns([1.5,2.5]); s_pk = c1.text_input("🔍 検索"); f_pk = [p for p in pm_u["資材名"].tolist() if s_pk in p] if s_pk else pm_u["資材名"].tolist()
        sl_pk = c2.selectbox("📦 資材", options=f_pk, index=None)
        pt = st.radio("区分", ["📥 入庫","📤 出庫","📋 棚卸"], horizontal=True)
        if "棚卸" in pt: pq = st.number_input("実在庫", min_value=0, step=1, value=None); ro = ["棚卸調整"]
        else: pq = st.number_input("数量", min_value=1, step=1, value=None); ro = ["仕入","返品","その他入庫"] if "入庫" in pt else ["破損","サンプル","その他出庫"]
        pr = st.selectbox("理由", options=ro); prm = st.text_input("📝 備考")
        
        m_add = st.empty()
        if st.session_state.get("msg_p_add"): m_add.success(st.session_state.msg_p_add); st.session_state.msg_p_add = None

        if st.button("➕ 登録", type="primary", use_container_width=True):
            if not sl_pk or pq is None: m_add.error("⚠️ 必須")
            else:
                lq = to_int(pq); fpt = "入庫" if "入庫" in pt else "出庫"
                if "棚卸" in pt: df = lq - ps.get(sl_pk,{}).get("現",0); fpt, lq = ("入庫", df) if df>=0 else ("出庫", abs(df))
                if lq>0:
                    app_df("packaging_logs", pd.DataFrame([{"ID":str(uuid.uuid4())[:6].upper(),"登録日":to_dt(pd_t),"資材名":sl_pk,"処理区分":fpt,"数量":lq,"理由":pr,"関連製品名":"","理論在庫":"","備考":prm,"登録日時":datetime.now()}]))
                    st.session_state.msg_p_add = f"✨ 登録: {sl_pk} ({fpt} {lq})"; st.rerun()

    with t4:
        dpk = df_pl.sort_values("登録日時",ascending=False).copy() if not df_pl.empty else pd.DataFrame()
        if not dpk.empty:
            dpk["登録日(表示)"] = dpk["登録日"].apply(format_date_jp) if "登録日" in dpk.columns else ""
            edp = st.data_editor(dpk.head(5)[[c for c in ["ID","登録日(表示)","資材名","処理区分","数量","理由","関連製品名","備考"] if c in dpk.columns]], hide_index=True, column_config={"ID":None,"処理区分":st.column_config.SelectboxColumn(options=["入庫","出庫","製造連動"]),"数量":st.column_config.NumberColumn(min_value=1,step=1,format="%d")})
            if st.button("💾 保存", key="btn_spk"): save_df("packaging_logs", pd.concat([df_pl[~df_pl["ID"].isin(dpk.head(5)["ID"])], pd.merge(edp.assign(登録日=to_dt(edp["登録日(表示)"].str.split(" ").str[0])), df_pl[["ID","理論在庫","登録日時"]], on="ID", how="left")], ignore_index=True)); st.rerun()

# ─────────────────────────────────────────────
# 📑 登録一覧
# ─────────────────────────────────────────────
elif pg == "📑 登録一覧":
    hdr("📑 登録データ一覧")
    t1, t2, t3 = st.tabs(["📋 受注","🏭 製造","📦 資材"])
    with t1:
        if not df_o.empty:
            eo = df_o.sort_values("登録日時", ascending=False).copy(); eo["納品日"] = eo["納品予定日"].apply(format_date_jp)
            eo["在庫状況"] = eo.apply(lambda r: f"不足 ({fs.get(r['製品名'],{}).get(pd.Timestamp(str(r['納品日']).split(' ')[0]).normalize(),0)})" if fs.get(r['製品名'],{}).get(pd.Timestamp(str(r['納品日']).split(' ')[0]).normalize(),0)<0 else "OK", axis=1)
            st.dataframe(eo[["ID","納品日","顧客名","製品名","ケース数","運送会社","備考","荷姿チェック","在庫状況","不良廃棄フラグ"]].style.apply(lambda r: ['background-color:#D1FAE5;']*len(r) if str(r.get("荷姿チェック")).upper()=="TRUE" else (['background-color:#FEE2E2;font-weight:bold;']*len(r) if "不足" in str(r.get("在庫状況","")) else ['']*len(r)), axis=1), hide_index=True, height=600)
    with t2:
        if not df_m.empty:
            em = df_m.sort_values("登録日時",ascending=False).copy(); em["製造日"] = em["製造予定日"].apply(format_date_jp)
            st.dataframe(em[["ID","製造日","製品名","ケース数","リパックフラグ","備考"]].style.apply(lambda r: ['background-color:#DBEAFE;font-weight:bold;']*len(r) if str(r.get("リパックフラグ")).upper()=="TRUE" else (['background-color:#F8FAFC;color:#64748B;']*len(r) if "【在庫非反映】" in str(r.get("備考","")) else ['']*len(r)), axis=1), hide_index=True, height=600)
    with t3:
        if not df_pl.empty:
            el = df_pl.sort_values("登録日時",ascending=False).copy(); el["日"] = el["登録日"].apply(format_date_jp)
            st.dataframe(el[["ID","日","資材名","処理区分","数量","理由","関連製品名","備考"]], hide_index=True, height=600)
            # ─────────────────────────────────────────────
# 📊 在庫・スケジュール
# ─────────────────────────────────────────────
elif pg == "📊 在庫・スケジュール":
    hdr("📊 在庫予測 ＆ スケジュール")
    t0, t1, t2, t3, t4 = st.tabs(["⚠️ 7日以内欠品予測", "📉 1ヶ月在庫予測", "📅 週間カレンダー", "🔍 製品別詳細ビュー", "👤 顧客別スケジュール"])

    with t0:
        al = []
        for p, d_fs in fs.items():
            for d in pd.date_range(today, today+timedelta(days=7)):
                if d_fs.get(d,0)<0:
                    do = df_o[(df_o["製品名"]==p)&(safe_dt_date(df_o["納品予定日"])==d.date())&(df_o["不良廃棄フラグ"]==False)] if not df_o.empty else pd.DataFrame()
                    al.append({"日付":format_date_jp(d),"製品名":p,"予測在庫":d_fs.get(d,0),"現在庫":cs.get(p,0),"顧客名":" / ".join(do["顧客名"].dropna().unique()) if not do.empty else "―","備考":" / ".join(do["備考"].dropna().unique()) if not do.empty else ""})
        if al:
            da = pd.DataFrame(al).drop_duplicates()
            st.dataframe(da.style.map(lambda v: 'color:#DC2626;font-weight:900;background-color:#FEE2E2;' if isinstance(v,(int,float)) and v<0 else '', subset=["予測在庫"]), **df_kws)
            st.download_button("📥 欠品アラート出力", data=make_csv_bytes(da), file_name=f"欠品アラート_{date.today()}.csv", mime="text/csv")
        else: st.success("✅ 欠品予測なし")

    with t1:
        if mst_u.empty: st.info("マスタ空")
        else:
            sd = pd.date_range(today, today+timedelta(days=30))
            iv = [{"カテゴリ":r["大カテゴリ"],"製品名":r["製品名"],"現在庫":cs.get(r["製品名"],0), **{format_date_jp(d):fs.get(r["製品名"],{}).get(d,cs.get(r["製品名"],0)) for d in sd}} for _,r in mst_u.iterrows()]
            idf = pd.DataFrame(iv).sort_values("カテゴリ").reset_index(drop=True)
            c1, c2 = st.columns([3, 1]); c1.markdown('<div style="font-size:13px;color:#64748B;">💡 行クリックで詳細展開</div>', unsafe_allow_html=True)
            if c2.button("🔄 閉じる"): st.session_state.drill = None; st.rerun()
            se = st.dataframe(idf.style.map(lambda v: 'color:#DC2626;font-weight:bold;background-color:#FEE2E2;' if isinstance(v,(int,float)) and v<0 else ''), use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
            if se.selection.get("rows"): st.session_state.drill = idf.iloc[se.selection.get("rows")[0]]["製品名"]

            dp = st.session_state.drill
            if dp:
                md(f'<div class="drill-panel">### 📦 {fn(dp)} 詳細')
                oy = today - timedelta(days=365)
                ph = df_o[(df_o["製品名"]==dp)&(to_dt(df_o["納品予定日"])>=oy)&(to_dt(df_o["納品予定日"])<today)].copy() if not df_o.empty else pd.DataFrame()
                mh = df_m[(df_m["製品名"]==dp)&(to_dt(df_m["製造予定日"])>=oy)&(to_dt(df_m["製造予定日"])<today)].copy() if not df_m.empty else pd.DataFrame()
                
                with st.expander("📜 過去1年履歴", expanded=True):
                    tho = ph["ケース数"].apply(to_int).sum() if not ph.empty else 0; thm = mh["ケース数"].apply(to_int).sum() if not mh.empty else 0
                    k1,k2,k3,k4 = st.columns(4)
                    k1.metric("出荷合計",f"{tho:,} cs"); k2.metric("製造合計",f"{thm:,} cs"); k3.metric("差引",f"{thm-tho:+,} cs"); k4.metric("現在庫",f"{cs.get(dp,0):,} cs")
                    ch1, ch2 = st.columns(2)
                    with ch1:
                        md('<div style="font-weight:800;color:#DC2626;border-left:4px solid #DC2626;padding-left:8px;">🚚 出荷履歴</div>')
                        if not ph.empty: st.dataframe(ph.assign(日付=ph["納品予定日"].apply(format_date_jp))[["日付","顧客名","ケース数","備考"]].sort_values("日付",ascending=False), hide_index=True)
                    with ch2:
                        md('<div style="font-weight:800;color:#059669;border-left:4px solid #059669;padding-left:8px;">🏭 製造履歴</div>')
                        if not mh.empty: st.dataframe(mh.assign(日付=mh["製造予定日"].apply(format_date_jp))[["日付","ケース数","備考"]].sort_values("日付",ascending=False).style.apply(lambda r: ["background:#F8FAFC;color:#64748B;"]*len(r) if "【在庫非反映】" in str(r.get("備考","")) else [""]*len(r), axis=1), hide_index=True)

                md('<div class="section-title">📅 今後60日間スケジュール</div>')
                pof = df_o[(df_o["製品名"]==dp)&(to_dt(df_o["納品予定日"])>=today)] if not df_o.empty else pd.DataFrame()
                pmf = df_m[(df_m["製品名"]==dp)&(to_dt(df_m["製造予定日"])>=today)&(~df_m["備考"].fillna("").str.contains("【在庫非反映】"))] if not df_m.empty else pd.DataFrame()
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
                md('</div>')

    with t2:
        html = '<table class="sched-table"><tr><th style="width:130px;">日付</th><th style="width:38%;">🏭 製造 / リパック</th><th style="width:44%;">🚚 出荷 / 不良廃棄</th></tr>'
        for i in range(7):
            d2 = today+timedelta(days=i); mh=""; oh=""
            if not df_m.empty:
                for _,r in df_m[to_dt(df_m["製造予定日"]).dt.normalize()==d2].iterrows():
                    if "【在庫非反映】" in str(r.get("備考","")): continue
                    bg,bc = ("#DBEAFE","#1E3A8A") if r.get("リパックフラグ") in [True,"TRUE"] else ("#F0FFF4","#10B981")
                    mh+=f'<div style="background:{bg};border-left:4px solid {bc};padding:6px;margin-bottom:4px;"><b>{fn(r["製品名"])}</b><span style="float:right;">{to_int(r.get("ケース数",0))}cs</span></div>'
            if not df_o.empty:
                for _,r in df_o[to_dt(df_o["納品予定日"]).dt.normalize()==d2].iterrows():
                    sod = fs.get(r["製品名"],{}).get(d2,0)
                    qh, bg, bc = "", "#F0F7FF", "#2563EB"
                    if r.get("荷姿チェック") in [True,"TRUE"]: qh, bg, bc = f'<span style="text-decoration:line-through;">{to_int(r.get("ケース数",0))}cs</span>', "#D1FAE5", "#059669"
                    elif r.get("不良廃棄フラグ") in [True,"TRUE"]: qh, bg, bc = f'<span style="color:#B45309;font-weight:900;">{to_int(r.get("ケース数",0))}cs(不良)</span>', "#FEF3C7", "#D97706"
                    elif sod < 0: qh, bg, bc = f'<span class="shortage-red">{to_int(r.get("ケース数",0))}cs(不足)</span>', "#FEE2E2", "#DC2626"
                    else: qh, bg, bc = f'<span style="color:#1D4ED8;font-weight:900;">{to_int(r.get("ケース数",0))}cs</span>', "#F0F7FF", "#2563EB"
                    oh+=f'<div style="background:{bg};border-left:4px solid {bc};padding:6px;margin-bottom:4px;"><b>{r["顧客名"]}: {fn(r["製品名"])}</b><span style="float:right;">{qh}</span></div>'
            html+=f'<tr><td><b>{format_date_jp(d2)}</b></td><td>{mh or "なし"}</td><td>{oh or "なし"}</td></tr>'
        md(html+'</table>')

    with t3:
        sec("🔍 製品別 詳細ビュー")
        cfd = st.pills("カテ詳細", CATS, default=CATS[0], label_visibility="collapsed"); c_det = cfd.split(" ",1)[1] if cfd else CATS[0].split(" ",1)[1]
        sc1, sc2 = st.columns([1.5,2.5]); s_d = sc1.text_input("🔍 検索", key="sd")
        p_d = [p for p in mst_u["製品名"].tolist() if s_d in p] if s_d else mst_u[mst_u["大カテゴリ"]==c_det]["製品名"].tolist() if not mst_u.empty else []
        sp = sc2.selectbox("製品", options=p_d, index=None, format_func=fn)
        if sp:
            oy = today-timedelta(days=365)
            poa = df_o[(df_o["製品名"]==sp)&(to_dt(df_o["納品予定日"])>=oy)&(to_dt(df_o["納品予定日"])<today)] if not df_o.empty else pd.DataFrame()
            pma = df_m[(df_m["製品名"]==sp)&(to_dt(df_m["製造予定日"])>=oy)&(to_dt(df_m["製造予定日"])<today)] if not df_m.empty else pd.DataFrame()
            k1,k2,k3,k4 = st.columns(4); k1.metric("現在庫",f"{cs.get(sp,0):,} cs"); k2.metric("過去1年 出荷",f"{poa['ケース数'].apply(to_int).sum() if not poa.empty else 0:,} cs"); k3.metric("過去1年 製造",f"{pma['ケース数'].apply(to_int).sum() if not pma.empty else 0:,} cs"); k4.metric("7日以内 欠品日数",f"{sum(1 for d in pd.date_range(today,today+timedelta(days=7)) if fs.get(sp,{}).get(d,0)<0)} 日")
            dth, dtf, dtg = st.tabs(["📜 履歴", "📅 予定", "📈 月次グラフ"])
            with dth:
                with st.expander("➕ 過去の実績を登録（在庫非反映）", expanded=False):
                    h1,h2,h3 = st.columns([1,1,2]); hd = h1.date_input("日", value=today-timedelta(days=1)); hq = h2.number_input("数", min_value=1, step=1); hr = h3.text_input("備考", placeholder="過去実績")
                    m_add_h = st.empty()
                    if st.session_state.get("msg_h_add"): m_add_h.success(st.session_state.msg_h_add); st.session_state.msg_h_add = None
                    if st.button("💾 登録（非反映）"):
                        app_df("manufactures", pd.DataFrame([{"ID":str(uuid.uuid4())[:6].upper(),"製造予定日":to_dt(hd),"大カテゴリ":c_det,"製品名":sp,"ケース数":to_int(hq),"リパックフラグ":False,"備考":f"【在庫非反映】 {hr}".strip(),"登録日時":datetime.now()}]))
                        st.session_state.msg_h_add = f"✅ {sp} の過去実績（{hq}cs）を登録しました！"; st.rerun()
                tc1, tc2 = st.columns(2)
                with tc1:
                    md('<div style="font-weight:800;color:#DC2626;border-left:4px solid #DC2626;padding-left:8px;">🚚 出荷履歴</div>')
                    if not poa.empty: st.dataframe(poa.assign(日付=poa["納品予定日"].apply(format_date_jp))[["日付","顧客名","ケース数","備考"]].sort_values("日付",ascending=False), hide_index=True)
                with tc2:
                    md('<div style="font-weight:800;color:#059669;border-left:4px solid #059669;padding-left:8px;">🏭 製造履歴</div>')
                    if not pma.empty: st.dataframe(pma.assign(日付=pma["製造予定日"].apply(format_date_jp))[["日付","ケース数","備考"]].sort_values("日付",ascending=False).style.apply(lambda r: ["background:#F8FAFC;color:#64748B;"]*len(r) if "【在庫非反映】" in str(r.get("備考","")) else [""]*len(r), axis=1), hide_index=True)
            with dtg:
                gr = []
                if not poa.empty:
                    po_m = poa.copy(); po_m["年月"] = to_dt(po_m["納品予定日"]).dt.to_period("M").astype(str)
                    for ym, g in po_m.groupby("年月"): gr.append({"年月": ym, "種別": "出荷(実績)", "ケース数": g["ケース数"].apply(to_int).sum()})
                if not pma.empty:
                    pm_m = pma.copy(); pm_m["年月"] = to_dt(pm_m["製造予定日"]).dt.to_period("M").astype(str)
                    for ym, g in pm_m.groupby("年月"): gr.append({"年月": ym, "種別": "製造(実績)", "ケース数": g["ケース数"].apply(to_int).sum()})
                fo = df_o[(df_o["製品名"]==sp)&(to_dt(df_o["納品予定日"])>=today)] if not df_o.empty else pd.DataFrame()
                vm3 = df_m[~df_m["備考"].fillna("").str.contains("【在庫非反映】")] if not df_m.empty else pd.DataFrame()
                fm = vm3[(vm3["製品名"]==sp)&(to_dt(vm3["製造予定日"])>=today)] if not vm3.empty else pd.DataFrame()
                if not fo.empty:
                    fom = fo.copy(); fom["年月"] = to_dt(fom["納品予定日"]).dt.to_period("M").astype(str)
                    for ym, g in fom.groupby("年月"): gr.append({"年月": ym, "種別": "出荷(予定)", "ケース数": g["ケース数"].apply(to_int).sum()})
                if not fm.empty:
                    fmm = fm.copy(); fmm["年月"] = to_dt(fmm["製造予定日"]).dt.to_period("M").astype(str)
                    for ym, g in fmm.groupby("年月"): gr.append({"年月": ym, "種別": "製造(予定)", "ケース数": g["ケース数"].apply(to_int).sum()})
                if gr:
                    dg = pd.DataFrame(gr).sort_values("年月")
                    fig = px.bar(dg, x="年月", y="ケース数", color="種別", barmode="group", color_discrete_map={"出荷(実績)":"#F43F5E","出荷(予定)":"#FCA5A5","製造(実績)":"#10B981","製造(予定)":"#6EE7B7"})
                    st.plotly_chart(fig, use_container_width=True)

    with t4:
        sec("👤 顧客別 今後の予定")
        cl = sorted(df_o[df_o["顧客名"].str.strip()!=""]["顧客名"].unique().tolist()) if not df_o.empty else []
        sc1c,sc2c = st.columns([1.5,2.5]); sc_c = sc1c.text_input("🔍 顧客検索"); sl_c = sc2c.selectbox("顧客", options=[c for c in cl if sc_c in c] if sc_c else cl, index=None)
        if sl_c:
            co = df_o[(df_o["顧客名"]==sl_c)&(to_dt(df_o["納品予定日"])>=today)].copy()
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
    spo = df_o[df_o["備考"].apply(is_special_order)].copy() if not df_o.empty else pd.DataFrame()
    ts1, ts2, ts3 = st.tabs(["📋 一覧","📅 製品別スケジュール","✏️ 編集・保存"])
    with ts1:
        if spo.empty: st.info("なし")
        else:
            spo["種別"] = spo["備考"].apply(lambda r: "特注+チャーター便" if "特注" in str(r) and "チャーター便" in str(r) else ("特注" if "特注" in str(r) else "チャーター便"))
            spo["納品予定日(表示)"] = spo["納品予定日"].apply(format_date_jp)
            sm = pd.merge(spo, df_sp[["受注ID","出荷予定日"]].rename(columns={"受注ID":"ID"}), on="ID", how="left") if not df_sp.empty else spo.assign(出荷予定日="（未設定）")
            if "出荷予定日" in sm and pd.api.types.is_datetime64_any_dtype(sm["出荷予定日"]): sm["出荷予定日"] = sm["出荷予定日"].apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "（未設定）")
            sc = [c for c in ["種別","顧客名","納品予定日(表示)","出荷予定日","製品名","ケース数","備考"] if c in sm.columns]
            st.dataframe(sm[sc].style.apply(lambda r: ['background-color:#F3E8FF;font-weight:bold;']*len(r) if "特注" in str(r.get("種別","")) and "チャーター" in str(r.get("種別","")) else (['background-color:#EDE9FE;font-weight:bold;']*len(r) if "特注" in str(r.get("種別","")) else ['background-color:#E0F2FE;font-weight:bold;']*len(r)), axis=1), hide_index=True)
    with ts2:
        if not spo.empty:
            pl = sorted(spo["製品名"].unique().tolist()); sl = st.selectbox("製品", ["（全製品）"]+pl)
            fsp = (spo.copy() if sl=="（全製品）" else spo[spo["製品名"]==sl].copy()).sort_values("納品予定日")
            fsp["納品予定日(表示)"] = fsp["納品予定日"].apply(format_date_jp)
            fsm = pd.merge(fsp, df_sp[["受注ID","出荷予定日"]].rename(columns={"受注ID":"ID"}), on="ID", how="left") if not df_sp.empty else fsp.assign(出荷予定日="（未設定）")
            if "出荷予定日" in fsm and pd.api.types.is_datetime64_any_dtype(fsm["出荷予定日"]): fsm["出荷予定日"] = fsm["出荷予定日"].apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "（未設定）")
            st.dataframe(fsm[[c for c in ["製品名","顧客名","納品予定日(表示)","出荷予定日","ケース数","備考"] if c in fsm.columns]], hide_index=True)
    with ts3:
        if not spo.empty:
            ex = df_sp["受注ID"].tolist() if not df_sp.empty else []; nr = [{"ID":str(uuid.uuid4())[:6].upper(),"受注ID":r["ID"],"製品名":r["製品名"],"顧客名":r["顧客名"],"納品予定日":r["納品予定日"],"出荷予定日":r["納品予定日"]-timedelta(days=1) if pd.notnull(r["納品予定日"]) else None,"備考":r.get("備考",""),"更新日時":datetime.now()} for _,r in spo.iterrows() if r["ID"] not in ex]
            sw = pd.concat([df_sp, pd.DataFrame(nr)], ignore_index=True) if nr else df_sp.copy()
            se = pd.merge(sw, df_o[["ID","備考"]].rename(columns={"ID":"受注ID","備考":"受注備考"}), on="受注ID", how="left")
            se["種別"] = se["受注備考"].apply(lambda x: "特注" if "特注" in str(x) else "チャーター便"); se["納品予定日(表示)"] = to_dt(se["納品予定日"]).apply(format_date_jp); se["出荷予定日_edit"] = to_dt(se["出荷予定日"]).dt.date
            ed = st.data_editor(se[[c for c in ["ID","種別","製品名","顧客名","納品予定日(表示)","出荷予定日_edit","備考"] if c in se.columns]], hide_index=True, column_config={"ID":None,"種別":st.column_config.TextColumn(disabled=True),"製品名":st.column_config.TextColumn(disabled=True),"顧客名":st.column_config.TextColumn(disabled=True),"納品予定日(表示)":st.column_config.TextColumn(disabled=True),"出荷予定日_edit":st.column_config.DateColumn("📅 出荷予定日",format="YYYY/MM/DD")})
            if st.button("💾 保存", type="primary"):
                for i, r in ed.iterrows():
                    m = sw["ID"]==se.iloc[i]["ID"]
                    if r.get("出荷予定日_edit"): sw.loc[m,"出荷予定日"] = to_dt(r.get("出荷予定日_edit"))
                    sw.loc[m,"備考"] = str(r.get("備考","")); sw.loc[m,"更新日時"] = datetime.now()
                save_sync("special_schedule", sw); st.rerun()
                # ─────────────────────────────────────────────
# 📈 経営・分析ダッシュボード
# ─────────────────────────────────────────────
elif pg == "📈 経営・分析ダッシュボード":
    page_header("📈 経営・製造管理 ダッシュボード")
    td1,td2,td3,td4 = st.tabs(["🏠 経営サマリ","📦 製品・ABC分析","🏭 製造効率分析","📅 月次トレンド"])
    with td1:
        if not df_o.empty:
            tm = date.today().replace(day=1); om = df_o[(safe_dt_date(df_o["納品予定日"])>=tm)&(df_o["不良廃棄フラグ"]==False)]
            c1,c2,c3,c4 = st.columns(4); c1.metric("今月 出荷", f"{om['ケース数'].apply(to_int).sum():,} cs", delta=f"{om['顧客名'].nunique()} 顧客"); c2.metric("今月 不良", f"{df_o[(safe_dt_date(df_o['納品予定日'])>=tm)&(df_o['不良廃棄フラグ']==True)]['ケース数'].apply(to_int).sum():,} cs", delta_color="inverse"); c3.metric("荷姿チェック率", f"{int(len(df_o[df_o['荷姿チェック']==True])/max(len(df_o),1)*100)} %"); c4.metric("欠品品目数", f"{sum(1 for v in cs.values() if v<=0)} 品目", delta_color="inverse")
            ca,cb = st.columns(2)
            with ca:
                ss = df_o[df_o["運送会社"].str.strip()!=""]["運送会社"].value_counts().reset_index()
                if not ss.empty: ss.columns=["運","件"]; st.plotly_chart(px.pie(ss,names="運",values="件",title="運送会社別"), use_container_width=True)
            with cb:
                cua = df_o[df_o["顧客名"]!="未指定"].groupby("顧客名")["ケース数"].apply(lambda x: x.apply(to_int).sum()).reset_index().sort_values("ケース数",ascending=False).head(5)
                if not cua.empty: st.plotly_chart(px.bar(cua,x="ケース数",y="顧客名",orientation='h',title="主要顧客 TOP5"), use_container_width=True)
    with td2:
        if not df_o.empty:
            o2 = df_o[df_o["不良廃棄フラグ"]==False].copy(); o2["ケース数"] = o2["ケース数"].apply(to_int); abc = o2.groupby("製品名")["ケース数"].sum().reset_index().sort_values("ケース数",ascending=False)
            if abc["ケース数"].sum()>0:
                abc["累計比率"] = abc["ケース数"].cumsum()/abc["ケース数"].sum()*100; abc["ランク"] = pd.cut(abc["累計比率"],bins=[0,70,90,100],labels=["A(主力)","B(中堅)","C(その他)"])
                st.plotly_chart(px.bar(abc.head(20),x="製品名",y="ケース数",color="ランク",title="ABC TOP20"), use_container_width=True)
    with td3:
        if not df_m.empty:
            mt = df_m[safe_dt_date(df_m["製造予定日"])>=date.today().replace(day=1)]; tc = mt["ケース数"].apply(to_int).sum(); rc = mt[mt["リパックフラグ"]==True]["ケース数"].apply(to_int).sum()
            c1,c2 = st.columns(2); c1.metric("今月 製造",f"{tc:,} cs"); c2.metric("今月 リパック",f"{rc:,} cs",delta=f"{int(rc/max(tc,1)*100)}%")
            st.plotly_chart(px.histogram(df_m,x="製造予定日",y="ケース数",color="大カテゴリ",barmode="stack",title="推移"), use_container_width=True)
        if ps: st.dataframe(pd.DataFrame([{"資材":k,"庫":v["現"],"点":v["点"],"出":v["出"]} for k,v in ps.items()]).style.apply(lambda r: ['background-color:#FFEDD5;color:#C2410C;']*len(r) if to_int(r.get("庫",0))<to_int(r.get("点",0)) else ['']*len(r), axis=1), hide_index=True)
    with td4:
        if not df_o.empty:
            tdf = df_o[df_o["不良廃棄フラグ"]==False].copy(); tdf["年月"] = to_dt(tdf["納品予定日"]).dt.to_period("M").astype(str)
            mn = tdf.groupby(["年月","大カテゴリ"])["ケース数"].apply(lambda x: x.apply(to_int).sum()).reset_index()
            if not mn.empty: st.plotly_chart(px.bar(mn,x="年月",y="ケース数",color="大カテゴリ",barmode="stack",title="月次カテ別"), use_container_width=True)

# ─────────────────────────────────────────────
# ⚙️ マスタ・分析
# ─────────────────────────────────────────────
elif pg == "⚙️ マスタ・分析":
    page_header("⚙️ マスタ")
    tm1,tm2,tm3,tm4 = st.tabs(["📦 製品","🏢 顧客","📦 資材","🚚 運送会社"])
    with tm1:
        em = st.data_editor(df_mst.copy(), num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"大カテゴリ":st.column_config.SelectboxColumn(options=[c.split(" ",1)[1] for c in CATS]),"使用資材名":st.column_config.SelectboxColumn(options=df_pm["資材名"].tolist() if not df_pm.empty else [])}, height=500)
        if st.button("💾 製品マスタ保存", type="primary"): save_sync("master", em); st.rerun()
    with tm2:
        ec = st.data_editor(df_c.copy(), num_rows="dynamic", use_container_width=True, hide_index=True)
        if st.button("💾 顧客マスタ保存", type="primary"): save_sync("customers", ec); st.rerun()
    with tm3:
        ep = st.data_editor(df_pm.copy(), num_rows="dynamic", use_container_width=True, hide_index=True)
        if st.button("💾 資材マスタ保存", type="primary"): save_sync("packaging_master", ep); st.rerun()
    with tm4:
        es = st.data_editor(df_sm.copy(), num_rows="dynamic", use_container_width=True, hide_index=True)
        if st.button("💾 運送会社保存", type="primary"): save_sync("shipping_master", es); st.rerun()

# ─────────────────────────────────────────────
# 🏗️ 製造スケジューラー
# ─────────────────────────────────────────────
elif pg == "🏗️ 製造スケジューラー":
    page_header("🏗️ 製造スケジューラー")
    def gpp(pn):
        df = {"時間あたり生産量":0, "歩留まり率":95, "リードタイム時間":0, "安全在庫数":0, "段取りグループ":""}
        if mst_u.empty or not pn: return df
        r = mst_u[mst_u["製品名"]==pn]
        if r.empty: return df
        return {"時間あたり生産量":max(1,to_int(r.iloc[0].get("時間あたり生産量",0))), "歩留まり率":max(1,min(100,to_int(r.iloc[0].get("歩留まり率",95)) or 95)), "リードタイム時間":to_int(r.iloc[0].get("リードタイム時間",0)), "安全在庫数":to_int(r.iloc[0].get("安全在庫数",0)), "段取りグループ":str(r.iloc[0].get("段取りグループ","") or "")}
    def calc_t(odf, mdf, cs, fs, mst_u, hd=30):
        tk=[]; n=pd.Timestamp.today().normalize()
        if odf.empty: return tk
        fo = odf[(odf["不良廃棄フラグ"]==False)&(to_dt(odf["納品予定日"])>=n)].copy(); fo["納品予定日"] = to_dt(fo["納品予定日"]); fo=fo.dropna(subset=["納品予定日"]).sort_values("納品予定日")
        for pn, g in fo.groupby("製品名"):
            pa = gpp(pn); c_s = cs.get(pn,0)
            for _, r in g.iterrows():
                sd = pd.Timestamp(r["納品予定日"]).normalize(); nq = to_int(r.get("ケース数",0))
                sh = nq - max(0, fs.get(pn,{}).get(sd,c_s) - pa["安全在庫数"])
                if sh<=0: tk.append({"製品名":pn,"顧客名":str(r.get("顧客名","")),"出荷日":sd,"受注数(cs)":nq,"製造必要量(cs)":0,"製造時間(h)":0,"製造開始期限":sd,"優先度":5,"ステータス":"✅ 在庫充足","段取りグループ":pa["段取りグループ"]}); continue
                mq = int(np.ceil(sh/(pa["歩留まり率"]/100))); mh = mq/max(1, pa["時間あたり生産量"])
                std = sd - timedelta(days=max(1, int(np.ceil((mh+pa["リードタイム時間"])/9)))); dl = (sd-n).days
                pr = 1 if dl<=1 else (2 if dl<=3 else (3 if dl<=7 else (4 if dl<=14 else 5)))
                stt = "🔴 緊急" if std<=n else ("🟠 要注意" if dl<=3 else ("🟡 注意" if dl<=7 else "🟢 計画内"))
                tk.append({"製品名":pn,"顧客名":str(r.get("顧客名","")),"出荷日":sd,"受注数(cs)":nq,"製造必要量(cs)":mq,"製造時間(h)":round(mh,1),"製造開始期限":std,"優先度":pr,"ステータス":stt,"段取りグループ":pa["段取りグループ"]})
        tn = [t for t in tk if t["製造必要量(cs)"]>0]; tn.sort(key=lambda t: (t["段取りグループ"] or "ZZZ", t["優先度"], t["出荷日"]))
        return tn + [t for t in tk if t["製造必要量(cs)"]==0]
    
    hd = st.slider("📅 期間(日)",7,60,30,7); so = st.checkbox("✅ 充足品も表示")
    tk = calc_t(df_o, df_m, cs, fs, mst_u, hd); tn = [t for t in tk if t["製造必要量(cs)"]>0]; dt = tk if so else tn
    k1,k2,k3,k4 = st.columns(4); k1.metric("🔴 緊急", f"{sum(1 for t in tn if t['優先度']<=2)} 件"); k2.metric("🟡 注意", f"{sum(1 for t in tn if t['優先度']==3)} 件"); k3.metric("📋 必要", f"{len(tn)} 件"); k4.metric("⏱ 時間", f"{sum(t['製造時間(h)'] for t in tn):.1f} h")
    ts1, ts2, ts3, ts4 = st.tabs(["📋 一覧", "📊 ガント", "🔧 段取り", "⚙️ 設定"])
    with ts1:
        if not dt: st.success("✅ なし")
        else:
            dft = pd.DataFrame(dt); sc = [c for c in ["優先度","ステータス","製品名","顧客名","出荷日","受注数(cs)","製造必要量(cs)","製造時間(h)","製造開始期限","段取りグループ"] if c in dft.columns]
            for c in ["出荷日","製造開始期限"]:
                if c in dft.columns: dft[c] = to_dt(dft[c]).apply(lambda x: x.strftime("%Y/%m/%d") if pd.notnull(x) else "")
            st.dataframe(dft[sc].style.apply(lambda r: ['background-color:#FEE2E2;']*len(r) if r.get("優先度",5)<=1 else (['background-color:#FFEDD5;']*len(r) if r.get("優先度",5)==2 else (['background-color:#FFFBEB;']*len(r) if r.get("優先度",5)==3 else ['']*len(r))), axis=1), hide_index=True)
    with ts2:
        if tn:
            gd = [dict(Task=f"{t['製品名'][:10]}", Start=t["製造開始期限"].strftime("%Y-%m-%d"), Finish=(t["製造開始期限"]+timedelta(hours=t["製造時間(h)"])).strftime("%Y-%m-%d") if (t["製造開始期限"]+timedelta(hours=t["製造時間(h)"]))>t["製造開始期限"] else (t["製造開始期限"]+timedelta(hours=1)).strftime("%Y-%m-%d"), Resource=t["ステータス"]) for t in tn if pd.notnull(t.get("製造開始期限"))]
            if gd:
                fig = px.timeline(pd.DataFrame(gd), x_start="Start", x_end="Finish", y="Task", color="Resource", color_discrete_map={"🔴 緊急":"#DC2626","🟠 要注意":"#EA580C","🟡 注意":"#D97706","🟢 計画内":"#059669"})
                fig.update_yaxes(autorange="reversed"); st.plotly_chart(fig, use_container_width=True)
    with ts3:
        if tn:
            gp = {}; pg = None; ro = []; tt = 0
            for t in tn: gp.setdefault(t["段取りグループ"] or "未設定", []).append(t)
            for gn, gts in gp.items():
                co = 30 if pg and pg!=gn else 0
                for t in sorted(gts, key=lambda t:(t["優先度"], t["出荷日"])):
                    ro.append({"順":len(ro)+1,"G":gn,"品":t["製品名"],"量":t["製造必要量(cs)"],"h":t["製造時間(h)"],"替":co,"優":t["優先度"]}); tt+=t["製造時間(h)"]; co=0
                pg = gn
            st.dataframe(pd.DataFrame(ro).style.apply(lambda r: ['background-color:#FEE2E2;']*len(r) if to_int(r.get("優",5))<=2 else ['']*len(r), axis=1), hide_index=True)
    with ts4:
        if not df_mst.empty:
            ep = st.data_editor(df_mst[[c for c in ["製品名","大カテゴリ","時間あたり生産量","歩留まり率","リードタイム時間","安全在庫数","段取りグループ"] if c in df_mst.columns]].copy(), hide_index=True)
            if st.button("💾 保存"):
                um = df_mst.copy()
                for c in ["時間あたり生産量","歩留まり率","リードタイム時間","安全在庫数","段取りグループ"]:
                    if c in ep.columns and c in um.columns: um[c] = ep[c].values
                save_sync("master", um); st.rerun()
