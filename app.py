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
        for c in cols:
            if c not in df.columns: df[c] = ""
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
# ★ 共通在庫計算エンジン（リアルタイム現在庫＆未来予測用）
# ─────────────────────────────────────────────
today = pd.Timestamp.today().normalize()
dates = pd.date_range(today, today + timedelta(days=30))
current_stocks = {}
all_ev = pd.DataFrame()

if not master_df.empty:
    o_ev = orders_df[["納品予定日", "製品名", "ケース数"]].copy() if not orders_df.empty else pd.DataFrame(columns=["納品予定日", "製品名", "ケース数"])
    if not o_ev.empty:
        o_ev = o_ev.rename(columns={"納品予定日":"日付", "ケース数":"qty"})
        o_ev["qty"] = -pd.to_numeric(o_ev["qty"], errors='coerce').fillna(0)
    
    m_ev = manus_df[["製造予定日", "製品名", "ケース数"]].copy() if not manus_df.empty else pd.DataFrame(columns=["製造予定日", "製品名", "ケース数"])
    if not m_ev.empty:
        m_ev = m_ev.rename(columns={"製造予定日":"日付", "ケース数":"qty"})
        m_ev["qty"] = pd.to_numeric(m_ev["qty"], errors='coerce').fillna(0)
    
    all_ev = pd.concat([o_ev, m_ev]).dropna(subset=["製品名", "日付"])
    past_ev = all_ev[all_ev["日付"] < today].groupby("製品名")["qty"].sum()
    
    for _, r in master_df.iterrows():
        p = r["製品名"]
        p_past = int(past_ev.get(p, 0))
        curr_stock = int(r.get("初期在庫数", 0)) + p_past
        current_stocks[p] = curr_stock

