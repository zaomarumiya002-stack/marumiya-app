"""
丸実屋 受注・製造・在庫管理アプリ (エラー完全修復・高コントラスト・爆速版)
"""

import os
# テーマ強制固定（文字消失防止 ＆ 背景を濃いめにして視認性アップ）
os.environ["STREAMLIT_THEME_BASE"] = "light"
os.environ["STREAMLIT_THEME_PRIMARY_COLOR"] = "#2563EB"
os.environ["STREAMLIT_THEME_BACKGROUND_COLOR"] = "#E5E7EB" # 背景を濃いグレーに
os.environ["STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR"] = "#FFFFFF"
os.environ["STREAMLIT_THEME_TEXT_COLOR"] = "#111827"

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
# 2. 高コントラスト・モダンCSS（文字消失防止）
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Noto Sans JP', sans-serif !important;
        background-color: #E5E7EB !important; /* 背景をさらに濃く */
    }
    
    /* 入力欄（白い窓）を強調 */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF !important;
        border-radius: 12px !important;
        border: 1px solid #D1D5DB !important;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1) !important;
        padding: 25px !important;
        margin-bottom: 20px !important;
    }

    /* テキスト色固定 */
    p, span, label, h1, h2, h3, h4, div { color: #111827 !important; }

    /* ヘッダー */
    .header-style {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        padding: 20px 30px; border-radius: 12px; color: white !important; margin-bottom: 20px;
    }
    .header-style h1 { color: white !important; font-size: 24px !important; margin: 0 !important; }
    .header-manu { background: linear-gradient(135deg, #064E3B 0%, #10B981 100%); }

    /* サイドバー */
    [data-testid="stSidebar"] { background-color: #FFFFFF !important; border-right: 1px solid #D1D5DB; }
    [data-testid="stSidebar"] .stRadio label p { font-size: 16px !important; font-weight: 600 !important; }

    /* カテゴリ選択（ボタン） */
    div.stRadio > div[role="radiogroup"] { gap: 10px !important; }
    div.stRadio > div[role="radiogroup"] > label {
        background-color: #F3F4F6 !important; border: 1px solid #D1D5DB !important;
        border-radius: 8px !important; padding: 12px 20px !important; cursor: pointer; transition: 0.2s;
    }
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) {
        background-color: #2563EB !important; border-color: #2563EB !important;
    }
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) p { color: #FFFFFF !important; font-weight: 800; }

    /* スケジュール表 */
    .sched-table { width: 100%; border-collapse: collapse; background: #FFFFFF; border-radius: 8px; overflow: hidden; border: 1px solid #D1D5DB; }
    .sched-table th { background: #F9FAFB; color: #374151 !important; padding: 12px; text-align: left; border-bottom: 2px solid #D1D5DB; }
    .sched-table td { padding: 12px; border-bottom: 1px solid #F3F4F6; vertical-align: top; }
    
    /* 500ケース対応プログレスバー */
    .bar-container { position: relative; background: #F3F4F6; border-left: 5px solid #2563EB; border-radius: 4px; padding: 8px; margin-bottom: 6px; }
    .bar-container.manu { border-left-color: #10B981; }
    .bar-text { font-size: 14px; font-weight: 700; color: #111827 !important; }
    .bar-qty { float: right; font-weight: 800; color: #2563EB !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. パスワード認証
# ─────────────────────────────────────────────
def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align:center; margin-top:80px; color:#1E3A8A;'>🏭 丸実屋システム ログイン</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.container():
                pwd = st.text_input("パスワード", type="password")
                if st.button("ログイン", use_container_width=True, type="primary"):
                    if pwd == st.secrets["app_password"]:
                        st.session_state["password_correct"] = True
                        st.rerun()
                    else:
                        st.error("❌ パスワードが違います")
        st.stop()

check_password()

# ─────────────────────────────────────────────
# 4. Googleスプレッドシート連携 (爆速 ＆ 強力なエラー回避)
# ─────────────────────────────────────────────
@st.cache_resource
def get_client():
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

client = get_client()
sheet = client.open_by_url(st.secrets["spreadsheet_url"])

# 必須列の定義 (KeyErrorを防止するためのマスター)
REQUIRED_COLS = {
    "orders": ["ID", "納品予定日", "顧客名", "大カテゴリ", "製品名", "ケース数", "備考", "登録日時"],
    "manufactures": ["ID", "製造予定日", "備考", "大カテゴリ", "製品名", "ケース数", "登録日時"],
    "master": ["大カテゴリ", "製品名", "初期在庫数"],
    "customers": ["顧客名", "ふりがな"]
}

@st.cache_data(ttl=600)
def load_data(sheet_name):
    try:
        ws = sheet.worksheet(sheet_name)
        data = ws.get_all_values()
        target_cols = REQUIRED_COLS[sheet_name]
        
        if len(data) <= 1: 
            return pd.DataFrame(columns=target_cols)
        
        df = pd.DataFrame(data[1:], columns=data[0])
        
        # ★ KeyError対策：足りない列があれば自動で空の列を追加する
        for col in target_cols:
            if col not in df.columns:
                df[col] = ""
        
        # 列を定義順に整理し、不要な列を削る
        df = df[target_cols]

        # 型の変換
        if "ケース数" in df.columns: df["ケース数"] = pd.to_numeric(df["ケース数"], errors='coerce').fillna(0).astype(int)
        if "初期在庫数" in df.columns: df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors='coerce').fillna(0).astype(int)
        if "納品予定日" in df.columns: df["納品予定日"] = pd.to_datetime(df["納品予定日"], errors='coerce')
        if "製造予定日" in df.columns: df["製造予定日"] = pd.to_datetime(df["製造予定日"], errors='coerce')
        return df
    except Exception:
        return pd.DataFrame(columns=REQUIRED_COLS[sheet_name])

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
# 5. マスタデータ・関数
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
    st.markdown("<h2 style='font-weight:800; color:#1E3A8A;'>🏭 丸実屋システム</h2>", unsafe_allow_html=True)
    st.write("---")
    page = st.radio("メニュー", ["📋 受注登録 (出庫)", "🏭 製造登録 (入庫)", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"])

# ─────────────────────────────────────────────
# 7. 各画面描画
# ─────────────────────────────────────────────

# --- 受注登録 ---
if page == "📋 受注登録 (出庫)":
    st.markdown('<div class="header-style"><h1>📋 受注（出荷予定）の登録</h1></div>', unsafe_allow_html=True)
    
    with st.container():
        c1, c2, c3 = st.columns([1.2, 2.5, 1])
        o_date = c1.date_input("📅 納品日", value=date.today() + timedelta(days=1))
        # 顧客名：ひらがな検索可能（リストは漢字のみ）
        cust_names = sorted(cust_df["顧客名"].unique().tolist()) if not cust_df.empty else []
        c_name = c2.selectbox("🏢 顧客名（検索・入力）", options=cust_names, index=None, placeholder="空欄（未選択）")
        qty = c3.number_input("📦 ケース数", min_value=1, value=None, step=1, placeholder="数字...")
        remarks = st.text_input("📝 備考（任意・空欄OK）", placeholder="例：午前着、特記事項など")

        st.write("---")
        st.write("📂 **カテゴリ選択**")
        cat_full = st.radio("カテゴリ", CATEGORIES, horizontal=True, label_visibility="collapsed")
        cat = cat_full.split(" ", 1)[1]
        
        prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist() if not master_df.empty else []
        prod = st.selectbox("📦 製品名", options=prods, index=None, placeholder="製品を選んでください", format_func=format_name)
        
        st.write("")
        if st.button("✅ 受注を登録する", type="primary", use_container_width=True):
            if not o_date or not prod or not qty:
                st.error("⚠️ 【納品日・製品名・ケース数】は必須入力です。")
            else:
                row_data = [str(uuid.uuid4())[:6].upper(), o_date.strftime('%Y-%m-%d'), c_name if c_name else "未指定", cat, prod, int(qty), remarks, datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                append_row("orders", row_data)
                st.session_state.success_msg = f"✅ 登録完了： {o_date.strftime('%m/%d')} ｜ {c_name if c_name else '未指定'} ｜ {prod}"
                st.rerun()

        if st.session_state.success_msg:
            st.success(st.session_state.success_msg)
            st.session_state.success_msg = None

    st.markdown("### ✏️ かんたん修正（直近登録5件）")
    if not orders_df.empty:
        # 必要な列が確実にある状態で表示
        recent_o = orders_df.sort_values("登録日時", ascending=False).head(5)
        edited_recent = st.data_editor(recent_o, use_container_width=True, hide_index=True, key="edit_rec_o")
        if st.button("💾 修正を保存", type="secondary"):
            others = orders_df[~orders_df["ID"].isin(recent_o["ID"])]
            save_data("orders", pd.concat([others, edited_recent], ignore_index=True))
            st.rerun()

# --- 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="header-style"><h1>📦 在庫推移と週間出荷予定</h1></div>', unsafe_allow_html=True)
    today = pd.Timestamp.today().normalize()

    with st.container():
        st.subheader("📥 出荷リスト出力 (Excel対応)")
        col_dl1, col_dl2 = st.columns(2)
        # エラー防止のため、列の存在を確認してから抽出
        def safe_export(df, cols):
            valid_cols = [c for c in cols if c in df.columns]
            return df[valid_cols]

        today_orders = orders_df[orders_df["納品予定日"] == today] if not orders_df.empty else pd.DataFrame()
        if not today_orders.empty:
            csv1 = safe_export(today_orders, ["顧客名", "製品名", "ケース数", "備考"]).to_csv(index=False, encoding="utf-8-sig")
            col_dl1.download_button("📝 今日の出荷予定(CSV)", data=csv1, file_name=f"出荷_{today.strftime('%Y%m%d')}.csv", type="primary", use_container_width=True)
        
        week_end = today + timedelta(days=6)
        week_orders = orders_df[(orders_df["納品予定日"] >= today) & (orders_df["納品予定日"] <= week_end)] if not orders_df.empty else pd.DataFrame()
        if not week_orders.empty:
            csv2 = safe_export(week_orders.sort_values(["納品予定日", "顧客名"]), ["納品予定日", "顧客名", "製品名", "ケース数", "備考"]).to_csv(index=False, encoding="utf-8-sig")
            col_dl2.download_button("📅 1週間の出荷予定(CSV)", data=csv2, file_name=f"週間出荷_{today.strftime('%Y%m%d')}.csv", use_container_width=True)

    t1, t2 = st.tabs(["📆 週間カレンダー", "📉 在庫予測マトリクス"])
    with t1:
        MAX_CASES = 500
        html = '<table class="sched-table"><tr><th style="width:120px;">日付</th><th style="width:45%;">🏭 製造予定</th><th style="width:45%;">📋 出荷予定</th></tr>'
        for i in range(7):
            d = today + timedelta(days=i)
            m_items = manus_df[manus_df["製造予定日"] == d] if not manus_df.empty else pd.DataFrame()
            o_items = orders_df[orders_df["納品予定日"] == d] if not orders_df.empty else pd.DataFrame()
            
            m_h = "".join([f'<div class="bar-container manu"><span class="bar-text">{format_name(r["製品名"])}</span><span class="bar-qty">{r["ケース数"]}cs</span><div style="background:#10B981; height:4px; width:{min(100, int(r["ケース数"]/MAX_CASES*100))}%; margin-top:4px; border-radius:2px;"></div></div>' for _,r in m_items.iterrows()])
            o_h = "".join([f'<div class="bar-container"><span class="bar-text">{r["顧客名"]}: {format_name(r["製品名"])}</span><span class="bar-qty">{r["ケース数"]}cs</span><div style="background:#2563EB; height:4px; width:{min(100, int(r["ケース数"]/MAX_CASES*100))}%; margin-top:4px; border-radius:2px;"></div></div>' for _,r in o_items.iterrows()])
            html += f'<tr><td><b style="font-size:18px;">{d.strftime("%m/%d")}</b><br>{["月","火","水","木","金","土","日"][d.dayofweek]}曜</td><td>{m_h}</td><td>{o_h}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)

    with t2:
        inv_list = []
        if not master_df.empty:
            for _, m in master_df.iterrows():
                prod = m["製品名"]
                curr = int(m["初期在庫数"])
                if not manus_df.empty: curr += manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] < today)]["ケース数"].sum()
                if not orders_df.empty: curr -= orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] < today)]["ケース数"].sum()
                row = {"製品名": format_name(prod)}
                for j in range(14):
                    d_f = today + timedelta(days=j)
                    if not manus_df.empty: curr += manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] == d_f)]["ケース数"].sum()
                    if not orders_df.empty: curr -= orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] == d_f)]["ケース数"].sum()
                    row[d_f.strftime("%m/%d")] = curr
                inv_list.append(row)
        if inv_list:
            st.dataframe(pd.DataFrame(inv_list).style.map(lambda x: 'color: #dc2626; font-weight: 900; background-color: #fee2e2;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True, height=600)

# その他、製造・統計・マスタは安定版を継承
elif page == "🏭 製造登録 (入庫)":
    st.markdown('<div class="header-style header-manu"><h1>🏭 製造データの登録</h1></div>', unsafe_allow_html=True)
    with st.container():
        col1, col2 = st.columns(2)
        m_date = col1.date_input("📅 製造日", value=date.today())
        m_qty = col2.number_input("📦 製造数", min_value=1, value=None, placeholder="数字...")
        cat_full = st.radio("カテゴリ", CATEGORIES, horizontal=True)
        cat = cat_full.split(" ", 1)[1]
        prod = st.selectbox("製品名", options=master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist() if not master_df.empty else [], index=None, placeholder="選択してください", format_func=format_name)
        if st.button("➕ 製造を記録", type="primary", use_container_width=True):
            if not m_date or not prod or not m_qty:
                st.error("⚠️ 必須入力です。")
            else:
                append_row("manufactures", [str(uuid.uuid4())[:6].upper(), m_date.strftime('%Y-%m-%d'), "", cat, prod, int(m_qty), datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                st.session_state.success_msg = f"✅ 登録完了：{prod}"; st.rerun()
        if st.session_state.success_msg: st.success(st.session_state.success_msg); st.session_state.success_msg = None

    st.markdown("### ✏️ かんたん修正（直近5件）")
    if not manus_df.empty:
        recent_m = manus_df.sort_values("登録日時", ascending=False).head(5)
        edited_m = st.data_editor(recent_m, use_container_width=True, hide_index=True, key="edit_rec_m")
        if st.button("💾 修正を保存", type="secondary"):
            others_m = manus_df[~manus_df["ID"].isin(recent_m["ID"])]
            save_data("manufactures", pd.concat([others_m, edited_m], ignore_index=True))
            st.rerun()

elif page == "📊 統計・分析":
    st.markdown('<div class="header-style" style="background:#4C1D95;"><h1>📊 分析ダッシュボード</h1></div>', unsafe_allow_html=True)
    if not orders_df.empty:
        col1, col2 = st.columns(2)
        orders_df["年月"] = orders_df["納品予定日"].dt.strftime("%Y-%m")
        col1.plotly_chart(px.bar(orders_df.groupby(["年月","大カテゴリ"])["ケース数"].sum().reset_index(), x="年月", y="ケース数", color="大カテゴリ", barmode="stack", title="出荷トレンド"), use_container_width=True)
        col2.plotly_chart(px.bar(orders_df.groupby("顧客名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False).head(10), x="ケース数", y="顧客名", orientation='h', title="得意先TOP10"), use_container_width=True)

elif page == "⚙️ マスタ管理":
    st.markdown('<div class="header-style" style="background:#374151;"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["📦 製品マスタ", "🏢 顧客マスタ"])
    with t1:
        ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 製品マスタを保存"): save_data("master", ed_m); st.rerun()
    with t2:
        ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 顧客マスタを保存"): save_data("customers", ed_c); st.rerun()
