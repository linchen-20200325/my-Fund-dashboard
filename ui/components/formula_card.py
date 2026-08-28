"""ui/components/formula_card.py — 高亮算式代入卡（UI3b）。

一句話：**把「這個數字是怎麼算出來的」攤開成「公式 → 代入 → 結果」三段**，
並且**讓「這一格是手動輸入／估算值」用看的就看得出來**。

⚠️ `kind="source_warn"` 為什麼要有視覺，不能只靠文字（本元件的起因）
--------------------------------------------------------------------
稽核 D1 的發現：**手動輸入的匯率被當成裸數字直接印進算式**，整塊沒有任何
「手動」字樣。而算式卡在整頁裡**最像「系統算給你的」**——它有公式、有代入、有等號，
看起來就是機器推導出來的東西。**最像權威的地方，反而最沒有揭露。**

所以 `source_warn` token 除了底色，**額外加左側 2px `WARN_AMBER` 邊**，
而且來源註腳**必帶 ⚠**（本元件自動補，不靠呼叫端記得）。
**用視覺而不只靠文字達成揭露** —— 文字會被跳過，色條不會。

⚠️ 強制不變式：用了 `source_warn` 就一定要交代來源
--------------------------------------------------
渲染到的步驟裡只要出現任一 `source_warn` token，`source_notes` 就**不得為空**，
否則 `raise ValueError`。理由：一個標了「這格可疑」卻不說可疑在哪的卡片，
比不標更糟 —— 它讓使用者知道有問題卻無從判斷。

§1 Fail Loud：缺值會**沿著算式往下傳**
--------------------------------------
任一步 `result is None` → 該步顯示 `—` + **就地說明缺什麼**，
且**其後所有步驟一律標「⬜ 上一步缺值」並且不計算、不顯示代入內容**。

**絕不用預設匯率、絕不用 1.0 頂替。** 用 1.0 當匯率，會讓一筆美元計價的部位
以 1:1 併進台幣總額 —— 那不是「少一個數字」，那是**一個錯到 30 倍的數字**，
而且它長得完全正常（§1：錯誤的數字比沒有數字更危險）。

⛔ **禁止 `degraded=True`**：本卡片產出的就是數值本身。

純函式邊界
----------
**零 streamlit 依賴**（本檔連 lazy import 都沒有）—— 純字串進、HTML 字串出，
可直接單元測試輸出內容。呼叫端自行 `st.markdown(..., unsafe_allow_html=True)`。
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from shared.colors import (
    GH_BG_HOVER,
    GH_BORDER,
    GH_FG_MUTED,
    GH_FG_PRIMARY,
    WARN_AMBER,
)
from ui.components.cards import gh_card

KIND_VALUE: str = "value"
KIND_SOURCE_WARN: str = "source_warn"   # 手動輸入 / 年化估算 / 任何非系統直取的值
KIND_PLAIN: str = "plain"               # 運算子、括號等，不加底色

MISSING_MARK: str = "—"
BLOCKED_MARK: str = "⬜ 上一步缺值"
WARN_PREFIX: str = "⚠"

# Result 18/700 —— 本批唯一新增的字級級距（見 UI3b 設計 token 表）。
_RESULT_FONT_PX: int = 18


def _esc(text: Any) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def substitution_token(text: Any, *, kind: str = KIND_VALUE) -> str:
    """單一代入 token 的 HTML。

    - `KIND_VALUE`       ：底 `GH_BG_HOVER`、圓角 4px、`tabular-nums`。
    - `KIND_SOURCE_WARN` ：同上 **＋ 左側 2px `WARN_AMBER` 邊**（來源可疑的視覺揭露）。
    - `KIND_PLAIN`       ：不加底色（運算子、括號）。
    """
    body = _esc(text)
    if kind == KIND_PLAIN:
        return (f"<span style='color:{GH_FG_MUTED};font-size:14px;padding:0 2px'>"
                f"{body}</span>")
    warn_edge = (f";border-left:2px solid {WARN_AMBER}" if kind == KIND_SOURCE_WARN
                 else "")
    return (f"<span style='background:{GH_BG_HOVER};border-radius:4px;"
            f"padding:1px 6px;margin:0 2px;font-size:14px;color:{GH_FG_PRIMARY};"
            f"font-variant-numeric:tabular-nums{warn_edge}'>{body}</span>")


def _normalize_tokens(tokens: Any) -> list[tuple[Any, str]]:
    """接受 `[(text, kind), ...]`、`[{"text":..,"kind":..}, ...]` 或 `[text, ...]`。"""
    out: list[tuple[Any, str]] = []
    for t in tokens or []:
        if isinstance(t, Mapping):
            out.append((t.get("text", ""), str(t.get("kind") or KIND_VALUE)))
        elif isinstance(t, (tuple, list)) and len(t) == 2:
            out.append((t[0], str(t[1] or KIND_VALUE)))
        else:
            out.append((t, KIND_VALUE))
    return out


def formula_card_html(
    *,
    title: str,
    formula: str,
    steps: Sequence[Mapping[str, Any]],
    source_notes: Sequence[str] = (),
) -> str:
    """組出算式卡 HTML。

    Parameters
    ----------
    title  : 卡片標題（這是在算什麼）。
    formula: 第 1 段 —— 符號形式的公式（例：`配息殖利率 = 近 12 個月配息 ÷ 現時淨值`）。
    steps  : 第 2/3 段 —— 每步一個 dict：
             `label`（這一步在做什麼）、
             `tokens`（代入內容，見 `_normalize_tokens`）、
             `result`（結果；**None = 缺值**）、
             `result_suffix`（單位）、
             `missing`（**`result is None` 時必填**：缺的是什麼）。
    source_notes : 來源註腳。**用到 `source_warn` token 就不得為空**。
                   每則自動補 `⚠` 前綴（呼叫端不必記得）。

    Raises
    ------
    ValueError : 有 `source_warn` token 卻沒給 `source_notes`。
    """
    rows: list[str] = []
    blocked = False
    used_source_warn = False

    for step in steps or []:
        step = step or {}
        label = _esc(step.get("label") or "")
        if blocked:
            # 上游缺值 → 這一步一律不計算、不顯示代入內容（避免看起來「算過了」）。
            rows.append(
                f"<div style='display:flex;gap:8px;align-items:baseline;margin:6px 0'>"
                f"<span style='font-size:11px;color:{GH_FG_MUTED};min-width:86px'>{label}</span>"
                f"<span style='font-size:14px;color:{GH_FG_MUTED}'>{BLOCKED_MARK}</span></div>")
            continue

        toks = _normalize_tokens(step.get("tokens"))
        if any(k == KIND_SOURCE_WARN for _, k in toks):
            used_source_warn = True
        sub_html = "".join(substitution_token(t, kind=k) for t, k in toks)

        result = step.get("result")
        if result is None:
            blocked = True
            missing = _esc(step.get("missing")
                           or "未提供缺值原因（呼叫端應填 step['missing']）")
            result_html = (
                f"<span style='font-size:{_RESULT_FONT_PX}px;font-weight:700;"
                f"color:{GH_FG_MUTED};font-variant-numeric:tabular-nums'>{MISSING_MARK}</span>"
                f"<span style='font-size:11px;color:{GH_FG_MUTED};margin-left:6px'>"
                f"缺：{missing}</span>")
        else:
            suffix = _esc(step.get("result_suffix") or "")
            result_html = (
                f"<span style='font-size:{_RESULT_FONT_PX}px;font-weight:700;"
                f"color:{GH_FG_PRIMARY};font-variant-numeric:tabular-nums'>"
                f"{_esc(result)}{suffix}</span>")

        rows.append(
            f"<div style='display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;"
            f"margin:6px 0'>"
            f"<span style='font-size:11px;color:{GH_FG_MUTED};min-width:86px'>{label}</span>"
            f"<span>{sub_html}</span>"
            f"<span style='color:{GH_FG_MUTED};font-size:14px'>=</span>"
            f"{result_html}</div>")

    notes = [str(n) for n in (source_notes or []) if str(n).strip()]
    if used_source_warn and not notes:
        raise ValueError(
            "算式中有 source_warn（手動輸入／估算）token，但沒有提供 source_notes。"
            "標了「這格可疑」卻不說可疑在哪，比不標更糟 —— 使用者知道有問題卻無從判斷。")

    notes_html = ""
    if notes:
        items = "".join(
            f"<div style='margin:2px 0'>"
            f"{_esc(n if str(n).startswith(WARN_PREFIX) else WARN_PREFIX + ' ' + str(n))}"
            f"</div>" for n in notes)
        notes_html = (f"<div style='border-top:1px solid {GH_BORDER};margin-top:8px;"
                      f"padding-top:6px;font-size:11px;color:{GH_FG_MUTED}'>{items}</div>")

    inner = (
        f"<div style='font-size:14px;font-weight:700;color:{GH_FG_PRIMARY};"
        f"margin-bottom:4px'>{_esc(title)}</div>"
        f"<div style='font-size:14px;color:{GH_FG_MUTED};margin-bottom:8px'>"
        f"{_esc(formula)}</div>"
        f"{''.join(rows)}"
        f"{notes_html}")
    return gh_card(inner)
