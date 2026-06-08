"""v18.162 PR：雲端讀寫 helper（純函式，便於上下方快捷面板共用）。

抽自 ui/tab3_portfolio.py L884-980 的「全部寫入」「全部讀回」核心邏輯。
Streamlit-agnostic：warning / error 透過 return 的 dict 帶出，由 caller 顯示。
這樣上方快捷面板（v18.162 新）與下方 L884+ 完整面板都用同一份序列化規則。
"""
from __future__ import annotations

from typing import Any, MutableMapping

from models.policy import fund_pk_str
from repositories.policy_repository import (
    ALL_COLS_V2,
    ITEM_TYPE_FUND,
    PolicySheetError,
    _is_quota_error,
    detect_sheet_schema_version,
    load_all_policies_v2,
    load_all_policy_worksheets,
    load_policies,
    sync_policies_to_portfolio_funds,
    upsert_fund_in_policy,
    write_policy_v2,
)
from repositories.snapshot_repository import (
    load_all_ledgers_snapshot,
    save_all_ledgers_snapshot,
    save_holdings_overview,
)
from infra.oauth import OAuthError


def _dump_all_to_sheet_v2(client: object,
                            sheet_id: str,
                            ss: MutableMapping[str, Any]) -> dict:
    """v18.250 PR C：v2 schema 主寫入路徑（per-policy 整 tab 覆寫 13 欄）。

    portfolio_funds + t7_ledgers groupby policy_id 後組成 v2 DataFrame，
    per-policy call `write_policy_v2`。**不寫 `_T7_State` / `_持倉總覽`**
    （v2 schema 13 欄已含 units/avg_nav/fx_avg，足以重建持倉）。

    成本基礎來源 priority：t7_ledger.position（權威）→ fund dict 欄位（fallback）
    """
    import pandas as pd  # noqa: PLC0415
    out = {"ok": False, "written": 0, "skipped_no_pid": 0,
           "n_state": 0, "n_overview": 0, "warnings": [], "error": None}
    try:
        _t7 = ss.get("t7_ledgers", {}) or {}
        _by_policy: dict[str, list[dict]] = {}
        for _f in ss.get("portfolio_funds", []) or []:
            _pid = str(_f.get("policy_id", "") or "").strip()
            _code = str(_f.get("code", "") or "").strip().upper()
            if not _pid:
                out["skipped_no_pid"] += 1
                continue
            if not _code:
                continue
            _pos = getattr(_t7.get(fund_pk_str(_f)), "position", None)
            _avg_nav = (float(getattr(_pos, "cost_unit", 0) or 0) if _pos
                        else float(_f.get("avg_nav", 0) or 0))
            _fx_avg = (float(getattr(_pos, "fx_avg", 0) or 0) if _pos
                       else float(_f.get("fx_avg", 0) or 0))
            _units = (float(getattr(_pos, "units", 0) or 0) if _pos
                      else float(_f.get("units", 0) or 0))
            _by_policy.setdefault(_pid, []).append({
                "policy_id":        _pid,
                "item_type":        ITEM_TYPE_FUND,
                "fund_code":        _code,
                "fund_name":        str(_f.get("name", "") or ""),
                "units":            _units,
                "avg_nav":          _avg_nav,
                "avg_nav_with_div": float(_f.get("avg_nav_with_div", 0) or 0),
                "avg_fx":           _fx_avg,
                "currency":         str(_f.get("currency", "")),
                "tier":             ("core" if _f.get("is_core") else
                                     "satellite" if _f.get("is_core") is False
                                     else ""),
                "amount":           0,
                "invest_twd":       int(_f.get("invest_twd", 0) or 0),
                "div_cash_pct":     float(_f.get("div_cash_pct", 100) or 0),
            })
        _written = 0
        _errors: list[str] = []
        # v18.253：節流 — 每保單寫入後 sleep 0.15s，13 檔 ≈ 2s 額外延遲，
        # 避免短時間集中砲轟撞 Google Sheets 60 reads/min quota（每檔 4-6 個 API call）
        import time as _time  # noqa: PLC0415
        _pids = list(_by_policy.items())
        for _i, (_pid, _rows) in enumerate(_pids):
            try:
                _df = pd.DataFrame(_rows, columns=list(ALL_COLS_V2))
                _n = write_policy_v2(client, sheet_id, _pid, _df)
                _written += int(_n)
            except (PolicySheetError, OAuthError) as _e:
                _errors.append(f"{_pid}: {str(_e)[:80]}")
            if _i < len(_pids) - 1:
                _time.sleep(0.15)
        out["written"] = _written
        if _errors:
            out["warnings"].append(
                f"⚠️ {len(_errors)} 個保單分頁寫入失敗："
                + "；".join(_errors[:5])
                + ("…" if len(_errors) > 5 else ""))
        out["ok"] = True
    except (PolicySheetError, OAuthError) as _pe:
        out["error"] = f"v2 寫入失敗：{_pe}"
    except Exception as _e:
        out["error"] = f"未預期錯誤：[{type(_e).__name__}] {_e}"
    return out


