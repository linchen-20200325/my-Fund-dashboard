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
- `YahooCloseSchema`:repositories.macro_repository.fetch_yf_close 出口 schema(Series)
- `validate_yf_close(s) -> s`:wrapper(同時驗 attrs.source / attrs.fetched_at)
- `FundNavSchema`:repositories.fund_repository.fetch_nav 等多 fetcher 共用 NAV 序列 schema
- `validate_fund_nav(s) -> s`:wrapper(NAV-specific:>0 / 多源 source prefix 允許清單)

Phase 規劃(SPEC §18.3):
- ✅ Phase A v19.155 — pilot:fetch_fred 1 個 fetcher
- ✅ Phase B v19.161 — 擴展 fetch_yf_close
- ✅ Phase B 後續 v19.162 — fetch_nav(本檔)
- Phase B 後續 — fetch_dividends
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


# ════════════════════════════════════════════════════════════════
# YahooCloseSchema — fetch_yf_close 出口契約(pd.Series)
# ════════════════════════════════════════════════════════════════
# 依據(repositories/macro_repository.py:392-429):
#   index = DatetimeIndex(monotonic_increasing,unique;dropna 確保無 NaT)
#   value = float64(close 價格 > 0;dropna 確保無 NaN)
#   attrs.source = "Yahoo:<ticker>"(F-PROV-1 v19.83 phase 2)
#   attrs.fetched_at = UTC ISO 字串(v19.83 phase 2)
#
# pandera SeriesSchema 支援 index + values 驗證;attrs 為 pandas-level
# 額外 metadata,須在 wrapper 手動驗證(SeriesSchema 不涵蓋)。

YahooCloseSchema = pa.SeriesSchema(
    "float64",
    nullable=False,
    checks=[
        pa.Check(lambda s: s.notna().all(), error="value 不可有 NaN(fetch_yf_close 已 dropna)"),
        pa.Check(lambda s: (s > 0).all(), error="close 價格必為 > 0"),
    ],
    index=pa.Index(
        "datetime64[ns]",
        checks=[
            pa.Check(lambda s: s.is_monotonic_increasing, error="index 必須單調遞增(asc)"),
            pa.Check(lambda s: s.is_unique, error="index 不可重複"),
        ],
    ),
)


def validate_yf_close(s: Any) -> Any:
    """fetch_yf_close 出口 schema validation wrapper。

    驗 3 件事:
    1. Series values:float64, > 0, no NaN
    2. Series index:datetime64[ns], monotonic, unique
    3. Series attrs:`source` 存在且以 'Yahoo:' 開頭;`fetched_at` 存在且為 ISO 字串

    對空 Series(fetch 失敗時)直接 pass — caller 已知 fallback。

    Returns
    -------
    驗證通過的 Series(不複製)。

    Raises
    ------
    pandera.errors.SchemaError:values / index 契約違反。
    ValueError:attrs.source / attrs.fetched_at 契約違反(F-PROV-1)。
    """
    if s is None or len(s) == 0:
        return s
    # 1+2. pandera 驗 values + index
    YahooCloseSchema.validate(s, lazy=False)
    # 3. provenance(attrs)— pandera SeriesSchema 不涵蓋,手動驗
    src = s.attrs.get("source", "")
    if not src.startswith("Yahoo:"):
        raise ValueError(
            f"validate_yf_close: attrs.source 必須以 'Yahoo:' 開頭(F-PROV-1),"
            f"實際 = {src!r}"
        )
    fetched_at = s.attrs.get("fetched_at", "")
    if "T" not in fetched_at:
        raise ValueError(
            f"validate_yf_close: attrs.fetched_at 必須是 ISO 8601 字串(含 'T' 分隔符),"
            f"實際 = {fetched_at!r}"
        )
    return s


