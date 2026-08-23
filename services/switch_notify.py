"""services/switch_notify.py — 換股顧問「該不該通知 + 通知文字」(v19.432)。L2 純函式,零 IO。

吃 `switch_advisor.advise_switches` 的結果 → 決定週報**該不該推播**(沒事不吵)+ 組一段
精簡的 LINE 文字。純邏輯,不碰網路/不抓資料(資料由 scripts/weekly_switch_notify headless 備好)。

**該通知的定義(actionable)**:任一持倉 →
- action ∈ {SWITCH(換股), SELL_CASH(賣轉現金)},或
- 表現差(underperformance.is_underperforming;跑輸大盤或絕對虧損)。
單純 WARN(成長看衰未跌破)/ HOLD / 資料不足 **不觸發通知**(避免每週噪音)。§1:誠實,不硬報。
"""
from __future__ import annotations

import math

from services.switch_advisor import HOLD, INSUFFICIENT, SELL_CASH, SWITCH, WARN  # noqa: F401

_LINE_TEXT_MAX = 4800          # LINE 單則文字上限 ~5000,留 buffer
_MAX_DETAIL_ROWS = 12          # 明細最多列幾檔(其餘收斂成「…還有 N 檔」)


def _is_actionable(a: dict) -> bool:
    """單筆建議是否值得通知:型態觸發換股/賣出,或表現差。"""
    if a.get("action") in (SWITCH, SELL_CASH):
        return True
    return bool((a.get("underperformance") or {}).get("is_underperforming"))


def _cand_of(a: dict) -> "dict | None":
    """該筆的建議換入標的(型態換股優先,否則表現差挑的)。"""
    return a.get("switch_to") or a.get("underperf_candidate")


def _holding_line(a: dict, source: str = "") -> str:
    """單檔一段精簡文字(來源標籤 + 名稱 + 建議 + 表現差原因 + 換入標的)。"""
    _name = a.get("name") or a.get("code") or "?"
    _tag = f"[{source}] " if source else ""
    _bits = [f"• {_tag}{_name}", f"  {a.get('action_zh', '')}".rstrip()]
    _u = a.get("underperformance") or {}
    if _u.get("is_underperforming"):
        _rz = "・".join(_u.get("reasons") or []) or "表現差"
        _ex = _u.get("excess_pct")
        _bits.append(f"  ⚠️ {_rz}" + (f"(vs 大盤 {_ex:+.1f}pp)" if isinstance(_ex, (int, float)) else ""))
    _c = _cand_of(a)
    if _c and _c.get("code"):
        _bs = _c.get("buy_sigma")
        _bs_txt = f"(σ{_bs:.2f})" if isinstance(_bs, (int, float)) else ""
        _bits.append(f"  → 建議換入:{_c.get('name') or _c.get('code')}{_bs_txt}")
    elif _u.get("is_underperforming"):
        _bits.append("  → 選股池無合適替代標的(不硬湊)")
    return "\n".join(_bits)


def _fmt_hwm(v) -> str:
    """距 HWM %(距高點)→ 精簡文字。數值:『距高:-8%』;字串原樣;None/空 → ''(§1 不臆造)。"""
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        if math.isnan(v) or math.isinf(v):       # §1:NaN/inf 不渲染成「距高:nan%」假數字
            return ""
        return f"距高:{v:+.0f}%"                   # 強制帶號(下方=負);與源字串 '-8.00%' 口徑一致
    _s = str(v).strip()
    return f"距高:{_s}" if _s else ""


def _status_line(r: dict, source: str = "") -> str:
    """單檔基金狀況一行:『• [來源] 名稱 ｜4D:X ｜距高:-N% ｜🔴吃本金』。
    缺欄位誠實省略(不臆造);全缺 → 標『資料不足』(§1)。"""
    _name = str(r.get("name") or r.get("code") or "?")[:14]
    _tag = f"[{source}] " if source else ""
    _bits = [f"• {_tag}{_name}"]
    _g = r.get("4D Grade")
    if _g:
        _bits.append(f"4D:{_g}")
    _hwm_txt = _fmt_hwm(r.get("距 HWM %"))
    if _hwm_txt:
        _bits.append(_hwm_txt)
    _eat = str(r.get("吃本金燈號") or "").strip()
    if _eat.startswith("🔴") or _eat.startswith("🟡"):   # 只標警示等級(🟢/空省略,省字)
        _bits.append(_eat)
    if len(_bits) == 1:
        _bits.append("資料不足")                          # §1:無任何指標 → 誠實標,不留空
    return " ｜".join(_bits)


