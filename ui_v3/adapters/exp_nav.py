# -*- coding: utf-8 -*-
"""🔍 找基金 NAV sibling 的 adapter：**呼叫端注入**的 loader 回傳的 dict → `ExpNavView`（純函式；不取數、不算公式、不連線、不讀環境變數）。

授權與邊界同 `ui_v3/viewmodels/exp_nav.py`（A-EXP-NAV-SIBLING-FAKE-1；客戶 2026-11-24；僅本機隔離 Preview）。
- 本檔**不 import** 任何 `services`／`repositories`／`infra`／fixtures：判定與格式化是來源層（FAKE fixture；日後 L2）的事，本檔只驗形狀並轉成 view model。
- 回傳形狀：`{"nav": {...}, "judgement": {...}, "ai_usable": bool}`；`loader` 回 `None`＝這一檔沒有 NAV sibling（結果卡維持原樣，只有五欄）。
- 契約不符一律 raise `ExpNavContractError`（訊息只含欄位名與型別名）；不吞、不降級成缺值。
"""
from __future__ import annotations

from typing import Callable, Optional

from ui_v3.viewmodels.exp_nav import (
    ConflictDiag, DividendStatus, ExpNavContractError, ExpNavView, JudgementView, MetricKind, MetricView, NavDisplay, NavSummaryView,
)

__all__ = ("adapt_exp_nav", "load_exp_nav")

_NAV_KEYS = frozenset({"display", "reason_codes", "nav_value", "ccy", "nav_date", "source_label", "cache_updated_at", "supplier_fetched_at",
                       "ccy_declared_at", "ccy_declared", "time_sources_differ", "conflicts", "content_tier"})
_JUDGE_KEYS = frozenset({"three_three_three", "eating_principal", "dividend_status"})
_METRIC_KEYS = frozenset({"kind", "reason_code", "evidence"})
_CONFLICT_KEYS = frozenset({"code", "a_date", "b_date"})


def _need(ok: bool, field: str, expected: str, value: object) -> None:
    if not ok:
        raise ExpNavContractError(f"{field}: expected {expected}, got {type(value).__name__}") from None


def _dict(value: object, field: str, allowed: frozenset, required: frozenset = frozenset()) -> dict:
    _need(isinstance(value, dict), field, "dict", value)
    extra = set(value) - allowed
    _need(not extra, field, "only known keys", value)
    missing = required - set(value)
    _need(not missing, field, "all required keys", value)
    return value


def _enum(cls, value: object, field: str):
    _need(isinstance(value, str), field, "str", value)
    try:
        return cls(value)
    except ValueError:
        raise ExpNavContractError(f"{field}: expected a known {cls.__name__} value, got str") from None


def _metric(raw: object, field: str) -> MetricView:
    d = _dict(raw, field, _METRIC_KEYS, frozenset({"kind"}))
    evidence = d.get("evidence", ())
    _need(isinstance(evidence, (list, tuple)), f"{field}.evidence", "sequence", evidence)
    pairs = []
    for item in evidence:
        _need(isinstance(item, (list, tuple)) and len(item) == 2, f"{field}.evidence[]", "(label, value)", item)
        pairs.append((item[0], item[1]))
    return MetricView(_enum(MetricKind, d["kind"], f"{field}.kind"), d.get("reason_code"), tuple(pairs))


def adapt_exp_nav(raw: object) -> ExpNavView:
    """loader 回傳 dict → `ExpNavView`。形狀不符或違反 view model 不變式 → `ExpNavContractError`。"""
    top = _dict(raw, "result", frozenset({"nav", "judgement", "ai_usable"}), frozenset({"nav", "judgement"}))
    n = _dict(top["nav"], "nav", _NAV_KEYS, frozenset({"display"}))
    reasons = n.get("reason_codes", ())
    _need(isinstance(reasons, (list, tuple)), "nav.reason_codes", "sequence", reasons)
    conflicts_raw = n.get("conflicts", ())
    _need(isinstance(conflicts_raw, (list, tuple)), "nav.conflicts", "sequence", conflicts_raw)
    conflicts = tuple(ConflictDiag(**_dict(c, "nav.conflicts[]", _CONFLICT_KEYS, _CONFLICT_KEYS)) for c in conflicts_raw)
    scalar = {k: n[k] for k in n if k not in ("display", "reason_codes", "conflicts")}
    nav = NavSummaryView(_enum(NavDisplay, n["display"], "nav.display"), tuple(reasons), conflicts=conflicts, **scalar)
    j = _dict(top["judgement"], "judgement", _JUDGE_KEYS, _JUDGE_KEYS)
    judgement = JudgementView(_metric(j["three_three_three"], "judgement.three_three_three"), _metric(j["eating_principal"], "judgement.eating_principal"),
                              _enum(DividendStatus, j["dividend_status"], "judgement.dividend_status"))
    return ExpNavView(nav, judgement, top.get("ai_usable", False))


def load_exp_nav(nav_loader: Callable[[str], object], query_text: object) -> Optional[ExpNavView]:
    """呼叫**呼叫端注入**的 `nav_loader(query_text)`；回 `None`＝沒有 NAV sibling。本檔不知道、也不 import 真實的 L1／L2。"""
    _need(callable(nav_loader), "nav_loader", "callable", nav_loader)
    _need(isinstance(query_text, str) and query_text.strip(" ") != "", "query_text", "non-blank str", query_text)
    raw = nav_loader(query_text.strip(" "))
    return None if raw is None else adapt_exp_nav(raw)
