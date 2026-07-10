"""tests/test_hotfix_v19_335.py — 2026-07-10 雲端倒站 hotfix 守護。

事故:Streamlit Cloud 平台強制遷 Python 3.14 + pyarrow 25.0.0 當日發布 →
死釘 streamlit==1.45.1(早於 py3.14 支援)的本 app 啟動即 Segmentation fault。

TARGET: requirements.txt(streamlit 升 1.59.1 / pyarrow cap 24.x)
本地全套件 2,402 tests 本就在 streamlit 1.59.1 上執行 — 版本升級已預驗證。
"""
from __future__ import annotations

from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]


class TestRequirementsHotfix:
    @property
    def _req(self) -> str:
        return (_REPO / "requirements.txt").read_text(encoding="utf-8")

    def test_streamlit_bumped_to_py314_capable(self):
        req = self._req
        assert "streamlit>=1.59.1,<1.60.0" in req
        # 死釘不得復活 — 只檢查生效行(hotfix 事故註解本身會提到舊 pin)
        active = [ln for ln in req.splitlines()
                  if ln.strip() and not ln.strip().startswith("#")]
        assert not any(ln.strip().startswith("streamlit==") for ln in active)

    def test_pyarrow_capped_below_25(self):
        assert "pyarrow>=14,<25" in self._req

    def test_local_env_matches_new_floor(self):
        # 守護「本地測試環境 = 部署目標版本」前提(全套件即在此版驗證)
        import streamlit
        parts = tuple(int(x) for x in streamlit.__version__.split(".")[:2])
        assert parts >= (1, 59)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
