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


def test_fund_category_help_states_real_source_not_old_claim():
    """「基金類別」欄 help 須如實說明來源（含 FundClear 後備、缺值不以名稱補），不得回到舊不實說法。"""
    from ui.helpers.fund_grp_health.columns import health_column_config
    cfg = health_column_config()
    helps = [str(getattr(v, "get", lambda *_: "")("help", "") or v) for k, v in cfg.items() if k == "基金類別"]
    text = _norm("".join(helps))
    assert text, "找不到「基金類別」欄 help"
    assert _norm("MoneyDJ 頁面上寫的") not in text, "舊不實說法：值不只來自 MoneyDJ 頁面"
    assert "FundClear" in text and "不以基金名稱補值" in text


def test_mk_fund_signal_comment_does_not_claim_no_source_exists():
    """helpers.py 註解不得宣稱「目前沒有這樣的來源」（MoneyDJ／FundClear category 原值存在）。"""
    src = _norm((ROOT / "ui/helpers/macro/helpers.py").read_text(encoding="utf-8"))
    assert _norm("目前沒有這樣的來源") not in src
    assert "不得由基金名稱推定" in src


def test_asset_attr_help_has_no_false_no_source_claim():
    """「基金屬性」欄恆「—」的原因是名稱推定停用＋本欄未接 category 原值，
    不是「無可靠來源」（MoneyDJ／FundClear category 本身可追溯，已用於「基金類別」欄）。
    突變：改回舊句 → 本條紅。"""
    from ui.helpers.fund_grp_health.columns import unified_column_config
    help_txt = _norm(str(unified_column_config()["基金屬性"]["help"]))
    src = _norm((ROOT / "ui/helpers/fund_grp_health/signals.py").read_text(encoding="utf-8"))
    # 2026-10-13(LINE 推播與舊 UI 解耦):`mk_signal_by_code` 實作已搬到 L2,兩檔一起掃。
    src += _norm((ROOT / "services/fund_grp_health/signals.py").read_text(encoding="utf-8"))
    for bad in ("目前尚無可靠來源", "無可追溯的原始分類來源前不顯示"):
        assert _norm(bad) not in help_txt, f"columns.py 基金屬性 help 含不實措辭：{bad}"
        assert _norm(bad) not in src, f"signals.py 含不實措辭：{bad}"


def _dict_label(rel: str, key: str, call_attr: str | None = None) -> list[str]:
    """AST：取 `{key: st.column_config.X("label", ...)}` 的第一個位置參數字串。"""
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Dict):
            for k, v in zip(n.keys, n.values):
                if (isinstance(k, ast.Constant) and k.value == key and isinstance(v, ast.Call)
                        and v.args and isinstance(v.args[0], ast.Constant)):
                    out.append(v.args[0].value)
    return out


def test_tier_column_label_consistent_across_editors():
    """同一個 Sheet 級別欄（tier ＝ policy_tier）在各編輯器 label 一致為「配置級別」。"""
    assert _dict_label("ui/helpers/v2_editor.py", "tier") == ["配置級別"]
    assert _dict_label("ui/helpers/portfolio/policy_admin_section.py", "tier") == ["配置級別"]


def test_sigma_explainer_has_no_core_satellite_assignment():
    from ui.helpers.chart.metric_explainers import METRIC_EXPLAINERS as D
    body = _norm(D["sigma"]["body"])
    for bad in ("擺核心", "擺衛星", "求穩）", "求攻）"):
        assert bad not in body, f"σ 說明不得把波動度指派為核心／衛星：{bad}"
    assert "越大越刺激" in body


def test_satellite_stop_help_mentions_unset_state():
    """T7「衛星停利」欄 help 須說明三態：未設定 ≠ 衛星（⬜ 未設定、不判）。"""
    tree = ast.parse((ROOT / "ui/tab3_t7_ledger.py").read_text(encoding="utf-8"))
    helps = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Dict):
            for k, v in zip(n.keys, n.values):
                if isinstance(k, ast.Constant) and k.value == "衛星停利" and isinstance(v, ast.Call):
                    for kw in v.keywords:
                        if kw.arg == "help":
                            helps.append(_norm("".join(
                                c.value for c in ast.walk(kw.value) if isinstance(c, ast.Constant))))
    assert len(helps) == 1, helps
    assert "未設定" in helps[0] and "不當衛星" in helps[0]
