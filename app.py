import os
import re
import unicodedata
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
from datetime import datetime, timedelta, date, timezone
JST = timezone(timedelta(hours=+9))
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

def nk(s):
    """製品名の全角/半角・前後スペースなどの表記ゆれを吸収した照合用キー"""
    try:
        return unicodedata.normalize("NFKC", str(s)).strip()
    except: return str(s).strip()

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
    try:
        if isinstance(s, pd.Series):
            converted = pd.to_datetime(s, errors='coerce', utc=False)
            try:
                if converted.dt.tz is not None:
                    converted = converted.dt.tz_localize(None)
            except Exception:
                pass
            return converted.dt.normalize().dt.date
        else:
            converted = pd.to_datetime(s, errors='coerce', utc=False)
            if pd.isna(converted):
                return None
            return converted.normalize().date()
    except Exception:
        if hasattr(s, '__len__'):
            return pd.Series([None] * len(s))
        return None

def _nd_to_date(series):
    try:
        s = pd.to_datetime(series, errors='coerce', utc=False)
        try:
            if s.dt.tz is not None:
                s = s.dt.tz_localize(None)
        except Exception:
            pass
        return s.dt.normalize().dt.date
    except Exception:
        return pd.Series([None] * len(series))

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
    st.markdown("<div style='text-align:center;margin-top:60px;'><span style='font-size:72px;'>🏭</span><h2 style='color:#1E3A8A;'>入力ミス、転記ミスに注意！！！</h2></div>", unsafe_allow_html=True)
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
    c_def = {
        "orders":       ["ID","納品予定日","顧客名","大カテゴリ","製品名","ケース数","運送会社","備考","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考","不良廃棄フラグ","日付未定フラグ","登録日時"],
        "manufactures": ["ID","製造予定日","大カテゴリ","製品名","ケース数","リパックフラグ","備考","登録日時"],
        "master":       ["大カテゴリ","製品名","初期在庫数",
                         "使用資材名","製造登録区分","入数","甲消費数",
                         "時間あたり生産量","歩留まり率","リードタイム時間","安全在庫数","段取りグループ",
                         "段取りタイプ","ラインID","最小製造ロット",
                         "調合比率","成形比率","包装比率","レトルト比率",
                         "最少人員_調合","最少人員_成形","最少人員_包装","最少人員_レトルト","キーマン必要"],
        "customers":        ["顧客名","ふりがな","帳合先","支店名"],
        "packaging_master": ["資材名","品番","規格","仕入先","保管場所","単位","初期在庫","発注点","発注リードタイム","管理区分"],
        "packaging_logs":   ["ID","登録日","資材名","処理区分","数量","理由","備考","関連製品名","理論在庫","登録日時"],
        "shipping_master":  ["運送会社名"],
        "special_schedule": ["ID","受注ID","製品名","顧客名","納品予定日","出荷予定日","備考","更新日時"],
        "order_purchases":  ["発注ID","発注日","資材名","発注時在庫","発注数","発注単価","仕入先",
                             "納入予定日","実際納入日","実際納入数","ステータス","備考","登録日時"],
    }
    tc = c_def.get(name, [])
    if not tc: return pd.DataFrame()
    try: ws = sheet.worksheet(name)
    except:
        ws = sheet.add_worksheet(title=name, rows="1000", cols="30")
        ws.update(values=[tc,["ヤマト運輸"],["佐川急便"],["自社配送"]] if name=="shipping_master" else [tc], range_name="A1")
    try:
        data = ws.get_all_values()
        if len(data) <= 1: return pd.DataFrame(columns=tc)
        df = pd.DataFrame(data[1:], columns=data[0])
        df.columns = df.columns.str.strip().str.replace(' ','').str.replace('　','')
        extra_cols = [c for c in df.columns if c not in tc]
        ordered_cols = tc + extra_cols
        df = df.loc[:, ~df.columns.duplicated()].reindex(columns=ordered_cols, fill_value="")
        for c in ["ケース数","初期在庫数","初期在庫","発注点","数量","理論在庫",
                  "入数","甲消費数","最小製造ロット","最少人員_調合","最少人員_成形",
                  "最少人員_包装","最少人員_レトルト","調合比率","成形比率","包装比率","レトルト比率",
                  "時間あたり生産量","歩留まり率","リードタイム時間","安全在庫数","発注リードタイム"]:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            
        if "入数" in df.columns: df["入数"] = df["入数"].apply(lambda x: 10 if x <= 0 else x)
        if "甲消費数" in df.columns: df["甲消費数"] = df["甲消費数"].apply(lambda x: 4 if x <= 0 else x)
        if "時間あたり生産量" in df.columns: df["時間あたり生産量"] = df["時間あたり生産量"].apply(lambda x: 10 if x <= 0 else x)
        if "歩留まり率" in df.columns: df["歩留まり率"] = df["歩留まり率"].apply(lambda x: 95 if x <= 0 else x)
        if "最小製造ロット" in df.columns: df["最小製造ロット"] = df["最小製造ロット"].apply(lambda x: 1 if x <= 0 else x)
            
        for c in ["納品予定日","製造予定日","登録日","登録日時","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","出荷予定日","更新日時"]:
            if c in df.columns:
                _parsed = pd.to_datetime(df[c], errors='coerce', utc=False)
                try:
                    if _parsed.dt.tz is not None: _parsed = _parsed.dt.tz_localize(None)
                except Exception: pass
                df[c] = _parsed
        for c in ["荷姿チェック","不良廃棄フラグ","リパックフラグ","日付未定フラグ","特注フラグ","チャーターフラグ"]:
            if c in df.columns: df[c] = df[c].astype(str).str.upper() == "TRUE"
            
        if "製造登録区分" not in df.columns: df["製造登録区分"] = df.get("資材消費単位", "ケース")
            
        return df[ordered_cols]
    except: return pd.DataFrame(columns=tc)

def save_sync(name, df):
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        st.warning(f"⚠️ {name} のデータが空のため、消失を防ぐために保存を中止しました。")
        return

    try:
        ds = df.copy()
        for col in ds.columns:
            if pd.api.types.is_datetime64_any_dtype(ds[col]):
                ds[col] = ds[col].dt.strftime('%Y-%m-%d %H:%M:%S').fillna('')
            elif pd.api.types.is_bool_dtype(ds[col]):
                ds[col] = ds[col].astype(str).str.upper()
            elif pd.api.types.is_numeric_dtype(ds[col]):
                ds[col] = ds[col].fillna(0).astype(str)
            else:
                ds[col] = ds[col].fillna('').astype(str)
        
        ds = ds.replace(["nan", "None", "NaT", "NaN"], "")
        update_values = [ds.columns.tolist()] + ds.values.tolist()
        
        ws = sheet.worksheet(name)
        ws.clear()
        ws.update(values=update_values, range_name='A1')
        
        st.cache_data.clear()
        st.session_state[f"{name}_df"] = df
        st.success(f"✅ {name} を正常に保存しました。")
    except Exception as e:
        st.error(f"保存処理中にエラーが発生しました: {str(e)}")
        st.write("発生箇所のDF情報:")
        st.write(df.dtypes)

def app_sync(name, nr):
    if nr.empty: return
    try:
        ws = sheet.worksheet(name)
        try:
            header = ws.row_values(1)
        except:
            header = nr.columns.tolist()
            ws.append_row(header)
            
        rc = nr.copy()
        for col in header:
            if col not in rc.columns: rc[col] = ""
        rc = rc[header]
        
        for col in rc.columns:
            if pd.api.types.is_datetime64_any_dtype(rc[col]): rc[col] = rc[col].dt.strftime('%Y-%m-%d %H:%M:%S').fillna('')
            elif pd.api.types.is_bool_dtype(rc[col]): rc[col] = rc[col].astype(str).str.upper()
            else: rc[col] = rc[col].fillna('').astype(str)
            
        ws.append_row(rc.fillna("").values[0].tolist())
        st.cache_data.clear()
        st.session_state[f"{name}_df"] = pd.concat([st.session_state[f"{name}_df"], nr], ignore_index=True)
    except Exception as e:
        st.error(f"追加保存エラー: {e}")

for _s in ["orders","manufactures","master","customers","packaging_master","packaging_logs","shipping_master","special_schedule","order_purchases"]:
    if f"{_s}_df" not in st.session_state: st.session_state[f"{_s}_df"] = load_data(_s)
if "current_page" not in st.session_state: st.session_state.current_page = "📋 受注登録"
if "drill_product" not in st.session_state: st.session_state.drill_product = None
if "_flash" not in st.session_state: st.session_state._flash = None

def flash(type_, msg): st.session_state._flash = {"type": type_, "msg": msg}
def show_flash(): pass
def show_flash_inline(placeholder=None):
    f = st.session_state.get("_flash")
    if f:
        st.session_state._flash = None
        target = placeholder if placeholder else st
        if f["type"] == "success": target.success(f["msg"])
        elif f["type"] == "error": target.error(f["msg"])
        elif f["type"] == "warning": target.warning(f["msg"])
        else: target.info(f["msg"])

odf = st.session_state.orders_df; mdf = st.session_state.manufactures_df; mst = st.session_state.master_df; cdf = st.session_state.customers_df
pk_m = st.session_state.packaging_master_df; pk_l = st.session_state.packaging_logs_df; sh_m = st.session_state.shipping_master_df; sp_s = st.session_state.special_schedule_df
po_df = st.session_state.order_purchases_df

CATS = ["🍝 つきこん","🟫 平こん","🍜 糸こん・しらたき","🔺 三角こん","🟤 玉こん","🎲 ダイスこん","🏷️ 短冊","🇯🇵 国産","🤲 ちぎりこん","🏮 大黒屋","🏭 かねこ","🍱 ショクカイ","❄️ 冷凍耐性","📦 その他"]
SP_T = ["（なし）","⭐ 特注","🚌 チャーター便"]

def fn(n): return f"⚫️ {n}" if "黒" in str(n) else f"⚪️ {n}" if "白" in str(n) else f"📦 {n}"

def pui(pn):
    if mst.empty or not pn: return "ケース", 10, 4
    r = mst[mst["製品名"] == pn]
    if r.empty: return "ケース", 10, 4
    row = r.iloc[0]
    kbn = str(row.get("製造登録区分", "ケース")).strip()
    if kbn not in ["ケース", "袋", "甲"]: kbn = "ケース"
    nyu = max(1, to_int(row.get("入数", 10)))
    kou = max(1, to_int(row.get("甲消費数", 4)))
    return kbn, nyu, kou

def get_toriatsuki_list(): return sorted(cdf["帳合先" if "帳合先" in cdf.columns else "顧客名"].dropna().unique().tolist()) if not cdf.empty else []
def get_shiten_list(tori): return sorted(cdf[cdf["帳合先"] == tori]["支店名"].dropna().replace("","").unique().tolist()) if not cdf.empty and tori and "帳合先" in cdf.columns else []

today = pd.Timestamp.today().normalize(); dates = pd.date_range(today, today + timedelta(days=60))
cs = {}; fs = {}; unmatched_products = []; nk2name = {}
mst_u = mst.drop_duplicates(subset=["製品名"]) if not mst.empty else pd.DataFrame(
    columns=["大カテゴリ","製品名","初期在庫数","使用資材名","製造登録区分","入数","甲消費数",
             "時間あたり生産量","歩留まり率","リードタイム時間","安全在庫数","段取りグループ"])

for _ext_col, _ext_def in [
    ("製造登録区分", "ケース"), ("入数", 10), ("甲消費数", 4),
    ("段取りタイプ", ""), ("ラインID", ""), ("最小製造ロット", 1),
    ("調合比率", 15), ("成形比率", 35), ("包装比率", 35), ("レトルト比率", 15),
    ("最少人員_調合", 1), ("最少人員_成形", 2), ("最少人員_包装", 2), ("最少人員_レトルト", 1),
    ("キーマン必要", "TRUE"),
]:
    if not mst.empty and _ext_col not in mst.columns:
        mst[_ext_col] = _ext_def
        mst_u = mst.drop_duplicates(subset=["製品名"])

