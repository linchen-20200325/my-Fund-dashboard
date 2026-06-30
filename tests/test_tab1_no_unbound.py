"""v19.137 regression — 物理重排(v19.134)後防跨桶變數 use-before-assign.

背景:v19.134 把 expert 區重排為 🌳→📈→🎯→⚠️,情境判斷(中期桶)
用了 War Room(拐點桶,在後)才定義的 _sahm_v/_adl_v → UnboundLocalError(production)。

本測試用 AST 靜態檢查 render_macro_tab:對重排敏感的關鍵變數,
確認在「中期桶情境判斷」使用前已在同函式內先定義。
"""
from __future__ import annotations

import ast
import pathlib


def _load_source():
    p = pathlib.Path(__file__).parent.parent / "ui" / "tab1_macro.py"
    return p.read_text(encoding="utf-8")


def _load_midcycle_source():
    # v19.262 P3-A3: L3 情境判斷卡隨中期循環整 section 抽至 ui/tab1_macro_midcycle.py
    p = pathlib.Path(__file__).parent.parent / "ui" / "tab1_macro_midcycle.py"
    return p.read_text(encoding="utf-8")


class TestNoUnboundLocal:
    def test_situation_cards_define_sahm_adl_locally(self):
        """情境判斷區的 _sahm_v / _adl_v 必須在『L3 情境判斷』區塊內自取,
        不依賴下方 War Room(物理重排後在後面)。

        v19.262 P3-A3: 中期循環(含 L3 情境判斷)整 section 抽至 ui/tab1_macro_midcycle.py。
        """
        src = _load_midcycle_source()
        # 定位情境判斷區塊(避開 module docstring 中的同名字串)
        idx = src.find("L3 情境判斷卡（Logic")
        assert idx > 0, "找不到 L3 情境判斷區塊"
        # 取該區塊後 ~30 行
        block = src[idx: idx + 1500]
        # 在第一次使用 _sahm_v / _adl_v 之前,必須有 assignment
        for _var in ("_sahm_v", "_adl_v"):
            _assign = block.find(f"{_var} = float")
            _use = block.find(f"{_var} <")
            assert _assign > 0, f"情境判斷區未自取 {_var}"
            # assignment 必須在第一次比較使用之前
            assert _assign < _use, f"{_var} 在比較使用後才定義(use-before-assign)"

    def test_render_macro_tab_compiles(self):
        """整檔 AST parse 成功(語法層守衛)"""
        src = _load_source()
        tree = ast.parse(src)
        # 確認 render_macro_tab 存在
        fns = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        assert "render_macro_tab" in fns
