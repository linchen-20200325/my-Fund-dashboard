# -*- coding: utf-8 -*-
"""`ui_v3/adapters/assets_source.py` 測試共用的建構器（不是測試檔；檔名取唯一的 `assets_source_support`，同 `ui_v3_guard_lib` 體例）。

- 持倉表一律用 L2 純函式 `services.v2_tables.alo_holdings.build_alo_tables` 從 L1 形狀的假輸入組出（真形狀，且過 `contract.holding_row_problems`）；
- 設定列用 L1 `settings_sheet_repository` 的真形狀 `{鍵: {setting_key, setting_value, value_kind, updated_at}}`；
- L2 替身只替換「讀取入口」與例外型別；其餘（組裝、生產者）都是真的。
"""
from __future__ import annotations

import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from repositories import policy_supplement_repository as R  # noqa: E402
from services.v2_tables import alo_holdings as A  # noqa: E402
from services.v2_tables import contract  # noqa: E402

S_TAB, P_TAB = R.TAB_HOLDING_SUPPLEMENT, R.TAB_POLICY_PROFILE
SECRET = "sk-test-0123456789abcdef"      # 測試用假秘密（不是任何真的憑證）
MASK_TOKEN = "‹已遮蔽›"


def mask(text: str) -> str:
    return text.replace(SECRET, MASK_TOKEN)


# ─────────── 持倉：L1 形狀 → build_alo_tables（真形狀） ───────────

def prow(pid="PX-TEST-001", code="ZZ9999", name="Fund A", ccy="USD", invest=300000, units=1000.0, avg_nav=10.0,
         row=2, **extra):
    r = {"policy_id": pid, "fund_code": code, "fund_name": name, "currency": ccy, "tier": "core",
         "invest_twd": invest, "div_cash_pct": 100.0, "units": units, "avg_nav": avg_nav, "avg_fx": 30.0,
         "_tab": pid, "_row": row}
    r.update(extra)
    return r


def srec(row, pid="PX-TEST-001", code="ZZ9999", opened="2001-01-01", checked="2001-02-03", bucket="core"):
    return {"_row": row, "_raw": (pid, code, opened, checked, bucket or ""), "policy_id": pid, "fund_code": code,
            "opened_on": opened, "last_checked_on": checked, "bucket": bucket}


def precd(row, pid="PX-TEST-001"):
    return {"_row": row, "_raw": (pid, "n", "i", "USD", "1", "2001-01-01", "active"), "policy_id": pid,
            "policy_name": "n", "issuer": "i", "ccy": "USD", "premium_paid_twd": 1, "opened_on": "2001-01-01",
            "status": "active"}


def tabs_of(supp=(), prof=(), supp_missing=False):
    return {S_TAB: {"records": list(supp), "bad_rows": [], "blank_rows": 0, "tab_missing": supp_missing},
            P_TAB: {"records": list(prof), "bad_rows": [], "blank_rows": 0, "tab_missing": False}}


def two_fund_tables(**build_kwargs):
    """兩檔 USD 持倉（core 300000、sat 100000）。回傳 `build_alo_tables` 的整包（含 skipped_*、warnings…）。"""
    rows = [prow(row=2, code="ZZ1", invest=300000), prow(row=3, code="ZZ2", invest=100000)]
    tabs = tabs_of([srec(2, code="ZZ1", bucket="core"), srec(3, code="ZZ2", bucket="sat")], [precd(2)])
    out = A.build_alo_tables(rows, tabs, **build_kwargs)
    for h in out["holding"]:
        assert contract.holding_row_problems(h) == []
    return out


def tables_with_skips():
    """一檔寫進持倉、一檔缺持倉補充（→ `skipped_holdings`）、一個保單分頁讀不到（→ `skipped_tabs`）。"""
    rows = [prow(row=2, code="ZZ1", invest=300000), prow(row=3, code="ZZ2", invest=100000)]
    tabs = tabs_of([srec(2, code="ZZ1", bucket="core")], [precd(2)])
    return A.build_alo_tables(rows, tabs, skipped_tabs=[{"tab": "PX-OTHER", "error": f"read failed {SECRET}"}])


