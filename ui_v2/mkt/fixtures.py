# -*- coding: utf-8 -*-
"""假資料（示意值）。純 dict/list，無 pandas、無網路、無舊 repo import。

每一列的欄位逐字照 `44` 第四節 `market_indicator` 那張表的八欄：
indicator_key／obs_date／release_date／value_num／value_unit／source_tier／
is_revised／fetched_at。

⚠️ 本檔的每一個數字都是**示意值**，不是任何真實觀測。
客戶裁示本輪用假資料；本樹不接任何真實資料源。
"""

from __future__ import annotations

# 三張核心卡在 `44` 各自「來源」欄裡點名的六個鍵。
SIX_KEYS = (
    "coincident_index",
    "credit_spread_pct",
    "fx_twd_per_usd",
    "leading_index",
    "policy_rate_pct",
    "vol_index",
)

# 第七個鍵：只進 MKT-6／MKT-7／MKT-5 的清單，三張核心卡不讀它。
# 放它進來是為了讓 MKT-5 的「勾選上限 6」這條規則有東西可以撞。
EXTRA_KEY = "term_spread_pct"


def observation(
    indicator_key: str,
    *,
    value_num: float = 0.0,
    value_unit: str = "index",
    obs_date: str = "2026-09-18",
    release_date: str | None = None,
    source_tier: str = "T1",
    is_revised: bool = False,
    fetched_at: str | None = None,
) -> dict:
    """造一列 market_indicator。八欄皆非空（照表宣告的可空＝否）。"""
    if release_date is None:
        release_date = obs_date
    if fetched_at is None:
        fetched_at = obs_date + "T01:00:00Z"
    return {
        "indicator_key": indicator_key,
        "obs_date": obs_date,
        "release_date": release_date,
        "value_num": value_num,
        "value_unit": value_unit,
        "source_tier": source_tier,
        "is_revised": is_revised,
        "fetched_at": fetched_at,
    }


def _daily_dates() -> list[str]:
    return [f"2026-09-{day:02d}" for day in range(14, 22)]


def _monthly() -> list[str]:
    return [f"2026-{month:02d}-01" for month in range(3, 10)]


def _plus_days(date_text: str, days: int) -> str:
    from datetime import date, timedelta

    return (date.fromisoformat(date_text) + timedelta(days=days)).isoformat()


def _base_rows(sign: int = 1) -> list[dict]:
    rows: list[dict] = []

    for index, obs in enumerate(_daily_dates()):
        rows.append(
            observation(
                "vol_index",
                value_num=sign * (16.0 + index * 0.4),
                value_unit="index",
                obs_date=obs,
                release_date=_plus_days(obs, 1),
                source_tier="T2",
                fetched_at=_plus_days(obs, 3) + "T02:00:00Z",
            )
        )
        rows.append(
            observation(
                "credit_spread_pct",
                value_num=sign * (3.10 + index * 0.05),
                value_unit="pp",
                obs_date=obs,
                release_date=_plus_days(obs, 1),
                source_tier="T1",
                fetched_at=_plus_days(obs, 3) + "T02:00:00Z",
            )
        )
        rows.append(
            observation(
                "fx_twd_per_usd",
                value_num=sign * (31.200 + index * 0.015),
                value_unit="新臺幣／美元",
                obs_date=obs,
                release_date=_plus_days(obs, 1),
                source_tier="T1",
                fetched_at=_plus_days(obs, 1) + "T08:00:00Z",
            )
        )

    for index, obs in enumerate(_monthly()):
        rows.append(
            observation(
                "leading_index",
                value_num=sign * (99.0 + index * 0.6),
                value_unit="index",
                obs_date=obs,
                release_date=_plus_days(obs, 5),
                source_tier="T1",
                fetched_at=_plus_days(obs, 6) + "T01:00:00Z",
            )
        )
        rows.append(
            observation(
                "coincident_index",
                value_num=sign * (101.0 + index * 0.4),
                value_unit="index",
                obs_date=obs,
                release_date=_plus_days(obs, 5),
                source_tier="T1",
                fetched_at=_plus_days(obs, 6) + "T01:00:00Z",
            )
        )

    rows.append(
        observation(
            "policy_rate_pct",
            value_num=sign * 1.875,
            value_unit="%",
            obs_date="2026-09-18",
            release_date="2026-09-18",
            source_tier="T1",
            fetched_at="2026-09-21T01:00:00Z",
        )
    )
    rows.append(
        observation(
            EXTRA_KEY,
            value_num=sign * 0.42,
            value_unit="pp",
            obs_date="2026-09-18",
            release_date="2026-09-19",
            source_tier="T2",
            fetched_at="2026-09-21T01:00:00Z",
        )
    )
    return rows


def _dataset(rows: list[dict], errors: dict | None = None) -> dict:
    return {"rows": rows, "errors": dict(errors or {})}


def _drop(rows: list[dict], keys) -> list[dict]:
    keys = set(keys)
    return [row for row in rows if row["indicator_key"] not in keys]


# ───────────────────────── 情境 ─────────────────────────


def dataset_all_ok(sign: int = 1) -> dict:
    """全齊（47 狀態 1）。sign=-1 用來驗「主值正負號相反時顏色相同」。"""
    return _dataset(_base_rows(sign))


def dataset_mkt1_one_key_missing() -> dict:
    """MKT-1 一鍵缺：該數位置 `⬜ 資料未備`，另一數照畫，標題掛「部分缺」徽章。"""
    return _dataset(_drop(_base_rows(), ["credit_spread_pct"]))


def dataset_mkt1_both_keys_missing() -> dict:
    return _dataset(_drop(_base_rows(), ["vol_index", "credit_spread_pct"]))