# ─────────────────────────────────────────────
# 在庫計算・資材計算エンジン (超高速 & 過去棚卸遡及絶対値化版)
# ─────────────────────────────────────────────
if not mst_u.empty:
    _mst_keys = set(mst_u["製品名"].apply(nk))
    nk2name = {nk(p): p for p in mst_u["製品名"]}
    ev_o = odf[["納品予定日","製品名","ケース数","備考","顧客名","登録日時"]].copy().rename(columns={"納品予定日":"日付","ケース数":"qty"}) if not odf.empty else pd.DataFrame(columns=["日付","製品名","qty","備考","顧客名","登録日時"])
    if not ev_o.empty: ev_o["qty"] = -pd.to_numeric(ev_o["qty"], errors='coerce').fillna(0).abs()
    vm = mdf[~mdf["備考"].fillna("").str.contains("【在庫非反映】")] if not mdf.empty else pd.DataFrame()
    ev_m = vm[["製造予定日","製品名","ケース数","備考","登録日時"]].copy().rename(columns={"製造予定日":"日付","ケース数":"qty"}) if not vm.empty else pd.DataFrame(columns=["日付","製品名","qty","備考","登録日時"])
    if "顧客名" not in ev_m.columns: ev_m["顧客名"] = ""
    if not ev_m.empty: ev_m["qty"] = pd.to_numeric(ev_m["qty"], errors='coerce').fillna(0).abs()
    
    ae = pd.concat([ev_o, ev_m], ignore_index=True).dropna(subset=["製品名","日付"])
    ae["qty"] = ae["qty"].apply(to_int)
    ae["備考"] = ae["備考"].fillna("").astype(str)
    ae["顧客名"] = ae["顧客名"].fillna("").astype(str)
    ae["日付"] = pd.to_datetime(ae["日付"]).dt.normalize()
    ae["製品名key"] = ae["製品名"].apply(nk)
    
    # 未一致製品の検出
    unmatched_products = sorted(set(ae.loc[~ae["製品名key"].isin(_mst_keys), "製品名"].dropna().unique().tolist()))
    
    # 日付未定の受注引当
    pend = pd.Series(dtype=int)
    if not odf.empty and "日付未定フラグ" in odf.columns:
        _pnd = odf[odf["日付未定フラグ"] == True]
        if not _pnd.empty:
            pend = _pnd.assign(製品名key=_pnd["製品名"].apply(nk)).groupby("製品名key")["ケース数"].apply(lambda s: s.apply(to_int).sum())

    # 棚卸実績の判定
    _anc_re = re.compile(r"実棚卸数[:=]\s*(-?\d+)")
    def get_inv_val(row):
        memo = row["備考"]
        cust = row["顧客名"]
        if "棚卸" in memo or "棚卸" in cust:
            m = _anc_re.search(memo)
            if m:
                return abs(int(m.group(1)))
            else:
                return abs(row["qty"])
        return None

    ae["anchor_val"] = ae.apply(get_inv_val, axis=1)
    ae["is_inv"] = ae["anchor_val"].notna()
    ae = ae.sort_values(["日付", "is_inv"])

    # グループ化し、高速にループを回すための製品別辞書作成
    p_events_dict = {}
    for pk, group in ae.groupby("製品名key"):
        p_events_dict[pk] = group.to_dict("records")
        
    for _, r in mst_u.iterrows():
        p = r["製品名"]; pk = nk(p)
        events = p_events_dict.get(pk, [])
        
        current_stock = to_int(r.get("初期在庫数", 0))
        
        # 今日より前の過去シミュレーション
        past_events = [e for e in events if e["日付"] < today]
        inv_events = [e for e in past_events if e["is_inv"]]
        
        if inv_events:
            latest_inv = inv_events[-1]
            inv_date = latest_inv["日付"]
            base_qty = latest_inv["anchor_val"]
            valid_past = [e for e in past_events if e["日付"] > inv_date]
        else:
            base_qty = to_int(r.get("初期在庫数", 0))
            valid_past = past_events
            
        # 現在庫 (出荷未定引当もここで差し引き)
        c_s = base_qty + sum(e["qty"] for e in valid_past) - to_int(pend.get(pk, 0))
        cs[p] = c_s
        
        # 今日以降の未来在庫シミュレーション
        if inv_events:
            future_events = [e for e in events if e["日付"] >= today and e["日付"] > inv_date]
        else:
            future_events = [e for e in events if e["日付"] >= today]
            
        future_by_date = {}
        for event in future_events:
            d = event["日付"]
            future_by_date.setdefault(d, []).append(event)
            
        fs_p = {}
        sim_stock = c_s
        for d in dates:
            daily_evs = future_by_date.get(d, [])
            for event in daily_evs:
                if event["is_inv"]:
                    sim_stock = event["anchor_val"]
                else:
                    sim_stock += event["qty"]
            fs_p[d] = sim_stock
            
        fs[p] = fs_p
        p = r["製品名"]; pk = nk(p)
        if pk in anchors.index:
            a_date = anchors.loc[pk, "日付"]; a_val = to_int(anchors.loc[pk, "_anchor_val"])
            _win = ae[(ae["製品名key"] == pk) & (ae["日付"] > a_date)]  # 棚卸日より後のイベントのみ加減算（棚卸日当日分は実棚卸数に反映済み）
            c_s = a_val + to_int(_win[_win["日付"] < today]["qty"].sum()) - to_int(pend.get(pk, 0)); cs[p] = c_s
            _pr = _win[_win["日付"] >= today].groupby("日付")["qty"].sum().reindex(dates, fill_value=0).fillna(0).cumsum()
            fs[p] = {d: c_s + to_int(_pr.get(d, 0)) for d in dates}
        else:
            c_s = to_int(r.get("初期在庫数",0)) + to_int(pe.get(pk,0)) - to_int(pend.get(pk,0)); cs[p] = c_s
            pr = piv.loc[pk] if pk in piv.index else pd.Series(0, index=dates)
            if isinstance(pr, pd.DataFrame): pr = pr.sum(axis=0)
            pc = pr.reindex(dates, fill_value=0).fillna(0).cumsum()
            fs[p] = {d: c_s + to_int(pc.get(d,0)) for d in dates}

# ▼▼▼ 資材の予測・発注残・統計計算エンジン ▼▼▼
fd = 90; pf = {}
if not mst_u.empty and not odf.empty:
    mpi = mst_u.set_index("製品名")[["使用資材名","製造登録区分","入数","甲消費数"]].to_dict('index')
    for _, r in odf.iterrows():
        p, q, dt = str(r.get("製品名","")), to_int(r.get("ケース数",0)), pd.to_datetime(r.get("納品予定日"),errors="coerce")
        if pd.isna(dt) or dt.date()<date.today() or dt>today+timedelta(days=fd) or p not in mpi: continue
        pn = str(mpi[p].get("使用資材名",""))
        kbn = str(mpi[p].get("製造登録区分","ケース")).strip()
        nyu = max(1, to_int(mpi[p].get("入数",10)))
        kou = max(1, to_int(mpi[p].get("甲消費数",4)))
        if pn:
            if kbn == "袋": use_qty = to_int(q / nyu)
            elif kbn == "甲": use_qty = to_int(q * kou)
            else: use_qty = q
            pf.setdefault(pn, {})[dt.normalize()] = pf.get(pn,{}).get(dt.normalize(),0) + use_qty

open_po = {}
if "order_purchases_df" in st.session_state and not st.session_state.order_purchases_df.empty:
    podf = st.session_state.order_purchases_df
    for _, r in podf[podf["ステータス"].isin(["発注済", "一部納入"])].iterrows():
        pn = str(r.get("資材名",""))
        o_qty = to_int(r.get("発注数", 0))
        a_qty = to_int(r.get("実際納入数", 0))
        open_po[pn] = open_po.get(pn, 0) + max(0, o_qty - a_qty)

p_sum = {}
if "管理区分" not in pk_m.columns: pk_m["管理区分"] = "定期発注(自動)"
if not pk_m.empty:
    for _, r in pk_m.drop_duplicates(subset=["資材名"]).iterrows():
        if pd.isna(r["資材名"]) or str(r["資材名"]).strip() == "": continue
        p_sum[r["資材名"]] = {
            "品番":str(r.get("品番","")), "規格":str(r.get("規格","")), 
            "仕入先":str(r.get("仕入先","")), "保管場所":str(r.get("保管場所","")), 
            "単位":str(r.get("単位","")), "期首在庫":to_int(r.get("初期在庫",0)), 
            "発注点":to_int(r.get("発注点",0)), "発注リードタイム":to_int(r.get("発注リードタイム",7)),
            "管理区分":str(r.get("管理区分","定期発注(自動)")),
            "入庫":0, "出庫":0, "現在庫":0
        }

for pn in p_sum.keys(): pf.setdefault(pn, {})

past_30_days = today - timedelta(days=30)
daily_usage = {}
net_change_by_day = {} # ★追加：グラフ逆算用の日別純増減

if not pk_l.empty:
    for _, r in pk_l.iterrows():
        dt = pd.to_datetime(r.get("登録日", today), errors="coerce")
        if pd.isna(dt): continue
        if dt.tz is not None: dt = dt.tz_localize(None)
        
        pn = str(r.get("資材名",""))
        q = to_int(r.get("数量",0))
        pt = str(r.get("処理区分",""))
        
        if pn in p_sum:
            # ★修復：mdfからの二重計上をやめ、純粋に履歴から入出庫を計算する
            if "入庫" in pt:
                p_sum[pn]["入庫"] += q
                net_chg = q
            elif "出庫" in pt or "連動" in pt:
                p_sum[pn]["出庫"] += q
                net_chg = -q
            else:
                net_chg = 0
                
            # 逆算グラフ用
            d_norm = dt.normalize().date()
            net_change_by_day.setdefault(pn, {})
            net_change_by_day[pn].setdefault(d_norm, 0)
            net_change_by_day[pn][d_norm] += net_chg
            
            # 統計用
            if dt >= past_30_days:
                if "出庫" in pt or "連動" in pt:
                    d_str = dt.normalize().strftime("%Y-%m-%d")
                    daily_usage.setdefault(pn, {}).setdefault(d_str, 0)
                    daily_usage[pn][d_str] += q

total_usage = {pn: sum(daily_usage.get(pn, {}).values()) for pn in p_sum.keys()}
total_all = sum(total_usage.values()) or 1
sorted_usage = sorted(total_usage.items(), key=lambda x: x[1], reverse=True)
abc_rank = {}; cum = 0
for pn, u in sorted_usage:
    cum += u
    ratio = cum / total_all
    if ratio <= 0.7: abc_rank[pn] = "A"
    elif ratio <= 0.95: abc_rank[pn] = "B"
    else: abc_rank[pn] = "C"

# ★修復：mdfをループして出庫を足す処理（二重計上の元凶）を完全に削除しました。

for pn, d in p_sum.items():
    d["現在庫"] = d.get("期首在庫", 0) + d.get("入庫", 0) - d.get("出庫", 0)
    d["発注残"] = open_po.get(pn, 0)
    
    du = daily_usage.get(pn, {})
    u_arr = [du.get((today - timedelta(days=i)).strftime("%Y-%m-%d"), 0) for i in range(1, 31)]
    mu = float(np.mean(u_arr)) if u_arr else 0
    sigma = float(np.std(u_arr)) if u_arr else 0
    lt = max(1, d.get("発注リードタイム", 7))
    rk = abc_rank.get(pn, "C")
    sf_coef = 2.0 if rk == "A" else (1.65 if rk == "B" else 1.0)
    
    safe_stock = sf_coef * np.sqrt(lt) * sigma
    rec_pt = (mu * lt) + safe_stock
    d["推奨発注点"] = int(np.ceil(rec_pt))
    d["1日平均消費"] = mu
    d["ABCランク"] = rk
    
    future_need = sum(pf.get(pn, {}).values())
    d["受注残"] = future_need
    
    if d.get("管理区分", "") == "都度発注(受注連動)":
        d["在庫日数"] = 999
        d["不足数"] = max(0, future_need - (d.get("現在庫", 0) + d.get("発注残", 0)))
        if d.get("不足数", 0) > 0:
            d["状態"] = "🚨 欠品予測"
            d["アラート色"] = "#FEE2E2"
        else:
            d["状態"] = "✅ 正常"
            d["アラート色"] = "#F0FDF4"
    else:
        d["在庫日数"] = (d.get("現在庫", 0) / mu) if mu > 0 else 999
        if d.get("現在庫", 0) < d.get("発注点", 0):
            d["状態"] = "⚠️ 要発注"
            d["アラート色"] = "#FEF3C7" if d.get("現在庫", 0) > 0 else "#FEE2E2"
        else:
            d["状態"] = "✅ 正常"
            if d.get("在庫日数", 999) < 3: d["アラート色"] = "#FEE2E2"
            elif d.get("在庫日数", 999) < 10: d["アラート色"] = "#FFFBEB"
            elif d.get("在庫日数", 999) > 30 and mu > 0: d["アラート色"] = "#EFF6FF"
            else: d["アラート色"] = "#F0FDF4"

# ─────────────────────────────────────────────
# サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<div style='padding:16px 8px 8px;'><span style='font-size:22px;'>🏭</span><span style='font-size:16px; font-weight:900; color:#F1F5F9; margin-left:8px;'>丸実屋システム</span></div>", unsafe_allow_html=True)
    _today = date.today()
    if not odf.empty and "納品予定日" in odf.columns:
        _odf_valid = odf[odf["不良廃棄フラグ"] == False] if "不良廃棄フラグ" in odf.columns else odf
        _odf_valid = _odf_valid[_odf_valid["日付未定フラグ"] == False] if "日付未定フラグ" in _odf_valid.columns else _odf_valid
        toc = int((_nd_to_date(_odf_valid["納品予定日"]) == _today).sum())
    else:
        toc = 0
    scnt = sum(1 for f in fs.values() if any(v < 0 for v in list(f.values())[:7]))
    st.markdown(f'<div style="margin:8px 0 12px; background:rgba(255,255,255,0.07); border-radius:8px; padding:10px 14px;"><div style="font-size:12px; color:#94A3B8; margin-bottom:4px;">本日状況</div><div style="display:flex; gap:12px;"><div><span style="font-size:20px; font-weight:900; color:#60A5FA;">{toc}</span><span style="font-size:11px; color:#94A3B8;"> 出荷</span></div><div><span style="font-size:20px; font-weight:900; color:#F87171;">{scnt}</span><span style="font-size:11px; color:#94A3B8;"> 欠品予測</span></div></div></div><div style="height:1px; background:rgba(255,255,255,0.1); margin:0 0 10px;"></div>', unsafe_allow_html=True)
    
    menus = ["📋 受注登録","🏭 製造登録","🚚 出荷・発送管理","📦 資材・入出庫","📑 登録一覧","📊 在庫・スケジュール","⭐ 特注・チャータースケジュール","📈 経営・分析ダッシュボード","⚙️ マスタ・分析"]
    for m in menus:
        if st.button(m, use_container_width=True, type="primary" if st.session_state.current_page == m else "secondary"):
            st.session_state.current_page = m; st.session_state.drill_product = None; st.rerun()

    st.markdown("<div style='height:1px; background:rgba(255,255,255,0.1); margin:14px 0 10px;'></div>", unsafe_allow_html=True)
    if st.button("🔄 スプレッドシートを再読込", use_container_width=True, help="Googleスプレッドシートを直接編集した場合など、最新データを読み込み直します"):
        for _s in ["orders","manufactures","master","customers","packaging_master",
                   "packaging_logs","shipping_master","special_schedule","order_purchases"]:
            st.session_state.pop(f"{_s}_df", None)
        st.cache_data.clear()
        st.session_state._flash = {"type": "success", "msg": "✅ スプレッドシートから最新データを再読込しました。"}
        st.rerun()