# ════════════════════════════════════════════════════════════════
# FundNavSchema — fetch_nav 及相關 fund NAV fetcher 共用契約(pd.Series)
# ════════════════════════════════════════════════════════════════
# 依據(repositories/fund_repository.py:3578-3616 + 多 NAV fetcher):
#   index = DatetimeIndex(monotonic_increasing,unique;週末/假日缺值為正常,
#                          不可 ffill 偽造每日值 — CLAUDE.md §1 Fail Loud)
#   value = float64(NAV > 0;停售/清算時應為 NaN,但生產線索 dropna 已過濾)
#   attrs.source = "<Provider>:<host_or_endpoint>:..." — Fund 端多源 prefix:
#       MoneyDJ / FundClear / TDCC / Cnyes / Morningstar / AllianzGI /
#       JPMorgan / Franklin / FundRich / SITCA / InsuranceSubdomain /
#       BankPlatform / GitHubActions / Yahoo(yf_close 共用)等
#   attrs.fetched_at = UTC ISO 字串
#
# vs YahooCloseSchema:NAV 比股價更可能單點極低(基金清算),但生產
# fetcher 已 dropna,我們嚴守 >0 契約。多源 prefix 用允許清單明列,違
# 反 = 違反 §2.1 SSOT(可能 source 寫死成「unknown」之類的腦補字串)。

# Fund NAV 多源 source prefix 允許清單(對應 §2.1 5-Tier 提到的 fetcher)
_FUND_NAV_SOURCE_PREFIXES = (
    "MoneyDJ:",
    "FundClear:",
    "TDCC:",
    "Cnyes:",
    "Morningstar:",
    "AllianzGI:",
    "JPMorgan:",
    "Franklin:",
    "FundRich:",
    "SITCA:",
    "InsuranceSubdomain:",
    "BankPlatform:",
    "GitHubActions:",
    "Yahoo:",  # fetch_nav 部分路徑可能透過 yfinance 走
)

FundNavSchema = pa.SeriesSchema(
    "float64",
    nullable=False,
    checks=[
        pa.Check(lambda s: s.notna().all(), error="NAV 不可有 NaN(fetcher 已 dropna)"),
        pa.Check(lambda s: (s > 0).all(), error="NAV 必為 > 0(停售/清算應為 NaN 而非 0)"),
    ],
    index=pa.Index(
        "datetime64[ns]",
        checks=[
            pa.Check(lambda s: s.is_monotonic_increasing, error="index 必須單調遞增(asc)"),
            pa.Check(lambda s: s.is_unique, error="index 不可重複"),
        ],
    ),
)


def validate_fund_nav(s: Any) -> Any:
    """fetch_nav(+ 其他 fund NAV fetcher)出口 schema validation wrapper。

    驗 3 件事:
    1. Series values:float64, > 0, no NaN(NAV 鐵則)
    2. Series index:datetime64[ns], monotonic, unique
    3. Series attrs:`source` 須以 _FUND_NAV_SOURCE_PREFIXES 之一開頭;
                    `fetched_at` 為 ISO 字串(含 'T')

    對空 Series(fetch 失敗時)直接 pass — caller 已知 fallback chain。

    Returns
    -------
    驗證通過的 Series(不複製)。

    Raises
    ------
    pandera.errors.SchemaError:values / index 契約違反。
    ValueError:attrs.source / attrs.fetched_at 契約違反(F-PROV-1)。
    """
    if s is None or len(s) == 0:
        return s
    # 1+2. pandera 驗 values + index
    FundNavSchema.validate(s, lazy=False)
    # 3. provenance(attrs)— SeriesSchema 不涵蓋,手動驗
    src = s.attrs.get("source", "")
    if not any(src.startswith(p) for p in _FUND_NAV_SOURCE_PREFIXES):
        raise ValueError(
            f"validate_fund_nav: attrs.source 必須以以下 prefix 之一開頭"
            f"(F-PROV-1 §2.1 SSOT 多源命名約定):{_FUND_NAV_SOURCE_PREFIXES}。"
            f"實際 = {src!r}"
        )
    fetched_at = s.attrs.get("fetched_at", "")
    if "T" not in fetched_at:
        raise ValueError(
            f"validate_fund_nav: attrs.fetched_at 必須是 ISO 8601 字串(含 'T' 分隔符),"
            f"實際 = {fetched_at!r}"
        )
    return s
