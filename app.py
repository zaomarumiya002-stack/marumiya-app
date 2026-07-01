import os
import unicodedata
import re
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

def convert_product_name(df, name_map, col_name="製品名"):
    if df.empty or not name_map:
        return df
    nk_map = {nk(k): v for k, v in name_map.items() if k}
    def _replace(val):
        if pd.isna(val) or not str(val).strip():
            return val
        norm_val = nk(val)
        if norm_val in nk_map:
            return nk_map[norm_val]
        return val
    df[col_name] = df[col_name].apply(_replace)
    return df

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
    r = mst[mst["製品名"].apply(nk) == nk(pn)]
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
cs = {}; fs = {}; nk2name = {}
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
# 在庫計算・資材計算エンジン
# ─────────────────────────────────────────────
if not mst_u.empty:
    _mst_keys = set(mst_u["製品名"].apply(nk))
    nk2name = {nk(p): p for p in mst_u["製品名"]}
    
    # 【1】全履歴データの読み込み（棚卸基準点の判定用）
    ev_o = odf[["登録日時", "納品予定日", "製品名", "ケース数", "備考", "日付未定フラグ", "不良廃棄フラグ"]].copy() if not odf.empty else pd.DataFrame(columns=["登録日時", "納品予定日", "製品名", "ケース数", "備考", "日付未定フラグ", "不良廃棄フラグ"])
    if not ev_o.empty:
        ev_o = ev_o[ev_o["不良廃棄フラグ"] == False]
        ev_o["qty"] = -pd.to_numeric(ev_o["ケース数"], errors='coerce').fillna(0).abs()
        ev_o["日付"] = pd.to_datetime(ev_o["納品予定日"], errors='coerce').dt.date
    
    vm = mdf[~mdf["備考"].fillna("").str.contains("【在庫非反映】")] if not mdf.empty else pd.DataFrame()
    ev_m = vm[["登録日時", "製造予定日", "製品名", "ケース数", "備考"]].copy() if not vm.empty else pd.DataFrame(columns=["登録日時", "製造予定日", "製品名", "ケース数", "備考"])
    if not ev_m.empty:
        ev_m["qty"] = pd.to_numeric(ev_m["ケース数"], errors='coerce').fillna(0).abs()
        ev_m["日付"] = pd.to_datetime(ev_m["製造予定日"], errors='coerce').dt.date
        
    ae = pd.concat([ev_o, ev_m], ignore_index=True)
    if not ae.empty:
        ae["製品名key"] = ae["製品名"].apply(nk)
        ae["登録日時"] = pd.to_datetime(ae["登録日時"], errors='coerce').fillna(pd.Timestamp.min)
    else:
        ae = pd.DataFrame(columns=["製品名key", "日付", "qty", "登録日時", "備考", "日付未定フラグ"])
        
    unmatched_products = []

    for _, r in mst_u.iterrows():
        p = r["製品名"]; pk = nk(p)
        
        hist = ae[ae["製品名key"] == pk].copy() if not ae.empty else pd.DataFrame()
        
        # 【2】最新の「棚卸実数」を検索し、絶対的な基準点とする
        base_stock = to_int(r.get("初期在庫数", 0))
        cutoff_time = pd.Timestamp.min
        
        if not hist.empty:
            inv_records = hist[hist["備考"].astype(str).str.contains("【棚卸実数:", na=False)]
            if not inv_records.empty:
                latest_inv = inv_records.sort_values("登録日時", ascending=False).iloc[0]
                cutoff_time = latest_inv["登録日時"]
                match = re.search(r"【棚卸実数:\s*([0-9\+\-]+)\s*】", str(latest_inv["備考"]))
                if match:
                    base_stock = int(match.group(1))
        
        # 【3】基準点以降のデータのみを抽出（棚卸以前の二重計算を完全に防止）
        if not hist.empty:
            valid_hist = hist[hist["登録日時"] > cutoff_time]
        else:
            valid_hist = pd.DataFrame()
            
        c_s = base_stock
        pc = pd.Series(0, index=dates)
        pend_qty = 0
        
        # 【4】基準点以降のデータから「現在庫」と「未来予測」を組み立てる
        if not valid_hist.empty:
            for _, h_row in valid_hist.iterrows():
                h_date = h_row["日付"]
                q = to_int(h_row["qty"])
                is_undet = h_row.get("日付未定フラグ", False) == True
                
                if is_undet:
                    pend_qty += q
                else:
                    if pd.isna(h_date):
                        continue
                    if h_date < today.date():
                        # 棚卸基準以降〜昨日までの実績は現在庫に合算
                        c_s += q
                    else:
                        # 今日以降の予定は未来予測グラフ(pc)にプロット
                        d_ts = pd.Timestamp(h_date)
                        if d_ts in pc.index:
                            pc[d_ts] += q
                            
        # 今日のスタート在庫（日付未定の確定引当分を差し引く）
        current_actual = c_s + pend_qty
        cs[p] = current_actual
        
        pc = pc.cumsum()
        fs[p] = {d: current_actual + to_int(pc.get(d, 0)) for d in dates}

