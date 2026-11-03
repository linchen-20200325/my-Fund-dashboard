# -*- coding: utf-8 -*-
"""🌍 比較圖：`NormalizedComparison`（L2）→ `ChartCard`＋`NormalizationDisclosure`（BL-0536-H3）。

純函式：無 Streamlit、無 I/O、不取數、不計算領域值；只把 L2 結果原樣搬進 view model。
放在 adapters 是因為 view model 不得 import services（`tests/ui_v3/ui_v3_guard_lib.py` 分層規則；adapters 可 import
`services.v2_domain`，守衛不需擴充）。

規則（`docs/v2/81` 第 3.1、4、4.1、9.1 節；`DEC-2026-11-03-01` Q2-a／b／c A；`DEC-2026-11-03-04`）：
1. 每條輸入序列一條 `ChartSeries`，依 L2 順序；有線的帶歸一化點（None 缺口照留、斷線不補），沒線的不帶任何數值點。
2. `ChartSeries.meta.as_of`＝該序列自己的 `last_obs_date`（圖下資料日一行；Q2-b A），沒畫線但有資料的也照實帶；
   `freshness_state` 恆為 `undetermined`（門檻未裁示，H2 `FRESHNESS_THRESHOLD_PENDING` 的 view model 詞彙）。
3. 沒線的序列 → `disclosure.series_issues`（序列鍵＋原因代碼，L2 狀態原樣）；完全沒有資料的（`missing`／取數失敗）另放
   `MissingItem` 進 `detail`（呈現恆為 `◇ 資料未備`，原因代碼區分）。
4. 取數失敗與缺資料分開（H2 稽核後 adapter 要求 (3)；81 第 4.1 節 S6）：呼叫端以 `failed_keys` 指明哪幾條是取數失敗，
   那幾條 `status == "failed"`、原因 `fetch_failed`；`failed_keys` 只能指向 L2 判為 `missing` 的序列，否則大聲失敗。
5. 有資料但不畫的（`insufficient`／`withheld`／`no_common_base`／`too_few_common_days`／`too_few_points`）→
   `status == "undetermined"`＋原因代碼（81 第 4.1 節 S7「無法判定」；不是缺資料，不放 `MissingItem`）。
6. 揭露：`mode`／`status`／`base_date`／`base_value`／`window_start`／`fallback_reason` 原樣取自 L2；
   `frequency == "daily"`（L2 輸入定義為日頻收盤）、`gap_policy == "no_fill"`（L2 不補值）。
7. 畫面字樣不在本層：`title`、各序列 `labels`、`sources` 由呼叫端提供（81：標題與揭露字樣 PENDING）；本層只產生代碼。
8. 不另畫 100 基準線、不加 chip（基準 chip 的字樣與日期承載方式屬 rendering 批，81 G4）。

⚠️ 沿用限制：L2 若出現 inf（基準原值極小等病態量級，見 BACKLOG BL-0536-H2 低優先登記），`ChartPoint` 會拒收而大聲失敗；
收盤值先轉 `float` 的要求屬呼叫 `normalize_pair` 的取數 adapter（rendering 批），本函式不接觸原始收盤。
"""
from __future__ import annotations

from services.v2_domain.normalization import SERIES_MISSING, STATUS_OK, NormalizedComparison
from ui_v3.viewmodels.chart_disclosure import (
    FREQUENCY_DAILY,
    GAP_POLICY_NO_FILL,
    NormalizationDisclosure,
    SeriesIssue,
)
from ui_v3.viewmodels.common import (
    FRESH_UNDETERMINED,
    STATUS_FAILED,
    STATUS_MISSING,
    STATUS_OK as VM_STATUS_OK,
    STATUS_UNDETERMINED,
    FactMeta,
)
from ui_v3.viewmodels.components import ChartCard, ChartPoint, ChartSeries, MissingItem

__all__ = ("REASON_FETCH_FAILED", "build_comparison_card")

# 取數失敗的原因代碼（＝ `shared/ui_semantics/rules.py` 的 `fetch_failed` 鍵；adapters 不得 import shared，故另存，測試鎖）。
REASON_FETCH_FAILED = "fetch_failed"


def _series(result, label, source, failed):
    if result.status == STATUS_OK:
        meta = FactMeta(status=VM_STATUS_OK, source=source, as_of=result.last_obs_date,
                        freshness_state=FRESH_UNDETERMINED)
        return ChartSeries(label, meta, tuple(ChartPoint(p.obs_date, p.value) for p in result.points)), None
    if failed:
        reason, status = REASON_FETCH_FAILED, STATUS_FAILED
    elif result.status == SERIES_MISSING:
        reason, status = SERIES_MISSING, STATUS_MISSING
    else:
        reason, status = result.status, STATUS_UNDETERMINED
    as_of = result.last_obs_date
    meta = FactMeta(status=status, source=source if as_of is not None else None, as_of=as_of,
                    freshness_state=FRESH_UNDETERMINED, reason_code=reason)
    return ChartSeries(label, meta, ()), SeriesIssue(result.key, reason)


def build_comparison_card(comparison: NormalizedComparison, *, title: str, labels, sources,
                          failed_keys=frozenset()) -> ChartCard:
    """把一個 `NormalizedComparison` 轉成歸一化 `ChartCard`（規則見模組 docstring 第 1～8 點）。

    - `labels`／`sources`：序列鍵 → 畫面名稱／來源標示（呼叫端提供；每個序列鍵都要有，否則 `KeyError`）。
    - `failed_keys`：取數失敗的序列鍵（必須是 L2 判為 `missing` 的序列，否則 `ValueError`）。
    """
    if not isinstance(comparison, NormalizedComparison):
        raise TypeError("comparison must be a NormalizedComparison")
    failed = frozenset(failed_keys)
    by_key = {r.key: r for r in comparison.series}
    unknown = failed - set(by_key)
    if unknown:
        raise ValueError(f"failed_keys not in comparison: {sorted(unknown)}")
    for key in failed:
        if by_key[key].status != SERIES_MISSING:
            raise ValueError(f"failed key {key!r} has status {by_key[key].status!r}; only missing series can be failed")

    series, issues, detail = [], [], []
    for result in comparison.series:
        chart_series, issue = _series(result, labels[result.key], sources[result.key], result.key in failed)
        series.append(chart_series)
        if issue is not None:
            issues.append(issue)
            if chart_series.meta.is_missing:
                detail.append(MissingItem(labels[result.key], issue.reason_code))

    disclosure = NormalizationDisclosure(
        mode=comparison.mode,
        status=comparison.status,
        base_date=comparison.base_date,
        window_start=comparison.window_start,
        base_value=comparison.base_value,
        frequency=FREQUENCY_DAILY,
        gap_policy=GAP_POLICY_NO_FILL,
        series_issues=tuple(issues),
        fallback_reason=comparison.fallback_reason,
    )
    return ChartCard(title, tuple(series), period=comparison.period, detail=tuple(detail),
                     normalized=True, disclosure=disclosure)