# ─────────────────────────────────────────────
# 6. サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<p style='font-size:20px; font-weight:900; color:#1E3A8A; margin-bottom:20px;'>🏭 丸実屋システム</p>", unsafe_allow_html=True)
    st.write("---")
    # 【追加機能1】 「📑 登録一覧・編集」メニューの追加
    menu_items = ["📋 受注登録", "🏭 製造登録", "📑 登録一覧・編集", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"]
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
        qty = c3.number_input("📦 ケース数", min_value=1, value=None, placeholder="数字...")
        cat_full = st.pills("カテゴリ", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
        cat = cat_full.split(" ", 1)[1] if cat_full else CATEGORIES[0].split(" ", 1)[1]
        
        sc1, sc2 = st.columns([1.5, 2.5])
        search_p = sc1.text_input("🔍 製品検索", placeholder="名称の一部を入力...")
        prods = [p for p in master_df["製品名"].tolist() if search_p in p] if search_p else (master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist() if not master_df.empty else [])
        prod = sc2.selectbox("確定製品", options=prods, index=None, placeholder="選択してください", format_func=format_name)
        rem = sc2.text_input("📝 備考")
        
        # 【追加機能4】 代替品チェックボックス
        is_substitute = sc2.checkbox("🔄 代替品として送付", help="チェックすると備考欄に自動で【代替品送付】と付与されます")
        
        st.write("---")

        # 【追加機能2】 リアルタイム在庫不足アラート
        if prod and qty:
            cur_stock = current_stocks.get(prod, 0)
            if cur_stock < qty:
                st.warning(f"⚠️ 在庫が不足します（現在庫: **{cur_stock}** cs / 不足: **{qty - cur_stock}** cs）", icon="🚨")

        submit_btn = st.button("✅ 受注を登録する", type="primary", use_container_width=True)
        msg_slot = st.empty()

        if submit_btn:
            if not prod or not qty: 
                msg_slot.error("⚠️ 【製品・ケース数】は必須です。")
            else:
                final_rem = f"【代替品送付】 {rem}".strip() if is_substitute else rem
                new_row = pd.DataFrame([{
                    "ID": str(uuid.uuid4())[:6].upper(), 
                    "納品予定日": pd.to_datetime(o_date), 
                    "顧客名": c_name if c_name else "未指定", 
                    "大カテゴリ": cat, 
                    "製品名": prod, 
                    "ケース数": int(qty), 
                    "備考": final_rem, 
                    "登録日時": datetime.now()
                }])
                append_and_sync("orders", new_row)
                st.session_state.success_msg = f"✨ 登録完了：{prod}"
                st.rerun()

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

# 【追加機能1】 --- 📑 登録一覧・編集 ---
elif page == "📑 登録一覧・編集":
    st.markdown('<div class="slim-header" style="background: linear-gradient(135deg, #0F766E 0%, #14B8A6 100%);"><h1>📑 登録一覧・データ編集</h1></div>', unsafe_allow_html=True)
    
    if orders_df.empty:
        st.info("登録データがありません。")
    else:
        # 新しい順に並び替え
        edit_df = orders_df.sort_values("登録日時", ascending=False).copy()
        edit_df["納品予定日"] = edit_df["納品予定日"].dt.date
        
        # 必要な列だけを整理
        cols = ["ID", "登録日時", "大カテゴリ", "顧客名", "納品予定日", "製品名", "ケース数", "備考"]
        edit_df = edit_df[[c for c in cols if c in edit_df.columns]]
        
        # 在庫不足アラート（Styler用関数）
        def highlight_shortage(row):
            is_short = False
            try:
                # ケース数が現在庫を上回る場合は赤字警告
                if int(row["ケース数"]) > current_stocks.get(row["製品名"], 0):
                    is_short = True
            except: pass
            # 在庫不足の行を丸ごと赤背景・赤文字に
            color = 'background-color: #FEE2E2; color: #DC2626; font-weight: bold;' if is_short else ''
            return [color] * len(row)

        st.markdown("※数量が現在庫を上回る（在庫不足）行は<span style='color:red;font-weight:bold;'>赤色</span>で強調表示されます。<br>※エクセル感覚で直接書き換えた後、下部の「💾 修正を保存」ボタンを押してください。", unsafe_allow_html=True)
        
        edited = st.data_editor(
            edit_df.style.apply(highlight_shortage, axis=1),
            use_container_width=True,
            hide_index=True,
            height=600,
            column_config={
                "ID": None, # バックエンド管理用（非表示）
                "登録日時": None,
                "大カテゴリ": None,
                "納品予定日": st.column_config.DateColumn("納品日", format="YYYY-MM-DD"),
                "ケース数": st.column_config.NumberColumn("ケース数", min_value=1)
            },
            key="edit_all_orders"
        )
        
        if st.button("💾 修正を保存", type="primary", use_container_width=True):
            save_and_sync("orders", edited)
            st.success("✅ 全データを更新しました！")
            st.rerun()

# --- 📦 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="slim-header"><h1>📦 在庫予測 ＆ 週間カレンダー</h1></div>', unsafe_allow_html=True)
    t1, t2, t3 = st.tabs(["📉 1ヶ月在庫予測", "📅 週間カレンダー", "🔍 製品別詳細ビュー"]) # 【追加機能3】タブ追加
    
    with t1:
        if master_df.empty: st.info("製品マスタが空です。")
        else:
            future_ev = all_ev[all_ev["日付"] >= today]
            if not future_ev.empty:
                pivot_ev = future_ev.pivot_table(index="製品名", columns="日付", values="qty", aggfunc="sum").reindex(columns=dates, fill_value=0)
            else:
                pivot_ev = pd.DataFrame(0, index=master_df["製品名"].unique(), columns=dates)
            
            inv_list = []
            for _, r in master_df.iterrows():
                p = r["製品名"]
                curr_stock = current_stocks.get(p, 0)
                p_future_row = pivot_ev.loc[p] if p in pivot_ev.index else pd.Series(0, index=dates)
                p_future_cumsum = p_future_row.fillna(0).cumsum()
                
                row = {"カテゴリ": r["大カテゴリ"], "製品名": format_name(p), "現在庫": curr_stock}
                for d in dates:
                    try: val = int(curr_stock + p_future_cumsum.get(d, 0))
                    except: val = int(curr_stock)
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
        html = '<table class="sched-table"><tr><th style="width:100px;">日付</th><th style="width:45%;">製造</th><th style="width:45%;">出荷</th></tr>'
        for i in range(7):
            d = today + timedelta(days=i)
            m_h = "".join([f'<div style="background:#F0FFF4; border-left:4px solid #10B981; padding:6px; margin-bottom:4px; border-radius:4px;"><span style="font-weight:700;">{format_name(r["製品名"])}</span> <span style="float:right; font-weight:900; color:#059669;">{int(r["ケース数"])}cs</span></div>' for _,r in manus_df[manus_df["製造予定日"]==d].iterrows()]) if not manus_df.empty else ""
            o_h = "".join([f'<div style="background:#F0F7FF; border-left:4px solid #2563EB; padding:6px; margin-bottom:4px; border-radius:4px;"><span style="font-weight:700;">{r["顧客名"]}: {format_name(r["製品名"])}</span> <span style="float:right; font-weight:900; color:#1D4ED8;">{int(r["ケース数"])}cs</span></div>' for _,r in orders_df[orders_df["納品予定日"]==d].iterrows()]) if not orders_df.empty else ""
            html += f'<tr><td><b>{d.strftime("%m/%d")}</b><br>{["月","火","水","木","金","土","日"][d.dayofweek]}曜</td><td>{m_h}</td><td>{o_h}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)

    # 【追加機能3】 製品別詳細ビュー
    with t3:
        st.markdown('### 🔍 製品別 在庫推移と詳細スケジュール')
        if master_df.empty:
            st.info("製品が登録されていません。")
        else:
            sel_prod = st.selectbox("対象製品を選択してください", options=sorted(master_df["製品名"].tolist()), format_func=format_name, index=None, placeholder="製品を選ぶ...")
            
            if sel_prod:
                prod_cur_stock = current_stocks.get(sel_prod, 0)
                
                # 出荷と製造の未来データを抽出
                p_o_ev = orders_df[(orders_df["製品名"] == sel_prod) & (orders_df["納品予定日"] >= today)][["納品予定日", "顧客名", "ケース数"]] if not orders_df.empty else pd.DataFrame(columns=["納品予定日", "顧客名", "ケース数"])
                p_m_ev = manus_df[(manus_df["製品名"] == sel_prod) & (manus_df["製造予定日"] >= today)][["製造予定日", "備考", "ケース数"]] if not manus_df.empty else pd.DataFrame(columns=["製造予定日", "備考", "ケース数"])
                
                detail_list = []
                temp_stock = prod_cur_stock
                
                for d in dates:
                    # その日の出荷
                    day_o = p_o_ev[p_o_ev["納品予定日"].dt.date == d.date()]
                    out_qty = day_o["ケース数"].sum() if not day_o.empty else 0
                    out_detail = " / ".join([f"{r['顧客名']}({r['ケース数']}cs)" for _, r in day_o.iterrows()]) if not day_o.empty else "-"
                    
                    # その日の製造
                    day_m = p_m_ev[p_m_ev["製造予定日"].dt.date == d.date()]
                    in_qty = day_m["ケース数"].sum() if not day_m.empty else 0
                    in_detail = " / ".join([f"製造({r['ケース数']}cs)" for _, r in day_m.iterrows()]) if not day_m.empty else "-"
                    
                    temp_stock = temp_stock + in_qty - out_qty
                    
                    detail_list.append({
                        "日付": d.strftime("%m/%d"),
                        "曜日": ["月","火","水","木","金","土","日"][d.dayofweek],
                        "製造 (入)": in_qty,
                        "製造詳細": in_detail,
                        "出荷 (出)": out_qty,
                        "出荷詳細": out_detail,
                        "予定在庫": temp_stock
                    })
                
                df_detail = pd.DataFrame(detail_list)
                
                # 可視化グラフ
                fig = px.line(df_detail, x="日付", y="予定在庫", title=f"【{sel_prod}】 1ヶ月の予定在庫推移", markers=True)
                fig.add_bar(x=df_detail["日付"], y=df_detail["製造 (入)"], name="製造", marker_color="#10B981", opacity=0.6)
                fig.add_bar(x=df_detail["日付"], y=-df_detail["出荷 (出)"], name="出荷", marker_color="#F43F5E", opacity=0.6)
                fig.update_layout(hovermode="x unified", yaxis_title="ケース数", margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig, use_container_width=True)
                
                # 詳細データテーブル
                st.dataframe(
                    df_detail.style.map(lambda x: 'color: #DC2626; font-weight: bold; background-color: #FEE2E2;' if isinstance(x, int) and x < 0 else '', subset=["予定在庫"]),
                    use_container_width=True, hide_index=True
                )

# --- 📊 統計・分析 ---
elif page == "📊 統計・分析":
    st.markdown('<div class="slim-header" style="background:#4C1D95;"><h1>📊 ABC分析 ＆ 顧客ランキング</h1></div>', unsafe_allow_html=True)
    if not orders_df.empty:
        abc = orders_df.groupby("製品名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False)
        total_sum = abc["ケース数"].sum()
        abc["累計比率"] = abc["ケース数"].cumsum() / total_sum * 100
        abc["ランク"] = pd.cut(abc["累計比率"], bins=[0, 70, 90, 100], labels=["A (主力)", "B (中堅)", "C (その他)"])
        st.dataframe(abc.style.map(lambda v: 'background-color: #FEE2E2; font-weight: 900;' if "A" in str(v) else '', subset=["ランク"]), use_container_width=True, hide_index=True)
        cust_abc = orders_df[orders_df["顧客名"]!="未指定"].groupby("顧客名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False).head(15)
        if not cust_abc.empty:
            st.plotly_chart(px.bar(cust_abc, x="ケース数", y="顧客名", orientation='h', title="主要顧客TOP15"), use_container_width=True)