def dump_all_to_sheet(client: object,
                      sheet_id: str,
                      ss: MutableMapping[str, Any]) -> dict:
    """全部寫入：portfolio_funds → 保單分頁 + t7_ledgers → _T7_State。

    v18.250 PR C：開頭 detect schema 版本 — 已升級到 v2 (header 含 `item_type`)
    → 自動走 `_dump_all_to_sheet_v2`（per-policy 整 tab 覆寫 13 欄 schema）；
    v1 / empty / detect 失敗 → 維持下方既有 v1 path（向後相容、不破壞舊資料）。

    回傳 dict：
      - ok:               bool — 整體是否成功（True 即使有 warnings）
      - written:          int  — 寫進保單分頁的基金數
      - skipped_no_pid:   int  — 因無 policy_id 被略過的基金數
      - n_state:          int  — 寫進 _T7_State 的快照列數（v2 path = 0）
      - warnings:         list[str] — 非致命警告（如 _T7_State 寫入失敗訊息）
      - error:            str|None  — 致命錯誤訊息（PolicySheetError / OAuthError）
    """
    # v18.250: schema-aware routing
    try:
        _ver = detect_sheet_schema_version(client, sheet_id)
    except Exception:
        _ver = "v1"   # detect 失敗保險走舊路徑
    if _ver == "v2":
        return _dump_all_to_sheet_v2(client, sheet_id, ss)

    out = {"ok": False, "written": 0, "skipped_no_pid": 0,
           "n_state": 0, "n_overview": 0, "warnings": [], "error": None}
    try:
        _written = 0
        _skipped_no_pid = 0
        _write_errors: list[str] = []   # v18.189：收集 per-fund 寫入失敗（原本靜默 continue）
        _t7 = ss.get("t7_ledgers", {}) or {}   # v18.198：成本基礎權威來源
        for _f in ss.get("portfolio_funds", []) or []:
            _pid = str(_f.get("policy_id", "") or "").strip()
            _code = str(_f.get("code", "") or "").strip().upper()
            if not _pid:
                _skipped_no_pid += 1
                continue
            if not _code:
                continue
            # v18.198：完整成本基礎優先取 t7_ledgers（帳本），缺則退 portfolio_funds
            _pos = getattr(_t7.get(fund_pk_str(_f)), "position", None)
            _avg_nav = (float(getattr(_pos, "cost_unit", 0) or 0) if _pos
                        else float(_f.get("avg_nav", 0) or 0))
            _fx_avg = (float(getattr(_pos, "fx_avg", 0) or 0) if _pos
                       else float(_f.get("fx_avg", 0) or 0))
            _units = (float(getattr(_pos, "units", 0) or 0) if _pos
                      else float(_f.get("units", 0) or 0))
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
                    # v18.198：完整成本基礎（平均買入淨值/匯率/單位數）
                    "avg_nav":          _avg_nav,
                    "fx_avg":           _fx_avg,
                    "units":            _units,
                })
                _written += 1
            except (PolicySheetError, OAuthError) as _e_up:
                # v18.189：不再靜默 — 收集失敗原因，讓「含息成本沒寫進去」這類
                # 問題能在畫面上看到根因（配額/權限/表頭升級失敗…）而非默默漏寫。
                _write_errors.append(f"{_pid}/{_code}：{str(_e_up)[:100]}")
                continue
        out["written"] = _written
        out["skipped_no_pid"] = _skipped_no_pid
        if _write_errors:
            out["warnings"].append(
                f"⚠️ {len(_write_errors)} 檔寫入保單分頁失敗（含息成本/欄位可能沒存進去）："
                + "；".join(_write_errors[:5])
                + ("…" if len(_write_errors) > 5 else ""))

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


