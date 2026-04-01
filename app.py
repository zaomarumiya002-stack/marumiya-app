"""
丸実屋 受注・製造・在庫管理アプリ (リアルタイム反映・爆速同期・完全版)
"""

import os
# テーマ強制設定（文字消失防止）
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

# ─────────────────────────────────────────────
# 1. ページ基本設定
# ─────────────────────────────────────────────
st.set_page_config(page_title="丸実屋 受注・在庫管理", page_icon="🏭", layout="wide", initial_sidebar_state="expanded")

# ─────────────────────────────────────────────
# 2. UIデザインCSS（文字消失防止・巨大ボタン）
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] { font-family: 'Noto Sans JP', sans-serif !important; }
    p, span, label, h1, h2, h3, h4, div { color: #0F172A !important; }

    /* サイドバー */
    [data-testid="stSidebar"] { background-color: #F8FAFC !important; border-right: 1px solid #E2E8F0; }
    [data-testid="stSidebar"] .stButton > button { height: 50px !important; font-size: 16px !important; border-radius: 10px !important; }

    /* ヘッダー */
    .block-container { padding-top: 1rem !important; }
    .slim-header { background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%); padding: 12px 24px; border-radius: 10px; color: white !important; margin-bottom: 16px; }
    .slim-header h1 { color: white !important; margin: 0 !important; }

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
# 4. スプレッドシート連携 ＆ メモリ同期システム
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

# ★ データを保存すると同時に、画面表示用メモリ（session_state）も更新する
def save_and_sync(name, df):
    ws = sheet.worksheet(name)
    ws.clear()
    df_str = df.copy()
    for col in df_str.columns:
        if pd.api.types.is_datetime64_any_dtype(df_str[col]):
            df_str[col] = df_str[col].dt.strftime('%Y-%m-%d %H:%M:%S')
    ws.update(values=[df_str.fillna("").columns.values.tolist()] + df_str.fillna("").astype(str).values.tolist(), range_name='A1')
    st.cache_data.clear()
    # メモリ更新
    if name == "orders": st.session_state.orders_df = df
    elif name == "manufactures": st.session_state.manus_df = df
    elif name == "master": st.session_state.master_df = df
    elif name == "customers": st.session_state.cust_df = df

# ★ 行追加時にGoogleの遅延を無視して、画面用メモリに即座に結合する
def append_and_sync(name, new_row_df):
    row_list = new_row_df.fillna("").astype(str).values[0].tolist()
    sheet.worksheet(name).append_row(row_list)
    st.cache_data.clear()
    # メモリ更新（即時反映の核）
    if name == "orders":
        st.session_state.orders_df = pd.concat([st.session_state.orders_df, new_row_df], ignore_index=True)
    elif name == "manufactures":
        st.session_state.manus_df = pd.concat([st.session_state.manus_df, new_row_df], ignore_index=True)

# ─────────────────────────────────────────────
# 5. セッション初期化とデータロード
# ─────────────────────────────────────────────
if "orders_df" not in st.session_state: st.session_state.orders_df = load_data("orders")
if "manus_df" not in st.session_state: st.session_state.manus_df = load_data("manufactures")
if "master_df" not in st.session_state: st.session_state.master_df = load_data("master")
if "cust_df" not in st.session_state: st.session_state.cust_df = load_data("customers")

orders_df = st.session_state.orders_df
manus_df = st.session_state.manus_df
master_df = st.session_state.master_df
cust_df = st.session_state.cust_df

CATEGORIES = ["🍝 つきこん", "🟫 平こん", "🍜 糸こん・しらたき", "🔺 三角こん", "🟤 玉こん", "🎲 ダイスこん", "🏷️ 短冊", "🇯🇵 国産", "🤲 ちぎりこん", "🏮 大黒屋", "🏭 かねこ", "❄️ 冷凍耐性", "📦 その他"]

def format_name(name):
    if not name: return ""
    n = str(name)
    return f"⚫️ {n}" if "黒" in n else f"⚪️ {n}" if "白" in n else f"📦 {n}"

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
        rem = sc2.text_input("📝 備考（任意）", placeholder="備考を入力...")
        
        st.markdown('<div style="margin-top: 15px;"></div>', unsafe_allow_html=True)
        if st.button("✅ 受注を登録する", type="primary", use_container_width=True):
            if not prod or not qty: st.error("⚠️ 製品とケース数は必須です")
            else:
                # DataFrame形式で作成して同期処理に渡す
                new_row_df = pd.DataFrame([{
                    "ID": str(uuid.uuid4())[:6].upper(),
                    "納品予定日": pd.to_datetime(o_date),
                    "顧客名": c_name if c_name else "未指定",
                    "大カテゴリ": cat,
                    "製品名": prod,
                    "ケース数": int(qty),
                    "備考": rem,
                    "登録日時": pd.to_datetime(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                }])
                append_and_sync("orders", new_row_df)
                st.session_state.success_msg = f"✅ 登録完了： {o_date.strftime('%m/%d')} ｜ {c_name if c_name else '未指定'} ｜ {prod}"
                st.rerun()

        if st.session_state.success_msg:
            st.success(st.session_state.success_msg); st.session_state.success_msg = None

    st.markdown('<h2 style="font-size:18px; margin-top:20px;">✏️ かんたん修正（直近3件）</h2>', unsafe_allow_html=True)
    if not orders_df.empty:
        # 確実に最新データが表示される
        recent = orders_df.sort_values("登録日時", ascending=False).head(3).copy()
        recent["納品予定日"] = recent["納品予定日"].dt.date
        edited = st.data_editor(recent, use_container_width=True, hide_index=True, column_config={"納品予定日": st.column_config.DateColumn(format="YYYY-MM-DD"), "登録日時": None}, key="edit_o")
        if st.button("💾 修正内容を保存する"):
            others = orders_df[~orders_df["ID"].isin(recent["ID"])]
            updated_df = pd.concat([others, edited], ignore_index=True)
            save_and_sync("orders", updated_df)
            st.success("データを更新しました"); st.rerun()

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
                new_row_df = pd.DataFrame([{
                    "ID": str(uuid.uuid4())[:6].upper(),
                    "製造予定日": pd.to_datetime(m_date),
                    "備考": "",
                    "大カテゴリ": cat_m,
                    "製品名": prod_m,
                    "ケース数": int(m_qty),
                    "登録日時": pd.to_datetime(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                }])
                append_and_sync("manufactures", new_row_df)
                st.session_state.success_msg = f"✅ 登録完了：{prod_m}"; st.rerun()
        if st.session_state.success_msg: st.success(st.session_state.success_msg); st.session_state.success_msg = None

    st.markdown('<h2 style="font-size:18px; margin-top:20px;">✏️ かんたん修正（直近3件）</h2>', unsafe_allow_html=True)
    if not manus_df.empty:
        recent_m = manus_df.sort_values("登録日時", ascending=False).head(3).copy()
        recent_m["製造予定日"] = recent_m["製造予定日"].dt.date
        edited_m = st.data_editor(recent_m, use_container_width=True, hide_index=True, column_config={"製造予定日": st.column_config.DateColumn(format="YYYY-MM-DD"), "登録日時": None}, key="edit_m")
        if st.button("💾 修正を保存", key="smb"):
            others_m = manus_df[~manus_df["ID"].isin(recent_m["ID"])]
            updated_m = pd.concat([others_m, edited_m], ignore_index=True)
            save_and_sync("manufactures", updated_m)
            st.success("データを更新しました"); st.rerun()

# --- 📦 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="slim-header"><h1>📦 在庫予測とスケジュール</h1></div>', unsafe_allow_html=True)
    today = pd.Timestamp.today().normalize()
    dates = pd.date_range(today, today + timedelta(days=30))
    
    t1, t2 = st.tabs(["📉 1ヶ月在庫予測マトリクス", "📅 週間カレンダー"])
    
    with t1:
        st.write("💡 30日先までの在庫予測です。マイナス（欠品）になる日は赤く強調されます。")
        inv_list = []
        o_sum = orders_df.groupby("製品名")["ケース数"].sum() if not orders_df.empty else pd.Series(dtype=int)
        m_sum = manus_df.groupby("製品名")["ケース数"].sum() if not manus_df.empty else pd.Series(dtype=int)
        if not master_df.empty:
            for _, m in master_df.iterrows():
                prod = m["製品名"]
                curr = int(m["初期在庫数"]) + m_sum.get(prod, 0) - o_sum.get(prod, 0)
                row = {"カテゴリ": m["大カテゴリ"], "製品名": format_name(prod), "現在庫": curr}
                temp_stock = curr
                for i in range(1, 31):
                    d_fut = today + timedelta(days=i)
                    d_m = manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] == d_fut)]["ケース数"].sum() if not manus_df.empty else 0
                    d_o = orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] == d_fut)]["ケース数"].sum() if not orders_df.empty else 0
                    temp_stock += (d_m - d_o)
                    row[d_fut.strftime("%m/%d")] = temp_stock
                inv_list.append(row)
        
        if inv_list:
            inv_df = pd.DataFrame(inv_list).sort_values("カテゴリ")
            st.dataframe(inv_df.style.map(lambda x: 'color: #dc2626; font-weight: 900; background-color: #fee2e2;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True, height=600)

    with t2:
        col_dl1, col_dl2 = st.columns(2)
        today_o = orders_df[orders_df["納品予定日"] == today] if not orders_df.empty else pd.DataFrame()
        if not today_o.empty:
            csv1 = today_o[["顧客名", "製品名", "ケース数", "備考"]].sort_values("顧客名").to_csv(index=False, encoding="utf-8-sig")
            col_dl1.download_button("📝 今日の出荷予定を保存 (CSV)", data=csv1, file_name=f"出荷_{today.strftime('%Y%m%d')}.csv", type="primary", use_container_width=True)
        
        week_o = orders_df[(orders_df["納品予定日"] >= today) & (orders_df["納品予定日"] <= today + timedelta(days=6))] if not orders_df.empty else pd.DataFrame()
        if not week_o.empty:
            csv2 = week_o.sort_values(["納品予定日", "顧客名"])[["納品予定日", "顧客名", "製品名", "ケース数", "備考"]].to_csv(index=False, encoding="utf-8-sig")
            col_dl2.download_button("📅 1週間の出荷予定を保存 (CSV)", data=csv2, file_name=f"週間出荷_{today.strftime('%Y%m%d')}.csv", use_container_width=True)

        MAX_CS = 500
        html = '<table class="sched-table"><tr><th style="width:100px;">日付</th><th style="width:45%;">製造</th><th style="width:45%;">出荷</th></tr>'
        for i in range(7):
            d = today + timedelta(days=i)
            m_items = manus_df[manus_df["製造予定日"] == d] if not manus_df.empty else pd.DataFrame()
            o_items = orders_df[orders_df["納品予定日"] == d] if not orders_df.empty else pd.DataFrame()
            m_h = "".join([f'<div style="background:#F0FFF4; border-left:4px solid #10B981; padding:6px; margin-bottom:4px; border-radius:4px;"><span style="font-weight:700;">{format_name(r["製品名"])}</span> <span style="float:right; font-weight:900; color:#059669;">{r["ケース数"]}cs</span></div>' for _,r in m_items.iterrows()])
            o_h = "".join([f'<div style="background:#F0F7FF; border-left:4px solid #2563EB; padding:6px; margin-bottom:4px; border-radius:4px;"><span style="font-weight:700;">{r["顧客名"]}: {format_name(r["製品名"])}</span> <span style="float:right; font-weight:900; color:#1D4ED8;">{r["ケース数"]}cs</span></div>' for _,r in o_items.iterrows()])
            html += f'<tr><td><b>{d.strftime("%m/%d")}</b><br>{["月","火","水","木","金","土","日"][d.dayofweek]}曜</td><td>{m_h}</td><td>{o_h}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)

# 統計・マスタ
elif page == "📊 統計・分析":
    st.markdown('<div class="slim-header" style="background:linear-gradient(135deg, #4C1D95 0%, #8B5CF6 100%);"><h1>📊 出荷傾向分析</h1></div>', unsafe_allow_html=True)
    if not orders_df.empty:
        t1, t2 = st.tabs(["🏆 顧客別分析", "🥇 製品ABC分析"])
        with t1:
            st.plotly_chart(px.bar(orders_df.groupby("顧客名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False).head(15), x="ケース数", y="顧客名", orientation='h', title="主要顧客TOP15"), use_container_width=True)
        with t2:
            st.write("💡 累計シェアで「A(上位70%)」「B(70〜90%)」「C(90%〜)」に分類します。")
            abc_df = orders_df.groupby("製品名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False)
            abc_df["シェア(%)"] = abc_df["ケース数"].cumsum() / abc_df["ケース数"].sum() * 100
            abc_df["ランク"] = pd.cut(abc_df["シェア(%)"], bins=[0, 70, 90, 100], labels=["A (主力)", "B (中堅)", "C (その他)"])
            st.dataframe(abc_df.style.map(lambda v: 'color: #DC2626; font-weight: 900; background-color: #FEE2E2;' if "A" in str(v) else 'color: #D97706;' if "B" in str(v) else '', subset=["ランク"]), use_container_width=True, hide_index=True)

elif page == "⚙️ マスタ管理":
    st.markdown('<div class="slim-header" style="background:#374151;"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["📦 製品マスタ", "🏢 顧客マスタ"])
    with t1:
        ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 保存", key="msave"): save_and_sync("master", ed_m); st.rerun()
    with t2:
        ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 保存", key="csave"): save_and_sync("customers", ed_c); st.rerun()