pg = st.session_state.current_page
hc = {"📋 受注登録": "#1E3A8A, #3B82F6", "🏭 製造登録": "#064E3B, #10B981", "🚚 出荷・発送管理": "#047857, #34D399", "📦 資材・入出庫": "#B45309, #F59E0B", "📑 登録一覧": "#0F766E, #14B8A6", "📊 在庫・スケジュール": "#1E3A8A, #6366F1", "⭐ 特注・チャータースケジュール": "#5B21B6, #8B5CF6", "📈 経営・分析ダッシュボード": "#0C4A6E, #0EA5E9", "⚙️ マスタ・分析": "#475569, #1E293B"}
def page_header(t):
    st.markdown(f'<div class="page-header" style="background:linear-gradient(135deg,{hc.get(t,"#1E3A8A, #3B82F6")});"><h1>{t}</h1></div>', unsafe_allow_html=True)
    show_flash()
def sec(t): st.markdown(f'<div class="section-title">{t}</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 📋 受注登録
# ─────────────────────────────────────────────
if pg == "📋 受注登録":
    page_header("📋 受注 登録")
    idu = st.checkbox("📅 出荷日を後で決める（日付未定で登録）", value=False)
    od = None if idu else st.date_input("📅 出荷日", value=date.today() + timedelta(days=1))
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

    kbn, nyu, kou = pui(prod)
    if kbn == "袋":
        qty = st.number_input("📦 数量（袋）", min_value=1, step=1, value=None)
    elif kbn == "甲":
        qty = st.number_input("📦 数量（甲）", min_value=1, step=1, value=None)
    else:
        qty = st.number_input("📦 数量（ケース）", min_value=1, step=1, value=None)

    r1, r2 = st.columns([2, 2]); rem = r1.text_input("📝 備考"); c1, c2, c3 = r2.columns(3); isub = c1.checkbox("🔄 代替品"); iirr = c2.checkbox("⚠️ 不良廃棄"); iadj = c3.checkbox("📊 在庫調整", help="在庫ずれ修正用。チェック時は出荷ではなく在庫への加算として扱われます（マイナスを戻す場合など）")
    
    if iadj:
        st.markdown('<div style="background:#EFF6FF;border:1.5px solid #2563EB;border-radius:8px;padding:8px 14px;font-size:13px;color:#1E40AF;margin:4px 0;">📊 <b>在庫調整モード</b>：この受注は「出荷」ではなく在庫を <b>増やす（＋）</b> 処理として登録されます。在庫ずれ補正にご利用ください。</div>', unsafe_allow_html=True)
    
    if prod and qty and to_int(qty)>0 and cs.get(prod,0) < to_int(qty):
        st.markdown(f'<div class="info-card red" style="background:#FEF2F2;">🚨 <b>製品在庫不足！</b> 現在庫: <b>{cs.get(prod,0)}</b> ／ 不足: <span class="shortage-red">－{to_int(qty)-cs.get(prod,0)}</span></div>', unsafe_allow_html=True)
    
    m_add = st.empty()
    if st.button("✅ 受注を登録", type="primary", use_container_width=True):
        if not prod or not qty or to_int(qty)<1:
            m_add.error("⚠️ 製品・数量は必須です。")
        else:
            frem = f"{'【代替品】' if isub else ''}{'【不良廃棄】' if iirr else ''}{'【在庫調整+】' if iadj else ''} {'特注' if '特注' in stype else ('チャーター便' if 'チャーター' in stype else '')} {rem}".strip()
            cn = f"{stor} {sv}".strip() if sv else (stor if stor else "未指定")
            nid = str(uuid.uuid4())[:6].upper(); ddt = pd.to_datetime(od) if od else pd.NaT
            if iadj:
                app_sync("manufactures", pd.DataFrame([{"ID":nid,"製造予定日":ddt if not pd.isna(ddt) else pd.Timestamp(date.today()),"大カテゴリ":cat,"製品名":prod,"ケース数":to_int(qty),"リパックフラグ":False,"備考":f"【在庫調整+】{frem}","登録日時": datetime.now(JST).replace(tzinfo=None)}]))
                flash("success", f"📊 在庫調整(＋)を登録しました！【{fn(prod)}】 ＋{to_int(qty):,}  現在庫: {cs.get(prod,0):,} → {cs.get(prod,0)+to_int(qty):,}")
                st.rerun()
            else:
                app_sync("orders", pd.DataFrame([{"ID":nid,"納品予定日":ddt,"顧客名":cn,"大カテゴリ":cat,"製品名":prod,"ケース数":to_int(qty),"運送会社":sc or "","備考":frem,"荷姿チェック":False,"発送備考":"","不良廃棄フラグ":iirr,"日付未定フラグ":idu,"登録日時": datetime.now(JST).replace(tzinfo=None)}]))
                if ("特注" in stype or "チャーター" in stype) and od:
                    app_sync("special_schedule", pd.DataFrame([{"ID":str(uuid.uuid4())[:6].upper(),"受注ID":nid,"製品名":prod,"顧客名":cn,"納品予定日":ddt,"出荷予定日":ddt-timedelta(days=1),"備考":frem,"更新日時":datetime.now()}]))
                _cur = cs.get(prod, 0)
                _d_key = pd.Timestamp(od).normalize() if od else None
                _proj = fs.get(prod, {}).get(_d_key, _cur) if _d_key else _cur
                _after = _proj - to_int(qty)
                if idu:
                    _stk_msg = f"📦 現在庫: {_cur:,} （日付未定のため在庫影響は確定後に反映）"
                    _ftype = "info"
                elif _after < 0:
                    _stk_msg = f"📦 現在庫: {_cur:,} ／ 出荷日予測在庫: {_proj:,} → 登録後: **{_after:,}** 🚨 在庫不足！"
                    _ftype = "error"
                else:
                    _stk_msg = f"📦 現在庫: {_cur:,} ／ 出荷日予測在庫: {_proj:,} → 登録後: {_after:,} ✅ 充足"
                    _ftype = "success"
                flash(_ftype, f"✨ 登録完了！【{fn(prod)}】 {to_int(qty):,}  出荷日: {format_date_jp(od) if od else '日付未定'}  顧客: {cn}\n{_stk_msg}")
                st.rerun()
    show_flash_inline(m_add)

    u_df = odf[odf["日付未定フラグ"]==True].copy().reset_index(drop=True) if not odf.empty and "日付未定フラグ" in odf.columns else pd.DataFrame()
    if not u_df.empty:
        with st.expander(f"🟡 日付未定受注を確定する ({len(u_df)}件)", expanded=True):
            udsp = u_df[["ID","製品名","ケース数","備考","顧客名","運送会社"]].copy(); udsp.insert(4,"納品予定日(確定)",None); udsp.insert(5,"帳合先(確定)",""); udsp.insert(6,"支店名(確定)","")
            ed_u = st.data_editor(udsp, use_container_width=True, hide_index=True, column_config={"ID":None,"製品名":st.column_config.TextColumn(disabled=True),"ケース数":st.column_config.NumberColumn(disabled=True),"備考":st.column_config.TextColumn(disabled=True),"顧客名":st.column_config.TextColumn(disabled=True),"納品予定日(確定)":st.column_config.DateColumn("📅 出荷日",format="YYYY/MM/DD"),"帳合先(確定)":st.column_config.SelectboxColumn("🏢 帳合先",options=tl),"運送会社":st.column_config.SelectboxColumn("🚚 運送会社",options=sl)})
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
                    flash("success", f"✅ {cnt}件の出荷日を確定しました。")
                    st.rerun()
                else:
                    _udf_msg.warning("⚠️ 確定する日付が入力されていません。")
            show_flash_inline(_udf_msg)

    sec("✏️ 直近データの修正・削除")
    if not odf.empty:
        do = odf.sort_values("登録日時",ascending=False).copy()
        do["出荷予定日(表示)"] = do.apply(lambda r: "🟡 日付未定" if r.get("日付未定フラグ") is True else format_date_jp(r["納品予定日"]), axis=1) if "日付未定フラグ" in do.columns else do["納品予定日"].apply(format_date_jp)
        _odf_limit = st.selectbox("編集件数", [5,10,20,50], format_func=lambda x: f"直近 {x} 件", index=0, key="odf_edit_limit")
        ed_o = st.data_editor(do.head(_odf_limit)[["ID","出荷予定日(表示)","顧客名","製品名","ケース数","運送会社","備考","不良廃棄フラグ"]], num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"ID":None,"ケース数":st.column_config.NumberColumn(min_value=1,step=1,format="%d")})
        _o_save_msg = st.empty()
        if st.button("💾 直近データ保存"):
            sv = ed_o.copy(); sv["納品予定日"] = pd.to_datetime(sv["出荷予定日(表示)"].str.replace("🟡 日付未定","").str.replace("🟡 ","").str.split(" ").str[0], errors="coerce")
            _o_ids = do.head(_odf_limit)["ID"].tolist()
            save_sync("orders", pd.concat([odf[~odf["ID"].isin(_o_ids)], pd.merge(sv, odf[[c for c in ["ID","大カテゴリ","荷姿チェック","賞味期限1","賞味期限2","賞味期限3","賞味期限4","賞味期限5","発送備考","日付未定フラグ","登録日時"] if c in odf.columns]], on="ID", how="left")], ignore_index=True))
            flash("success", "✅ 受注データを保存しました。"); st.rerun()
        show_flash_inline(_o_save_msg)
        with st.expander("📂 全データ一括編集"):
            ea_o = st.data_editor(do[["ID","出荷予定日(表示)","顧客名","製品名","ケース数","運送会社","備考","不良廃棄フラグ"]], num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"ID":None,"ケース数":st.column_config.NumberColumn(min_value=1,step=1,format="%d")}, height=400)
            _o_all_msg = st.empty()
            if st.button("💾 全データ保存"):
                sva = ea_o.copy(); sva["納品予定日"] = pd.to_datetime(sva["出荷予定日(表示)"].str.replace("🟡 日付未定","").str.replace("🟡 ","").str.split(" ").str[0], errors="coerce")
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
        _local_today = pd.Timestamp.now().date()
        td = st.date_input("📅 対象日", value=_local_today)
        if not odf.empty:
            _mask = (
                (_nd_to_date(odf["納品予定日"]) == td) &
                (odf["不良廃棄フラグ"] == False) &
                (odf.get("日付未定フラグ", pd.Series(False, index=odf.index)) == False)
            )
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
            return df[_nd_to_date(df["納品予定日"]) == target_date].copy()
        if st.radio("モード", ["📋 日別折りたたみ", "📊 全件一覧"], horizontal=True) == "📋 日別折りたたみ":
            for i in range(int(wd)):
                d = pd.Timestamp(sw)+timedelta(days=i)
                wo = _ord_for_date(odf, d.date())
                if not wo.empty:
                    with st.expander(f"**{format_date_jp(d)}**　{len(wo)}件 ✅{len(wo[wo['荷姿チェック']==True])}件完了", expanded=(d.date()==date.today())):
                        st.dataframe(wo[["顧客名","製品名","ケース数","運送会社","荷姿チェック","発送備考"]].style.apply(lambda r: ['background-color:#D1FAE5;']*len(r) if r.get("荷姿チェック")==True else ['']*len(r), axis=1), use_container_width=True, hide_index=True)
        else:
            frames = [_ord_for_date(odf, (pd.Timestamp(sw)+timedelta(days=i)).date()).assign(出荷日=format_date_jp(pd.Timestamp(sw)+timedelta(days=i))) for i in range(int(wd))]
            aw = pd.concat([f for f in frames if not f.empty], ignore_index=True) if any(not f.empty for f in frames) else pd.DataFrame()
            if aw.empty: st.info("予定なし")
            else:
                c1,c2,c3=st.columns(3); c1.metric("件数",f"{len(aw)}件"); c2.metric("✅ 消込済",f"{len(aw[aw['荷姿チェック']==True])}件"); c3.metric("総数",f"{aw['ケース数'].apply(to_int).sum():,}cs")
                sc = [c for c in ["出荷日","顧客名","製品名","ケース数","運送会社","荷姿チェック","発送備考","備考"] if c in aw.columns]
                st.dataframe(aw[sc].style.apply(lambda r: ['background-color:#D1FAE5;color:#065F46;']*len(r) if r.get("荷姿チェック")==True else ['']*len(r), axis=1), use_container_width=True, hide_index=True, height=min(600, max(300, len(aw)*38+60)))
                st.download_button("📥 CSV出力", data=make_csv_bytes(aw[sc]), file_name=f"週間出荷_{sw}.csv", mime="text/csv", use_container_width=True)

    with ts3:
        ce1, ce2 = st.columns(2); es = ce1.date_input("開始", value=date.today().replace(day=1)); ee = ce2.date_input("終了", value=date.today())
        if not odf.empty:
            _nd3_date = _nd_to_date(odf["納品予定日"])
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
    mdt = c1.date_input("📅 製造日", value=date.today())
    cf = st.pills("カテゴリ", CATS, default=CATS[0], label_visibility="collapsed"); c_m = cf.split(" ",1)[1] if cf else CATS[0].split(" ",1)[1]
    s1, s2 = st.columns([1.5, 2.5]); sp = s1.text_input("🔍 製品名検索", placeholder="検索...")
    pl = [p for p in mst_u["製品名"].tolist() if sp in p] if sp else (mst_u[mst_u["大カテゴリ"]==c_m]["製品名"].tolist() if not mst_u.empty else [])
    pm = s2.selectbox("確定製品", options=pl, index=None, format_func=fn)
    
    kbn, nyu, kou = pui(pm)
    if kbn == "袋":
        mq = c2.number_input(f"📦 数量（袋） ※{nyu}袋で1箱(ﾀﾞﾝﾎﾞｰﾙ)消費", min_value=1, step=1, value=None)
    elif kbn == "甲":
        mq = c2.number_input(f"📦 数量（甲） ※1甲で{kou}箱(ﾀﾞﾝﾎﾞｰﾙ)消費", min_value=1, step=1, value=None)
    else:
        mq = c2.number_input("📦 数量（ケース） ※1ケースで1箱(ﾀﾞﾝﾎﾞｰﾙ)消費", min_value=1, step=1, value=None)

    mr = s2.text_input("📝 備考（製造）")
    irp = st.checkbox("🔄 リパック製造（在庫加算）")
    iadj_m = st.checkbox("📊 在庫調整（－）", help="在庫ずれ修正用。チェック時は在庫を減らす（マイナス）処理として受注登録されます。製造ミス・廃棄・棚卸減など。")
    if iadj_m:
        st.markdown('<div style="background:#FEF2F2;border:1.5px solid #DC2626;border-radius:8px;padding:8px 14px;font-size:13px;color:#991B1B;margin:4px 0;">📊 <b>在庫調整（－）モード</b>：この登録は在庫を <b>減らす（－）</b> 処理として出荷登録されます。在庫ずれ補正にご利用ください。</div>', unsafe_allow_html=True)
    ipl = st.checkbox("📦 紐づく資材の在庫も同時に減らす", value=True) if (irp and not iadj_m) else (True if not iadj_m else False)

    if pm and mq and ipl and not mst_u.empty and pm in mst_u["製品名"].values:
        _mrow = mst_u[mst_u["製品名"]==pm].iloc[0]
        _mat_name = str(_mrow.get("使用資材名","")).strip()
        _kbn = str(_mrow.get("製造登録区分","ケース")).strip()
        _nyu = max(1, to_int(_mrow.get("入数", 10)))
        _kou = max(1, to_int(_mrow.get("甲消費数", 4)))

        if _mat_name:
            if _kbn == "袋":
                _mat_deduct = to_int(to_int(mq) / _nyu)
                _calc_desc = f"{to_int(mq)} 袋 ÷ {_nyu} (入数) = {_mat_deduct:,} 枚のダンボール消費"
            elif _kbn == "甲":
                _mat_deduct = to_int(to_int(mq) * _kou)
                _calc_desc = f"{to_int(mq)} 甲 × {_kou} (甲消費数) = {_mat_deduct:,} 枚のダンボール消費"
            else:
                _mat_deduct = to_int(mq)
                _calc_desc = f"{to_int(mq)} ケース = {_mat_deduct:,} 枚のダンボール消費"

            _cur_mat = p_sum.get(_mat_name,{}).get("現在庫",0)
            _after_mat = _cur_mat - _mat_deduct
            _color = "#FEE2E2" if _after_mat < 0 else "#D1FAE5"
            st.markdown(f"""<div style="background:{_color};border-radius:8px;padding:10px 14px;margin:6px 0;font-size:13px;">
            📦 <b>資材自動減算プレビュー</b>：【{_mat_name}】<br>
            計算式: {_calc_desc}<br>
            現在庫 <b>{_cur_mat:,} 枚</b> → 減算後 <b style="color:{'#DC2626' if _after_mat<0 else '#059669'}">{_after_mat:,} 枚</b>
            {"　⚠️ <b>資材不足！</b>" if _after_mat < 0 else "　✅ 充足"}
            </div>""", unsafe_allow_html=True)

    if pm and mq and cs.get(pm,0)<=0 and not iadj_m:
        st.markdown(f"<div class='info-card red' style='background:#FEF2F2; padding:10px;'>現在庫: <span class='shortage-red'>{cs.get(pm,0)} cs</span> → 製造後: <b>{cs.get(pm,0)+to_int(mq)} cs</b></div>", unsafe_allow_html=True)
    st.write("---")
    _mfg_reg_msg = st.empty()
    if st.button("➕ 製造データを記録", type="primary", use_container_width=True):
        if not pm or not mq: st.error("⚠️ 製品・数量は必須")
        else:
            nid = str(uuid.uuid4())[:6].upper()
            if iadj_m:
                rt_adj = f"【在庫調整-】 {mr}".strip()
                app_sync("orders", pd.DataFrame([{
                    "ID": nid, "納品予定日": pd.to_datetime(mdt),
                    "顧客名": "在庫調整", "大カテゴリ": c_m, "製品名": pm,
                    "ケース数": to_int(mq), "運送会社": "",
                    "備考": rt_adj, "荷姿チェック": False, "発送備考": "",
                    "不良廃棄フラグ": False, "日付未定フラグ": False,
                    "登録日時": datetime.now(JST).replace(tzinfo=None)
                }]))
                flash("success", f"📊 在庫調整(－)を登録しました！【{fn(pm)}】 -{to_int(mq):,} cs  現在庫: {cs.get(pm,0):,} → {cs.get(pm,0)-to_int(mq):,} cs")
                st.rerun()
            else:
                rt = f"{'【リパック】' if irp else ''} {'【資材非連動】' if irp and not ipl else ''} {mr}".strip()
                app_sync("manufactures", pd.DataFrame([{"ID":nid,"製造予定日":pd.to_datetime(mdt),"大カテゴリ":c_m,"製品名":pm,"ケース数":to_int(mq),"リパックフラグ":irp,"備考":rt,"登録日時": datetime.now(JST).replace(tzinfo=None)}]))
                _mfg_mat_msg = ""
                if ipl and not mst_u.empty and pm in mst_u["製品名"].values:
                    _mrow2 = mst_u[mst_u["製品名"]==pm].iloc[0]
                    _pnn = str(_mrow2.get("使用資材名","")).strip()
                    _kbn2 = str(_mrow2.get("製造登録区分","ケース")).strip()
                    _nyu2 = max(1, to_int(_mrow2.get("入数",10)))
                    _kou2 = max(1, to_int(_mrow2.get("甲消費数",4)))
                    if _pnn:
                        if _kbn2 == "袋":
                            _deduct_qty = abs(to_int(to_int(mq) / _nyu2))
                            _calc_memo = f"製造{to_int(mq)}袋 ÷ {_nyu2}(入数)"
                        elif _kbn2 == "甲":
                            _deduct_qty = abs(to_int(to_int(mq) * _kou2))
                            _calc_memo = f"製造{to_int(mq)}甲 × {_kou2}(甲消費数)"
                        else:
                            _deduct_qty = abs(to_int(mq))
                            _calc_memo = f"製造{to_int(mq)}ケース"
                        app_sync("packaging_logs", pd.DataFrame([{
                            "ID": str(uuid.uuid4())[:6].upper(), "登録日": pd.to_datetime(mdt), "資材名": _pnn,
                            "処理区分": "製造連動", "数量": _deduct_qty, "理由": f"製造ID:{nid} ({_calc_memo})",
                            "関連製品名": pm, "理論在庫": p_sum.get(_pnn,{}).get("現在庫",0) - _deduct_qty,
                            "備考": f"自動記録 [{_calc_memo}]", "登録日時": datetime.now(JST).replace(tzinfo=None)
                        }]))
                        _mfg_mat_msg = f"  ＋【{_pnn}】 {_deduct_qty:,}枚 自動減算（{_calc_memo}）"
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
    s_pks = [pn for pn,d in p_sum.items() if (d.get("管理区分","")=="定期発注(自動)" and d.get("現在庫",0) < d.get("発注点",0)) or (d.get("管理区分","")=="都度発注(受注連動)" and d.get("不足数",0)>0)]
    if s_pks: st.error("🚨 **要発注アラート:** " + "、".join(s_pks))
    tp1, tp2, tp3, tp4, tp5 = st.tabs(["📦 発注予測","📊 サマリ","📝 入出庫","✏️ 履歴","🛒 発注管理"])

    with tp1:
        if pk_m.empty: st.warning("マスタに資材がありません。")
        else:
            oa = []
            for pn, du in pf.items():
                d_info = p_sum.get(pn, {})
                kbn = d_info.get("管理区分", "定期発注(自動)")
                lt = d_info.get("発注リードタイム", 7) or 7
                ci = d_info.get("現在庫", 0)
                pt = d_info.get("発注点", 0)
                rec_pt = d_info.get("推奨発注点", 0)
                
                if kbn == "都度発注(受注連動)":
                    req = sum(du.values())
                    rem = ci + d_info.get("発注残", 0) - req
                    if rem < 0:
                        urg, uc, bc = "🔴 即手配(受注連動)", "#FEE2E2", "#DC2626"
                        dl = 0
                    else:
                        urg, uc, bc = "✅ 充足(受注連動)", "#F0FDF4", "#059669"
                        dl = 999
                    oa.append({
                        "資材名": f"{pn} [都度]", "現在庫": ci, "設定点/推奨": f"0 / {req}(必要量)", 
                        "LT": lt, "在庫日数": "連動", "発注推奨日": "都度", "枯渇予測": "―",
                        "緊急度": urg, "_s": dl, "_c": uc, "_b": bc
                    })
                else:
                    ri = ci; ro_d = None; z_d = None; io = None; cu = 0
                    for d_lt in pd.date_range(today, today+timedelta(days=fd)):
                        u = du.get(d_lt,0); ri-=u; cu+=u
                        if ri<=pt and ro_d is None: ro_d=d_lt; io=ri
                        if ri<=0 and z_d is None: z_d=d_lt
                    
                    if ro_d:
                        od = ro_d - timedelta(days=lt); dl = (od.date() - date.today()).days
                        urg, uc, bc = ("🔴 今すぐ発注！","#FEE2E2","#DC2626") if dl<=0 else (f"🟠 {dl}日以内","#FFF7ED","#EA580C") if dl<=3 else (f"🟡 {dl}日以内","#FFFBEB","#D97706") if dl<=7 else (f"🔵 {dl}日後","#EFF6FF","#2563EB")
                    else: od=None; io=None; dl=999; urg, uc, bc = "✅ 問題なし", "#F0FDF4", "#059669"
                    
                    days_str = f"{int(d_info.get('在庫日数',999))}日" if d_info.get('在庫日数',999) < 999 else "潤沢"
                    oa.append({
                        "資材名": pn, "現在庫": ci, "設定点/推奨": f"{pt} / {rec_pt}",
                        "LT": lt, "在庫日数": days_str, "発注推奨日": od.strftime("%Y/%m/%d") if od else "―",
                        "枯渇予測": z_d.strftime("%Y/%m/%d") if z_d else "―", "緊急度": urg,
                        "_s": dl, "_c": uc, "_b": bc
                    })
            
            if not oa:
                df_a = pd.DataFrame(columns=["資材名","現在庫","設定点/推奨","LT","在庫日数","発注推奨日","枯渇予測","緊急度","_s","_c","_b"])
            else:
                df_a = pd.DataFrame(oa).sort_values("_s").reset_index(drop=True)
                
            u_df = df_a[df_a["_s"]<=7] if not df_a.empty else pd.DataFrame()
            if not u_df.empty:
                st.markdown("### 🚨 直近7日以内に発注手配が必要")
                for _, r in u_df.iterrows(): st.markdown(f'<div style="background:{r["_c"]};border-left:6px solid {r["_b"]};border-radius:10px;padding:14px;margin-bottom:10px;"><b>📦 {r["資材名"]}</b> <span style="float:right;font-weight:900;">{r["緊急度"]}</span><br><span style="font-size:13px;">現在庫: {r["現在庫"]:,} | 設定/推奨: {r.get("設定点/推奨","")} | LT: {r["LT"]}日<br>⏰ <b>発注点到達: {r["発注推奨日"]}</b><br>📉 <b>枯渇予測: {r["枯渇予測"]}</b></span></div>', unsafe_allow_html=True)
            
            st.dataframe(df_a[["資材名","現在庫","設定点/推奨","LT","在庫日数","発注推奨日","枯渇予測","緊急度"]].style.apply(lambda r: ['background-color:#FEE2E2;font-weight:bold;']*len(r) if "即手配" in str(r.get("緊急度","")) or "今すぐ" in str(r.get("緊急度","")) else (['background-color:#FFF7ED;']*len(r) if "🟠" in str(r.get("緊急度","")) else (['background-color:#FFFBEB;']*len(r) if "🟡" in str(r.get("緊急度","")) else (['background-color:#EFF6FF;']*len(r) if "🔵" in str(r.get("緊急度","")) else ['background-color:#F0FDF4;']*len(r)))), axis=1), use_container_width=True, hide_index=True, height=500)

            pack_mst_unique = pk_m.drop_duplicates(subset=["資材名"]) if not pk_m.empty else pd.DataFrame(columns=["資材名"])
            spg = st.selectbox("グラフ表示", options=[r["資材名"] for _, r in pack_mst_unique.iterrows() if r["資材名"]])
            if spg:
                # ★修復：過去30日の実績〜未来90日の予測を繋げて描画する
                ri = p_sum.get(spg,{}).get("現在庫",0)
                ri_future = ri
                gd, gs, gu = [], [], []
                
                # 未来予測（現在庫から順算）
                for d_g in pd.date_range(today, today+timedelta(days=fd)):
                    ug = pf.get(spg,{}).get(d_g,0)
                    ri_future -= ug
                    gd.append(d_g)
                    gs.append(ri_future)
                    gu.append(-ug)
                
                # 過去30日実績（現在庫から逆算）
                ri_past = ri
                past_dates = pd.date_range(today-timedelta(days=30), today-timedelta(days=1))
                past_gd, past_gs, past_gu = [], [], []
                for d_g in reversed(past_dates):
                    net = net_change_by_day.get(spg, {}).get((d_g + timedelta(days=1)).date(), 0)
                    ri_past = ri_past - net
                    past_gd.insert(0, d_g)
                    past_gs.insert(0, ri_past)
                    past_u = daily_usage.get(spg, {}).get(d_g.strftime("%Y-%m-%d"), 0)
                    past_gu.insert(0, -past_u)
                
                full_gd = past_gd + gd
                full_gs = past_gs + gs
                full_gu = past_gu + gu

                fig = go.Figure()
                fig.add_trace(go.Bar(x=full_gd, y=full_gu, name="日別出庫/消費", marker_color="#F43F5E", opacity=0.55))
                fig.add_trace(go.Scatter(x=full_gd, y=full_gs, name="予測/実績在庫", mode="lines+markers", line=dict(color="#2563EB", width=2.5)))
                fig.add_hline(y=p_sum.get(spg,{}).get("発注点",0), line_dash="dash", line_color="#F59E0B", annotation_text="発注点")
                fig.add_hline(y=0, line_dash="dot", line_color="#DC2626", annotation_text="ゼロ")
                fig.add_vline(x=today, line_dash="dash", line_color="#10B981", annotation_text="今日")
                fig.update_layout(title=f"【{spg}】 過去30日実績〜未来予測 在庫推移", hovermode="x unified", barmode="relative", margin=dict(l=10,r=10,t=55,b=10), height=380)
                st.plotly_chart(fig, use_container_width=True)

    with tp2:
        if not p_sum:
            st.info("資材マスタが登録されていません。")
        else:
            c_btn1, c_btn2 = st.columns([2, 3])
            if c_btn1.button("✨ 推奨発注点をマスタに一括反映して保存", type="primary", key="btn_apply_rec_pt"):
                upd = pk_m.copy()
                for pn, d_info in p_sum.items():
                    if d_info.get("管理区分") == "定期発注(自動)":
                        upd.loc[upd["資材名"] == pn, "発注点"] = d_info.get("推奨発注点", 0)
                save_sync("packaging_master", upd)
                flash("success", "✅ 推奨発注点をマスタに反映しました。")
                st.rerun()

            for item in p_sum.values():
                if item.get("管理区分") == "都度発注(受注連動)":
                    item["在庫日数表示"] = "連動"
                else:
                    item["在庫日数表示"] = f"{int(item.get('在庫日数', 999))}日" if item.get("在庫日数", 999) < 999 else "潤沢"
                    
            _sum_df = pd.DataFrame([{"資材名":k, **v} for k,v in p_sum.items()])
            
            if not _sum_df.empty:
                _sum_df["発注点(推奨)"] = _sum_df.get("発注点", 0).astype(str) + " (" + _sum_df.get("推奨発注点", 0).astype(str) + ")"
                
                if "在庫日数" in _sum_df.columns:
                    _sum_df = _sum_df.drop(columns=["在庫日数"])
                _sum_df = _sum_df.rename(columns={"在庫日数表示": "在庫日数"})
                
                _sum_cols = [c for c in ["資材名","管理区分","現在庫","発注点(推奨)","状態","在庫日数","単位"] if c in _sum_df.columns]
                
                def _highlight_mat(row):
                    mat_name = row.get("資材名", "")
                    color = p_sum.get(mat_name, {}).get("アラート色", "")
                    return [f"background-color: {color}" if color else ""] * len(row)

                st.dataframe(
                    _sum_df[_sum_cols].style.apply(_highlight_mat, axis=1), 
                    use_container_width=True, 
                    hide_index=True
                )
            else:
                st.info("表示できる資材データがありません。")
    with tp3:
        pd_t = st.date_input("📅 処理日", value=date.today())
        pack_mst_unique = pk_m.drop_duplicates(subset=["資材名"]) if not pk_m.empty else pd.DataFrame(columns=["資材名"])
        c1,c2 = st.columns([1.5,2.5]); s_pk = c1.text_input("🔍 検索"); f_pk = [p for p in pack_mst_unique["資材名"].tolist() if s_pk in p and str(p)] if s_pk else [p for p in pack_mst_unique["資材名"].tolist() if str(p)]
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
                        flash("info", f"ℹ️ 【{sl_pk}】 在庫数に変更なし（棚卸一致）")
                        st.rerun()
                    else:
                        fpt, lq = ("入庫", diff) if diff > 0 else ("出庫", abs(diff))
                        app_sync("packaging_logs", pd.DataFrame([{"ID":str(uuid.uuid4())[:6].upper(),"登録日":pd.to_datetime(pd_t),"資材名":sl_pk,"処理区分":fpt,"数量":lq,"理由":pr,"関連製品名":"","理論在庫":"","備考":prm,"登録日時":datetime.now()}]))
                        flash("success", f"✅ 登録しました！【{sl_pk}】 棚卸調整 {'+' if fpt=='入庫' else '-'}{lq} ({fpt})")
                        st.rerun()
                elif lq > 0:
                    app_sync("packaging_logs", pd.DataFrame([{"ID":str(uuid.uuid4())[:6].upper(),"登録日":pd.to_datetime(pd_t),"資材名":sl_pk,"処理区分":fpt,"数量":lq,"理由":pr,"関連製品名":"","理論在庫":"","備考":prm,"登録日時":datetime.now()}]))
                    disp_type = "入庫" if "入庫" in pt else "出庫"
                    flash("success", f"✅ 登録しました！【{sl_pk}】 {disp_type} {lq:,} 枚 / {pr}")
                    st.rerun()
                else:
                    _pk_msg.error("⚠️ 数量は1以上を入力してください")
        show_flash_inline(_pk_msg)

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
                    }, key="pack_log_del_ed"
                )
                _del_ids = []
                for i, row in _del_editor.iterrows():
                    if row.get("削除", False):
                        _del_ids.append(_dpk_show.iloc[i]["ID"])

                _del_msg = st.empty()
                _del_col1, _del_col2 = st.columns([1, 3])
                if _del_col1.button(f"🗑️ 選択行を削除（{len(_del_ids)}件）", type="primary", disabled=(len(_del_ids)==0), key="btn_del_log"):
                    if _del_ids:
                        new_pk = pk_l[~pk_l["ID"].isin(_del_ids)].copy()
                        save_sync("packaging_logs", new_pk)
                        flash("success" if len(_del_ids) > 0 else "info", f"🗑️ {len(_del_ids)}件の履歴を削除しました。")
                        st.rerun()
                show_flash_inline(_del_msg)
            else:
                # ★修復：エディタから返ってきたIDを信頼するように変更し、履歴消失バグを防止
                edp = st.data_editor(
                    _dpk_show[_tp4_cols], hide_index=True,
                    use_container_width=True,
                    height=min(600, _h_limit * 38 + 60),
                    column_config={
                        "ID": None,
                        "処理区分": st.column_config.SelectboxColumn(options=["入庫","出庫","製造連動"]),
                        "数量": st.column_config.NumberColumn(min_value=1, step=1, format="%d"),
                    }, key="pack_log_edit_ed"
                )
                _hist_save_msg = st.empty()
                if st.button("💾 履歴を保存", key="btn_spk", type="primary"):
                    edited_ids = edp["ID"].tolist()
                    rest = pk_l[~pk_l["ID"].isin(edited_ids)].copy()
                    edp_with_id = edp.copy()
                    edp_with_id["登録日"] = pd.to_datetime(edp_with_id["登録日(表示)"].str.split(" ").str[0], errors="coerce")
                    keep_cols = [c for c in ["ID","理論在庫","登録日時"] if c in pk_l.columns]
                    merged = pd.merge(edp_with_id.drop(columns=["登録日(表示)"], errors="ignore"), pk_l[keep_cols], on="ID", how="left")
                    merged = merged.reindex(columns=pk_l.columns)
                    save_sync("packaging_logs", pd.concat([rest, merged], ignore_index=True))
                    flash("success", "✅ 資材履歴を保存しました。")
                    st.rerun()
                show_flash_inline(_hist_save_msg)

    with tp5:
        st.markdown('<div class="section-title">🛒 資材発注管理</div>', unsafe_allow_html=True)
        st.markdown('<div class="info-tip">💡 発注登録 → 一覧管理 → 納入完了処理（在庫自動加算）の流れで管理できます。</div>', unsafe_allow_html=True)
        _PO_COLS = ["発注ID","発注日","資材名","発注時在庫","発注数","発注単価","仕入先","納入予定日","実際納入日","実際納入数","ステータス","備考","登録日時"]
        if "po_df_loaded" not in st.session_state:
            try:
                _ws_po = sheet.worksheet("order_purchases")
                _po_data = _ws_po.get_all_values()
                if len(_po_data) > 1:
                    po_df = pd.DataFrame(_po_data[1:], columns=_po_data[0])
                    po_df.columns = po_df.columns.str.strip()
                    po_df = po_df.reindex(columns=_PO_COLS, fill_value="")
                else: po_df = pd.DataFrame(columns=_PO_COLS)
            except Exception: po_df = pd.DataFrame(columns=_PO_COLS)
            st.session_state.order_purchases_df = po_df
            st.session_state.po_df_loaded = True

        po_df = st.session_state.order_purchases_df
        def _save_po(df):
            try:
                try: _wsp = sheet.worksheet("order_purchases")
                except: _wsp = sheet.add_worksheet(title="order_purchases", rows="500", cols="20")
                _wsp.clear()
                _ds = df.copy().fillna("").astype(str)
                _wsp.update(values=[_ds.columns.tolist()] + _ds.values.tolist(), range_name="A1")
                st.cache_data.clear()
                st.session_state.order_purchases_df = df
                st.session_state.po_df_loaded = True
            except Exception as e: st.error(f"保存エラー: {e}")

        _alert_mats = [(pn, d) for pn,d in p_sum.items() if (d.get("管理区分")=="定期発注(自動)" and d.get("現在庫",0) < d.get("発注点",0)) or (d.get("管理区分")=="都度発注(受注連動)" and d.get("不足数",0)>0)]
        if _alert_mats:
            st.markdown(f'<div class="danger-banner">🚨 手配が必要な資材が <b>{len(_alert_mats)}件</b> あります：{" / ".join(m for m,_ in _alert_mats[:5])}{"…" if len(_alert_mats)>5 else ""}</div>', unsafe_allow_html=True)

        po_t1, po_t2, po_t3 = st.tabs(["➕ 新規発注登録", "📋 発注一覧", "✅ 納入完了処理"])
        with po_t1:
            st.markdown("**📝 新発注を登録**")
            pack_names = [pn for pn in p_sum.keys()] if p_sum else []
            po_c1, po_c2 = st.columns([1.5, 2.5])
            _po_s = po_c1.text_input("🔍 資材検索", key="po_search")
            _po_filtered = [p for p in pack_names if _po_s in p] if _po_s else pack_names
            _po_mat = po_c2.selectbox("📦 資材名", options=_po_filtered, index=None, key="po_mat_sel")
            po_r1, po_r2, po_r3 = st.columns(3)
            _po_date  = po_r1.date_input("📅 発注日", value=date.today(), key="po_date")
            _po_qty   = po_r2.number_input("発注数（枚）", min_value=1, step=100, value=1000, key="po_qty")
            _po_price = po_r3.number_input("単価（円/枚）", min_value=0, step=1, value=0, key="po_price", format="%d")
            po_r4, po_r5 = st.columns(2)
            _po_supplier = po_r4.text_input("🏢 仕入先", key="po_supplier", placeholder=p_sum.get(_po_mat,{}).get("仕入先","") if _po_mat else "")
            _lt_days = to_int(pk_m[pk_m["資材名"]==_po_mat]["発注リードタイム"].iloc[0]) if (not pk_m.empty and _po_mat and _po_mat in pk_m["資材名"].values) else 7
            _po_eta = po_r5.date_input(f"📦 納入予定日（LT:{_lt_days}日から自動算出）", value=date.today() + timedelta(days=_lt_days), key="po_eta")
            _po_rem = st.text_input("📝 備考", key="po_rem")
            if _po_mat:
                _d_info = p_sum.get(_po_mat,{})
                _cur_inv = _d_info.get("現在庫",0)
                _order_pt = _d_info.get("発注点",0)
                if _d_info.get("管理区分") == "都度発注(受注連動)":
                    _req = _d_info.get("受注残", 0)
                    _col = "#FEE2E2" if _cur_inv + _d_info.get("発注残",0) < _req else "#D1FAE5"
                    st.markdown(f'<div style="background:{_col};border-radius:8px;padding:8px 14px;font-size:13px;margin:4px 0;">📊 <b>{_po_mat} [受注連動]</b>  現在庫: <b>{_cur_inv:,} 枚</b>  必要量: {_req:,} 枚  → 発注後予定在庫: <b>{_cur_inv + _po_qty:,} 枚</b></div>', unsafe_allow_html=True)
                else:
                    _col = "#FEE2E2" if _cur_inv < _order_pt else "#D1FAE5"
                    st.markdown(f'<div style="background:{_col};border-radius:8px;padding:8px 14px;font-size:13px;margin:4px 0;">📊 <b>{_po_mat}</b>  現在庫: <b>{_cur_inv:,} 枚</b>  発注点: {_order_pt:,} 枚  {"⚠️ 発注点以下！" if _cur_inv < _order_pt else "✅ 在庫充足"}  → 発注後予定在庫: <b>{_cur_inv + _po_qty:,} 枚</b></div>', unsafe_allow_html=True)
            
            _po_reg_msg = st.empty()
            if st.button("✅ 発注を登録", type="primary", use_container_width=True, key="po_reg_btn"):
                if not _po_mat:
                    _po_reg_msg.error("⚠️ 資材名は必須です")
                else:
                    _new_po = pd.DataFrame([{
                        "発注ID": f"PO-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        "発注日": _po_date.strftime("%Y-%m-%d"),
                        "資材名": _po_mat,
                        "発注時在庫": p_sum.get(_po_mat, {}).get("現在庫", 0),
                        "発注数": _po_qty,
                        "発注単価": _po_price,
                        "仕入先": _po_supplier,
                        "納入予定日": _po_eta.strftime("%Y-%m-%d"),
                        "実際納入日": "",
                        "実際納入数": 0,
                        "ステータス": "発注済",
                        "備考": _po_rem,
                        "登録日時": datetime.now(JST).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
                    }])
                    merged_po = pd.concat([po_df, _new_po], ignore_index=True)
                    _save_po(merged_po)
                    flash("success", f"✅ 発注を登録しました！【{_po_mat}】 {_po_qty:,}枚  納入予定: {_po_eta.strftime('%Y/%m/%d')}")
                    st.rerun()
            show_flash_inline(_po_reg_msg)

        with po_t2:
            if po_df.empty: st.info("発注データがありません。")
            else:
                st.markdown("💡 編集して「保存」ボタンを押してください。削除は行チェックボックスで行います。")
                
                po_edit = po_df.copy()
                po_edit.insert(0, "🗑️ 削除", False)
                
                edited_df = st.data_editor(
                    po_edit, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={"🗑️ 削除": st.column_config.CheckboxColumn(width="small")},
                    key="po_edit_editor"
                )
                
                c1, c2 = st.columns(2)
                if c1.button("💾 変更を保存"):
                    to_keep = edited_df[edited_df["🗑️ 削除"] == False].drop(columns=["🗑️ 削除"])
                    _save_po(to_keep)
                    flash("success", "✅ 発注データを更新しました。")
                    st.rerun()
                
                show_flash_inline() 

        with po_t3:
            st.markdown("**✅ 納入完了処理**")
            st.markdown('<div class="info-tip">💡 納入された資材の実数量を入力し「納入完了」を押すと、資材在庫に自動加算されます。</div>', unsafe_allow_html=True)
            _open_po = po_df[po_df["ステータス"].isin(["発注済","一部納入"])].copy() if not po_df.empty else pd.DataFrame()
            if _open_po.empty: st.success("✅ 処理待ちの発注はありません。")
            else:
                _open_po["表示"] = _open_po.apply(lambda r: f"[{r.get('発注ID','')}] {r.get('資材名','')}  発注{r.get('発注数','')}枚  納入予定:{r.get('納入予定日','')}", axis=1)
                _sel_po_label = st.selectbox("処理する発注を選択", options=_open_po["表示"].tolist(), key="po_sel_complete")
                _sel_po_idx = _open_po[_open_po["表示"]==_sel_po_label].index[0] if _sel_po_label else None
                if _sel_po_idx is not None:
                    _sel_row = _open_po.loc[_sel_po_idx]
                    _mat_nm = _sel_row.get("資材名","")
                    _ord_qty = to_int(_sel_row.get("発注数",0))
                    _already = to_int(_sel_row.get("実際納入数",0))
                    st.markdown(f"""<div style="background:#EFF6FF;border-radius:8px;padding:10px 14px;margin:6px 0;font-size:13px;">📦 <b>{_mat_nm}</b>　発注数: {_ord_qty:,}枚　既納入数: {_already:,}枚　残: {max(0,_ord_qty-_already):,}枚</div>""", unsafe_allow_html=True)
                    _del_c1, _del_c2, _del_c3 = st.columns(3)
                    _actual_date = _del_c1.date_input("📅 実際の納入日", value=date.today(), key="po_actual_date")
                    _actual_qty  = _del_c2.number_input("📦 実際の納入数（枚）", min_value=1, step=100, value=max(1, _ord_qty - _already), key="po_actual_qty")
                    _po_comp_rem = _del_c3.text_input("備考", key="po_comp_rem")
                    _new_total = _already + _actual_qty
                    _new_status = "納入完了" if _new_total >= _ord_qty else "一部納入"
                    st.caption(f"納入後合計: {_new_total:,}枚 / {_ord_qty:,}枚  → ステータス:「{_new_status}」　現在庫: {p_sum.get(_mat_nm,{}).get('現在庫',0):,}枚 → {p_sum.get(_mat_nm,{}).get('現在庫',0)+_actual_qty:,}枚")
                    _comp_msg = st.empty()
                    if st.button("✅ 納入完了処理を実行", type="primary", use_container_width=True, key="po_comp_btn"):
                        app_sync("packaging_logs", pd.DataFrame([{
                            "ID": str(uuid.uuid4())[:6].upper(), "登録日": pd.to_datetime(_actual_date), "資材名": _mat_nm, "処理区分": "入庫", "数量": _actual_qty,
                            "理由": f"発注納入 [{_sel_row.get('発注ID','')}]", "関連製品名": "", "理論在庫": p_sum.get(_mat_nm,{}).get("現在庫",0) + _actual_qty,
                            "備考": f"発注納入完了 仕入先:{_sel_row.get('仕入先','')} {_po_comp_rem}", "登録日時": datetime.now(JST).replace(tzinfo=None)
                        }]))
                        _po_updated = po_df.copy()
                        _po_updated.loc[_po_updated["発注ID"]==_sel_row["発注ID"], "実際納入日"] = _actual_date.strftime("%Y-%m-%d")
                        _po_updated.loc[_po_updated["発注ID"]==_sel_row["発注ID"], "実際納入数"] = str(_new_total)
                        _po_updated.loc[_po_updated["発注ID"]==_sel_row["発注ID"], "ステータス"] = _new_status
                        _save_po(_po_updated)
                        flash("success", f"✅ 納入完了！【{_mat_nm}】 {_actual_qty:,}枚 入庫  現在庫: {p_sum.get(_mat_nm,{}).get('現在庫',0):,} → {p_sum.get(_mat_nm,{}).get('現在庫',0)+_actual_qty:,}枚  ステータス→「{_new_status}」")
                        st.rerun()
                    show_flash_inline(_comp_msg)