# ▼▼▼ 資材の予測・発注残・統計計算エンジン ▼▼▼
fd = 90; pf = {}
if not mst_u.empty and not odf.empty:
    mpi = mst_u.set_index("製品名")[["使用資材名","製造登録区分","入数","甲消費数"]].to_dict('index')
    mpi_nk = {nk(k): v for k, v in mpi.items()}
    for _, r in odf.iterrows():
        p, q, dt = str(r.get("製品名","")), to_int(r.get("ケース数",0)), pd.to_datetime(r.get("納品予定日"),errors="coerce")
        p_key = nk(p)
        if pd.isna(dt) or dt.date()<date.today() or dt>today+timedelta(days=fd) or p_key not in mpi_nk: continue
        pn = str(mpi_nk[p_key].get("使用資材名",""))
        kbn = str(mpi_nk[p_key].get("製造登録区分","ケース")).strip()
        nyu = max(1, to_int(mpi_nk[p_key].get("入数",10)))
        kou = max(1, to_int(mpi_nk[p_key].get("甲消費数",4)))
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

    if pm and mq and ipl and not mst_u.empty and nk(pm) in [nk(x) for x in mst_u["製品名"].values]:
        _mrow = mst_u[mst_u["製品名"].apply(nk) == nk(pm)].iloc[0]
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
                if ipl and not mst_u.empty and nk(pm) in [nk(x) for x in mst_u["製品名"].values]:
                    _mrow2 = mst_u[mst_u["製品名"].apply(nk) == nk(pm)].iloc[0]
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
    page_header("📦 資材・入出庫管理")
    t1, t2 = st.tabs(["📊 資材在庫状況", "➕ 入庫・出庫登録"])
    
    with t1:
        if p_sum:
            df_mat = pd.DataFrame.from_dict(p_sum, orient="index").reset_index().rename(columns={"index":"資材名"})
            # 表示用のカラムを整理
            disp_cols = ["資材名", "現在庫", "発注点", "状態", "1日平均消費", "在庫日数", "発注残", "推奨発注点", "仕入先", "保管場所"]
            df_disp = df_mat[[c for c in disp_cols if c in df_mat.columns]].copy()
            
            # 状態に応じて背景色をつける
            st.dataframe(
                df_disp.style.apply(lambda r: [f'background-color:{df_mat.iloc[r.name].get("アラート色", "#ffffff")}'] * len(r), axis=1),
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.info("資材のデータがありません。")

    with t2:
        sec("資材の入出庫・棚卸登録")
        mat_sel = st.selectbox("対象の資材を選択", list(p_sum.keys()) if p_sum else [], index=None)
        in_out = st.radio("処理区分", ["入庫（プラス）", "出庫（マイナス）", "棚卸（実数上書き）"], horizontal=True)
        mqty = st.number_input("数量", min_value=1, step=1)
        mrsn = st.text_input("理由・備考（納品書番号など）")
        
        _mat_msg = st.empty()
        if st.button("💾 登録する", type="primary"):
            if not mat_sel or mqty < 1:
                _mat_msg.error("⚠️ 資材の選択と数量の入力は必須です。")
            else:
                cur_q = p_sum.get(mat_sel, {}).get("現在庫", 0)
                if in_out == "入庫（プラス）":
                    calc_qty = mqty
                    new_q = cur_q + mqty
                elif in_out == "出庫（マイナス）":
                    calc_qty = -mqty
                    new_q = cur_q - mqty
                else: # 棚卸
                    calc_qty = mqty - cur_q
                    new_q = mqty
                    
                app_sync("packaging_logs", pd.DataFrame([{
                    "ID": str(uuid.uuid4())[:6].upper(), "登録日": pd.Timestamp.now(),
                    "資材名": mat_sel, "処理区分": in_out, "数量": calc_qty,
                    "理由": mrsn, "備考": "手動登録", "関連製品名": "",
                    "理論在庫": new_q,
                    "登録日時": datetime.now(JST).replace(tzinfo=None)
                }]))
                flash("success", f"✅ 【{mat_sel}】 {in_out} を登録しました。 現在庫: {cur_q:,} → {new_q:,}")
                st.rerun()
        show_flash_inline(_mat_msg)

# ─────────────────────────────────────────────
# 📑 登録一覧
# ─────────────────────────────────────────────
elif pg == "📑 登録一覧":
    page_header("📑 登録データ一覧")
    t_ord, t_mfg = st.tabs(["📋 受注データ", "🏭 製造データ"])
    
    with t_ord:
        st.markdown('<div class="info-card">💡 登録されたすべての<b>受注・出荷</b>データの一覧です。</div>', unsafe_allow_html=True)
        do = odf.sort_values("登録日時", ascending=False).copy() if not odf.empty else pd.DataFrame()
        st.dataframe(do, use_container_width=True, hide_index=True)
        if not do.empty:
            st.download_button("📥 受注データをCSVでダウンロード", make_csv_bytes(do), "受注データ.csv", "text/csv")
            
    with t_mfg:
        st.markdown('<div class="info-card">💡 登録されたすべての<b>製造</b>データの一覧です。</div>', unsafe_allow_html=True)
        dm = mdf.sort_values("登録日時", ascending=False).copy() if not mdf.empty else pd.DataFrame()
        st.dataframe(dm, use_container_width=True, hide_index=True)
        if not dm.empty:
            st.download_button("📥 製造データをCSVでダウンロード", make_csv_bytes(dm), "製造データ.csv", "text/csv")

# ─────────────────────────────────────────────
# 📊 在庫・スケジュール
# ─────────────────────────────────────────────
elif pg == "📊 在庫・スケジュール":
    page_header("📊 在庫推移・スケジュール")
    
    # 欠品警告
    shortages = [p for p, f in fs.items() if any(v < 0 for v in list(f.values())[:14])]
    if shortages:
        st.markdown(f'<div class="info-card red">🚨 <b>向こう14日間で欠品が予測される製品（{len(shortages)}件）:</b><br>{", ".join(shortages)}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="info-card green">✅ 向こう14日間の欠品予測はありません。</div>', unsafe_allow_html=True)
    
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("📈 製品別 在庫推移グラフ")
        prod = st.selectbox("推移を確認したい製品を選択", list(fs.keys()), index=0 if fs else None, format_func=fn)
        if prod:
            df_f = pd.DataFrame(list(fs[prod].items()), columns=["日付", "予測在庫"])
            fig = px.line(df_f, x="日付", y="予測在庫", markers=True, title=f"【{prod}】 の在庫推移 (向こう60日)")
            fig.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="欠品ライン")
            
            # 安全在庫ライン
            if not mst_u[mst_u["製品名"]==prod].empty:
                ss = to_int(mst_u[mst_u["製品名"]==prod].iloc[0].get("安全在庫数", 0))
                if ss > 0: 
                    fig.add_hline(y=ss, line_dash="dot", line_color="orange", annotation_text="安全在庫")
                    
            st.plotly_chart(fig, use_container_width=True)
            
    with c2:
        st.subheader("📦 現在庫一覧")
        if cs:
            df_cs = pd.DataFrame(list(cs.items()), columns=["製品名", "現在庫数"])
            st.dataframe(df_cs, use_container_width=True, hide_index=True, height=500)

