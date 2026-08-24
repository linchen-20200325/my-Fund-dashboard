"""v19.516:週報 cron 讀持倉的 sheet 選擇(scripts/weekly_switch_notify._load_client_and_sheet)。

2026-08-24 dry-run 實測:持倉/選股池自 v19.462 起存於 POLICY_SHEET_ID(使用者持倉本),
但 cron 原本把 macro_weights_sheet_id 當帳本來源 → 讀到 404、持倉 0。修:優先 POLICY_SHEET_ID,
未設才退 macro_weights(舊單本設定零變化)。此 sheet_id 只餵 _read_holdings;選股池另走 list_pool。

註:本檔只碰 weekly_switch_notify + infra.config + policy_repository,不觸 fund_service,
故無 fund_fetcher 循環 import 疑慮(不需 prime)。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import weekly_switch_notify as M  # noqa: E402


def _patch_secrets(monkeypatch, secrets: dict):
    import infra.config as CFG
    import repositories.policy_repository as PR
    monkeypatch.setattr(CFG, "get_secret", lambda k, *a, **kw: secrets.get(k, ""))
    monkeypatch.setattr(PR, "get_gspread_client", lambda sa, *a, **kw: ("client", sa))


def test_prefers_policy_sheet_id(monkeypatch):
    _patch_secrets(monkeypatch, {
        "google_service_account": "SA_JSON",
        "POLICY_SHEET_ID": "POL_ID",
        "macro_weights_sheet_id": "MW_ID",
    })
    client, sid = M._load_client_and_sheet()
    assert sid == "POL_ID"                       # 優先持倉本(持倉在此)
    assert client == ("client", "SA_JSON")


def test_falls_back_to_macro_weights_when_no_policy(monkeypatch):
    _patch_secrets(monkeypatch, {
        "google_service_account": "SA_JSON",
        "POLICY_SHEET_ID": "",                    # 未設(舊單本設定)
        "macro_weights_sheet_id": "MW_ID",
    })
    _, sid = M._load_client_and_sheet()
    assert sid == "MW_ID"                         # 退回 macro_weights,行為零變化


def test_none_when_both_sheet_ids_missing(monkeypatch):
    _patch_secrets(monkeypatch, {"google_service_account": "SA_JSON"})  # 兩本都缺
    client, sid = M._load_client_and_sheet()
    assert client is None and sid is None         # 呼叫端據此 exit 2(§1 不靜默)


def test_none_when_no_service_account(monkeypatch):
    _patch_secrets(monkeypatch, {"POLICY_SHEET_ID": "POL_ID"})          # 缺 SA
    client, sid = M._load_client_and_sheet()
    assert client is None and sid is None
