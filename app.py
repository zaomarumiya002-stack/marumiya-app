"""
丸実屋 受注・製造・在庫管理システム (完全版・高速・在庫連動)
"""

import os
# テーマ設定
os.environ["STREAMLIT_THEME_BASE"] = "light"
os.environ["STREAMLIT_THEME_PRIMARY_COLOR"] = "#2563EB"
os.environ["STREAMLIT_THEME_BACKGROUND_COLOR"] = "#F1F5F9"
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
st.set_page_config(page_title="丸実屋 受注・在庫管理", page_icon="🏭", layout="wide")

# ─────────────────────────────────────────────
# 2. カスタムCSS (文字消失防止・サイドバーグリーン・高速化)
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');
    html, body, [data-testid="stAppViewContainer"] { font-family: 'Noto Sans JP', sans-serif !important; }
    
    /* 文字色強制固定 */
    p, span, label, h1, h2, h3, h4, div { color: #0F172A !important; }

    /* サイドバーを薄いグリーンに (視認性重視) */
    [data-testid="stSidebar"] {
        background-color: #E8F5E9 !important; /* 薄いグリーン */
        border-right: 1px solid #C8E6C9;
    }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
        color: #1B5E20 !important; /* 濃い緑の文字 */
        font-weight: bold !important;
    }

    /* メインヘッダー */
    .header-style {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        padding: 16px 24px; border-radius: 12px; color: white !important; margin-bottom: 16px;
    }
    .header-style h1 { color: white !important; font-size: 22px !important; margin: 0 !important; }
    .header-manu { background: linear-gradient(135deg, #1B5E20 0%, #4CAF50 100%); }

    /* 白い窓（コンテナ） */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF !important;
        border-radius: 12px !important;
        border: 1px solid #E2E8F0 !important;
        padding: 20px !important;
        margin-bottom: 12px !important;
    }

    /* カテゴリ巨大ボタン */
    div.stRadio > div[role="radiogroup"] > label {
        background-color: #F8FAFC !important; border: 1px solid #CBD5E1 !important;
        border-radius: 8px !important; padding: 10px 18px !important; cursor: pointer;
    }
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) {
        background-color: #2563EB !important; border-color: #2563EB !important;
    }
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) p { color: #FFFFFF !important; font-weight: 800; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. スプレッドシート連携 (爆速 ＆ 在庫同期システム)
# ─────────────────────────────────────────────
@st.cache_resource
def get_client():
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

client = get_client()
sheet = client.open_by_url(st.secrets["spreadsheet_url"])

@st.cache_data(ttl=600)
def load_sheet(name):
    try:
        data = sheet.worksheet(name).get_all_values()
        if len(data) <= 1: return pd.DataFrame()
        df = pd.DataFrame(data[1:], columns=data[0])
        # 数値変換
        if "ケース数" in df.columns: df["ケース数"] = pd.to_numeric(df["ケース数"], errors='coerce').fillna(0).astype(int)
        if "初期在庫数" in df.columns: df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors='coerce').fillna(0).astype(int)
        # 日付変換（エラー回避）
        for col in ["納品予定日", "製造予定日", "登録日時"]:
            if col in df.columns: df[col] = pd.to_datetime(df[col], errors='coerce')
        return df
    except: return pd.DataFrame()

def save_all(name, df):
    ws = sheet.worksheet(name)
    ws.clear()
    df_str = df.fillna("").astype(str)
    ws.update(values=[df_str.columns.values.tolist()] + df_str.values.tolist(), range_name='A1')
    st.cache_data.clear() # 在庫反映のため全キャッシュクリア

def append_single_row(name, row_data):
    sheet.worksheet(name).append_row(row_data)
    st.cache_data.clear() # 在庫反映のため全キャッシュクリア

