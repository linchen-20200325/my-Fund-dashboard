"""④ 資產配置：**舊 ④ → 新 ④ 逐塊對照表**，以及守住它不腐爛的機器規則。

這一份在守什麼（先講清楚，它跟 `test_wf04_portfolio_skeleton.py` 不重疊）
----------------------------------------------------------------------
骨架守衛問的是「**新頁畫對了沒**」；本檔問的是**另一個方向**的問題：

    **舊 ④ 身上每一塊東西，在新 ④ 都有人記得它嗎？**

⭐ **本檔存在的理由是病史，不是儀式。** 五分頁重構前兩次切換（① 與 ②）的事故
都不是「新頁畫錯」，而是「**某個舊區塊沒有人記得它存在**」——
沒有人記得的東西不會有人去接，也不會有人去畫灰，它就**無聲消失**。
一份寫在 PR 描述裡的對照表擋不住這個：PR 會被合併掉，表不會被重跑。
→ 故本檔把那張表**寫成常數**（:data:`OLD_TAB4_INVENTORY`），
  再讓 :func:`test_every_old_block_is_accounted_for` 每次 CI 都重掃一次舊檔比對。
  **舊 ④ 一旦長出第 12 個區塊而沒有人登記，本檔當場轉紅。**

⛔ **本檔不驗「處置對不對」，只驗「有沒有人記得」。**
   `已委派` 那幾筆對不對是骨架守衛的事；`待客戶裁決` 那幾筆對不對是客戶的事。
   本檔只擋一件事：**漏掉**。

⚠️ 這道守衛看得見什麼、看不見什麼（照實寫，不要讀成「掃乾淨了」）
------------------------------------------------------------------
**看得見**

* `render_portfolio_tab()` 內以 ``X = st.container()`` 宣告的**版面 slot**
  （舊 ④ 既有的慣例：建立順序＝顯示順序、``with`` 順序＝執行順序，
  該慣例就地寫在 `ui/tab3_portfolio.py` 的長註解裡）。
* 每個 slot 的 ``with`` 區塊內呼叫到的 ``render_*`` / ``_render_*`` 委派函式。

**看不見（已知缺口，逐條寫出來，不要當成保證）**

1. **不是用 `st.container()` 宣告的區塊。** 舊 ④ 若哪天改用 `st.columns()` 或
   直接裸寫，本掃描器看不到它。→ :func:`test_the_scanner_can_actually_see_things`
   是**正對照**，它會在掃描器變瞎的時候轉紅，但它擋不住「換一種寫法」。
2. **`with` 區塊內的 `if` 分支。** 本檔用 `ast.walk`，**不看可達性** ——
   一個永遠不會執行到的 `render_x()` 一樣會被登記。**寧可多記，不可漏記。**
3. **動態呼叫**（`getattr` / `importlib` / 別名再呼叫）本檔看不到。
4. ⭐ **本檔完全不知道「畫面上長什麼樣」。** 它讀的是 AST，不是渲染結果。
   一個 slot 可能在 production 恆為空（例如它的內容全被 `if` 擋掉），
   本檔仍會要求你登記它 —— 那是**刻意的**：登記的成本是一行，漏掉的成本是一個功能。

⚠️ **本檔由執行組單組產出，未經第二組獨立複驗**（`CLAUDE.md §-2` 規則 6）。
   :data:`OLD_TAB4_INVENTORY` 的 `disposition` 欄是**本組依既有文件判讀**的結果，
   **不是**每一筆都有人實跑驗過。逐筆的依據寫在 `evidence` 欄，**請據此打折信任**。
"""

from __future__ import annotations

import ast
import pathlib

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_OLD_TAB = _REPO / "ui" / "tab3_portfolio.py"
_ENTRY = "render_portfolio_tab"


# ══════════════════════════════════════════════════════════════════════
# 掃描器
# ══════════════════════════════════════════════════════════════════════

