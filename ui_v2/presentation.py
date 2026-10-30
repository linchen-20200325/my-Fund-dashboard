# -*- coding: utf-8 -*-
"""B 線共用 presentation primitives（純函式；BL-0525 Batch A；`docs/v2/44_fund_ui_ssot.md` 第七節第三小節之十九）。

做什麼：把「呈現契約」要的四種共用形狀，放在 `ui_v2/` 內一處，讓日後各頁（Batch C～F）套用時不必各寫一份：

1. **metadata／status chip**（`chip`、`chip_html`、`chips_html`）：卡頭小徽章。每張卡至多 `MAX_CHIPS` 枚（之十九其一之一）；
   超過的不丟掉，由 `split_chips` 交出 `overflow`，呼叫端要放進 detail。顏色不是唯一資訊載體：chip 的狀態一律帶字（與符號）。
2. **chart card 模型**（`chart_card_model`）：標題＋3～5 枚 chips＋至多一句摘要＋（圖表由呼叫端畫、外露）＋detail。
   形狀不對（chip 數、摘要不只一句、缺標題）一律 `ValueError`（§1 Fail Loud），不默默截斷。
3. **detail 模型**（`detail_model`）：「▸ 為什麼‧來源‧限制‧去哪補」四組，預設收合；空組不畫、**全空不畫展開區**；
   內容完整保留（資訊存在與資訊外露分離，之十九其二）。
4. **Missing placeholder 模型**（`missing_model`）：卡＋`◇ 資料未備` chip＋一句短原因＋同卡 detail（必含「去哪補」組，缺了拋錯）。
   原因空白一律 `ValueError` —— Missing 不寫 0、不寫中性、不留空（missing ≠ 0；unavailable ≠ neutral）。

**不做什麼**：不 import streamlit、不 import 舊樹（`tests/ui_v2/test_ui_v2_live_import_guard.py`）；不決定資料語意、符號語意、
provenance 內容（只搬運呼叫端交來的字）；不套用到任何頁（頁面套用屬 Batch C～F）。符號與字樣取自 `ui_v2/health.py` 的常數，不另造。
畫 Streamlit 元件的部分在 `ui_v2/presentation_view.py`。
"""

from __future__ import annotations

import html as _html

from ui_v2 import health

# ───────────────────────── 常數 ─────────────────────────

MAX_CHIPS = 5          # 之十九其一之一：每張卡 metadata／status chips 至多 5 枚
MIN_CHART_CHIPS = 3    # 同上：圖卡 3～5 枚（Missing placeholder 不受下限約束，見 `missing_model`）

TONES = ("中性", "灰", "黃", "紅")

# detail 四組（順序固定；標題只列有內容的那幾組）。字面對應之十九其二「為什麼、來源、取得時間、限制、缺值規則、公式、去哪補、技術診斷」
# 的四個分組；取得時間、缺值規則、公式歸「來源」「限制」，技術診斷走既有「進階診斷」（`plain.ADVANCED_DIAG_TITLE`），不在此重畫。
DETAIL_GROUPS = ("為什麼", "來源", "限制", "去哪補")
DETAIL_PREFIX = "▸ "
DETAIL_JOINER = "‧"

MISSING_CHIP_TEXT = f"{health.SYMBOL_MISSING} {health.TEXT_MISSING}"

_SENTENCE_END = "。！？!?"


# ───────────────────────── chip ─────────────────────────


def chip(text: str, tone: str = "中性", *, title: str | None = None) -> dict:
    """一枚 chip 的資料。`text` 必須非空（空白 chip 等於沒有資訊）；`tone` 只能是 `TONES` 之一。"""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("chip 文字不得為空")
    if tone not in TONES:
        raise ValueError(f"chip tone 不在 {TONES}：{tone!r}")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        raise ValueError("chip title 若給就必須非空")
    return {"text": text.strip(), "tone": tone, "title": title}


def missing_chip() -> dict:
    """`◇ 資料未備`（44 之七其四；客戶第三則確認字樣照舊）。灰色，字與符號都在 —— 顏色不是唯一載體。"""
    return chip(MISSING_CHIP_TEXT, "灰")


