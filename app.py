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

    # 棚卸実績の判定 (備考欄の「実棚卸数=」または「棚卸」の文字列を全自動でキャッチして絶対値リセット)
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

    # グループ化し、高速にループを回すための製品別辞書作成 (pandasフィルタ排除により超高速化)
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
net_change_by_day = {}

if not pk_l.empty:
    for _, r in pk_l.iterrows():
        dt = pd.to_datetime(r.get("登録日", today), errors="coerce")
        if pd.isna(dt): continue
        if dt.tz is not None: dt = dt.tz_localize(None)
        
        pn = str(r.get("資材名",""))
        q = to_int(r.get("数量",0))
        pt = str(r.get("処理区分",""))
        
        if pn in p_sum:
            if "入庫" in pt:
                p_sum[pn]["入庫"] += q
                net_chg = q
            elif "出庫" in pt or "連動" in pt:
                p_sum[pn]["出庫"] += q
                net_chg = -q
            else:
                net_chg = 0
                
            d_norm = dt.normalize().date()
            net_change_by_day.setdefault(pn, {})
            net_change_by_day[pn].setdefault(d_norm, 0)
            net_change_by_day[pn][d_norm] += net_chg
            
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
        st.session_state._flash = {"type": "success", "msg": "✅ スプレッドシートから最新データを再読込しました。"}
        st.rerun()

pg = st.session_state.current_page
hc = {"📋 受注登録": "#1E3A8A, #3B82F6", "🏭 製造登録": "#064E3B, #10B981", "🚚 出荷・発送管理": "#047857, #34D399", "📦 資材・入出庫": "#B45309, #F59E0B", "📑 登録一覧": "#0F766E, #14B8A6", "📊 在庫・スケジュール": "#1E3A8A, #6366F1", "⭐ 特注・チャータースケジュール": "#5B21B6, #8B5CF6", "📈 経営・分析ダッシュボード": "#0C4A6E, #0EA5E9", "⚙️ マスタ・分析": "#475569, #1E293B"}
def page_header(t):
    st.markdown(f'<div class="page-header" style="background:linear-gradient(135deg,{hc.get(t,"#1E3A8A, #3B82F6")});"><h1>{t}</h1></div>', unsafe_allow_html=True)
    show_flash()
def sec(t): st.markdown(f'<div class="section-title">{t}</div>', unsafe_allow_html=True)
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
                        if not _fm.empty: st.dataframe(_fm.assign(日付=_fm["製造予定日"].apply(format_date_jp))[["日付","顧客名","ケース数","備考"]].sort_values("日付"), hide_index=True, height=220)
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
                "ใช้資材名": st.column_config.SelectboxColumn(options=pk_m["資材名"].tolist() if not pk_m.empty else []),
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
    
