"""services/switch_notify.py — 換股顧問「該不該通知 + 通知文字」(v19.432)。L2 純函式,零 IO。

吃 `switch_advisor.advise_switches` 的結果 → 決定週報**該不該推播**(沒事不吵)+ 組一段
精簡的 LINE 文字。純邏輯,不碰網路/不抓資料(資料由 scripts/weekly_switch_notify headless 備好)。

**該通知的定義(actionable)**:任一持倉 →
- action ∈ {SWITCH(換股), SELL_CASH(賣轉現金)},或
- 表現差(underperformance.is_underperforming;跑輸大盤或絕對虧損)。
單純 WARN(成長看衰未跌破)/ HOLD / 資料不足 **不觸發通知**(避免每週噪音)。§1:誠實,不硬報。
"""
from __future__ import annotations

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


def build_notification(result: dict, *, portfolio_name: "str | None" = None,
                       as_of: "str | None" = None, skipped: int = 0,
                       source_by_code: "dict | None" = None) -> dict:
    """advise_switches 結果 → {should_notify, message, n_actionable, actionable_codes}。

    should_notify=False 時 message 仍給一段「本週無需換股」摘要(呼叫端可選擇不送)。
    skipped:抓不到資料、未納入評估的標的檔數(§1 誠實帶進訊息,不讓「N 檔」看起來像全部)。
    source_by_code:{code: "持倉"/"觀察"}(選填);有給則每檔前面標來源。既有 caller 不傳 → 行為零變化。
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

    if not _actionable:
        _msg = f"{_header}\n\n✅ 本週無需換股：所有標的續抱 / 觀察中。{_skip_note}\n\n{_tail}\n{_caveat}"
        return {"should_notify": False, "message": _msg[:_LINE_TEXT_MAX],
                "n_actionable": 0, "actionable_codes": []}

    _lines = [f"⚠️ 本週有 {len(_actionable)} 檔需留意：", ""]
    _shown = _actionable[:_MAX_DETAIL_ROWS]
    _lines.append("\n\n".join(
        _holding_line(a, _src.get(str(a.get("code") or ""), "")) for a in _shown))
    if len(_actionable) > _MAX_DETAIL_ROWS:
        _lines.append(f"\n…另有 {len(_actionable) - _MAX_DETAIL_ROWS} 檔(開 App 看完整)")

    _msg = f"{_header}\n\n" + "\n".join(_lines) + f"{_skip_note}\n\n{_tail}\n{_caveat}"
    if len(_msg) > _LINE_TEXT_MAX:
        _msg = _msg[:_LINE_TEXT_MAX - 1] + "…"
    return {"should_notify": True, "message": _msg, "n_actionable": len(_actionable),
            "actionable_codes": [str(a.get("code") or "") for a in _actionable]}


__all__ = ["build_notification"]