def _load_all_from_sheet_v2(client: object,
                              sheet_id: str,
                              ss: MutableMapping[str, Any],
                              *,
                              refresh_only: bool = False) -> dict:
    """v18.250 PR C：v2 schema 主讀回路徑（13 欄 → portfolio_funds + ledger）。

    從 v2 13 欄反推：
    - portfolio_funds：保留 prev fund 的 metadata（name/series/dividends/metrics/
      moneydj_raw），覆蓋 units/avg_nav/avg_fx/invest_twd/div_cash_pct/is_core 等
      持倉欄位（13 欄帶來的最新值）
    - t7_ledgers：對每檔 units>0 的基金，建空 Ledger + 一筆 subscribe 還原
      position snapshot（units / cost_unit / fx_avg / TWD 成本）

    **trade-off**：完整 transactions 歷史不從 v2 重建（13 欄沒這個資訊）；
    若需歷史，仍需 `_T7_State` snapshot — 但 v2 主路徑設計上不依賴它。
    """
    from datetime import date as _date
    out = {"ok": False, "refresh_only": refresh_only,
           "added": [], "kept": [], "removed": [], "reused": [],
           "restored_ct": 0, "reconciled_added": 0,
           "warnings": [], "error": None}
    try:
        _df = load_all_policies_v2(client, sheet_id)
        if not _df.empty and "policy_id" in _df.columns:
            ss["policy_tabs"] = sorted(
                {str(_t).strip() for _t in _df["policy_id"] if str(_t).strip()})
        else:
            ss["policy_tabs"] = []
        ss["policies_df"] = _df

        if refresh_only:
            out["ok"] = True
            return out

        _prev_funds = list(ss.get("portfolio_funds", []) or [])
        _prev_by_pk = {fund_pk_str(_f): _f for _f in _prev_funds}
        _new_funds: list[dict] = []
        _prev_codes = {fund_pk_str(_f) for _f in _prev_funds}
        _new_codes = set()
        for _, _row in _df.iterrows():
            if str(_row.get("item_type", "")).strip() != ITEM_TYPE_FUND:
                continue   # 跳過 cash 列（後續可擴）
            _pid = str(_row.get("policy_id", "") or "").strip()
            _code = str(_row.get("fund_code", "") or "").strip().upper()
            if not _pid or not _code:
                continue
            _pk = f"{_pid}::{_code}"
            _new_codes.add(_pk)
            _prev = _prev_by_pk.get(_pk) or {}
            _tier = str(_row.get("tier", "") or "").strip().lower()
            _new_funds.append({
                **_prev,   # 保留 name / series / dividends / metrics / moneydj_raw 等
                "code":             _code,
                "policy_id":        _pid,
                "name":             (str(_row.get("fund_name", "") or "").strip()
                                       or _prev.get("name", "") or _code),
                "currency":         (str(_row.get("currency", "") or "").strip()
                                       or _prev.get("currency", "USD")),
                "units":            float(_row.get("units", 0) or 0),
                "avg_nav":          float(_row.get("avg_nav", 0) or 0),
                "avg_nav_with_div": float(_row.get("avg_nav_with_div", 0) or 0),
                "fx_avg":           float(_row.get("avg_fx", 0) or 0),
                "invest_twd":       int(_row.get("invest_twd", 0) or 0),
                "div_cash_pct":     float(_row.get("div_cash_pct", 100) or 0),
                "is_core":          (True if _tier == "core" else
                                     False if _tier == "satellite" else None),
            })
        ss["portfolio_funds"] = _new_funds
        out["added"]   = sorted(_new_codes - _prev_codes)
        out["kept"]    = sorted(_new_codes & _prev_codes)
        out["removed"] = sorted(_prev_codes - _new_codes)

        # 從 13 欄重建 ledger snapshot
        try:
            from services.ledger_service import Ledger as _Ledger
            _new_ledgers: dict = {}
            for _f in _new_funds:
                _u = float(_f.get("units") or 0)
                _n = float(_f.get("avg_nav") or 0)
                _fx = float(_f.get("fx_avg") or 0)
                if _u > 0 and _n > 0 and _fx > 0:
                    _led = _Ledger(fund_code=_f["code"],
                                    currency=_f.get("currency", "USD"))
                    try:
                        _led.subscribe(amount_twd=_u * _n * _fx,
                                        fx_rate=_fx, nav=_n,
                                        txn_date=_date.today())
                        _new_ledgers[fund_pk_str(_f)] = _led
                    except Exception:
                        continue
            ss["t7_ledgers"] = _new_ledgers
            out["restored_ct"] = len(_new_ledgers)
            ss.pop("_t7_auto_restore_done", None)
            ss.pop("_t7_auto_estimate_done", None)
        except Exception as _e_ld:
            out["warnings"].append(
                f"v2 ledger 重建失敗（不影響 portfolio_funds）：{str(_e_ld)[:80]}")

        out["ok"] = True
    except (PolicySheetError, OAuthError) as _pe:
        if _is_quota_error(_pe):
            out["error"] = ("⏳ Google Sheets 讀取配額暫時超載（每分鐘上限）。"
                             "請等 30~60 秒再按「📥 立即全部讀回」。")
        else:
            out["error"] = f"v2 讀取失敗：{_pe}"
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
    # v18.250 PR C：schema-aware routing — v2 走專屬 helper
    if oauth_mode:
        try:
            _ver = detect_sheet_schema_version(client, sheet_id)
        except Exception:
            _ver = "v1"
        if _ver == "v2":
            return _load_all_from_sheet_v2(
                client, sheet_id, ss, refresh_only=refresh_only)

    out = {"ok": False, "refresh_only": refresh_only,
           "added": [], "kept": [], "removed": [], "reused": [],
           "restored_ct": 0, "reconciled_added": 0,
           "warnings": [], "error": None}
    try:
        if oauth_mode:
            _pdf = load_all_policy_worksheets(client, sheet_id)
            # v18.199：policy_tabs 直接從已讀回的 DataFrame 推（policy_id 欄 = 分頁名），
            # 不再額外呼叫 list_policy_worksheets → 省一次 open_by_key + worksheets 讀取
            # （切換/重讀帳本時讀取配額吃緊、易觸發 429 Quota exceeded）。
            if not _pdf.empty and "policy_id" in _pdf.columns:
                ss["policy_tabs"] = sorted(
                    {str(_t).strip() for _t in _pdf["policy_id"] if str(_t).strip()})
            else:
                ss["policy_tabs"] = []
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

        # v18.191：讀取齊全 — 保證每個帳本部位都有 portfolio_funds spine + 回填成本
        # 基礎（avg_nav/fx_avg/units/含息成本）。修 user「讀取時帳本一直缺資料」：
        # 保單分頁與 _T7_State 漂移時，只在快照裡的基金原本會看不到。
        try:
            from ui.helpers.portfolio_load import reconcile_funds_with_ledgers
            _rec_funds, _n_added = reconcile_funds_with_ledgers(
                ss.get("portfolio_funds", []), ss.get("t7_ledgers", {}))
            ss["portfolio_funds"] = _rec_funds
            out["reconciled_added"] = _n_added
        except Exception as _e_rec:
            out["warnings"].append(
                f"帳本對帳失敗（不影響既有資料）：{str(_e_rec)[:80]}")

        out["ok"] = True
    except (PolicySheetError, OAuthError) as _pe:
        # v18.199：429 配額超載 → 友善訊息（切換/重讀太頻繁，等 30-60s 配額重置即可）
        if _is_quota_error(_pe):
            out["error"] = ("⏳ Google Sheets 讀取配額暫時超載（每分鐘上限）。"
                            "剛切換 / 重讀帳本太頻繁——請等 30~60 秒，待配額重置後"
                            "再按一次「📥 立即全部讀回」即可（資料沒壞）。")
        else:
            out["error"] = f"Sheet 操作失敗：{_pe}"
    except Exception as _e:
        if _is_quota_error(_e):
            out["error"] = ("⏳ Google Sheets 讀取配額暫時超載（每分鐘上限）。"
                            "請等 30~60 秒再按「📥 立即全部讀回」。")
        else:
            out["error"] = f"未預期錯誤：[{type(_e).__name__}] {_e}"
    return out