def holding_row(code="ZZ1", bucket="core", cost=100000, ccy="USD", policy="PX-1", holding_id=None):
    row = {"holding_id": holding_id or f"{policy}|{code}|1", "policy_id": policy, "fund_code": code, "fund_name": "Fund",
           "ccy": ccy, "units_shares": 10.0, "cost_orig_ccy": 100.0, "cost_twd": cost, "opened_on": "2001-01-01",
           "bucket": bucket, "last_synced_at": "2001-02-03T04:00:00Z"}
    assert contract.holding_row_problems(row) == []
    return row


def loaded_tables(holdings, skipped_holdings=(), skipped_tabs=()):
    return {"holding": list(holdings), "policy": [], "skipped_holdings": list(skipped_holdings),
            "skipped_tabs": list(skipped_tabs)}


# ─────────── 設定：L1 形狀的列 ───────────

_KIND = {"alo_basis": "list", "alo_target_weights": "list", "alo_tolerance_pp": "float", "alo_bucket_names": "list"}


def setting_row(key, raw):
    return {"setting_key": key, "setting_value": raw, "value_kind": _KIND.get(key, "list"),
            "updated_at": "2026-11-01T00:00:00Z"}


def settings_rows(basis="成本", targets='[{"bucket":"core","weight_ratio":0.75},{"bucket":"sat","weight_ratio":0.25}]',
                  tolerance="5", names='["core","sat"]', **extra):
    """None ＝ 不放那一列（未設）。"""
    raw = {"alo_basis": basis, "alo_target_weights": targets, "alo_tolerance_pp": tolerance,
           "alo_bucket_names": names, **extra}
    return {k: setting_row(k, v) for k, v in raw.items() if v is not None}


def settings_payload(rows=None, broken=()):   # broken 原樣放進去（測試要餵字串、整數等錯型別）
    return {"rows": settings_rows() if rows is None else rows, "bad_rows": [], "broken_keys": broken,
            "blank_rows": 0, "tab_missing": False}


# ─────────── L2 替身 ───────────

class FakeActiveSourceError(Exception):
    """替身：形狀同 `alo_holdings.ActiveSourceError`（code／reason／tab）。"""

    def __init__(self, code, reason=None, tab=None):
        self.code, self.reason, self.tab = code, reason, tab
        super().__init__(code)


class FakeSettingsError(Exception):
    pass


def real_is_no_active(exc) -> bool:
    return exc.code == "AUTH_REQUIRED" or (exc.code == "UNAVAILABLE" and exc.reason == "no_active")


KNOWN_CODES = frozenset({"AUTH_REQUIRED", "AUTH_EXPIRED", "AUTH_STATE_INVALID", "PERMISSION_DENIED", "SHEET_NOT_FOUND",
                         "SCHEMA_INVALID", "NETWORK_ERROR", "UPSTREAM_ERROR", "UNAVAILABLE"})


class Calls:
    def __init__(self):
        self.holdings, self.settings, self.fx_rule = [], [], 0


def make_reads(M, *, holdings=None, holding_exc=None, settings=None, settings_exc=None, fx_flag=False, calls=None,
               known_codes=None):
    """`M`：被測模組（真的或突變體）。`holdings`：`read_holdings` 的回傳；`*_exc`：改成拋這個例外。"""
    calls = calls if calls is not None else Calls()

    def read_holdings(state, secret_values):
        calls.holdings.append((state, tuple(secret_values)))
        if holding_exc is not None:
            raise holding_exc
        return holdings

    def read_settings(secret_values):
        calls.settings.append(tuple(secret_values))
        if settings_exc is not None:
            raise settings_exc
        return settings if settings is not None else settings_payload()

    def read_fx():
        calls.fx_rule += 1
        return fx_flag() if callable(fx_flag) else fx_flag

    reads = M.L2Reads(
        read_holdings=read_holdings, read_settings=read_settings,
        holding_errors=(FakeActiveSourceError,), settings_errors=(FakeSettingsError,),
        is_no_active=real_is_no_active, known_codes=KNOWN_CODES if known_codes is None else frozenset(known_codes),
        make_mask=lambda secrets: (lambda text: text.replace(SECRET, MASK_TOKEN) if SECRET in secrets else text),
        fx_key_of=lambda ccy: "fx_twd_per_" + ccy.lower(), read_fx_rule_verified=read_fx)
    return reads, calls
