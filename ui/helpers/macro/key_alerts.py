"""ui/helpers/macro/key_alerts.py — ⚡ 今日關鍵橫幅 HTML(L3 純渲染)。

v19.349:股票 repo v19.108 `key_alerts_banner` 同構移植(色票改本 repo
shared/colors SSOT)。資料來自 L2 services/macro/daily_key_alerts;本檔
只做 dict → HTML 字串,零取數零 session_state。
- 有異常:紅/黃左框橫條,item 以 chip 併排(hover title=白話 detail)。
- 無異常:細綠條「今日無異常」— 誠實顯示掃描過而非硬擠內容(§1)。
"""
from __future__ import annotations

from shared.colors import (  # v19.389 V3a:chip 底/框/字色收 GH_* SSOT(inline hex 為精確複本)
    GH_BG_CARD, GH_BORDER, GH_FG_PRIMARY,
    TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW,
)


def key_alerts_banner(result: dict) -> str:
    items = (result or {}).get('items') or []
    if not items:
        return ('<div style="background:#0d2318;border-left:3px solid '
                f'{TRAFFIC_GREEN};border-radius:0 6px 6px 0;padding:6px 14px;'
                'margin:4px 0 10px 0;">'
                f'<span style="color:{TRAFFIC_GREEN};font-size:12px;">'
                '✅ 今日關鍵：訊號＋拐點雙層掃描無異常</span></div>')
    _n_red = (result or {}).get('n_red', 0)
    _bc = TRAFFIC_RED if _n_red else TRAFFIC_YELLOW
    _bg = '#2d1b1b' if _n_red else '#2d2208'
    _chips = ''.join(
        f'<span title="{i.get("detail", "")}" '
        f'style="display:inline-block;background:{GH_BG_CARD};border:1px solid {GH_BORDER};'
        f'border-radius:6px;padding:2px 8px;margin:2px 6px 2px 0;font-size:12px;'
        f'color:{GH_FG_PRIMARY};cursor:help;">{i.get("emoji", "")} {i.get("text", "")}</span>'
        for i in items)
    return (f'<div style="background:{_bg};border-left:3px solid {_bc};'
            'border-radius:0 6px 6px 0;padding:8px 14px;margin:4px 0 10px 0;">'
            f'<span style="color:{_bc};font-weight:700;font-size:13px;">'
            f'⚡ 今日關鍵（{len(items)} 項）</span><br>{_chips}'
            '<div style="font-size:10px;color:#8b949e;margin-top:2px;">'
            '滑鼠停在項目上看白話說明｜訊號層=指標評分超限（依校準權重排序）'
            '｜拐點層=景氣拐點偵測命中</div></div>')