def _scan() -> dict[str, dict]:
    """舊 ④ 的版面 slot → 它宣告在哪、`with` 在哪、委派了哪些 render 函式。

    ⚠️ **`_ENTRY` 找不到就 `raise`，不是回空 dict**（`CLAUDE.md §1`）——
       回空 dict 會讓下游每一條斷言都**空集合通過**（vacuous pass），
       也就是掃描器指錯檔的那一天，整份守衛會安靜地全綠。
    """
    _tree = ast.parse(_OLD_TAB.read_text(encoding="utf-8"))
    _fn = next((n for n in ast.walk(_tree)
                if isinstance(n, ast.FunctionDef) and n.name == _ENTRY), None)
    if _fn is None:
        raise AssertionError(
            f"`{_OLD_TAB.relative_to(_REPO)}` 裡找不到 `{_ENTRY}()` —— "
            "掃描器指錯檔或該函式被改名了。**先修掃描器，不要放寬斷言。**")

    _slots: dict[str, dict] = {}
    for _n in ast.walk(_fn):
        if not isinstance(_n, ast.Assign) or not isinstance(_n.value, ast.Call):
            continue
        try:
            _callee = ast.unparse(_n.value.func)
        except Exception:                                    # pragma: no cover
            continue
        if _callee != "st.container":
            continue
        for _t in _n.targets:
            if isinstance(_t, ast.Name):
                _slots[_t.id] = {"declared": _n.lineno, "span": None, "helpers": set()}

    for _n in ast.walk(_fn):
        if not isinstance(_n, ast.With):
            continue
        for _item in _n.items:
            try:
                _name = ast.unparse(_item.context_expr)
            except Exception:                                # pragma: no cover
                continue
            if _name not in _slots:
                continue
            _slots[_name]["span"] = (_n.lineno, _n.end_lineno)
            for _sub in ast.walk(_n):
                if not isinstance(_sub, ast.Call):
                    continue
                try:
                    _base = ast.unparse(_sub.func).split(".")[-1]
                except Exception:                            # pragma: no cover
                    continue
                if _base.startswith(("render_", "_render_")):
                    _slots[_name]["helpers"].add(_base)
    return _slots


# ══════════════════════════════════════════════════════════════════════
# 對照表本體
# ══════════════════════════════════════════════════════════════════════

#: 允許出現在 `disposition` 欄的值。**五種，缺一不可，也不得自創第六種。**
#:
#: ⚠️ **`待客戶裁決` 這一格是本組新增的，派工單原本只給四種**
#: （`已委派` / `本批委派` / `刻意灰態` / `已由總管裁決搬走`）。
#: **必須新增的理由是實測出來的，不是偏好**：本批被指派的三件事
#: （保單升全寬、狀態列補第四格、三個子區塊升具名）
#: **逐字就是 PR #791 送給客戶、客戶尚未答覆的那幾題的推薦方案**
#: （#791 題一與題三；本組實測該 PR 仍 `state=open` / `draft=true` / `merged=false`、
#: **零則 comment**，且 `docs/wireframes/README.md` 的「客戶已拍板」表**查無此檔**）。
#: → 把它們記成 `本批委派` 會是**假的**；記成 `刻意灰態` 會**吃掉「還在等人回答」這個事實**。
#: **一張對照表最重要的功能是不說謊，所以寧可多一種狀態。**
DISPOSITIONS: frozenset[str] = frozenset({
    "已委派",              # 新 ④ 已經接上，`page_04` 現在就會渲染它
    "本批委派",            # 本批要接上的
    "刻意灰態",            # 新 ④ 明知道它存在、刻意畫灰，理由已寫進 `REASON_*`
    "已由總管裁決搬走",    # 依已拍板線框搬到別頁，④ 不再擁有它
    "待客戶裁決",          # 送出去了、還沒回來 —— **不得**當成上面任何一種
})

