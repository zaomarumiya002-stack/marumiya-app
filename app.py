"""
丸実屋 受注・製造・在庫管理アプリ (カテゴリ不一致バグ修正版)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid
from datetime import datetime, timedelta, date
import gspread
from google.oauth2.service_account import Credentials

# ─────────────────────────────────────────────
# 1. ページ基本設定
# ─────────────────────────────────────────────
st.set_page_config(page_title="丸実屋 受注・在庫管理", page_icon="🏭", layout="wide")

# ─────────────────────────────────────────────
# 2. 安全なカスタムCSS（ウィジェットを破壊しない）
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* 全体の背景・文字色を固定 */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #F8FAFC !important;
        color: #0F172A !important;
    }
    .stMarkdown, p, span, h1, h2, h3, h4, label, div {
        color: #1E293B !important;
    }

    /* モダンなグラデーションヘッダー */
    .modern-header {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        padding: 24px 32px;
        border-radius: 12px;
        margin-bottom: 24px;
        box-shadow: 0 4px 15px -3px rgba(59, 130, 246, 0.4);
    }
    .modern-header h1 { color: white !important; margin: 0 !important; font-size: 26px !important; font-weight: 800 !important; letter-spacing: 1px !important; }
    .modern-header.manu { background: linear-gradient(135deg, #064E3B 0%, #10B981 100%); box-shadow: 0 4px 15px -3px rgba(16, 185, 129, 0.4); }
    .modern-header.stat { background: linear-gradient(135deg, #4C1D95 0%, #8B5CF6 100%); box-shadow: 0 4px 15px -3px rgba(139, 92, 246, 0.4); }

    /* カテゴリ選択ボタン（Pills） */
    div.stRadio > div[role="radiogroup"] {
        display: flex; flex-direction: row; flex-wrap: wrap; gap: 10px; padding-bottom: 16px;
    }
    div.stRadio > div[role="radiogroup"] > label {
        background-color: #F1F5F9 !important;
        border: 2px solid #CBD5E1 !important;
        border-radius: 9999px !important;
        padding: 6px 18px !important;
        color: #475569 !important;
        cursor: pointer !important;
        transition: all 0.2s !important;
    }
    div.stRadio > div[role="radiogroup"] > label:hover {
        background-color: #E2E8F0 !important;
        border-color: #94A3B8 !important;
        color: #1E293B !important;
    }
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) {
        background-color: #2563EB !important;
        border-color: #2563EB !important;
        box-shadow: 0 4px 14px 0 rgba(37, 99, 235, 0.3) !important;
    }
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) p,
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) span,
    div.stRadio > div[role="radiogroup"] > label:has(input:checked) div {
        color: #FFFFFF !important;
        font-weight: bold !important;
    }
    div.stRadio > div[role="radiogroup"] label[data-baseweb="radio"] div:first-child { display: none !important; }

    /* サイドバーの色固定 */
    [data-testid="stSidebar"] { background-color: #0F172A !important; }
    [data-testid="stSidebar"] * { color: #F8FAFC !important; }
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) { background-color: #2563EB !important; border-radius: 8px; }

    /* 視覚的スケジュール表のデザイン */
    .sched-table { width: 100%; border-collapse: separate; border-spacing: 0; background: transparent; }
    .sched-table th { background-color: #F8FAFC; color: #475569 !important; font-weight: 700; padding: 12px; text-align: left; border-bottom: 2px solid #E2E8F0; }
    .sched-table td { padding: 12px; border-bottom: 1px solid #F1F5F9; vertical-align: top; }
    
    /* プログレスバー風のイベントカード */
    .event-card {
        position: relative;
        padding: 8px 12px;
        margin-bottom: 8px;
        border-radius: 6px;
        border-left: 4px solid #3B82F6;
        background-color: #F1F5F9;
        overflow: hidden;
        z-index: 1;
    }
    .event-card.manu-card { border-left-color: #10B981; }
    
    /* 背景のバー（割合で伸びる） */
    .event-bg-bar {
        position: absolute; top: 0; left: 0; height: 100%;
        background-color: #DBEAFE; z-index: -1;
        transition: width 0.3s ease;
    }
    .event-card.manu-card .event-bg-bar { background-color: #D1FAE5; }
    
    /* カード内のテキスト */
    .event-text { font-size: 13px; font-weight: 600; color: #1E293B; line-height: 1.4; }
    .event-qty { float: right; font-weight: 800; color: #1D4ED8; }
    .event-card.manu-card .event-qty { color: #047857; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. パスワード認証
# ─────────────────────────────────────────────
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    
    if not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align:center; color:#1E3A8A; margin-top:50px;'>🏭 丸実屋システム ログイン</h2>", unsafe_allow_html=True)
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
# 4. Googleスプレッドシート連携（爆速キャッシュ）
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

# キャッシュを「10分間（600秒）」保持し、動作を爆速化
@st.cache_data(ttl=600)
def load_data(sheet_name):
    ws = sheet.worksheet(sheet_name)
    data = ws.get_all_values()
    cols = EXPECTED_COLS[sheet_name]
    if len(data) <= 1: return pd.DataFrame(columns=cols)
    df = pd.DataFrame(data[1:], columns=data[0])
    for c in cols:
        if c not in df.columns: df[c] = ""
    # 型変換を高速化
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
# 5. データ処理と在庫計算
# ─────────────────────────────────────────────

# 【重要修正】ここで設定する文字列の右側（空白の後ろ）が、スプレッドシートの「大カテゴリ」と完全に一致する必要があります
CATEGORIES_LIST = [
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

# データロード
orders_df = load_data("orders")
manus_df = load_data("manufactures")
master_df = load_data("master")
cust_df = load_data("customers")

if "last_registered" not in st.session_state:
    st.session_state.last_registered = None

# ─────────────────────────────────────────────
# 6. メインUI (サイドバー)
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h2 style='font-weight:900;'>🏭 丸実屋システム</h2>", unsafe_allow_html=True)
    st.write("---")
    page = st.radio("メニュー", ["📋 受注登録", "🏭 製造登録", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"])

# ─────────────────────────────────────────────
# 7. 各画面の描画
# ─────────────────────────────────────────────

# --- 受注登録 ---
if page == "📋 受注登録":
    st.markdown('<div class="modern-header"><h1>📋 受注（出荷予定）の登録</h1></div>', unsafe_allow_html=True)
    
    if st.session_state.last_registered:
        st.success(f"✨ {st.session_state.last_registered}")
        st.session_state.last_registered = None

    with st.container(border=True):
        col1, col2, col3 = st.columns([1, 2, 1])
        o_date = col1.date_input("📅 納品予定日", value=date.today() + timedelta(days=1))
        
        # 顧客名：ふりがなを目立たせずスッキリ見せる工夫
        cust_options = ["(空欄)"] + [f"{r['顧客名']} ｜ {r['ふりがな']}" for _, r in cust_df.iterrows() if str(r['顧客名']).strip() != ""]
        sel_c_raw = col2.selectbox("🏢 顧客名（ひらがな検索可）", cust_options)
        c_name = sel_c_raw.split(" ｜")[0] if sel_c_raw != "(空欄)" else ""
        
        qty = col3.number_input("📦 出荷ケース数", min_value=1, value=1, step=1)

        # カテゴリ・製品
        st.write("---")
        st.write("📂 **カテゴリを選択**")
        cat_full = st.radio("カテゴリ", CATEGORIES_LIST, horizontal=True, label_visibility="collapsed")
        
        # 【重要】空白で分割し、2つ目以降の文字列（糸こん・しらたき 等）を抽出
        cat = cat_full.split(" ", 1)[1]
        
        prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
        prod = st.selectbox("📦 製品名を選択", prods if prods else ["(このカテゴリに製品がありません)"], format_func=format_name)
        
        st.write("")
        if st.button("✅ 受注を登録する (続けて入力できます)", type="primary", use_container_width=True):
            if prod and prod != "(このカテゴリに製品がありません)":
                new_row = pd.DataFrame([{
                    "ID": str(uuid.uuid4())[:6].upper(), "納品予定日": str(o_date), "顧客名": c_name if c_name else "未指定",
                    "大カテゴリ": cat, "製品名": prod, "ケース数": int(qty), "登録日時": datetime.now().strftime("%Y-%m-%d %H:%M")
                }])
                save_data("orders", pd.concat([orders_df, new_row], ignore_index=True))
                st.toast(f"✅ {c_name if c_name else '未指定'}様宛 / {prod} ({qty}cs)", icon="📦")
                st.session_state.last_registered = f"{o_date.strftime('%m/%d')} 出荷 | {c_name if c_name else '未指定'} | {prod} | {qty}ケース"
                st.rerun()
            else:
                st.error("⚠️ 製品が正しく選択されていません。")

    with st.expander("🕒 直近の登録履歴を確認・削除"):
        st.dataframe(orders_df.tail(10).sort_values("登録日時", ascending=False), use_container_width=True, hide_index=True)
        del_id = st.text_input("削除するIDを入力（例: O-A1B2C3）")
        if st.button("🗑️ このIDのデータを削除", type="secondary"):
            if del_id:
                save_data("orders", orders_df[orders_df["ID"] != del_id.strip()])
                st.success("削除しました"); st.rerun()

# --- 製造登録 ---
elif page == "🏭 製造登録":
    st.markdown('<div class="modern-header manu"><h1>🏭 製造（入庫）実績の登録</h1></div>', unsafe_allow_html=True)
    
    if st.session_state.last_registered:
        st.success(f"✨ {st.session_state.last_registered}")
        st.session_state.last_registered = None

    with st.container(border=True):
        col1, col2 = st.columns(2)
        m_date = col1.date_input("📅 製造日", value=date.today())
        m_qty = col2.number_input("📦 製造ケース数", min_value=1, value=50, step=10)
        
        st.write("---")
        st.write("📂 **カテゴリを選択**")
        cat_full = st.radio("カテゴリ", CATEGORIES_LIST, horizontal=True, label_visibility="collapsed")
        cat = cat_full.split(" ", 1)[1]
        
        prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
        prod = st.selectbox("📦 製品名を選択", prods if prods else ["(このカテゴリに製品がありません)"], format_func=format_name)
        
        st.write("")
        if st.button("➕ 製造データを記録する", type="primary", use_container_width=True):
            if prod and prod != "(このカテゴリに製品がありません)":
                new_row = pd.DataFrame([{
                    "ID": str(uuid.uuid4())[:6].upper(), "製造予定日": str(m_date), "備考": "",
                    "大カテゴリ": cat, "製品名": prod, "ケース数": int(m_qty), "登録日時": datetime.now().strftime("%Y-%m-%d %H:%M")
                }])
                save_data("manufactures", pd.concat([manus_df, new_row], ignore_index=True))
                st.toast(f"🏭 {prod} ({m_qty}cs)", icon="✅")
                st.session_state.last_registered = f"{m_date.strftime('%m/%d')} 製造 | {prod} | {m_qty}ケース"
                st.rerun()
            else:
                st.error("⚠️ 製品が正しく選択されていません。")

# --- 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="modern-header"><h1>📦 在庫推移とカレンダー</h1></div>', unsafe_allow_html=True)
    
    today = pd.Timestamp.today().normalize()
    dates = pd.date_range(today, today + timedelta(days=14))
    
    t1, t2 = st.tabs(["📊 在庫予測マトリクス", "📆 直近カレンダー (視覚化)"])
    
    with t1:
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
            # 大カテゴリ順に並び替え
            cat_order = [c.split(" ", 1)[1] for c in CATEGORIES_LIST]
            inv_df["カテゴリ順"] = inv_df["大カテゴリ"].apply(lambda x: cat_order.index(x) if x in cat_order else 99)
            inv_df = inv_df.sort_values(["カテゴリ順", "製品名"]).drop(columns=["カテゴリ順", "大カテゴリ"])
            
            st.dataframe(inv_df.style.applymap(lambda x: 'color: #DC2626; font-weight: 900; background-color: #FEE2E2;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True, height=600)
    
    with t2:
        st.write("1日の出入りをプログレスバー（最大100ケース想定）で視覚的に表現しています。")
        MAX_CASES = 100
        
        html = '<table class="sched-table"><tr><th style="width:100px;">日付</th><th style="width:45%;">🏭 製造予定 (入庫)</th><th style="width:45%;">📋 出荷予定 (出庫)</th></tr>'
        for i in range(7):
            d = today + timedelta(days=i)
            m_items = manus_df[manus_df["製造予定日"] == d]
            o_items = orders_df[orders_df["納品予定日"] == d]
            
            m_html = ""
            for _, r in m_items.iterrows():
                pct = min(100, int((r["ケース数"] / MAX_CASES) * 100))
                m_html += f"""
                <div class="event-card manu-card">
                    <div class="event-bg-bar" style="width: {pct}%;"></div>
                    <div class="event-text">{format_name(r["製品名"])} <span class="event-qty">{r["ケース数"]}cs</span></div>
                </div>"""
                
            o_html = ""
            for _, r in o_items.iterrows():
                pct = min(100, int((r["ケース数"] / MAX_CASES) * 100))
                o_html += f"""
                <div class="event-card">
                    <div class="event-bg-bar" style="width: {pct}%;"></div>
                    <div class="event-text">{r["顧客名"]}: {format_name(r["製品名"])} <span class="event-qty">{r["ケース数"]}cs</span></div>
                </div>"""
                
            html += f'<tr><td><b style="font-size:16px;">{d.strftime("%m/%d")}</b></td><td>{m_html}</td><td>{o_html}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)

# --- 統計分析 ---
elif page == "📊 統計・分析":
    st.markdown('<div class="modern-header stat"><h1>📊 出荷データの傾向分析</h1></div>', unsafe_allow_html=True)
    
    if orders_df.empty:
        st.info("分析するデータがありません。")
    else:
        total_cs = orders_df["ケース数"].sum()
        total_customers = orders_df[orders_df["顧客名"] != "未指定"]["顧客名"].nunique()
        c1, c2, c3 = st.columns(3)
        c1.metric("総出荷ケース数", f"{total_cs:,} cs")
        c2.metric("総受注件数", f"{len(orders_df):,} 件")
        c3.metric("取引先数", f"{total_customers} 社")
        
        st.write("---")
        t1, t2, t3 = st.tabs(["📈 月別トレンド", "🏢 顧客別ランキング", "📦 製品別シェア"])
        
        with t1:
            orders_df["年月"] = orders_df["納品予定日"].dt.strftime("%Y-%m")
            trend_df = orders_df.groupby(["年月","大カテゴリ"])["ケース数"].sum().reset_index()
            fig = px.bar(trend_df, x="年月", y="ケース数", color="大カテゴリ", barmode="stack", title="月別・カテゴリ別 出荷数推移")
            st.plotly_chart(fig, use_container_width=True)
            
        with t2:
            cust_df_stat = orders_df[orders_df["顧客名"] != "未指定"].groupby("顧客名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False).head(15)
            fig2 = px.bar(cust_df_stat, x="ケース数", y="顧客名", orientation='h', title="得意先ランキング (TOP 15)")
            fig2.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig2, use_container_width=True)
            
        with t3:
            prod_df = orders_df.groupby("大カテゴリ")["ケース数"].sum().reset_index()
            fig3 = px.pie(prod_df, values="ケース数", names="大カテゴリ", hole=0.4, title="カテゴリ別 出荷シェア")
            st.plotly_chart(fig3, use_container_width=True)

# --- マスタ管理 ---
elif page == "⚙️ マスタ管理":
    st.markdown('<div class="modern-header" style="background:linear-gradient(135deg, #475569 0%, #1E293B 100%);"><h1>⚙️ マスタ・設定管理</h1></div>', unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["📦 製品マスタ（棚卸・初期在庫）", "🏢 顧客マスタ（ふりがな）"])
    
    with t1:
        st.info("💡 実際の在庫数を「初期在庫数」に入力して保存すると、そこを起点に在庫計算がリセットされます。")
        ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 製品マスタを保存する", type="primary"):
            save_data("master", ed_m)
            st.toast("✅ 製品情報を更新しました")
            st.rerun()
            
    with t2:
        st.write("「ふりがな」を登録しておくと、受注登録時のドロップダウンでひらがな検索ができるようになります。")
        ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 顧客マスタを保存する", type="primary"):
            save_data("customers", ed_c)
            st.toast("✅ 顧客情報を更新しました")
            st.rerun()
