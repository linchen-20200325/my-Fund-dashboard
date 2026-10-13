"""scripts/dividend_calendar_png.py — 每月配息日曆推播的 PNG 產圖(編排層)。

2026-10-13 客戶裁示(LINE 推播與舊 UI 解耦):「兩支 LINE 推播保留……核准把它們目前借用的
`ui/helpers` 必要函式搬到適當共用層。要求:不讓排程依賴 UI;不改推播業務語意;不新增資料來源……」

`render_month_calendar_png` 原住 `ui/helpers/dividend_calendar_render.py`,本函式**原封搬來**
(函式本體一字未改)。為什麼放這裡、不放 `services/`:
  - 它做兩件事:組 HTML(純字串,已搬到 L2 `services/dividend_calendar_render.py`)+
    委派 L0 `infra.html_to_png` 啟動 headless Chromium 截圖(**I/O**)。
  - L2 的 import 白名單(`tests/test_services_purity_contract.py`)不收 `infra.html_to_png`,
    且該守衛明言「請修掉它,而不是把它加進豁免表」;`infra/`(L0)又不得往上依賴 `services/`。
  - 它全 repo 唯一的 production 呼叫者就是 `scripts/dividend_calendar_notify.py`(App 只用 HTML)。
  → 放在排程同一層(編排層,與 `app.py` 同為組裝者),依賴方向 scripts → services / infra 皆合法。
HTML 樣板仍只有 L2 那一份,App(方式 A)與推播(方式 C)共用 —— 推播圖與 App 畫面不會走鐘。
"""
from __future__ import annotations

from services.dividend_calendar_render import (
    _PUSH_WIDTH,
    _TITLE_DEFAULT,
    render_month_calendar_html,
)


def render_month_calendar_png(cal: dict, *, title: str = _TITLE_DEFAULT,
                              is_sample: bool = False, width: int = _PUSH_WIDTH,
                              scale: int = 2) -> bytes:
    """月曆結構 → PNG bytes(headless Chromium 截 `render_month_calendar_html` 的 `.wrap`)。

    user 2026-08-24 選「截 App 那張最像」:重用**同一份 HTML 樣板**(App 方式 A / LINE 方式 C 單一
    SSOT),故推播圖與 App 畫面一模一樣,不會走鐘。截圖 I/O **委派 L0** `infra.html_to_png`(本函式
    只組合 HTML + 呼叫,不直接開瀏覽器 → 合法下行依賴)。lazy import → App 只取 HTML 時不載入 playwright。

    Raises:
        infra.html_to_png.HtmlRenderError — playwright 缺 / Chromium 無法啟動 / 逾時(§1);
        呼叫端(每月 cron)接到後退回 Flex / 純文字,提醒仍送達。
    """
    from infra.html_to_png import html_to_png
    _html = render_month_calendar_html(cal, title=title, is_sample=is_sample, compact=True)
    # require_cjk:本圖滿版中文 —— runner 缺中文字型會整張畫成 tofu 方塊,寧可 raise 讓呼叫端退
    # Flex/純文字,也不推一張沒人看得懂的圖(§1)。
    return html_to_png(_html, width=width, scale=scale, selector=".wrap",
                       color_scheme="light", require_cjk=True)


__all__ = ["render_month_calendar_png"]
