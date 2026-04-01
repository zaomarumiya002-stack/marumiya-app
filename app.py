"""
丸実屋 受注・製造・在庫管理アプリ (エラー修復・入力チェック・視認性強化版)
"""

import os
# テーマ強制固定（文字消失を100%防ぐ）
os.environ["STREAMLIT_THEME_BASE"] = "light"
os.environ["STREAMLIT_THEME_PRIMARY_COLOR"] = "#0071E3"
os.environ["STREAMLIT_THEME_BACKGROUND_COLOR"] = "#F5F5F7"
os.environ["STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR"] = "#FFFFFF"
os.environ["STREAMLIT_THEME_TEXT_COLOR"] = "#1D1D1F"

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
# 2. 安全なモダンCSS（文字消失防止・PC最適化）
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');
    
    /* 基本設定 */
    html, body, [data-testid="stAppViewContainer"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans JP", sans-serif !important;
        background-color: #F5F5F7 !important;
    }
    
    /* テキストをハッキリさせる */
    p, span, label, h1, h2, h3, h4, div { color: #1D1D1F !important; }

    /* スリムなヘッダー */
    .slim-header {
        background: linear-gradient(135deg, #0071E3 0%, #004799 100%);
        padding: 15px 25px; border-radius: 12px; color: white !important; margin-bottom: 15px;
        box-shadow: 0 4px 12px rgba(0, 113, 227, 0.2);
    }
    .slim-header h1 { color: white !important; font-size: 22px !important; font-weight: 700; margin: 0 !important; }
    .header-manu { background: linear-gradient(135deg, #34C759 0%, #1E823D 100%); }

    /* サイドバーの視認性向上 */
    [data-testid="stSidebar"] { background-color: #FFFFFF !important; border-right: 1px solid #D2D2D7; }
    [data-testid="stSidebar"] .stRadio label p { font-size: 17px !important; font-weight: 600 !important; color: #1D1D1F !important; }

    /* 白い窓（カード） */
    .glass-card {
        background-color: #FFFFFF !important;
        padding: 20px; border-radius: 15px; border: 1px solid #D2D2D7;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05); margin-bottom: 20px;
    }

    /* カテゴリ選択（巨大ボタン化） */
    div.stRadio > div[role="radiogroup"] { gap: 10px !important; }
    div.stRadio > div[role="radiogroup"] > label {
        background-color: #F5F5F7 !important; border: 1px solid #D2D2D7 !important;
        border-radius: 10px !important; padding: 10px 20px !important; cursor: pointer; transition: 0.2s;
    }
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) {
        background-color: #0071E3 !important; border-color: #0071E3 !important;
    }
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) p { color: #FFFFFF !important; font-weight: bold; }

    /* スケジュール表 */
    .sched-table { width: 100%; border-collapse: collapse; background: #FFFFFF; border-radius: 12px; overflow: hidden; border: 1px solid #D2D2D7; }
    .sched-table th { background: #F5F5F7; color: #86868B !important; padding: 12px; text-align: left; border-bottom: 1px solid #D2D2D7; font-size: 13px; }
    .sched-table td { padding: 12px; border-bottom: 1px solid #F5F5F7; vertical-align: top; }
    
    /* バー表示 */
    .bar-wrap { position: relative; background: #F5F5F7; border-left: 4px solid #0071E3; border-radius: 5px; padding: 8px 12px; margin-bottom: 5px; }
    .bar-wrap.manu { border-left-color: #34C759; }
    .bar-text { font-size: 14px; font-weight: 700; }
    .bar-qty { float: right; font-weight: 900; color: #0071E3; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. パスワード認証
# ─────────────────────────────────────────────
def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align:center; margin-top:80px; color:#0071E3;'>🏭 丸実屋システム ログイン</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.container():
                pwd = st.text_input("パスワード", type="password")
                if st.button("ログイン", use_container_width=True, type="primary"):
                    if pwd == st.secrets["app_password"]:
                        st.session_state["password_correct"] = True
                        st.rerun()
                    else: st.error("❌ パスワードが違います")
        st.stop()

check_password()

# ─────────────────────────────────────────────
# 4. スプレッドシート連携 (爆速＆KeyError対策)
# ─────────────────────────────────────────────
@st.cache_resource
def get_client():
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

client = get_client()
sheet = client.open_by_url(st.secrets["spreadsheet_url"])

@st.cache_data(ttl=600)
def load_data(sheet_name):
    try:
        ws = sheet.worksheet(sheet_name)
        data = ws.get_all_values()
        cols = {"orders":["ID","納品予定日","顧客名","大カテゴリ","製品名","ケース数","備考","登録日時"],
                "manufactures":["ID","製造予定日","備考","大カテゴリ","製品名","ケース数","登録日時"],
                "master":["大カテゴリ","製品名","初期在庫数"],
                "customers":["顧客名","ふりがな"]}[sheet_name]
        if len(data) <= 1: return pd.DataFrame(columns=cols)
        df = pd.DataFrame(data[1:], columns=data[0])
        # 型変換
        if "ケース数" in df.columns: df["ケース数"] = pd.to_numeric(df["ケース数"], errors='coerce').fillna(0).astype(int)
        if "初期在庫数" in df.columns: df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors='coerce').fillna(0).astype(int)
        if "納品予定日" in df.columns: df["納品予定日"] = pd.to_datetime(df["納品予定日"], errors='coerce')
        if "製造予定日" in df.columns: df["製造予定日"] = pd.to_datetime(df["製造予定日"], errors='coerce')
        return df
    except Exception:
        return pd.DataFrame()

def save_data(sheet_name, df):
    ws = sheet.worksheet(sheet_name)
    ws.clear()
    df_str = df.fillna("").astype(str)
    ws.update(values=[df_str.columns.values.tolist()] + df_str.values.tolist(), range_name='A1')
    st.cache_data.clear()

def append_row(sheet_name, row_data):
    sheet.worksheet(sheet_name).append_row(row_data)
    st.cache_data.clear()

# ─────────────────────────────────────────────
# 5. マスタ定義
# ─────────────────────────────────────────────
CATEGORIES = ["🍝 つきこん", "🟫 平こん", "🍜 糸こん・しらたき", "🔺 三角こん", "🟤 玉こん", "🎲 ダイスこん", "🏷️ 短冊", "🇯🇵 国産", "🤲 ちぎりこん", "🏮 大黒屋", "🏭 かねこ", "❄️ 冷凍耐性", "📦 その他"]

def format_name(name):
    if not name: return ""
    n = str(name)
    if "黒" in n: return f"⚫️ {n}"
    if "白" in n: return f"⚪️ {n}"
    return f"📦 {n}"

orders_df = load_data("orders")
manus_df = load_data("manufactures")
master_df = load_data("master")
cust_df = load_data("customers")

if "success_msg" not in st.session_state: st.session_state.success_msg = None

# ─────────────────────────────────────────────
# 6. サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<p style='font-size:20px; font-weight:800; color:#0071E3;'>🏭 丸実屋システム</p>", unsafe_allow_html=True)
    st.write("---")
    page = st.radio("メニュー", ["📋 受注登録 (出庫)", "🏭 製造登録 (入庫)", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"])

# ─────────────────────────────────────────────
# 7. 各画面描画
# ─────────────────────────────────────────────

# --- 受注登録 ---
if page == "📋 受注登録 (出庫)":
    st.markdown('<div class="slim-header"><h1>📋 受注（出荷予定）登録</h1></div>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1.2, 2.5, 1])
        o_date = c1.date_input("📅 納品日", value=date.today() + timedelta(days=1))
        # 漢字のみリスト表示。入力して絞り込み
        cust_names = sorted(cust_df["顧客名"].unique().tolist()) if not cust_df.empty else []
        c_name = c2.selectbox("🏢 顧客名（検索・入力）", options=cust_names, index=None, placeholder="空欄（未選択）")
        qty = c3.number_input("📦 ケース数", min_value=1, value=None, step=1, placeholder="数字...")
        remarks = st.text_input("📝 備考（任意）", placeholder="午前着、特記事項など")

        st.write("📂 **カテゴリ**")
        cat_full = st.radio("カテゴリ", CATEGORIES, horizontal=True, label_visibility="collapsed")
        cat = cat_full.split(" ", 1)[1]
        
        prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist() if not master_df.empty else []
        prod = st.selectbox("📦 製品名", options=prods, index=None, placeholder="製品を選んでください", format_func=format_name)
        
        st.write("")
        if st.button("✅ 受注を登録する", type="primary", use_container_width=True):
            # ★ 必須項目チェック
            if not o_date or not prod or not qty:
                st.error("⚠️ 【納品日・製品名・ケース数】は必須入力です。")
            else:
                row_data = [str(uuid.uuid4())[:6].upper(), o_date.strftime('%Y-%m-%d'), c_name if c_name else "未指定", cat, prod, int(qty), remarks, datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                append_row("orders", row_data)
                st.session_state.success_msg = f"✨ 登録完了： {o_date.strftime('%m/%d')} ｜ {c_name if c_name else '未指定'} ｜ {prod}"
                st.rerun()

        if st.session_state.success_msg:
            st.success(st.session_state.success_msg)
            st.session_state.success_msg = None
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("### ✏️ かんたん修正（直近登録5件）")
    if not orders_df.empty:
        recent_o = orders_df.sort_values("登録日時", ascending=False).head(5)
        edited_recent = st.data_editor(recent_o, use_container_width=True, hide_index=True, key="edit_rec_o")
        if st.button("💾 修正を保存", type="secondary"):
            others = orders_df[~orders_df["ID"].isin(recent_o["ID"])]
            save_data("orders", pd.concat([others, edited_recent], ignore_index=True))
            st.rerun()

# --- 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="slim-header"><h1>📦 在庫推移とスケジュール</h1></div>', unsafe_allow_html=True)
    today = pd.Timestamp.today().normalize()

    # --- ピッキングリスト出力 ---
    with st.container():
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("📥 リスト出力 (Excel対応)")
        col_dl1, col_dl2 = st.columns(2)
        today_orders = orders_df[orders_df["納品予定日"] == today] if not orders_df.empty else pd.DataFrame()
        if not today_orders.empty:
            csv1 = today_orders[["顧客名", "製品名", "ケース数", "備考"]].to_csv(index=False, encoding="utf-8-sig")
            col_dl1.download_button("📝 今日の出荷予定(CSV)", data=csv1, file_name=f"出荷_{today.strftime('%Y%m%d')}.csv", type="primary", use_container_width=True)
        
        week_end = today + timedelta(days=6)
        week_orders = orders_df[(orders_df["納品予定日"] >= today) & (orders_df["納品予定日"] <= week_end)] if not orders_df.empty else pd.DataFrame()
        if not week_orders.empty:
            csv2 = week_orders.sort_values(["納品予定日", "顧客名"])[["納品予定日", "顧客名", "製品名", "ケース数", "備考"]].to_csv(index=False, encoding="utf-8-sig")
            col_dl2.download_button("📅 1週間の出荷予定(CSV)", data=csv2, file_name=f"週間出荷_{today.strftime('%Y%m%d')}.csv", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    t1, t2 = st.tabs(["📆 週間カレンダー", "📉 在庫予測マトリクス"])
    with t1:
        MAX_CASES = 500
        html = '<table class="sched-table"><tr><th style="width:120px;">日付</th><th style="width:45%;">🏭 製造予定</th><th style="width:45%;">📋 出荷予定</th></tr>'
        for i in range(7):
            d = today + timedelta(days=i)
            # 安全にフィルタリング (KeyError対策)
            m_items = manus_df[manus_df["製造予定日"] == d] if not manus_df.empty else pd.DataFrame()
            o_items = orders_df[orders_df["納品予定日"] == d] if not orders_df.empty else pd.DataFrame()
            
            m_h = "".join([f'<div class="bar-wrap manu"><span class="bar-text">{format_name(r["製品名"])}</span><span class="bar-qty">{r["ケース数"]}cs</span><div style="background:#34C759; height:3px; width:{min(100, int(r["ケース数"]/MAX_CASES*100))}%; margin-top:4px;"></div></div>' for _,r in m_items.iterrows()])
            o_h = "".join([f'<div class="bar-wrap"><span class="bar-text">{r["顧客名"]}: {format_name(r["製品名"])}</span><span class="bar-qty">{r["ケース数"]}cs</span><div style="background:#0071E3; height:3px; width:{min(100, int(r["ケース数"]/MAX_CASES*100))}%; margin-top:4px;"></div></div>' for _,r in o_items.iterrows()])
            html += f'<tr><td><b style="font-size:18px;">{d.strftime("%m/%d")}</b><br>{["月","火","水","木","金","土","日"][d.dayofweek]}</td><td>{m_h}</td><td>{o_h}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)

    with t2:
        # 在庫計算ロジック
        inv_list = []
        if not master_df.empty:
            for _, m in master_df.iterrows():
                prod = m["製品名"]
                curr = int(m["初期在庫数"])
                if not manus_df.empty: curr += manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] < today)]["ケース数"].sum()
                if not orders_df.empty: curr -= orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] < today)]["ケース数"].sum()
                row = {"製品名": format_name(prod)}
                for j in range(14):
                    d_fut = today + timedelta(days=j)
                    if not manus_df.empty: curr += manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] == d_fut)]["ケース数"].sum()
                    if not orders_df.empty: curr -= orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] == d_fut)]["ケース数"].sum()
                    row[d_fut.strftime("%m/%d")] = curr
                inv_list.append(row)
        if inv_list:
            st.dataframe(pd.DataFrame(inv_list).style.map(lambda x: 'color: #dc2626; font-weight: 900; background-color: #fee2e2;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True, height=600)

# その他、統計・マスタは前回の安定版を継承
elif page == "🏭 製造登録 (入庫)":
    st.markdown('<div class="slim-header header-manu"><h1>🏭 製造データの登録</h1></div>', unsafe_allow_html=True)
    with st.container():
        col1, col2 = st.columns(2)
        m_date = col1.date_input("📅 製造日", value=date.today())
        m_qty = col2.number_input("📦 製造数", min_value=1, value=None, placeholder="数字...")
        cat_full = st.radio("カテゴリ", CATEGORIES, horizontal=True)
        cat = cat_full.split(" ", 1)[1]
        prod = st.selectbox("製品名", options=master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist() if not master_df.empty else [], index=None, placeholder="選択してください", format_func=format_name)
        if st.button("➕ 製造を記録", type="primary", use_container_width=True):
            if not m_date or not prod or not m_qty:
                st.error("⚠️ 【製造日・製品名・製造数】は必須入力です。")
            else:
                append_row("manufactures", [str(uuid.uuid4())[:6].upper(), m_date.strftime('%Y-%m-%d'), "", cat, prod, int(m_qty), datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                st.session_state.success_msg = f"✅ 製造記録完了：{prod}"; st.rerun()
        if st.session_state.success_msg: st.success(st.session_state.success_msg); st.session_state.success_msg = None

elif page == "📊 統計・分析":
    st.markdown('<div class="slim-header" style="background:#5E5CE6;"><h1>📊 分析ダッシュボード</h1></div>', unsafe_allow_html=True)
    if not orders_df.empty:
        col1, col2 = st.columns(2)
        orders_df["年月"] = orders_df["納品予定日"].dt.strftime("%Y-%m")
        col1.plotly_chart(px.bar(orders_df.groupby(["年月","大カテゴリ"])["ケース数"].sum().reset_index(), x="年月", y="ケース数", color="大カテゴリ", barmode="stack", title="出荷トレンド"), use_container_width=True)
        col2.plotly_chart(px.bar(orders_df.groupby("顧客名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False).head(10), x="ケース数", y="顧客名", orientation='h', title="得意先TOP10"), use_container_width=True)

elif page == "⚙️ マスタ管理":
    st.markdown('<div class="slim-header" style="background:#475569;"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["📦 製品マスタ", "🏢 顧客マスタ"])
    with t1:
        ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 保存"): save_data("master", ed_m); st.rerun()
    with t2:
        ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 保存"): save_data("customers", ed_c); st.rerun()