# ─────────────────────────────────────────────
# 📑 登録一覧
# ─────────────────────────────────────────────
elif pg == "📑 登録一覧":
    page_header("📑 登録データ一覧・出力")
    tl1, tl2, tl3 = st.tabs(["📋 受注・出荷","🏭 製造","📦 資材"])
    with tl1:
        if not odf.empty:
            eo = odf.sort_values("登録日時", ascending=False).copy(); eo["出荷日"] = eo["納品予定日"].apply(format_date_jp)
            def _zaiko_status(r):
                try:
                    d = pd.Timestamp(str(r["納品予定日"])).normalize()
                    v = fs.get(r["製品名"],{}).get(d, 0)
                    return f"不足 ({v})" if v < 0 else "OK"
                except Exception: return "―"
            eo["在庫状況"] = eo.apply(_zaiko_status, axis=1)
            st.dataframe(eo[["ID","出荷日","顧客名","製品名","ケース数","運送会社","備考","荷姿チェック","在庫状況","不良廃棄フラグ"]].style.apply(lambda r: ['background-color:#D1FAE5;']*len(r) if str(r.get("荷姿チェック")).upper()=="TRUE" else (['background-color:#FEE2E2;font-weight:bold;']*len(r) if "不足" in str(r.get("在庫状況","")) else ['']*len(r)), axis=1), hide_index=True, height=600)
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
    t1, t0, t2, t3, t4, t5 = st.tabs(["📉 1ヶ月在庫予測", "⚠️ 7日以内欠品予測", "📅 週間カレンダー", "🔍 製品別詳細ビュー", "👤 顧客別スケジュール", "📋 棚卸入力"])

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
            if 'pend' in dir() and isinstance(pend, pd.Series) and not pend.empty:
                st.markdown(f'<div class="info-tip">💡 出荷日未定の受注 {int(pend.sum()):,} cs（{pend[pend>0].shape[0]}品目）を現在庫から引当済みです。</div>', unsafe_allow_html=True)
            if unmatched_products:
                with st.expander(f"⚠️ マスタと製品名が一致しないデータが {len(unmatched_products)} 件あります（在庫予測に反映されません）", expanded=False):
                    st.warning("受注・製造データの製品名が「⚙️ マスタ・分析」の製品マスタと完全一致していないため、以下の製品名は在庫予測から除外されています。表記ゆれ（スペース・全角半角・記号違いなど）がないかご確認ください。")
                    st.dataframe(pd.DataFrame({"未一致の製品名": unmatched_products}), hide_index=True, use_container_width=True)
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
                
                with st.expander("📜 過去1年履歴 ＆ 出荷予定", expanded=True):
                    _fo = odf[(odf["製品名"]==dp)&(pd.to_datetime(odf["納品予定日"],errors='coerce')>=today)] if not odf.empty else pd.DataFrame()
                    _fm = mdf[(mdf["製品名"]==dp)&(pd.to_datetime(mdf["製造予定日"],errors='coerce')>=today)&(~mdf["備考"].fillna("").str.contains("【在庫非反映】"))] if not mdf.empty else pd.DataFrame()
                    tho = ph["ケース数"].apply(to_int).sum() if not ph.empty else 0; thm = mh["ケース数"].apply(to_int).sum() if not mh.empty else 0
                    fto = _fo["ケース数"].apply(to_int).sum() if not _fo.empty else 0; ftm = _fm["ケース数"].apply(to_int).sum() if not _fm.empty else 0
                    k1,k2,k3,k4,k5 = st.columns(5)
                    k1.metric("過去1年 出荷",f"{tho:,} cs"); k2.metric("過去1年 製造",f"{thm:,} cs"); k3.metric("現在庫",f"{cs.get(dp,0):,} cs"); k4.metric("今後 出荷予定",f"{fto:,} cs"); k5.metric("今後 製造予定",f"{ftm:,} cs")

                    _gr = []
                    for _df, _dc, _lb in [(ph,"納品予定日","出荷(実績)"), (mh,"製造予定日","製造(実績)"), (_fo,"納品予定日","出荷(予定)"), (_fm,"製造予定日","製造(予定)")]:
                        if not _df.empty:
                            _t = _df.copy(); _t["年月"] = pd.to_datetime(_t[_dc],errors='coerce').dt.to_period("M").astype(str)
                            for ym, g in _t.groupby("年月"): _gr.append({"年月":ym,"種別":_lb,"ケース数":g["ケース数"].apply(to_int).sum()})
                    if _gr:
                        _dgp = pd.DataFrame(_gr).sort_values("年月")
                        _figp = px.bar(_dgp, x="年月", y="ケース数", color="種別", barmode="group",
                                        color_discrete_map={"出荷(実績)":"#F43F5E","出荷(予定)":"#FCA5A5","製造(実績)":"#10B981","製造(予定)":"#6EE7B7"})
                        _figp.update_layout(margin=dict(l=10,r=10,t=20,b=10), height=280, legend=dict(orientation="h", y=1.15))
                        st.plotly_chart(_figp, use_container_width=True)

                    ch1, ch2 = st.columns(2)
                    with ch1:
                        st.markdown('<div style="font-size:13px;font-weight:800;color:#DC2626;border-left:4px solid #DC2626;padding-left:8px;">🚚 出荷履歴（過去）</div>', unsafe_allow_html=True)
                        if not ph.empty: st.dataframe(ph.assign(日付=ph["納品予定日"].apply(format_date_jp))[["日付","顧客名","ケース数","備考"]].sort_values("日付",ascending=False), hide_index=True, height=220)
                    with ch2:
                        st.markdown('<div style="font-size:13px;font-weight:800;color:#059669;border-left:4px solid #059669;padding-left:8px;">🏭 製造履歴（過去）</div>', unsafe_allow_html=True)
                        if not mh.empty: st.dataframe(mh.assign(日付=mh["製造予定日"].apply(format_date_jp))[["日付","ケース数","備考"]].sort_values("日付",ascending=False).style.apply(lambda r: ["background:#F8FAFC;color:#64748B;"]*len(r) if "【在庫非反映】" in str(r.get("備考","")) else [""]*len(r), axis=1), hide_index=True, height=220)
                    ch3, ch4 = st.columns(2)
                    with ch3:
                        st.markdown('<div style="font-size:13px;font-weight:800;color:#F97316;border-left:4px solid #F97316;padding-left:8px;">📦 出荷予定（今後）</div>', unsafe_allow_html=True)
                        if not _fo.empty: st.dataframe(_fo.assign(日付=_fo["納品予定日"].apply(format_date_jp))[["日付","顧客名","ケース数","備考"]].sort_values("日付"), hide_index=True, height=220)
                        else: st.caption("予定なし")
                    with ch4:
                        st.markdown('<div style="font-size:13px;font-weight:800;color:#6EE7B7;border-left:4px solid #10B981;padding-left:8px;">🏭 製造予定（今後）</div>', unsafe_allow_html=True)
                        if not _fm.empty: st.dataframe(_fm.assign(日付=_fm["製造予定日"].apply(format_date_jp))[["日付","ケース数","備考"]].sort_values("日付"), hide_index=True, height=220)
                        else: st.caption("予定なし")

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
        _odf_dates = _nd_to_date(odf["納品予定日"]) if not odf.empty else pd.Series(dtype=object)
        _mdf_dates = _nd_to_date(mdf["製造予定日"]) if not mdf.empty else pd.Series(dtype=object)
        for i in range(7):
            d2 = today + timedelta(days=i); d2_date = d2.date(); mh=""; oh=""
            if not mdf.empty:
                for _,r in mdf[_mdf_dates == d2_date].iterrows():
                    bg,bc = ("#DBEAFE","#1E3A8A") if r.get("リパックフラグ") in [True,"TRUE"] else ("#F0FFF4","#10B981")
                    mh+=f'<div style="background:{bg};border-left:4px solid {bc};padding:6px;margin-bottom:4px;"><b>{fn(r["製品名"])}</b><span style="float:right;">{to_int(r.get("ケース数",0))}cs</span></div>'
            if not odf.empty:
                for _,r in odf[_odf_dates == d2_date].iterrows():
                    sod = fs.get(r["製品名"],{}).get(d2, cs.get(r["製品名"],0))
                    if r.get("荷姿チェック") in [True,"TRUE"]:
                        qh,bg,bc = f'<span style="text-decoration:line-through;">{to_int(r.get("ケース数",0))}cs ✅</span>',"#D1FAE5","#059669"
                    elif sod < 0:
                        qh,bg,bc = f'<span class="shortage-red">{to_int(r.get("ケース数",0))}cs ⚠️予定在庫:{sod}cs</span>',"#FEE2E2","#DC2626"
                    elif sod < to_int(r.get("ケース数",0)):
                        qh,bg,bc = f'<span style="color:#D97706;font-weight:900;">{to_int(r.get("ケース数",0))}cs ⚡予定在庫:{sod}cs</span>',"#FFFBEB","#D97706"
                    else:
                        qh,bg,bc = f'<span style="color:#1D4ED8;font-weight:900;">{to_int(r.get("ケース数",0))}cs ✓{sod}cs</span>',"#F0F7FF","#2563EB"
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

            with dtf:
                st.markdown('<div class="section-title">📅 今後60日間スケジュール</div>', unsafe_allow_html=True)
                pof = odf[(odf["製品名"]==sp)&(pd.to_datetime(odf["納品予定日"],errors='coerce')>=pd.Timestamp(today))&(odf["不良廃棄フラグ"]==False)] if not odf.empty else pd.DataFrame()
                vm3 = mdf[~mdf["備考"].fillna("").str.contains("【在庫非反映】")] if not mdf.empty else pd.DataFrame()
                pmf = vm3[(vm3["製品名"]==sp)&(pd.to_datetime(vm3["製造予定日"],errors='coerce')>=pd.Timestamp(today))] if not vm3.empty else pd.DataFrame()
                fk1,fk2,fk3,fk4 = st.columns(4)
                fk1.metric("現在庫", f"{cs.get(sp,0):,} cs")
                fk2.metric("今後60日 出荷予定", f"{pof['ケース数'].apply(to_int).sum() if not pof.empty else 0:,} cs")
                fk3.metric("今後60日 製造予定", f"{pmf['ケース数'].apply(to_int).sum() if not pmf.empty else 0:,} cs")
                fk4.metric("7日以内欠品", f"{sum(1 for d in pd.date_range(today,today+timedelta(days=7)) if fs.get(sp,{}).get(d,0)<0)} 日", delta_color="inverse")

                dtl = []; ts2_ = cs.get(sp,0)
                for d2 in pd.date_range(today, today+timedelta(days=59)):
                    do2 = pof[safe_dt_date(pof["納品予定日"])==d2.date()] if not pof.empty else pd.DataFrame()
                    oq2 = to_int(do2["ケース数"].sum()) if not do2.empty else 0
                    dm2 = pmf[safe_dt_date(pmf["製造予定日"])==d2.date()] if not pmf.empty else pd.DataFrame()
                    iq2 = to_int(dm2["ケース数"].sum()) if not dm2.empty else 0
                    ts2_ += (iq2 - oq2)
                    if iq2>0 or oq2>0 or ts2_<0:
                        cust = " / ".join(do2["顧客名"].dropna().astype(str).unique()) if not do2.empty else ""
                        dtl.append({"日付":format_date_jp(d2),"顧客":cust,"製造(入)":iq2 or "","出荷(出)":oq2 or "","予定在庫":ts2_})

                if dtl:
                    dfd = pd.DataFrame(dtl)
                    fig_dtf = go.Figure()
                    fig_dtf.add_trace(go.Bar(x=dfd["日付"],y=[r["製造(入)"] if r["製造(入)"]!="" else 0 for _,r in dfd.iterrows()],name="製造",marker_color="#10B981"))
                    fig_dtf.add_trace(go.Bar(x=dfd["日付"],y=[-(r["出荷(出)"] if r["出荷(出)"]!="" else 0) for _,r in dfd.iterrows()],name="出荷",marker_color="#F43F5E"))
                    fig_dtf.add_trace(go.Scatter(x=dfd["日付"],y=dfd["予定在庫"],name="予定在庫",mode="lines+markers",line=dict(color="#2563EB",width=2.5)))
                    fig_dtf.add_hline(y=0,line_dash="dot",line_color="#DC2626",annotation_text="在庫ゼロ")
                    fig_dtf.update_layout(barmode="relative",hovermode="x unified",margin=dict(l=10,r=10,t=30,b=10),height=320,plot_bgcolor="white")
                    st.plotly_chart(fig_dtf, use_container_width=True)
                    st.dataframe(dfd.style.map(lambda v: 'color:#DC2626;font-weight:900;background-color:#FEE2E2;' if isinstance(v,(int,float)) and v<0 else '', subset=["予定在庫"]), hide_index=True, use_container_width=True)
                else: st.info("今後60日間の出荷・製造予定はありません。")

                if not pof.empty:
                    st.markdown('<div class="section-title">📋 出荷予定一覧</div>', unsafe_allow_html=True)
                    pof_disp = pof.copy()
                    pof_disp["納品予定日"] = pof_disp["納品予定日"].apply(format_date_jp)
                    pof_disp["在庫状況"] = pof_disp.apply(lambda r: (f"❌ 欠品 ({fs.get(sp,{}).get(pd.Timestamp(str(r.get('納品予定日',''))).normalize() if pd.notnull(r.get('納品予定日')) else pd.Timestamp(today), 0)})" if fs.get(sp,{}).get(pd.Timestamp(today),0) < 0 else "✅ OK"), axis=1)
                    st.dataframe(pof_disp[["納品予定日","顧客名","ケース数","在庫状況","備考"]].sort_values("納品予定日"), hide_index=True, use_container_width=True)
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

    with t5:
        st.markdown('<div class="section-title">📋 製品 棚卸入力</div>', unsafe_allow_html=True)
        st.markdown("""<div class="info-tip">💡 実際に数えた在庫数（実棚卸数）を入力すると、現在の計算上の在庫との差分を自動計算し、「棚卸調整」として登録します。マスタの「初期在庫数」は変更しません。微調整用途を想定しています。</div>""", unsafe_allow_html=True)
        inv_d = st.date_input("📅 棚卸日", value=date.today(), key="inv_date")
        prod_list = sorted(mst_u["製品名"].dropna().unique().tolist()) if not mst_u.empty else []
        ic1, ic2 = st.columns([1.5, 2.5])
        inv_s = ic1.text_input("🔍 検索", key="inv_search")
        inv_f = [p for p in prod_list if inv_s in p] if inv_s else prod_list
        sel_p = ic2.selectbox("📦 製品を選択", options=inv_f, index=None, key="inv_prod")
        if sel_p:
            _cur_cs = cs.get(sel_p, 0)
            st.markdown(f'<div class="info-card">現在の計算上の在庫：<b style="font-size:18px;">{_cur_cs:,} cs</b></div>', unsafe_allow_html=True)
            actual_q = st.number_input("実際に数えた在庫数（ケース）", min_value=0, step=1, value=None, key="inv_qty")
            inv_note = st.text_input("📝 備考", key="inv_note")
            if actual_q is not None:
                _diff = to_int(actual_q) - _cur_cs
                if _diff == 0:
                    st.markdown('<div class="ok-banner">✅ 現在の在庫と一致しています（登録不要）</div>', unsafe_allow_html=True)
                else:
                    _dcolor = "#059669" if _diff > 0 else "#DC2626"
                    st.markdown(f'<div class="info-card" style="border-left-color:{_dcolor};">差分：<b style="color:{_dcolor};">{_diff:+,} cs</b>　（{_cur_cs:,} → {to_int(actual_q):,}）</div>', unsafe_allow_html=True)
            _inv_msg = st.empty()
            if st.button("✅ 棚卸を登録", type="primary", use_container_width=True, key="inv_submit"):
                if actual_q is None:
                    _inv_msg.error("⚠️ 実棚卸数を入力してください")
                else:
                    _diff = to_int(actual_q) - _cur_cs
                    _anchor = f"実棚卸数={to_int(actual_q)}"  # ← 将来在庫計算の基準値として解析される機械可読タグ
                    nid = str(uuid.uuid4())[:6].upper()
                    _cat = mst_u[mst_u["製品名"] == sel_p]["大カテゴリ"].iloc[0] if sel_p in mst_u["製品名"].values else ""
                    if _diff == 0:
                        app_sync("manufactures", pd.DataFrame([{
                            "ID": nid, "製造予定日": pd.to_datetime(inv_d),
                            "大カテゴリ": _cat, "製品名": sel_p, "ケース数": 0,
                            "リパックフラグ": False, "備考": f"【棚卸基準】{_anchor} {inv_note}".strip(),
                            "登録日時": datetime.now(JST).replace(tzinfo=None),
                        }]))
                        flash("success", f"✅【{sel_p}】棚卸一致を確認し、この時点を新しい在庫計算の基準にしました（{_cur_cs:,} cs）")
                    elif _diff > 0:
                        app_sync("manufactures", pd.DataFrame([{
                            "ID": nid, "製造予定日": pd.to_datetime(inv_d),
                            "大カテゴリ": _cat, "製品名": sel_p, "ケース数": _diff,
                            "リパックフラグ": False, "備考": f"【棚卸調整+】{_anchor} {inv_note}".strip(),
                            "登録日時": datetime.now(JST).replace(tzinfo=None),
                        }]))
                        flash("success", f"✅【{sel_p}】棚卸差分 {_diff:+,} cs を登録しました（{_cur_cs:,} → {to_int(actual_q):,}）。この時点が新しい在庫計算の基準になります。")
                    else:
                        app_sync("orders", pd.DataFrame([{
                            "ID": nid, "納品予定日": pd.to_datetime(inv_d),
                            "顧客名": "在庫調整（棚卸）", "大カテゴリ": _cat, "製品名": sel_p,
                            "ケース数": abs(_diff), "運送会社": "",
                            "備考": f"【棚卸調整-】{_anchor} {inv_note}".strip(), "荷姿チェック": False, "発送備考": "",
                            "不良廃棄フラグ": False, "日付未定フラグ": False,
                            "登録日時": datetime.now(JST).replace(tzinfo=None),
                        }]))
                        flash("success", f"✅【{sel_p}】棚卸差分 {_diff:+,} cs を登録しました（{_cur_cs:,} → {to_int(actual_q):,}）。この時点が新しい在庫計算の基準になります。")
                    st.rerun()
            show_flash_inline(_inv_msg)

        st.markdown('<div class="section-title">📜 棚卸 履歴</div>', unsafe_allow_html=True)
        _adj_o = odf[odf["備考"].fillna("").str.contains("実棚卸数=")] if not odf.empty else pd.DataFrame()
        _adj_m = mdf[mdf["備考"].fillna("").str.contains("実棚卸数=")] if not mdf.empty else pd.DataFrame()
        _hist_rows = []
        if not _adj_o.empty:
            for _, r in _adj_o.iterrows():
                _hist_rows.append({"日付": format_date_jp(r.get("納品予定日")), "製品名": r.get("製品名", ""), "差分": -to_int(r.get("ケース数", 0)), "備考": r.get("備考", ""), "登録日時": r.get("登録日時", "")})
        if not _adj_m.empty:
            for _, r in _adj_m.iterrows():
                _hist_rows.append({"日付": format_date_jp(r.get("製造予定日")), "製品名": r.get("製品名", ""), "差分": to_int(r.get("ケース数", 0)), "備考": r.get("備考", ""), "登録日時": r.get("登録日時", "")})
        if _hist_rows:
            _hist_df = pd.DataFrame(_hist_rows).sort_values("登録日時", ascending=False)
            st.dataframe(_hist_df[["日付", "製品名", "差分", "備考"]], hide_index=True, use_container_width=True, height=300)
        else:
            st.info("棚卸の履歴はまだありません。")

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
            _dtcol = pd.to_datetime(spo["納品予定日"], errors="coerce")
            _is_undet = (spo["日付未定フラグ"] == True) if "日付未定フラグ" in spo.columns else pd.Series(False, index=spo.index)
            spo_future = spo[(_dtcol >= today) & (~_is_undet)].copy()
            spo_past = spo[(_dtcol < today) & (~_is_undet)].copy()
            spo_undet = spo[_is_undet | _dtcol.isna()].copy()

            m1, m2, m3 = st.columns(3)
            m1.metric("📅 今後の予定", f"{len(spo_future)} 件", f"{spo_future['ケース数'].apply(to_int).sum():,} cs" if not spo_future.empty else "0 cs")
            m2.metric("🟡 日付未定", f"{len(spo_undet)} 件", f"{spo_undet['ケース数'].apply(to_int).sum():,} cs" if not spo_undet.empty else "0 cs")
            m3.metric("📜 過去の履歴", f"{len(spo_past)} 件", f"{spo_past['ケース数'].apply(to_int).sum():,} cs" if not spo_past.empty else "0 cs")

            def _style_spo(df):
                return df.style.apply(lambda r: ['background-color:#F3E8FF;font-weight:bold;']*len(r) if "特注" in str(r.get("種別","")) and "チャーター" in str(r.get("種別","")) else (['background-color:#EDE9FE;font-weight:bold;']*len(r) if "特注" in str(r.get("種別","")) else ['background-color:#E0F2FE;font-weight:bold;']*len(r)), axis=1)

            st.markdown('<div class="section-title">📅 今後の予定</div>', unsafe_allow_html=True)
            if spo_future.empty: st.caption("なし")
            else:
                spo_future["出荷予定日"] = spo_future["納品予定日"].apply(format_date_jp)
                spo_future["在庫状況"] = spo_future.apply(lambda r: ("❌ 欠品" if fs.get(nk2name.get(nk(r["製品名"]), r["製品名"]),{}).get(pd.to_datetime(r["納品予定日"]).normalize(), cs.get(nk2name.get(nk(r["製品名"]), r["製品名"]),0)) < 0 else "✅ OK"), axis=1)
                spo_future = spo_future.sort_values("納品予定日")
                _sc = [c for c in ["種別","出荷予定日","顧客名","製品名","ケース数","在庫状況","備考"] if c in spo_future.columns]
                st.dataframe(_style_spo(spo_future[_sc]), hide_index=True, use_container_width=True)

            st.markdown('<div class="section-title">🟡 日付未定</div>', unsafe_allow_html=True)
            if spo_undet.empty: st.caption("なし")
            else:
                spo_undet["出荷予定日"] = "🟡 未定"
                _sc = [c for c in ["種別","出荷予定日","顧客名","製品名","ケース数","備考"] if c in spo_undet.columns]
                st.dataframe(_style_spo(spo_undet[_sc]), hide_index=True, use_container_width=True)
                st.caption("💡 出荷日を確定するには「📋 受注登録」ページ下部の「🟡 日付未定受注を確定する」から対応してください。")

            with st.expander(f"📜 過去の履歴を見る（{len(spo_past)}件）"):
                if spo_past.empty: st.caption("なし")
                else:
                    spo_past["出荷予定日"] = spo_past["納品予定日"].apply(format_date_jp)
                    spo_past = spo_past.sort_values("納品予定日", ascending=False)
                    _sc = [c for c in ["種別","出荷予定日","顧客名","製品名","ケース数","備考"] if c in spo_past.columns]
                    st.dataframe(_style_spo(spo_past[_sc]), hide_index=True, use_container_width=True)
    with ts2:
        if not spo.empty:
            pl = sorted(spo["製品名"].unique().tolist()); sl = st.selectbox("製品", ["（全製品）"]+pl)
            fsp = (spo.copy() if sl=="（全製品）" else spo[spo["製品名"]==sl].copy()).sort_values("納品予定日")
            fsp["出荷予定日"] = fsp["納品予定日"].apply(format_date_jp)
            st.dataframe(fsp[[c for c in ["製品名","顧客名","出荷予定日","ケース数","備考"] if c in fsp.columns]], hide_index=True)
    with ts3:
        if not spo.empty:
            ex = sp_s["受注ID"].tolist() if not sp_s.empty else []; nr = [{"ID":str(uuid.uuid4())[:6].upper(),"受注ID":r["ID"],"製品名":r["製品名"],"顧客名":r["顧客名"],"納品予定日":r["納品予定日"],"出荷予定日":r["納品予定日"]-timedelta(days=1) if pd.notnull(r["納品予定日"]) else None,"備考":r.get("備考",""),"更新日時": datetime.now(JST).replace(tzinfo=None)} for _,r in spo.iterrows() if r["ID"] not in ex]
            sw = pd.concat([sp_s, pd.DataFrame(nr)], ignore_index=True) if nr else sp_s.copy()
            se = pd.merge(sw, odf[["ID","備考"]].rename(columns={"ID":"受注ID","備考":"受注備考"}), on="受注ID", how="left")
            se["種別"] = se["受注備考"].apply(lambda x: "特注" if "特注" in str(x) else "チャーター便"); se["出荷予定日(表示)"] = pd.to_datetime(se["納品予定日"],errors='coerce').apply(format_date_jp); se["出荷予定日_edit"] = pd.to_datetime(se["出荷予定日"],errors='coerce').dt.date
            ed = st.data_editor(se[[c for c in ["ID","種別","製品名","顧客名","出荷予定日(表示)","出荷予定日_edit","備考"] if c in se.columns]], hide_index=True, column_config={"ID":None,"種別":st.column_config.TextColumn(disabled=True),"製品名":st.column_config.TextColumn(disabled=True),"顧客名":st.column_config.TextColumn(disabled=True),"出荷予定日(表示)":st.column_config.TextColumn(disabled=True),"出荷予定日_edit":st.column_config.DateColumn("📅 出荷予定日",format="YYYY/MM/DD")})
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
        if p_sum: st.dataframe(pd.DataFrame([{"資材":k,"庫":v.get("現在庫",0),"点":v.get("発注点",0),"出":v.get("出庫",0)} for k,v in p_sum.items()]).style.apply(lambda r: ['background-color:#FFEDD5;color:#C2410C;']*len(r) if to_int(r.get("庫",0))<to_int(r.get("点",0)) else ['']*len(r), axis=1), hide_index=True)
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
        st.markdown('<div class="info-tip">💡 <b>製造登録区分</b>：製造・受注の登録単位とダンボール消費の計算をシンプルに設定できます。<br>・<b>ケース</b>：1登録で1枚消費<br>・<b>袋</b>：登録数 ÷ 入数 ＝ 消費枚数（例: 10袋登録 ÷ 入数10 = 1枚消費）<br>・<b>甲</b>：登録数 × 甲消費数 ＝ 消費枚数（例: 1甲登録 × 甲消費数4 = 4枚消費）</div>', unsafe_allow_html=True)
        em_base = mst.copy()
        
        if "製造登録区分" not in em_base.columns: em_base["製造登録区分"] = em_base.get("資材消費単位", "ケース")
        if "入数" not in em_base.columns: em_base["入数"] = em_base.get("入数(袋/cs)", 10)
        if "甲消費数" not in em_base.columns: em_base["甲消費数"] = em_base.get("甲入数", 4)
        
        _mst_active = ["大カテゴリ","製品名","初期在庫数",
                       "使用資材名","製造登録区分","入数","甲消費数",
                       "時間あたり生産量","歩留まり率","リードタイム時間","安全在庫数","段取りグループ"]
        
        em_show = em_base[[c for c in _mst_active if c in em_base.columns]]
        em = st.data_editor(em_show, num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={
                "大カテゴリ": st.column_config.SelectboxColumn(options=[c.split(" ",1)[1] for c in CATS]),
                "使用資材名": st.column_config.SelectboxColumn(options=pk_m["資材名"].tolist() if not pk_m.empty else []),
                "製造登録区分": st.column_config.SelectboxColumn("製造登録区分", options=["ケース","袋","甲"]),
                "入数": st.column_config.NumberColumn("入数(袋)", min_value=1, step=1, format="%d", help="区分が「袋」の場合：何袋でダンボール1箱になるか"),
                "甲消費数": st.column_config.NumberColumn("甲消費数(枚/甲)", min_value=1, step=1, format="%d", help="区分が「甲」の場合：1甲でダンボールを何箱消費するか"),
                "初期在庫数": st.column_config.NumberColumn(min_value=0, step=1, format="%d"),
                "時間あたり生産量": st.column_config.NumberColumn("生産量(cs/h)", min_value=1, step=1, format="%d"),
                "歩留まり率": st.column_config.NumberColumn("歩留まり(%)", min_value=1, max_value=100, step=1, format="%d"),
                "リードタイム時間": st.column_config.NumberColumn("LT(h)", min_value=0, step=1, format="%d"),
                "安全在庫数": st.column_config.NumberColumn("安全在庫(cs)", min_value=0, step=1, format="%d"),
                "段取りグループ": st.column_config.TextColumn("段取りG"),
            }, height=500, key="prod_mst_ed")
        _m1_msg = st.empty()
        if st.button("💾 製品マスタ保存", type="primary", key="btn_save_prod_mst"):
            try:
                save_target = em.copy() 

                missing_cols = [c for c in mst.columns if c not in save_target.columns]
                if not mst.empty and missing_cols:
                    save_target = pd.merge(save_target, mst[["製品名"] + missing_cols], on="製品名", how="left")
                for c in missing_cols:
                    if c not in save_target.columns:
                        save_target[c] = ""

                numeric_cols = ["初期在庫数", "時間あたり生産量", "歩留まり率", "リードタイム時間", "安全在庫数", "入数", "甲消費数", "最小製造ロット"]
                for col in numeric_cols:
                    if col in save_target.columns:
                        save_target[col] = pd.to_numeric(save_target[col], errors='coerce').fillna(0).astype(int)

                save_target["製造登録区分"] = save_target["製造登録区分"].replace(["", None], "ケース")
                save_target["大カテゴリ"] = save_target["大カテゴリ"].replace(["", None], "その他")

                save_sync("master", save_target)
                
                flash("success", "✅ 製品マスタを保存しました。")
                st.rerun()
            except Exception as e:
                st.error(f"保存失敗: {e}")
                st.exception(e)
    with tm2:
        ec = st.data_editor(cdf.copy(), num_rows="dynamic", use_container_width=True, hide_index=True, key="cust_mst_ed")
        _m2_msg = st.empty()
        if st.button("💾 顧客マスタ保存", type="primary", key="btn_save_cust_mst"): save_sync("customers", ec); flash("success", "✅ 顧客マスタを保存しました。"); st.rerun()
        show_flash_inline(_m2_msg)
    with tm3:
        if "管理区分" not in pk_m.columns: pk_m["管理区分"] = "定期発注(自動)"
        ep = st.data_editor(pk_m.copy(), num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={
                "管理区分": st.column_config.SelectboxColumn("管理区分", options=["定期発注(自動)", "都度発注(受注連動)"]),
                "初期在庫": st.column_config.NumberColumn(min_value=0, step=1, format="%d"),
                "発注点": st.column_config.NumberColumn(min_value=0, step=1, format="%d"),
                "発注リードタイム": st.column_config.NumberColumn(min_value=1, step=1, format="%d"),
            }, key="pack_mst_ed"
        )
        _m3_msg = st.empty()
        if st.button("💾 資材マスタ保存", type="primary", key="btn_save_pack_mst"): 
            save_sync("packaging_master", ep)
            flash("success", "✅ 資材マスタを保存しました。")
            st.rerun()
        show_flash_inline(_m3_msg)
    with tm4:
        es = st.data_editor(sh_m.copy(), num_rows="dynamic", use_container_width=True, hide_index=True, key="ship_mst_ed")
        _m4_msg = st.empty()
        if st.button("💾 運送会社保存", type="primary", key="btn_save_ship_mst"): save_sync("shipping_master", es); flash("success", "✅ 運送会社マスタを保存しました。"); st.rerun()
        show_flash_inline(_m4_msg)

