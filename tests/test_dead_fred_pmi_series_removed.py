"""死掉的 FRED PMI series（NAPM / ISPMANPMI）不得再被查詢 —— fail-closed 守衛。

背景（三處 repo 內第一手證據，非轉述）
------------------------------------
1. `repositories/macro/alternate.py` 檔頭橫幅：兩條 series 自 2016-08 ISM 收回
   授權後停更；
2. `services/macro/us_indicators.py` v19.404 稽核註：兩條都「停更/下架」；
3. `scripts/update_macro_history.py`：明文「PMI 暫不抓——FRED NAPM 2016 停更」，
   其 `FRED_SERIES_IDS` 常數確實不含這兩條。

客戶 2026-09-01 指令：「已廢棄的資料源一律從資料庫與取數邏輯中徹底拔除，
**不得留存或發起查詢**」。

拔除前的實況是「**先發請求、拿回資料才依 max_age_days 丟棄**」——
請求已經送出去了，命中率恆為 0。本檔守的就是「請求不再送出」這件事。

為什麼是 fail-closed（而不是形態偵測）
-------------------------------------
本檔**不**用「原始碼裡有沒有 'NAPM' 這個字」來判斷 —— 那種寫法改個別名、
改個字串拼接就能繞過。本檔改為**攔截 `fetch_fred` 的實際呼叫參數**：
只要 production 路徑對這兩個 series_id 發出任何一次請求，測試就轉紅。
突變驗證：把 `alternate.py` 的方案 1+2 或 `us_indicators.py` 的預熱清單 /
series 補救任一段加回去，本檔即紅燈。
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd
import pytest

# 兩條已廢棄 series 的**字面值**（刻意不 import `shared.fred_series` 的常數：
# 若有人把常數值改掉，本檔仍要能抓到「真的打了 NAPM/ISPMANPMI」這件事）
_DEAD_SIDS = {"NAPM", "ISPMANPMI"}


def _live_monthly_df() -> pd.DataFrame:
    """一段**時效內**的月頻 series —— 讓時效檢查不成為擋下請求的原因。

    重點：若方案 1+2 還在，這份資料會讓它**命中並 return**，
    使 `_DEAD_SIDS` 一定被記錄到 → 測試紅。
    """
    end = pd.Timestamp(_dt.date.today()).normalize()
    idx = pd.date_range(end=end, periods=8, freq="ME")
    return pd.DataFrame({
        "date": idx,
        "value": [52.0, 51.5, 50.8, 49.7, 48.5, 51.1, 52.4, 53.3],
    })


class _FredSpy:
    """記錄每一次 `fetch_fred` 呼叫的 series_id。"""

    def __init__(self) -> None:
        self.series_ids: list[str] = []

    def __call__(self, series_id, api_key="", n=250, *args, **kwargs):
        self.series_ids.append(str(series_id))
        return _live_monthly_df()

    @property
    def dead_hits(self) -> list[str]:
        return [s for s in self.series_ids if s in _DEAD_SIDS]


class TestFetchIsmPmiIssuesNoDeadQuery:
    def test_no_request_for_dead_series(self, monkeypatch):
        """`fetch_ism_pmi` 全程不得對 NAPM / ISPMANPMI 發出任何請求。

        突變驗證：把 `alternate.py` 方案 1+2 加回去 → 本條紅。
        """
        from repositories.macro import alternate as alt

        spy = _FredSpy()
        monkeypatch.setattr(alt, "fetch_fred", spy)
        monkeypatch.setattr(alt, "fetch_url", lambda *a, **kw: None)

        alt.fetch_ism_pmi("dummy-key")

        assert spy.dead_hits == [], (
            f"fetch_ism_pmi 仍對已廢棄 series 發出請求：{spy.dead_hits}；"
            f"本次全部 fetch_fred 呼叫={spy.series_ids}"
        )

    def test_still_reaches_a_live_stage(self, monkeypatch):
        """降級鏈沒被拔斷：仍有存活的 FRED 段會被叫到（方案 6 Phil Fed）。

        這條與上一條配對 —— 防止「用『什麼都不查』來讓上一條變綠」。
        """
        from repositories.macro import alternate as alt
        from shared.fred_series import FRED_PHILLY_FED

        spy = _FredSpy()
        monkeypatch.setattr(alt, "fetch_fred", spy)
        monkeypatch.setattr(alt, "fetch_url", lambda *a, **kw: None)

        out = alt.fetch_ism_pmi("dummy-key")

        assert FRED_PHILLY_FED in spy.series_ids, (
            f"存活的 Phil Fed 段沒有被叫到，降級鏈可能被拔斷：{spy.series_ids}")
        assert out.get("value") is not None, "降級鏈應仍能產出 PMI 讀數"

    def test_fail_loud_when_every_stage_fails(self, monkeypatch):
        """五段全敗 → 誠實回 err token（value=None），不得填補假值（§1）。"""
        from repositories.macro import alternate as alt

        monkeypatch.setattr(alt, "fetch_fred", lambda *a, **kw: pd.DataFrame())
        monkeypatch.setattr(alt, "fetch_url", lambda *a, **kw: None)

        out = alt.fetch_ism_pmi("dummy-key")

        assert out.get("value") is None, "全敗時不得回退到任何猜測值"
        assert "_err_pmi" in out, "全敗時必須帶錯誤原因供 audit"
        assert out.get("source") == "ISM-PMI:all_5_stages_failed"


class TestFetchAllIndicatorsIssuesNoDeadQuery:
    def test_prewarm_and_series_paths_skip_dead_series(self, monkeypatch):
        """`fetch_all_indicators` 的**預熱清單**與 **PMI series 補救**都不得碰死 series。

        突變驗證：把 `(FRED_ISM_PMI, 144)` 加回預熱清單，或把
        `df_hist = _fred(FRED_ISM_PMI, ...)` 補救段加回去 → 本條紅。
        """
        import services.macro.us_indicators as us

        batched: list[str] = []
        singles = _FredSpy()

        def _spy_batch(pairs, api_key, max_workers=8, *a, **kw):
            batched.extend(str(sid) for sid, _n in pairs)
            return {}

        monkeypatch.setattr(us, "fetch_fred_batch", _spy_batch)
        monkeypatch.setattr(us, "_fred", singles)
        # PMI 主路徑：回一個**沒有 dates/values** 的命中 →
        # 若「series 補救」還在，它一定會被觸發（s is None）→ 打 ISPMANPMI → 紅。
        monkeypatch.setattr(us, "fetch_ism_pmi", lambda *a, **kw: {
            "value": 52.0, "date": "2026-08-01", "label": "stub",
            "source": "stub:pmi", "is_proxy": False, "series_id": "stub",
        })
        # 擋掉本檔不關心的對外行情往返（否則測試會真的去打 Yahoo）
        monkeypatch.setattr(us, "_yf_s", lambda *a, **kw: pd.Series(dtype=float))
        try:
            us.fetch_all_indicators("x" * 32)
        except Exception:
            # 本條只關心「有沒有對死 series 發問」，不關心整條聚合是否跑完；
            # 其餘指標的 stub 不完整導致的例外不影響下方斷言。
            pass

        dead_in_batch = [s for s in batched if s in _DEAD_SIDS]
        assert dead_in_batch == [], (
            f"fetch_fred_batch 預熱清單仍含已廢棄 series：{dead_in_batch}")
        assert singles.dead_hits == [], (
            f"fetch_all_indicators 仍對已廢棄 series 發出單次請求：{singles.dead_hits}")