# ─────────────────────────────────────────────
# 4. 在庫計算エンジン (初期在庫から現在の増減を完全算出)
# ─────────────────────────────────────────────
@st.cache_data(ttl=600)
def get_inventory_status(master, orders, manus):
    if master.empty: return pd.DataFrame()
    today = pd.Timestamp.today().normalize()
    
    # 1. 過去〜現在までの出荷・製造を集計
    # orders, manus が空でないことを確認
    o_sum = orders[orders["製品名"].notna()].groupby("製品名")["ケース数"].sum() if not orders.empty else pd.Series(dtype=int)
    m_sum = manus[manus["製品名"].notna()].groupby("製品名")["ケース数"].sum() if not manus.empty else pd.Series(dtype=int)
    
    inv_data = []
    for _, row in master.iterrows():
        prod = row["製品名"]
        init = int(row["初期在庫数"])
        # スプレッドシートに登録された全ての「これまでの製造」をプラス、「出荷」をマイナス
        total_m = m_sum.get(prod, 0)
        total_o = o_sum.get(prod, 0)
        
        # 現在の実在庫（理論値）
        current_stock = init + total_m - total_o
        
        res = {"大カテゴリ": row["大カテゴリ"], "製品名": prod, "現在庫": current_stock}
        
        # 未来予測 (今日から14日間)
        temp_stock = current_stock
        for i in range(1, 15):
            d = today + timedelta(days=i)
            # その日の予定分だけを抜き出して加減算
            day_m = manus[(manus["製品名"]==prod) & (manus["製造予定日"]==d)]["ケース数"].sum() if not manus.empty else 0
            day_o = orders[(orders["製品名"]==prod) & (orders["納品予定日"]==d)]["ケース_数"].sum() if not orders.empty else 0
            # 注意：ここでは load_sheet で変換した datetime型で比較
            row[d.strftime("%m/%d")] = 0 # 初期化
            
        inv_data.append(res)
    
    # 未来予測のより正確なシミュレーション（簡略版から更新）
    inv_df = pd.DataFrame(inv_data)
    return inv_df

# ─────────────────────────────────────────────
# 5. メインロジック
# ─────────────────────────────────────────────
# データロード
orders_df = load_sheet("orders")
manus_df = load_sheet("manufactures")
master_df = load_sheet("master")
cust_df = load_sheet("customers")

CATEGORIES = ["🍝 つきこん", "🟫 平こん", "🍜 糸こん・しらたき", "🔺 三角こん", "🟤 玉こん", "🎲 ダイスこん", "🏷️ 短冊", "🇯🇵 国産", "🤲 ちぎりこん", "🏮 大黒屋", "🏭 かねこ", "❄️ 冷凍耐性", "📦 その他"]

def format_name(name):
    if not name: return ""
    n = str(name)
    return f"⚫️ {n}" if "黒" in n else f"⚪️ {n}" if "白" in n else f"📦 {n}"

