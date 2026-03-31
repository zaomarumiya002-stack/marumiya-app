"""
丸実屋 受注・製造・在庫管理アプリ (かんたん修正機能・爆速・完全安定版)
"""

import os
# 【超重要】Streamlitの標準テーマを強制的に「明るく清潔な配色」に固定。これで絶対に文字が消えません。
os.environ["STREAMLIT_THEME_BASE"] = "light"
os.environ["STREAMLIT_THEME_PRIMARY_COLOR"] = "#2563EB" # 鮮やかなブルー
os.environ["STREAMLIT_THEME_BACKGROUND_COLOR"] = "#F4F7F9" # 全体の背景（ごく薄いグレー）
os.environ["STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR"] = "#E2E8F0" # サイドバーの背景
os.environ["STREAMLIT_THEME_TEXT_COLOR"] = "#1E293B" # 文字は濃い紺色（黒に近い）

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
# 2. 安全なCSS（絶対に文字を隠さない装飾のみ）
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* 全体のフォントを大きく見やすく */
    html, body, [class*="css"] {
        font-family: 'Noto Sans JP', sans-serif !important;
        font-size: 16px;
    }

    /* ヘッダーパネル（グラデーション） */
    .main-header {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        padding: 24px 32px;
        border-radius: 12px;
        color: white;
        margin-bottom: 24px;
        box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3);
    }
    .main-header h1 { color: #FFFFFF !important; margin: 0; font-size: 28px; font-weight: 900; }
    .header-manu { background: linear-gradient(135deg, #064E3B 0%, #10B981 100%); box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3); }

    /* サイドバーの文字サイズを大きく */
    [data-testid="stSidebar"] div[role="radiogroup"] label p {
        font-size: 18px !important;
        font-weight: bold !important;
    }

    /* スケジュール表 */
    .sched-table { width: 100%; border-collapse: separate; border-spacing: 0; background: #FFFFFF; border-radius: 12px; overflow: hidden; border: 1px solid #CBD5E1; }
    .sched-table th { background: #F1F5F9; color: #334155 !important; padding: 14px; text-align: left; border-bottom: 2px solid #CBD5E1; font-size: 15px; }
    .sched-table td { padding: 12px; border-bottom: 1px solid #E2E8F0; vertical-align: top; }
    
    /* スケジュールのプログレスバー */
    .event-bar { position: relative; background: #F8FAFC; border-left: 5px solid #3B82F6; border-radius: 6px; padding: 10px 14px; margin-bottom: 8px; z-index: 1; }
    .event-bar.manu { border-left-color: #10B981; }
    .event-bg { position: absolute; top: 0; left: 0; height: 100%; background: #DBEAFE; z-index: -1; }
    .event-bar.manu .event-bg { background: #D1FAE5; }
    .event-text { font-size: 15px; font-weight: 700; color: #0F172A; }
    .event-qty { float: right; font-weight: 900; color: #1D4ED8; font-size: 16px; }
    .event-bar.manu .event-qty { color: #047857; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. パスワード認証
# ─────────────────────────────────────────────
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    
    if not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align:center; margin-top:50px; color:#1E3A8A;'>🏭 丸実屋システム ログイン</h2>", unsafe_allow_html=True)
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
# 4. Googleスプレッドシート連携（独立キャッシュで爆速）
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

@st.cache_data(ttl=600)
def load_data(sheet_name):
    ws = sheet.worksheet(sheet_name)
    data = ws.get_all_values()
    cols = {"orders":["ID","納品予定日","顧客名","大カテゴリ","製品名","ケース数","登録日時"],
            "manufactures":["ID","製造予定日","備考","大カテゴリ","製品名","ケース数","登録日時"],
            "master":["大カテゴリ","製品名","初期在庫数"],
            "customers":["顧客名","ふりがな"]}[sheet_name]
    if len(data) <= 1: return pd.DataFrame(columns=cols)
    df = pd.DataFrame(data[1:], columns=data[0])
    
    if "ケース数" in df.columns: df["ケース数"] = pd.to_numeric(df["ケース数"], errors='coerce').fillna(0).astype(int)
    if "初期在庫数" in df.columns: df["初期在庫数"] = pd.to_numeric(df["初期在庫数"], errors='coerce').fillna(0).astype(int)
    if "納品予定日" in df.columns: df["納品予定日"] = pd.to_datetime(df["納品予定日"], errors='coerce')
    if "製造予定日" in df.columns: df["製造予定日"] = pd.to_datetime(df["製造予定日"], errors='coerce')
    return df

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

# ★ 爆速で1行だけ追加する関数 ★
def append_row(sheet_name, row_data):
    sheet.worksheet(sheet_name).append_row(row_data)
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

orders_df = load_data("orders")
manus_df = load_data("manufactures")
master_df = load_data("master")
cust_df = load_data("customers")

if "success_msg" not in st.session_state:
    st.session_state.success_msg = None

# ─────────────────────────────────────────────
# 6. サイドバー（安全な標準メニュー）
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h2 style='font-size:26px; font-weight:900;'>🏭 丸実屋システム</h2>", unsafe_allow_html=True)
    st.write("---")
    page = st.radio(
        "メニューを選択", 
        ["📋 受注登録 (出庫)", "🏭 製造登録 (入庫)", "📦 在庫・スケジュール", "📊 統計・分析", "⚙️ マスタ管理"],
        label_visibility="collapsed"
    )

# ─────────────────────────────────────────────
# 7. 各画面の描画
# ─────────────────────────────────────────────

# --- 受注登録 ---
if page == "📋 受注登録 (出庫)":
    st.markdown('<div class="main-header"><h1>📋 受注（出荷予定）の管理</h1></div>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["➕ 新規登録 ＆ かんたん修正", "⚙️ 全データ一覧・詳細検索"])
    
    with tab1:
        with st.container(border=True):
            st.markdown("### 📝 新規入力フォーム")
            col1, col2, col3 = st.columns([1.2, 2.5, 1])
            o_date = col1.date_input("📅 納品予定日", value=date.today() + timedelta(days=1))
            
            # 顧客名：ひらがなを非表示にし、漢字のリストのみにする。入力は「空白」からスタート
            cust_names = sorted(cust_df[cust_df["顧客名"].str.strip() != ""]["顧客名"].unique().tolist())
            c_name = col2.selectbox("🏢 顧客名（漢字変換で検索）", options=cust_names, index=None, placeholder="空欄（クリックして入力）")
            
            qty = col3.number_input("📦 出荷ケース数", min_value=1, value=None, step=1, placeholder="数字を入力")

            st.write("---")
            st.write("### 📂 カテゴリを選択（ボタンをクリック）")
            
            # ★ Streamlit公式のボタン型選択（Pills）で文字全体をボタン化
            try:
                cat_full = st.pills("カテゴリ", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
                if not cat_full: cat_full = CATEGORIES[0]
            except AttributeError:
                cat_full = st.radio("カテゴリ", CATEGORIES, horizontal=True, label_visibility="collapsed")
                
            cat = cat_full.split(" ", 1)[1]
            
            prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
            prod = st.selectbox("📦 製品名を選択", options=prods, index=None, placeholder="製品を選んでください", format_func=format_name)
            
            st.write("")
            submit_btn = st.button("✅ 受注を登録する (続けて入力できます)", type="primary", use_container_width=True)
            msg_area = st.empty()
            
            if submit_btn:
                if not prod or not qty:
                    msg_area.error("⚠️ 製品とケース数を入力してください。")
                else:
                    c_val = c_name if c_name else "未指定"
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    row_data = [str(uuid.uuid4())[:6].upper(), o_date.strftime('%Y-%m-%d'), c_val, cat, prod, int(qty), now_str]
                    append_row("orders", row_data)
                    
                    st.session_state.success_msg = f"✨ 登録完了： {o_date.strftime('%m/%d')} 出荷 ｜ {c_val} 様宛 ｜ {prod} ({qty}cs)"
                    st.rerun()
                    
        if st.session_state.success_msg:
            st.success(st.session_state.success_msg)
            st.session_state.success_msg = None

        # ★ 【新機能】直近5件のかんたん修正機能
        st.write("---")
        st.markdown("### ✏️ かんたん修正（直近登録5件）")
        st.info("💡 下の表の文字や数字を直接クリックして書き換え、「修正を保存」を押すだけで変更できます。行を選択してDeleteキーで削除も可能です。")
        
        recent_orders = orders_df.sort_values("登録日時", ascending=False).head(5)
        recent_ids_before = recent_orders["ID"].tolist()
        
        edited_recent = st.data_editor(recent_orders, use_container_width=True, hide_index=True, num_rows="dynamic", key="editor_recent_o")
        
        if st.button("💾 直近5件の修正・削除を保存", type="primary"):
            edited_ids = edited_recent["ID"].tolist()
            deleted_ids = [uid for uid in recent_ids_before if uid not in edited_ids]
            
            # 削除を反映しつつ、編集された内容を上書き
            new_df = orders_df[~orders_df["ID"].isin(deleted_ids)].copy()
            for _, row in edited_recent.iterrows():
                r_id = row["ID"]
                if r_id in new_df["ID"].values:
                    idx = new_df[new_df["ID"] == r_id].index[0]
                    new_df.at[idx, "納品予定日"] = pd.to_datetime(row["納品予定日"])
                    new_df.at[idx, "顧客名"] = row["顧客名"]
                    new_df.at[idx, "大カテゴリ"] = row["大カテゴリ"]
                    new_df.at[idx, "製品名"] = row["製品名"]
                    new_df.at[idx, "ケース数"] = int(row["ケース数"])
            
            save_data("orders", new_df)
            st.success("修正を保存しました！")
            st.rerun()

    with tab2:
        st.info("💡 全データの確認・修正が可能です。")
        edited_all = st.data_editor(orders_df.sort_values("納品予定日", ascending=False), use_container_width=True, hide_index=True, num_rows="dynamic", key="editor_all_o")
        if st.button("💾 全データの修正を保存", type="primary"):
            save_data("orders", edited_all)
            st.success("全データを更新しました！")
            st.rerun()

# --- 製造登録 ---
elif page == "🏭 製造登録 (入庫)":
    st.markdown('<div class="main-header header-manu"><h1>🏭 製造（入庫）の管理</h1></div>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["➕ 新規登録 ＆ かんたん修正", "⚙️ 全データ一覧・詳細検索"])
    
    with tab1:
        with st.container(border=True):
            st.markdown("### 📝 新規入力フォーム")
            col1, col2 = st.columns(2)
            m_date = col1.date_input("📅 製造日", value=date.today())
            m_qty = col2.number_input("📦 製造ケース数", min_value=1, value=None, step=10, placeholder="数字を入力")
            
            st.write("---")
            st.write("### 📂 カテゴリを選択（クリック）")
            
            try:
                cat_full = st.pills("カテゴリ", CATEGORIES, default=CATEGORIES[0], label_visibility="collapsed")
                if not cat_full: cat_full = CATEGORIES[0]
            except AttributeError:
                cat_full = st.radio("カテゴリ", CATEGORIES, horizontal=True, label_visibility="collapsed")
                
            cat = cat_full.split(" ", 1)[1]
            
            prods = master_df[master_df["大カテゴリ"] == cat]["製品名"].tolist()
            prod = st.selectbox("📦 製品名を選択", options=prods, index=None, placeholder="製品を選んでください", format_func=format_name)
            
            st.write("")
            submit_btn = st.button("➕ 製造データを記録する", type="primary", use_container_width=True)
            msg_area = st.empty()
            
            if submit_btn:
                if not prod or not m_qty:
                    msg_area.error("⚠️ 製品と製造ケース数を入力してください。")
                else:
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    row_data = [str(uuid.uuid4())[:6].upper(), m_date.strftime('%Y-%m-%d'), "", cat, prod, int(m_qty), now_str]
                    append_row("manufactures", row_data)
                    st.session_state.success_msg = f"✨ 登録完了： {m_date.strftime('%m/%d')} 製造 ｜ {prod} ({m_qty}cs)"
                    st.rerun()

        if st.session_state.success_msg:
            st.success(st.session_state.success_msg)
            st.session_state.success_msg = None

        st.write("---")
        st.markdown("### ✏️ かんたん修正（直近登録5件）")
        st.info("💡 表のセルを直接クリックして修正・削除が可能です。")
        recent_manus = manus_df.sort_values("登録日時", ascending=False).head(5)
        recent_ids_m = recent_manus["ID"].tolist()
        
        edited_recent_m = st.data_editor(recent_manus, use_container_width=True, hide_index=True, num_rows="dynamic", key="editor_recent_m")
        
        if st.button("💾 直近5件の修正・削除を保存", type="primary"):
            edited_ids_m = edited_recent_m["ID"].tolist()
            deleted_ids_m = [uid for uid in recent_ids_m if uid not in edited_ids_m]
            
            new_df_m = manus_df[~manus_df["ID"].isin(deleted_ids_m)].copy()
            for _, row in edited_recent_m.iterrows():
                r_id = row["ID"]
                if r_id in new_df_m["ID"].values:
                    idx = new_df_m[new_df_m["ID"] == r_id].index[0]
                    new_df_m.at[idx, "製造予定日"] = pd.to_datetime(row["製造予定日"])
                    new_df_m.at[idx, "備考"] = row["備考"]
                    new_df_m.at[idx, "大カテゴリ"] = row["大カテゴリ"]
                    new_df_m.at[idx, "製品名"] = row["製品名"]
                    new_df_m.at[idx, "ケース数"] = int(row["ケース数"])
            
            save_data("manufactures", new_df_m)
            st.success("修正を保存しました！")
            st.rerun()

    with tab2:
        st.info("💡 全データの確認・修正が可能です。")
        edited_all_m = st.data_editor(manus_df.sort_values("製造予定日", ascending=False), use_container_width=True, hide_index=True, num_rows="dynamic", key="editor_all_m")
        if st.button("💾 全データの修正を保存", type="primary"):
            save_data("manufactures", edited_all_m)
            st.success("全データを更新しました！")
            st.rerun()

# --- 在庫・スケジュール ---
elif page == "📦 在庫・スケジュール":
    st.markdown('<div class="main-header"><h1>📦 在庫推移とカレンダー</h1></div>', unsafe_allow_html=True)
    
    today = pd.Timestamp.today().normalize()
    dates = pd.date_range(today, today + timedelta(days=14))
    
    t1, t2 = st.tabs(["📅 カレンダー＆リストDL", "📉 在庫予測マトリクス"])
    
    with t1:
        with st.container(border=True):
            st.write("📥 **ピッキングリスト（出荷予定）のダウンロード**")
            col_dl1, col_dl2 = st.columns(2)
            today_orders = orders_df[orders_df["納品予定日"] == today]
            if not today_orders.empty:
                export_df1 = today_orders[["顧客名", "大カテゴリ", "製品名", "ケース数"]].sort_values(["顧客名", "大カテゴリ"])
                csv1 = export_df1.to_csv(index=False, encoding="utf-8-sig")
                col_dl1.download_button("📝 今日の出荷予定を保存 (CSV)", data=csv1, file_name=f"出荷_{today.strftime('%Y%m%d')}.csv", mime="text/csv", type="primary")
            else:
                col_dl1.info("今日の出荷予定はありません。")
            
            week_orders = orders_df[(orders_df["納品予定日"] >= today) & (orders_df["納品予定日"] <= today + timedelta(days=6))]
            if not week_orders.empty:
                export_df2 = week_orders[["納品予定日", "顧客名", "大カテゴリ", "製品名", "ケース数"]].sort_values(["納品予定日", "顧客名"])
                export_df2["納品予定日"] = export_df2["納品予定日"].dt.strftime('%Y/%m/%d')
                csv2 = export_df2.to_csv(index=False, encoding="utf-8-sig")
                col_dl2.download_button("📅 1週間の出荷予定を保存 (CSV)", data=csv2, file_name=f"出荷_1週間_{today.strftime('%Y%m%d')}.csv", mime="text/csv")
            else:
                col_dl2.info("1週間の出荷予定はありません。")
        
        with st.container(border=True):
            st.write("バーの長さは **最大500ケース** を基準にしています。")
            MAX_CASES = 500 # ★500ケース対応
            
            html = '<table class="sched-table"><tr><th style="width:100px;">日付</th><th style="width:45%;">🏭 製造予定 (入庫)</th><th style="width:45%;">📋 出荷予定 (出庫)</th></tr>'
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
                    
                html += f'<tr><td><b style="font-size:18px;">{d.strftime("%m/%d")}</b><br><span style="font-size:13px; color:#64748B;">{["月","火","水","木","金","土","日"][d.dayofweek]}曜</span></td><td>{m_html}</td><td>{o_html}</td></tr>'
            st.markdown(html + '</table>', unsafe_allow_html=True)

    with t2:
        with st.container(border=True):
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
                cat_order = [c.split(" ", 1)[1] for c in CATEGORIES]
                inv_df["カテゴリ順"] = inv_df["大カテゴリ"].apply(lambda x: cat_order.index(x) if x in cat_order else 99)
                inv_df = inv_df.sort_values(["カテゴリ順", "製品名"]).drop(columns=["カテゴリ順", "大カテゴリ"])
                
                st.dataframe(inv_df.style.map(lambda x: 'color: #DC2626; font-weight: 900; background-color: #FEE2E2;' if isinstance(x, (int,float)) and x < 0 else ''), use_container_width=True, hide_index=True, height=600)

# --- 統計分析 ---
elif page == "📊 統計・分析":
    st.markdown('<div class="main-header header-stat"><h1>📊 分析ダッシュボード</h1></div>', unsafe_allow_html=True)
    
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
    st.markdown('<div class="main-header" style="background:linear-gradient(135deg, #475569 0%, #1E293B 100%);"><h1>⚙️ マスタ管理</h1></div>', unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["📦 製品マスタ（棚卸・初期在庫）", "🏢 顧客マスタ（ふりがな）"])
    with t1:
        with st.container(border=True):
            st.info("💡 実際の在庫数を「初期在庫数」に入力して保存すると、そこを起点に在庫計算がリセットされます。")
            ed_m = st.data_editor(master_df, num_rows="dynamic", use_container_width=True, height=500)
            if st.button("💾 製品マスタを保存する", type="primary"):
                save_data("master", ed_m)
                st.success("製品情報を更新しました")
                st.rerun()
                
    with t2:
        with st.container(border=True):
            st.write("「ふりがな」を登録しておくと、顧客名の一覧に表示されなくても検索のキーとして機能させることができます。")
            ed_c = st.data_editor(cust_df, num_rows="dynamic", use_container_width=True, height=500)
            if st.button("💾 顧客マスタを保存する", type="primary"):
                save_data("customers", ed_c)
                st.success("顧客情報を更新しました")
                st.rerun()