#: ⭐ **舊 ④ → 新 ④ 逐塊對照表。**
#:
#: 每一筆 = ``(slot, 區塊名, disposition, evidence)``。
#: `slot` 是舊 ④ 的版面容器變數名（掃描器認得的那個），
#: `evidence` 是**這個處置的依據**，寫成可以自己去查的東西。
#:
#: ⛔ **新增一筆之前先問：這是「我知道它去哪了」還是「我希望它去哪」？**
#:    後者一律寫 `待客戶裁決`。
OLD_TAB4_INVENTORY: tuple[tuple[str, str, str, str], ...] = (
    # ── 8 個頂層 slot ────────────────────────────────────────────────
    ("_sec_add", "➕ 加入與管理基金", "待客戶裁決",
     "ia Tab 04 未列；2026-09-05 總管裁決 (A)「線框是版面規範不是功能清單」保住它"
     "不會被砍，但同一條裁決的反面逐字寫著『不是授權在線框之外新增版面』。"
     "新 ④ 的空狀態目前指向它（`where_to_find('pf_add')`）。"),
    ("_sec_policy", "保單管理（Google Sheets CRUD）", "已由總管裁決搬走",
     "`policy-split-wireframe.html` 決定 A~F（客戶已拍板：『版面 OK，動工』）——"
     "『連線／授權』搬 ⑤『🔌 連線與帳號』，④ 只留保單列新增更新。"
     "實作 `ui/helpers/portfolio/policy_admin_section.py`，⑤ 端橋接 "
     "`ui/helpers/settings_diag/policy_admin_bridge.py`。"),
    ("_sec_overview", "（版面容器，本身無內容）", "已委派",
     "它只 `st.container()` 出 `_ov_core` / `_ov_warroom` / `_ov_group` 三個子 slot，"
     "自己不畫任何東西。三個子 slot 各自登記在下方。"),
    ("_sec_overlap", "🔬 持股重疊度診斷（T5 — 底層持股＋產業重疊度，按保單分組）",
     "已由總管裁決搬走",
     "ia Tab 04「這裡不放什麼」逐字：『診斷「哪裡有問題」→ 02』。"
     "⚠️ **實測補正（本組後續查證，與初判不同，據實留痕）**：② **確實**接上了同一支 SSOT "
     "`services/portfolio_service.py::calc_holdings_overlap`，"
     "但它渲染的是**「影子基金重疊」一張 1/3 卡**（`page_02_health` 三欄網格第三格），"
     "**不是**舊 ④ 這一塊的**按保單分組矩陣 ＋ 兩張 `st.dataframe`**。"
     "→ **計算搬走了，呈現沒有一比一搬走。** 那個差異是刻意縮編還是漏搬，**本組未查證**。"),
    ("_sec_switch", "🎯 換股顧問", "刻意灰態",
     "`page_04_portfolio.REASON_SWITCH`：撞既有唯一渲染點（`switch_advise_btn` 會 "
     "`DuplicateWidgetID`），且需要雲端選股池與逐檔基準線。"
     "另有 `tests/test_ia_switch_advisor_moved_to_portfolio.py` 釘住呼叫點恰好一個。"),
    ("_sec_ledger", "💼 持倉戰情（T7 帳本）＋ 費用與扣款", "刻意灰態",
     "`page_04_portfolio.REASON_LEDGER`：線框只給內容類型、沒給欄位規格，"
     "補一份等於自己發明，而欄位增減是客戶 gate。"
     "⚠️ 本批原被指派『把灰態指路改指舊頁入口』，**未做**，理由見 PR 描述。"),
    ("_sec_ai", "🤖 AI 摘要", "待客戶裁決",
     "`fund-wireframe-final.html` 有、ia Tab 04 未列。同 `_sec_add`，"
     "裁決 (A) 保住它不被砍，但沒有授權把它升成新 ④ 的區塊。"),
    ("_sec_raw", "🗂️ Raw data（核對數字來源）", "待客戶裁決",
     "同 `_sec_ai`。`fund-wireframe-final.html` 列在 ④ 最後、刻意不擋路。"),
    # ── 3 個 `_sec_overview` 底下的子 slot ───────────────────────────
    ("_ov_core", "📊 配置總覽（KPI 卡＋淨值成長模擬曲線）", "已委派",
     "核心／衛星那一半已由 `page_04_portfolio._render_mix()` 接上，走全站唯一真相 "
     "`ui/helpers/portfolio/allocation.py`。"
     "⚠️ **本 slot 底下另有三個子區塊處置不同**，見下方 `UNDECIDED_SUBBLOCKS`。"),
    ("_ov_warroom", "💱 FX 曝險摘要／智能戰情室", "已由總管裁決搬走",
     "⚠️ **這個 slot 底下三支 helper 的狀態互不相同，不要當成一塊讀**（實測）："
     "(1) `render_fund_checkup` → **已在 ② 的 `DELEGATED_ENTRIES` 內**"
     "（`ui.helpers.fund.checkup`）；"
     "(2) `render_mk_war_room`（波段觀測站）→ 客戶 2026-09-05 裁決『搬 ②，"
     "**排在該頁上線之後的獨立批次**』——**裁決有了、搬遷還沒做**，"
     "且 ② 自己的守衛目前**明文擋** `mk_dashboard` 的 import；"
     "(3) `render_hero_kpi_cards`（`ui/helpers/portfolio/health.py`，6 格 KPI）→ "
     "**本組在 ② 找不到它**；它是 **PR #791 題二**（『② 總分那一格』）的標的，"
     "**客戶尚未答覆**。"
     "→ 本列的 `disposition` 取 (1)(2) 的多數判定；**(3) 嚴格說仍懸著**，"
     "在此具名登記以免它從兩張表中間掉下去。"),
    ("_ov_group", "🗂️ 保單分組視圖", "待客戶裁決",
     "＝新 ④ 的 `BLOCK_POLICY`「保單與扣款標的」的資料來源。"
     "版面（3 欄摘要卡 vs 全寬明細表）為 PR #791 題一，客戶**尚未答覆**；"
     "`page_04_portfolio.py` 未決事項 (B) 逐字『硬性前置：動工前必須先有客戶裁決』。"),
)