# ─────────────────────────────────────────────
# ⭐ 特注・チャータースケジュール
# ─────────────────────────────────────────────
elif pg == "⭐ 特注・チャータースケジュール":
    page_header("⭐ 特注・チャータースケジュール")
    st.markdown('<div class="info-card badge-special" style="color:#fff;">受注時に「特注」または「チャーター便」として登録された予定の一覧です。</div>', unsafe_allow_html=True)
    if not sp_s.empty:
        st.dataframe(sp_s.sort_values("納品予定日", ascending=True), use_container_width=True, hide_index=True)
    else:
        st.info("現在、特注・チャーターの予定はありません。")

# ─────────────────────────────────────────────
# 📈 経営・分析ダッシュボード
# ─────────────────────────────────────────────
elif pg == "📈 経営・分析ダッシュボード":
    page_header("📈 経営・分析ダッシュボード")
    if not odf.empty:
        df_ana = odf[odf["不良廃棄フラグ"] == False].copy()
        df_ana["月"] = pd.to_datetime(df_ana["納品予定日"], errors="coerce").dt.to_period("M").astype(str)
        
        c1, c2 = st.columns(2)
        with c1:
            agg_m = df_ana.groupby("月")["ケース数"].sum().reset_index()
            fig1 = px.bar(agg_m, x="月", y="ケース数", title="月別 出荷ケース数推移", text_auto=True)
            st.plotly_chart(fig1, use_container_width=True)
            
        with c2:
            agg_p = df_ana.groupby("大カテゴリ")["ケース数"].sum().reset_index()
            fig2 = px.pie(agg_p, values="ケース数", names="大カテゴリ", title="カテゴリ別 出荷割合")
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("分析用のデータがまだありません。")

