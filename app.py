# app.py
import streamlit as st
import pandas as pd
import json
import time
import io
from datetime import datetime, date
import traceback
import plotly.graph_objects as go

try:
    from PIL import Image
    import base64
    from io import BytesIO
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

st.set_page_config(
    page_title="製造ERPシステム",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ════════════════════════════════════════════════════════════════
#  モバイル・タブレット特化 UI/UX 修正版 CSS (文字欠け・操作性徹底改善)
# ════════════════════════════════════════════════════════════════
st.markdown("""
<style>
:root {
    --c-bg: #f3f4f6;
    --c-surface: #ffffff;
    --c-primary: #2563eb;
    --c-primary-hover: #1d4ed8;
    --c-secondary: #0f172a;
    --c-border: #cbd5e1;
    --c-text: #1e293b;
    --c-danger: #ef4444;
    --c-success: #10b981;
    --c-warning: #f59e0b;
}
.stApp { background-color: var(--c-bg); color: var(--c-text); font-family: 'Helvetica Neue', Arial, sans-serif; }

[data-testid="stSidebar"] {
    background-color: var(--c-secondary) !important;
    padding-top: 1rem;
}
[data-testid="stSidebar"] * { color: #f8fafc !important; }

[data-testid="stSidebar"] div[role="radiogroup"] label {
    padding: 14px 18px !important;
    border-radius: 12px !important;
    margin-bottom: 10px !important;
    background: #1e293b !important;
    border: 1px solid #334155 !important;
    cursor: pointer;
    font-size: 1.1rem !important;
    font-weight: 700 !important;
}
[data-testid="stSidebar"] button {
    background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 800 !important;
    font-size: 1.1rem !important;
    padding: 16px !important;
    margin-top: 20px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
}

.main-header {
    background: var(--c-surface);
    padding: 24px 28px;
    border-radius: 14px;
    margin-bottom: 24px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.03);
    border-left: 8px solid var(--c-primary);
}
.main-header h1 { color: var(--c-secondary) !important; font-size: 1.8rem !important; margin: 0 0 8px 0 !important; font-weight: 850 !important; }
.main-header p { color: #64748b !important; font-size: 1rem !important; margin: 0 !important; font-weight: 600; }

.form-card {
    background: var(--c-surface);
    border: 1px solid var(--c-border);
    border-radius: 14px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}
.section-title { font-size: 1.25rem; font-weight: 850; color: var(--c-secondary); margin-bottom: 20px; display: flex; align-items: center; gap: 10px; }
.section-title::before { content: ''; display: block; width: 6px; height: 22px; background-color: var(--c-primary); border-radius: 4px; }

/* モバイルでタップしやすく、文字が絶対に欠けないようにフォントサイズと高さを調整 */
.stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"], .stDateInput input {
    background-color: #f8fafc !important;
    border: 2px solid var(--c-border) !important;
    border-radius: 10px !important;
    color: var(--c-text) !important;
    font-size: 1.1rem !important; 
    font-weight: 700 !important;
    padding: 12px 14px !important; 
    min-height: 54px !important; 
    box-sizing: border-box !important;
    width: 100% !important;
    line-height: 1.5 !important;
}
.stTextInput input:focus, .stNumberInput input:focus, .stSelectbox div[data-baseweb="select"]:focus-within {
    border-color: var(--c-primary) !important;
    background-color: var(--c-surface) !important;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15) !important;
}
label { color: #475569 !important; font-weight: 800 !important; font-size: 1rem !important; margin-bottom: 8px; display: inline-block; }

div[data-testid="stRadio"] > div { gap: 12px !important; flex-wrap: wrap !important; }
div[data-testid="stRadio"] label {
    font-size: 1.1rem !important; 
    color: var(--c-secondary) !important;
    background-color: #f8fafc;
    padding: 14px 20px !important; 
    border-radius: 10px;
    border: 2px solid var(--c-border);
    font-weight: 800 !important;
    cursor: pointer;
}

/* ボタンを大きくし、スマホやタブレットで非常に押しやすく変更 */
.stButton button, .stButton button[kind="primary"] {
    background: linear-gradient(135deg, var(--c-primary), var(--c-primary-hover)) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    font-size: 1.25rem !important;
    font-weight: 800 !important;
    padding: 16px 24px !important;
    min-height: 60px !important;
    width: 100% !important;
    box-shadow: 0 4px 10px rgba(37, 99, 235, 0.25) !important;
    transition: all 0.15s ease;
}
.stButton button:active {
    transform: scale(0.98) !important;
}

/* 数値入力の＋－ステッパーボタンをスマホ・タブレットでタップしやすいサイズに拡大 */
button[data-testid="stNumberInputStepUp"],
button[data-testid="stNumberInputStepDown"] {
    min-width: 48px !important;
    min-height: 48px !important;
    width: 48px !important;
    height: 48px !important;
    border-radius: 10px !important;
    border: 2px solid var(--c-border) !important;
    background-color: #f8fafc !important;
}
button[data-testid="stNumberInputStepUp"] svg,
button[data-testid="stNumberInputStepDown"] svg {
    width: 22px !important;
    height: 22px !important;
}
div[data-baseweb="input"] { min-height: 54px !important; }

.alert-box { background-color: #fffbeb; border-left: 6px solid var(--c-warning); color: #92400e; padding: 18px; border-radius: 10px; margin-bottom: 18px; font-size: 1.05rem; font-weight: 700; }
.alert-box.danger { background-color: #fef2f2; border-left-color: var(--c-danger); color: #991b1b; }
.alert-box.info { background-color: #f0fdf4; border-left-color: var(--c-success); color: #065f46; }
div[data-testid="stCheckbox"] label span { font-size: 1.15rem !important; font-weight: 800 !important; color: var(--c-secondary) !important; }
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════
#  データロード・安全確認
# ════════════════════════════════════════════════════════════════
try:
    import sheets
except Exception as e:
    st.error("🚨 `sheets.py` のインポート時にエラーが発生しました。")
    st.stop()

try:
    import report_generator
    HAS_REPORT_GEN = True
except Exception:
    HAS_REPORT_GEN = False

def refresh():
    st.cache_data.clear()
    st.rerun()

@st.cache_data(ttl=60)
def load_all_datasets():
    return {
        "arrivals": sheets.load_arrivals(),
        "brewing": sheets.load_brewing(),
        "adjustments": sheets.load_adjustments(),
        "supplies": sheets.load_supplies(),
        "supply_logs": sheets.load_supply_logs(),
        "materials": sheets.load_materials(),
        "makers": sheets.load_makers(),
        "inspectors": sheets.load_inspectors(),
        "order_points": sheets.load_order_points(),
        "recipes": sheets.load_recipes(),
        "recipe_logs": sheets.load_recipe_logs()
    }

try:
    dataset = load_all_datasets()
    arrivals, brewing, adjustments = dataset["arrivals"], dataset["brewing"], dataset["adjustments"]
    supplies, supply_logs = dataset["supplies"], dataset["supply_logs"]
    materials, makers, inspectors = dataset["materials"], dataset["makers"], dataset["inspectors"]
    order_points, recipes_raw, recipe_logs = dataset["order_points"], dataset["recipes"], dataset["recipe_logs"]
except Exception as e:
    st.error("🚨 データの読み込みに失敗しました。")
    st.stop()

# ════════════════════════════════════════════════════════════════
#  共通データ整合性ユーティリティ
#  ページ(page)の分岐の「外側」に定義することで、どのページ・
#  どのタブからでも安全に利用できるようにしている。
#  （以前はページ分岐の内側に定義していたため、他のページから
#    呼び出すと NameError になり、画面全体が止まる不具合があった）
# ════════════════════════════════════════════════════════════════
def is_corrupted_name(name):
    """原料名としてあり得ない文字列（JSON文字列の丸ごと混入など）を検知する"""
    name = str(name).strip()
    if not name:
        return False
    return len(name) > 30 or name.startswith("[") or name.startswith("{")


def safe_parse_recipe(recipe_val):
    """
    配合JSONを安全にリストへ復元する。
    ・多重にシリアライズされたデータでも復元を試みる
    ・原料名が壊れている項目（JSON文字列がそのまま入っている等）は
      自動的に除外し、常にクリーンなデータだけを返す
      （壊れた項目は表示から静かに取り除かれるだけなので、必要な原料は
       「配合レシピ」画面から改めて登録し直せば良い）
    """
    if not recipe_val:
        return []
    if isinstance(recipe_val, dict):
        data = [recipe_val]
    elif isinstance(recipe_val, list):
        data = recipe_val
    else:
        data = recipe_val
        try:
            for _ in range(5):
                if isinstance(data, str):
                    data = json.loads(data)
                else:
                    break
        except Exception:
            data = []
        if not isinstance(data, list):
            data = []

    cleaned = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("原料名", "")).strip()
        if not name or is_corrupted_name(name):
            continue
        try:
            ratio = float(item.get("比率", 0.0))
        except Exception:
            continue
        cleaned.append({"原料名": name, "比率": ratio})
    return cleaned


def sanitize_name_list(names):
    """原料マスタ等の1次元リストから、壊れた文字列（JSONの混入など）だけを除去する"""
    return [str(n).strip() for n in names if str(n).strip() and not is_corrupted_name(n)]

# ════════════════════════════════════════════════════════════════
#  現在庫算出ロジック
# ════════════════════════════════════════════════════════════════
def get_inventory():
    inv = {}
    for a in arrivals:
        ano = str(a.get("入荷No", "")).strip()
        if not ano: continue
        inv[ano] = {
            "入荷No": ano, "ロットNo": str(a.get("ロットNo", "")).strip(), 
            "メーカー": str(a.get("メーカー", "")).strip(), "原料種別": str(a.get("原料種別", "")).strip(), 
            "1袋重量": float(a.get("1袋重量(kg)") or 20.0), "入荷袋数": float(a.get("袋数") or 0.0), 
            "使用量(kg)": 0.0, "調整袋数": 0.0
        }

    for b in brewing:
        oa = b.get("その他添加物", "")
        if oa:
            try:
                items = json.loads(oa)
                for item in items:
                    t_lot = str(item.get("lot", "")).strip()
                    t_kg = float(item.get("kg", 0.0))
                    if "," in t_lot:
                        lots = [l.strip() for l in t_lot.split(",")]
                        kg_per_lot = t_kg / len(lots)
                        for l in lots:
                            for v in inv.values():
                                if l and v["ロットNo"] == l: v["使用量(kg)"] += kg_per_lot
                    else:
                        for v in inv.values():
                            if t_lot and v["ロットNo"] == t_lot: v["使用量(kg)"] += t_kg
            except:
                pass

    for adj in adjustments:
        ano = str(adj.get("入荷No", "")).strip()
        if ano in inv:
            inv[ano]["調整袋数"] += float(adj.get("調整袋数") or 0.0)

    for v in inv.values():
        bpk = v["1袋重量"] if v["1袋重量"] > 0 else 20.0
        v["使用袋数"] = v["使用量(kg)"] / bpk
        v["現在庫(袋)"] = max(v["入荷袋数"] - v["使用袋数"] + v["調整袋数"], 0.0)
        v["現在庫(kg)"] = v["現在庫(袋)"] * bpk
    return inv

inventory_data = get_inventory()
type_totals = {}
for v in inventory_data.values():
    m_type = v["原料種別"]
    type_totals[m_type] = type_totals.get(m_type, 0.0) + v["現在庫(袋)"]

# ════════════════════════════════════════════════════════════════
#  サイドバー
# ════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown('<div style="font-size:1.6rem; font-weight:900; margin-bottom:1.5rem; color:white; display:flex; align-items:center; gap:8px;">🏭 <span>製造管理 ERP</span></div>', unsafe_allow_html=True)
    page = st.radio("", [
        "📊 ダッシュボード", 
        "📥 原料入荷登録", 
        "🧪 仕込み・配合計算", 
        "📦 原料在庫・棚卸", 
        "🧹 資材・消耗品管理", 
        "🔍 履歴トレース", 
        "⚙️ マスタ設定"
    ], label_visibility="collapsed")
    st.markdown("---")
    if st.button("🔄 最新データに更新"): refresh()

# ════════════════════════════════════════════════════════════════
#  1. ダッシュボード
# ════════════════════════════════════════════════════════════════
if page == "📊 ダッシュボード":
    st.markdown('<div class="main-header"><h1>📊 生産・在庫ダッシュボード</h1><p>工場の在庫状況およびアラート監視をリアルタイムに行います。</p></div>', unsafe_allow_html=True)
    
    alerts = [{"name": m, "current": type_totals.get(m, 0.0), "point": order_points.get(m, 0.0)} for m in materials if order_points.get(m, 0.0) > 0 and type_totals.get(m, 0.0) < order_points.get(m, 0.0)]
    if alerts:
        for al in alerts:
            st.markdown(f'<div class="alert-box danger">🚨 【発注警告】 {al["name"]} の在庫（{al["current"]:.2f} 袋）が発注点（{al["point"]:.2f} 袋）を下回っています！</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="alert-box info">🟢 すべて的原料在庫は発注基準値を満たし、安全な状態です。</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">📦 主要原料 在庫モニター</div>', unsafe_allow_html=True)
    cols = st.columns(min(4, len(materials) if materials else 1))
    for idx, m in enumerate(materials):
        curr = type_totals.get(m, 0.0)
        pt = order_points.get(m, 0.0)
        alert_class = "alert" if pt > 0 and curr < pt else ""
        with cols[idx % 4]:
            st.markdown(f"""
            <div style="background:#fff; border:1px solid #e2e8f0; border-radius:12px; padding:20px; text-align:center; margin-bottom:16px; box-shadow:0 1px 3px rgba(0,0,0,0.05); { 'border-color:#ef4444; background:#fef2f2;' if pt > 0 and curr < pt else '' }">
                <div style="font-size:1rem; color:#64748b; font-weight:700; margin-bottom:8px;">{m}</div>
                <div style="font-size:1.8rem; font-weight:900; color:{'#ef4444' if pt > 0 and curr < pt else '#0f172a'};">{curr:,.2f} <span style="font-size:1rem;">袋</span></div>
                <div style="font-size:0.85rem; color:#94a3b8; font-weight:600; margin-top:4px;">発注基準: {pt:,.2f} 袋</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('<div class="section-title">⏱️ 直近の製造仕込み履歴（最新5件）</div>', unsafe_allow_html=True)
    if brewing:
        df_brw = pd.DataFrame(brewing)[["仕込No", "仕込日", "品名", "仕込量(kg)", "主原料ロット"]]
        st.dataframe(df_brw.tail(5)[::-1], use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════════════
#  2. 原料入荷登録
# ═══════════════════════════════════════════════════════════════
elif page == "📥 原料入荷登録":
    st.markdown('<div class="main-header"><h1>📥 原料入荷品質記録</h1><p>現場での素早い入荷検品と情報登録を行います。</p></div>', unsafe_allow_html=True)
    tab_a, tab_b = st.tabs(["➕ 新規入荷検品", "📋 入荷履歴"])
    
    with tab_a:
        st.markdown('<div class="form-card"><div class="section-title">🚛 基本入荷情報</div>', unsafe_allow_html=True)
        new_no = sheets.next_arrival_no(arrivals)
        c1, c2 = st.columns(2)
        c1.text_input("入荷No", value=new_no, disabled=True)
        arr_date = c2.date_input("入荷日", value=date.today())
        
        c3, c4 = st.columns(2)
        maker_sel = c3.selectbox("メーカー", makers + ["その他"])
        maker_val = st.text_input("メーカー名を入力") if maker_sel == "その他" else maker_sel
        lot_val = c4.text_input("ロットNo ＊")

        c5, c6 = st.columns(2)
        m_type = c5.selectbox("原料種別", materials)
        bags_qty = c6.number_input("入荷袋数", min_value=1, step=1, value=10)
        weight_per_bag = st.number_input("1袋重量 (kg)", min_value=1.0, value=20.0, step=0.5)
        st.info(f"💡 自動算出 合計重量: **{bags_qty * weight_per_bag:,.2f} kg**")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="form-card"><div class="section-title">🔍 受入品質検査</div>', unsafe_allow_html=True)
        cc1, cc2 = st.columns(2)
        chk_app = cc1.selectbox("① 外観検査", ["OK（正常）", "NG（異常あり）"])
        chk_spec = cc2.selectbox("② 品名・規格", ["OK（一致）", "NG（不一致）"])
        chk_exp = cc1.selectbox("③ 賞味期限", ["OK（期限内）", "NG（期限切れ）"])
        chk_dmg = cc2.selectbox("④ 異物・破損", ["OK（なし）", "NG（あり）"])
        
        abn_desc = st.text_input("⚠️ 異常内容の詳細", placeholder="異常詳細を入力してください") if "NG" in [chk_app, chk_spec, chk_exp, chk_dmg] else ""
        inspector_val = st.selectbox("受入検査担当者", inspectors)
        remarks_val = st.text_input("備考")
        st.markdown('</div>', unsafe_allow_html=True)

        if st.button("💾 入荷記録を登録する", type="primary", use_container_width=True):
            if not lot_val:
                st.error("ロットNoは必須項目です。")
            else:
                sheets.append_arrival({
                    "入荷No": new_no, "入荷日": str(arr_date), "メーカー": maker_val, "ロットNo": lot_val,
                    "原料種別": m_type, "袋数": bags_qty, "1袋重量(kg)": weight_per_bag, "総量(kg)": bags_qty * weight_per_bag,
                    "外観": chk_app, "品名・規格確認": chk_spec, "賞味期限": chk_exp, "異物": chk_dmg,
                    "搬入温度": "-", "臭い": "OK", "包装": "OK", "色調": "OK", "水分": "OK",
                    "異常内容": abn_desc, "担当者": inspector_val, "備考": remarks_val, "登録日時": datetime.now().isoformat()
                })
                st.success("入荷品質検査記録を保存しました。画面を更新します...")
                time.sleep(1.5)
                refresh()

    with tab_b:
        if arrivals:
            df_arr = pd.DataFrame(arrivals)[["入荷No", "入荷日", "メーカー", "ロットNo", "原料種別", "袋数", "外観", "担当者"]]
            st.dataframe(df_arr[::-1], use_container_width=True, hide_index=True, column_config={"袋数": st.column_config.NumberColumn(format="%.2f")})

# ═══════════════════════════════════════════════════════════════
#  3. 仕込み・配合記録（修繕版・二重JSON & 状態消失防止）
# ═══════════════════════════════════════════════════════════════
elif page == "🧪 仕込み・配合計算":
    st.markdown('<div class="main-header"><h1>🧪 製造仕込み・配合計算</h1><p>カテゴリから製品を選択し、割合(%)を入力すると実投入量(kg)が自動算出されます。</p></div>', unsafe_allow_html=True)
    
    tab_brw1, tab_brw2, tab_brw3 = st.tabs(["🧪 新規配合・登録", "📋 履歴一覧・Excel出力", "✏️ 履歴の編集・削除"])

    p_recipes = {}
    for r in recipes_raw:
        p_name = r.get("品名", "未定義")
        p_recipes[p_name] = {
            "大カテゴリ": r.get("大カテゴリ", "その他"),
            "中カテゴリ": r.get("中カテゴリ", "その他"),
            "成分": safe_parse_recipe(r.get("配合JSON"))
        }

    with tab_brw1:
        st.markdown('<div class="form-card"><div class="section-title">📝 1. 製造製品のカテゴリと仕込み量の指定</div>', unsafe_allow_html=True)
        
        st.write("##### **▶ 大カテゴリを選択**")
        cat_main = st.radio("", ["🏭 プラント", "🟦 OKM", "📝 直接入力（マスタ外）"], horizontal=True, label_visibility="collapsed")
        
        selected_p = None
        active_recipe = []

        if "直接入力" in cat_main:
            p_name = st.text_input("品名を手動入力してください", value="手動配合こんにゃく")
            active_recipe = [{"原料名": "こんにゃく粉（国産）", "比率": 2.50}, {"原料名": "石灰", "比率": 0.14}, {"原料名": "水", "比率": 97.36}]
        else:
            cat_str = "プラント" if "プラント" in cat_main else "OKM"
            
            if cat_str == "プラント":
                st.write("##### **▶ ライン（中カテゴリ）を選択**")
                cat_sub = st.radio("", ["⚪ 白", "⚫ 黒", "❄️ 耐冷", "🍽️ ショクカイ", "🍜 めん", "📦 その他"], horizontal=True, label_visibility="collapsed")
                sub_str = cat_sub.split(" ")[1]
            else:
                sub_str = None
                
            filtered_opts = []
            for k, v in p_recipes.items():
                if v["大カテゴリ"] == cat_str:
                    if cat_str == "プラント" and v["中カテゴリ"] != sub_str:
                        continue
                    filtered_opts.append(k)
            
            st.write("##### **▶ 製造する製品名を選択**")
            if not filtered_opts:
                st.warning("選択したカテゴリに紐づく製品マスタがありません。")
                p_name = ""
            else:
                selected_p = st.selectbox("", filtered_opts, label_visibility="collapsed")
                p_name = selected_p
                active_recipe = p_recipes.get(selected_p, {}).get("成分", [])

        st.markdown("---")
        target_size = st.number_input(
            "希望仕込製品量 (調合全体重量 kg)",
            min_value=1,
            value=100,
            step=10,
            format="%d",
            help="整数のみ入力できます（小数点は不要です）"
        )
        st.markdown('</div>', unsafe_allow_html=True)

        # 【文字消失・画面崩れバグ修正】
        # 従来は target_size（希望仕込量）を毎回キーに含めていたため、
        # 数量欄を1文字入力するたびに、下の原料入力欄が全て新しいウィジェットとして
        # 再生成され、入力中の文字が消えたり画面が崩れる原因になっていました。
        # 数量の変更では原料欄の状態をリセットする必要がないため、
        # キーは「選択した製品」が変わったときだけ変化するようにします。
        key_suffix = f"_{selected_p}" if selected_p else "_直接入力"

        if not active_recipe:
            st.info("製品を選択してください。")
        else:
            st.markdown('<div class="form-card"><div class="section-title">⚖️ 2. 投入原料の算出と入力</div>', unsafe_allow_html=True)
            st.write("各原料の「割合(%)」を変更すると、実投入量(kg)が自動で再計算されます。")
            
            current_month = date.today().month
            is_summer = 6 <= current_month <= 9
            
            water_weight = 0.0
            lime_water_val = 0.0
            
            submitted_ingredients = []
            recent_arrivals = sorted(arrivals, key=lambda x: x.get("入荷日", ""), reverse=True)

            for i, item in enumerate(active_recipe[:10]):
                if not isinstance(item, dict): continue
                r_name = str(item.get("原料名", "未定義原料")).strip()
                base_ratio = float(item.get("比率", 0.0))

                # 1. 水・お湯の処理
                if "水" == r_name or "お湯" in r_name:
                    water_weight = target_size * (base_ratio / 100.0)
                    st.markdown(f'<div style="background:#e0f2fe; padding:14px; border-radius:10px; margin-bottom:16px; border:1px solid #bae6fd; color:#0369a1; font-weight:bold; font-size:1.1rem;">💧 [自動算出] 配合加水量: {water_weight:.2f} kg (マスタ比率: {base_ratio:.2f}%)</div>', unsafe_allow_html=True)
                    submitted_ingredients.append({"原料名": r_name, "kg": water_weight, "lot": "─"})
                    continue

                # 2. 石灰の処理
                if "石灰" in r_name or "カルシウム" in r_name:
                    if is_summer:
                        orig_ratio = base_ratio
                        base_ratio += 0.01
                        st.markdown(f'<div class="alert-box info" style="margin-bottom:12px;">☀️ 夏季自動調整: 石灰比率を +0.01% 増量 ({orig_ratio:.2f}% → {base_ratio:.2f}%)</div>', unsafe_allow_html=True)
                    
                    st.markdown(f"#### 🧪 {r_name}")
                    col_l1, col_l2 = st.columns(2)
                    act_ratio = col_l1.number_input("適用比率 (%)", value=base_ratio, step=0.01, format="%.2f", key=f"ratio_{i}{key_suffix}")
                    lime_water_l = col_l2.number_input("作りたい石灰水の量 (L)", min_value=0.0, value=float(target_size), step=1.0, format="%.2f", key=f"lime_l_{i}{key_suffix}")
                    
                    lime_water_val = lime_water_l
                    calc_kg = lime_water_l * (act_ratio / 100.0)
                    st.metric("✅ 必要な石灰粉末 (自動計算)", f"{calc_kg:.3f} kg")
                    
                    raw_arr_matches = [a for a in recent_arrivals if str(a.get("原料種別", "")).strip() == r_name]
                    recent_filtered_lots = []
                    for a in raw_arr_matches:
                        l_no = str(a.get("ロットNo", "")).strip()
                        if l_no and l_no not in recent_filtered_lots: recent_filtered_lots.append(l_no)
                        if len(recent_filtered_lots) >= 5: break
                    
                    lots_choices = ["─ (ロットを選択)", "✏️ 手入力 (リスト外)"] + recent_filtered_lots
                    col_l_sel, col_l_txt = st.columns(2)
                    lot_sel = col_l_sel.selectbox("入荷ロットの選択", lots_choices, key=f"lot_sel_{i}{key_suffix}")
                    lot_txt = col_l_txt.text_input("ロット手入力", value="" if lot_sel == "✏️ 手入力 (リスト外)" else lot_sel, disabled=(lot_sel != "✏️ 手入力 (リスト外)"), key=f"lot_txt_{i}{key_suffix}")
                    
                    final_lot = lot_txt if lot_sel == "✏️ 手入力 (リスト外)" else lot_sel
                    if final_lot == "─ (ロットを選択)": final_lot = "─"
                    submitted_ingredients.append({"原料名": r_name, "kg": calc_kg, "lot": final_lot})
                    st.markdown("<hr style='margin:20px 0;'>", unsafe_allow_html=True)
                    continue

                # 3. 通常の粉体原料
                st.markdown(f"#### 🍏 {r_name}")
                col_rat, col_kg_show = st.columns(2)
                act_ratio = col_rat.number_input("適用割合 (%)", value=base_ratio, step=0.01, format="%.2f", key=f"ratio_{i}{key_suffix}")
                
                calc_kg = target_size * (act_ratio / 100.0)
                
                raw_arr_matches = [a for a in recent_arrivals if str(a.get("原料種別", "")).strip() == r_name]
                recent_filtered_lots = []
                for a in raw_arr_matches:
                    l_no = str(a.get("ロットNo", "")).strip()
                    if l_no and l_no not in recent_filtered_lots: recent_filtered_lots.append(l_no)
                    if len(recent_filtered_lots) >= 5: break
                lots_choices = ["─ (ロットを選択)", "✏️ 手入力 (リスト外)"] + recent_filtered_lots

                if "こんにゃく" in r_name:
                    use_blend = st.toggle("🔀 こんにゃく粉をブレンドする（複数ロット）", key=f"blend_{i}{key_suffix}")
                    act_kg_total = col_kg_show.number_input(f"実投入量 合計(kg)", min_value=0.0, value=calc_kg, step=0.01, key=f"act_kg_total_{i}{key_suffix}", format="%.3f")
                    
                    if use_blend:
                        st.markdown('<div style="background:#f8fafc; padding:18px; border-radius:12px; border:2px dashed #cbd5e1; margin-bottom:12px;">', unsafe_allow_html=True)
                        st.write(f"**ブレンド割合指定**（実投入量 {act_kg_total:.3f} kg を各ロットに割り振ります）")
                        
                        col_r1, col_r2 = st.columns([1, 1])
                        
                        st.write("▼ ロット A")
                        pct_A = col_r1.number_input("ロットA 割合 (%)", min_value=0.0, max_value=100.0, value=50.0, step=1.0, format="%.1f", key=f"pct_A_{i}{key_suffix}")
                        act_kg_1 = act_kg_total * (pct_A / 100.0)
                        col_r1.markdown(f"**算出された投入量 A:** <span style='color:#2563eb; font-size:1.15rem; font-weight:bold;'>{act_kg_1:.3f} kg</span>", unsafe_allow_html=True)
                        
                        lot_sel_1 = col_r2.selectbox("ロット選択 A", lots_choices, key=f"lot_sel_{i}_b1{key_suffix}")
                        lot_txt_1 = col_r2.text_input("ロット手入力 A", value="" if lot_sel_1 == "✏️ 手入力 (リスト外)" else lot_sel_1, disabled=(lot_sel_1 != "✏️ 手入力 (リスト外)"), key=f"lot_txt_{i}_b1{key_suffix}")
                        final_lot_1 = lot_txt_1 if lot_sel_1 == "✏️ 手入力 (リスト外)" else lot_sel_1
                        if final_lot_1 == "─ (ロットを選択)": final_lot_1 = "─"

                        st.markdown("<br>", unsafe_allow_html=True)
                        st.write("▼ ロット B")
                        pct_B = 100.0 - pct_A
                        col_r1.markdown(f"ロットB 割合 (%): <span style='font-size:1.15rem; font-weight:bold;'>{pct_B:.1f} %</span> (自動計算)", unsafe_allow_html=True)
                        act_kg_2 = act_kg_total * (pct_B / 100.0)
                        col_r1.markdown(f"**算出された投入量 B:** <span style='color:#2563eb; font-size:1.15rem; font-weight:bold;'>{act_kg_2:.3f} kg</span>", unsafe_allow_html=True)
                        
                        lot_sel_2 = col_r2.selectbox("ロット選択 B", lots_choices, key=f"lot_sel_{i}_b2{key_suffix}")
                        lot_txt_2 = col_r2.text_input("ロット手入力 B", value="" if lot_sel_2 == "✏️ 手入力 (リスト外)" else lot_sel_2, disabled=(lot_sel_2 != "✏️ 手入力 (リスト外)"), key=f"lot_txt_{i}_b2{key_suffix}")
                        final_lot_2 = lot_txt_2 if lot_sel_2 == "✏️ 手入力 (リスト外)" else lot_sel_2
                        if final_lot_2 == "─ (ロットを選択)": final_lot_2 = "─"
                        
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        if act_kg_1 > 0: submitted_ingredients.append({"原料名": r_name, "kg": act_kg_1, "lot": final_lot_1})
                        if act_kg_2 > 0: submitted_ingredients.append({"原料名": r_name, "kg": act_kg_2, "lot": final_lot_2})
                        
                    else:
                        col_s, col_t = st.columns(2)
                        lot_sel = col_s.selectbox("入荷ロットの選択", lots_choices, key=f"lot_sel_{i}_val{key_suffix}")
                        lot_txt = col_t.text_input("ロット手入力", value="" if lot_sel == "✏️ 手入力 (リスト外)" else lot_sel, disabled=(lot_sel != "✏️ 手入力 (リスト外)"), key=f"lot_txt_{i}_val{key_suffix}")
                        final_lot = lot_txt if lot_sel == "✏️ 手入力 (リスト外)" else lot_sel
                        if final_lot == "─ (ロットを選択)": final_lot = "─"
                        
                        submitted_ingredients.append({"原料名": r_name, "kg": act_kg_total, "lot": final_lot})
                else:
                    act_kg = col_kg_show.number_input(f"実投入量 (kg)", min_value=0.0, value=calc_kg, step=0.01, key=f"act_kg_{i}_val{key_suffix}", format="%.3f")
                    col_s, col_t = st.columns(2)
                    lot_sel = col_s.selectbox("入荷ロットの選択", lots_choices, key=f"lot_sel_{i}_val{key_suffix}")
                    lot_txt = col_t.text_input("ロット手入力", value="" if lot_sel == "✏️ 手入力 (リスト外)" else lot_sel, disabled=(lot_sel != "✏️ 手入力 (リスト外)"), key=f"lot_txt_{i}_val{key_suffix}")
                    final_lot = lot_txt if lot_sel == "✏️ 手入力 (リスト外)" else lot_sel
                    if final_lot == "─ (ロットを選択)": final_lot = "─"
                    submitted_ingredients.append({"原料名": r_name, "kg": act_kg, "lot": final_lot})

                st.markdown("<hr style='margin:20px 0;'>", unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)

            if st.button("💾 この実績で製造記録を保存する", type="primary", use_container_width=True):
                if not p_name: st.error("品名が設定されていません。")
                else:
                    k_kg = s_kg = st_kg = lime_kg = 0.0
                    k_lot = s_lot = st_lot = "─"
                    
                    for ing in submitted_ingredients:
                        n = ing["原料名"]
                        if "こんにゃく" in n:
                            k_kg += ing["kg"]
                            if k_lot == "─": k_lot = ing["lot"]
                            elif ing["lot"] not in k_lot: k_lot += f", {ing['lot']}"
                        elif "海藻" in n:
                            s_kg += ing["kg"]
                            if s_lot == "─": s_lot = ing["lot"]
                            elif ing["lot"] not in s_lot: s_lot += f", {ing['lot']}"
                        elif "デンプン" in n or "でんぷん" in n:
                            st_kg += ing["kg"]
                            if st_lot == "─": st_lot = ing["lot"]
                            elif ing["lot"] not in st_lot: st_lot += f", {ing['lot']}"
                        elif "石灰" in n or "カルシウム" in n:
                            lime_kg += ing["kg"]

                    sheets.append_brewing({
                        "仕込No": sheets.next_brewing_no(brewing), "仕込日": str(date.today()), "品名": p_name,
                        "メーカー": "自社", "主原料ロット": k_lot, "仕込量(kg)": target_size,
                        "こんにゃく精粉(kg)": k_kg, "海藻粉(kg)": s_kg, "海藻粉ロット": s_lot,
                        "デンプン(kg)": st_kg, "デンプンロット": st_lot, "デンプン種別": "-",
                        "石灰(kg)": lime_kg, "石灰水(L)": lime_water_val,
                        "その他添加物": json.dumps(submitted_ingredients, ensure_ascii=False),
                        "備考": "割合ベース動的登録", "登録日時": datetime.now().isoformat()
                    })
                    st.success("仕込み・製造実績を登録しました。画面を更新します...")
                    time.sleep(1.5)
                    refresh()

    with tab_brw2:
        st.markdown('<div class="form-card"><div class="section-title">📋 仕込み・製造実績の履歴一覧</div>', unsafe_allow_html=True)
        if not brewing:
            st.info("まだ製造実績が登録されていません。")
        else:
            df_brw = pd.DataFrame(brewing)
            show_cols = [c for c in [
                "仕込No", "仕込日", "品名", "メーカー", "仕込量(kg)", "主原料ロット",
                "こんにゃく精粉(kg)", "海藻粉(kg)", "デンプン(kg)", "石灰(kg)", "石灰水(L)", "備考"
            ] if c in df_brw.columns]
            st.dataframe(df_brw[show_cols][::-1], use_container_width=True, hide_index=True)

            excel_buffer = io.BytesIO()
            try:
                with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                    df_brw[show_cols].to_excel(writer, index=False, sheet_name="仕込み履歴")
                st.download_button(
                    "📥 Excelファイルとしてダウンロード",
                    data=excel_buffer.getvalue(),
                    file_name=f"仕込み履歴_{date.today().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except Exception:
                st.warning("Excel出力用のライブラリ(openpyxl)が見つからないため、代わりにCSVで出力します。")
                csv_bytes = df_brw[show_cols].to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "📥 CSVファイルとしてダウンロード",
                    data=csv_bytes,
                    file_name=f"仕込み履歴_{date.today().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_brw3:
        st.markdown('<div class="form-card"><div class="section-title">✏️ 仕込み・製造実績の編集・削除</div>', unsafe_allow_html=True)
        if not brewing:
            st.info("まだ製造実績が登録されていません。")
        else:
            brw_edit_opts = {f"No.{b.get('仕込No')} - {b.get('品名')} ({b.get('仕込日')})": b for b in brewing}
            sel_label = st.selectbox("編集・削除する記録を選択", list(brw_edit_opts.keys()))
            sel_rec = brw_edit_opts[sel_label]

            with st.form("brw_edit_form"):
                e_date = st.text_input("仕込日", value=str(sel_rec.get("仕込日", "")))
                e_name = st.text_input("品名", value=str(sel_rec.get("品名", "")))
                e_size = st.number_input("仕込量(kg)", min_value=1, value=int(float(sel_rec.get("仕込量(kg)", 100) or 100)), step=10, format="%d")
                e_note = st.text_input("備考", value=str(sel_rec.get("備考", "")))

                col_save, col_del = st.columns(2)
                do_save = col_save.form_submit_button("💾 変更を保存する", type="primary", use_container_width=True)
                do_delete = col_del.form_submit_button("🗑️ この記録を削除する", use_container_width=True)

                if do_save or do_delete:
                    if not hasattr(sheets, "save_brewing"):
                        st.error("この操作には `sheets.py` 側に `save_brewing(list)` 関数（仕込みデータ全体を上書き保存する関数、他の save_recipes 等と同じ形式）を追加する必要があります。現状は追加・登録のみ対応しています。")
                    else:
                        updated_brewing = [b for b in brewing if b.get("仕込No") != sel_rec.get("仕込No")]
                        if do_save:
                            new_rec = dict(sel_rec)
                            new_rec.update({"仕込日": e_date, "品名": e_name, "仕込量(kg)": e_size, "備考": e_note})
                            updated_brewing.append(new_rec)
                            sheets.save_brewing(updated_brewing)
                            st.success("製造実績を更新しました。")
                        else:
                            sheets.save_brewing(updated_brewing)
                            st.success("製造実績を削除しました。")
                        time.sleep(1.5)
                        refresh()
        st.markdown('</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
#  4. 原料在庫・棚卸
# ═══════════════════════════════════════════════════════════════
elif page == "📦 原料在庫・棚卸":
    st.markdown('<div class="main-header"><h1>📦 原料在庫・棚卸管理</h1><p>ロット別現在庫の確認、入出庫トレンドのグラフ化、棚卸し調整を行います。</p></div>', unsafe_allow_html=True)
    tab_inv1, tab_inv_trend, tab_inv2 = st.tabs(["📋 ロット別現在庫一覧", "📈 入出庫トレンド推移", "⚖️ 棚卸し在庫調整"])
    
    with tab_inv1:
        active_inv = [v for v in inventory_data.values() if v["現在庫(袋)"] > 0.0]
        if active_inv:
            df_curr_inv = pd.DataFrame(active_inv)[["入荷No", "原料種別", "ロットNo", "入荷袋数", "使用袋数", "調整袋数", "現在庫(袋)"]]
            st.dataframe(
                df_curr_inv, 
                use_container_width=True, hide_index=True,
                column_config={"入荷袋数": st.column_config.NumberColumn(format="%.2f"), "使用袋数": st.column_config.NumberColumn(format="%.2f"), "調整袋数": st.column_config.NumberColumn(format="%.2f"), "現在庫(袋)": st.column_config.NumberColumn(format="%.2f")}
            )

    with tab_inv_trend:
        st.markdown('<div class="form-card"><div class="section-title">📊 原料種別 月別入出庫トレンド</div>', unsafe_allow_html=True)
        target_mat = st.selectbox("グラフ表示する原料種別", materials)
        df_a = pd.DataFrame(arrivals)
        df_b = pd.DataFrame(brewing)
        if not df_a.empty and not df_b.empty:
            df_a["date"] = pd.to_datetime(df_a["入荷日"], errors="coerce")
            df_a = df_a.dropna(subset=["date"])
            df_a["month"] = df_a["date"].dt.to_period("M").astype(str)
            df_a["総量(kg)"] = pd.to_numeric(df_a["総量(kg)"], errors="coerce").fillna(0)
            in_trend = df_a[df_a["原料種別"] == target_mat].groupby("month")["総量(kg)"].sum().reset_index()
            in_trend.rename(columns={"総量(kg)": "入荷量(kg)"}, inplace=True)
            
            out_records = []
            for _, r in df_b.iterrows():
                try:
                    b_date = pd.to_datetime(r["仕込日"], errors="coerce")
                    if pd.isna(b_date): continue
                    m_str = b_date.to_period("M").astype(str)
                    oa = r.get("その他添加物", "")
                    if oa:
                        items = json.loads(oa)
                        for item in items:
                            if item.get("原料名", "").strip() == target_mat: out_records.append({"month": m_str, "消費量(kg)": float(item.get("kg", 0))})
                except: pass
            
            df_out = pd.DataFrame(out_records)
            out_trend = df_out.groupby("month")["消費量(kg)"].sum().reset_index() if not df_out.empty else pd.DataFrame(columns=["month", "消費量(kg)"])

            df_trend = pd.merge(in_trend, out_trend, on="month", how="outer").fillna(0).sort_values("month")
            if not df_trend.empty:
                fig = go.Figure()
                fig.add_trace(go.Bar(x=df_trend["month"], y=df_trend["入荷量(kg)"], name="入荷量 (kg)", marker_color="#10b981"))
                fig.add_trace(go.Bar(x=df_trend["month"], y=df_trend["消費量(kg)"], name="消費量 (kg)", marker_color="#f43f5e"))
                fig.update_layout(barmode="group", xaxis_title="年月", yaxis_title="重量 (kg)", plot_bgcolor="#f8fafc")
                st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_inv2:
        st.markdown('<div class="form-card"><div class="section-title">⚖️ 棚卸による理論在庫ズレ調整</div>', unsafe_allow_html=True)
        if inventory_data:
            tgt_list = {f"{v['入荷No']} - {v['原料種別']} (ロット:{v['ロットNo']})": v["入荷No"] for v in inventory_data.values()}
            selected_tgt = st.selectbox("調整対象ロット", list(tgt_list.keys()))
            diff_bags = st.number_input("理論在庫との差分（袋数単位）", step=1.0, value=0.0, format="%.2f")
            reason_txt = st.text_input("調整の理由", placeholder="例: 実地棚卸との差分修正")
            operator = st.selectbox("調整実施者", inspectors)

            if st.button("💾 在庫データを上書き調整する", type="primary", use_container_width=True):
                sheets.append_adjustment({"調整ID": f"ADJ-{datetime.now().strftime('%Y%m%d%H%M%S')}", "入荷No": tgt_list[selected_tgt], "調整日": str(date.today()), "調整袋数": diff_bags, "理由": reason_txt, "担当者": operator, "登録日時": datetime.now().isoformat()})
                st.success("調整情報を書き込みました。")
                time.sleep(1.5)
                refresh()
        st.markdown('</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
#  5. 資材・消耗品管理
# ═══════════════════════════════════════════════════════════════
elif page == "🧹 資材・消耗品管理":
    st.markdown('<div class="main-header"><h1>🧹 資材・消耗品管理</h1><p>資材の残量確認および入出庫操作を行います。</p></div>', unsafe_allow_html=True)
    tab_s1, tab_s2 = st.tabs(["📋 在庫一覧・入出庫", "🕒 ログ管理"])
    
    with tab_s1:
        if supplies:
            st.markdown('<div class="section-title">🚦 資材モニター</div>', unsafe_allow_html=True)
            cols_grid = st.columns(max(2, min(4, len(supplies))))
            for idx, s in enumerate(supplies):
                with cols_grid[idx % len(cols_grid)]:
                    st.markdown(f"**{s.get('資材名')}** ({s.get('カテゴリ')})")
                    img_data = s.get("画像URL", "")
                    if img_data and img_data.startswith("data:image"): st.image(img_data, width=100)
                    else: st.caption("📷 画像なし")
                    st.write(f"初期: {s.get('初期在庫')} / 発注点: {s.get('発注点')}")
                    st.markdown("---")
            
            st.markdown('<div class="form-card"><div class="section-title">📥 資材入出庫の記録</div>', unsafe_allow_html=True)
            col_sc1, col_sc2 = st.columns(2)
            sup_name = col_sc1.selectbox("資材名", [s.get("資材名") for s in supplies])
            action_type = col_sc2.selectbox("処理内容", ["➕ 補充する (入荷)", "➖ 使用する (出庫)"])
            qty_val = st.number_input("数量", min_value=1.0, value=1.0, step=1.0, format="%.2f")
            operator_val = st.selectbox("作業担当者", inspectors, key="op_sup")
            notes_val = st.text_input("備考情報")
            
            if st.button("💾 資材変動を保存する", type="primary", use_container_width=True):
                target_sup = next(s for s in supplies if s.get("資材名") == sup_name)
                sheets.append_supply_log({
                    "ログID": f"LOG-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                    "登録日": str(date.today()), "資材ID": target_sup.get("資材ID"),
                    "処理": "入荷" if "補充" in action_type else "使用", "数量": qty_val,
                    "作業者": operator_val, "備考": notes_val, "登録日時": datetime.now().isoformat()
                })
                st.success("資材情報を記録しました。")
                time.sleep(1.5)
                refresh()
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.warning("資材が未登録です。マスタ設定よりご登録ください。")

    with tab_s2:
        if supply_logs:
            id_name_map = {s.get("資材ID"): s.get("資材名") for s in supplies}
            df_logs = pd.DataFrame(supply_logs).copy()
            df_logs["資材名"] = df_logs["資材ID"].map(id_name_map)
            st.dataframe(df_logs.tail(20)[::-1], use_container_width=True, hide_index=True)
            
            st.markdown('<div class="section-title">🚨 ログの取り消し・削除</div>', unsafe_allow_html=True)
            log_id_to_del = st.text_input("削除するログIDを入力してください")
            if st.button("🗑️ このログIDを完全に削除する"):
                if log_id_to_del:
                    sheets.delete_supply_log(log_id_to_del)
                    st.success("ログを削除しました。")
                    time.sleep(1.5)
                    refresh()

# ═══════════════════════════════════════════════════════════════
#  6. 双方向トレース
# ═══════════════════════════════════════════════════════════════
elif page == "🔍 履歴トレース":
    st.markdown('<div class="main-header"><h1>🔍 双方向原料トレース</h1><p>原料ロットと製品製造ロットの関連付けを完全に追跡します。</p></div>', unsafe_allow_html=True)
    trace_dir = st.radio("トレース方向", ["➡️ 原料ロットから製品を追跡（フォワード）", "⬅️ 製品から原料を遡及（バックワード）"])
    
    if "フォワード" in trace_dir:
        st.markdown('<div class="form-card">', unsafe_allow_html=True)
        lots_to_search = sorted(list(set([str(a.get("ロットNo", "")).strip() for a in arrivals if a.get("ロットNo")])), reverse=True)
        if not lots_to_search:
            st.info("原料ロット情報がありません。")
        else:
            target_lot = st.selectbox("検索する原料ロット番号", lots_to_search)
            if st.button("➡️ 追跡を開始する", type="primary", use_container_width=True):
                match_arr = [a for a in arrivals if str(a.get("ロットNo", "")).strip() == target_lot]
                if match_arr:
                    st.markdown("##### 📦 入荷・受け入れ情報")
                    st.dataframe(pd.DataFrame(match_arr)[["入荷No", "入荷日", "原料種別", "メーカー", "袋数", "外観", "担当者"]], use_container_width=True, hide_index=True)
                
                match_brw = []
                for b in brewing:
                    matched = False
                    try:
                        items = json.loads(b.get("その他添加物", "[]"))
                        if any(target_lot in str(i.get("lot", "")).strip() for i in items): matched = True
                    except:
                        pass
                    if matched: match_brw.append(b)

                if match_brw:
                    st.markdown("##### 🧪 製造仕込み消費実績")
                    st.dataframe(pd.DataFrame(match_brw)[["仕込No", "仕込日", "品名", "仕込量(kg)", "こんにゃく精粉(kg)", "主原料ロット"]], use_container_width=True, hide_index=True)
                else:
                    st.warning("⚠️ このロットを使用した仕込み履歴は存在しません。")
        st.markdown('</div>', unsafe_allow_html=True)

    else:
        st.markdown('<div class="form-card">', unsafe_allow_html=True)
        if not brewing:
            st.info("製造記録が存在しません。")
        else:
            brw_opts = {f"No.{b.get('仕込No')} - {b.get('品名')} ({b.get('仕込日')})": b for b in brewing}
            selected_brw_label = st.selectbox("対象の製造仕込み記録", list(brw_opts.keys()))
            selected_b = brw_opts[selected_brw_label]
            
            if st.button("⬅️ 遡及を開始する", type="primary", use_container_width=True):
                st.markdown("##### 🧪 製造の基本情報")
                st.markdown(f"""
                <div style="background-color: #f8fafc; padding: 20px; border-radius: 12px; border-left: 6px solid #2563eb; margin-bottom: 20px; border: 1px solid #e2e8f0;">
                    <h3 style="margin-top:0; color:#1e293b;">{selected_b.get('品名')}</h3>
                    <div style="display: flex; gap: 20px; flex-wrap: wrap;">
                        <p style="margin-bottom:0; font-size:1.1rem;"><strong>仕込No:</strong> {selected_b.get('仕込No')}</p>
                        <p style="margin-bottom:0; font-size:1.1rem;"><strong>製造日:</strong> {selected_b.get('仕込日')}</p>
                        <p style="margin-bottom:0; font-size:1.1rem;"><strong>製造量:</strong> <span style="color:#2563eb; font-weight:bold;">{selected_b.get('仕込量(kg)')} kg</span></p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                used_lots = []
                try:
                    items = json.loads(selected_b.get("その他添加物", "[]"))
                    for ing in items:
                        l_nums = str(ing.get("lot", "")).strip().split(",")
                        for l in l_nums:
                            if l.strip() and l.strip() != "─":
                                used_lots.append({"原料種別": ing.get("原料名", "副資材"), "ロットNo": l.strip()})
                except:
                    pass
                
                if used_lots:
                    st.markdown("##### 📦 使用原料の入荷元詳細情報")
                    details = []
                    for u in used_lots:
                        arr_match = next((a for a in arrivals if str(a.get("ロットNo", "")).strip() == u["ロットNo"]), None)
                        if arr_match:
                            details.append({"原料種別": u["原料種別"], "ロットNo": u["ロットNo"], "入荷No": arr_match.get("入荷No"), "入荷日": arr_match.get("入荷日"), "メーカー": arr_match.get("メーカー"), "外観検査": arr_match.get("外観")})
                        else:
                            details.append({"原料種別": u["原料種別"], "ロットNo": u["ロットNo"], "入荷No": "不明", "入荷日": "不明", "メーカー": "不明", "外観検査": "不明"})
                    st.dataframe(pd.DataFrame(details), use_container_width=True, hide_index=True)
                else:
                    st.warning("この製造ロットで使用された原料ロットの記録はありません。")
        st.markdown('</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
#  7. マスタ設定
# ═══════════════════════════════════════════════════════════════
elif page == "⚙️ マスタ設定":
    st.markdown('<div class="main-header"><h1>⚙️ マスターデータ管理</h1><p>システム全体で共有されるリストや配合基準、資材の定義を行います。</p></div>', unsafe_allow_html=True)
    m_tab1, m_tab2, m_tab3, m_tab4, m_tab5 = st.tabs(["⚗️ 原料", "🏢 メーカー・担当", "🚨 発注点", "🧪 配合レシピ（登録・編集・履歴）", "📦 資材・消耗品"])
    
    with m_tab1:
        st.markdown('<div class="form-card">', unsafe_allow_html=True)
        df_materials = pd.DataFrame({"原料名": materials})
        edited_materials = st.data_editor(df_materials, num_rows="dynamic", use_container_width=True, key="mat_ed_k")
        if st.button("💾 原料マスタを更新する", type="primary"):
            raw_names = [str(x).strip() for x in edited_materials["原料名"].tolist() if str(x).strip()]
            # 【破損防止】原料名としてあり得ない文字列（JSONの貼り付け間違い等）が
            # 万一入力されても、マスタに保存される前に弾く。
            bad_names = [n for n in raw_names if is_corrupted_name(n)]
            clean_names = [n for n in raw_names if not is_corrupted_name(n)]
            if bad_names:
                st.error(f"⚠️ 原料名として不正な値が {len(bad_names)} 件含まれていたため、保存をスキップしました。原料名の欄には短い名称のみを入力してください（誤って長い文章やコードを貼り付けていないかご確認ください）。")
            else:
                sheets.save_materials(clean_names)
                st.success("原料マスター情報を保存しました。")
                time.sleep(1.5)
                refresh()
        st.markdown('</div>', unsafe_allow_html=True)

    with m_tab2:
        col_sub1, col_sub2 = st.columns(2)
        with col_sub1:
            st.markdown('<div class="form-card"><div class="section-title">取引先メーカー</div>', unsafe_allow_html=True)
            df_makers = pd.DataFrame({"メーカー名": makers})
            edited_makers = st.data_editor(df_makers, num_rows="dynamic", use_container_width=True, key="maker_ed_k")
            if st.button("💾 メーカーリストを保存", type="primary"):
                sheets.save_makers([str(x).strip() for x in edited_makers["メーカー名"].tolist() if str(x).strip()])
                st.success("保存しました。")
                time.sleep(1.5)
                refresh()
            st.markdown('</div>', unsafe_allow_html=True)
            
        with col_sub2:
            st.markdown('<div class="form-card"><div class="section-title">担当者</div>', unsafe_allow_html=True)
            df_inspectors = pd.DataFrame({"担当者名": inspectors})
            edited_inspectors = st.data_editor(df_inspectors, num_rows="dynamic", use_container_width=True, key="inspector_ed_k")
            if st.button("💾 担当者を保存", type="primary"):
                sheets.save_inspectors([str(x).strip() for x in edited_inspectors["担当者名"].tolist() if str(x).strip()])
                st.success("保存しました。")
                time.sleep(1.5)
                refresh()
            st.markdown('</div>', unsafe_allow_html=True)

    with m_tab3:
        st.markdown('<div class="form-card">', unsafe_allow_html=True)
        op_rows = [{"原料名": m, "発注点(袋)": float(order_points.get(m, 0.0))} for m in materials]
        df_op = pd.DataFrame(op_rows)
        edited_op = st.data_editor(
            df_op, 
            use_container_width=True, 
            key="op_ed_k",
            column_config={"発注点(袋)": st.column_config.NumberColumn(format="%.2f")}
        )
        if st.button("💾 発注点設定を更新する", type="primary"):
            new_op_dict = {str(r["原料名"]).strip(): float(r["発注点(袋)"] or 0.0) for _, r in edited_op.iterrows() if str(r["原料名"]).strip()}
            sheets.save_order_points(new_op_dict)
            st.success("発注点設定を保存しました。")
            time.sleep(1.5)
            refresh()
        st.markdown('</div>', unsafe_allow_html=True)

    with m_tab4:
        st.markdown('<div class="form-card">', unsafe_allow_html=True)
        r_tab1, r_tab2, r_tab3 = st.tabs(["📝 新規登録・編集", "📋 登録済み一覧と削除", "🕒 変更履歴（監査ログ）"])
        
        def get_recipe_diff(old_json, new_json):
            try:
                old_items = json.loads(old_json) if isinstance(old_json, str) else old_json
                new_items = json.loads(new_json) if isinstance(new_json, str) else new_json
                old_dict = {i["原料名"]: float(i["比率"]) for i in old_items}
                new_dict = {i["原料名"]: float(i["比率"]) for i in new_items}
                changes = []
                for k in set(old_dict.keys()) | set(new_dict.keys()):
                    o_val = old_dict.get(k)
                    n_val = new_dict.get(k)
                    if o_val == n_val: continue
                    if o_val is None: changes.append(f"[{k}] 追加({n_val}%)")
                    elif n_val is None: changes.append(f"[{k}] 削除")
                    else: changes.append(f"[{k}] {o_val}%→{n_val}%")
                return " / ".join(changes) if changes else "変更なし"
            except:
                return "詳細不明（パースエラー）"

        with r_tab1:
            st.write("水を含む各配合原料の全体比率(％)を定義します。")
            edit_mode = st.radio("操作を選択", ["新規作成", "既存レシピの編集"], horizontal=True)
            
            target_recipe = None
            old_json = "[]"
            if edit_mode == "既存レシピの編集":
                if not recipes_raw: st.warning("編集できるレシピがありません。")
                else:
                    target_name = st.selectbox("編集するレシピを選択", [r["品名"] for r in recipes_raw])
                    target_recipe = next((r for r in recipes_raw if r["品名"] == target_name), None)
                    if target_recipe: old_json = target_recipe.get("配合JSON", "[]")
            
            init_name = target_recipe["品名"] if target_recipe else ""
            init_cat_m = "OKM" if target_recipe and target_recipe.get("大カテゴリ") == "OKM" else "プラント"
            init_cat_s = target_recipe.get("中カテゴリ", "黒") if target_recipe else "黒"
            
            try: 
                init_items = json.loads(old_json) if isinstance(old_json, str) else old_json
                if not isinstance(init_items, list): init_items = []
            except: 
                init_items = []
                
            def_mats = ["(未設定)", "水"] + materials

            with st.form("recipe_builder_form"):
                cat_main = st.radio("大カテゴリ", ["🏭 プラント", "🟦 OKM"], index=0 if init_cat_m == "プラント" else 1, horizontal=True)
                cat_sub = st.radio("中カテゴリ（プラントの場合のみ）", ["⚪ 白", "⚫ 黒", "❄️ 耐冷", "🍽️ ショクカイ", "🍜 めん", "📦 その他"], 
                                   index=["白","黒","耐冷","ショクカイ","めん","その他"].index(init_cat_s) if init_cat_s in ["白","黒","耐冷","ショクカイ","めん","その他"] else 1, horizontal=True)
                new_p_name = st.text_input("製品の名称 (例: こんにゃく極細白)", value=init_name, disabled=(target_recipe is not None))
                
                st.write("🧪 **各構成原料のパーセンテージ（％）比率**")
                cols_recipe_inputs = []
                for j in range(10):
                    c_n, c_w = st.columns([2, 1])
                    def_mat_val = init_items[j]["原料名"] if j < len(init_items) else "(未設定)"
                    def_rat_val = float(init_items[j]["比率"]) if j < len(init_items) else 0.00
                    try: mat_idx = def_mats.index(def_mat_val)
                    except: mat_idx = 0
                    
                    ing_mat = c_n.selectbox(f"配合成分 {j+1}", def_mats, index=mat_idx, key=f"rec_b_{j}")
                    ing_ratio = c_w.number_input("比率 (％)", min_value=0.00, max_value=100.00, value=def_rat_val, step=0.01, format="%.2f", key=f"rec_r_{j}")
                    cols_recipe_inputs.append({"name": ing_mat, "ratio": ing_ratio})
                
                operator = st.selectbox("操作担当者", inspectors)
                
                if st.form_submit_button("💾 配合比率を保存する"):
                    if not new_p_name: st.error("製品の名称は必須です。")
                    elif is_corrupted_name(new_p_name):
                        st.error("⚠️ 製品名として不正な値です（長すぎる、または記号で始まっています）。短い製品名を入力してください。")
                    else:
                        valid_items = [
                            {"原料名": i["name"], "比率": float(i["ratio"])}
                            for i in cols_recipe_inputs
                            if i["name"] != "(未設定)" and i["ratio"] > 0 and not is_corrupted_name(i["name"])
                        ]
                        if not valid_items: st.error("有効な配合成分がありません。")
                        else:
                            cat_str = "プラント" if "プラント" in cat_main else "OKM"
                            sub_str = cat_sub.split(" ")[1] if cat_str == "プラント" else "その他"
                            new_json = json.dumps(valid_items, ensure_ascii=False)
                            
                            new_recipe_entry = {"品名": new_p_name, "大カテゴリ": cat_str, "中カテゴリ": sub_str, "配合JSON": new_json}
                            updated_recipes = [r for r in recipes_raw if r["品名"] != new_p_name]
                            updated_recipes.append(new_recipe_entry)
                            
                            action = "新規" if not target_recipe else "更新"
                            diff_str = get_recipe_diff(old_json, new_json) if target_recipe else "新規作成"
                            try:
                                sheets.append_recipe_log({
                                    "ログID": f"RLOG-{datetime.now().strftime('%Y%m%d%H%M%S')}", "変更日時": datetime.now().strftime('%Y/%m/%d %H:%M:%S'),
                                    "品名": new_p_name, "処理": action, "変更内容": diff_str, "作業者": operator
                                })
                            except: pass
                            sheets.save_recipes(updated_recipes)
                            st.success(f"配合レシピ: {new_p_name} を保存しました。")
                            time.sleep(1.5)
                            refresh()

        with r_tab2:
            if recipes_raw:
                for idx, rec in enumerate(recipes_raw):
                    with st.expander(f"📦 {rec.get('品名')} (【{rec.get('大カテゴリ','')}】 {rec.get('中カテゴリ','')})"):
                        try:
                            # 📝 安全な読み出し・パース処理
                            comp_list = safe_parse_recipe(rec.get("配合JSON"))
                            if comp_list: st.dataframe(pd.DataFrame(comp_list), use_container_width=True, hide_index=True)
                            else: st.write("成分データがありません")
                        except Exception as e:
                            st.error(f"読み出しエラー（データ破損）")
                
                st.markdown("---")
                del_recipe_name = st.selectbox("削除するレシピを選択", [r["品名"] for r in recipes_raw])
                if st.button("🗑️ 選択したレシピを完全に削除する", type="primary"):
                    updated_recipes = [r for r in recipes_raw if r["品名"] != del_recipe_name]
                    try:
                        sheets.append_recipe_log({
                            "ログID": f"RLOG-{datetime.now().strftime('%Y%m%d%H%M%S')}", "変更日時": datetime.now().strftime('%Y/%m/%d %H:%M:%S'),
                            "品名": del_recipe_name, "処理": "削除", "変更内容": "レシピの完全削除", "作業者": "システム"
                        })
                    except: pass
                    sheets.save_recipes(updated_recipes)
                    st.success(f"{del_recipe_name} を削除しました。")
                    time.sleep(1.5)
                    refresh()
            else:
                st.info("登録済みの配合レシピはありません。")
                
        with r_tab3:
            try:
                recipe_logs = dataset.get("recipe_logs", [])
                if recipe_logs: st.dataframe(pd.DataFrame(recipe_logs)[::-1], use_container_width=True, hide_index=True)
                else: st.info("変更履歴はまだありません。")
            except:
                st.warning("履歴データの読み込みに失敗しました。")
        st.markdown('</div>', unsafe_allow_html=True)

    with m_tab5:
        st.markdown('<div class="form-card"><div class="section-title">📋 登録済み資材の管理・編集</div>', unsafe_allow_html=True)
        df_sup_list = pd.DataFrame(supplies)
        if not df_sup_list.empty:
            df_sup_edit = df_sup_list[["資材ID", "資材名", "カテゴリ", "初期在庫", "発注点"]]
            edited_sup = st.data_editor(
                df_sup_edit, 
                num_rows="dynamic", 
                use_container_width=True, 
                key="sup_master_ed", 
                disabled=["資材ID"],
                column_config={"初期在庫": st.column_config.NumberColumn(format="%.2f"), "発注点": st.column_config.NumberColumn(format="%.2f")}
            )
            if st.button("💾 資材マスタの変更を保存", type="primary"):
                new_supplies = []
                for _, r in edited_sup.iterrows():
                    sid = str(r.get("資材ID", "")).strip()
                    orig = next((s for s in supplies if s.get("資材ID") == sid), {})
                    if str(r.get("資材名", "")).strip() and str(r.get("資材名", "")) != "nan":
                        new_supplies.append({
                            "資材ID": sid if sid and sid != "nan" else f"SUP-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                            "資材名": str(r.get("資材名")), "カテゴリ": str(r.get("カテゴリ")),
                            "画像URL": orig.get("画像URL", ""), "初期在庫": float(r.get("初期在庫", 0)),
                            "発注点": float(r.get("発注点", 0)), "登録日": orig.get("登録日", str(date.today()))
                        })
                sheets.save_supplies(new_supplies)
                st.success("資材マスタを更新しました。")
                time.sleep(1.5)
                refresh()
        else:
            st.info("登録済みの資材はありません。")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="form-card"><div class="section-title">➕ 新規資材・衛生消耗品の登録</div>', unsafe_allow_html=True)
        with st.form("new_sup_form_rich"):
            c_s1, c_s2 = st.columns(2)
            new_s_name = c_s1.text_input("資材・備品名称 ＊")
            new_s_cat = c_s2.text_input("カテゴリ (例: 包材, 衛生消耗品)")
            c_s3, c_s4 = st.columns(2)
            new_s_stock = c_s3.number_input("現在の実地在庫数", min_value=0.0, value=0.0, format="%.2f")
            new_s_point = c_s4.number_input("発注注意アラート点", min_value=0.0, value=10.0, format="%.2f")
            uploaded_file = st.file_uploader("📷 写真・画像をアップロード (スマホ対応)", type=["jpg", "png", "jpeg"])
            
            if st.form_submit_button("➕ 画像付きで新規登録する"):
                if not new_s_name:
                    st.error("資材名称は必須入力項目です。")
                else:
                    img_base64_str = ""
                    if uploaded_file and HAS_PIL:
                        try:
                            img = Image.open(uploaded_file)
                            img.thumbnail((150, 150))
                            buffered = BytesIO()
                            img.save(buffered, format="PNG", optimize=True)
                            img_base64_str = f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode('utf-8')}"
                        except Exception as e:
                            st.warning(f"画像の処理に失敗しました。: {e}")
                    
                    current_supplies = supplies.copy()
                    current_supplies.append({
                        "資材ID": f"SUP-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        "資材名": new_s_name, "カテゴリ": new_s_cat, "画像URL": img_base64_str,
                        "初期在庫": new_s_stock, "発注点": new_s_point, "登録日": str(date.today())
                    })
                    sheets.save_supplies(current_supplies)
                    st.success(f"資材: {new_s_name} を登録しました。")
                    time.sleep(1.5)
                    refresh()
        st.markdown('</div>', unsafe_allow_html=True)