#: ⭐ **PR #791 題三點名、客戶尚未答覆的三個子區塊。**
#:
#: 它們**不是** slot，是住在 slot 深處的 render 函式 —— 所以上面那張以 slot 為單位的
#: 表**掃不到它們**。#791 自己的更正 A 逐字記載了這個射程問題：
#: 「舊表述『**只有**組合績效需要你點頭』在自己的射程內是對的（射程＝頂層區塊），
#: **但射程寫在表頭、沒有寫在那句話裡**」。
#: → 故本檔把它們**單獨列一張表**，而不是塞進 slot 那張，免得重蹈同一個覆轍。
UNDECIDED_SUBBLOCKS: tuple[tuple[str, str, str], ...] = (
    ("render_portfolio_performance", "_sec_add",
     "📊 組合績效（年化報酬／σ／Sharpe／最大回撤＋逐檔貢獻）"),
    ("render_efficient_frontier", "_sec_add",
     "🎯 效率前緣診斷（教學・非建議）"),
    ("render_concentration_summary", "_ov_core",
     "穿透式持股集中度（把基金穿透合併，示警「你以為分散了」）"),
    ("render_sector_concentration_summary", "_ov_core",
     "產業集中度（同上，產業維度）"),
    ("render_macro_exposure_link", "_ov_core",
     "總經曝險聯動（① 的景氣位階接到組合上，大盤與我的配置之間唯一一條連線）"),
)


# ══════════════════════════════════════════════════════════════════════
# 正對照 —— 掃描器沒瞎
# ══════════════════════════════════════════════════════════════════════

