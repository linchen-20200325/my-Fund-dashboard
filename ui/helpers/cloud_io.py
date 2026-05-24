"""v18.162 PR：雲端讀寫 helper（純函式，便於上下方快捷面板共用）。

抽自 ui/tab3_portfolio.py L884-980 的「全部寫入」「全部讀回」核心邏輯。
Streamlit-agnostic：warning / error 透過 return 的 dict 帶出，由 caller 顯示。
這樣上方快捷面板（v18.162 新）與下方 L884+ 完整面板都用同一份序列化規則。
"""
from __future__ import annotations

from typing import Any, MutableMapping

from models.policy import fund_pk_str
from repositories.policy_repository import (
    PolicySheetError,
    list_policy_worksheets,
    load_all_policy_worksheets,
    load_policies,
    sync_policies_to_portfolio_funds,
    upsert_fund_in_policy,
)
from repositories.snapshot_repository import (
    load_all_ledgers_snapshot,
    save_all_ledgers_snapshot,
    save_holdings_overview,
)
from infra.oauth import OAuthError


def dump_all_to_sheet(client: object,
                      sheet_id: str,
                      ss: MutableMapping[str, Any]) -> dict:
    """全部寫入：portfolio_funds → 保單分頁 + t7_ledgers → _T7_State。

    回傳 dict：
      - ok:               bool — 整體是否成功（True 即使有 warnings）
      - written:          int  — 寫進保單分頁的基金數
      - skipped_no_pid:   int  — 因無 policy_id 被略過的基金數
      - n_state:          int  — 寫進 _T7_State 的快照列數
      - warnings:         list[str] — 非致命警告（如 _T7_State 寫入失敗訊息）
      - error:            str|None  — 致命錯誤訊息（PolicySheetError / OAuthError）
    """
    out = {"ok": False, "written": 0, "skipped_no_pid": 0,
           "n_state": 0, "n_overview": 0, "warnings": [], "error": None}
    try:
        _written = 0
        _skipped_no_pid = 0
        for _f in ss.get("portfolio_funds", []) or []:
            _pid = str(_f.get("policy_id", "") or "").strip()
            _code = str(_f.get("code", "") or "").strip().upper()
            if not _pid:
                _skipped_no_pid += 1
                continue
            if not _code:
                continue
            try:
                upsert_fund_in_policy(client, sheet_id, _pid, {
                    "fund_url":     _code,
                    "policy_name":  _pid,
                    "invest_twd":   int(_f.get("invest_twd", 0) or 0),
                    "invest_date":  "",
                    "currency":     str(_f.get("currency", "")),
                    "fx_at_buy":    0.0,
                    "notes":        "v18.162 全部寫入",
                    "policy_tier":  ("core" if _f.get("is_core")
                                     else "satellite"
                                     if _f.get("is_core") is False
                                     else ""),
                    # v18.183：現金給付% + 含息成本也寫進保單分頁
                    "div_cash_pct":     float(_f.get("div_cash_pct", 100) or 0),
                    "avg_nav_with_div": float(_f.get("avg_nav_with_div", 0) or 0),
                })
                _written += 1
            except (PolicySheetError, OAuthError):
                continue
        out["written"] = _written
        out["skipped_no_pid"] = _skipped_no_pid

        _t7_dict = ss.get("t7_ledgers", {}) or {}
        _funds_lookup = {fund_pk_str(_f): _f
                         for _f in ss.get("portfolio_funds", []) or []}
        if _t7_dict:
            try:
                out["n_state"] = save_all_ledgers_snapshot(
                    client, sheet_id, _t7_dict, _funds_lookup)
            except (PolicySheetError, OAuthError) as _e_sn:
                out["warnings"].append(
                    f"_T7_State 寫入失敗：{str(_e_sn)[:120]}")
            # v18.182：人看得懂的完整成本帳本 → _持倉總覽
            try:
                out["n_overview"] = save_holdings_overview(
                    client, sheet_id, _t7_dict, _funds_lookup)
            except (PolicySheetError, OAuthError) as _e_ov:
                out["warnings"].append(
                    f"_持倉總覽 寫入失敗：{str(_e_ov)[:120]}")
        out["ok"] = True
    except (PolicySheetError, OAuthError) as _pe:
        out["error"] = f"Sheet 寫入失敗：{_pe}"
    except Exception as _e:
        out["error"] = f"未預期錯誤：[{type(_e).__name__}] {_e}"
    return out


