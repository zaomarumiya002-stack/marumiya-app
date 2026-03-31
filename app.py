"""
丸実屋 受注・製造・在庫管理アプリ (ネイティブUI・高機能・安定版)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import uuid
from datetime import datetime, timedelta, date
import gspread
from google.oauth2.service_account import Credentials

# ─────────────────────────────────────────────
# 1. ページ設定
# ─────────────────────────────────────────────
st.set_page_config(page_title="丸実屋 受注・在庫管理", page_icon="🏭", layout="wide")

# ─────────────────────────────────────────────
# 2. 安全なCSS（ウィジェットを一切破壊しない装飾のみ）
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* ヘッダーのデザイン（ここだけリッチにする） */
    .main-header {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 20px 30px;
        border-radius: 12px;
        color: white;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .main-header h1 { margin: 0; color: white !important; font-size: 24px; font-weight: bold; }
    .manu-header { background: linear-gradient(135deg, #064e3b 0%, #10b981 100%); }
    .stat-header { background: linear-gradient(135deg, #4c1d95 0%, #8b5cf6 100%); }

    /* スケジュール表のデザイン */
    .sched-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    .sched-table th { background-color: #f8fafc; color: #334155; padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 14px; }
    .sched-table td { padding: 12px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
    
    /* イベント（製造・出荷）の表示用 */
    .event-box { margin-bottom: 12px; font-size: 13px; line-height: 1.4; }
    .event-title { font-weight: bold; color: #1e293b; }
    .event-qty { font-weight: 900; float: right; color: #3b82f6; }
    .event-qty.manu { color: #10b981; }
    
    /* 横に伸びるプログレスバー */
    .bar-bg { width: 100%; background-color: #e2e8f0; border-radius: 4px; height: 6px; margin-top: 4px; overflow: hidden; }
    .bar-fill { height: 100%; background-color: #3b82f6; border-radius: 4px; }
    .bar-fill.manu { background-color: #10b981; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. パスワード認証
# ─────────────────────────────────────────────
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    
    if not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align:center; color:#1e3a8a; margin-top:50px;'>🏭 丸実屋システム ログイン</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.container(border=True):
                pwd = st.text_input("パスワードを入力してください", type="password")
                if st.button("ログイン", use_container_width=True, type="primary"):
                    if pwd == st.secrets["app_password"]:
                        st.session_state["password_correct"] = True
                        st.rerun()
                    else:
                        st.error("❌ パスワードが違います")
        st.stop()

check_password()

# ─────────────────────────────────────────────
# 4. スプレッドシート連携（キャッシュで高速化）
# ─────────────────────────────────────────────
@st.cache_resource
def get_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(creds)

client = get_client()
sheet = client.open_by_url(st.secrets["spreadsheet_url"])

EXPECTED_COLS = {
    "orders": ["ID", "納品予定日", "顧客名", "大カテゴリ", "製品名", "ケース数", "登録日時"],
    "manufactures": ["ID", "製造予定日", "備考", "大カテゴリ", "製品名", "ケース数", "登録日時"],
    "master": ["大カテゴリ", "製品名", "初期在庫数"],
    "customers": ["顧客名", "ふりがな"]
}

@st.cache_data(ttl=600)
def load_data(sheet_name):
    try:
        ws = sheet.worksheet(sheet_name)
        data = ws.get_all_values()
        cols = EXPECTED_COLS[sheet_name]
        if len(data) <= 1: return pd.DataFrame(columns=cols)
        df = pd.DataFrame(data[1:], columns=data[0])
        for c in cols:
            if c not in df.columns: df[c] = ""
        if "ケース数" in df.columns: df["ケース数"] = pd.to_numeric(df["ケース数"], errors='coerce').fillna(0).astype(int)
        if "初期在庫数" in df.columns: df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors='coerce').fillna(0).astype(int)
        if "納品予定日" in df.columns: df["納品予定日"] = pd.to_datetime(df["納品予定日"], errors='coerce')
        if "製造予定日" in df.columns: df["製造予定日"] = pd.to_datetime(df["製造予定日"], errors='coerce')
        return df[cols]
    except Exception:
        return pd.DataFrame(columns=EXPECTED_COLS[sheet_name])

def save_data(sheet_name, df):
    ws = sheet.worksheet(sheet_name)
    ws.clear()
    df_str = df.copy()
    for col in df_str.columns:
        if pd.api.types.is_datetime64_any_dtype(df_str[col]):
            df_str[col] = df_str[col].dt.strftime('%Y-%m-%d')
    df_str = df_str.fillna("").astype(str)
    ws.update(values=[df_str.columns.values.tolist()] + df_str.values.tolist(), range_name='A1')
    st.cache_data.clear()

# ─────────────────────────────────────────────
# 5. マスタデータ・関数
# ─────────────────────────────────────────────
CATEGORIES = [
    "🍝 つきこん", "🟫 平こん", "🍜 糸こん・しらたき", "🔺 三角こん", 
    "🟤 玉こん", "🎲 ダイスこん", "🏷️ 短冊", "🇯🇵 国産", 
    "🤲 ちぎりこん", "🏮 大黒屋", "🏭 かねこ", "❄️ 冷凍耐性", "📦 その他"
]

def format_name(name):
    if not name: return ""
    n = str(name)
    if "黒" in n: return f"⚫️ {n}"
    if "白" in n: return f"⚪️ {n}"
    return f"📦 {n}"

if "last_msg" not in st.session_state:
    st.session_state.last_msg = None

# データロード
orders_df = load_data("orders")
manus_df = load_data("manufactures")
master_df = load_data("master")
cust_df = load_data("customers")

# ─────────────────────────────────────────────
# 6. サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.title("🏭 丸実屋システム")
    st.write("---")
    # 標準のラジオボタンを使用（文字が消えない）
    page = st.radio(
        "メニューを選択", 
        ["📋 受注登録", "🏭 製造登録", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"]
    )

# ─────────────────────────────────────────────
# 7. 各画面の表示
# ─────────────────────────────────────────────

# --- 受注登録 ---
if page == "📋 受注登録":
    st.markdown('<div class="main-header"><h1>📋 受注（出荷予定）の登録</h1></div>', unsafe_allow_html=True)
    
    if st.session_state.last_msg:
        st.success(st.session_state.last_msg)
        st.session_state.last_msg = None

    with st.container(border=True):
        col1, col2, col3 = st.columns([1, 2, 1])
        
        o_date = col1.date_input("📅 納品予定日", value=date.today() + timedelta(days=1))
        
        # 顧客名：ひらがなで検索可能にするが、長すぎないようにする工夫
        cust_options = ["(空欄)"]
        for _, r in cust_df.iterrows():
            if str(r['顧客名']).strip() != "":
                if str(r['ふりがな']).strip() != "":
                    cust_options.append(f"{r['顧客名']} ｜ {r['ふりがな']}")
                else:
                    cust_options.append(r['顧客名'])

        sel_c_raw = col2.selectbox("🏢 顧客名（ひらがな検索可）", cust_options)
        # 選んだあとは「ふりがな」を切り捨ててスッキリさせる
        c_name = sel_c_raw.split(" ｜")[0] if sel_c_raw != "(空欄)" else ""
        
        qty = col3.number_input("📦 ケース数", min_value=1, value=1, step=1)

        st.write("---")
        # カテゴリ選択を標準機能で行う（文字が絶対に消えない）
        cat_full = st.radio("📂 カテゴリを選択", CATEGORIES, horizontal=True)
        cat = cat_full.split(" ", 1)[1] if " " in cat_full else cat_full
        
        prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
        prod = st.selectbox("📦 製品名", prods if prods else ["(このカテゴリに製品がありません)"], format_func=format_name)
        
        st.write("")
        if st.button("✅ 受注を登録する (続けて入力できます)", type="primary", use_container_width=True):
            if prod and prod != "(このカテゴリに製品がありません)":
                new_row = pd.DataFrame([{
                    "ID": str(uuid.uuid4())[:6].upper(),
                    "納品予定日": pd.Timestamp(o_date),
                    "顧客名": c_name if c_name else "未指定",
                    "大カテゴリ": cat,
                    "製品名": prod,
                    "ケース数": int(qty),
                    "登録日時": datetime.now()
                }])
                save_data("orders", pd.concat([orders_df, new_row], ignore_index=True))
                
                msg = f"✨ 登録完了: {o_date.strftime('%m/%d')} | {c_name if c_name else '未指定'} | {prod} | {qty}cs"
                st.session_state.last_msg = msg
                st.toast(msg, icon="📦")
                st.rerun()

    with st.expander("🕒 直近の登録データを確認・削除"):
        st.dataframe(orders_df.tail(10).sort_values("登録日時", ascending=False), use_container_width=True, hide_index=True)
        del_id = st.text_input("削除するデータのID（例: O-1A2B3C）")
        if st.button("🗑️ 削除を実行", type="secondary"):
            if del_id:
                save_data("orders", orders_df[orders_df["ID"] != del_id.strip()])
                st.success("削除しました"); st.rerun()

# --- 製造登録 ---
elif page == "🏭 製造登録":
    st.markdown('<div class="main-header manu-header"><h1>🏭 製造（入庫）実績の登録</h1></div>', unsafe_allow_html=True)
    
    if st.session_state.last_msg:
        st.success(st.session_state.last_msg)
        st.session_state.last_msg = None

    with st.container(border=True):
        col1, col2 = st.columns(2)
        m_date = col1.date_input("📅 製造日", value=date.today())
        m_qty = col2.number_input("📦 製造ケース数", min_value=1, value=50, step=10)
        
        st.write("---")
        cat_full = st.radio("📂 カテゴリを選択", CATEGORIES, horizontal=True)
        cat = cat_full.split(" ", 1)[1] if " " in cat_full else cat_full
        
        prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
        prod = st.selectbox("📦 製品名", prods if prods else ["(このカテゴリに製品がありません)"], format_func=format_name)
        
        st.write("")
        if st.button("➕ 製造データを記録する", type="primary", use_container_width=True):
            if prod and prod != "(このカテゴリに製品がありません)":
                new_row = pd.DataFrame([{
                    "ID": str(uuid.uuid4())[:6].upper(),
                    "製造予定日": pd.Timestamp(m_date),
                    "備考": "",
                    "大カテゴリ": cat,
                    "製品名": prod,
                    "ケース数": int(m_qty),
                    "登録日時": datetime.now()
                }])
                save_data("manufactures", pd.concat([manus_df, new_row], ignore_index=True))
                msg = f"✨ 製造登録完了: {m_date.strftime('%m/%d')} | {prod} | {m_qty}cs"
                st.session_state.last_msg = msg
                st.toast(msg, icon="🏭")
                st.rerun()

# --- 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="main-header"><h1>📦 在庫推移とスケジュール</h1></div>', unsafe_allow_html=True)
    
    today = pd.Timestamp.today().normalize()
    dates = pd.date_range(today, today + timedelta(days=14))
    
    t1, t2 = st.tabs(["📅 週間カレンダー (視覚化)", "📊 在庫予測マトリクス"])
    
    with t1:
        st.write("1日の出入りをプログレスバー（最大100ケース）で視覚的に表現しています。")
        MAX_CASES = 100
        
        html = '<table class="sched-table"><tr><th style="width:100px;">日付</th><th style="width:45%;">🏭 製造 (入庫)</th><th style="width:45%;">📋 出荷 (出庫)</th></tr>'
        for i in range(7):
            d = today + timedelta(days=i)
            m_items = manus_df[manus_df["製造予定日"] == d]
            o_items = orders_df[orders_df["納品予定日"] == d]
            
            m_html = ""
            for _, r in m_items.iterrows():
                pct = min(100, int((r["ケース数"] / MAX_CASES) * 100))
                m_html += f"""
                <div class="event-box">
                    <span class="event-title">{format_name(r["製品名"])}</span>
                    <span class="event-qty manu">{r["ケース数"]} cs</span>
                    <div class="bar-bg"><div class="bar-fill manu" style="width: {pct}%;"></div></div>
                </div>"""
                
            o_html = ""
            for _, r in o_items.iterrows():
                pct = min(100, int((r["ケース数"] / MAX_CASES) * 100))
                o_html += f"""
                <div class="event-box">
                    <span class="event-title">{r["顧客名"]}: {format_name(r["製品名"])}</span>
                    <span class="event-qty">{r["ケース数"]} cs</span>
                    <div class="bar-bg"><div class="bar-fill" style="width: {pct}%;"></div></div>
                </div>"""
                
            html += f'<tr><td><b style="font-size:16px;">{d.strftime("%m/%d")}</b></td><td>{m_html}</td><td>{o_html}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)

    with t2:
        st.write("マイナス（欠品）になる日は赤字・赤背景で強調表示されます。")
        inv_list = []
        for _, m in master_df.iterrows():
            prod = m["製品名"]
            curr = int(m["初期在庫数"])
            curr += manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] < today)]["ケース数"].sum()
            curr -= orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] < today)]["ケース数"].sum()
            
            row = {"大カテゴリ": m["大カテゴリ"], "製品名": format_name(prod)}
            for d in dates:
                in_q = manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] == d)]["ケース数"].sum()
                out_q = orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] == d)]["ケース数"].sum()
                curr += (in_q - out_q)
                row[d.strftime("%m/%d")] = curr
            inv_list.append(row)
        
        if inv_list:
            inv_df = pd.DataFrame(inv_list)
            st.dataframe(inv_df.style.map(lambda x: 'color: #dc2626; font-weight: 900; background-color: #fee2e2;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True)

# --- 統計分析 ---
elif page == "📊 統計分析":
    st.markdown('<div class="main-header stat-header"><h1>📊 出荷データの傾向分析</h1></div>', unsafe_allow_html=True)
    
    if orders_df.empty:
        st.info("データがありません。")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("総出荷ケース数", f"{orders_df['ケース数'].sum():,} cs")
        c2.metric("総受注件数", f"{len(orders_df):,} 件")
        c3.metric("取引先数", f"{orders_df[orders_df['顧客名'] != '未指定']['顧客名'].nunique()} 社")
        
        st.write("---")
        orders_df["年月"] = orders_df["納品予定日"].dt.strftime("%Y-%m")
        
        col_L, col_R = st.columns(2)
        with col_L:
            st.write("📈 **月別・カテゴリ別 出荷数推移**")
            trend_df = orders_df.groupby(["年月","大カテゴリ"])["ケース数"].sum().reset_index()
            fig = px.bar(trend_df, x="年月", y="ケース数", color="大カテゴリ", barmode="stack")
            st.plotly_chart(fig, use_container_width=True)
        with col_R:
            st.write("🏢 **得意先ランキング (TOP 10)**")
            cust_stat = orders_df[orders_df["顧客名"] != "未指定"].groupby("顧客名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False).head(10)
            fig2 = px.bar(cust_stat, x="ケース数", y="顧客名", orientation='h')
            fig2.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig2, use_container_width=True)

# --- マスタ管理 ---
elif page == "⚙️ マスタ管理":
    st.markdown('<div class="main-header" style="background:#475569;"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["📦 製品マスタ（棚卸・初期在庫）", "🏢 顧客マスタ（ふりがな）"])
    with t1:
        st.info("💡 実際の在庫数を「初期在庫数」に入力して保存すると、そこを起点に在庫計算がリセットされます。")
        ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 製品マスタを保存", type="primary"):
            save_data("master", ed_m)
            st.success("製品情報を更新しました")
            st.rerun()
            
    with t2:
        st.write("「ふりがな」を登録しておくと、受注登録時のドロップダウンでひらがな検索ができるようになります。")
        ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 顧客マスタを保存", type="primary"):
            save_data("customers", ed_c)
            st.success("顧客情報を更新しました")
            st.rerun()
