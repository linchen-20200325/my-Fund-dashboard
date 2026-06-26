"""shared/schemas.py — Pandera 資料 schema SSOT(v19.155 Phase A pilot)

CLAUDE.md §3.1 / SPEC §18 — DataFrame 邊界契約集中宣告。

設計
----
- L0 / 純常數,零 I/O
- 各 fetcher 出口 / service 入口呼叫 `Schema.validate(df)` 強制契約
- schema 改動 = 本檔唯一 commit point;**禁止** caller 端重新宣告
- pandera 不在環境時(極罕見:requirements.txt 已 pin >=0.20),caller 應降級
  為 best-effort try/except,不阻斷流程(§1 Fail Loud 對齊:契約違反 raise,
  但 schema 模組本身不可用視為環境問題)

對外 API
========
- `MacroFredSchema`:repositories.macro_repository.fetch_fred 出口 schema
- `validate_fred(df) -> df`:wrapper(避免每個 caller import pandera 細節)

Phase 規劃(SPEC §18.3):
- Phase A(本檔)— pilot:fetch_fred 1 個 fetcher
- Phase B — 擴展 fetch_yf_close / fetch_fund_nav_series / fetch_dividends
- Phase C — service 入口(compute_1y_total_return_mk_simple / calc_metrics)
- Phase D — 全面 + CI gate
"""
from __future__ import annotations

from typing import Any

import pandera.pandas as pa


# ════════════════════════════════════════════════════════════════
# MacroFredSchema — fetch_fred 出口契約
# ════════════════════════════════════════════════════════════════
# 依據(SPEC §3.1 + repositories/macro_repository.py:280-302 實際輸出):
#   date          datetime64[ns]  ascending 排序,unique;to_datetime 強制
#   value         float64         dropna 後保證無 NaN;> 0 不強制(macro 可負,e.g. yield spread)
#   source        str             v19.82 起必含,格式 "FRED:<series_id>"
#   fetched_at    str             ISO 8601 UTC 字串
#   realtime_start datetime64[ns] 可 NaT(FRED 部分 series 缺欄)
#
# 容差(SPEC §18.2 過度設計反例):
# - strict=False — 允許 unknown 額外欄位(FRED 原始 obs 帶 realtime_end 等不檢)
# - coerce=False — 不強制型別轉換(fetch_fred 內部已 pd.to_datetime / to_numeric,
#                   此處 schema 只做 final assert,違反 = 上游 bug)

MacroFredSchema = pa.DataFrameSchema(
    {
        "date": pa.Column(
            "datetime64[ns]",
            nullable=False,
            checks=[
                pa.Check(
                    lambda s: s.is_monotonic_increasing,
                    error="date 必須單調遞增(asc)",
                ),
                pa.Check(
                    lambda s: s.is_unique,
                    error="date 不可重複",
                ),
            ],
        ),
        "value": pa.Column(
            "float64",
            nullable=False,
            checks=[
                pa.Check(lambda s: s.notna().all(), error="value 不可有 NaN(fetch_fred 已 dropna)"),
            ],
        ),
        "source": pa.Column(
            str,
            nullable=False,
            checks=[
                pa.Check(
                    lambda s: s.str.startswith("FRED:").all(),
                    error="source 必須以 'FRED:' 開頭(SSOT provenance 慣例 v19.82)",
                ),
            ],
        ),
        "fetched_at": pa.Column(
            str,
            nullable=False,
            checks=[
                pa.Check(
                    lambda s: s.str.contains("T", regex=False).all(),
                    error="fetched_at 必須是 ISO 8601 字串(含 'T' 分隔符)",
                ),
            ],
        ),
        "realtime_start": pa.Column(
            "datetime64[ns]",
            nullable=True,  # FRED 部分 series 缺欄,允許 NaT
        ),
    },
    strict=False,   # 允許 FRED 原始額外欄位(realtime_end 等)
    coerce=False,   # fetch_fred 已內部轉型,此處只 assert
)


def validate_fred(df: Any) -> Any:
    """fetch_fred 出口 schema validation wrapper。

    對空 DataFrame(fetch 失敗時)直接 pass — §1 Fail Loud:caller 已知是
    fail token,schema 不重複擋。

    Returns
    -------
    驗證通過的 DataFrame(schema lazy 模式可能 augment,但本檔 strict=False)。

    Raises
    ------
    pandera.errors.SchemaError:契約違反(date 重複 / value NaN / source 缺前綴等)。
    """
    if df is None or len(df) == 0:
        return df
    return MacroFredSchema.validate(df, lazy=False)
