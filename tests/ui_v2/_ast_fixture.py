# -*- coding: utf-8 -*-
"""💼 我的資產頁（BL-0525 Batch D）測試共用的腳本產生器：固定 fixtures／替身、不打任何外部網路、不讀 secrets。

`script(variant)` 回一段可交給 `AppTest.from_string` 或 streamlit 子行程執行的 Python 原始碼。持股那一側用 `ui_v2/hld/fixtures` 的
`full` 情境（同 `test_live_390_page.py` 的 hld 腳本），配置那一側用 `ui_v2/alo/fixtures` 的 `full` 情境；兩側各自一個替身載入函式。
variant：`full`（兩側正常）、`no_active`（載入函式拋 `NoActiveSource`）、`alo_fail`／`hld_fail`（一側載入函式拋例外）、
`alo_fail_hld_noactive`／`alo_noactive_hld_fail`（一側拋例外、另一側拋 `NoActiveSource`；取數失敗優先於尚未設定）、
`hld_count_boom`（持倉體檢的計數行拋 `ValueError`，只該讓持股這一側改畫狀態）。
`alo`／`hld`：兩側各自挑 fixtures 情境名（預設 `full`）；`blank_target=True`：配置側用 `inband` 並把第一個類別的目標比重留空（A6m）。
"""

from __future__ import annotations

import pathlib

_ROOT = pathlib.Path(__file__).resolve().parents[2]

_HEAD = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
import datetime
from ui_v2 import active_gate
from ui_v2.alo import fixtures as alo_fixtures
from ui_v2.hld import fixtures as hld_fixtures, logic as hld_logic
from ui_v2.asset import page

def _scrub(node):
    if isinstance(node, str):
        return node.replace(hld_logic.HINT, "")
    if isinstance(node, dict):
        return {{k: _scrub(v) for k, v in node.items()}}
    if isinstance(node, list):
        return [_scrub(v) for v in node]
    return node

_hld_dataset = _scrub(hld_fixtures.scenario("full")["dataset"])
for _h in _hld_dataset["holding"]:
    if _h["policy_id"] == "DIRECT":
        _h["policy_id"] = "P-001"
_hld_args = {{"direct_policy_id": "DIRECT", "today": datetime.date(2026, 9, 28),
              "nav_provenance": {{r["fund_code"]: {{"cache_fallback": False, "stale": None}} for r in _hld_dataset["nav"]}}}}
_alo_dataset = alo_fixtures.scenario("full")

def _alo_load():
    return {{"dataset": _alo_dataset, "notes": {{}}}}

def _hld_load():
    return {{"dataset": _hld_dataset, "live_args": _hld_args}}
"""

_BODY = {
    "full": """
page.render(alo_live={"load": _alo_load, "save": lambda *_a: {"status": "saved"}, "mask": str},
            hld_live={"load": _hld_load, "save": lambda *_a: {"status": "saved"}, "mask": str})
""",
    "no_active": """
def _none():
    raise active_gate.NoActiveSource("AUTH_REQUIRED")
page.render(alo_live={"load": _none, "save": None, "mask": str}, hld_live={"load": _none, "save": None, "mask": str})
""",
    "alo_fail": """
def _boom():
    raise RuntimeError("alo-load-boom")
page.render(alo_live={"load": _boom, "save": None, "mask": str},
            hld_live={"load": _hld_load, "save": lambda *_a: {"status": "saved"}, "mask": str})
""",
    "hld_fail": """
def _boom():
    raise RuntimeError("hld-load-boom")
page.render(alo_live={"load": _alo_load, "save": lambda *_a: {"status": "saved"}, "mask": str},
            hld_live={"load": _boom, "save": None, "mask": str})
""",
}

_BLANK_TARGET = """
import copy
_alo_dataset = copy.deepcopy(alo_fixtures.scenario("inband"))
for _row in _alo_dataset["user_setting"]:
    if _row["setting_key"] == "alo_target_weights":
        _row["setting_value"][0]["weight_ratio"] = None
"""

_BODY.update({
    "alo_fail_hld_noactive": """
def _boom():
    raise RuntimeError("alo-load-boom")
def _none():
    raise active_gate.NoActiveSource("AUTH_REQUIRED")
page.render(alo_live={"load": _boom, "save": None, "mask": str}, hld_live={"load": _none, "save": None, "mask": str})
""",
    "alo_noactive_hld_fail": """
def _boom():
    raise RuntimeError("hld-load-boom")
def _none():
    raise active_gate.NoActiveSource("AUTH_REQUIRED")
page.render(alo_live={"load": _none, "save": None, "mask": str}, hld_live={"load": _boom, "save": None, "mask": str})
""",
    "hld_count_boom": """
from ui_v2 import sections
def _count_boom(_model):
    raise ValueError("持倉體檢計數不成立：測試注入")
_orig_counts = sections.hld_counts
sections.hld_counts = _count_boom
try:   # AppTest 跑在同一個行程：用完一定還原，免得汙染別的測試
    page.render(alo_live={"load": _alo_load, "save": lambda *_a: {"status": "saved"}, "mask": str},
                hld_live={"load": _hld_load, "save": lambda *_a: {"status": "saved"}, "mask": str})
finally:
    sections.hld_counts = _orig_counts
""",
})

VARIANTS = tuple(_BODY)


def script(variant: str = "full", *, alo: str = "full", hld: str = "full", blank_target: bool = False) -> str:
    head = _HEAD.replace('alo_fixtures.scenario("full")', f"alo_fixtures.scenario({alo!r})") \
                .replace('hld_fixtures.scenario("full")', f"hld_fixtures.scenario({hld!r})")
    if blank_target:
        head += _BLANK_TARGET
    return head + _BODY[variant]