def dataset_mkt1_fetch_failed() -> dict:
    """MKT-1 取數失敗（47 狀態 4）。刻意讓 MKT-2 同時缺來源，
    好驗「紅蓋過黃」不是因為畫面上只剩一種狀態。"""
    rows = _drop(_base_rows(), ["leading_index", "coincident_index"])
    return _dataset(
        rows,
        errors={
            "vol_index": (
                "HTTPSConnectionPool(host='example.invalid', port=443): "
                "Max retries exceeded"
            )
        },
    )


def dataset_mkt2_both_keys_missing() -> dict:
    """47 狀態 2：以 MKT-2 兩鍵皆缺為例。"""
    return _dataset(_drop(_base_rows(), ["leading_index", "coincident_index"]))


def dataset_mkt2_only_five_rows() -> dict:
    """任一鍵不足 6 筆 → 副標 `⬜ 不適用：可用筆數不足 6`，主值照出。"""
    rows = []
    seen = 0
    for row in _base_rows():
        if row["indicator_key"] == "leading_index":
            seen += 1
            if seen > 5:
                continue
        rows.append(row)
    return _dataset(rows)


def dataset_mkt2_one_row_after_baseline() -> dict:
    """一筆的公布日晚於比較基準日 → 該筆不進入計算，副標加一行寫被排除的筆數。

    基準日取 2026-06-30：下面刻意把兩條序列的公布日全部壓在 6 月之前，
    再各補一筆 7 月公布的。
    """
    rows = _drop(_base_rows(), ["leading_index", "coincident_index"])
    for index, month in enumerate(range(1, 7)):
        obs = f"2026-{month:02d}-01"
        for key, base in (("leading_index", 99.0), ("coincident_index", 101.0)):
            rows.append(
                observation(
                    key,
                    value_num=base + index * 0.5,
                    value_unit="index",
                    obs_date=obs,
                    release_date=_plus_days(obs, 5),
                    fetched_at=_plus_days(obs, 6) + "T01:00:00Z",
                )
            )
    for key, base in (("leading_index", 103.0), ("coincident_index", 104.0)):
        rows.append(
            observation(
                key,
                value_num=base,
                value_unit="index",
                obs_date="2026-07-01",
                release_date="2026-07-15",
                fetched_at="2026-07-16T01:00:00Z",
            )
        )
    return _dataset(rows)


def dataset_mkt2_diverging() -> dict:
    """兩條線反向 → 副標「兩者分歧」。"""
    rows = _drop(_base_rows(), ["coincident_index"])
    for index, obs in enumerate(_monthly()):
        rows.append(
            observation(
                "coincident_index",
                value_num=104.0 - index * 0.4,
                value_unit="index",
                obs_date=obs,
                release_date=_plus_days(obs, 5),
                fetched_at=_plus_days(obs, 6) + "T01:00:00Z",
            )
        )
    return _dataset(rows)


def dataset_mkt3_unit_mismatch() -> dict:
    """47 狀態 3：來源給的單位與本卡宣告的不同 → `⬜ 不適用：單位不符`，
    副標寫出來源給的單位字面值。"""
    rows = []
    for row in _base_rows():
        if row["indicator_key"] == "fx_twd_per_usd":
            row = dict(row, value_unit="TWD")
        rows.append(row)
    return _dataset(rows)


def dataset_all_empty() -> dict:
    """47 狀態 6：全空（首次開啟）。一列也沒有。"""
    return _dataset([])


def dataset_revised_row() -> dict:
    """同一 obs_date 被修正 → 各成一列，修正不覆蓋原列，修正那一列掛「修正過」徽章。"""
    rows = _base_rows()
    rows.append(
        observation(
            "policy_rate_pct",
            value_num=1.900,
            value_unit="%",
            obs_date="2026-09-18",
            release_date="2026-09-20",
            is_revised=True,
            fetched_at="2026-09-21T01:00:00Z",
        )
    )
    return _dataset(rows)


def dataset_unknown_unit_literal() -> dict:
    """本表未列舉的單位字面值 → 照印，不做任何換算。"""
    rows = []
    for row in _base_rows():
        if row["indicator_key"] == EXTRA_KEY:
            row = dict(row, value_unit="basis_point")
        rows.append(row)
    return _dataset(rows)


def dataset_fetched_before_obs() -> dict:
    """取得時間早於觀測日 → 延遲欄 `⬜ 不適用：取得時間早於觀測日`，不是負數。"""
    rows = []
    for row in _base_rows():
        if row["indicator_key"] == "policy_rate_pct":
            row = dict(row, fetched_at="2026-09-17T01:00:00Z")
        rows.append(row)
    return _dataset(rows)


def all_datasets() -> dict:
    """全部情境。紅線字表掃描與徽章掃描一律跑過每一個。"""
    return {
        "all_ok": dataset_all_ok(),
        "all_ok_negative": dataset_all_ok(sign=-1),
        "mkt1_one_key_missing": dataset_mkt1_one_key_missing(),
        "mkt1_both_keys_missing": dataset_mkt1_both_keys_missing(),
        "mkt1_fetch_failed": dataset_mkt1_fetch_failed(),
        "mkt2_both_keys_missing": dataset_mkt2_both_keys_missing(),
        "mkt2_only_five_rows": dataset_mkt2_only_five_rows(),
        "mkt2_one_row_after_baseline": dataset_mkt2_one_row_after_baseline(),
        "mkt2_diverging": dataset_mkt2_diverging(),
        "mkt3_unit_mismatch": dataset_mkt3_unit_mismatch(),
        "all_empty": dataset_all_empty(),
        "revised_row": dataset_revised_row(),
        "unknown_unit_literal": dataset_unknown_unit_literal(),
        "fetched_before_obs": dataset_fetched_before_obs(),
    }
