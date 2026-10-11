# -*- coding: utf-8 -*-
"""命名原則安全小批次（客戶 2026-10-11 裁示）的文字守衛。

- 客戶在 Sheet 設定的 core/satellite → 「配置級別」；規則衍生結果 → 「系統分類」。
- 「核心/衛星」欄 help 不得像角色指派／投資建議；核心／衛星說明不得寫死 80/20。
- 設定頁顯示欄名為「配置級別」，但 Sheet 標頭鍵 `policy_tier` 不得被改（改了會讀不到使用者 Sheet）。
以 AST 字串常數檢查，不用全檔字串 grep。
"""
from __future__ import annotations

import ast
import pathlib
import re
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _consts(rel: str) -> list[str]:
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _norm(t: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", t))


def test_core_satellite_help_is_system_classification_not_advice():
    from ui.helpers.fund_grp_health.columns import health_column_config
    cfg = health_column_config()
    helps = [str(getattr(v, "get", lambda *_: "")("help", "") or v) for k, v in cfg.items() if "核心/衛星" in k]
    text = _norm("".join(helps))
    assert text, "找不到「核心/衛星」欄 help"
    for bad in ("扮演什麼角色", "放大部位", "小部位"):
        assert bad not in text, f"help 不得含建議／角色指派字樣：{bad}"
    assert "系統分類" in text and "配置級別" in text
    assert "優先於" in text, "須保留判斷順序說明(衛星優先於 3-3-3)"


def test_core_satellite_explainer_has_no_hardcoded_ratio():
    from ui.helpers.chart.metric_explainers import METRIC_EXPLAINERS as D
    body = _norm(D["core_satellite"]["body"])
    for bad in ("80%", "20%", "建議約"):
        assert bad not in body
    assert "配置級別" in body


def test_policy_admin_label_renamed_but_sheet_header_key_untouched():
    c = _consts("ui/helpers/portfolio/policy_admin_section.py")
    assert "配置級別" in c and "配置定位" not in c
    from repositories.policy._helpers import OPTIONAL_COLS
    assert "policy_tier" in OPTIONAL_COLS


def test_policy_tier_column_label_via_ast():
    tree = ast.parse((ROOT / "ui/helpers/portfolio/policy_admin_section.py").read_text(encoding="utf-8"))
    labels = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Dict):
            for k, v in zip(n.keys, n.values):
                if (isinstance(k, ast.Constant) and k.value == "policy_tier" and isinstance(v, ast.Call)
                        and v.args and isinstance(v.args[0], ast.Constant)):
                    labels.append(v.args[0].value)
    assert labels == ["配置級別"], labels