# ─────────────────────────────────────────────
# ⚙️ マスタ・分析
# ─────────────────────────────────────────────
elif pg == "⚙️ マスタ・分析":
    page_header("⚙️ マスタ管理")
    t1, t2 = st.tabs(["📦 製品マスタ", "🏢 顧客マスタ"])
    
    with t1:
        st.markdown('<div class="info-card">スプレッドシートを開かずに、製品ごとの設定（入数や使用資材など）を直接編集できます。</div>', unsafe_allow_html=True)
        ed_m = st.data_editor(mst, num_rows="dynamic", use_container_width=True, hide_index=True)
        _mst_msg = st.empty()
        if st.button("💾 製品マスタを保存", type="primary"):
            save_sync("master", ed_m)
            flash("success", "✅ 製品マスタを更新しました。"); st.rerun()
        show_flash_inline(_mst_msg)
            
    with t2:
        st.markdown('<div class="info-card">帳合先や支店・店舗の一覧を編集できます。</div>', unsafe_allow_html=True)
        ed_c = st.data_editor(cdf, num_rows="dynamic", use_container_width=True, hide_index=True)
        _c_msg = st.empty()
        if st.button("💾 顧客マスタを保存", type="primary"):
            save_sync("customers", ed_c)
            flash("success", "✅ 顧客マスタを更新しました。"); st.rerun()
        show_flash_inline(_c_msg)
