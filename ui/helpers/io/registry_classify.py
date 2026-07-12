"""ui/helpers/io/registry_classify.py — Tab5 資料診斷「分類分組」純函式（v19.350）。

user 2026-07-12 要求「基金的資料診斷分類參考台股」：台股 Tab5 診斷表依類別
收合（如「🇹🇼 台灣總經（6 筆｜🟢3 🟡1 🔴2）」）+ 每類燈號 rollup。基金端原本
是一張平面大表 + 三個篩選器，無分類。本模組把 data_registry（session）依 key
前綴分組、算每類燈號統計，供 Tab5 ② 渲染。

§8.2 分層：純函式（dict in → list out），**不 import streamlit**、無 IO，
屬 L3 UI helper（與 data_registry.py 同域，co-locate 於 ui/helpers/io/）。

**範圍誠實聲明（§1 / §8.1 step 6）**：
- 本模組只做「分組 + rollup + 整類未載入的 ⚪ 提示」= 類別級缺席可見性。
- **不做逐指標「應有而無」偵測**：總經類（引擎實際輸出 25 鍵）無乾淨正典
  SSOT 可比對（services/macro/us_indicators.fetch_all_indicators 的 R[...]
  散列，與 data_registry._FREQ 的 30 鍵不一致，含 CHN_* 引擎核心迴圈未設），
  硬湊期望集合會誤報缺席（違 §1）；雷達 10 燈既有 code 本就迴圈跑滿全部
  登記（缺的以 N/A 紅燈現身，不會消失），無缺席問題。
  升級觸發條件：若總經引擎日後抽出正典 indicator SSOT → 再加逐指標缺席列。
"""
from __future__ import annotations

# 類別中繼 SSOT：(key 前綴, 顯示名, 未載入時提示的來源 Tab)
# 順序即 Tab5 呈現順序。key 前綴取 registry key 的第一個 "_" 之前段
# （_update_data_registry 命名慣例：總經_/雷達_/新聞_/基金_/組合_）。
DIAG_CATEGORIES: list[tuple[str, str, str]] = [
    ("總經", "🌍 美國＋全球總經", "Tab1 總經指南針"),
    ("雷達", "🚨 系統性風險雷達", "Tab1 風險雷達"),
    ("新聞", "📰 財經新聞", "Tab1 新聞"),
    ("基金", "💰 單一基金（NAV／配息／持股／績效／風險）", "Tab2 單一基金"),
    ("組合", "📊 投資組合基金", "Tab3 我的組合"),
]

_ICON_ORDER = {"🔴": 0, "🟡": 1, "🟢": 2, "⬜": 3, "⚪": 3}


def _prefix_of(key: str) -> str:
    """registry key → 類別前綴（第一個 "_" 之前）。無 "_" 則整段當前綴。"""
    return str(key).split("_", 1)[0]


def classify_registry(reg: dict) -> list[dict]:
    """將 data_registry 依類別前綴分組 + 計算每類燈號 rollup（純函式）。

    Parameters
    ----------
    reg : dict
        st.session_state["data_registry"]，{key: {label, source, freq,
        latest_date, count, fresh_icon, fresh_label, fresh_color, ...}}。

    Returns
    -------
    list[dict]
        依 DIAG_CATEGORIES 順序的類別群組；每群組：
        {
          "prefix": str, "name": str, "hint": str,
          "loaded": bool,                     # 該類是否有任何已載入資料
          "rows": list[dict],                 # 該類 registry 列（含原欄位 + "key"）
          "rollup": {"🔴": int, "🟡": int, "🟢": int, "⚪": int},
        }
        整類未載入（rows 空）→ loaded=False、rollup 全 0，UI 顯示 ⚪ 提示。
        **未落入任何已知前綴的 key** 收進尾端 "其他" 群組（防漂移消失）。
    """
    known_prefixes = {p for p, _, _ in DIAG_CATEGORIES}
    # 先按前綴桶分（單次線性掃描，O(n)）
    buckets: dict[str, list[dict]] = {}
    for k, v in (reg or {}).items():
        if not isinstance(v, dict):
            continue
        row = dict(v)
        row["key"] = k
        buckets.setdefault(_prefix_of(k), []).append(row)

    groups: list[dict] = []
    for prefix, name, hint in DIAG_CATEGORIES:
        rows = buckets.get(prefix, [])
        groups.append(_build_group(prefix, name, hint, rows))

    # 未知前綴 → "其他"（§1：不讓任何已登記資料在分類表中無聲消失）
    other_rows: list[dict] = []
    for pfx, rows in buckets.items():
        if pfx not in known_prefixes:
            other_rows.extend(rows)
    if other_rows:
        groups.append(_build_group("其他", "❓ 其他（未分類前綴）", "—", other_rows))

    return groups


def _build_group(prefix: str, name: str, hint: str, rows: list[dict]) -> dict:
    rollup = {"🔴": 0, "🟡": 0, "🟢": 0, "⚪": 0}
    for r in rows:
        icon = r.get("fresh_icon", "⚪")
        rollup[icon] = rollup.get(icon, 0) + 1
    # 每列排序：紅 → 黃 → 綠 → 其他；同燈依 label
    rows_sorted = sorted(
        rows,
        key=lambda r: (_ICON_ORDER.get(r.get("fresh_icon", "⚪"), 3),
                       str(r.get("label", r.get("key", "")))),
    )
    return {
        "prefix": prefix,
        "name": name,
        "hint": hint,
        "loaded": bool(rows),
        "rows": rows_sorted,
        "rollup": rollup,
    }


def rollup_caption(rollup: dict) -> str:
    """rollup dict → 「🟢3 🟡1 🔴2」風格字串（0 的燈省略）。"""
    parts = []
    for icon in ("🟢", "🟡", "🔴", "⚪"):
        n = rollup.get(icon, 0)
        if n:
            parts.append(f"{icon}{n}")
    return "　".join(parts) if parts else "—"