def split_chips(chips, *, limit: int = MAX_CHIPS):
    """把 chips 切成（外露、溢出）。溢出的不丟 —— 呼叫端要把它放進 detail（`overflow_lines` 轉成字）。"""
    items = list(chips or ())
    for c in items:
        if not isinstance(c, dict) or "text" not in c or "tone" not in c:
            raise ValueError(f"chips 必須由 chip() 產生：{c!r}")
    return items[:limit], items[limit:]


def overflow_lines(overflow) -> list:
    """溢出的 chips 轉成 detail「限制」組可放的字（保留資訊，不外露）。"""
    return [c["text"] for c in overflow]


def _esc(value) -> str:
    return _html.escape(str(value), quote=True)


def chip_html(c: dict) -> str:
    """單枚 chip 的 HTML。樣式用 CSS class（`PRESENTATION_CSS`）；色碼由 `data-tone` 對應，不寫進行內樣式。"""
    title = f' title="{_esc(c["title"])}"' if c.get("title") else ""
    return f'<span class="pc-chip" data-tone="{_esc(c["tone"])}"{title}>{_esc(c["text"])}</span>'


def chips_html(chips) -> str:
    """一列 chips。超過 `MAX_CHIPS` 直接 `ValueError`（呼叫端應先 `split_chips`）；空列回空字串。"""
    items = list(chips or ())
    if len(items) > MAX_CHIPS:
        raise ValueError(f"一張卡的 chips 至多 {MAX_CHIPS} 枚，收到 {len(items)} 枚；請先 split_chips")
    if not items:
        return ""
    return f'<div class="pc-chips">{"".join(chip_html(c) for c in items)}</div>'


# ───────────────────────── 一句摘要 ─────────────────────────


def is_one_sentence(text: str) -> bool:
    """至多一句：非空、不含換行、句末標點（。！？）只在結尾。"""
    if not isinstance(text, str):
        return False
    s = text.strip()
    if not s or "\n" in s:
        return False
    body = s[:-1] if s[-1] in _SENTENCE_END else s
    return not any(ch in _SENTENCE_END for ch in body)


# ───────────────────────── detail ─────────────────────────


def detail_model(*, why=(), source=(), limits=(), where=()) -> dict:
    """「▸ 為什麼‧來源‧限制‧去哪補」的資料。

    回 `{"title": ..., "groups": [(組名, [行,...]), ...]}`；沒有任何一組有內容時回 `{"title": None, "groups": []}`
    （呼叫端不畫展開區）。每一行必須是非空字串 —— 空行代表上游漏了資訊，不默默吞掉。
    """
    raw = {"為什麼": why, "來源": source, "限制": limits, "去哪補": where}
    groups = []
    for name in DETAIL_GROUPS:
        lines = []
        for line in raw[name] or ():
            if not isinstance(line, str) or not line.strip():
                raise ValueError(f"detail「{name}」含空白行")
            lines.append(line.strip())
        if lines:
            groups.append((name, lines))
    if not groups:
        return {"title": None, "groups": []}
    title = DETAIL_PREFIX + DETAIL_JOINER.join(name for name, _ in groups)
    return {"title": title, "groups": groups}


def detail_html(detail: dict) -> str:
    """detail 的內文 HTML（不含展開區外殼；外殼由 view 層決定用 `st.expander` 還是巢狀時的純區塊）。"""
    parts = []
    for name, lines in detail["groups"]:
        items = "".join(f"<li>{_esc(line)}</li>" for line in lines)
        parts.append(f'<div class="pc-detail-group"><div class="pc-detail-name">{_esc(name)}</div><ul>{items}</ul></div>')
    return "".join(parts)


def detail_texts(detail: dict) -> list:
    """detail 裡的全部字（含組名與標題）；測試與「資訊未遺失」檢查用。"""
    out = []
    if detail["title"]:
        out.append(detail["title"])
    for name, lines in detail["groups"]:
        out.append(name)
        out.extend(lines)
    return out


# ───────────────────────── chart card ─────────────────────────


