"""⑥ `[新] 💊 持倉體檢` 的 **🧾 ① 結論層** —— 守「有沒有回答問題」，不是「有沒有更多欄位」。

本檔存在的理由（客戶原話，兩句要合起來讀）
------------------------------------------
> 「新的 UI 設計我不滿意，少了很多資訊，**無法判斷這檔基金好不好，配息金額**，
>   搭配組合以及標的是否需要調整，這些都沒有」
> 「我覺得**舊 UI 資訊太多**，才希望總管 AI 重新設計，去重複然後讓新手也能看得懂的方式設計」

⇒ **他要的不是更多欄位，是看一眼就知道「所以呢」。**
盤點結論：② 的**數字都在**（逐檔表 9 欄有 8 欄是真資料），**缺的是有人下判定**。

⛔ **因此本檔有一條「反向」守衛**（:func:`test_the_conclusion_stays_two_sentences_not_a_second_table`）：
   它擋的不是「少做」，是**做過頭** —— 把密度搬回來等於推翻客戶要求重新設計的理由。
   **兩個方向都是失敗**，所以兩個方向都要有機器規則。

三種證據分開標，⛔ 不混寫
-------------------------
本檔的斷言**全部是執行期的**（要 streamlit ＋ 假 `st` 錄一輪），也就是**只有 CI 跑得動**。
撰寫當下的本機環境**沒有** streamlit / pandas / pytest（且不得 `pip install`），
所以本檔在本機只做過 `ast.parse`；**「本機通過」這句話本檔一次都不會出現。**

與既有兩個測試檔的分工（⛔ 不重複、也不互相取代）
------------------------------------------------
- `tests/test_wf02_health_skeleton.py` —— 骨架、四大鐵律、委派名單、灰態理由。
  **本檔直接 import 它的假 streamlit 與 fixtures，不另抄一份**
  （該檔自己的 docstring 就地寫著「這裡**不要**再抄一份掃描邏輯：②③④ 三頁曾各自抄一份
  較弱的版本，三份同時漏掉同樣三條管道」——**抄第二份 harness 是本 repo 實證過的病**）。
- `tests/test_wf02_health_no_writes.py` —— 零寫入。
- **本檔** —— 只管結論層：**數字對不對、沒算進去的有沒有講出來、判不動有沒有獨立成一類、
  以及這一層有沒有偷偷長大。**
"""
from __future__ import annotations

import ast
import copy
import pathlib
import sys
from typing import Any

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from test_wf02_health_skeleton import _Rec, _fund, _render, _text  # noqa: E402

