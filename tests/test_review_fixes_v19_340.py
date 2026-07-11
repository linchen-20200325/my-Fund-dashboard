"""v19.340 — 第六份外部 review 查證後修復的回歸測試。

本輪基金端核心發現(報告 Bug 6「broad except 吞 NameError」同病灶第三次現形,
由 ruff F821 抓出、runtime 證實):

1. `sources.fetch_fund_multi_source`(多來源聚合主入口)自 v19.248 拆檔後
   `_fetch_fund_single` 漏搬 import — 每呼叫必 NameError,被 caller
   `except Exception: print` 吞掉 → `fetch_fund_from_moneydj_url` 的
   Step 2 多來源聚合 + alt page_type 重試(境內↔境外切換)全滅。
   修法:呼叫端 lazy import(同 v19.339 _parse_nav_html,循環方向:
   fund_orchestration L34 頂層 star-import sources)。
2. `repositories/policy/v1.py` 型別註解用 `Iterable` 漏 import(靠
   future-annotations 延遲求值才沒炸)— 補 import。
3. 掃描網盲區:`test_undefined_name_scan` 原只選 F405(star-import 歧義),
   無 star-import 的模組(sources.py)漏搬 import 是純 F821 → 完全看不見。
   擴 `--select F405,F821` 補上。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent


# ══════════════════════════════════════════════════════════════
# 1. fetch_fund_multi_source:主聚合入口不再 NameError
# ══════════════════════════════════════════════════════════════
class TestMultiSourceOrchestratorResolvable:
    def test_lazy_import_present(self):
        src = (REPO / "repositories/fund/sources.py").read_text(encoding="utf-8")
        assert ("from repositories.fund.fund_orchestration import "
                "_fetch_fund_single") in src, \
            "fetch_fund_multi_source 必須 lazy import _fetch_fund_single(v19.248 拆檔漏搬)"

    def test_orchestrator_runs_without_nameerror(self, monkeypatch):
        """monkeypatch 單源 fetcher 後,主入口須能正常跑完 loop 並回結果 —
        修復前這裡在第一圈就拋 NameError(runtime 已證實)。"""
        import fund_fetcher  # noqa: F401  解 circular
        from repositories.fund import fund_orchestration as O
        from repositories.fund import sources as S

        _stub = {
            "fund_code": "ZZTM99",
            "fund_name": "測試基金",
            "series": pd.Series([10.0 + i * 0.01 for i in range(15)]),
            "metrics": {"ret_1y": 5.0},
        }

        def _fake_single(code, force_refresh=False, page_type=""):
            return dict(_stub, fund_code=code)

        monkeypatch.setattr(O, "_fetch_fund_single", _fake_single)
        out = S.fetch_fund_multi_source("ZZTM99")
        assert isinstance(out, dict)
        assert out.get("fund_name") == "測試基金"
        # complete 路徑帶 orchestrator provenance(setdefault,不蓋 inner source)
        assert str(out.get("source", "")).startswith("Fund:multi_source_orchestrator")
        assert out.get("fetched_at")

    def test_failed_path_returns_error_dict_not_raise(self, monkeypatch):
        """全候選失敗 → 回 error dict(不 raise、不 NameError)。"""
        import fund_fetcher  # noqa: F401
        from repositories.fund import fund_orchestration as O
        from repositories.fund import sources as S

        monkeypatch.setattr(
            O, "_fetch_fund_single",
            lambda code, force_refresh=False, page_type="": {"fund_code": code})
        out = S.fetch_fund_multi_source("ZZTM98")
        assert isinstance(out, dict)
        assert "error" in out or out.get("fund_code")


# ══════════════════════════════════════════════════════════════
# 2. policy/v1.py Iterable import
# ══════════════════════════════════════════════════════════════
class TestPolicyV1IterableImport:
    def test_iterable_resolvable_in_module(self):
        import repositories.policy.v1 as V1
        assert hasattr(V1, "Iterable"), \
            "Iterable 型別註解必須真的 import(防拿掉 future-annotations 時 NameError)"
        assert callable(V1.sync_policies_to_portfolio_funds)


# ══════════════════════════════════════════════════════════════
# 3. 掃描網涵蓋 F821(meta-test:釘住防護網本身的選項)
# ══════════════════════════════════════════════════════════════
class TestScanNetCoversF821:
    def test_scan_selects_f405_and_f821(self):
        src = (REPO / "tests/test_undefined_name_scan.py").read_text(encoding="utf-8")
        assert '"F405,F821"' in src, \
            "掃描網必須同時選 F405+F821 — 無 star-import 模組的漏搬 import 只有 F821 看得見"

    def test_repo_is_f821_clean_now(self):
        """修復後全 production 目標須 0 個 F821(掃描網主測試的前置健檢,
        用同一組 targets;ruff 不可用時 skip — 主掃描測試會給更明確的錯誤)。"""
        import json
        import subprocess
        try:
            proc = subprocess.run(
                ["ruff", "check", "--select", "F821", "--output-format=json",
                 "repositories", "services", "ui", "infra", "shared",
                 "app.py", "fund_fetcher.py"],
                cwd=REPO, capture_output=True, text=True, timeout=60)
        except FileNotFoundError:
            pytest.skip("ruff 未安裝(requirements-dev)")
        findings = json.loads(proc.stdout or "[]")
        assert findings == [], \
            "production 程式碼存在 F821 未定義名:\n" + "\n".join(
                f"{f['filename']}:{f['location']['row']} {f['message']}"
                for f in findings)
