"""
丸実屋 受注・製造・在庫管理アプリ (即時反映完全保証・カレンダーExcel出力版)
"""

import os
# テーマ強制設定
os.environ["STREAMLIT_THEME_BASE"] = "light"
os.environ["STREAMLIT_THEME_PRIMARY_COLOR"] = "#2563EB"
os.environ["STREAMLIT_THEME_BACKGROUND_COLOR"] = "#F8FAFC"
os.environ["STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR"] = "#FFFFFF"
os.environ["STREAMLIT_THEME_TEXT_COLOR"] = "#0F172A"

import streamlit as st
import pandas as pd
import plotly.express as px
import uuid
from datetime import datetime, timedelta, date
import gspread
from google.oauth2.service_account import Credentials
import io

# ─────────────────────────────────────────────
# 1. ページ基本設定
# ─────────────────────────────────────────────
st.set_page_config(page_title="丸実屋 受注・在庫管理", page_icon="🏭", layout="wide", initial_sidebar_state="expanded")

# ─────────────────────────────────────────────
# 2. CSS (巨大ボタン・コンパクトレイアウト)
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&display=swap');
    html, body, [data-testid="stAppViewContainer"] { font-family: 'Noto Sans JP', sans-serif !important; font-size: 16px !important; }
    p, span, label, div { color: #0F172A !important; }

    /* サイドバー */
    [data-testid="stSidebar"] { background-color: #F8FAFC !important; border-right: 1px solid #E2E8F0; }
    [data-testid="stSidebar"] .stButton > button { height: 50px !important; font-size: 16px !important; border-radius: 10px !important; }

    /* ヘッダー */
    .block-container { padding-top: 1rem !important; }
    .slim-header { background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%); padding: 12px 24px; border-radius: 10px; color: white !important; margin-bottom: 16px; }
    .slim-header h1 { color: white !important; margin: 0 !important; font-size: 24px !important; }

    /* カテゴリ巨大ボタン */
    [data-testid="stPills"] button { padding: 14px 28px !important; font-size: 18px !important; font-weight: 800 !important; border-radius: 12px !important; border: 2px solid #CBD5E1 !important; margin: 4px !important; }
    [data-testid="stPills"] button[aria-selected="true"] { background-color: #2563EB !important; color: #FFFFFF !important; border-color: #2563EB !important; box-shadow: 0 4px 10px rgba(37, 99, 235, 0.3) !important; }

    /* スケジュール表 */
    .sched-table { width: 100%; border-collapse: collapse; background: white; font-size: 15px; border-radius: 10px; overflow: hidden; }
    .sched-table th { background: #F8FAFC; padding: 10px; border-bottom: 2px solid #E2E8F0; }
    .sched-table td { padding: 10px; border-bottom: 1px solid #F1F5F9; vertical-align: top; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. 認証
# ─────────────────────────────────────────────
def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            pwd = st.text_input("パスワードを入力", type="password")
            if st.button("ログイン", use_container_width=True, type="primary"):
                if pwd == st.secrets["app_password"]: st.session_state["password_correct"] = True; st.rerun()
                else: st.error("❌ 違います")
        st.stop()
check_password()

# ─────────────────────────────────────────────
# 4. スプレッドシート連携（確実な同期ロジック）
# ─────────────────────────────────────────────
@st.cache_resource
def get_client():
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

client = get_client()
sheet = client.open_by_url(st.secrets["spreadsheet_url"])

@st.cache_data(ttl=600)
def load_data(name):
    try:
        ws = sheet.worksheet(name)
        data = ws.get_all_values()
        cols = {"orders":["ID","納品予定日","顧客名","大カテゴリ","製品名","ケース数","備考","登録日時"],
                "manufactures":["ID","製造予定日","備考","大カテゴリ","製品名","ケース数","登録日時"],
                "master":["大カテゴリ","製品名","初期在庫数"],
                "customers":["顧客名","ふりがな"]}[name]
        if len(data) <= 1: return pd.DataFrame(columns=cols)
        df = pd.DataFrame(data[1:], columns=data[0])
        if "ケース数" in df.columns: df["ケース数"] = pd.to_numeric(df["ケース数"], errors='coerce').fillna(0).astype(int)
        if "初期在庫数" in df.columns: df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors='coerce').fillna(0).astype(int)
        for c in ["納品予定日", "製造予定日", "登録日時"]:
            if c in df.columns: df[c] = pd.to_datetime(df[c], errors='coerce')
        return df
    except: return pd.DataFrame()

def save_data(name, df):
    ws = sheet.worksheet(name)
    ws.clear()
    df_str = df.fillna("").astype(str)
    ws.update(values=[df_str.columns.values.tolist()] + df_str.values.tolist(), range_name='A1')
    st.cache_data.clear()

def append_row(name, row_data):
    sheet.worksheet(name).append_row(row_data)
    st.cache_data.clear() # キャッシュを破棄
    load_data(name) # ★【バグ修正】即座に再読み込みを行い、確実に最新データにする

# ─────────────────────────────────────────────
# 5. マスタ ＆ 便利関数
# ─────────────────────────────────────────────
CATEGORIES = ["🍝 つきこん", "🟫 平こん", "🍜 糸こん・しらたき", "🔺 三角こん", "🟤 玉こん", "🎲 ダイスこん", "🏷️ 短冊", "🇯🇵 国産", "🤲 ちぎりこん", "🏮 大黒屋", "🏭 かねこ", "❄️ 冷凍耐性", "📦 その他"]

def format_name(name):
    if not name: return ""
    n = str(name)
    return f"⚫️ {n}" if "黒" in n else f"⚪️ {n}" if "白" in n else f"📦 {n}"

# データロード（常に最新）
orders_df = load_data("orders")
manus_df = load_data("manufactures")
master_df = load_data("master")
cust_df = load_data("customers")

if "success_msg" not in st.session_state: st.session_state.success_msg = None
if "current_page" not in st.session_state: st.session_state.current_page = "📋 受注登録"
def change_page(pname): st.session_state.current_page = pname

# ─────────────────────────────────────────────
# 6. サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<p style='font-size:22px; font-weight:900; color:#1E3A8A; margin-bottom:20px;'>🏭 丸実屋システム</p>", unsafe_allow_html=True)
    st.write("---")
    menu_items = ["📋 受注登録", "🏭 製造登録", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"]
    for item in menu_items:
        is_active = st.session_state.current_page == item
        if st.button(item, key=f"menu_{item}", use_container_width=True, type="primary" if is_active else "secondary"):
            change_page(item); st.rerun()

page = st.session_state.current_page

# ─────────────────────────────────────────────
# 7. 各画面描画
# ─────────────────────────────────────────────

# --- 📋 受注登録 ---
if page == "📋 受注登録":
    st.markdown('<div class="slim-header"><h1>📋 受注（出荷予定）登録</h1></div>', unsafe_allow_html=True)
    with st.container():
        c1, c2, c3 = st.columns([1, 2, 1])
        o_date = c1.date_input("📅 納品日", value=date.today() + timedelta(days=1))
        cust_list = sorted(cust_df["顧客名"].unique().tolist()) if not cust_df.empty else []
        c_name = c2.selectbox("🏢 顧客名（検索）", options=cust_list, index=None, placeholder="空欄（クリックして検索）")
        qty = c3.number_input("📦 ケース数", min_value=1, value=None, step=1, placeholder="数字...")

        cat_full = st.pills("カテゴリ", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
        cat = cat_full.split(" ", 1)[1] if cat_full else CATEGORIES[0].split(" ", 1)[1]
        
        sc1, sc2 = st.columns([1.5, 2])
        search_p = sc1.text_input("🔍 製品名検索", placeholder="名称の一部を入力...")
        prods = [p for p in master_df["製品名"].tolist() if search_p in p] if search_p else (master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist() if not master_df.empty else [])
        prod = sc2.selectbox("確定製品", options=prods, index=None, placeholder="製品を選んでください", format_func=format_name)
        rem = st.text_input("📝 備考（任意）", placeholder="備考を入力...")
        
        st.markdown('<div style="margin-top: 15px;"></div>', unsafe_allow_html=True)
        if st.button("✅ 受注を登録する", type="primary", use_container_width=True):
            if not prod or not qty: st.error("⚠️ 製品とケース数は必須です")
            else:
                row = [str(uuid.uuid4())[:6].upper(), o_date.strftime('%Y-%m-%d'), c_name if c_name else "未指定", cat, prod, int(qty), rem, datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                append_row("orders", row)
                st.session_state.success_msg = f"✅ 登録完了： {o_date.strftime('%m/%d')} ｜ {c_name if c_name else '未指定'} ｜ {prod}"
                st.rerun()

        if st.session_state.success_msg:
            st.success(st.session_state.success_msg); st.session_state.success_msg = None

    st.markdown('<h2 style="font-size:18px; margin-top:20px;">✏️ かんたん修正（直近3件）</h2>', unsafe_allow_html=True)
    if not orders_df.empty:
        # ★【バグ修正】 最新データを確実に表示
        recent = orders_df.sort_values("登録日時", ascending=False).head(3).copy()
        recent["納品予定日"] = recent["納品予定日"].dt.date
        edited = st.data_editor(recent, use_container_width=True, hide_index=True, column_config={"納品予定日": st.column_config.DateColumn(format="YYYY-MM-DD"), "登録日時": None}, key="edit_o")
        if st.button("💾 修正内容を保存する"):
            others = orders_df[~orders_df["ID"].isin(recent["ID"])]
            save_data("orders", pd.concat([others, edited], ignore_index=True)); st.rerun()

# --- 🏭 製造登録 ---
elif page == "🏭 製造登録":
    st.markdown('<div class="slim-header" style="background:linear-gradient(135deg, #064E3B 0%, #10B981 100%);"><h1>🏭 製造データの登録</h1></div>', unsafe_allow_html=True)
    with st.container():
        col1, col2 = st.columns([1, 1])
        m_date = col1.date_input("📅 製造日", value=date.today())
        m_qty = col2.number_input("📦 製造ケース数", min_value=1, value=None, placeholder="数字...")
        
        cat_full_m = st.pills("カテゴリ製造", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
        cat_m = cat_full_m.split(" ", 1)[1] if cat_full_m else CATEGORIES[0].split(" ", 1)[1]

        sc1_m, sc2_m = st.columns([1.5, 2])
        search_p_m = sc1_m.text_input("🔍 製品名検索", placeholder="名称の一部...", key="sm")
        prods_m = [p for p in master_df["製品名"].tolist() if search_p_m in p] if search_p_m else (master_df[master_df["大カテゴリ"] == cat_m]["製品名"].tolist() if not master_df.empty else [])
        prod_m = sc2_m.selectbox("確定製品", options=prods_m, index=None, placeholder="選択してください", format_func=format_name, key="selm")
        
        st.markdown('<div style="margin-top: 15px;"></div>', unsafe_allow_html=True)
        if st.button("➕ 製造を記録する", type="primary", use_container_width=True):
            if not prod_m or not m_qty: st.error("⚠️ 製品と数量は必須です")
            else:
                row_m = [str(uuid.uuid4())[:6].upper(), m_date.strftime('%Y-%m-%d'), "", cat_m, prod_m, int(m_qty), datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                append_row("manufactures", row_m)
                st.session_state.success_msg = f"✅ 登録完了：{prod_m}"; st.rerun()
        if st.session_state.success_msg: st.success(st.session_state.success_msg); st.session_state.success_msg = None

    st.markdown('<h2 style="font-size:18px; margin-top:20px;">✏️ かんたん修正（直近3件）</h2>', unsafe_allow_html=True)
    if not manus_df.empty:
        recent_m = manus_df.sort_values("登録日時", ascending=False).head(3).copy()
        recent_m["製造予定日"] = recent_m["製造予定日"].dt.date
        edited_m = st.data_editor(recent_m, use_container_width=True, hide_index=True, column_config={"製造予定日": st.column_config.DateColumn(format="YYYY-MM-DD"), "登録日時": None}, key="edit_m")
        if st.button("💾 修正を保存", key="smb"):
            others_m = manus_df[~manus_df["ID"].isin(recent_m["ID"])]
            save_data("manufactures", pd.concat([others_m, edited_m], ignore_index=True)); st.rerun()

# --- 📦 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="slim-header"><h1>📦 在庫予測とカレンダー</h1></div>', unsafe_allow_html=True)
    today = pd.Timestamp.today().normalize()
    dates = pd.date_range(today, today + timedelta(days=30))
    
    t1, t2 = st.tabs(["📅 週間カレンダー (A3印刷・Excel出力)", "📉 1ヶ月在庫予測マトリクス"])
    
    with t1:
        # ★ 【新機能】A3印刷や壁貼りに使える「週間カレンダー（マトリクス形式）」のExcel出力
        st.write("📥 **印刷・掲示用 週間カレンダーのダウンロード**")
        cal_data = []
        for i in range(7):
            d = today + timedelta(days=i)
            d_str = d.strftime("%m/%d") + ["(月)","(火)","(水)","(木)","(金)","(土)","(日)"][d.dayofweek]
            
            m_items = manus_df[manus_df["製造予定日"] == d] if not manus_df.empty else pd.DataFrame()
            o_items = orders_df[orders_df["納品予定日"] == d] if not orders_df.empty else pd.DataFrame()
            
            # Excelに出力する用の見やすい文字列を作成
            m_txt = "\n".join([f"【製造】{r['製品名']} : {r['ケース数']}cs" for _, r in m_items.iterrows()])
            o_txt = "\n".join([f"【出荷】{r['顧客名']} : {r['製品名']} : {r['ケース数']}cs" for _, r in o_items.iterrows()])
            
            cal_data.append({"日付": d_str, "製造予定 (入庫)": m_txt, "出荷予定 (出庫)": o_txt})
        
        cal_df = pd.DataFrame(cal_data)
        csv_cal = cal_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("🖨️ 週間カレンダーをダウンロード (Excel対応CSV)", data=csv_cal, file_name=f"週間カレンダー_{today.strftime('%Y%m%d')}.csv", type="primary", use_container_width=True)
        
        st.write("---")
        html = '<table class="sched-table"><tr><th style="width:100px;">日付</th><th style="width:45%;">製造</th><th style="width:45%;">出荷</th></tr>'
        for i in range(7):
            d = today + timedelta(days=i)
            m_items = manus_df[manus_df["製造予定日"] == d] if not manus_df.empty else pd.DataFrame()
            o_items = orders_df[orders_df["納品予定日"] == d] if not orders_df.empty else pd.DataFrame()
            m_h = "".join([f'<div style="background:#F0FFF4; border-left:4px solid #10B981; padding:6px; margin-bottom:4px; border-radius:4px;"><span style="font-weight:700;">{format_name(r["製品名"])}</span> <span style="float:right; font-weight:900; color:#059669;">{r["ケース数"]}cs</span></div>' for _,r in m_items.iterrows()])
            o_h = "".join([f'<div style="background:#F0F7FF; border-left:4px solid #2563EB; padding:6px; margin-bottom:4px; border-radius:4px;"><span style="font-weight:700;">{r["顧客名"]}: {format_name(r["製品名"])}</span> <span style="float:right; font-weight:900; color:#1D4ED8;">{r["ケース数"]}cs</span></div>' for _,r in o_items.iterrows()])
            html += f'<tr><td><b>{d.strftime("%m/%d")}</b><br>{["月","火","水","木","金","土","日"][d.dayofweek]}曜</td><td>{m_h}</td><td>{o_h}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)

    with t2:
        st.write("💡 30日先までの在庫予測です。マイナス（欠品）になる日は赤く強調されます。")
        if not master_df.empty:
            o_tmp = orders_df[["納品予定日", "製品名", "ケース数"]].copy() if not orders_df.empty else pd.DataFrame(columns=["納品予定日", "製品名", "ケース数"])
            m_tmp = manus_df[["製造予定日", "製品名", "ケース数"]].copy() if not manus_df.empty else pd.DataFrame(columns=["製造予定日", "製品名", "ケース数"])
            o_tmp.columns, m_tmp.columns = ["日付", "製品名", "変動"], ["日付", "製品名", "変動"]
            o_tmp["変動"] = -o_tmp["変動"]
            
            events = pd.concat([o_tmp, m_tmp]).dropna(subset=["製品名"])
            if not events.empty:
                events["日付"] = pd.to_datetime(events["日付"]).dt.normalize()
                
                inv_list = []
                for _, m in master_df.iterrows():
                    p = m["製品名"]
                    curr = int(m["初期在庫数"])
                    p_events = events[events["製品名"] == p]
                    curr += p_events[p_events["日付"] < today]["変動"].sum()
                    row = {"カテゴリ": m["大カテゴリ"], "製品名": format_name(p), "現在庫": curr}
                    future = p_events[p_events["日付"] >= today].groupby("日付")["変動"].sum()
                    
                    temp_stk = curr
                    for d in dates:
                        temp_stk += future.get(d, 0)
                        row[d.strftime("%m/%d")] = temp_stk
                    inv_list.append(row)
                
                inv_df = pd.DataFrame(inv_list).sort_values("カテゴリ")
                st.dataframe(inv_df.style.map(lambda x: 'color: #dc2626; font-weight: 900; background-color: #fee2e2;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True, height=600)

# --- 統計・分析 (ABC分析実装) ---
elif page == "📊 統計・分析":
    st.markdown('<div class="slim-header" style="background:linear-gradient(135deg, #4C1D95 0%, #8B5CF6 100%);"><h1>📊 統計・ABC分析ダッシュボード</h1></div>', unsafe_allow_html=True)
    if not orders_df.empty:
        t1, t2 = st.tabs(["🏆 顧客・カテゴリ分析", "🥇 製品ABC分析 (出荷量ランク)"])
        with t1:
            col1, col2 = st.columns(2)
            orders_df["年月"] = orders_df["納品予定日"].dt.strftime("%Y-%m")
            col1.plotly_chart(px.bar(orders_df.groupby(["年月","大カテゴリ"])["ケース数"].sum().reset_index(), x="年月", y="ケース数", color="大カテゴリ", barmode="stack", title="出荷トレンド"), use_container_width=True)
            col2.plotly_chart(px.bar(orders_df[orders_df["顧客名"]!="未指定"].groupby("顧客名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False).head(15), x="ケース数", y="顧客名", orientation='h', title="主要顧客TOP15"), use_container_width=True)
        with t2:
            st.write("💡 **ABC分析**: 全出荷品目を数量順に並べ、累計シェアで「A(上位70%)」「B(70〜90%)」「C(90%〜)」に分類します。")
            abc_df = orders_df.groupby("製品名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False)
            total = abc_df["ケース数"].sum()
            abc_df["累計シェア"] = abc_df["ケース数"].cumsum() / total * 100
            abc_df["ランク"] = pd.cut(abc_df["累計シェア"], bins=[0, 70, 90, 100], labels=["Aランク (主力)", "Bランク (中堅)", "Cランク (その他)"])
            
            def color_rank(val):
                if "A" in str(val): return 'color: #DC2626; font-weight: 900; background-color: #FEE2E2;'
                elif "B" in str(val): return 'color: #D97706; font-weight: 700; background-color: #FEF3C7;'
                return 'color: #475569;'
                
            st.dataframe(abc_df.style.map(color_rank, subset=["ランク"]), use_container_width=True, hide_index=True)

# マスタ
elif page == "⚙️ マスタ管理":
    st.markdown('<div class="slim-header" style="background:#374151;"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["📦 製品マスタ", "🏢 顧客マスタ"])
    with t1:
        ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 保存", key="msave"): save_data("master", ed_m); st.rerun()
    with t2:
        ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 保存", key="csave"): save_data("customers", ed_c); st.rerun()
