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
        # ⚠️ 2026-08-05 更新:ADL 變數由 `_adl_v = float(...value...)` 改為
        #    `_adl_mom_pct = _safe_num(...prev...)`。這不是改名而已 ——
        #    `value` 是 RSP÷SPY **比值**(恆為正),`prev` 才是**月變動 %**;
        #    原本拿比值去比 `< -2` 的負數門檻,Situation B 這張警報卡自建立起
        #    從未觸發過一次(§1 假訊號)。本測試守的是「**不得 use-before-assign**」
        #    這個契約,故改為**釘 assignment 早於 use**,不釘變數名與取值函式,
        #    避免下次正當改名時測試又瞎掉。
        for _var in ("_sahm_v", "_adl_mom_pct"):
            _assign = block.find(f"{_var} = ")
            _use = block.find(f"{_var} <")
            assert _assign > 0, f"情境判斷區未自取 {_var}"
            # assignment 必須在第一次比較使用之前
            assert _assign < _use, f"{_var} 在比較使用後才定義(use-before-assign)"

        # ADL 專屬回歸鎖:必須讀 `prev`(月變動 %),讀 `value`(比值)會讓
        # Situation B 的負數門檻恆假 —— 那正是本輪修掉的 bug。
        assert '"ADL"' in block and '"prev"' in block, \
            "Situation B 未讀 ADL 的 prev(月變動 %)— 讀 value(比值)會讓警報永不觸發"

    def test_render_macro_tab_compiles(self):
        """整檔 AST parse 成功(語法層守衛)"""
        src = _load_source()
        tree = ast.parse(src)
        # 確認 render_macro_tab 存在
        fns = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        assert "render_macro_tab" in fns
