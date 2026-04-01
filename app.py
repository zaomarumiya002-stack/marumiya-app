"""
丸実屋 受注・製造・在庫管理アプリ (エラー完全修復・通知位置最適化・安定版)
"""

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
        cols = {"orders":["ID","納品予定日","顧客名","大カテゴリ","製品名","ケース数","備考","登録日時"],
                "manufactures":["ID","製造予定日","備考","大カテゴリ","製品名","ケース数","登録日時"],
                "master":["大カテゴリ","製品名","初期在庫数"],
                "customers":["顧客名","ふりがな"]}[name]
        if len(data) <= 1: return pd.DataFrame(columns=cols)
        df = pd.DataFrame(data[1:], columns=data[0])
        # 足りない列があれば補完 (KeyError防止)
        for c in cols:
            if c not in df.columns: df[c] = ""
        # 型変換
        if "ケース数" in df.columns: df["ケース数"] = pd.to_numeric(df["ケース数"], errors='coerce').fillna(0).astype(int)
        if "初期在庫数" in df.columns: df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors='coerce').fillna(0).astype(int)
        for c in ["納品予定日", "製造予定日", "登録日時"]:
            if c in df.columns: df[c] = pd.to_datetime(df[c], errors='coerce')
        return df[cols]
    except: return pd.DataFrame()

def save_and_sync(name, df):
    ws = sheet.worksheet(name)
    ws.clear()
    df_save = df.copy()
    for col in df_save.columns:
        if pd.api.types.is_datetime64_any_dtype(df_save[col]):
            df_save[col] = df_save[col].dt.strftime('%Y-%m-%d %H:%M:%S').replace('NaT', '')
        elif pd.api.types.is_numeric_dtype(df_save[col]):
            df_save[col] = df_save[col].fillna(0).astype(int).astype(str)
    df_save = df_save.fillna("").astype(str).replace(["nan", "None", "NaT"], "")
    ws.update(values=[df_save.columns.values.tolist()] + df_save.values.tolist(), range_name='A1')
    st.cache_data.clear()
    if name == "orders": st.session_state.orders_df = load_data_from_cloud("orders")
    elif name == "manufactures": st.session_state.manus_df = load_data_from_cloud("manufactures")

def append_and_sync(name, new_row_df):
    row_copy = new_row_df.copy()
    for col in row_copy.columns:
        if pd.api.types.is_datetime64_any_dtype(row_copy[col]):
            row_copy[col] = row_copy[col].dt.strftime('%Y-%m-%d %H:%M:%S').replace('NaT', '')
    row_to_send = row_copy.fillna("").astype(str).replace(["nan", "None", "NaT"], "").values[0].tolist()
    sheet.worksheet(name).append_row(row_to_send)
    st.cache_data.clear()
    if name == "orders": st.session_state.orders_df = pd.concat([st.session_state.orders_df, new_row_df], ignore_index=True)
    elif name == "manufactures": st.session_state.manus_df = pd.concat([st.session_state.manus_df, new_row_df], ignore_index=True)

# ─────────────────────────────────────────────
# 5. セッション初期化
# ─────────────────────────────────────────────
if "orders_df" not in st.session_state: st.session_state.orders_df = load_data_from_cloud("orders")
if "manus_df" not in st.session_state: st.session_state.manus_df = load_data_from_cloud("manufactures")
if "master_df" not in st.session_state: st.session_state.master_df = load_data_from_cloud("master")
if "cust_df" not in st.session_state: st.session_state.cust_df = load_data_from_cloud("customers")
if "current_page" not in st.session_state: st.session_state.current_page = "📋 受注登録"
if "success_msg" not in st.session_state: st.session_state.success_msg = None

orders_df = st.session_state.orders_df
manus_df = st.session_state.manus_df
master_df = st.session_state.master_df
cust_df = st.session_state.cust_df

CATEGORIES = ["🍝 つきこん", "🟫 平こん", "🍜 糸こん・しらたき", "🔺 三角こん", "🟤 玉こん", "🎲 ダイスこん", "🏷️ 短冊", "🇯🇵 国産", "🤲 ちぎりこん", "🏮 大黒屋", "🏭 かねこ", "❄️ 冷凍耐性", "📦 その他"]