def test_the_scanner_can_actually_see_things():
    """⭐ **正對照：先證明掃描器真的看得到東西，再去信它回報的「沒有遺漏」。**

    ⚠️ **這條為什麼排在最前面**：本檔其餘每一條斷言的形狀都是
    「掃到的東西 ⊆ 登記的東西」—— 那個形狀在**掃描器回空**的時候**恆真**。
    也就是說：掃描器壞掉的那一天，本檔會安靜地全綠，
    而它守的正是「不要安靜地漏掉東西」。**空掃就是最危險的那種綠燈。**

    本條釘三件事，任一不成立即紅：

    1. **輸入非空** —— 舊檔存在、`render_portfolio_tab()` 找得到。
    2. **掃到的 slot 數量下限** —— 至少 11 個。
    3. **具名錨點** —— 幾個已知一定存在的 slot 與 helper 必須真的被掃到。
       （只驗數量不夠：一個回傳 11 個垃圾字串的掃描器也能過第 2 關。）
    """
    assert _OLD_TAB.exists(), f"舊 ④ 不見了：{_OLD_TAB}"
    _slots = _scan()
    assert len(_slots) >= 11, (
        f"只掃到 {len(_slots)} 個版面 slot，預期至少 11 個 —— "
        "掃描器可能瞎了（舊 ④ 改用別的方式宣告區塊？）。\n"
        "⛔ **先修掃描器，不要調低這個數字。** 調低它等於把守衛關掉。\n"
        f"掃到的：{sorted(_slots)}")
    for _anchor in ("_sec_add", "_sec_ledger", "_ov_core", "_ov_group"):
        assert _anchor in _slots, (
            f"具名錨點 `{_anchor}` 沒被掃到 —— 掃描器看得到東西，但看的不是對的東西。\n"
            f"掃到的：{sorted(_slots)}")
    _all_helpers = set().union(*(_s["helpers"] for _s in _slots.values()))
    for _anchor in ("render_portfolio_performance", "render_t7_section",
                    "render_macro_exposure_link"):
        assert _anchor in _all_helpers, (
            f"具名 helper 錨點 `{_anchor}` 沒被掃到 —— "
            "委派掃描那一半是瞎的，`UNDECIDED_SUBBLOCKS` 的覆蓋檢查會空轉。\n"
            f"掃到的：{sorted(_all_helpers)}")


# ══════════════════════════════════════════════════════════════════════
# 覆蓋 —— 沒有人被忘記
# ══════════════════════════════════════════════════════════════════════

def test_every_old_block_is_accounted_for():
    """⭐ **舊 ④ 的每一個版面 slot，在對照表裡都要找得到。**

    這就是本檔的本體。紅了代表：**舊 ④ 長出一個沒有人登記的區塊。**

    **紅了要做什麼**：去 :data:`OLD_TAB4_INVENTORY` 補一筆，
    並誠實填 `disposition` —— 不知道它該去哪就填 `待客戶裁決`，
    **不要**為了讓測試變綠而隨手填 `刻意灰態`
    （那會讓下一個人以為有人想過這件事）。
    """
    _scanned = set(_scan())
    _registered = {_slot for _slot, *_ in OLD_TAB4_INVENTORY}
    _missing = sorted(_scanned - _registered)
    assert not _missing, (
        "舊 ④ 有版面 slot **沒有登記在對照表裡** —— 這正是前兩次切換事故的形狀"
        "（沒有人記得它存在 ⇒ 沒有人接、也沒有人畫灰 ⇒ 它無聲消失）：\n  "
        + "\n  ".join(_missing)
        + "\n\n→ 到 `OLD_TAB4_INVENTORY` 補一筆。不知道去哪就填 `待客戶裁決`。")


def test_the_inventory_has_no_phantom_entries():
    """反向：對照表裡**不得**有舊 ④ 已經沒有的 slot。

    ⚠️ 這條擋的是另一種腐爛：舊 ④ 拔掉了一塊，對照表卻還留著它 ——
    於是表上寫著「已委派」的東西**其實兩邊都不存在**，
    而讀表的人會以為那個功能還活著。
    """
    _scanned = set(_scan())
    _phantom = sorted({_slot for _slot, *_ in OLD_TAB4_INVENTORY} - _scanned)
    assert not _phantom, (
        "對照表登記了舊 ④ 已經不存在的 slot：\n  " + "\n  ".join(_phantom)
        + "\n→ 舊 ④ 拔掉它了嗎？拔掉的話這一筆要一起刪，不要留著假裝還在。")


