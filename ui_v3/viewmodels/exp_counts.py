# -*- coding: utf-8 -*-
"""EXP-0 篩選結果結論列的計數文案與一致性驗證（S0；純 Python，只用標準函式庫）。

定義（客戶 2026-11-14 裁示）：
- N（`matched`）＝明確符合條件的基金數；
- M（`undetermined`）＝因資料不足而無法判定的基金數。
本模組**只**把呼叫端給的三個輸入組成文案：`conditions_count`（生效條件數）、`matched`（N）、`undetermined`（M）。
不取數、不判定、不排序、不新增任何金融公式、來源或閾值。

契約：
- `conditions_count == 0` → 文案「尚未設定條件」，N／M 不展示（回傳的 `matched`／`undetermined` 為 None）；
  此時呼叫端傳什麼（含 None、含負數、含任何型別）都不檢查、不展示。
- `conditions_count > 0` → `matched`、`undetermined` 必須是非負整數；bool、float、字串、None、負數一律
  `ValueError`（訊息含欄位名與收到的值）。缺值絕不當 0。
- 文案四種（逐字；N、M 為十進位整數，不加千分位）：
  N>0、M==0「目前條件下有 N 檔符合」；
  N>0、M>0「目前條件下有 N 檔符合；另有 M 檔無法判定」；
  N==0、M==0「目前條件下沒有符合的基金」；
  N==0、M>0「目前條件下沒有符合的基金；另有 M 檔無法判定」。
  M==0 絕不出現尾句；無法判定不被當成符合、0、中性或安全。
- 一致性驗證（不一致一律 `ValueError`）：EXP-2 列數必須等於 N+M；EXP-7 最後一列的符合數必須等於 N、
  無法判定數必須等於 M。輸入皆由呼叫端提供，本模組不自行讀取任何表。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

TEXT_NO_CONDITION = "尚未設定條件"
TEXT_HAS_MATCH_PREFIX = "目前條件下有 "
TEXT_HAS_MATCH_SUFFIX = " 檔符合"
TEXT_NO_MATCH = "目前條件下沒有符合的基金"
TEXT_UNDETERMINED_PREFIX = "；另有 "
TEXT_UNDETERMINED_SUFFIX = " 檔無法判定"


def require_count(name: str, value: object) -> int:
    """非負整數。bool 是 int 的子類，明確擋掉；float、字串、None、負數一律拒絕（缺值不得轉成 0）。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} 必須是非負整數，收到 {value!r}（{type(value).__name__}）")
    if value < 0:
        raise ValueError(f"{name} 必須是非負整數，收到 {value!r}")
    return value


@dataclass(frozen=True)
class ExpCountsConclusion:
    """EXP-0 結論列。`text` 為畫面文案；`matched`（N）、`undetermined`（M）為展示用數字，
    尚未設定條件時兩者皆為 None（不展示，不是 0）。
    """

    text: str
    matched: Optional[int] = None
    undetermined: Optional[int] = None

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError(f"text 必須是非空字串，收到 {self.text!r}")
        if (self.matched is None) != (self.undetermined is None):
            raise ValueError("matched 與 undetermined 必須同時有值或同時為 None")
        if self.matched is not None:
            require_count("matched", self.matched)
            require_count("undetermined", self.undetermined)

    @property
    def counts_shown(self) -> bool:
        return self.matched is not None


def exp0_conclusion(conditions_count: object, matched: object, undetermined: object) -> ExpCountsConclusion:
    """依生效條件數、N、M 組出 EXP-0 結論列（契約見模組 docstring）。"""
    conditions = require_count("conditions_count", conditions_count)
    if conditions == 0:
        return ExpCountsConclusion(text=TEXT_NO_CONDITION)
    n = require_count("matched", matched)
    m = require_count("undetermined", undetermined)
    text = f"{TEXT_HAS_MATCH_PREFIX}{n}{TEXT_HAS_MATCH_SUFFIX}" if n > 0 else TEXT_NO_MATCH
    if m > 0:
        text += f"{TEXT_UNDETERMINED_PREFIX}{m}{TEXT_UNDETERMINED_SUFFIX}"
    return ExpCountsConclusion(text=text, matched=n, undetermined=m)


def verify_exp2_row_count(row_count: object, matched: object, undetermined: object) -> None:
    """EXP-2 列數必須等於 N+M；任一輸入不是非負整數，或不相等，一律 `ValueError`。"""
    rows = require_count("row_count", row_count)
    n = require_count("matched", matched)
    m = require_count("undetermined", undetermined)
    if rows != n + m:
        raise ValueError(f"EXP-2 列數 {rows} 不等於 N+M（{n}+{m}={n + m}）")


def verify_exp7_last_row(rows: Sequence[Sequence[object]], matched: object, undetermined: object) -> None:
    """EXP-7 最後一列的（符合數, 無法判定數）必須等於（N, M）；不一致一律 `ValueError`。

    `rows` 為 EXP-7 逐條列（由呼叫端提供，每列是 `(符合數, 無法判定數)` 兩個元素的 tuple 或 list）。
    只檢查**最後一列**（規格只要求末列＝N、M）；前面各列不檢查、不要求任何單調性。
    `rows` 為空、末列不是兩個元素、末列的值不是非負整數（含 None、bool），一律 `ValueError`。
    """
    n = require_count("matched", matched)
    m = require_count("undetermined", undetermined)
    if isinstance(rows, (str, bytes)) or not isinstance(rows, (list, tuple)) or len(rows) == 0:
        raise ValueError(f"EXP-7 必須提供至少一列（list 或 tuple），收到 {rows!r}")
    last = rows[-1]
    if isinstance(last, (str, bytes)) or not isinstance(last, (list, tuple)) or len(last) != 2:
        raise ValueError(f"EXP-7 最後一列必須是（符合數, 無法判定數）兩個元素，收到 {last!r}")
    last_matched = require_count("EXP-7 末列符合數", last[0])
    last_undetermined = require_count("EXP-7 末列無法判定數", last[1])
    if last_matched != n:
        raise ValueError(f"EXP-7 末列符合數 {last_matched} 不等於 N（{n}）")
    if last_undetermined != m:
        raise ValueError(f"EXP-7 末列無法判定數 {last_undetermined} 不等於 M（{m}）")
