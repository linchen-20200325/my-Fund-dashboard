"""ui/components/status.py — 全站狀態色 / 燈號 SSOT 單一入口 (v19.388 V2)。

收斂目標(可視化稽核 ② 狀態色):原本 TRAFFIC_* 與 MATERIAL_* 兩套近似 status ramp
並存,加上散落的 inline hex 複本 → 「綠=好」在一頁一個綠、下一頁另一個綠。本檔把狀態
語意收斂成單一 `status_color(level)`:**TRAFFIC 為唯一 status SSOT**(user F-GRAY-4
決定),`MATERIAL_*` 降為「資料視覺 accent」(sparkline 線色),不再當狀態色用。

dataviz 準則 #4:狀態色恆帶 icon + label,不靠顏色單獨編碼 → `status_chip()` 一律附 emoji。

level 語意(容錯別名見 `_ALIASES`):
    ok / good   → 🟢 綠   正常、健康、通過
    warn        → 🟡 黃   警戒、留意
    caution     → 🟠 橘   次級警示、邊緣
    bad / crit  → 🔴 紅   危險、吃本金、觸發
    unknown     → ⬜ 灰   缺資料 / disabled(§1 誠實)

2026-08-05 稽核 🟡 必修 5 裁決(`PROCESS.md §4` 0-consumer 條款)= **保留 + 接線**。
理由:`_TABLE` 是全站燈號「emoji + 文字」的語意 SSOT,刪了會讓各處重新各寫一份
(稽核當下已經有 3 份複本)。已接的 production consumer:
  1. `ui/helpers/macro/beginner_view.py::_LEVEL_EMOJI` — 四時域 / 五桶 bar 的燈號
     emoji 收本檔 SSOT(原本 3 個函式各自維護一份 {"green":"🟢",...})。
     ⚠️ **只收 emoji、未收 hex**:該 bar 現用 `MATERIAL_*`,換成本檔的 `TRAFFIC_*`
     會改動畫面顏色 = user 未要求的視覺變更(`CLAUDE.md §-1`),留待 user 拍板。
  2. `ui/tab1_macro.py::_render_realtime_decision_dashboard` — 經 `stat_tile()`
     的 `status=` 參數使用(加碼 ok / 減倉 caution / 全撤 bad)。
  3. `ui/tab1_macro.py` 綜合健康度 hero 下方的 F-RECON-1 **對帳 chip** —
     原本是手刻 emoji 的 `st.caption`,改吃 `status_chip()`。

✅ **0-consumer 已清零(v19.429)**:`status_hex()` 已刪除。它是 `status_color(x).hex`
   的 2 行取值糖、production 0 caller;前一輪以「四個 Coder 平行作業期間不宜刪公開
   helper」暫留,該理由在合併時已失效(全 repo 無任何 caller)。依 `PROCESS.md §4`
   「0 consumer → 接線或刪除,不得留著假裝有揭露」處置。需要 hex 直接用
   `status_color(level).hex`。
"""
from __future__ import annotations

from typing import NamedTuple

from shared.colors import (
    TRAFFIC_GREEN,
    TRAFFIC_NEUTRAL,
    TRAFFIC_ORANGE,
    TRAFFIC_RED,
    TRAFFIC_YELLOW,
)


class Status(NamedTuple):
    level: str
    hex: str
    emoji: str
    label: str


# 別名 → 標準 level(容錯:大小寫 / 常見同義詞)
_ALIASES = {
    "ok": "ok", "good": "ok", "green": "ok", "pass": "ok", "healthy": "ok", "safe": "ok",
    "warn": "warn", "warning": "warn", "yellow": "warn", "watch": "warn",
    "caution": "caution", "orange": "caution", "edge": "caution",
    "bad": "bad", "crit": "bad", "critical": "bad", "red": "bad", "danger": "bad", "fail": "bad",
    "unknown": "unknown", "none": "unknown", "na": "unknown", "n/a": "unknown",
    "gray": "unknown", "grey": "unknown", "disabled": "unknown",
}

_TABLE = {
    "ok":      Status("ok",      TRAFFIC_GREEN,   "🟢", "正常"),
    "warn":    Status("warn",    TRAFFIC_YELLOW,  "🟡", "警戒"),
    "caution": Status("caution", TRAFFIC_ORANGE,  "🟠", "留意"),
    "bad":     Status("bad",     TRAFFIC_RED,     "🔴", "危險"),
    "unknown": Status("unknown", TRAFFIC_NEUTRAL, "⬜", "資料不足"),
}


def status_color(level, *, default: str = "unknown") -> Status:
    """level(容錯別名)→ Status(level, hex, emoji, label)。無法識別 → default(預設 unknown)。"""
    key = _ALIASES.get(str(level).strip().lower())
    if key is None:
        key = _ALIASES.get(str(default).strip().lower(), "unknown")
    return _TABLE[key]


# v19.429 刪除 `status_hex(level)` —— `status_color(x).hex` 的 2 行糖,production
# 0 consumer。依 PROCESS.md §4「0 consumer 等同未達標;若確實不需要 → 刪除,而不是
# 留著假裝有揭露」。前一輪以「平行作業期間不宜刪公開 helper」暫留,該理由在合併時
# 已失效(全 repo 無任何 caller)。需要 hex 請直接用 `status_color(level).hex`。


def status_chip(label: str, level, *, sublabel: str = "") -> str:
    """狀態 chip HTML:恆帶 emoji + 文字(dataviz #4:不靠顏色單獨編碼)。caller 自行 st.markdown。"""
    s = status_color(level)
    sub = (f" <span style='color:{TRAFFIC_NEUTRAL};font-size:11px'>{sublabel}</span>"
           if sublabel else "")
    return (f"<span style='display:inline-flex;align-items:center;gap:6px;"
            f"font-size:12.5px;color:{s.hex}'>{s.emoji} {label}{sub}</span>")
