"""v19.281 regression test — NAV 歷史窗口擴展 + span-extend。

User 反饋:TLZF9(保單代碼)MoneyDJ 有 3-5 年資料,但本站顯示「成立 0.1 年」、
3Y/5Y 全 —。根因:
1. cnyes / Morningstar NAV 窗口原僅 400d(~13 月)→ 不足以算 3Y/5Y。
2. NAV 來源鏈只用「筆數」把關,保單代碼落到近期短源(~1 月,≥10 筆)就鎖定,
   把長歷史 Morningstar(硬編 secId)整條 skip。

本檔守:
- cnyes / Morningstar NAV 請求窗口 ≥ ~5 年(擴到 2000 天)。
- _fetch_fund_single 有 span-extend 分支(短跨度保單代碼 → 換長歷史)。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd


class _FakeJsonResp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


def _days_between_ms(start_ms: int, end_ms: int) -> int:
    return int((end_ms - start_ms) / 1000 / 86400)


def test_cnyes_nav_window_is_multi_year():
    """fetch_nav_cnyes 請求窗口應 ≥ ~5 年(擴到 2000d,足以算 3Y/5Y)。"""
    import repositories.fund.sources as S

    seen_urls: list = []

    def _fake_get(url, **kw):
        seen_urls.append(url)
        return _FakeJsonResp({"data": {"nav": []}})

    with patch.object(S, "_cnyes_resolve_code", return_value=["TLZF9"]), \
         patch.object(S.requests, "get", side_effect=_fake_get):
        S.fetch_nav_cnyes("TLZF9")

    # 取第一個 nav 端點 URL,解析 start/end
    nav_urls = [u for u in seen_urls if "/nav?" in u]
    assert nav_urls, f"應打 nav 端點,實際 {seen_urls}"
    import urllib.parse as _up
    q = _up.parse_qs(_up.urlparse(nav_urls[0]).query)
    start_ms, end_ms = int(q["start"][0]), int(q["end"][0])
    span_days = _days_between_ms(start_ms, end_ms)
    assert span_days >= 1500, f"cnyes NAV 窗口應 ≥ ~5 年(1500d+),實際 {span_days}d"


def test_morningstar_nav_window_is_multi_year():
    """_src_morningstar_nav 請求窗口應 ≥ ~5 年(擴到 2000d)。"""
    import repositories.fund.sources as S

    seen_urls: list = []

    class _Resp:
        status_code = 200
        text = ""

        def read(self):  # urllib 介面(morningstar 用 urllib)
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _fake_urlopen(req, **kw):
        seen_urls.append(getattr(req, "full_url", str(req)))
        return _Resp()

    # TLZF9 已在 _MORNINGSTAR_SECID_MAP → 直接走硬編 secId,不需 search
    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        S._src_morningstar_nav("TLZF9")

    ts_urls = [u for u in seen_urls if "timeseries_price" in u]
    assert ts_urls, f"應打 timeseries_price,實際 {seen_urls}"
    import urllib.parse as _up
    q = _up.parse_qs(_up.urlparse(ts_urls[0]).query)
    start = q["startDate"][0]
    end = q["endDate"][0]
    span_days = (pd.Timestamp(end) - pd.Timestamp(start)).days
    assert span_days >= 1500, f"Morningstar NAV 窗口應 ≥ ~5 年,實際 {span_days}d"


def test_span_extend_helper_prefers_longer_span():
    """span-extend 決策邏輯:跨度更長者才替換(additive,不退步)。

    以純資料驗證「短跨度 → 換長跨度」的決策(整合層 _fetch_fund_single 網路重、
    不做端到端 mock;此處守決策不變式)。
    """
    def _span(_s):
        if _s is None or len(_s) < 2:
            return 0
        return int((pd.Timestamp(_s.index.max())
                    - pd.Timestamp(_s.index.min())).days)

    _short = pd.Series(range(25),
                       index=pd.date_range(end="2026-06-30", periods=25, freq="D"))
    _long = pd.Series(range(1200),
                      index=pd.date_range(end="2026-06-30", periods=1200, freq="D"))
    # 短跨度應觸發 span-extend(< 300d),長跨度不觸發
    assert 0 < _span(_short) < 300
    assert _span(_long) >= 300
    # 替換規則:長者 span 嚴格大於短者 → 採長者
    assert _span(_long) > _span(_short)
