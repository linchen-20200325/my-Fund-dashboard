# -*- coding: utf-8 -*-
"""【FAKE】scenario 資料（80 第 9 節 scenario 清單）：用元件 view model 表達，全部為**虛構**。

- 來源一律標 `FAKE-…`、數值是明顯的示意值，不代表任何真實市場、基金或帳戶。
- 只用批 1 已有的元件 dataclass；頁級 view model 不在本批範圍。
- 十個情境名稱逐一對應 80 第 9 節清單；`SCENARIOS` 是 `名稱 → tuple[元件]`。
- 純函式、零副作用、決定性（不用亂數、不讀時鐘）。
"""
from __future__ import annotations

from typing import Dict, Tuple

from ui_v3.viewmodels import (
    ChartCard,
    ChartPoint,
    ChartSeries,
    FactMeta,
    MISSING_TEXT,
    MetricCard,
    MissingItem,
    StatusChip,
    ValueFacts,
)

FAKE_FIXTURE = True
FAKE_SOURCE = "FAKE-來源（示意，非真實資料）"
FAKE_AS_OF = "2000-01-03"


def _ok(value: float, unit: str = "pt") -> ValueFacts:
    return ValueFacts(value, FactMeta(status="ok", source=FAKE_SOURCE, as_of=FAKE_AS_OF, unit=unit))


def _missing(reason_code: str) -> ValueFacts:
    return ValueFacts(None, FactMeta(status="missing", reason_code=reason_code))


def _line(label: str, values: Tuple[object, ...], status: str = "ok") -> ChartSeries:
    points = tuple(ChartPoint(f"2000-01-{i + 3:02d}", v) for i, v in enumerate(values))
    meta = FactMeta(status=status, source=FAKE_SOURCE, as_of=points[-1].date if points else None,
                    reason_code=None if status == "ok" else "fake_series_issue")
    return ChartSeries(label, meta, points)


def build_scenarios() -> Dict[str, tuple]:
    long_name = "FAKE-" + "這是一檔名稱非常非常長的示意基金" * 6
    missing_series = ChartSeries("FAKE 缺值序列", FactMeta(status="missing", reason_code="fake_no_data"), ())
    gap_series = _line("FAKE 中間缺段（斷線不補）", (100.0, 101.0, None, None, 103.0))
    return {
        "missing": (MetricCard("FAKE 指標", _missing("fake_missing"), MISSING_TEXT),),
        "source_failure": (
            MetricCard("FAKE 指標", ValueFacts(None, FactMeta(status="failed", reason_code="fake_fetch_failed")),
                       MISSING_TEXT),
            StatusChip("failed", "fetch_failed"),
        ),
        "stale": (
            MetricCard(
                "FAKE 指標",
                ValueFacts(98.5, FactMeta(status="stale", source=FAKE_SOURCE, as_of="1999-12-01",
                                          freshness_state="stale")),
                "98.5",
            ),
            StatusChip("stale", "not_latest"),
        ),
        "long_text": (
            MetricCard(long_name, _ok(1.0), "1.0"),
            MissingItem(long_name, "fake_long_reason_" + "x" * 40),
        ),
        "no_holdings": (MissingItem("FAKE 持股", "fake_no_holdings"),),
        "multiple_holdings": tuple(MetricCard(f"FAKE 持股 {i}", _ok(10.0 * i), f"{10.0 * i:.1f}") for i in (1, 2, 3)),
        "isin_not_enabled": (MissingItem("FAKE ISIN 查詢", "fake_isin_not_enabled"),),
        "oauth_not_logged_in": (MissingItem("FAKE 帳號", "fake_auth_required"),),
        "sheet_not_selected": (MissingItem("FAKE Active Sheet", "fake_sheet_not_selected"),),
        "permission_insufficient": (MissingItem("FAKE 試算表權限", "fake_permission_denied"),),
        "chart_with_gap": (
            ChartCard("FAKE 圖卡", (gap_series, missing_series), (StatusChip("neutral", "fake_chip"),)),
        ),
    }


SCENARIOS: Dict[str, tuple] = build_scenarios()

# 80 第 9 節 scenario 清單（逐項）；`chart_with_gap` 是額外的圖卡斷線情境。
REQUIRED_SCENARIO_NAMES = (
    "missing", "source_failure", "stale", "long_text", "no_holdings", "multiple_holdings",
    "isin_not_enabled", "oauth_not_logged_in", "sheet_not_selected", "permission_insufficient",
)
