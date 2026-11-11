# -*- coding: utf-8 -*-
"""核准色票（G3：候選 B）在**實際用到的配對**上的 WCAG 2.x 對比守衛（fast lane；純運算，不需要 streamlit／瀏覽器）。

- 配對清單＝CSS 真的把哪個色放在哪個底上（`design/theme.py`／`shell/nav.py`／`pages/mkt.py`）；色值取自 `ui_v3/design/tokens.py`
  （改 token 值而讓某配對跌破門檻，這裡會紅）。公式：相對亮度（`c≤0.03928` 取 `c/12.92`，否則 `((c+0.055)/1.055)^2.4`）、
  比值 `(L亮+0.05)/(L暗+0.05)`；半透明（圖的 `opacity`）先以 alpha 合成到底色再算。
- 門檻：一般文字 ≥4.5；非文字 UI 元件邊界／圖形物件 ≥3；裝飾性分隔線／座標軸底線不判（列在 `DECORATIVE`，不是漏測）。
- 負控：在記憶體內現編一個低對比配對，確認 `failures()` 真的會報；不改任何檔案。
- ⚠️ 作者自驗：獨立第二組複算另行進行（見 build evidence）；本檔只鎖「token 改了之後不會悄悄跌破門檻」。
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import ui_v3_guard_lib as lib  # noqa: F401  (把 repo 根加進 sys.path)
from ui_v3.design import tokens

TEXT, UI = 4.5, 3.0


def _rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _lin(c: int) -> float:
    x = c / 255
    return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4


def luminance(rgb: Tuple[int, int, int]) -> float:
    r, g, b = (_lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fg: Tuple[int, int, int], bg: Tuple[int, int, int]) -> float:
    a, b = luminance(fg), luminance(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def over(fg: Tuple[int, int, int], alpha: float, bg: Tuple[int, int, int]) -> Tuple[int, int, int]:
    return tuple(round(f * alpha + b * (1 - alpha)) for f, b in zip(fg, bg))  # type: ignore[return-value]


def _c(name: str) -> Tuple[int, int, int]:
    return _rgb(tokens.value(name))  # type: ignore[arg-type]


def _tone(tone: str, part: str) -> Tuple[int, int, int]:
    return _rgb(tokens.value(f"color.tone.{tone}")[part])  # type: ignore[index]


def pairs() -> List[Tuple[str, Tuple[int, int, int], Tuple[int, int, int], float]]:
    page, surf, t1, t2 = _c("color.page.bg"), _c("color.surface"), _c("color.text.primary"), _c("color.text.secondary")
    sb, sb2, sbt, sbt2 = _c("color.sidebar.bg"), _c("color.sidebar.bg2"), _c("color.sidebar.text"), _c("color.sidebar.text2")
    accent, primary, border = _c("color.sidebar.accent"), _c("color.primary"), _c("color.card.border")
    out: List[Tuple[str, Tuple[int, int, int], Tuple[int, int, int], float]] = [
        ("主文字 on 主背景", t1, page, TEXT), ("主文字 on 卡面", t1, surf, TEXT),
        ("次要文字 on 主背景", t2, page, TEXT), ("次要文字 on 卡面", t2, surf, TEXT),
        ("側欄文字 on 側欄底", sbt, sb, TEXT), ("側欄文字 on 側欄 secondary", sbt, sb2, TEXT),
        ("側欄次要文字 on 側欄底", sbt2, sb, TEXT), ("側欄次要文字 on 側欄 secondary", sbt2, sb2, TEXT),
        ("側欄強調 on 側欄底", accent, sb, UI), ("側欄強調 on 側欄 secondary", accent, sb2, UI),
        ("primary on 卡面", primary, surf, UI), ("primary on 主背景", primary, page, UI), ("白色內點 on primary", surf, primary, UI),
        ("卡片邊線 on 主背景", border, page, UI), ("卡片邊線 on 卡面", border, surf, UI),
        ("圖刻度文字（opacity .7）on 卡面", over(t1, 0.7, surf), surf, TEXT), ("圖線與端點標籤 on 卡面", t1, surf, UI),
    ]
    for tone in tokens.TONE_KEYS:
        out += [(f"chip {tone}：字 on 底", _tone(tone, "text"), _tone(tone, "background"), TEXT),
                (f"chip {tone}：邊 on 卡面", _tone(tone, "border"), surf, UI),
                (f"chip {tone}：邊 on 主背景", _tone(tone, "border"), page, UI)]
    return out


# 裝飾性線條：不判 3:1（分隔／座標軸底線；資訊不靠它傳達）。列出來是為了「不是漏測」。
DECORATIVE = ("側欄邊線 on 側欄底（分隔線、停用按鈕框）", "圖座標軸底線（opacity .35）on 卡面")


def failures(rows=None) -> List[Tuple[str, float, float]]:
    return [(label, round(ratio(fg, bg), 2), need) for label, fg, bg, need in (pairs() if rows is None else rows)
            if ratio(fg, bg) < need]


def test_every_approved_pairing_clears_its_wcag_threshold():
    assert failures() == []


def test_known_values_match_the_hand_computed_table():
    """與 evidence 的獨立自算表對得上（容差 0.01）；同時驗公式本身（黑對白＝21）。"""
    assert abs(ratio((0, 0, 0), (255, 255, 255)) - 21.0) < 1e-9
    expect: Dict[str, float] = {"主文字 on 卡面": 16.27, "次要文字 on 卡面": 7.35, "primary on 主背景": 5.45,
                                "卡片邊線 on 主背景": 3.16, "側欄文字 on 側欄底": 14.60, "chip red：字 on 底": 7.67}
    got = {label: ratio(fg, bg) for label, fg, bg, _ in pairs()}
    for label, want in expect.items():
        assert abs(got[label] - want) < 0.01, (label, got[label], want)


def test_no_listed_pairing_is_below_3_to_1_decorative_lines_are_not_listed():
    """清單內每一組（文字或非文字）都 ≥3；裝飾線（`DECORATIVE`）不在清單內，所以不會被誤當成已驗。"""
    assert [label for label, fg, bg, _ in pairs() if ratio(fg, bg) < UI] == []
    assert not {label for label, *_ in pairs()} & set(DECORATIVE)


def test_negative_control_low_contrast_pair_is_reported():
    surf = _c("color.surface")
    bad = [("假的淺灰字 on 白", _rgb("#cdcecf"), surf, TEXT), ("假的淺邊線 on 白", _rgb("#cdcecf"), surf, UI)]
    assert [f[0] for f in failures(bad)] == ["假的淺灰字 on 白", "假的淺邊線 on 白"]
