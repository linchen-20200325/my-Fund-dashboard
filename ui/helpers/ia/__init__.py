"""IA kit —— 五分頁資訊架構的四大鐵則共用元件（2026-09-01 客戶拍板線框）。

線框：`docs/wireframes/ia-wireframe.html`（規範性文件，客戶已逐字確認）。四大鐵則與其落點：

===== ====================== ==========================================
鐵則   內容                   實作在哪
===== ====================== ==========================================
01     三欄自適應網格          :mod:`ui.helpers.ia.layout`
02     Form 封裝防重繪         :mod:`ui.helpers.ia.gated_form`
03     三態顏色分離            **`ui/helpers/render_state.py`（既有 SSOT）**
                              ＋ :mod:`ui.helpers.ia.cards`（把三態收成參數）
04     首屏無冗餘占位          :mod:`ui.helpers.ia.empty_state`
===== ====================== ==========================================

⚠️ **鐵則 03 沒有在本套件重新實作，這是刻意的，不是漏做。**
`ui/helpers/render_state.py` 已經是三態顏色的 SSOT（2026-08-28／08-31 兩批落地，
色票在 `shared/colors.py`：`BUSINESS_ALERT_ON_DARK` 等）。本套件**不 re-export
它的三個入口**，因為 re-export 會讓同一個函式有兩條 import path，
下一個人就有兩個地方可以改 —— 那正是 SSOT 要防的事（`CLAUDE.md §2.1`）。

**要用三態，請直接**::

    from ui.helpers.render_state import business_alert, not_ready, system_error

本套件只在 :mod:`~ui.helpers.ia.cards` 提供一個**組合**入口
（`state_card(..., state=...)`），把「挑哪個顏色」從呼叫端的自由心證
變成一個必填參數 —— 那是 `render_state` 沒有、也不該有的東西
（它是顏色層，不知道什麼叫「一張卡」）。

守衛
----
`tests/test_ia_kit.py`：
- 本套件內**不得出現 hex 色碼字面值**（顏色一律走 `shared.colors`，§3.3）；
- 本套件內**不得自己實作三態**（必須 import `render_state`）；
- 三個狀態必須畫出**三種不同的 widget**（不是三種文案）。
"""
from __future__ import annotations

from ui.helpers.ia.cards import (
    CARD_STATES,
    STATE_BUSINESS,
    STATE_ERROR,
    STATE_NOT_READY,
    STATE_OK,
    render_cards,
    state_card,
)
from ui.helpers.ia.empty_state import empty_state
from ui.helpers.ia.gated_form import APPLY_LABEL, FormGate, applied_form
from ui.helpers.ia.layout import GRID_COLS, card_grid, card_row, wide_table

__all__ = [
    # 鐵則 01
    "GRID_COLS", "card_row", "card_grid", "wide_table",
    # 鐵則 02
    "APPLY_LABEL", "FormGate", "applied_form",
    # 鐵則 03（組合層；顏色本身在 ui.helpers.render_state）
    "CARD_STATES", "STATE_OK", "STATE_NOT_READY", "STATE_BUSINESS",
    "STATE_ERROR", "state_card", "render_cards",
    # 鐵則 04
    "empty_state",
]