def chart_card_model(title: str, chips, summary: str, *, detail: dict | None = None) -> dict:
    """圖卡的資料：標題＋3～5 枚 chips＋至多一句摘要＋detail。圖表本身由呼叫端畫（外露、不放進展開區）。

    chips 超過上限的由呼叫端先 `split_chips`、溢出放 detail；這裡超過或不足一律 `ValueError`。
    """
    if not isinstance(title, str) or not title.strip():
        raise ValueError("圖卡標題不得為空")
    items = list(chips or ())
    if not (MIN_CHART_CHIPS <= len(items) <= MAX_CHIPS):
        raise ValueError(f"圖卡 chips 須 {MIN_CHART_CHIPS}～{MAX_CHIPS} 枚，收到 {len(items)} 枚")
    split_chips(items)  # 驗每枚都是 chip() 產的
    if not is_one_sentence(summary):
        raise ValueError(f"圖卡摘要須為至多一句、非空、不含換行：{summary!r}")
    det = detail if detail is not None else detail_model()
    return {"kind": "chart_card", "title": title.strip(), "chips": items, "summary": summary.strip(), "detail": det}


def chart_card_head_html(model: dict) -> str:
    """圖卡「圖表之前」的那一段：標題、chips、一句摘要（短，確保圖表在首屏）。"""
    return (
        f'<div class="pc-card-head"><span class="pc-card-title">{_esc(model["title"])}</span></div>'
        f'{chips_html(model["chips"])}'
        f'<div class="pc-summary">{_esc(model["summary"])}</div>'
    )


# ───────────────────────── Missing placeholder ─────────────────────────


def missing_model(title: str, reason: str, *, detail: dict | None = None, extra_chips=()) -> dict:
    """Missing 卡：標題＋`◇ 資料未備` chip（可再加至多 `MAX_CHIPS - 1` 枚說明用 chip）＋一句短原因＋同卡 detail。

    - `reason` 空白或不只一句 → `ValueError`（不留空白 Missing 卡，也不拿數段技術文字填滿）。
    - 不產生任何數值欄位：這個模型沒有 value，所以不可能被畫成 0 或中性。
    - **detail 必須含「去哪補」組**（客戶契約：Missing 卡同卡有「▸ 去哪補」）；沒給或缺該組 → `ValueError`。
    """
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Missing 卡標題不得為空")
    if not is_one_sentence(reason):
        raise ValueError(f"Missing 原因須為非空的一句短句：{reason!r}")
    chips = [missing_chip(), *list(extra_chips or ())]
    if len(chips) > MAX_CHIPS:
        raise ValueError(f"Missing 卡 chips 至多 {MAX_CHIPS} 枚，收到 {len(chips)} 枚")
    split_chips(chips)
    if detail is None or "去哪補" not in [name for name, _ in detail["groups"]]:
        raise ValueError("Missing 卡的 detail 必須含「去哪補」組（detail_model(where=[...])）")
    det = detail
    return {"kind": "missing", "title": title.strip(), "chips": chips, "reason": reason.strip(), "detail": det}


def missing_card_html(model: dict) -> str:
    return (
        f'<div class="pc-card-head"><span class="pc-card-title">{_esc(model["title"])}</span></div>'
        f'{chips_html(model["chips"])}'
        f'<div class="pc-missing-reason">{_esc(model["reason"])}</div>'
    )


# ───────────────────────── CSS ─────────────────────────

# 色碼取自 `ui_v2/mkt/theme.py` 的 `TONE_HEX`（淺色殼層）；這裡只複製四個值，不 import 頁面 theme（避免共用模組反過來依賴某一頁）。
PRESENTATION_CSS = """
.pc-card-head{display:flex;align-items:baseline;gap:.5rem;margin:0 0 .25rem}
.pc-card-title{font-weight:600}
.pc-chips{display:flex;flex-wrap:wrap;gap:.25rem .4rem;margin:.1rem 0 .35rem}
.pc-chip{display:inline-block;padding:.05rem .5rem;border:1px solid currentColor;border-radius:999px;font-size:.78rem;line-height:1.5;white-space:nowrap}
.pc-chip[data-tone="中性"]{color:#1f2328}
.pc-chip[data-tone="灰"]{color:#59636e}
.pc-chip[data-tone="黃"]{color:#8a5a00}
.pc-chip[data-tone="紅"]{color:#cf222e}
.pc-summary,.pc-missing-reason{font-size:.92rem;margin:.1rem 0 .4rem}
.pc-missing-reason{color:#59636e}
.pc-detail-group{margin:.2rem 0}
.pc-detail-name{font-weight:600;font-size:.85rem}
.pc-detail-group ul{margin:.1rem 0 .2rem 1.1rem;padding:0;font-size:.85rem}
""".strip()