def build_fund_status_section(rows: "list | None", *, source_by_code: "dict | None" = None,
                              max_rows: int = 20) -> str:
    """assembled rows(含 4D Grade / 距 HWM % / 吃本金燈號)→ 一段精簡「基金狀況總覽」LINE 文字。

    **L2 純函式**,零 IO(rows 由 headless script 備妥)。每檔一行精簡狀況;無 rows → '' (呼叫端不附)。
    §1:缺欄位省略、全缺標「資料不足」;超過 max_rows 收斂成「…另有 N 檔」誠實不謊報全覆蓋。
    user 2026-08-23:附進換股週報,定期看持倉狀況。
    """
    _rows = [r for r in (rows or []) if r]
    if not _rows:
        return ""
    _src = source_by_code or {}
    # 標題檔數:有來源標記時拆「持倉／觀察」(§1 不讓觀察清單灌水成「你的持倉數」)。
    _n_hold = sum(1 for r in _rows if _src.get(str(r.get("code") or "")) == "持倉")
    _n_watch = sum(1 for r in _rows if _src.get(str(r.get("code") or "")) == "觀察")
    if _src and (_n_hold or _n_watch):
        _cnt = f"{len(_rows)} 檔:持倉 {_n_hold}／觀察 {_n_watch}"
    else:
        _cnt = f"{len(_rows)} 檔"
    _shown = _rows[:max_rows]
    _lines = [_status_line(r, _src.get(str(r.get("code") or ""), "")) for r in _shown]
    _out = f"🩺 基金狀況總覽（{_cnt}）：\n" + "\n".join(_lines)
    if len(_rows) > max_rows:
        _out += f"\n…另有 {len(_rows) - max_rows} 檔(開 App 看完整)"
    return _out


def build_notification(result: dict, *, portfolio_name: "str | None" = None,
                       as_of: "str | None" = None, skipped: int = 0,
                       source_by_code: "dict | None" = None,
                       fund_status_section: str = "") -> dict:
    """advise_switches 結果 → {should_notify, message, n_actionable, actionable_codes}。

    should_notify=False 時 message 仍給一段「本週無需換股」摘要(呼叫端可選擇不送)。
    skipped:抓不到資料、未納入評估的標的檔數(§1 誠實帶進訊息,不讓「N 檔」看起來像全部)。
    source_by_code:{code: "持倉"/"觀察"}(選填);有給則每檔前面標來源。既有 caller 不傳 → 行為零變化。
    fund_status_section:選填,`build_fund_status_section` 產出的「基金狀況總覽」文字;有給則附進訊息
      (user 2026-08-23「基金狀況併進週報」)。空字串 → 行為零變化,不影響既有 caller。
    """
    _advices = (result or {}).get("advices") or []
    _summary = (result or {}).get("summary") or {}
    _actionable = [a for a in _advices if _is_actionable(a)]
    _src = source_by_code or {}

    _hdr_bits = ["📊 換股顧問週報"]
    if portfolio_name:
        _hdr_bits.append(str(portfolio_name))
    if as_of:
        _hdr_bits.append(str(as_of))
    _header = " · ".join(_hdr_bits)

    _tail = (
        f"標的 {_summary.get('n_holdings', len(_advices))} 檔｜"
        f"換股 {_summary.get('n_switch', 0)}｜賣轉現金 {_summary.get('n_sell_cash', 0)}｜"
        f"表現差 {_summary.get('n_underperforming', 0)}"
    )
    _skip_note = f"\n⬜ 另有 {skipped} 檔資料不足、未評估" if skipped and skipped > 0 else ""
    _caveat = "※ 教學紀律工具,非獲利保證;請自行判斷後再決定。"
    _tailblock = f"\n\n{_tail}\n{_caveat}"

    def _assemble(body: str) -> str:
        """body + 基金狀況(吃剩餘預算)+ tail/caveat。§1:免責/摘要**永遠保留**,長 section 只截自己
        (稽核修:原本 section 插在 caveat 前 + 尾端截斷 → 免責會被先切掉)。"""
        _budget = _LINE_TEXT_MAX - len(body) - len(_tailblock)
        _blk = ""
        if fund_status_section and _budget > 4:       # 4:預留「\n\n」+「…」
            _cand = f"\n\n{fund_status_section}"
            _blk = _cand if len(_cand) <= _budget else (_cand[:_budget - 1] + "…")
        _full = body + _blk + _tailblock
        return _full if len(_full) <= _LINE_TEXT_MAX else (_full[:_LINE_TEXT_MAX - 1] + "…")

    if not _actionable:
        _body = f"{_header}\n\n✅ 本週無需換股：所有標的續抱 / 觀察中。{_skip_note}"
        return {"should_notify": False, "message": _assemble(_body),
                "n_actionable": 0, "actionable_codes": []}

    _lines = [f"⚠️ 本週有 {len(_actionable)} 檔需留意：", ""]
    _shown = _actionable[:_MAX_DETAIL_ROWS]
    _lines.append("\n\n".join(
        _holding_line(a, _src.get(str(a.get("code") or ""), "")) for a in _shown))
    if len(_actionable) > _MAX_DETAIL_ROWS:
        _lines.append(f"\n…另有 {len(_actionable) - _MAX_DETAIL_ROWS} 檔(開 App 看完整)")

    _body = f"{_header}\n\n" + "\n".join(_lines) + _skip_note
    return {"should_notify": True, "message": _assemble(_body), "n_actionable": len(_actionable),
            "actionable_codes": [str(a.get("code") or "") for a in _actionable]}


__all__ = ["build_notification", "build_fund_status_section"]
