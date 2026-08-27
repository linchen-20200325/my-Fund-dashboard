"""守衛:**production code 不得引用已退役的 §8.2.A 例外 ID**(2026-08-27)。

## 這道守衛在擋什麼

憲法主檔 §8.2.A 的例外表是「架構硬規則的合法豁免清單」,末句明文
**「禁止未經登錄的潛在『軟例外』」**。例外會退役(豁免對象被刪掉、或被升級成真重構),
退役時該列**整列加刪除線**保留在表上 —— 保留是為了可追溯,**不是**為了讓人繼續引用。

實證(本檔誕生的原因):`ui/helpers/macro/beginner_view.py` 有兩處寫
「不抽 SSOT;§8.2.A EX-POLICY-1 同理」,但 **EX-POLICY-1 早在 v19.212 就退役**
(豁免對象 `services/allocation_simulator.py` 整檔 866 LOC 拔毒)。
= 拿一個**已經不存在的授權**替自己豁免掉一條現行規則。這與同期抓到的
`quick_merge.sh`(拿不存在的授權繞過 PR)是同一型失效模式。

## 判定規則(刻意寫得可機械檢查,不猜語意)

「這段引用到底是不是在當授權用」無法用測試判斷,所以改用一個**可遵守、可檢查**的代理:

    production code 提到一個已退役的例外 ID 時,**同一行**必須帶退役標記
    (退役 / 撤銷 / 失效 / 已刪除 / 避免重蹈)。

正面範本 `shared/regime_fit.py` 檔頭就是這樣寫的:
「**不硬編 % 配置矩陣**(§-1/§1;**專案已退役** allocation_simulator EX-POLICY-1)」
—— 標明已退役,而且是把它當**反面前例**引用,不是當豁免。

⚠️ 這條規則**擋不住**「同一行既寫了『退役』又照樣拿它當豁免」這種刻意規避 ——
它擋的是**無意識沿用**(本次抓到的那兩處正是),那才是實際發生過的失效模式。

## 退役清單從哪來

**不寫死在測試裡** —— 直接從憲法主檔 §8.2.A 例外表抽:第一格被 `~~ ~~` 包起來的 = 退役。
憲法改一次,守衛自動跟著改;人工同步一份名單正是 §8.2.A.0 規則 3 點名的失效模式。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_CONSTITUTION = _REPO / "CLAUDE.md"
_SELF = Path(__file__).resolve()

# 引用退役 ID 時同一行必須出現其一。刻意**很短** —— 清單越長,規避越容易。
# 兩個非字面「退役」的收錄理由,據實寫出(不是隨手加寬):
#   - 「避免重蹈」:既有 code(services/fund_service.py)用它把退役例外當**反面前例**引,
#     語意正確,不收就是誤殺。
#   - 「升級」:本 repo 的退役路徑之一就叫「升級退役」(憲法主檔 §8.2.A 對 EX-L1ORCH-1
#     的原文是「v19.240 R8 升級退役」),寫「EX-L1ORCH-1 升級」是在描述**例外被拿掉**,
#     不是在主張它還有效。
# ⚠️ 代價據實記:這兩個詞比「退役」寬,理論上可被拿來規避。守衛擋的是**無意識沿用**
#   (實際發生過的那種),不是刻意規避 —— 刻意規避得靠稽核,不是靠 grep。
_RETIREMENT_MARKERS: tuple[str, ...] = (
    "退役", "撤銷", "失效", "已刪除", "避免重蹈", "升級",
)

_EX_ID = re.compile(r"EX-[A-Z0-9]+(?:-[A-Z0-9]+)*")
_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__",
              ".pytest_cache", "site-packages", "scratchpad"}


# ══════════════════════════════════════════════════════════════
# 純函式(測試自己也用同一條路徑做突變測試 —— 不是兩套邏輯)
# ══════════════════════════════════════════════════════════════
def parse_exception_ids(md_text: str) -> tuple[set[str], set[str]]:
    """憲法主檔全文 → (已退役 ID, 生效中 ID)。

    只看 markdown 表格列的**第一格**(ID 欄)。整列刪除線的寫法是
    `| ~~**EX-POLICY-1**~~(v19.212 ... 退役) | ...`,故判定為「第一格裡該 ID
    被一對 `~~` 夾住」。
    """
    retired: set[str] = set()
    active: set[str] = set()
    for _line in md_text.splitlines():
        if not _line.lstrip().startswith("|"):
            continue
        _cell = _line.lstrip()[1:].split("|", 1)[0]
        for _id in set(_EX_ID.findall(_cell)):
            _struck = re.search(r"~~[^~]*" + re.escape(_id) + r"[^~]*~~", _cell)
            (retired if _struck else active).add(_id)
    # 同一 ID 若兩種寫法都出現過,以「退役」為準(從嚴)
    return retired, active - retired


def offending_lines(text: str, retired: set[str]) -> list[tuple[int, str]]:
    """回 [(行號, 行內容)] —— 引用了退役 ID 卻沒帶退役標記的行。"""
    _bad: list[tuple[int, str]] = []
    for _n, _line in enumerate(text.splitlines(), start=1):
        _hits = {_i for _i in _EX_ID.findall(_line) if _i in retired}
        if _hits and not any(_m in _line for _m in _RETIREMENT_MARKERS):
            _bad.append((_n, _line.strip()))
    return _bad


def _python_sources() -> list[Path]:
    _out = []
    for _p in _REPO.rglob("*.py"):
        if any(_part in _SKIP_DIRS for _part in _p.parts):
            continue
        if _p.resolve() == _SELF:          # 本檔必然含退役 ID(突變測試的素材)
            continue
        _out.append(_p)
    return sorted(_out)


@pytest.fixture(scope="module")
def retired_ids() -> set[str]:
    _retired, _active = parse_exception_ids(_CONSTITUTION.read_text(encoding="utf-8"))
    return _retired


# ══════════════════════════════════════════════════════════════
# 1. 反空轉:parser 壞掉時必須紅燈,不能安靜通過
# ══════════════════════════════════════════════════════════════
class TestParserLiveness:
    def test_known_retired_and_active_ids_are_parsed(self):
        """憲法表格格式一改,本測試就會整組失效(退役清單變空 → 掃描永遠 0 命中)。

        故釘住三個**已知事實**當金絲雀:EX-POLICY-1 / EX-L1ORCH-1 已退役、
        EX-CACHE-1 生效中。金絲雀死掉 = parser 需要更新,不是「repo 變乾淨了」。
        """
        _retired, _active = parse_exception_ids(
            _CONSTITUTION.read_text(encoding="utf-8"))
        assert "EX-POLICY-1" in _retired, (
            f"parser 沒抓到 EX-POLICY-1 已退役 —— 憲法 §8.2.A 表格格式可能變了。"
            f"目前解析結果 retired={sorted(_retired)} active={sorted(_active)}")
        assert "EX-L1ORCH-1" in _retired, f"retired={sorted(_retired)}"
        assert "EX-CACHE-1" in _active, f"active={sorted(_active)}"
        assert "EX-CACHE-1" not in _retired


# ══════════════════════════════════════════════════════════════
# 2. 本體:全 repo production code 掃描
# ══════════════════════════════════════════════════════════════
class TestNoRetiredExceptionCitedAsLiveAuthority:
    def test_repo_wide_scan(self, retired_ids):
        """**修正前必紅** —— `ui/helpers/macro/beginner_view.py` 兩處
        「不抽 SSOT;§8.2.A EX-POLICY-1 同理」既沒退役標記、又是拿它當豁免。"""
        _bad: list[str] = []
        for _p in _python_sources():
            _rel = _p.relative_to(_REPO)
            for _n, _line in offending_lines(
                    _p.read_text(encoding="utf-8", errors="replace"), retired_ids):
                _bad.append(f"{_rel}:{_n}: {_line}")
        assert not _bad, (
            "引用了已退役的 §8.2.A 例外 ID 卻沒標明它已退役 —— 這是憲法主檔 §8.2.A "
            "末句禁止的「未經登錄的軟例外」。\n"
            "改法:要嘛改引用真正成立的依據,要嘛比照 shared/regime_fit.py 明寫「已退役」"
            "並且只當反面前例用。\n命中:\n  " + "\n  ".join(_bad))

    def test_regime_fit_is_the_reference_style(self, retired_ids):
        """正面範本本身必須通過 —— 它若通不過,代表規則訂得不可遵守。"""
        _txt = (_REPO / "shared" / "regime_fit.py").read_text(encoding="utf-8")
        assert "EX-POLICY-1" in _txt, "範本檔已改寫,本測試需重挑範本"
        assert offending_lines(_txt, retired_ids) == []


# ══════════════════════════════════════════════════════════════
# 3. 突變測試:把病放回去,守衛必須轉紅
# ══════════════════════════════════════════════════════════════
class TestMutation:
    def test_reintroducing_the_bad_citation_is_caught(self, retired_ids):
        """把 beginner_view 修正前的那一行原文餵回同一條檢查路徑 → 必須被抓。"""
        _relapse = ("# 閾值常數(本檔特用,非通用 metric — "
                    "不抽 SSOT;§8.2.A EX-POLICY-1 同理)\n")
        _hits = offending_lines(_relapse, retired_ids)
        assert _hits, "守衛沒抓到已知的假引用 —— 這道守衛是空的"
        assert _hits[0][0] == 1

    def test_second_bad_citation_is_caught(self, retired_ids):
        _relapse = "# 中期循環警戒閾值(本檔特用,§3.3 EX-POLICY-1 同理 — 教學語意門檻)\n"
        assert offending_lines(_relapse, retired_ids)

    def test_marker_makes_it_pass(self, retired_ids):
        """帶退役標記的引用(regime_fit 的寫法)不得誤殺。"""
        _ok = "# 不硬編 % 配置矩陣(§-1/§1;專案已退役 allocation_simulator EX-POLICY-1)\n"
        assert offending_lines(_ok, retired_ids) == []

    def test_active_exception_id_is_never_flagged(self, retired_ids):
        """生效中的例外照常可以引用,不需要任何標記 —— 否則守衛會擋到合法用法。"""
        _ok = "# EX-CRUD-1 允許 L3 直呼本地持久化 repository\n"
        assert offending_lines(_ok, retired_ids) == []