def load_all_from_sheet(client: object,
                        sheet_id: str,
                        ss: MutableMapping[str, Any],
                        *,
                        oauth_mode: bool,
                        refresh_only: bool = False) -> dict:
    """全部讀回 / 只刷新清單。

    refresh_only=True 時只刷新 policy_tabs / policies_df，不動本地投組。

    回傳 dict：
      - ok:           bool
      - refresh_only: bool — 跟 input 對齊
      - added/kept/removed: list[str] — sync_policies_to_portfolio_funds report
      - restored_ct:  int  — T7 ledger 還原筆數
      - warnings:     list[str]
      - error:        str|None
    """
    out = {"ok": False, "refresh_only": refresh_only,
           "added": [], "kept": [], "removed": [], "reused": [],
           "restored_ct": 0, "warnings": [], "error": None}
    try:
        if oauth_mode:
            _pdf = load_all_policy_worksheets(client, sheet_id)
            _tabs = list_policy_worksheets(client, sheet_id)
            ss["policy_tabs"] = _tabs
        else:
            _pdf = load_policies(client, sheet_id)
        ss["policies_df"] = _pdf

        if refresh_only:
            out["ok"] = True
            return out

        _prev_funds = list(ss.get("portfolio_funds", []) or [])
        _merged, _report = sync_policies_to_portfolio_funds(_pdf, _prev_funds)
        # 跨帳本共用基金資訊：同 code 上一本已載入過 → 沿用免重抓（持倉仍走新帳本）
        from ui.helpers.portfolio_load import reuse_fund_info_by_code
        out["reused"] = reuse_fund_info_by_code(_merged, _prev_funds)
        ss["portfolio_funds"] = _merged
        out["added"]   = list(_report.get("added", []))
        out["kept"]    = list(_report.get("kept", []))
        out["removed"] = list(_report.get("removed", []))

        try:
            from services.ledger_service import Ledger as _Ledger
            _restored = load_all_ledgers_snapshot(client, sheet_id, _Ledger)
            # v18.187：一律覆蓋 t7_ledgers（含「空 → 清掉」）。否則切換到「沒有
            # _T7_State 快照」的帳本時會殘留前一本的帳本，造成 user 反映的
            # 「切換帳本後帳本無法更新」（持倉換了、T7 帳本面板卻還是舊本）。
            ss["t7_ledgers"] = _restored or {}
            out["restored_ct"] = len(_restored or {})
            # 清自動還原旗標 → 換帳本後 T7 區塊會對「新帳本」重跑 auto-restore，
            # 新本無快照時 t7_ledgers 維持空（正確），不再顯示舊本資料。
            ss.pop("_t7_auto_restore_done", None)
            ss.pop("_t7_auto_estimate_done", None)
            if _restored:
                try:
                    from ui.tab3_t7_ledger import _sync_invest_twd_from_ledgers
                    _sync_invest_twd_from_ledgers()
                except Exception as _e_sync:
                    out["warnings"].append(
                        f"invest_twd 同步失敗（不影響資料正確性）：{str(_e_sync)[:80]}")
        except (PolicySheetError, OAuthError) as _e_ld:
            out["warnings"].append(f"_T7_State 讀回失敗：{str(_e_ld)[:120]}")
        out["ok"] = True
    except (PolicySheetError, OAuthError) as _pe:
        out["error"] = f"Sheet 操作失敗：{_pe}"
    except Exception as _e:
        out["error"] = f"未預期錯誤：[{type(_e).__name__}] {_e}"
    return out