def test_every_undecided_subblock_still_lives_where_the_table_says():
    """`UNDECIDED_SUBBLOCKS` 的每一筆，都要真的還在它宣稱的那個 slot 裡。

    ⚠️ **這條守的是 PR #791 題三那張表的有效性** —— 那三塊是送給客戶決定去留的，
    客戶回覆時我們必須還找得到它們。若舊 ④ 在等待期間把它們搬走了，
    本條會轉紅，提醒送出去的那張表已經過期。
    """
    _slots = _scan()
    _bad = []
    for _helper, _slot, _label in UNDECIDED_SUBBLOCKS:
        if _slot not in _slots:
            _bad.append(f"{_helper}：宣稱住在 `{_slot}`，但那個 slot 不存在了")
        elif _helper not in _slots[_slot]["helpers"]:
            _bad.append(
                f"{_helper}（{_label}）：宣稱住在 `{_slot}`，"
                f"但該 slot 現在只委派 {sorted(_slots[_slot]['helpers'])}")
    assert not _bad, (
        "送給客戶決定去留的子區塊，位置已經跟表上寫的不一樣了：\n  "
        + "\n  ".join(_bad)
        + "\n→ PR #791 題三那張表過期了，回覆進來之前要先更新。")


@pytest.mark.parametrize("slot,label,disposition,evidence", OLD_TAB4_INVENTORY)
def test_every_entry_is_filled_in_properly(slot: str, label: str,
                                           disposition: str, evidence: str):
    """每一筆都要有**合法的處置**與**非空的依據**。

    ⚠️ **`evidence` 不得留空**是刻意的：一筆沒有依據的處置，
    下一個人無從查證，只能選擇相信或整張表重做 —— 而重做的成本正是本檔要省掉的。
    """
    assert disposition in DISPOSITIONS, (
        f"`{slot}` 的處置 `{disposition}` 不在允許清單內：{sorted(DISPOSITIONS)}\n"
        "⛔ 不得自創第六種狀態；真的需要，先改 `DISPOSITIONS` 並在那裡寫清楚為什麼。")
    assert label.strip(), f"`{slot}` 沒有區塊名。"
    assert len(evidence.strip()) >= 20, (
        f"`{slot}` 的依據太短（{len(evidence.strip())} 字）——"
        "「依據」要能讓下一個人自己去查，不是一句『線框有寫』。")


def test_the_client_gated_entries_are_not_quietly_marked_done():
    """⭐ **本批被指派、但卡在客戶那一關的三件事，不得被記成「做完了」。**

    ## 這條為什麼要存在

    本批派工單逐字寫「總管已拍板」，而本組實測發現那三件事
    **逐字就是 PR #791 送給客戶、尚未答覆的推薦方案**。
    在客戶回覆之前，把它們記成 `已委派` / `本批委派` 會讓對照表**說謊**，
    而這張表存在的唯一理由就是不說謊。

    → 本條把三個相關 slot 釘在 `待客戶裁決`。

    ## ⚠️ 客戶回覆之後這條會擋路 —— 那時候**正解是改它，不是繞過它**

    客戶說「照 A 做」之後，把該筆改成 `本批委派`／`已委派`，
    **同時**把本條的 `_GATED` 清單一起改小。
    ⛔ **不要**因為它擋路就整條刪掉 —— 剩下的兩筆還需要它。
    """
    _GATED = {
        "_ov_group": "PR #791 題一（保單版面：3 欄摘要卡 vs 全寬明細表）",
        "_sec_add": "PR #791 題三（舊 ④ 頂層區塊去留）",
        "_sec_ai": "PR #791 題三（同上）",
    }
    _byslot = {_slot: _disp for _slot, _label, _disp, _ev in OLD_TAB4_INVENTORY}
    _bad = [f"`{_slot}` 被記成 `{_byslot.get(_slot)}`，但它卡在 {_why}"
            for _slot, _why in _GATED.items()
            if _byslot.get(_slot) != "待客戶裁決"]
    assert not _bad, (
        "有卡在客戶那一關的區塊被記成已處置：\n  " + "\n  ".join(_bad)
        + "\n\n客戶真的回覆了嗎？回覆了就連同本條的 `_GATED` 一起改；"
        "還沒回覆就把它改回 `待客戶裁決`。")
