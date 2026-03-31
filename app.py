"""
丸実屋 受注・製造・在庫管理アプリ (Apple風モダンUI・完全安定・爆速版)
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
# 2. Apple風モダンCSS (安全で崩れない設計)
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* ベースフォントと背景色（Apple風の洗練されたグレーとSan Franciscoフォント） */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #F5F5F7 !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Noto Sans JP" !important;
        color: #1D1D1F !important;
    }
    
    /* すべてのテキストの基本色を固定（文字消失防止） */
    p, span, div, label, h1, h2, h3, h4, .stMarkdown {
        color: #1D1D1F !important;
    }

    /* ヘッダーのグラデーション */
    .apple-header {
        background: linear-gradient(135deg, #0071E3 0%, #004799 100%);
        padding: 30px;
        border-radius: 18px;
        margin-bottom: 24px;
        box-shadow: 0 10px 30px rgba(0, 113, 227, 0.2);
    }
    .apple-header h1 { color: #FFFFFF !important; margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.02em; }
    .header-manu { background: linear-gradient(135deg, #34C759 0%, #1E823D 100%); box-shadow: 0 10px 30px rgba(52, 199, 89, 0.2); }
    .header-stat { background: linear-gradient(135deg, #5E5CE6 0%, #3634A3 100%); box-shadow: 0 10px 30px rgba(94, 92, 230, 0.2); }

    /* Streamlit標準コンテナ(st.container)の見た目をカード風に上書き */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF !important;
        border-radius: 18px !important;
        border: 1px solid #E5E5EA !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04) !important;
        padding: 24px !important;
    }

    /* スケジュール表（500ケース対応プログレスバー） */
    .sched-table { width: 100%; border-collapse: separate; border-spacing: 0; }
    .sched-table th { background: #F5F5F7; color: #86868B !important; font-weight: 600; padding: 14px; text-align: left; border-bottom: 1px solid #D2D2D7; font-size: 14px; }
    .sched-table td { padding: 14px; border-bottom: 1px solid #E5E5EA; vertical-align: top; }
    
    .event-bar {
        position: relative; background-color: #F5F5F7; border-left: 4px solid #0071E3;
        border-radius: 8px; padding: 10px 14px; margin-bottom: 8px; overflow: hidden; z-index: 1;
    }
    .event-bar.manu { border-left-color: #34C759; }
    
    .event-bg { position: absolute; top: 0; left: 0; height: 100%; background-color: #E8F0FE; z-index: -1; }
    .event-bar.manu .event-bg { background-color: #E8F8F0; }
    
    .event-text { font-size: 14px; font-weight: 600; color: #1D1D1F; }
    .event-qty { float: right; font-weight: 800; color: #0071E3; font-size: 15px; }
    .event-bar.manu .event-qty { color: #34C759; }

    /* サイドバーの色 */
    [data-testid="stSidebar"] { background-color: #1D1D1F !important; }
    [data-testid="stSidebar"] * { color: #F5F5F7 !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. パスワード認証
# ─────────────────────────────────────────────
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    
    if not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align:center; margin-top:80px; color:#0071E3;'>🏭 丸実屋システム ログイン</h2>", unsafe_allow_html=True)
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

@st.cache_data(ttl=3600)
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

# 新規追加を「行追加(append)」にすることで、全書き換えの重さを解消（爆速化）
def append_order(row_data):
    sheet.worksheet("orders").append_row(row_data)
    load_orders.clear()

def append_manu(row_data):
    sheet.worksheet("manufactures").append_row(row_data)
    load_manus.clear()

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

# データロード
orders_df = load_orders()
manus_df = load_manus()
master_df = load_master()
cust_df = load_cust()

if "success_msg" not in st.session_state:
    st.session_state.success_msg = None

# ─────────────────────────────────────────────
# 6. サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h2 style='font-weight:900;'>🏭 丸実屋システム</h2>", unsafe_allow_html=True)
    st.write("---")
    page = st.radio("メニュー", ["📋 受注登録", "🏭 製造登録", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"])

# ─────────────────────────────────────────────
# 7. 画面の描画
# ─────────────────────────────────────────────

# --- 受注登録 ---
if page == "📋 受注登録":
    st.markdown('<div class="apple-header"><h1>📋 受注（出荷予定）の登録</h1></div>', unsafe_allow_html=True)
    
    with st.container(border=True):
        col1, col2, col3 = st.columns([1.2, 2.5, 1])
        o_date = col1.date_input("📅 納品予定日", value=date.today() + timedelta(days=1))
        
        # 顧客名：空欄初期化。漢字のみのリスト（IMEで漢字変換して検索してもらう）
        cust_names = sorted(cust_df[cust_df["顧客名"].str.strip() != ""]["顧客名"].unique().tolist())
        c_name = col2.selectbox("🏢 顧客名（入力・変換して検索）", options=cust_names, index=None, placeholder="空白（クリックして入力）")
        
        qty = col3.number_input("📦 出荷ケース数", min_value=1, value=None, step=1, placeholder="数値を入力")

        st.write("---")
        st.markdown("### 📂 カテゴリを選択")
        
        # 【新機能】Streamlit公式の「Pills（ボタン式選択）」を安全に呼び出す
        try:
            cat_full = st.pills("カテゴリ", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
            if not cat_full: cat_full = CATEGORIES[0] # 選択解除された場合のガード
        except AttributeError:
            # 古いバージョンのフォールバック
            cat_full = st.radio("カテゴリ", CATEGORIES, horizontal=True, label_visibility="collapsed")
            
        cat = cat_full.split(" ", 1)[1]
        
        prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
        prod = st.selectbox("📦 製品名", options=prods, index=None, placeholder="製品を選んでください", format_func=format_name)
        
        st.write("")
        submit_btn = st.button("✅ 受注を登録する (続けて入力できます)", type="primary", use_container_width=True)
        msg_area = st.empty() # エラーメッセージ用
        
        if submit_btn:
            if not prod or not qty:
                msg_area.error("⚠️ 製品とケース数を入力してください。")
            else:
                c_val = c_name if c_name else "未指定"
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                row_data = [str(uuid.uuid4())[:6].upper(), o_date.strftime('%Y-%m-%d'), c_val, cat, prod, int(qty), now_str]
                append_order(row_data)
                
                st.session_state.success_msg = f"✨ 登録完了： {o_date.strftime('%m/%d')} 出荷 ｜ {c_val} 様宛 ｜ {prod} ({qty}cs)"
                st.rerun()
                
    if st.session_state.success_msg:
        st.success(st.session_state.success_msg)
        st.session_state.success_msg = None

    with st.expander("🕒 直近の登録履歴を確認・削除"):
        st.dataframe(orders_df.tail(10).sort_values("登録日時", ascending=False), use_container_width=True, hide_index=True)
        del_id = st.text_input("削除するIDを入力（例: O-123456）")
        if st.button("🗑️ データを削除", type="secondary"):
            if del_id:
                save_data("orders", orders_df[orders_df["ID"] != del_id.strip()]); st.success("削除しました"); st.rerun()

# --- 製造登録 ---
elif page == "🏭 製造登録":
    st.markdown('<div class="apple-header header-manu"><h1>🏭 製造（入庫）の登録</h1></div>', unsafe_allow_html=True)
    
    with st.container(border=True):
        col1, col2 = st.columns(2)
        m_date = col1.date_input("📅 製造日", value=date.today())
        # 初期値を空白 (None) に設定
        m_qty = col2.number_input("📦 製造ケース数", min_value=1, value=None, step=10, placeholder="数値を入力")
        
        st.write("---")
        st.markdown("### 📂 カテゴリを選択")
        try:
            cat_full = st.pills("カテゴリ", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
            if not cat_full: cat_full = CATEGORIES[0]
        except AttributeError:
            cat_full = st.radio("カテゴリ", CATEGORIES, horizontal=True, label_visibility="collapsed")
            
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
    st.markdown('<div class="apple-header"><h1>📦 在庫推移とスケジュール</h1></div>', unsafe_allow_html=True)
    
    today = pd.Timestamp.today().normalize()
    dates = pd.date_range(today, today + timedelta(days=14))
    
    t1, t2 = st.tabs(["📅 直近スケジュール (バー表示)", "📉 在庫予測マトリクス"])
    
    with t1:
        st.write("1日の出入りを視覚的に表現しています（バーの長さは **500ケース** を最大値としています）。")
        MAX_CASES = 500 # 500ケース想定に引き上げ
        
        html = '<table class="sched-table"><tr><th style="width:120px;">日付</th><th style="width:40%;">🏭 製造予定 (入庫)</th><th style="width:40%;">📋 出荷予定 (出庫)</th></tr>'
        for i in range(7):
            d = today + timedelta(days=i)
            m_items = manus_df[manus_df["製造予定日"] == d]
            o_items = orders_df[orders_df["納品予定日"] == d]
            
            m_html = ""
            for _, r in m_items.iterrows():
                pct = min(100, int((r["ケース数"] / MAX_CASES) * 100))
                m_html += f"""
                <div class="event-bar manu">
                    <div class="event-bg" style="width: {pct}%;"></div>
                    <span class="event-text">{format_name(r["製品名"])}</span>
                    <span class="event-qty">{r["ケース数"]} cs</span>
                </div>"""
                
            o_html = ""
            for _, r in o_items.iterrows():
                pct = min(100, int((r["ケース数"] / MAX_CASES) * 100))
                o_html += f"""
                <div class="event-bar">
                    <div class="event-bg" style="width: {pct}%;"></div>
                    <span class="event-text">{r["顧客名"]}: {format_name(r["製品名"])}</span>
                    <span class="event-qty">{r["ケース数"]} cs</span>
                </div>"""
                
            html += f'<tr><td><b style="font-size:18px; color:#1D1D1F;">{d.strftime("%m/%d")}</b><br><span style="font-size:12px; color:#86868B;">{["月","火","水","木","金","土","日"][d.dayofweek]}曜日</span></td><td>{m_html}</td><td>{o_html}</td></tr>'
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
    st.markdown('<div class="apple-header header-stat"><h1>📊 統計・分析ダッシュボード</h1></div>', unsafe_allow_html=True)
    
    if orders_df.empty:
        st.info("データがありません。")
    else:
        with st.container(border=True):
            col1, col2, col3 = st.columns(3)
            col1.metric("📦 総出荷ケース数", f"{orders_df['ケース数'].sum():,} cs")
            col2.metric("📋 総受注件数", f"{len(orders_df):,} 件")
            col3.metric("🏢 取引先数", f"{orders_df[orders_df['顧客名'] != '未指定']['顧客名'].nunique()} 社")
        
        orders_df["年月"] = orders_df["納品予定日"].dt.strftime("%Y-%m")
        
        c_left, c_right = st.columns(2)
        with c_left:
            with st.container(border=True):
                st.write("📈 **月別・カテゴリ別の出荷数トレンド**")
                trend_df = orders_df.groupby(["年月","大カテゴリ"])["ケース数"].sum().reset_index()
                fig = px.bar(trend_df, x="年月", y="ケース数", color="大カテゴリ", barmode="stack")
                st.plotly_chart(fig, use_container_width=True)
            
        with c_right:
            with st.container(border=True):
                st.write("🏆 **お得意様ランキング (TOP 10)**")
                cust_stat = orders_df[orders_df["顧客名"] != "未指定"].groupby("顧客名")["ケース数"].sum().reset_index().sort_values("ケース数", ascending=False).head(10)
                fig2 = px.bar(cust_stat, x="ケース数", y="顧客名", orientation='h')
                fig2.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig2, use_container_width=True)

# --- マスタ管理 ---
elif page == "⚙️ マスタ管理":
    st.markdown('<div class="apple-header" style="background:linear-gradient(135deg, #475569 0%, #1d1d1f 100%);"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["📦 製品マスタ（棚卸・初期在庫）", "🏢 顧客マスタ"])
    with t1:
        with st.container(border=True):
            st.info("💡 実際の在庫数を「初期在庫数」に入力して保存すると、そこを起点に在庫計算がリセットされます。")
            ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True, height=500)
            if st.button("💾 製品マスタを保存", type="primary"):
                save_master_data("master", ed_m)
                st.toast("✅ 製品情報を更新しました")
                st.rerun()
            
    with t2:
        with st.container(border=True):
            st.write("※ひらがなの列は現在使用していませんが、将来的な拡張のために残してあります。")
            ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True, height=500)
            if st.button("💾 顧客マスタを保存", type="primary"):
                save_master_data("customers", ed_c)
                st.toast("✅ 顧客情報を更新しました")
                st.rerun()
