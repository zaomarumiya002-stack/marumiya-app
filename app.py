"""
丸実屋 受注・製造・在庫管理アプリ (安定稼働・ネイティブUI版)
"""

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
st.set_page_config(
    page_title="丸実屋 受注・在庫管理", 
    page_icon="🏭", 
    layout="wide"
)

# ─────────────────────────────────────────────
# 2. 安全なCSS（ウィジェットを破壊しない装飾のみ）
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* ヘッダーバナーのデザイン（安全な領域のみ装飾） */
    .banner {
        background: linear-gradient(135deg, #1a6fc4 0%, #0e4d8a 100%);
        padding: 20px 30px;
        border-radius: 10px;
        color: white;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .banner.manu {
        background: linear-gradient(135deg, #0e8c5a 0%, #0a6641 100%);
    }
    .banner h1 {
        margin: 0;
        color: white;
        font-size: 24px;
        font-weight: bold;
    }
    
    /* スケジュール表のデザイン */
    .custom-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 10px;
    }
    .custom-table th {
        background-color: #1a6fc4;
        color: white;
        padding: 10px;
        text-align: left;
        border: 1px solid #d0d7e3;
    }
    .custom-table td {
        padding: 10px;
        border: 1px solid #d0d7e3;
        vertical-align: top;
    }
    .event-tag {
        background-color: #eef4fd;
        border-left: 4px solid #1a6fc4;
        padding: 6px 10px;
        margin-bottom: 6px;
        border-radius: 4px;
        font-size: 13px;
        font-weight: bold;
        color: #1c2a3a;
    }
    .event-tag.manu-tag {
        background-color: #e8f5f0;
        border-left-color: #0e8c5a;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. パスワード認証
# ─────────────────────────────────────────────
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    
    if not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align:center;'>🏭 丸実屋システム ログイン</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            pwd = st.text_input("パスワードを入力", type="password")
            if st.button("ログイン", use_container_width=True, type="primary"):
                if pwd == st.secrets["app_password"]:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("❌ パスワードが違います")
        st.stop()

check_password()

# ─────────────────────────────────────────────
# 4. スプレッドシート連携
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

@st.cache_data(ttl=5)
def load_data(sheet_name):
    ws = sheet.worksheet(sheet_name)
    data = ws.get_all_values()
    cols = EXPECTED_COLS[sheet_name]
    if len(data) <= 1:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(data[1:], columns=data[0])
    for c in cols:
        if c not in df.columns: df[c] = ""
    # 型変換
    if "ケース数" in df.columns: df["ケース数"] = pd.to_numeric(df["ケース数"], errors='coerce').fillna(0).astype(int)
    if "初期在庫数" in df.columns: df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors='coerce').fillna(0).astype(int)
    if "納品予定日" in df.columns: df["納品予定日"] = pd.to_datetime(df["納品予定日"], errors='coerce')
    if "製造予定日" in df.columns: df["製造予定日"] = pd.to_datetime(df["製造予定日"], errors='coerce')
    return df[cols]

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
# 5. マスタデータ・アイコン定義
# ─────────────────────────────────────────────
CATEGORIES = [
    "🍝 つきこん", "🟫 平こん", "🍜 糸こん", "🔺 三角こん", 
    "🟤 玉こん", "🎲 ダイス", "🏷️ 短冊", "🇯🇵 国産", 
    "🤲 ちぎり", "🏮 大黒屋", "🏭 かねこ", "❄️ 冷凍耐性", "📦 その他"
]

def format_name(name):
    if not name: return ""
    n = str(name)
    if "黒" in n: return f"⚫️ {n}"
    if "白" in n: return f"⚪️ {n}"
    return f"📦 {n}"

# データロード
orders_df = load_data("orders")
manus_df = load_data("manufactures")
master_df = load_data("master")
cust_df = load_data("customers")

# セッション管理
if "last_registered" not in st.session_state:
    st.session_state.last_registered = None

# ─────────────────────────────────────────────
# 6. サイドバー (メニュー)
# ─────────────────────────────────────────────
with st.sidebar:
    st.title("🏭 丸実屋システム")
    st.write("---")
    page = st.radio(
        "📝 メニューを選択してください", 
        ["📋 受注登録 (出庫)", "🏭 製造登録 (入庫)", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"]
    )

# ─────────────────────────────────────────────
# 7. メイン画面の描画
# ─────────────────────────────────────────────

# --- 受注登録 ---
if page == "📋 受注登録 (出庫)":
    st.markdown('<div class="banner"><h1>📋 受注（出荷予定）の登録</h1></div>', unsafe_allow_html=True)
    
    # 直前の登録メッセージ
    if st.session_state.last_registered:
        st.success(f"✨ 直前の登録が完了しました： {st.session_state.last_registered}")
        st.session_state.last_registered = None

    with st.container(border=True):
        st.subheader("📝 入力フォーム")
        col1, col2, col3 = st.columns([1, 2, 1])
        
        o_date = col1.date_input("📅 納品予定日", value=date.today() + timedelta(days=1))
        
        # 顧客名（ひらがな検索 ＆ 空欄OK）
        cust_list = ["(空欄)"] + [f"{r['顧客名']} ({r['ふりがな']})" for _, r in cust_df.iterrows() if str(r['顧客名']).strip() != ""]
        sel_c_raw = col2.selectbox("🏢 顧客名（ひらがな検索可）", cust_list, index=0)
        c_name = sel_c_raw.split(" (")[0] if sel_c_raw != "(空欄)" else ""
        
        qty = col3.number_input("📦 出荷ケース数", min_value=1, value=1, step=1)

        # カテゴリ選択（標準のラジオボタンを横並びで安全に使用）
        st.write("📂 **カテゴリを選択**")
        sel_cat_full = st.radio("カテゴリ", CATEGORIES, horizontal=True, label_visibility="collapsed")
        sel_cat = sel_cat_full.split(" ")[1]

        # 製品選択
        prods = master_df[master_df["大カテゴリ"] == sel_cat]["製品名"].tolist()
        prod = st.selectbox("📦 製品名", prods, format_func=format_name)
        
        st.write("") # スペース
        if st.button("✅ 受注を登録する (続けて入力できます)", type="primary", use_container_width=True):
            if prod:
                new_row = pd.DataFrame([{
                    "ID": str(uuid.uuid4())[:6].upper(),
                    "納品予定日": str(o_date),
                    "顧客名": c_name if c_name else "未指定",
                    "大カテゴリ": sel_cat,
                    "製品名": prod,
                    "ケース数": int(qty),
                    "登録日時": datetime.now().strftime("%Y-%m-%d %H:%M")
                }])
                save_data("orders", pd.concat([orders_df, new_row], ignore_index=True))
                
                # トースト通知と履歴保存
                st.toast(f"✅ {c_name if c_name else '未指定'} 様宛 / {prod} を登録", icon="📦")
                st.session_state.last_registered = f"{o_date} | {c_name if c_name else '未指定'} | {prod} | {qty}ケース"
                st.rerun()
            else:
                st.error("⚠️ 製品が選択されていません。")

    st.write("### 🕒 最近の登録履歴 (直近5件)")
    if not orders_df.empty:
        st.dataframe(orders_df.tail(5).sort_values("登録日時", ascending=False), use_container_width=True, hide_index=True)

# --- 製造登録 ---
elif page == "🏭 製造登録 (入庫)":
    st.markdown('<div class="banner manu"><h1>🏭 製造（入庫）実績の登録</h1></div>', unsafe_allow_html=True)
    
    if st.session_state.last_registered:
        st.success(f"✨ 直前の登録が完了しました： {st.session_state.last_registered}")
        st.session_state.last_registered = None

    with st.container(border=True):
        st.subheader("📝 入力フォーム")
        col1, col2 = st.columns(2)
        m_date = col1.date_input("📅 製造日", value=date.today())
        m_qty = col2.number_input("📦 製造ケース数", min_value=1, value=50, step=10)
        
        st.write("📂 **カテゴリを選択**")
        sel_cat_full = st.radio("カテゴリ", CATEGORIES, horizontal=True, label_visibility="collapsed", key="m_cat")
        sel_cat = sel_cat_full.split(" ")[1]

        prods = master_df[master_df["大カテゴリ"] == sel_cat]["製品名"].tolist()
        prod = st.selectbox("📦 製品名", prods, format_func=format_name, key="m_prod")
        
        st.write("")
        if st.button("➕ 製造データを記録する", type="primary", use_container_width=True):
            if prod:
                new_row = pd.DataFrame([{
                    "ID": str(uuid.uuid4())[:6].upper(),
                    "製造予定日": str(m_date),
                    "備考": "",
                    "大カテゴリ": sel_cat,
                    "製品名": prod,
                    "ケース数": int(m_qty),
                    "登録日時": datetime.now().strftime("%Y-%m-%d %H:%M")
                }])
                save_data("manufactures", pd.concat([manus_df, new_row], ignore_index=True))
                
                st.toast(f"🏭 製造登録完了: {prod}", icon="✅")
                st.session_state.last_registered = f"{m_date} | {prod} | {m_qty}ケース製造"
                st.rerun()

# --- 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="banner"><h1>📦 在庫推移・スケジュール</h1></div>', unsafe_allow_html=True)
    
    today = pd.Timestamp.today().normalize()
    dates = pd.date_range(today, today + timedelta(days=14))
    
    with st.container(border=True):
        st.subheader("📉 向こう14日間の在庫予測 (マイナスは赤字)")
        inv_list = []
        for _, m in master_df.iterrows():
            prod = m["製品名"]
            curr = int(m["初期在庫数"])
            curr += manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] < today)]["ケース数"].sum()
            curr -= orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] < today)]["ケース数"].sum()
            
            row = {"製品名": format_name(prod)}
            for d in dates:
                in_q = manus_df[(manus_df["製品名"]==prod) & (manus_df["製造予定日"] == d)]["ケース数"].sum()
                out_q = orders_df[(orders_df["製品名"]==prod) & (orders_df["納品予定日"] == d)]["ケース数"].sum()
                curr += (in_q - out_q)
                row[d.strftime("%m/%d")] = curr
            inv_list.append(row)
        
        if inv_list:
            df_inv = pd.DataFrame(inv_list)
            # マイナス値を赤字・赤背景にする
            st.dataframe(df_inv.style.map(lambda x: 'color: red; font-weight: bold; background-color: #fee2e2;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True)

    with st.container(border=True):
        st.subheader("📅 直近1週間の入出庫カレンダー")
        html = '<table class="custom-table"><tr><th>日付</th><th>🏭 製造予定 (入庫)</th><th>📋 出荷予定 (出庫)</th></tr>'
        for i in range(7):
            d = today + timedelta(days=i)
            m_items = manus_df[manus_df["製造予定日"] == d]
            o_items = orders_df[orders_df["納品予定日"] == d]
            
            m_h = "".join([f'<div class="event-tag manu-tag">{format_name(r["製品名"])} ({r["ケース数"]}cs)</div>' for _,r in m_items.iterrows()])
            o_h = "".join([f'<div class="event-tag">{r["顧客名"]}: {format_name(r["製品名"])} ({r["ケース数"]}cs)</div>' for _,r in o_items.iterrows()])
            
            html += f'<tr><td style="width: 120px;"><b>{d.strftime("%m/%d")}</b></td><td>{m_h}</td><td>{o_h}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)

# --- 統計分析 ---
elif page == "📊 統計・分析":
    st.markdown('<div class="banner"><h1>📊 月別出荷実績分析</h1></div>', unsafe_allow_html=True)
    if not orders_df.empty:
        with st.container(border=True):
            orders_df["年月"] = orders_df["納品予定日"].dt.strftime("%Y-%m")
            fig = px.bar(orders_df.groupby(["年月","大カテゴリ"])["ケース数"].sum().reset_index(), x="年月", y="ケース数", color="大カテゴリ", barmode="stack", title="カテゴリ別 出荷数トレンド")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("データがありません。")

# --- マスタ管理 ---
elif page == "⚙️ マスタ管理":
    st.markdown('<div class="banner" style="background:linear-gradient(135deg, #475569 0%, #1e293b 100%);"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["📦 製品マスタ（棚卸・初期在庫）", "🏢 顧客マスタ（ふりがな）"])
    with t1:
        st.info("💡 実際の在庫数を「初期在庫数」に入力して保存すると、そこを起点に在庫計算がリセットされます。")
        ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 製品マスタを保存する", type="primary"):
            save_data("master", ed_m)
            st.toast("✅ 製品情報を更新しました")
            st.rerun()
            
    with t2:
        st.write("「ふりがな」を登録しておくと、受注登録時のドロップダウンでひらがな検索ができるようになります。")
        ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 顧客マスタを保存する", type="primary"):
            save_data("customers", ed_c)
            st.toast("✅ 顧客情報を更新しました")
            st.rerun()
