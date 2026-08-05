"""2026-08-05 稽核 — 中期循環 / 拐點警報三項必修的**接線驗證**(`PROCESS.md §4`)。

覆蓋:
  必修 1(§4.1 量綱 + §1)ADL 三處把「比值」當「百分比」用
  必修 2(教學語料接線)Z-Score 卡加歷史錨點 —— MACRO_EDU 原本全站 0 consumer
  必修 3(§3.3 SSOT)Z-Score 卡標出「這張卡屬於哪個分類」,分類讀服務層不自建對照表

⚠️ 設計準則(`PROCESS.md §4`):本 repo 已 6 次出現「算對了但沒接出去」。
   凡是「服務層/語料早就備妥、只差 caller」的項目,一律**檢查呼叫端**
   (AST 找實際取用的欄位 / 實際傳入的引數),而不是只測 helper 本身能不能跑 ——
   後者在 caller 沒改時照樣綠,等於沒測。每條 test 的 docstring 標明「修正前紅在哪」。

【背景 — 必修 1 的錯在哪】
`services/macro/us_indicators.py` 的 `R["ADL"]` 是**對的**:
    value = RSP 收盤 ÷ SPY 收盤的比值(無因次,量級 ~0.29)
    prev  = 該比值的**月變動百分比**
    unit  = ""(服務層誠實標示此值無單位)
錯的是三個 UI 消費端:兩處拿比值去比負數門檻(條件恆假 = 死分支 / 指針恆黏在
0.29 = 假訊號),一處在 UI 硬寫 `"%"` 把比值印成百分比。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from ui.components.macro_card_edu import MACRO_EDU
from ui.tab1_macro_midcycle import (
    _EDU_ANCHOR_PILOT,
    _ZS_INDICATORS,
    _ZS_MATRIX_LABEL,
    _ZS_TYPE_UNKNOWN,
    _card_label,
    _card_note,
    _card_unit,
)

_ROOT = Path(__file__).resolve().parents[1]
_MID = _ROOT / "ui" / "tab1_macro_midcycle.py"
_INFL = _ROOT / "ui" / "tab1_macro_inflection.py"
_SVC = _ROOT / "services" / "macro" / "us_indicators.py"

_MID_SRC = _MID.read_text(encoding="utf-8")
_ZS_KEYS = {r[0] for r in _ZS_INDICATORS}


# ══════════════════════════════════════════════════════════════
# 共用 AST 工具
# ══════════════════════════════════════════════════════════════
def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _const_str_arg(call: ast.Call) -> str | None:
    if call.args and isinstance(call.args[0], ast.Constant) \
            and isinstance(call.args[0].value, str):
        return call.args[0].value
    return None


def _is_get_of(node: ast.AST, key: str) -> bool:
    """node 子樹裡有沒有 `<something>.get("<key>")` 呼叫。"""
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == "get" and _const_str_arg(n) == key:
            return True
    return False


def _fields_read_from_indicator(path: Path, ind_key: str) -> set[str]:
    """該檔實際從 `ind["<ind_key>"]` 這個 dict 取用了哪些欄位名。

    兩種寫法都吃:
      (a) `_d = ind.get("ADL") or {}` → 之後 `_d.get("prev")`     (拐點警報檔)
      (b) `(ind.get("ADL") or {}).get("prev")`                    (中期循環檔)
    """
    tree = _tree(path)
    # pass 1:哪些變數名綁到了該 indicator dict
    bound: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and _is_get_of(n.value, ind_key):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    bound.add(t.id)
    # pass 2:對這些變數 / 對內嵌 `.get("<key>")` 結果做的欄位取用
    out: set[str] = set()
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "get"):
            continue
        fld = _const_str_arg(n)
        if fld is None or fld == ind_key:
            continue
        recv = n.func.value
        if (isinstance(recv, ast.Name) and recv.id in bound) or _is_get_of(recv, ind_key):
            out.add(fld)
    return out


def _calls_named(path: Path, fname: str) -> list[ast.Call]:
    return [n for n in ast.walk(_tree(path))
            if isinstance(n, ast.Call) and
            (getattr(n.func, "id", None) == fname or getattr(n.func, "attr", None) == fname)]


# ══════════════════════════════════════════════════════════════
# 必修 1 — ADL:比值 vs 月變動 % 的接線
# ══════════════════════════════════════════════════════════════
class TestAdlReadsMomNotRatio:
    """§4.1 量綱陷阱。三處必須同一批修完 —— 只修一處會留下一半對一半錯。"""

    @pytest.mark.parametrize("path", [_INFL, _MID], ids=["inflection", "midcycle"])
    def test_alert_paths_read_prev_not_value(self, path: Path):
        """**修正前必紅**(兩個 id 都紅)——

        拐點警報檔:全域導航塔第三個儀表(軸域 ±10、suffix %、燈號門檻 ±2、
          紅線 ±5,整組刻度都是為月變動 % 設計)原本餵 `value` 的比值 →
          指針永遠落在 0.29,燈永遠是中性,不論真實廣度如何(§1 假訊號)。
        中期循環檔:Situation B 極端乖離警報原本 `value < -2`,而 RSP÷SPY 是
          兩個正價格相除、恆為正 → 條件恆假,這張警報卡從未觸發過(死分支)。

        判準(`PROCESS.md §4`):把取用欄位改回 `value`,本 test 兩條 assert 同時紅。
        """
        _fields = _fields_read_from_indicator(path, "ADL")
        assert "prev" in _fields, (
            f"{path.name} 未從 ADL 取 `prev`(月變動 %)—— 警報/儀表沒接到正確量綱")
        assert "value" not in _fields, (
            f"{path.name} 仍讀 ADL 的 `value`(RSP÷SPY 比值,恆為正)去比百分比門檻 "
            "—— 這是本次要修掉的量綱錯,不可回退")

    def test_service_contract_still_puts_mom_in_prev(self):
        """漂移鎖:上述接線建立在服務層契約上 —— value=比值 / prev=月變動 % / unit=""。

        修正前不紅(服務層本來就是對的),但服務層一旦改把月變動塞回 `value`,
        本 test 會紅並指名要同步改 UI,避免又變成「一半對一半錯」。
        """
        _m = re.search(r'R\["ADL"\]\s*=\s*dict\(.*?weight=[^\n]*\)',
                       _SVC.read_text(encoding="utf-8"), re.S)
        assert _m, '找不到 R["ADL"] = dict(...) 區塊(服務層結構已變,請一併重評 UI 接線)'
        _blk = _m.group(0)
        assert re.search(r"value\s*=\s*round\(\s*v\s*,", _blk), (
            "ADL 的 value 不再是比值 v —— UI 的單位/小數位設定需同步重評")
        assert re.search(r"prev\s*=\s*round\(\s*chg\s*,", _blk), (
            "ADL 的 prev 不再是月變動 chg —— UI 三處警報/儀表的取用欄位需同步改")
        assert re.search(r'unit\s*=\s*""', _blk), (
            "服務層不再標 ADL 為無單位 —— 卡片單位會跟著變,需重看畫面")


# ══════════════════════════════════════════════════════════════
# 必修 1 續 — 單位一律吃服務層 `unit`,UI 不硬寫(§3.3 SSOT)
# ══════════════════════════════════════════════════════════════
class TestCardUnitFromService:
    def test_service_empty_unit_beats_spec_percent(self):
        """**修正前必紅**(修正前根本沒有這個 fn,import 就 ImportError)——

        ADL 就是實例:服務層標無單位,矩陣 spec 硬寫 `%` → 畫面印「值 0.29 %」。
        空字串是**有意義的答案**(此值無單位),不可被 falsy 判斷退回 spec 的錯單位。
        """
        assert _card_unit("%", {"unit": ""}) == ""

    def test_service_unit_wins_when_more_precise(self):
        """服務層用字比 spec 精確時(萬 → 萬人 / 千 → 千戶)也以服務層為準。"""
        assert _card_unit("萬", {"unit": "萬人"}) == "萬人"
        assert _card_unit("千", {"unit": "千戶"}) == "千戶"

    def test_spec_is_fallback_only_when_service_omits_field(self):
        """邊界:服務層整格沒給 `unit` 欄 → 退 spec,不得變空白。"""
        assert _card_unit("%", {"value": 3.2}) == "%"
        assert _card_unit("%", {}) == "%"
        assert _card_unit("%", None) == "%"

    def test_adl_spec_no_longer_hardwires_percent(self):
        """**修正前必紅** —— spec 那一欄原本寫死百分比。"""
        _row = next(r for r in _ZS_INDICATORS if r[0] == "ADL")
        assert _row[2] != "%", "ADL 的 spec 單位仍是百分比(比值不是百分比)"
        assert _card_unit(_row[2], {"unit": ""}) == ""

    def test_render_actually_calls_card_unit(self):
        """**修正前必紅**(0 caller)—— helper 寫好但 render 沒接 = 沒修。

        判準:把 render 那行改回直接用 spec 欄組單位字串,本 test 紅。
        """
        assert _calls_named(_MID, "_card_unit"), "`_card_unit` 在中期循環檔 0 caller"


# ══════════════════════════════════════════════════════════════
# 必修 2 — 歷史錨點(MACRO_EDU 原本全站 0 consumer)
# ══════════════════════════════════════════════════════════════
class TestHistoricalAnchorWiring:
    def test_two_arg_call_behaviour_unchanged(self):
        """相容性硬要求:既有 2-arg 呼叫與 `test_midcycle_card_labels` 的斷言不得被改簽名弄紅。"""
        assert _card_note("🟢 正常", {}) == "🟢 正常"
        assert _card_note("🟢 正常", {}, None) == "🟢 正常"

    def test_anchor_rendered_when_edu_supplied(self):
        """**修正前必紅**(修正前 `_card_note` 只吃 2 個參數 → TypeError)。"""
        _n = _card_note("🟢 正常", {}, MACRO_EDU["SAHM"])
        assert "2008/03" in _n and "雷曼海嘯" in _n

    def test_anchor_is_html_escaped(self):
        """錨點文字含「安全區 < 0.3」「健康區 < 10%」;卡片走 unsafe_allow_html,
        不 escape 會被當標籤吃掉整段。"""
        _n = _card_note("🟢 正常", {}, {"historical_anchor": "安全區 < 0.3"})
        assert "&lt; 0.3" in _n and "< 0.3" not in _n

    def test_anchor_sits_after_service_desc(self):
        """版面約定:燈號 → 服務層口徑 → 歷史錨點。錨點是比例尺,不該蓋掉當期口徑。"""
        _n = _card_note("🟢 正常", {"desc": "口徑說明"},
                        {"historical_anchor": "錨點內容"})
        assert _n.index("口徑說明") < _n.index("錨點內容")

    def test_render_passes_edu_into_every_card_note_call(self):
        """**修正前必紅**(所有呼叫都只有 2 個引數)——

        `PROCESS.md §4`:語料早就寫好、只差 caller。這裡檢查**呼叫端**真的把
        第三個引數傳進去,而不是只驗 `_card_note` 自己吃得下 edu。
        判準:拿掉 render 端任一個 `_zedu` 引數,本 test 紅。
        """
        _calls = _calls_named(_MID, "_card_note")
        assert _calls, "`_card_note` 在中期循環檔 0 caller"
        _bad = [c.lineno for c in _calls if len(c.args) < 3]
        assert not _bad, f"這些 `_card_note` 呼叫沒把教學語料傳進去:line {_bad}"

    def test_pilot_keys_are_real_matrix_indicators_with_real_anchors(self):
        """樣張 key 必須(a)真的是矩陣上的卡、(b)語料真的有錨點 —— 否則接了等於沒接。

        §1:不得把不在矩陣上的 key(例如只出現在拐點儀表 / 短線雷達的指標)
        寫進樣張名單,那會是「掛了名單但畫面上找不到」的假交付。
        """
        assert _EDU_ANCHOR_PILOT, "樣張名單是空的"
        for _k in _EDU_ANCHOR_PILOT:
            assert _k in _ZS_KEYS, f"{_k} 不在 Z-Score 矩陣上,樣張放這裡看不到"
            assert _k in MACRO_EDU, f"{_k} 在教學語料裡不存在"
            assert str(MACRO_EDU[_k].get("historical_anchor") or "").strip(), \
                f"{_k} 沒有 historical_anchor,列進樣張只會多一行空白"

    def test_pilot_is_a_subset_pending_user_signoff(self):
        """樣張 = 3 張,不是一次全鋪 —— user 要先看效果再決定要不要鋪滿。"""
        assert len(_EDU_ANCHOR_PILOT) < len(_ZS_KEYS)

    def test_ui_does_not_author_indicator_prose_of_its_own(self):
        """§8.3 F-GRAY-4:教學敘事的唯一來源是 `ui/components/macro_card_edu.py`。

        UI 層不得就地補指標語意字串 —— 抽樣驗:樣張三張的錨點原文都**不**出現在
        中期循環檔的原始碼裡(出現 = 有人把語料複製貼過來,兩份必然漂移)。
        """
        for _k in _EDU_ANCHOR_PILOT:
            _anchor = str(MACRO_EDU[_k]["historical_anchor"])
            assert _anchor not in _MID_SRC, f"{_k} 的錨點文字被複製進 UI 檔了"


# ══════════════════════════════════════════════════════════════
# 必修 3 — 卡片標出分類,分類讀服務層(§3.3 不自建對照表)
# ══════════════════════════════════════════════════════════════
class TestCardBucketLabel:
    def test_label_carries_service_type(self):
        """**修正前必紅**(修正前沒有 `_card_label`,import 即 ImportError)——

        user 的困惑:「為什麼美元指數屬於景氣循環 3-12 月?」
        服務層對它標的分類是資金流向,把這件事標在卡上就回答了。
        """
        assert _card_label({"type": "資金流向"}).endswith("資金流向")
        assert _card_label({"type": "市場廣度"}).endswith("市場廣度")
        assert _card_label({"type": "流動性"}).startswith(_ZS_MATRIX_LABEL)

    def test_unknown_type_is_honest_placeholder_not_a_guess(self):
        """§1:服務層沒給分類就誠實佔位,**不准**猜一個桶塞上去。"""
        for _zd in ({}, {"type": ""}, {"type": None}, None):
            _lb = _card_label(_zd)
            assert _ZS_TYPE_UNKNOWN in _lb
            for _guess in ("領先", "同時", "落後", "流動性", "中期"):
                assert _guess not in _lb, f"分類缺失時猜了「{_guess}」:{_lb!r}"

    def test_card_label_is_not_a_hardcoded_constant_anymore(self):
        """**修正前必紅** —— 原本 18 張卡的 label 全是同一個寫死字串,
        等於沒有任何分類資訊。

        判準:把 `label=` 改回字串字面值,本 test 紅。
        """
        _found = []
        for _c in _calls_named(_MID, "_render_macro_indicator_card"):
            for _kw in _c.keywords:
                if _kw.arg == "label":
                    _found.append(_kw.value)
        assert _found, "找不到卡片 render 呼叫的 label 引數(結構已變,請更新本測試)"
        for _v in _found:
            assert not isinstance(_v, ast.Constant), (
                "卡片 label 又變回寫死常數 —— 分類標記等於沒接")
        assert _calls_named(_MID, "_card_label"), "`_card_label` 0 caller"

    def test_no_ui_side_bucket_lookup_table(self):
        """§3.3:桶歸屬只能讀 SSOT。UI 層不得出現「指標 key → 桶名」的 dict literal
        (`shared.macro_buckets` 的 key 與本矩陣大量不同名,要接就得再寫一份別名表 ——
        那就是第二份真相)。AST 掃 dict literal,不受引號/空白風格影響。"""
        _dup = [
            n.lineno for n in ast.walk(_tree(_MID))
            if isinstance(n, ast.Dict)
            and any(isinstance(k, ast.Constant) and k.value in _ZS_KEYS for k in n.keys)
        ]
        assert not _dup, f"中期循環檔出現指標 key 對照表 dict literal:line {_dup}"

    def test_every_matrix_card_gets_a_label(self):
        """回歸:資料不足 / 格式異常的佔位列也要有 label,否則 render 端 KeyError。"""
        for _zd in ({}, {"type": "領先"}, {"value": None}):
            assert _card_label(_zd).strip()


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
