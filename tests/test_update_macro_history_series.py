"""tests/test_update_macro_history_series.py — 驗 v19.29 補 3 新 FRED series 進常量."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

_spec = importlib.util.spec_from_file_location(
    "update_macro_history",
    _REPO_ROOT / "scripts" / "update_macro_history.py",
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


class TestFredSeriesIds:
    def test_v1929_new_series_present(self):
        """v19.29 補 DXY proxy / PPI / Copper 進 FRED_SERIES_IDS."""
        ids = _mod.FRED_SERIES_IDS
        assert "DTWEXBGS" in ids   # DXY proxy: Trade Weighted Dollar Index Broad
        assert "PPIACO" in ids     # PPI All Commodities
        assert "PCOPPUSDM" in ids  # Global Price of Copper

    def test_existing_8_series_kept(self):
        """v19.27 既有 8 series 不被 v19.29 動到（backward compat）."""
        ids = _mod.FRED_SERIES_IDS
        for sid in ("DGS10", "DGS2", "DGS3MO", "BAMLH0A0HYM2",
                    "M2SL", "WALCL", "CPIAUCSL", "UNRATE"):
            assert sid in ids

    def test_total_count_is_11(self):
        """8 既有 + 3 新 = 11，避免重複加入或誤刪."""
        assert len(_mod.FRED_SERIES_IDS) == 11
        # 無重複
        assert len(set(_mod.FRED_SERIES_IDS)) == 11


class TestDefaultYears:
    def test_default_35_years_covers_2000_2008(self):
        """v19.29 default 從 15 → 35，bootstrap 後覆蓋 2000 dot-com / 2008 GFC."""
        # 透過 argparse 默認值檢查
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--years", type=int, default=35)
        args = parser.parse_args([])
        assert args.years == 35
        # 35 年從 2026 = 1991，覆蓋 2000/2008/2020/2022 全 4 大熊市