from ui.helpers.render_state import NOT_READY_MARK  # noqa: E402
from ui.helpers.story_nav import where_to_find  # noqa: E402
from ui.views.page_02_health import (  # noqa: E402
    CONCLUSION_HEADING,
    HEALTH_TABLE_COLUMNS,
    PRINCIPAL_HELP,
    _income_tally,
    _peer_verdicts,
    _uniq_by_code,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "ui" / "views" / "page_02_health.py"


# ══════════════════════════════════════════════════════════════════
# fixtures —— 逐檔「跟同類比」與「每月配息」各自需要的形狀
# ══════════════════════════════════════════════════════════════════
def _with_peer(fund: dict, peer_1y: float | None) -> dict:
    """替一檔補上 MoneyDJ 的「同類型平均」。

    ⚠️ 形狀不是本檔發明的：`ui/helpers/fund/checkup.py::_extract_peer_1y` 讀的是
    ``moneydj_raw.risk_metrics.peer_compare`` 底下**第一個名字含「平均」且含
    同／類／型／區域**的 key。抄錯形狀的話這些 fixture 會全部落進「資料不足」，
    而測試仍然「通過」—— 那是 fail-open，所以下面每一條都**正面斷言桶名**。
    """
    _f = copy.deepcopy(fund)
    if peer_1y is not None:
        _f["moneydj_raw"]["risk_metrics"] = {
            "peer_compare": {"同類型平均": {"1Y": peer_1y}}}
    return _f


def _with_money(fund: dict, invest_twd: float | None) -> dict:
    """替一檔補上使用者**實際投入**的金額（`portfolio_funds` 的既有欄位）。"""
    _f = copy.deepcopy(fund)
    if invest_twd is not None:
        _f["invest_twd"] = invest_twd
    return _f


#: 一份**四種判定都齊**的持股：贏／輸／平／判不動。
#: ⚠️ 超額報酬刻意跨過 `checkup._EXCESS_GOOD`(+2) 與 `_EXCESS_LAG`(−2) 兩側，
#:    而且**不是**壓在門檻上 —— 壓在門檻上的 fixture 分不出「≥」與「>」的突變。
WIN = _with_money(_with_peer(_fund("WIN", div=8.0, ret=10.0), 2.0), 1_200_000.0)
LAG = _with_money(_with_peer(_fund("LAG", div=6.0, ret=0.0), 5.0), 600_000.0)
MID = _with_money(_with_peer(_fund("MID", div=4.0, ret=3.0), 2.5), 0.0)
#: **判不動**：有報酬、沒有同類平均 → `_grade` 回 `(None, "⬜ 同類資料不足")`。
BLIND = _with_money(_fund("BLIND", div=5.0, ret=4.0), 300_000.0)

FOUR_WAY = [WIN, LAG, MID, BLIND]

#: **一檔都沒有填投入金額** —— 每月配息合計必須誠實留白，⛔ 不得印 0。
NO_MONEY = [_with_peer(_fund("NM1", div=8.0, ret=10.0), 2.0),
            _with_peer(_fund("NM2", div=6.0, ret=1.0), 5.0)]

#: 有金額、但**查不到年化配息率**（`div=None` 且 metrics 沒有 `annual_div_rate`）。
NO_RATE = [_with_money(_with_peer(_fund("NR", div=None, ret=6.0), 2.0), 900_000.0)]


def _expected_best_excess(funds: list[dict]) -> dict[str, float]:
    """`判定字 -> 該桶內最好的超額報酬`，**獨立於被測物算出來**。

    ⚠️ **刻意不從 `_peer_verdicts()` 的回傳值反推** —— 拿被測物的輸出當期望值，
    等於讓它自己替自己打分（排序反轉時兩邊會一起反轉，斷言恆真）。
    這裡直接走 `checkup` 的 SSOT 重算一次。
    """
    from ui.helpers.fund.checkup import _extract_peer_1y, _grade, _ret_1y_total

    _best: dict[str, float] = {}
    for _f in funds:
        _peer, _ = _extract_peer_1y(_f)
        _excess, _text = _grade(_ret_1y_total(_f), _peer)
        if _excess is None:
            continue
        _best[str(_text)] = max(_best.get(str(_text), float("-inf")), float(_excess))
    return _best


def _conclusion_slice(parts: list[str]) -> list[str]:
    """結論層那幾筆 —— 從 :data:`CONCLUSION_HEADING` 到第一個 `#### ` 之前。

    ⚠️ **切片而不是整頁比對**，理由與骨架檔 `_units()` 的長註同一條：
    **邊界一寬，鄰居的字就會替你通過。**（那份檔案是被兩輪突變逼到這個粒度的。）
    """
    _open = f"[markdown] {CONCLUSION_HEADING}"
    assert _open in parts, (
        f"畫面上找不到結論層的標題 {CONCLUSION_HEADING!r}。\n" + "\n".join(parts))
    _i = parts.index(_open)
    _out: list[str] = []
    for _p in parts[_i + 1:]:
        if _p.startswith("[markdown] #### "):
            break
        _out.append(_p)
    return _out


# ══════════════════════════════════════════════════════════════════
# ① 位置：結論在依據前面
# ══════════════════════════════════════════════════════════════════
def test_the_conclusion_comes_after_the_form_and_before_every_piece_of_evidence():
    """順序 ＝ 閱讀順序：條件 → **結論** → 依據。

    照 ① `ui/views/page_01_macro.py` 的既有四層（`### 🧾 ① 結論` → 卡片 →
    `### 🧾 ② 依據` → 詳細區）。**結論排到依據後面，等於沒有結論層** ——
    使用者要先滑過三張卡與一張九欄表才看得到答案，那正是客戶說「看不懂」的那件事。
    """
    _parts = _render(portfolio=FOUR_WAY)
    _head = _parts.index(f"[markdown] {CONCLUSION_HEADING}")
    _submit = next(_i for _i, _p in enumerate(_parts)
                   if _p.startswith("[form_submit_button]"))
    _first_block = next(_i for _i, _p in enumerate(_parts)
                        if _p.startswith("[markdown] #### "))
    assert _submit < _head < _first_block, (
        "結論層的位置不對（要在 Form 之後、第一個 `####` 依據區塊之前）。\n"
        f"  送出鈕 {_submit} / 結論 {_head} / 第一個依據區塊 {_first_block}")


def test_no_holdings_shows_no_conclusion_at_all():
    """沒有持倉 → **空狀態取代全部**，結論層一個字都不畫。

    ⛔ 對著一份空持倉印「每月配息合計 0 TWD」或「0 檔優等生」，
       是本頁 `_render_alert_cards` 已經寫死要防的那種假綠燈（§1）。
    """
    _all = _text(_render(portfolio=[]))
    assert CONCLUSION_HEADING not in _all, (
        "沒有持倉時仍畫出了結論層 —— 空狀態應**取代**它，不是疊在它上面。\n" + _all)


# ══════════════════════════════════════════════════════════════════
# ② 每月配息合計（TWD）—— 客戶點名的第二題
# ══════════════════════════════════════════════════════════════════
def test_the_monthly_income_total_is_the_sum_of_the_per_fund_ssot_numbers(monkeypatch):
    """合計 ＝ **SSOT 每檔給的 `monthly_div_twd` 相加**，本頁不自己重算。

    ⭐ **手法：把 SSOT 的回答換掉**（同骨架檔
    `test_the_numbers_on_the_cards_come_from_the_ssot` 的既有家風）。
    餵兩個**任何公式都湊不出來**的數字（1,234 / 4,321），畫面就必須印 5,555。

    ⛔ **不驗「有沒有出現『每月配息』這四個字」** —— 那種斷言在數字算錯時照樣全綠。
       本條驗的是**那個數字本身**，所以把加總改成別的運算（取最大、取第一筆、
       乘一個係數）**一律轉紅**。

    ⚠️ patch 的是 `ui.helpers.fund.checkup` 的**模組屬性**，不是本頁的名字 ——
       本頁對它是**函式內 lazy import**（頁 docstring 就地寫明理由 (b)：
       module 層 `from X import f` 會把函式綁進本頁命名空間，patch 就打不到）。
    """
    import ui.helpers.fund.checkup as _ck

    _fake = {"WIN": 1_234.0, "LAG": 4_321.0}

    def _stub(fund: dict) -> dict[str, Any]:
        return {"monthly_div_twd": _fake[str(fund.get("code"))],
                "invest_twd": 1.0, "adr": 1.0}

    monkeypatch.setattr(_ck, "_compute_fund_health_kpis", _stub)
    _body = "\n".join(_conclusion_slice(_render(portfolio=[WIN, LAG])))
    assert "5,555" in _body, (
        "每月配息合計不等於 SSOT 逐檔數字之和（1,234 ＋ 4,321 ＝ 5,555）。\n"
        "⛔ 這個數字必須是**加總**，不是取最大、取第一筆、或本頁自己重算一次公式。\n"
        + _body)
    assert "2 檔" in _body, (
        "沒有說清楚這個合計是由**幾檔**加出來的 —— "
        "少了分母，使用者無從判斷它涵不涵蓋他手上全部的東西。\n" + _body)


def test_the_income_line_uses_each_funds_real_amount_not_a_flat_principal():
    """公式吃的是**各檔實際 `invest_twd`**，⛔ 不是「假設每檔都投入 100 萬」。

    `WIN` 投入 1,200,000 × 年化 8% ÷ 12 ＝ **8,000**；
    `LAG` 投入 600,000 × 6% ÷ 12 ＝ **3,000** ⇒ 合計 **11,000**。
    ⚠️ 若有人把它接到 `_principal_twd()`（齊頭 100 萬），
       同一組 fixture 會變成 6,667 ＋ 5,000 ＝ 11,667 ——
       **數字仍然「看起來合理」，但那是另一個問題的答案**（§1）。
       兩個數字刻意不接近，就是為了讓這顆突變殺得死。
    """
    _t = _income_tally([WIN, LAG])
    assert _t["counted"] == 2 and _t["monthly_twd"] == pytest.approx(11_000.0), (
        "每月配息合計沒有走各檔實際投入金額。\n"
        f"  實際：{_t}\n"
        "  期望：WIN 1,200,000×8%/12 ＝ 8,000；LAG 600,000×6%/12 ＝ 3,000；合計 11,000")
    _body = "\n".join(_conclusion_slice(_render(portfolio=[WIN, LAG])))
    assert "11,000" in _body, f"畫面上沒有印出合計 11,000 TWD。\n{_body}"

    # ⭐ **X2（2026-09-08 稽核）：主句本身不得說謊，不是只驗子字串。**
    #    稽核實測：把主句改成「已涵蓋你手上全部 N 檔」而附註仍誠實 → **全綠**，
    #    因為斷言只比對 `11,000` / `2 檔` 這種子字串。**主句與附註可以互相矛盾。**
    #    這裡改成正反兩面都釘：有東西沒算進去時**不得**宣稱「全部／都」。
    _left_out_funds = [WIN, LAG, _with_peer(_fund("NM", div=8.0, ret=3.0), 2.0)]
    _t2 = _income_tally(_left_out_funds)
    assert _t2["counted"] == 2 and _t2["no_amount"] == 1, f"前提不成立：{_t2}"
    _body2 = "\n".join(_conclusion_slice(_render(portfolio=_left_out_funds)))
    assert "全部" not in _body2 and "都算進" not in _body2, (
        "有 1 檔沒算進合計，主句卻宣稱涵蓋全部 —— 主句與附註互相矛盾（§1）。\n" + _body2)
    assert "依這 2 檔" in _body2, (
        "主句沒有說清楚這個合計是由**幾檔**加出來的（應為 2 檔，共 3 檔）。\n" + _body2)


def test_funds_left_out_of_the_income_total_are_named_by_reason():
    """⭐ **沒算進去的必須講出來，而且兩種原因要分開講。**

    ``monthly_div_twd`` 是 None 有兩個原因，**下一步完全不同**：

    - **沒填投入金額** → 使用者**可以去補**（④ 加入與管理基金）
    - **查不到配息率** → 使用者**補不了**，那是上游沒抓到

    併成一句「N 檔資料不足」等於把**唯一可行動的那個原因**蓋掉。
    ⛔ 更不准的是**默默漏掉**：那個合計會被讀成「這就是我全部的配息」。
    """
    # ⭐ **fixture 刻意「不對稱」（2 / 1），這是被一顆存活的突變逼出來的。**
    #    2026-09-08 獨立稽核實測：舊 fixture 是 `(counted, no_amount, no_rate) == (1, 1, 1)`，
    #    把 `_income_tally` 那兩個分支**對調**之後三個數字一模一樣、兩句附註也都還在
    #    ⇒ **141 次執行全綠**。也就是「哪個原因對應哪個數字」原本零守衛。
    #    ⛔ 後果不是排版難看：使用者會被叫去補一個他**早就填好**的欄位，
    #       而真正的原因（抓不到配息率）被蓋掉 —— 正是 `_income_tally` docstring
    #       自己說要防的那件事。
    _funds = [
        WIN,                                                    # counted
        _with_peer(_fund("NM1", div=8.0, ret=3.0), 2.0),        # 沒填金額 ①
        _with_peer(_fund("NM2", div=8.0, ret=3.0), 2.0),        # 沒填金額 ②
        NO_RATE[0],                                             # 有金額、查不到配息率
    ]
    _t = _income_tally(_funds)
    assert (_t["counted"], _t["no_amount"], _t["no_rate"]) == (1, 2, 1), (
        f"三種落點沒有分開（期望 counted=1 / no_amount=2 / no_rate=1）：{_t}")
    _body = "\n".join(_conclusion_slice(_render(portfolio=_funds)))
    # ⛔ 數字與標籤必須**綁在一起**驗；分開驗等於沒驗（那正是舊版存活的突變）。
    assert "2 檔沒有填投入金額" in _body, (
        "「沒填投入金額」那一類的**檔數不對或標籤接錯**（應為 2 檔）。\n" + _body)
    assert "1 檔查不到配息率" in _body, (
        "「查不到配息率」那一類的**檔數不對或標籤接錯**（應為 1 檔）。\n" + _body)
    assert "1 檔沒有填投入金額" not in _body and "2 檔查不到配息率" not in _body, (
        "兩個原因的標籤對調了 —— 使用者會被叫去補一個他早就填好的欄位。\n" + _body)


def test_the_income_line_goes_grey_instead_of_printing_a_zero():
    """一檔都算不出來 → **誠實留白 ＋ 說缺什麼 ＋ 指路**，⛔ 不得印「0 TWD」。

    「算不出來」與「一毛都沒領」在畫面上長得一模一樣、意思相反 ——
    本頁 `_render_alert_cards` 對「0 檔吃本金」已經寫死同一條規矩，這裡照同一個慣例。
    """
    _body = "\n".join(_conclusion_slice(_render(portfolio=NO_MONEY)))
    assert NOT_READY_MARK in _body, f"算不出來時沒有退回灰態。\n{_body}"
    assert "0 TWD" not in _body, (
        "把「算不出來」印成了 0 TWD —— 那會被讀成「檢查過了，你一毛都沒領」。\n" + _body)
    assert where_to_find("pf_add") in _body, (
        "灰態沒有指路 —— 這一種灰**使用者真的補得了**（去 ④ 填投入金額），"
        "沒有指路等於把「消失」換成「灰色的消失」。\n" + _body)


# ══════════════════════════════════════════════════════════════════
# ③ 逐檔判定盤點 —— 客戶點名的第一題
# ══════════════════════════════════════════════════════════════════
def test_the_verdict_tally_counts_each_bucket_from_the_ssot_grade():
    """四種落點各自數對：贏／輸／平各 1 檔，**判不動另計 1 檔**。

    判準完全走 `ui.helpers.fund.checkup._grade`（＝閘門後那張基金體檢表
    「體檢判定」欄用的同一支），本頁**沒有自己定義任何門檻**。
    """
    _judged, _unjudged = _peer_verdicts(FOUR_WAY)
    assert dict(_judged) and sum(_c for _, _c in _judged) == 3, (
        f"判得動的應為 3 檔（贏／輸／平各 1）：{_judged}")
    assert sum(_c for _, _c in _unjudged) == 1, (
        f"判不動的應為 1 檔（BLIND 沒有同類平均）：{_unjudged}")
    # ⭐ **X3（2026-09-08 稽核）：排序反轉原本不會轉紅。**
    #    舊斷言是 `_judged[0][0] != _judged[-1][0]` —— 只要有兩個以上的桶就恆真，
    #    **近乎空轉**；稽核把排序反轉過來，測試照樣全綠。
    #    docstring 明寫「好消息在前」，那就要真的驗它。
    _order_texts = [_t for _t, _ in _judged]
    _by_best = [_t for _t, _ in sorted(
        _expected_best_excess(FOUR_WAY).items(), key=lambda _kv: -_kv[1])]
    assert _order_texts == _by_best, (
        "判得動的桶沒有依「桶內最好的超額報酬」由大到小排 —— "
        f"docstring 說好消息在前。\n  實際：{_order_texts}\n  應為：{_by_best}")
    _body = "\n".join(_conclusion_slice(_render(portfolio=FOUR_WAY)))
    assert "這 4 檔裡" in _body, f"沒有講出分母（手上總共幾檔）。\n{_body}"


def test_a_fund_we_cannot_judge_is_counted_as_undecided_not_as_fine():
    """⭐⭐ **「資料不足」必須是獨立一類，⛔ 不得併進「沒問題」。**

    本頁對吃本金已經寫死同一條規矩（`_render_alert_cards` 逐字：
    「**無法判定（不是判定為沒有吃本金）**」）。這裡照同一個慣例。

    ⚠️ 本條用的是**只有一檔判得動、三檔判不動**的極端輸入 —— 若有人把判不動的
       併進任何一個判得動的桶，那個桶的數字會從 1 變成 4，**當場轉紅**。
    """
    _funds = [WIN,
              _with_money(_fund("B1", div=5.0, ret=4.0), 100_000.0),
              _with_money(_fund("B2", div=5.0, ret=4.0), 100_000.0),
              _with_money(_fund("B3", div=5.0, ret=4.0), 100_000.0)]
    _judged, _unjudged = _peer_verdicts(_funds)
    assert [_c for _, _c in _judged] == [1], (
        f"判不動的被併進了判得動的桶：{_judged}")
    assert sum(_c for _, _c in _unjudged) == 3, f"判不動的沒有獨立計數：{_unjudged}"

    _body = "\n".join(_conclusion_slice(_render(portfolio=_funds)))
    assert "3 檔" in _body and NOT_READY_MARK in _body, (
        "畫面上沒有把那 3 檔「判不動」講出來。\n" + _body)
    assert "未判定 ≠ 沒問題" in _body, (
        "沒有點破「未判定 ≠ 沒問題」—— 少了這半句，使用者會把留白讀成安全。\n" + _body)


def test_the_same_fund_across_two_policies_is_counted_once_in_the_conclusion():
    """⭐⭐ **裁決 2（2026-09-08 稽核 X8）：結論層的去重原本零守衛。**

    `portfolio_funds` 的主鍵是 `(policy_id, code)` —— **同一檔基金買在兩張保單就有兩筆**
    （`ui/helpers/portfolio/load.py::reconcile_funds_with_ledgers`）。

    **稽核實測**：把結論層的 `_uniq_by_code(...)` 拿掉 → **全綠**，
    而畫面會變成「這 **3** 檔裡…🏆 **2** 檔」，底下的逐檔表卻說「共 **1** 檔」。
    ⛔ 那正是 `_uniq_by_code` 自己 docstring 點名要防的
    「**一個看不出來的錯誤數字**」（`CLAUDE.md §1`）——
    配息合計更嚴重：**同一筆錢會被加兩次**。

    本條兩半都釘（缺任一半，突變就會活）：
      (a) **計數**：兩筆同 code 只能算一檔；
      (b) **金額**：合計不得因為重複而變成兩倍。
    """
    _dup = [dict(WIN, policy_id="P1"), dict(WIN, policy_id="P2")]
    assert len({_f["code"] for _f in _dup}) == 1, "前提：這兩筆是同一檔基金。"

    # (a) 計數 —— 判定盤點只能看見一檔
    _judged, _unjudged = _peer_verdicts(_uniq_by_code(_dup))
    _seen = sum(_c for _, _c in _judged) + sum(_c for _, _c in _unjudged)
    assert _seen == 1, f"同一檔基金跨兩張保單被算成 {_seen} 檔：{_judged} {_unjudged}"

    # (b) 金額 —— 合計不得翻倍
    _t = _income_tally(_uniq_by_code(_dup))
    assert _t["counted"] == 1 and _t["monthly_twd"] == pytest.approx(8_000.0), (
        f"配息合計把同一筆錢加了兩次（應為 1 檔 / 8,000）：{_t}")

    # (c) 端到端 —— 畫面上講的是「1 檔」，不是「2 檔」
    _body = "\n".join(_conclusion_slice(_render(portfolio=_dup)))
    assert "這 1 檔裡" in _body, (
        "畫面上的分母把同一檔基金算了兩次 —— 使用者看不出來，但每個數字都會偏。\n" + _body)
    assert "8,000" in _body, f"畫面上的配息合計不是 8,000（重複加總？）。\n{_body}"

    # (d) **靜態的那一半 —— 這一半是被一顆存活的突變逼出來的，留痕。**
    #     本組先寫了 (a)(b)(c)，然後在本機跑突變「把 `_render_conclusion` 裡的
    #     `_uniq_by_code(...)` 拿掉」—— (a)(b) **抓不到**（它們自己就先呼叫了去重），
    #     (c) 抓得到但**本機跑不動**（要 streamlit）。
    #     ⇒ 只有 (a)(b)(c) 的話，這條守衛在本機是「看起來有守、其實驗不到」。
    #     本半用 AST 直接釘住**餵給兩句結論的到底是不是去重過的東西**，
    #     於是**本機與 CI 都殺得死**這顆突變。
    _fn = next(_n for _n in ast.walk(ast.parse(SRC.read_text(encoding="utf-8")))
               if isinstance(_n, ast.FunctionDef) and _n.name == "_render_conclusion")
    _src = ast.unparse(_fn)
    assert "_uniq_by_code(" in _src, (
        "`_render_conclusion()` 沒有對持股去重 —— `portfolio_funds` 的主鍵是 "
        "`(policy_id, code)`，同一檔基金買在兩張保單就會被算兩次，"
        "而**配息合計會把同一筆錢加兩次**（`CLAUDE.md §1`：看不出來的錯誤數字）。\n"
        + _src)


def test_every_fund_is_accounted_for_in_both_conclusions():
    """⛔ **兩句結論的分類數字都必須加回持股總數** —— 一檔都不准無聲消失。

    ⚠️ 這條擋的是最便宜也最貴的一種退化：`try/except` 之後 `continue`。
       畫面不會壞、數字看起來也對，只是**分母悄悄變小**了。
    """
    _t = _income_tally(FOUR_WAY)
    assert _t["counted"] + _t["no_amount"] + _t["no_rate"] == len(FOUR_WAY), (
        f"配息合計的分類加不回 {len(FOUR_WAY)} 檔：{_t}")
    _judged, _unjudged = _peer_verdicts(FOUR_WAY)
    _seen = sum(_c for _, _c in _judged) + sum(_c for _, _c in _unjudged)
    assert _seen == len(FOUR_WAY), (
        f"逐檔判定的分類加不回 {len(FOUR_WAY)} 檔：judged={_judged} unjudged={_unjudged}")


def test_the_page_never_hardcodes_the_ssot_verdict_words():
    """⛔ 桶名一律用 `_grade` **回傳的那句話**，本頁不准抄一份字面值。

    抄了之後 SSOT 一改措辭，**畫面與閘門後那張表就會各說各話**，而沒有任何東西會報錯
    （`CLAUDE.md §2.1`；本頁 `_shadow_formula` / `_eating_note` 都是同一個處置）。

    ⭐ **本條在 CI 上抓到過一次，抓的是我自己 —— 留痕，因為結論違反直覺。**
    2026-09-08：我在 `_peer_verdicts` 的 docstring 裡**引用上游那段程式碼時，
    連它的中文行末註解一起抄了進去**（`# 🏆 N 檔優等生` 之類）。
    那是**說明**、不是分桶邏輯，`8126 passed, 1 failed` 的那一顆就是它。

    ⛔ **修的是文字，不是這條守衛。** 兩個理由：
    1. **docstring 裡的抄本一樣會漂移** —— SSOT 改了措辭，這裡的說明就開始說謊，
       而讀者無從得知（`_shadow_formula` 的 docstring 早就把這個形狀寫下來了）。
    2. **「在合併壓力下放寬守衛」是本 repo 反覆吃虧的形狀**（`CLAUDE.md §-2`）。
       一條守衛第一次擋到自己人就被改精確，下一次它就不會擋到別人。

    ⇒ 現行寫法：引用上游程式碼時**只留 `startswith("🏆")` 這種 emoji 判準**，
    桶名一律用 emoji 指稱。**要講「哪一桶」，指 emoji，不要抄它的中文。**
    """
    _txt = SRC.read_text(encoding="utf-8")
    _bad = [_w for _w in ("優等生", "汰弱", "普通生") if _w in _txt]
    assert not _bad, (
        "本頁原始碼出現了 `_grade()` 的判定字面值：" + "、".join(_bad)
        + "\n分桶請直接拿它的回傳值當 key —— 抄一份就是第二份真相源。")


# ══════════════════════════════════════════════════════════════════
# ④ 反向守衛：這一層不准長大
# ══════════════════════════════════════════════════════════════════
def test_the_conclusion_stays_two_sentences_not_a_second_table():
    """⛔⛔ **本批最大的失敗模式是「過度修正」，這條專門擋它。**

    客戶第二句原話是「**舊 UI 資訊太多**，才希望總管 AI 重新設計」——
    在結論層加第三張表、第四張卡、或把舊 ② 的欄位搬回來，
    **就算每個數字都對，這一批也是失敗的**。

    射程：結論層（標題到第一個 `#### ` 之間）**不得出現任何表格／metric 卡**，
    且總筆數以「標題 ＋ 兩句 ＋ 各自最多一句附註」為上限。
    """
    _slice = _conclusion_slice(_render(portfolio=FOUR_WAY))
    _heavy = [_p for _p in _slice
              if _p.startswith(("[dataframe]", "[dataframe_row]", "[dataframe_rows]",
                                "[table]", "[metric]", "[metric_value]"))]
    assert not _heavy, (
        "結論層長出了表格／卡片：\n" + "\n".join(_heavy)
        + "\n⛔ 這一層只准放「一句話」等級的結論。要更多明細，下面已經有一張九欄表了。")
    assert len(_slice) <= 4, (
        f"結論層變成了 {len(_slice)} 筆（上限 4 ＝ 兩句結論 ＋ 各一句附註）：\n"
        + "\n".join(_slice)
        + "\n⛔ 客戶要的是「看一眼就知道所以呢」，不是第二份儀表板。")


def test_the_per_fund_table_still_shows_exactly_nine_columns():
    """⛔ 逐檔體檢表**一欄都不准加**（現行 9 欄）—— 結論是一句話，不是第 10 欄。

    ⚠️ **與骨架檔那條不重複**：那一條驗的是「九個欄名**都在**」（`in` 子字串），
       **一個第 10 欄它看不見**；本條驗的是**畫面上的表頭到底幾欄**。
       兩條一起才擋得住「加欄位」這個動作。
    """
    assert len(HEALTH_TABLE_COLUMNS) == 9
    _parts = _render(portfolio=FOUR_WAY)
    # ⚠️ 不用 `next(...)`：找不到時它拋 `StopIteration`，訊息完全看不出發生什麼事
    #    —— 而「表根本沒畫出來」正是本條要能講清楚的一種失敗。
    _headers = [_p for _p in _parts if _p.startswith("[dataframe] ")]
    assert _headers, (
        "畫面上沒有任何表格 —— 有持股時逐檔體檢表應該畫得出來。\n" + "\n".join(_parts))
    _cols = [_c for _c in _headers[0][len("[dataframe] "):].split("　") if _c]
    assert len(_cols) == 9, (
        f"畫面上的逐檔體檢表有 {len(_cols)} 欄，不是 9 欄：{_cols}\n"
        "⛔ 客戶說的是「舊 UI 資訊太多」—— 舊 ② 那張表約 85 欄，新頁收成 9 欄是對的。\n"
        "要回答「所以呢」請加**一句結論**，不是第 10 欄。")


# ══════════════════════════════════════════════════════════════════
# ⑤ 為什麼結論層可以住在委派區的 Checkbox Gate 前面
# ══════════════════════════════════════════════════════════════════
def test_the_conclusion_layer_draws_nothing_through_the_shared_helpers():
    """⭐ **這條證明的是「把數字提到閘門前」的前提：它不會撞。**

    ⚠️ **本 docstring 原寫「唯一需要證明的那件事」，已改掉** —— 那是一句我證不出來的
    全稱句（同一份 PR 已經因為兩句「⑥ 沒有 X」的全稱句被實測推翻兩次）。
    **實際上至少還有一件事要證：它不會多打一輪網路**（見下一條）。

    閘門（`DELEGATE_GATE_LABEL`）擋的是 `StreamlitDuplicateElementId`，
    而那個 id 是 **`st.plotly_chart` 每次呼叫都註冊**才產生的 ——
    **渲染才會撞，計算不會。** 本條把結論層用到的四支 helper 各跑一次，
    把 `ui.helpers.fund.checkup` 的 `st` 換成錄音機：**錄到任何一筆就紅。**

    ⛔ 哪天有人在這四支裡加一行 `st.caption(...)`（或改接一支會畫東西的 helper），
       本條會轉紅 —— 那一刻起「結論層在閘門前」就不再安全，**要處理的是那一行，
       不是把本條放寬**。
    """
    import ui.helpers.fund.checkup as _ck

    _rec = _Rec()
    _saved = _ck.st
    try:
        _ck.st = _rec
        for _f in FOUR_WAY:
            _ck._compute_fund_health_kpis(_f)
            _ck._grade(_ck._ret_1y_total(_f), _ck._extract_peer_1y(_f)[0])
    finally:
        _ck.st = _saved
    assert _rec.parts == [], (
        "結論層用到的 helper 畫了 Streamlit 元件：\n" + "\n".join(_rec.parts)
        + "\n⛔ 那會讓「放在閘門前」重新引發重複 element ID 的碰撞。")


def test_the_per_fund_number_is_gated_but_our_total_is_not():
    """⭐ **本批賴以成立的那個事實，用機器釘住 —— 因為它已經被講反過兩次。**

    ⛔ **「⑥ 沒有配息金額」是假的**：逐檔的月配息 TWD 早就存在
    （`checkup._compute_fund_health_kpis` → `_render_fund_health_card` 無條件渲染），
    而且吃的就是使用者各檔真實 `invest_twd`。本檔 2026-09-07 已經就地更正過同一個誤解。

    ✅ **成立的是另外兩件事，本條各釘一半**：

    1. **那個逐檔數字被閘門關著** —— `render_fund_checkup` 的呼叫點必須落在
       `_render_delegated_sections` 裡（那裡有 Checkbox Gate，預設不勾）。
    2. **我們這句合計沒有被關著** —— `_render_conclusion` 必須在
       `render_holdings_health` 裡、且排在 `_render_delegated_sections` **之前**。

    ⛔ **哪天有人把 `render_fund_checkup` 搬到閘門外，本條轉紅** —— 那一刻起
       「使用者看不到逐檔月配息」不再成立，這一層的說明文字**必須跟著改**，
       而不是讓一句在寫下當天為真的話安靜地變成假的。
    """
    _tree = ast.parse(SRC.read_text(encoding="utf-8"))
    _fns = {_n.name: _n for _n in ast.walk(_tree) if isinstance(_n, ast.FunctionDef)}

    # ── 一半：逐檔那個數字只能在委派區（＝閘門後）被畫出來 ──────────
    _hosts = [_name for _name, _fn in _fns.items()
              for _c in ast.walk(_fn)
              if isinstance(_c, ast.Call) and isinstance(_c.func, ast.Name)
              and _c.func.id == "render_fund_checkup"]
    assert _hosts == ["_render_delegated_sections"], (
        f"`render_fund_checkup` 的呼叫點跑出委派區了：{_hosts}\n"
        "⛔ 那裡才有 Checkbox Gate。搬出去等於本層說明文字（「它被閘門關著」）當場變成假的。")

    # ── 另一半：我們的合計在閘門**前面** ────────────────────────────
    # ⚠️ **這一段的第一版是錯的，留痕**：原本寫成
    #    `_c.func.id if isinstance(_c.func, ast.Name) else (_c.args[1].id …)`
    #    —— 但 `safe_section("結論", _render_conclusion)` 的 `_c.func` **本來就是**
    #    `ast.Name("safe_section")`，三元式因此**永遠走第一條**、`args` 那半從來沒被看過，
    #    於是 `_render_conclusion` 整個消失、`_order` 只剩一個元素。
    #    **本機實跑當場 `AssertionError`** —— 一條「順序守衛」看不到它要守的那一半，
    #    正是本 repo 反覆吃虧的 fail-open。修法是**兩者都收**，不是二選一。
    _entry = _fns["render_holdings_health"]
    _order: list[str] = []
    for _c in ast.walk(_entry):
        if not isinstance(_c, ast.Call) or not isinstance(_c.func, ast.Name):
            continue
        _order.append(_c.func.id)
        if len(_c.args) > 1 and isinstance(_c.args[1], ast.Name):
            _order.append(_c.args[1].id)      # `safe_section(label, fn)` 的那個 fn
    _order = [_x for _x in _order if _x in
              ("_render_conclusion", "_render_delegated_sections")]
    assert _order == ["_render_conclusion", "_render_delegated_sections"], (
        f"結論層與委派區的先後不對：{_order}\n"
        "結論必須在閘門**之前**畫 —— 那正是這一批要解決的問題（數字存在、但看不到）。")


def test_the_conclusion_layer_never_reaches_the_fx_fetcher():
    """⛔ 結論層的呼叫閉包裡**不得出現 `checkup._safe_fx`** —— 那支會打 `get_latest_fx`。

    ⚠️ 這條不是重複上一條。上一條問「會不會**畫**東西」，本條問「會不會**上網**」。
       `build_checkup_dataframe`（閘門後那張表用的）**會呼叫 `_safe_fx`**；
       若有人為了省事把結論層改接它，畫面照樣正確，但**每一次 rerun 都可能多打一輪匯率**
       —— 而那正是 Checkbox Gate 這種設計要避免的東西。

    ⛔ **2026-09-08 射程更正 ＋ 補上缺的那一半（獨立稽核指出）。**
    **舊版只走 `checkup.py` 的呼叫圖，完全不看 `page_02_health.py`** ——
    也就是它**守不到自己 docstring 講的那個情境**：稽核直接在本頁裡呼叫 `_safe_fx`，
    抓到它的是**另一條**守衛（`test_the_page_delegates_to_exactly_the_approved_entries`
    的精確集合相等），不是本條。**縱深防禦沒破，但那段 docstring 在說謊。**
    ⇒ 本條現在**兩邊都掃**：(a) `checkup.py` 那四支的呼叫閉包；
      (b) **本頁自己**有沒有出現 `_safe_fx` / `get_latest_fx`。
    ⚠️ **這是把射程補齊，不是放寬** —— 舊斷言一個字都沒有拿掉。
    """
    _tree = ast.parse((ROOT / "ui" / "helpers" / "fund" / "checkup.py")
                      .read_text(encoding="utf-8"))
    _fns = {_n.name: _n for _n in ast.walk(_tree) if isinstance(_n, ast.FunctionDef)}
    _seen: set[str] = set()
    _todo = ["_compute_fund_health_kpis", "_ret_1y_total", "_extract_peer_1y", "_grade"]
    while _todo:
        _name = _todo.pop()
        if _name in _seen or _name not in _fns:
            continue
        _seen.add(_name)
        for _c in ast.walk(_fns[_name]):
            if isinstance(_c, ast.Call) and isinstance(_c.func, ast.Name):
                _todo.append(_c.func.id)
    assert "_safe_fx" not in _seen, (
        f"結論層的呼叫閉包碰到了 `_safe_fx`（閉包：{sorted(_seen)}）—— "
        "那支會呼叫 `services.fund_service.get_latest_fx`，也就是每次 rerun 多一輪取數。")

    # ── (b) 補上的那一半：**本頁自己**不得直接碰匯率取數 ──────────────
    _page = ast.parse(SRC.read_text(encoding="utf-8"))
    _names: set[str] = set()
    for _n in ast.walk(_page):
        if isinstance(_n, ast.Call):
            if isinstance(_n.func, ast.Name):
                _names.add(_n.func.id)
            elif isinstance(_n.func, ast.Attribute):
                _names.add(_n.func.attr)
        elif isinstance(_n, ast.ImportFrom):
            _names.update(_a.name for _a in _n.names)
    _hit = sorted({_w for _w in ("_safe_fx", "get_latest_fx") if _w in _names})
    assert not _hit, (
        f"本頁直接碰了匯率取數：{_hit}\n"
        "⛔ 結論層跑在 Checkbox Gate **之前**，每一次 rerun 都會走到它 —— "
        "在那裡打匯率等於把重取數搬到頁面入口。")


# ══════════════════════════════════════════════════════════════════
# ⑥ 本金（TWD）：文案不得聲稱一個它沒有的消費者
# ══════════════════════════════════════════════════════════════════
#: 0 caller 時，畫面文案**必須**講清楚的兩件事（**使用者語言**，不是工程話）。
#: ⚠️ 2026-09-08 M3：舊值是 `("沒有任何區塊在讀", "實際")` —— 那是**內部術語**。
#: 事實沒錯，錯的是講給誰聽：客戶第二條驗收標準逐字是「讓**新手**也能看得懂」。
_HONEST_BITS = ("不影響", "實際投入")

#: ⛔ **畫面文案裡不准出現的工程術語。** 這一條是 M3 的**回歸防線** ——
#: 沒有它，下一個人（或下一輪的我）會很自然地把「0 caller」寫回 tooltip 裡，
#: 因為那在 repo 的 docstring 裡到處都是。**docstring 可以，`help=` 不行。**
_JARGON = ("caller", "接線", "SSOT", "session", "commit", "docstring", "AST")


def test_the_principal_help_never_claims_a_consumer_it_does_not_have():
    """⛔ **文案與接線綁在一起，兩個方向都 fail-closed。**

    現況（本頁 2026-09-07 就地登記的 AST 實測）：`_principal_twd()` **0 caller**，
    也就是使用者填了數字、按了套用，畫面什麼都不會變。
    而它舊的 `help=` 逐字寫著「所有基金都假設投入這個金額……」——
    **描述了一個本頁沒有發生的行為**，而且與本頁真正在用的東西（各檔實際
    `invest_twd`）**正好相反**。

    - **0 caller 時** → 文案必須誠實揭露「沒有人在讀它」。
    - **有 caller 之後** → 這條轉紅，逼那個人回來把文案改成真的。

    ⛔ **本條不是「允許它一直空轉」的許可證。** 這個 widget 的去留要動三條既有守衛
       （`test_the_principal_input_keeps_the_wireframe_numbers` /
        `..._is_read_from_the_applied_gate_not_derived` /
        `..._lives_inside_the_single_applied_form`），
       **為了拿掉一個 widget 去放寬守衛是本 repo 反覆吃虧的形狀** —— 已具名回報總管裁決。
    """
    _tree = ast.parse(SRC.read_text(encoding="utf-8"))
    _callers = [_n.lineno for _n in ast.walk(_tree)
                if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name)
                and _n.func.id == "_principal_twd"]
    # ⭐ **不論接線與否都成立的一半：畫面上不准講工程話（2026-09-08 M3）。**
    _bad_jargon = [_w for _w in _JARGON if _w in PRINCIPAL_HELP]
    assert not _bad_jargon, (
        "本金欄的 `help=` 出現了工程術語：" + "、".join(_bad_jargon)
        + "\n⛔ 那是使用者滑鼠停在輸入框上會看到的字。客戶第二條驗收標準逐字是"
          "「讓**新手**也能看得懂」。**工程細節寫在 docstring，不要寫在 `help=`。**"
        + f"\n目前文案：{PRINCIPAL_HELP}")

    if _callers:
        assert not any(_b in PRINCIPAL_HELP for _b in _HONEST_BITS[:1]), (
            f"`_principal_twd()` 現在有 {len(_callers)} 個呼叫點"
            f"（行 {_callers}），但 help 文案還寫著它「不影響上面任何一個數字」。\n"
            "接線之後請回來把文案改成真的 —— 一句在寫下當天為真的話，"
            "不會自己過期，它只會安靜地變成假的。")
        return
    for _b in _HONEST_BITS:
        assert _b in PRINCIPAL_HELP, (
            f"`_principal_twd()` 是 0 caller，但 help 文案沒有揭露這件事（缺「{_b}」）。\n"
            "⛔ 揭露要用**使用者語言**：他要知道的是「填了會不會影響上面的數字」，"
            "不是我們的接線狀態。\n"
            f"目前文案：{PRINCIPAL_HELP}")


def test_the_principal_help_is_actually_the_string_on_the_widget():
    """⛔ 上一條驗的是常數；本條驗**畫面上真的用了那個常數**。

    ⚠️ 少了這一半，把 `help=` 改回一句硬寫的字面值、只留常數沒人用，上一條照樣全綠。
    """
    _tree = ast.parse(SRC.read_text(encoding="utf-8"))
    _fn = next(_n for _n in ast.walk(_tree)
               if isinstance(_n, ast.FunctionDef) and _n.name == "_render_filter_form")
    _helps = [ast.unparse(_k.value) for _c in ast.walk(_fn)
              if isinstance(_c, ast.Call) and isinstance(_c.func, ast.Attribute)
              and _c.func.attr == "number_input"
              for _k in _c.keywords if _k.arg == "help"]
    assert "PRINCIPAL_HELP" in _helps, (
        f"本金 widget 的 `help=` 不是 `PRINCIPAL_HELP`：{_helps}")
