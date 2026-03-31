"""
丸実屋 受注・製造・在庫管理アプリ (爆速・モダン・安全版)
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
st.set_page_config(page_title="丸実屋 受注・在庫管理", page_icon="🏭", layout="wide")

# ─────────────────────────────────────────────
# 2. 安全なモダンCSS（ウィジェットを壊さない装飾のみ）
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* ヘッダーのデザイン */
    .modern-header {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 24px;
        border-radius: 12px;
        color: white;
        margin-bottom: 24px;
        box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.3);
    }
    .modern-header h1 { color: white !important; margin: 0; font-size: 26px; font-weight: bold; }
    .header-manu { background: linear-gradient(135deg, #064e3b 0%, #10b981 100%); box-shadow: 0 4px 6px -1px rgba(16, 185, 129, 0.3); }
    .header-stat { background: linear-gradient(135deg, #4c1d95 0%, #8b5cf6 100%); box-shadow: 0 4px 6px -1px rgba(139, 92, 246, 0.3); }

    /* スケジュール表（プログレスバー）のデザイン */
    .sched-table { width: 100%; border-collapse: separate; border-spacing: 0; background: transparent; }
    .sched-table th { background-color: #f8fafc; color: #475569; padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; }
    .sched-table td { padding: 10px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
    
    .event-bar-container { position: relative; background-color: #f1f5f9; border-left: 4px solid #3b82f6; border-radius: 6px; padding: 8px 12px; margin-bottom: 8px; overflow: hidden; z-index: 1; }
    .event-bar-container.manu { border-left-color: #10b981; }
    
    .event-bg { position: absolute; top: 0; left: 0; height: 100%; background-color: #dbeafe; z-index: -1; }
    .event-bar-container.manu .event-bg { background-color: #d1fae5; }
    
    .event-text { font-size: 13px; font-weight: 600; color: #1e293b; }
    .event-qty { float: right; font-weight: 900; color: #1d4ed8; }
    .event-bar-container.manu .event-qty { color: #047857; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. パスワード認証
# ─────────────────────────────────────────────
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    
    if not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align:center; margin-top:50px;'>🏭 丸実屋システム ログイン</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.container(border=True):
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
# 4. Googleスプレッドシート連携（独立キャッシュで爆速化）
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

# 読み込みをシートごとに独立させ、他シートの無駄な通信を削減
@st.cache_data(ttl=600)
def load_orders():
    data = sheet.worksheet("orders").get_all_values()
    cols = ["ID", "納品予定日", "顧客名", "大カテゴリ", "製品名", "ケース数", "登録日時"]
    if len(data) <= 1: return pd.DataFrame(columns=cols)
    df = pd.DataFrame(data[1:], columns=data[0])
    df["ケース数"] = pd.to_numeric(df["ケース数"], errors='coerce').fillna(0).astype(int)
    df["納品予定日"] = pd.to_datetime(df["納品予定日"], errors='coerce')
    return df

@st.cache_data(ttl=600)
def load_manus():
    data = sheet.worksheet("manufactures").get_all_values()
    cols = ["ID", "製造予定日", "備考", "大カテゴリ", "製品名", "ケース数", "登録日時"]
    if len(data) <= 1: return pd.DataFrame(columns=cols)
    df = pd.DataFrame(data[1:], columns=data[0])
    df["ケース数"] = pd.to_numeric(df["ケース数"], errors='coerce').fillna(0).astype(int)
    df["製造予定日"] = pd.to_datetime(df["製造予定日"], errors='coerce')
    return df

@st.cache_data(ttl=3600) # マスタは1時間キャッシュ
def load_master():
    data = sheet.worksheet("master").get_all_values()
    cols = ["大カテゴリ", "製品名", "初期在庫数"]
    if len(data) <= 1: return pd.DataFrame(columns=cols)
    df = pd.DataFrame(data[1:], columns=data[0])
    df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors='coerce').fillna(0).astype(int)
    return df

@st.cache_data(ttl=3600)
def load_cust():
    data = sheet.worksheet("customers").get_all_values()
    cols = ["顧客名", "ふりがな"]
    if len(data) <= 1: return pd.DataFrame(columns=cols)
    return pd.DataFrame(data[1:], columns=data[0])

# 新規追加を「行追加(append)」にすることで、全書き換えの重さを解消（爆速）
def append_order(row_data):
    sheet.worksheet("orders").append_row(row_data)
    load_orders.clear() # ordersのキャッシュだけ消す

def append_manu(row_data):
    sheet.worksheet("manufactures").append_row(row_data)
    load_manus.clear()

# マスタ編集用（全上書き）
def save_master_data(sheet_name, df):
    ws = sheet.worksheet(sheet_name)
    ws.clear()
    df_str = df.fillna("").astype(str)
    ws.update(values=[df_str.columns.values.tolist()] + df_str.values.tolist(), range_name='A1')
    if sheet_name == "master": load_master.clear()
    if sheet_name == "customers": load_cust.clear()

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

# データロード（キャッシュが効くため一瞬）
orders_df = load_orders()
manus_df = load_manus()
master_df = load_master()
cust_df = load_cust()

# 登録完了メッセージ用のセッション
if "success_msg" not in st.session_state:
    st.session_state.success_msg = None

# ─────────────────────────────────────────────
# 6. サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.title("🏭 丸実屋システム")
    st.write("---")
    page = st.radio("メニュー", ["📋 受注登録", "🏭 製造登録", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"])

# ─────────────────────────────────────────────
# 7. 画面の描画
# ─────────────────────────────────────────────

# --- 受注登録 ---
if page == "📋 受注登録":
    st.markdown('<div class="modern-header"><h1>📋 受注（出荷予定）の登録</h1></div>', unsafe_allow_html=True)
    
    with st.container(border=True):
        col1, col2, col3 = st.columns([1, 2, 1])
        o_date = col1.date_input("📅 納品予定日", value=date.today() + timedelta(days=1))
        
        # 顧客名：空欄初期化。漢字のみのリスト（ひらがなは表示せず、IMEで変換してもらう）
        cust_names = sorted(cust_df[cust_df["顧客名"].str.strip() != ""]["顧客名"].unique().tolist())
        c_name = col2.selectbox("🏢 顧客名（入力して検索）", options=cust_names, index=None, placeholder="顧客名を選択または検索...")
        
        qty = col3.number_input("📦 出荷ケース数", min_value=1, value=1, step=1)

        st.write("---")
        cat_full = st.radio("📂 カテゴリを選択", CATEGORIES, horizontal=True)
        cat = cat_full.split(" ", 1)[1]
        
        prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
        prod = st.selectbox("📦 製品名", options=prods, index=None, placeholder="製品を選んでください", format_func=format_name)
        
        st.write("")
        submit_btn = st.button("✅ 受注を登録する", type="primary", use_container_width=True)
        
        # メッセージ表示領域（ボタンのすぐ下）
        msg_area = st.empty()
        
        if submit_btn:
            if not prod:
                msg_area.error("⚠️ 製品を選択してください。")
            else:
                c_val = c_name if c_name else "未指定"
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # 行として追加（超高速）
                row_data = [str(uuid.uuid4())[:6].upper(), o_date.strftime('%Y-%m-%d'), c_val, cat, prod, int(qty), now_str]
                append_order(row_data)
                
                st.session_state.success_msg = f"✨ 登録完了： {o_date.strftime('%m/%d')} 出荷 ｜ {c_val} 様宛 ｜ {prod} ({qty}cs)"
                st.rerun()
                
    # リラン後にメッセージを表示
    if st.session_state.success_msg:
        st.success(st.session_state.success_msg)
        st.session_state.success_msg = None

    with st.expander("🕒 直近の登録履歴を確認"):
        st.dataframe(orders_df.tail(10).sort_values("登録日時", ascending=False), use_container_width=True, hide_index=True)

# --- 製造登録 ---
elif page == "🏭 製造登録":
    st.markdown('<div class="modern-header header-manu"><h1>🏭 製造（入庫）の登録</h1></div>', unsafe_allow_html=True)
    
    with st.container(border=True):
        col1, col2 = st.columns(2)
        m_date = col1.date_input("📅 製造日", value=date.today())
        
        # 初期値を空白 (None) に設定
        m_qty = col2.number_input("📦 製造ケース数", min_value=1, value=None, step=10, placeholder="数字を入力...")
        
        st.write("---")
        cat_full = st.radio("📂 カテゴリを選択", CATEGORIES, horizontal=True)
        cat = cat_full.split(" ", 1)[1]
        
        prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
        prod = st.selectbox("📦 製品名", options=prods, index=None, placeholder="製品を選んでください", format_func=format_name)
        
        st.write("")
        submit_btn = st.button("➕ 製造データを記録する", type="primary", use_container_width=True)
        
        msg_area = st.empty()
        
        if submit_btn:
            if not prod or not m_qty:
                msg_area.error("⚠️ 製品と製造ケース数を入力してください。")
            else:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                row_data = [str(uuid.uuid4())[:6].upper(), m_date.strftime('%Y-%m-%d'), "", cat, prod, int(m_qty), now_str]
                append_manu(row_data)
                
                st.session_state.success_msg = f"✨ 登録完了： {m_date.strftime('%m/%d')} 製造 ｜ {prod} ({m_qty}cs)"
                st.rerun()

    if st.session_state.success_msg:
        st.success(st.session_state.success_msg)
        st.session_state.success_msg = None

# --- 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="modern-header"><h1>📦 在庫推移とスケジュール</h1></div>', unsafe_allow_html=True)
    
    today = pd.Timestamp.today().normalize()
    dates = pd.date_range(today, today + timedelta(days=14))
    
    t1, t2 = st.tabs(["📅 直近スケジュール (バー表示)", "📉 在庫予測マトリクス"])
    
    with t1:
        st.write("1日の出入りを視覚的に表現しています（バーの長さは100ケースを最大としています）。")
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
                <div class="event-bar-container manu">
                    <div class="event-bg" style="width: {pct}%;"></div>
                    <span class="event-text">{format_name(r["製品名"])}</span>
                    <span class="event-qty">{r["ケース数"]} cs</span>
                </div>"""
                
            o_html = ""
            for _, r in o_items.iterrows():
                pct = min(100, int((r["ケース数"] / MAX_CASES) * 100))
                o_html += f"""
                <div class="event-bar-container">
                    <div class="event-bg" style="width: {pct}%;"></div>
                    <span class="event-text">{r["顧客名"]}: {format_name(r["製品名"])}</span>
                    <span class="event-qty">{r["ケース数"]} cs</span>
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
            st.dataframe(inv_df.style.map(lambda x: 'color: #dc2626; font-weight: 900; background-color: #fee2e2;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True, height=600)

# --- 統計分析 ---
elif page == "📊 統計・分析":
    st.markdown('<div class="modern-header header-stat"><h1>📊 統計・分析ダッシュボード</h1></div>', unsafe_allow_html=True)
    
    if orders_df.empty:
        st.info("データがありません。")
    else:
        # メトリクス表示
        col1, col2, col3 = st.columns(3)
        col1.metric("📦 総出荷ケース数", f"{orders_df['ケース数'].sum():,} cs")
        col2.metric("📋 総受注件数", f"{len(orders_df):,} 件")
        col3.metric("🏢 取引先数", f"{orders_df[orders_df['顧客名'] != '未指定']['顧客名'].nunique()} 社")
        
        st.write("---")
        orders_df["年月"] = orders_df["納品予定日"].dt.strftime("%Y-%m")
        
        c_left, c_right = st.columns(2)
        with c_left:
            st.write("📈 **月別・カテゴリ別の出荷数トレンド**")
            trend_df = orders_df.groupby(["年月","大カテゴリ"])["ケース数"].sum().reset_index()
            fig = px.bar(trend_df, x="年月", y="ケース数", color="大カテゴリ", barmode="stack")
            st.plotly_chart(fig, use_container_width=True)
            
        with c_right:
            st.write("🏆 **お得意様ランキング (TOP 10)**")
            cust_stat = orders_df[orders_df["顧客名"] != "未指定"].groupby("顧客名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False).head(10)
            fig2 = px.bar(cust_stat, x="ケース数", y="顧客名", orientation='h')
            fig2.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig2, use_container_width=True)

# --- マスタ管理 ---
elif page == "⚙️ マスタ管理":
    st.markdown('<div class="modern-header" style="background:#475569;"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["📦 製品マスタ（棚卸・初期在庫）", "🏢 顧客マスタ"])
    with t1:
        st.info("💡 棚卸した際の実際の在庫数を「初期在庫数」に入力して保存すると、そこを起点に在庫計算がリセットされます。")
        ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 製品マスタを保存"):
            save_master_data("master", ed_m)
            st.success("製品情報を更新しました")
            st.rerun()
            
    with t2:
        ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True, height=500)
        if st.button("💾 顧客マスタを保存"):
            save_master_data("customers", ed_c)
            st.success("顧客情報を更新しました")
            st.rerun()