def format_name(name):
    if not name: return ""
    n = str(name)
    return f"⚫️ {n}" if "黒" in n else f"⚪️ {n}" if "白" in n else f"📦 {n}"

# ─────────────────────────────────────────────
# 6. サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<p style='font-size:20px; font-weight:900; color:#1E3A8A; margin-bottom:20px;'>🏭 丸実屋システム</p>", unsafe_allow_html=True)
    st.write("---")
    for item in ["📋 受注登録", "🏭 製造登録", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"]:
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
        qty = c3.number_input("📦 ケース数", min_value=1, value=None, placeholder="数字...")
        cat_full = st.pills("カテゴリ", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
        cat = cat_full.split(" ", 1)[1] if cat_full else CATEGORIES[0].split(" ", 1)[1]
        
        sc1, sc2 = st.columns([1.5, 2.5])
        search_p = sc1.text_input("🔍 製品検索", placeholder="名称の一部を入力...")
        prods = [p for p in master_df["製品名"].tolist() if search_p in p] if search_p else (master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist() if not master_df.empty else [])
        prod = sc2.selectbox("確定製品", options=prods, index=None, placeholder="選択してください", format_func=format_name)
        rem = sc2.text_input("📝 備考")
        
        # ★ 登録完了通知をボタンの下に配置するためのプレースホルダー
        submit_btn = st.button("✅ 受注を登録する", type="primary", use_container_width=True)
        msg_slot = st.empty()

        if submit_btn:
            if not prod or not qty: 
                msg_slot.error("⚠️ 【製品・ケース数】は必須です。")
            else:
                new_row = pd.DataFrame([{"ID": str(uuid.uuid4())[:6].upper(), "納品予定日": pd.to_datetime(o_date), "顧客名": c_name if c_name else "未指定", "大カテゴリ": cat, "製品名": prod, "ケース数": int(qty), "備考": rem, "登録日時": datetime.now()}])
                append_and_sync("orders", new_row)
                st.session_state.success_msg = f"✨ 登録完了：{prod}"
                st.rerun()

        # rerun後にメッセージを表示
        if st.session_state.success_msg:
            msg_slot.success(st.session_state.success_msg)
            st.session_state.success_msg = None

    st.markdown('<h2 style="font-size:18px; margin-top:20px;">✏️ かんたん修正（直近3件）</h2>', unsafe_allow_html=True)
    if not st.session_state.orders_df.empty:
        recent = st.session_state.orders_df.sort_values("登録日時", ascending=False).head(3).copy()
        recent["納品予定日"] = recent["納品予定日"].dt.date
        edited = st.data_editor(recent, use_container_width=True, hide_index=True, column_config={"納品予定日": st.column_config.DateColumn(format="YYYY-MM-DD"), "登録日時": None}, key="edit_o")
        if st.button("💾 修正保存"):
            others = st.session_state.orders_df[~st.session_state.orders_df["ID"].isin(recent["ID"])]
            save_and_sync("orders", pd.concat([others, edited], ignore_index=True)); st.rerun()

# --- 🏭 製造登録 ---
elif page == "🏭 製造登録":
    st.markdown('<div class="slim-header header-manu"><h1>🏭 製造データ登録</h1></div>', unsafe_allow_html=True)
    with st.container():
        col1, col2 = st.columns([1, 1])
        m_date = col1.date_input("📅 製造日", value=date.today())
        m_qty = col2.number_input("📦 製造ケース数", min_value=1, value=None, placeholder="数字を入力...")
        cat_full_m = st.pills("カテゴリ製造", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
        cat_m = cat_full_m.split(" ", 1)[1] if cat_full_m else CATEGORIES[0].split(" ", 1)[1]
        sc1_m, sc2_m = st.columns([1.5, 2.5])
        search_p_m = sc1_m.text_input("🔍 製品名検索", placeholder="検索...", key="sm")
        prods_m = [p for p in master_df["製品名"].tolist() if search_p_m in p] if search_p_m else (master_df[master_df["大カテゴリ"] == cat_m]["製品名"].tolist() if not master_df.empty else [])
        prod_m = sc2_m.selectbox("確定製品", options=prods_m, index=None, format_func=format_name, key="selm")
        
        # ★ 通知をボタンの下に配置
        m_submit_btn = st.button("➕ 製造を記録する", type="primary", use_container_width=True)
        m_msg_slot = st.empty()

        if m_submit_btn:
            if not prod_m or not m_qty: 
                m_msg_slot.error("⚠️ 【製品・数量】は必須です。")
            else:
                new_row = pd.DataFrame([{"ID": str(uuid.uuid4())[:6].upper(), "製造予定日": pd.to_datetime(m_date), "備考": "", "大カテゴリ": cat_m, "製品名": prod_m, "ケース数": int(m_qty), "登録日時": datetime.now()}])
                append_and_sync("manufactures", new_row)
                st.session_state.success_msg = f"✨ 登録完了：{prod_m}"
                st.rerun()
        
        if st.session_state.success_msg:
            m_msg_slot.success(st.session_state.success_msg)
            st.session_state.success_msg = None

    st.markdown('<h2 style="font-size:18px; margin-top:20px;">✏️ かんたん修正（直近3件）</h2>', unsafe_allow_html=True)
    if not st.session_state.manus_df.empty:
        recent_m = st.session_state.manus_df.sort_values("登録日時", ascending=False).head(3).copy()
        recent_m["製造予定日"] = recent_m["製造予定日"].dt.date
        edited_m = st.data_editor(recent_m, use_container_width=True, hide_index=True, column_config={"製造予定日": st.column_config.DateColumn(format="YYYY-MM-DD"), "登録日時": None}, key="edit_m")
        if st.button("💾 修正を保存", key="smb"):
            others_m = st.session_state.manus_df[~st.session_state.manus_df["ID"].isin(recent_m["ID"])]
            save_and_sync("manufactures", pd.concat([others_m, edited_m], ignore_index=True)); st.rerun()

# --- 📦 在庫・スケジュール (エラー修復版) ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="slim-header"><h1>📦 在庫予測 ＆ 週間カレンダー</h1></div>', unsafe_allow_html=True)
    today = pd.Timestamp.today().normalize()
    dates = pd.date_range(today, today + timedelta(days=30))
    t1, t2 = st.tabs(["📉 1ヶ月在庫予測", "📅 週間カレンダー"])
    with t1:
        if master_df.empty: st.info("製品マスタが空です。")
        else:
            # ★ エラーの出ない行列計算エンジン
            o_ev = orders_df[["納品予定日", "製品名", "ケース数"]].rename(columns={"納品予定日":"日付", "ケース数":"qty"}) if not orders_df.empty else pd.DataFrame(columns=["日付", "製品名", "qty"])
            o_ev["qty"] = -o_ev["qty"]
            m_ev = manus_df[["製造予定日", "製品名", "ケース数"]].rename(columns={"製造予定日":"日付", "ケース数":"qty"}) if not manus_df.empty else pd.DataFrame(columns=["日付", "製品名", "qty"])
            all_ev = pd.concat([o_ev, m_ev]).dropna(subset=["製品名", "日付"])
            
            past_ev = all_ev[all_ev["日付"] < today].groupby("製品名")["qty"].sum()
            future_ev = all_ev[all_ev["日付"] >= today]
            # 未来分を製品×日付のピボットへ。存在しない製品もカバー。
            if not future_ev.empty:
                pivot_ev = future_ev.pivot_table(index="製品名", columns="日付", values="qty", aggfunc="sum").reindex(columns=dates, fill_value=0)
            else:
                pivot_ev = pd.DataFrame(0, index=master_df["製品名"].unique(), columns=dates)
            
            inv_list = []
            for _, r in master_df.iterrows():
                p = r["製品名"]
                # 安全な整数計算
                p_past = int(past_ev.get(p, 0))
                curr_stock = int(r.get("初期在庫数", 0)) + p_past
                # 存在チェックをしてからcumsum
                p_future_row = pivot_ev.loc[p] if p in pivot_ev.index else pd.Series(0, index=dates)
                p_future_cumsum = p_future_row.fillna(0).cumsum()
                
                row = {"カテゴリ": r["大カテゴリ"], "製品名": format_name(p), "現在庫": int(curr_stock)}
                for d in dates:
                    # ここの計算で ValueError が出ないように確実に型変換
                    try:
                        val = int(curr_stock + p_future_cumsum.get(d, 0))
                    except:
                        val = int(curr_stock)
                    row[d.strftime("%m/%d")] = val
                inv_list.append(row)
                
            inv_df = pd.DataFrame(inv_list).sort_values("カテゴリ")
            st.dataframe(inv_df.style.map(lambda x: 'color: #dc2626; font-weight: bold; background-color: #fee2e2;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True, height=600)

    with t2:
        cal_data = []
        for i in range(7):
            d = today + timedelta(days=i)
            m_txt = "\n".join([f"製: {r['製品名']} ({r['ケース数']}cs)" for _, r in manus_df[manus_df["製造予定日"]==d].iterrows()]) if not manus_df.empty else ""
            o_txt = "\n".join([f"出: {r['顧客名']} : {r['製品名']} ({r['ケース数']}cs)" for _, r in orders_df[orders_df["納品予定日"]==d].iterrows()]) if not orders_df.empty else ""
            cal_data.append({"日付": d.strftime("%m/%d"), "製造": m_txt, "出荷": o_txt})
        st.download_button("🖨️ カレンダーExcel出力", data=pd.DataFrame(cal_data).to_csv(index=False, encoding="utf-8-sig"), file_name=f"予定_{today.strftime('%Y%m%d')}.csv", type="primary", use_container_width=True)
        MAX_CS = 500
        html = '<table class="sched-table"><tr><th style="width:100px;">日付</th><th style="width:45%;">製造</th><th style="width:45%;">出荷</th></tr>'
        for i in range(7):
            d = today + timedelta(days=i)
            m_h = "".join([f'<div style="background:#F0FFF4; border-left:4px solid #10B981; padding:6px; margin-bottom:4px; border-radius:4px;"><span style="font-weight:700;">{format_name(r["製品名"])}</span> <span style="float:right; font-weight:900; color:#059669;">{int(r["ケース数"])}cs</span></div>' for _,r in manus_df[manus_df["製造予定日"]==d].iterrows()]) if not manus_df.empty else ""
            o_h = "".join([f'<div style="background:#F0F7FF; border-left:4px solid #2563EB; padding:6px; margin-bottom:4px; border-radius:4px;"><span style="font-weight:700;">{r["顧客名"]}: {format_name(r["製品名"])}</span> <span style="float:right; font-weight:900; color:#1D4ED8;">{int(r["ケース数"])}cs</span></div>' for _,r in orders_df[orders_df["納品予定日"]==d].iterrows()]) if not orders_df.empty else ""
            html += f'<tr><td><b>{d.strftime("%m/%d")}</b><br>{["月","火","水","木","金","土","日"][d.dayofweek]}曜</td><td>{m_h}</td><td>{o_h}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)

# 統計・マスタ (KeyError対策済み)
elif page == "📊 統計・分析":
    st.markdown('<div class="slim-header" style="background:#4C1D95;"><h1>📊 ABC分析 ＆ 顧客ランキング</h1></div>', unsafe_allow_html=True)
    if not orders_df.empty:
        abc = orders_df.groupby("製品名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False)
        total_sum = abc["ケース数"].sum()
        abc["累計比率"] = abc["ケース数"].cumsum() / total_sum * 100
        abc["ランク"] = pd.cut(abc["累計比率"], bins=[0, 70, 90, 100], labels=["A (主力)", "B (中堅)", "C (その他)"])
        st.dataframe(abc.style.map(lambda v: 'background-color: #FEE2E2; font-weight: 900;' if "A" in str(v) else '', subset=["ランク"]), use_container_width=True, hide_index=True)
        # 漢字のみリストから集計
        cust_abc = orders_df[orders_df["顧客名"]!="未指定"].groupby("顧客名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False).head(15)
        if not cust_abc.empty:
            st.plotly_chart(px.bar(cust_abc, x="ケース数", y="顧客名", orientation='h', title="主要顧客TOP15"), use_container_width=True)