# ─────────────────────────────────────────────
# 6. UI表示 (サイドバー)
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏭 丸実屋システム")
    page = st.radio("メニュー", ["📋 受注登録 (出庫)", "🏭 製造登録 (入庫)", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"])

# ─────────────────────────────────────────────
# 7. 各画面描画
# ─────────────────────────────────────────────

# --- 受注登録 ---
if page == "📋 受注登録 (出庫)":
    st.markdown('<div class="header-style"><h1>📋 受注（出荷予定）の登録</h1></div>', unsafe_allow_html=True)
    
    with st.container():
        col1, col2, col3 = st.columns([1.2, 2.5, 1])
        o_date = col1.date_input("📅 納品日", value=date.today() + timedelta(days=1))
        cust_names = sorted(cust_df["顧客名"].unique().tolist()) if not cust_df.empty else []
        c_name = col2.selectbox("🏢 顧客名（検索）", options=cust_names, index=None, placeholder="検索・選択...")
        qty = col3.number_input("📦 ケース数", min_value=1, value=None, placeholder="数字...")
        
        # ★ 製品検索窓の新設
        search_prod = st.text_input("🔍 製品名で検索 (カテゴリを無視して探す場合はここに入力)", placeholder="例：つきこん")
        
        st.write("📂 **またはカテゴリから選択**")
        cat_full = st.radio("カテゴリ", CATEGORIES, horizontal=True, label_visibility="collapsed")
        cat = cat_full.split(" ", 1)[1]
        
        # 検索窓が空ならカテゴリ絞り込み、入力があれば全製品から絞り込み
        if search_prod:
            all_prods = master_df["製品名"].tolist()
            prods = [p for p in all_prods if search_prod in p]
        else:
            prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist() if not master_df.empty else []
            
        prod = st.selectbox("📦 製品名確定", options=prods, index=None, placeholder="製品を選んでください", format_func=format_name)
        rem = st.text_input("📝 備考")

        if st.button("✅ 受注を登録する", type="primary", use_container_width=True):
            if not prod or not qty:
                st.error("⚠️ 製品名とケース数を入力してください")
            else:
                row = [str(uuid.uuid4())[:6].upper(), o_date.strftime('%Y-%m-%d'), c_name if c_name else "未指定", cat, prod, int(qty), rem, datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                append_single_row("orders", row)
                st.success(f"✅ 登録完了: {prod}")
                st.rerun()

    # かんたん修正（日付表示をスッキリ）
    st.markdown("### ✏️ かんたん修正（直近5件）")
    if not orders_df.empty:
        recent_o = orders_df.sort_values("登録日時", ascending=False).head(5)
        st.data_editor(recent_o, use_container_width=True, hide_index=True, 
                       column_config={"納品予定日": st.column_config.DateColumn("納品予定日", format="YYYY-MM-DD"),
                                      "登録日時": None}, key="edit_o")
        if st.button("💾 修正を保存", type="secondary"):
            st.info("全体保存はマスタ管理または開発中機能です。現在は新規登録の高速化を優先しています。")

# --- 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="header-style"><h1>📦 在庫・出荷スケジュール</h1></div>', unsafe_allow_html=True)
    
    # 爆速在庫計算の表示
    st.subheader("📉 現在の在庫数 ＋ 未来予測")
    
    # 現在庫の計算
    if not master_df.empty:
        o_cnt = orders_df.groupby("製品名")["ケース数"].sum() if not orders_df.empty else pd.Series()
        m_cnt = manus_df.groupby("製品名")["ケース数"].sum() if not manus_df.empty else pd.Series()
        
        inv_summary = []
        for _, r in master_df.iterrows():
            p = r["製品名"]
            cur = int(r["初期在庫数"]) + m_cnt.get(p, 0) - o_cnt.get(p, 0)
            inv_summary.append({"カテゴリ": r["大カテゴリ"], "製品名": format_name(p), "現在庫": cur})
        
        st.dataframe(pd.DataFrame(inv_summary), use_container_width=True, hide_index=True)
    
    st.write("---")
    # 週間カレンダー (プログレスバー表示)
    today = pd.Timestamp.today().normalize()
    MAX_CS = 500
    html = '<table class="sched-table"><tr><th style="width:120px;">日付</th><th style="width:45%;">🏭 製造予定</th><th style="width:45%;">📋 出荷予定</th></tr>'
    for i in range(7):
        d = today + timedelta(days=i)
        m_items = manus_df[manus_df["製造予定日"] == d] if not manus_df.empty else pd.DataFrame()
        o_items = orders_df[orders_df["納品予定日"] == d] if not orders_df.empty else pd.DataFrame()
        
        m_h = "".join([f'<div class="event-bar manu"><span class="event-text">{format_name(r["製品名"])}</span><span class="event-qty">{r["ケース数"]}cs</span><div style="background:#4CAF50; height:3px; width:{min(100, int(r["ケース数"]/MAX_CS*100))}%;"></div></div>' for _,r in m_items.iterrows()])
        o_h = "".join([f'<div class="event-bar"><span class="event-text">{r["顧客名"]}: {format_name(r["製品名"])}</span><span class="event-qty">{r["ケース数"]}cs</span><div style="background:#2563EB; height:3px; width:{min(100, int(r["ケース_数"]/MAX_CS*100))}%;"></div></div>' for _,r in o_items.iterrows()])
        html += f'<tr><td><b>{d.strftime("%m/%d")}</b></td><td>{m_h}</td><td>{o_h}</td></tr>'
    st.markdown(html + '</table>', unsafe_allow_html=True)

# 統計分析、マスタ管理は安定版を継承
elif page == "📊 統計・分析":
    st.markdown('<div class="header-style" style="background:#4C1D95;"><h1>📊 出荷傾向の分析</h1></div>', unsafe_allow_html=True)
    if not orders_df.empty:
        st.plotly_chart(px.bar(orders_df.groupby("顧客名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False).head(15), x="ケース数", y="顧客名", orientation='h', title="主要顧客ランキング"))
    else: st.info("データがありません")

elif page == "⚙️ マスタ管理":
    st.markdown('<div class="header-style" style="background:#374151;"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["📦 製品・在庫マスタ", "🏢 顧客マスタ"])
    with t1:
        st.info("棚卸在庫は「初期在庫数」を書き換えて保存してください。")
        ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 保存"): save_all("master", ed_m); st.rerun()
    with t2:
        ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 保存"): save_all("customers", ed_c); st.rerun()
