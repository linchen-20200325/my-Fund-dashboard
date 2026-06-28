"""tests/test_schemas_phase_a.py — Pandera Phase A pilot 守衛(v19.155)

SPEC §18 / CLAUDE.md §3.1 — DataFrame 契約集中宣告。本檔守:
1. MacroFredSchema 對合法 fetch_fred 輸出 pass
2. 對 illegal column drift 立擋(date 重複 / value NaN / source 缺前綴 / fetched_at 格式錯)
3. validate_fred wrapper 空 df 通行(§1 Fail Loud 由 caller 處理)
4. strict=False 允許 FRED 原始額外欄位
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd
import pytest
from pandera.errors import SchemaError

from shared.schemas import MacroFredSchema, validate_fred


def _good_df(rows: int = 3) -> pd.DataFrame:
    """合法 fetch_fred 輸出 fixture。"""
    base = _dt.datetime(2026, 1, 1)
    return pd.DataFrame({
        "date": [base + _dt.timedelta(days=i) for i in range(rows)],
        "value": [1.0 + i * 0.1 for i in range(rows)],
        "source": [f"FRED:CPILFESL"] * rows,
        "fetched_at": ["2026-06-26T12:00:00+00:00"] * rows,
        "realtime_start": [base + _dt.timedelta(days=i) for i in range(rows)],
    }).astype({
        "date": "datetime64[ns]",
        "realtime_start": "datetime64[ns]",
    })


class TestSchemaPassesValidInput:
    def test_basic_pass(self):
        df = _good_df()
        out = validate_fred(df)
        assert out is not None
        assert len(out) == 3

    def test_realtime_start_nullable(self):
        """部分 series 缺 realtime_start → NaT,應 pass。"""
        df = _good_df()
        df["realtime_start"] = pd.NaT
        validate_fred(df)  # 不 raise = pass

    def test_strict_false_allows_extra_columns(self):
        """FRED 原始 obs 可能帶 realtime_end / realtime_period 等,應 pass。"""
        df = _good_df()
        df["realtime_end"] = pd.to_datetime("2099-12-31")
        df["custom_field"] = "anything"
        validate_fred(df)  # strict=False → 不 raise

    def test_empty_df_passes(self):
        """fetch 失敗回空 DF → validate_fred 直接 pass(§1 Fail Loud 由 caller 處理)。"""
        empty = pd.DataFrame()
        out = validate_fred(empty)
        assert out is empty

    def test_none_passes(self):
        out = validate_fred(None)
        assert out is None


class TestSchemaRejectsIllegalInput:
    def test_duplicate_date_rejected(self):
        df = _good_df()
        df.loc[1, "date"] = df.loc[0, "date"]
        with pytest.raises((SchemaError, Exception)) as exc:
            validate_fred(df)
        assert "date" in str(exc.value).lower() or "unique" in str(exc.value).lower()

    def test_non_monotonic_date_rejected(self):
        df = _good_df(3)
        # 反轉,變 desc
        df = df.iloc[::-1].reset_index(drop=True)
        with pytest.raises((SchemaError, Exception)):
            validate_fred(df)

    def test_nan_value_rejected(self):
        df = _good_df()
        df.loc[1, "value"] = float("nan")
        with pytest.raises((SchemaError, Exception)):
            validate_fred(df)

    def test_source_missing_fred_prefix_rejected(self):
        """source 必須以 'FRED:' 開頭(SSOT provenance v19.82 慣例)。"""
        df = _good_df()
        df["source"] = "Yahoo:VIX"  # 錯誤 provenance
        with pytest.raises((SchemaError, Exception)) as exc:
            validate_fred(df)
        assert "FRED" in str(exc.value) or "source" in str(exc.value)

    def test_fetched_at_not_iso_rejected(self):
        df = _good_df()
        df["fetched_at"] = "2026/06/26 12:00"  # 非 ISO
        with pytest.raises((SchemaError, Exception)) as exc:
            validate_fred(df)
        assert "fetched_at" in str(exc.value) or "ISO" in str(exc.value).upper()


class TestFetchFredIntegration:
    """real fetch_fred mock smoke — schema hooked into output path。"""

    def test_fetch_fred_validates_on_output(self, monkeypatch):
        """fetch_fred 內部 validate_fred 呼叫 — mock requests 模擬完整 happy path
        確認 schema 通過 + 不 raise(無 network)。"""
        # mock proxy fetch_url to return合法 FRED-like JSON
        import json

        class _MockResp:
            def __init__(self, payload):
                self._payload = payload
            def json(self):
                return self._payload
            @property
            def status_code(self):
                return 200

        _mock_payload = {
            "observations": [
                {"date": "2026-01-01", "value": "1.5",
                 "realtime_start": "2026-01-15"},
                {"date": "2026-02-01", "value": "1.6",
                 "realtime_start": "2026-02-15"},
                {"date": "2026-03-01", "value": "1.7",
                 "realtime_start": "2026-03-15"},
            ]
        }
        from repositories import macro_repository as mr
        monkeypatch.setattr("repositories.macro.fred.fetch_url",
                            lambda *a, **kw: _MockResp(_mock_payload))
        # fetch_fred 走完整 path → out 含 source / fetched_at,validate_fred 應 pass
        df = mr.fetch_fred("CPILFESL", "x" * 32, n=3)
        # 若 schema 違反 fetch_fred 會 raise → 能跑到這代表通過
        assert not df.empty
        assert "source" in df.columns
        assert df["source"].iloc[0] == "FRED:CPILFESL"
        assert "fetched_at" in df.columns

    def test_fetch_fred_integer_only_series_dtype(self, monkeypatch):
        """v19.172 regression — FRED series 全為整數(PAYEMS / HSN1F 等)
        時,fetch_fred 必須強制轉 float64,否則 MacroFredSchema 拒。

        v19.171 之前:pd.to_numeric 對全整數 series 回 int64 → SchemaError
        v19.172 起:.astype("float64") 強制統一 dtype。
        """
        class _MockResp:
            def __init__(self, payload):
                self._payload = payload
            def json(self):
                return self._payload
            @property
            def status_code(self):
                return 200

        # payload 全為整數字串(模擬 PAYEMS / HSN1F / ICSA 等就業/住宅啟動數)
        _int_payload = {
            "observations": [
                {"date": "2026-01-01", "value": "300000",
                 "realtime_start": "2026-01-15"},
                {"date": "2026-02-01", "value": "305000",
                 "realtime_start": "2026-02-15"},
                {"date": "2026-03-01", "value": "310000",
                 "realtime_start": "2026-03-15"},
            ]
        }
        from repositories import macro_repository as mr
        monkeypatch.setattr("repositories.macro.fred.fetch_url",
                            lambda *a, **kw: _MockResp(_int_payload))
        df = mr.fetch_fred("PAYEMS", "x" * 32, n=3)
        # 核心斷言:整數 series 也要回 float64,否則上游 schema 炸
        assert not df.empty
        assert str(df["value"].dtype) == "float64", \
            f"v19.172 regression: 整數 series value 必為 float64,實際 = {df['value'].dtype}"
