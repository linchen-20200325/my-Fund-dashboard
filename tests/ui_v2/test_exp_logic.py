# -*- coding: utf-8 -*-
"""標的探索（EXP）純邏輯測試。**不需要 streamlit**，系統直譯器跑得起來。

要跑起來：`pytest tests/ui_v2/test_exp_logic.py -q --noconftest`
（`--noconftest` 是因為 repo 根的 `tests/conftest.py` 會 import 舊 repo 的取數層。）

⚠️ **每一條都寫出它在驗 `44` 的哪一行判準。** 一條沒有正控的綠燈等於沒有檢查：
   凡是本檔宣稱「拿掉實作就會紅」的地方，本輪都**真的把實作拿掉跑過一次**，
   結果逐條記在本輪回報的突變總表裡。
"""

import hashlib
import inspect
import json
import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ui_v2.exp import fixtures, logic, theme  # noqa: E402

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_D44 = _ROOT / "docs" / "v2" / "44_fund_ui_ssot.md"


def _model(name, *, save_failed=False, **override):
    params = dict(fixtures.scenario_with(name, save_failed=save_failed))
    dataset = params.pop("dataset")
    params.update(override)
    return logic.build_page_model(dataset, save_failed=save_failed, **params)


def _every_case():
    for name in fixtures.ALL_SCENARIO_NAMES:
        for save_failed in fixtures.SAVE_FAIL_CHOICES:
            yield name, save_failed


# ═════════════════════ 一、分離與隔離 ═════════════════════


def test_logic與fixtures與theme都沒有import_streamlit或舊repo或網路():
    banned = (
        "import streamlit",
        "from ui.",
        "from services.",
        "from repositories.",
        "from shared.",
        "from infra.",
        "import fund_fetcher",
        "import requests",
        "import httpx",
        "import urllib",
        "import yfinance",
        "import gspread",
        "import feedparser",
        "import socket",
        "import subprocess",
        "from ui_v2.mkt",
        "from ui_v2.hld",
        "from ..mkt",
        "from ..hld",
    )
    files = [logic.__file__, fixtures.__file__, theme.__file__]
    assert len(files) == 3
    for path in files:
        source = pathlib.Path(path).read_text(encoding="utf-8")
        for word in banned:
            assert word not in source, (path, word)


def test_fixtures不import_logic_假資料不依賴判定層():
    source = pathlib.Path(fixtures.__file__).read_text(encoding="utf-8")
    assert "import logic" not in source
    assert "from . import" not in source


def test_44還是凍結的那一份():
    """`44` 在 2026-09-24 第二十輪解凍（落 `ALO-4` 那一枚導覽鈕用途改為去 Sheets 維護持倉與指派的裁示（2026-09-24）並把規則欄行末那筆用途矛盾的登記改為已裁結案、在該塊客戶裁示段補一句歷史註、並登記一筆新矛盾，只在既有行內擴寫、行數不變），改完重新凍結，下面的 md5 是那一輪改完後的新值。行號引用全靠內容比對，不靠行號 —— 但檔案本身要是那一份。"""
    digest = hashlib.md5(_D44.read_bytes()).hexdigest()
    assert digest == "b54020cda7aac68e16850336b0e98c63", digest
    assert len(_D44.read_text(encoding="utf-8").split("\n")) == 4260  # 4259 行 ＋ 末尾換行


# ═════════════════════ 二、逐字引文守衛 ═════════════════════

_QUOTE_SCAN_FILES = (
    "ui_v2/exp/logic.py",
    "ui_v2/exp/fixtures.py",
    "ui_v2/exp/theme.py",
    "ui_v2/exp/page.py",
    "ui_v2/app_exp.py",
)

# 「逐字」與它引進來的那個 `「` 之間，允許夾哪些字。
_QUOTE_CONNECTORS = set(" \t\r\n#：:是寫著引的為，,。－—-*~`＝=（(")

# ⚠️ **本表目前是空的，而且那是好事** —— 上列五個檔裡，每一句由「逐字」引進來的引文
#    都真的逐字對得上 `44`。留這個機制是為了**日後真的出現「逐字引別的東西」時有合法出口**
#    （例：某處寫「草稿逐字要求：『…』」—— 那是引草稿，不是引 `44`）。
# ⛔ 加進來的每一筆都必須寫出**它到底在引什麼** —— 一張沒有理由的豁免清單，
#    就是把「無法否證」從函式裡搬到字典裡。
_NOT_A_44_QUOTE: dict = {
    # ⛔ **這是這張豁免表的第一筆，而且它是被守衛自己逼出來的** ——
    #    我在 `logic.COLUMN_ORDER` 上方寫了「草稿 §H 的 `T-09` **逐字**是『可選欄位四項』」，
    #    守衛當場紅燈，因為那一句在 `44` 裡找不到。**它本來就不在 `44` 裡：那是引草稿。**
    #    （實測：把標籤剝乾淨之後，`ui_prototype_exp.html` 含這一句、`44` 不含。）
    "可選欄位**四項**": "引的是已拍板草稿 ui_prototype_exp.html §H 的 T-09，不是 44",
}

# 下限：五個檔裡由「逐字」引進來、而且**真的對得上 `44`** 的引文筆數。
# ⛔ **2026-09-24 就地更正：這裡原本寫「量測值 59」，而當時現場重跑是 62。**
#    一個寫在註解裡、又不會被任何東西檢查的量測值，**改一次程式就過期一次**。
#    **現在不寫那個數**（要知道現值，跑 `test_標了逐字的引文…` 看它的斷言訊息）；
#    下限只寫下限，並寫明它是怎麼挑的。
# ⛔ **2026-09-24 第二輪稽核：這個下限原本的理由是假的，而且是第三次寫錯同一段註解。**
#    舊理由宣稱「收窄成只認同一行會讓筆數掉下來，**下限 50 擋得住那一種**」。
#    **擋不住。本組實測（量測日 2026-09-24）**：
#      · 現況 verified = **66**（跨行起頭 **6** ＋ 同行起頭 **60**）
#      · 把連接字元表拿掉 `\n`（＝只認同一行）→ verified = **60**
#      · **60 > 50 ⇒ 下限完全不會紅。** 稽核量到 52、也 > 50，**結論一致：擋不住。**
#    ⚠️ **前兩次錯的是數字，這次錯的是結論** —— 一個「用下限擋收窄」的機制，
#    從一開始就不成立：收窄只掉 6 筆，而下限離現值有 16 筆的距離。
#
# ✅ **下限留著，但把它的職務寫對**：它是**粗篩**，只擋「抽取整個垮掉」那一種
#    （例如觸發詞打錯、檔案清單被清空 → verified 掉到個位數）。
#    **它擋不住、也不該被期待擋得住「少抓幾筆」那一種。**
# ⛔ **真正擋收窄的是另一條**：`test_跨行起頭的逐字引文真的被抓到_收窄成同一行會紅`
#    —— 它直接釘「跨行起頭」那 6 筆，收窄會讓它掉到 0，當場紅。
#    **用對的工具擋對的東西；不要靠把 50 調高來假裝有守。**
_MIN_VERIFIED_QUOTES = 50
# 跨行起頭的已驗證引文筆數下限（現值 6，量測日 2026-09-24）。留 3 的餘裕給正常退役。
_MIN_CROSS_LINE_QUOTES = 3


def _unstruck_text(text: str) -> str:
    """把**成對**的 `~~…~~` 之間的字挖掉（退役的紀錄不該紅燈）。

    ⛔ **2026-09-24 就地更正：上一版是一個「遇到 `~~` 就翻轉」的狀態機，遇到奇數個 `~~` 會吃掉檔案後半。**
    **本組實測（量測日 2026-09-24，修復前）**：當時 `test_exp_logic.py` 有**奇數**個 `~~`，
    舊寫法把本檔砍掉約 95%、「逐字」由 63 剩 7。
    ⚠️ **那組絕對數字今天已經量不出來了，刻意不留在這裡**：本檔每編一次就會漂。
    ⛔ **2026-09-24 第二輪稽核更正：上一版在這裡寫「今天重量是 24 個、偶數，兩種寫法結果相同」。**
    **稽核實測當時是 27、奇數 —— 那句話是假的，而且它推出的「還沒出事」也是假的。**
    ⛔ **而在修這一句的同一次編輯裡，它又自己過期了一次**：本段原本引用了那兩個字元的字面，
    刪掉之後本檔的計數與奇偶**當場再變一次**。
    ⇒ **所以這裡自本輪起一個計數都不寫**（要現值請現場量）。
    **這正是不能靠「檔案當下剛好是偶數」當護欄的實證** ——
    `test_落單的刪除線標記不會吃掉它後面的引文` **自己注入一個落單標記**，不看檔案的湊巧。
    ⚠️ 同 `CLAUDE.md` §-2.A 第 8 款：把掃描用的字串寫進文件，它就會自己命中。
    ⛔ **這正是不能靠「檔案現在剛好是偶數」當護欄的理由** —— 所以
    `test_落單的刪除線標記不會吃掉它後面的引文` **自己注入一個落單的 `~~`**，不看檔案當下的湊巧。
    ⚠️ 五個受檢的實作檔目前 `~~` 都是 0，所以**還沒出事** ——
    但只要有人在 `logic.py` 尾段放一個沒有配對的 `~~`，
    **它後面每一句逐字引文都會悄悄退出受檢集**，而守衛照樣綠。
    下限（現值見 `_MIN_VERIFIED_QUOTES`）只擋得住掉很多的那一種，擋不住掉一兩句。
    **現在改成只剝成對的那一段**：落單的 `~~` 原樣留著，不吃掉它後面的東西。
    """
    return re.sub(r"~~.*?~~", "", text, flags=re.DOTALL)


# ⛔ **登記（2026-09-24 第二輪稽核；潛在缺口，不是現行錯誤，本輪只登記）**：
#    `_flat44()` 只把 `44` 裡的刪除線**標記**剝掉，**被劃掉的字仍留在母體裡** ——
#    也就是拿 `44` 裡**已經退役的舊條文**當逐字引文，本守衛**會判它合法**。
#    稽核的正控：餵一句 `44` 裡真的被劃掉的舊條文進來 → **判為合法引文**。
#    ⚠️ **這個病本專案犯過一次**，記錄就在客戶拍板的那份草稿裡
#    （`ui_prototype_exp.html`：「**錯的是授權它的那句引文**」）。
#    ✅ **目前沒有一句踩到它**：稽核用不同演算法獨立重抽 116 句，落在劃線內的 **0**。
#    ⇒ **是潛在缺口，不是現行錯誤。** 本輪不動它的理由：修法要決定
#    「引一句已退役的條文算不算違規」——那是**`44` 沒有寫**的事，不該由本組順手定。
def _flat44(text: str) -> str:
    """比對前的正規化。三件事，每一件都有實測理由：

    1. 拿掉 markdown 強調（`**`／`` ` ``／`~~`／`*`／`_`）—— 引文常帶本檔自己的粗體。
    2. 拿掉全部空白 —— 引文會換行並加註解前綴。
    3. **`『』` 一律折成 `「」`** —— `44` 裡寫 `「對照」`，而本 repo 把它**巢狀**引在
       外層 `「…」` 之內時必須改寫成 `『對照』`，那是**排版必需**、不是竄改。
    """
    text = re.sub(r"\n\s*#\s*", "", text)
    text = text.replace("『", "「").replace("』", "」")
    return re.sub(r"\s+", "", re.sub(r"\*\*|~~|`|\*|_", "", text))


def _quotes_introduced_by_verbatim(text: str):
    """回 [(字元位置, 引文)]：**由「逐字」兩個字引進來的**那些 `「…」`。

    ⚠️ **為什麼是這個觸發條件**（三種都想過，經過寫在這裡免得下一個人再走一遍）：
      · **逐行**：引文與「逐字」可以**不在同一行**（本檔就有），會漏；
        而且把引文改壞時可能**連觸發詞一起改掉**，於是那一句從此不被檢查 ——
        **會被它要抓的那個編輯關掉的守衛，等於沒有守衛。**
      · **整個註解區塊**：會把區塊裡每一個普通強調引號都掃進來，豁免表會膨脹成幾十筆
        「這只是強調」，**雜訊會殺死守衛**。
      · **由「逐字」引進來**：觸發詞在引文**之外**，改壞引文不會把觸發關掉。

    ⛔ **射程要誠實**：本支只管「**宣告自己是逐字的**」那些引文。
    一句把改寫放進引號、**旁邊沒有寫「逐字」**的句子，本支**掃不到** —— 那是另一個問題。
    """
    out = []
    for match in re.finditer("逐字", text):
        j = match.end()
        while j < len(text) and j - match.end() <= 12 and text[j] in _QUOTE_CONNECTORS:
            j += 1
        if j >= len(text) or text[j] != "「":
            continue
        depth, k = 0, j
        while k < len(text):
            if text[k] == "「":
                depth += 1
            elif text[k] == "」":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        if k < len(text):
            out.append((match.start(), text[j + 1 : k]))
    return out


def _all_verbatim_quotes():
    out = []
    for rel in _QUOTE_SCAN_FILES:
        text = _unstruck_text((_ROOT / rel).read_text(encoding="utf-8"))
        for pos, quote in _quotes_introduced_by_verbatim(text):
            out.append((rel, text[:pos].count("\n") + 1, quote))
    return out


def test_標了逐字的引文_每一句都回比過44():
    """⛔ **從檔案抽，不是從一張清單抽。**

    一個「先列一張清單、再檢查清單裡的句子還在不在原始碼」的寫法有一個洞：
    **引文一旦被改壞，它就從受檢清單裡掉出去、從此不被檢查**，而反空掃的斷言
    因為還剩幾條而照樣通過。**那只驗得到「我列出來的句子有沒有跑掉」，
    驗不到「檔案裡標了逐字的句子是不是逐字」。**

    **本支的契約**：從**檔案**抽出每一句由「逐字」引進來的 `「…」`，逐句回比 `44`；
    要嘛對得上，要嘛登記進 `_NOT_A_44_QUOTE` 並寫出它在引什麼。
    ⇒ **引文被改壞時它仍然被抽出來、仍然對不上 ⇒ 紅。**

    ⛔ **一條擋不住的逃生路徑，據實寫明，不假裝守得到**：
    **把某一句的「逐字」兩個字順手刪掉**，那一句就脫離本支的射程。
    這**在定義上是對的** —— 不寫「逐字」的句子沒有宣稱自己逐字；
    但它確實是一條路：**想造假的人只要先撤掉宣稱就能繞過**。本支不宣稱擋得住那一種。
    """
    flat44 = _flat44(_D44.read_text(encoding="utf-8"))
    found = _all_verbatim_quotes()
    assert found, "一句引文也沒抽到 —— 這一條會變成空掃"

    bad, verified = [], 0
    for rel, lineno, quote in found:
        if quote in _NOT_A_44_QUOTE:
            continue
        if _flat44(quote) in flat44:
            verified += 1
        else:
            bad.append(
                f"{rel}:{lineno} 標了「逐字」，但這一句在 `44` 裡找不到：\n"
                f"    {quote!r}\n"
                "    怎麼修：回 `44` 讀那一行照抄；真的不是在引 `44`（例如引草稿、"
                "引本檔舊表述）就登記進 `_NOT_A_44_QUOTE` 並寫出它在引什麼。"
            )
    assert not bad, "\n".join(bad)
    assert verified >= _MIN_VERIFIED_QUOTES, (
        f"只驗到 {verified} 句逐字引文，低於下限 {_MIN_VERIFIED_QUOTES} —— "
        "要嘛引文被整批刪了，要嘛抽取判定被收窄了（＝這一條正在變成空掃）"
    )


def test_落單的刪除線標記不會吃掉它後面的引文():
    """⛔ **2026-09-24 突變測試抓到的洞：`_unstruck_text` 原本是「遇到 `~~` 就翻轉」的狀態機。**

    **本組實測（量測日 2026-09-24，修復前）**：當時本檔有**奇數**個刪除線標記，
    舊寫法把它砍掉約 95%、「逐字」由 63 剩 7。**絕對數字會漂，不寫在這裡。**
    ⛔ **2026-09-24 第二輪稽核更正：上一版寫「今天重量是 24 個、偶數」是假的（稽核實測 27、奇數）。**
    ⛔ **本輪刻意不寫替代的計數** —— 修這一句的那次編輯本身就又把計數改掉了一次。
    **所以本條自己注入一個落單的標記**，不靠檔案當下的湊巧。
    五個受檢的實作檔目前 `~~` 都是 0，所以**還沒出事** —— 但只要有人在 `logic.py` 尾段
    放一個沒有配對的 `~~`，**它後面每一句逐字引文都會悄悄退出受檢集**，而守衛照樣綠。
    下限只擋得住掉很多的那一種，擋不住掉一兩句。
    """
    source = (_ROOT / "ui_v2" / "exp" / "logic.py").read_text(encoding="utf-8")
    assert source.count("~~") == 0, "這一檔已經有刪除線了，本條的前提要重想"
    before = len(_quotes_introduced_by_verbatim(_unstruck_text(source)))
    assert before >= 20, before

    # ⛔ **標記要插在「後面還有東西可以被吃掉」的地方** ——
    #    本輪第一版把它加在**檔尾**，那裡吃不到任何東西，於是舊寫法照樣綠（突變存活）。
    #    這裡插在第一句逐字引文**之前**，舊的「遇到 `~~` 就翻轉」會把它之後整片吃掉。
    cut = source.index("逐字")
    injected = source[:cut] + "\n# ~~ 落單的標記\n" + source[cut:]
    assert injected.count("~~") == 1, injected.count("~~")
    after = len(_quotes_introduced_by_verbatim(_unstruck_text(injected)))
    assert after == before, (
        before, after,
        "一個沒有配對的 `~~` 把它後面的逐字引文吃掉了 —— 那些句子會悄悄退出受檢集")
    # 而**成對**的那一種照舊要被剝掉（退役的紀錄不該紅燈）。
    paired = _unstruck_text("留著 ~~這段退役了~~ 也留著")
    assert paired == "留著  也留著", repr(paired)
    assert "這段退役了" not in paired


def test_逐字豁免表沒有死條目而且每一筆都有理由():
    """`_NOT_A_44_QUOTE` 目前是空的；這一條是為了**它不是空的那一天**。

    ⚠️ 沒有這一條，一筆已經不存在的豁免可以永遠躺在表裡；
    下一個人把一句真的假引文改成與它同字，就會被那筆死條目默默放行。
    """
    live = {q for _rel, _line, q in _all_verbatim_quotes()}
    assert live, "一句也沒抽到 —— 這一條會變成空掃"
    dead = sorted(set(_NOT_A_44_QUOTE) - live)
    assert not dead, f"這些豁免登記在檔案裡已經找不到了，請刪掉：{dead}"
    for quote, why in _NOT_A_44_QUOTE.items():
        assert len(why) >= 10, (quote, why)


# ═════════════════════ 三、塊名、層次、四層通則 ═════════════════════


def test_八塊的塊名逐字引44():
    """`44` 3.3 那張層次表 ＋ 八個 `#### 塊 EXP-n｜…` 標題。"""
    text = _D44.read_text(encoding="utf-8")
    assert len(logic.BLOCK_TITLES) == 8
    for code, title in logic.BLOCK_TITLES.items():
        assert f"#### 塊 {code}｜{title}" in text, (code, title)


def test_八塊的回答什麼逐字引44():
    text = _flat44(_D44.read_text(encoding="utf-8"))
    assert len(logic.ANSWERS) == 8
    for code, answer in logic.ANSWERS.items():
        assert _flat44(answer) in text, (code, answer)


def test_層次分佈照44那張表():
    """`44` 3.3：層 1 `EXP-0`／層 2 `EXP-1`~`EXP-3`／層 3 `EXP-4`~`EXP-5`／層 4 `EXP-6`~`EXP-7`。"""
    model = _model("full")
    assert logic.codes_in_layer(model, 1) == ["EXP-0"]
    assert logic.codes_in_layer(model, 2) == ["EXP-1", "EXP-2", "EXP-3"]
    assert logic.codes_in_layer(model, 3) == ["EXP-4", "EXP-5"]
    assert logic.codes_in_layer(model, 4) == ["EXP-6", "EXP-7"]


def test_初次載入展開的剛好是結論燈與三張核心卡():
    """`44` 2 硬規則逐字：「初次載入時展開的東西 ＝ 結論燈 ＋ 3 張核心卡。其餘層級收合。」"""
    for name, save_failed in _every_case():
        model = _model(name, save_failed=save_failed)
        opened = [b["code"] for b in model["blocks"] if b["_default_open"]]
        assert opened == ["EXP-0", "EXP-1", "EXP-2", "EXP-3"], (name, save_failed, opened)


def test_一頁最多十塊而層2最多三張():
    model = _model("full")
    assert len(model["blocks"]) == 8
    assert len(logic.codes_in_layer(model, 2)) <= 3


def test_斷點欄數照客戶最終版三段():
    """`44` 2.1 節判準的六個寬度：1280／1279／769／768／375／374 → 三、二、二、一、一、一。"""
    got = [logic.layer_columns(2, w) for w in (1280, 1279, 769, 768, 375, 374)]
    assert got == [3, 2, 2, 1, 1, 1], got
    # `44` 廢棄的那兩個值不得出現在任何一段的邊界上。
    edges = {w for w in range(2, 2000) if logic.columns_for_width(w) != logic.columns_for_width(w - 1)}
    assert edges == {769, 1280}, sorted(edges)
    assert 1024 not in edges and 640 not in edges


def test_層1與層4永遠單欄_層3最多兩欄():
    for width in (374, 375, 768, 769, 1279, 1280, 1920):
        assert logic.layer_columns(1, width) == 1
        assert logic.layer_columns(4, width) == 1
        assert logic.layer_columns(3, width) <= 2


def test_EXP3在窄寬度改成逐檔堆疊():
    """`44` 2.1 硬規則：任何一段都不出現橫向捲動。⚠️ 塌法是沿用草稿挑的那一邊（`E-15`）。"""
    assert logic.compare_stacks(768) is True
    assert logic.compare_stacks(375) is True
    assert logic.compare_stacks(769) is False
    assert logic.compare_stacks(1280) is False
    stacked = _model("mixedccy", viewport_width=768)
    wide = _model("mixedccy", viewport_width=1280)
    assert logic.find_block(stacked, "EXP-3")["_stacked"] is True
    assert logic.find_block(wide, "EXP-3")["_stacked"] is False


# ═════════════════════ 四、紅線（全頁掃字串） ═════════════════════


def test_全頁文字零方向詞零箭頭():
    """`44` 1.2 節判準：把介面全頁文字抓成一份字串，上列方向詞一個也對不上。"""
    for name, save_failed in _every_case():
        model = _model(name, save_failed=save_failed)
        strings = logic.collect_ui_strings(model)
        assert strings, (name, save_failed, "一句畫面文字也沒收到 —— 這一條會變成空掃")
        assert logic.scan_forbidden(strings) == {}, (name, save_failed)


def test_掃描器本身會咬_負控():
    """⛔ 上一條若永遠回空字典，它跟沒跑一樣。這一條證明掃描器真的認得那些詞。"""
    for word in logic.FORBIDDEN_DIRECTION_WORDS + logic.FORBIDDEN_ARROWS:
        assert logic.scan_forbidden([f"這一句含 {word} 這個詞"]) != {}, word


def test_按鈕標籤零禁詞_而且工廠會擋():
    """`44` 1.1 節判準：沒有一列的標籤含「一鍵」「最佳」「推薦」「最適」。"""
    for name, save_failed in _every_case():
        buttons = logic.collect_buttons(_model(name, save_failed=save_failed))
        assert buttons, (name, save_failed, "一顆按鈕也沒有 —— 這一條會變成空掃")
        for button in buttons:
            for word in logic.FORBIDDEN_BUTTON_WORDS:
                assert word not in button["label"], (name, button["label"], word)
    for word in logic.FORBIDDEN_BUTTON_WORDS:
        with pytest.raises(ValueError):
            logic._button(f"測試{word}測試", "存檔")


def test_沒有一列輸入欄帶非空的預設值_在首次開啟那個情境():
    """`44` 1.1 節判準逐字：「把全部輸入欄列成一張表，表裡沒有一列帶有非空的預設值」。

    ⚠️ **母體限定在「首次開啟」那個情境**（`nocond`）—— 其餘情境代表「使用者已經填過了」，
    那時欄位當然有值。**預設值講的是首次開啟那一刻。**
    """
    model = _model("nocond")
    fields = logic.collect_inputs(model)
    assert fields == [], [f["name"] for f in fields]
    checkboxes = logic.collect_checkboxes(model)
    assert all(not box["_checked"] for box in checkboxes), [
        b["label"] for b in checkboxes if b["_checked"]
    ]


def test_欄名集合裡沒有分數星等排名推薦四類欄():
    """`44` `EXP-2` 判準逐字第一分句。"""
    for name, save_failed in _every_case():
        labels = logic.column_label_words(_model(name, save_failed=save_failed))
        if not labels:
            continue
        for label in labels:
            for word in logic.FORBIDDEN_COLUMN_WORDS:
                assert word not in label, (name, label, word)
    # 反空掃：至少有一個情境真的有欄名。
    assert logic.column_label_words(_model("full"))


def test_沒有任何一個跨幣別合成出來的數():
    """客戶 2026-09-22 設計引導第三條 ＋ `44` `EXP-3` 規則欄「跨欄不做合計也不做差額排序」。"""
    for name, save_failed in _every_case():
        model = _model(name, save_failed=save_failed)
        assert logic.cross_currency_nodes(model) == [], (name, save_failed)
    # 反空掃 ＋ 負控：把一個數的幣別改掉，守衛必須當場咬住。
    model = _model("full")
    assert logic.numeric_nodes(model), "全頁一個數也沒有 —— 上面那一圈會變成空掃"
    logic.find_row(logic.find_block(model, "EXP-2"), "F0025")["_cells"]["nav_orig_ccy"]["_ccy"] = "JPY"
    assert len(logic.cross_currency_nodes(model)) == 1


def test_跨幣別守衛的第二條路也真的會咬():
    """⛔ **2026-09-24 就地更正：那支 docstring 說「兩條路都會被抓到」，

    而第二條路（**掛不到任何一檔底下的出數值**）在全部情境裡命中 0 次、也沒有負控。**
    **本組實測（量測日 2026-09-24）**：走訪全部情境的每一個 value node，第二條路命中 **0** 次。
    ⚠️ 當初寫的「19 情境 528 個 node」是**修復前**的數，情境數後來加到 23，**該數已作廢**。
    本條把那條路**造出來**（在塊層級塞一個跨欄合計）並確認它會被咬。
    """
    model = _model("full")
    assert logic.cross_currency_nodes(model) == []
    block = logic.find_block(model, "EXP-2")
    # 一個掛在**塊層級**（不屬於任何一列）的出數值 —— 那正是跨欄合計會長的樣子。
    block["_bogus_total"] = logic._value(
        "99.99 USD", has_number=True, ccy="USD", label="全欄合計")
    bad = logic.cross_currency_nodes(model)
    assert len(bad) == 1, bad
    assert bad[0]["label"] == "全欄合計"


def test_紅線徽章只出現在說明區_不掛在數值旁():
    """`44` 5.2 禁止欄逐字：「紅線徽章不掛在數值旁邊」。"""
    for name, save_failed in _every_case():
        model = _model(name, save_failed=save_failed)
        marks = [b for b in logic.collect_badges(model) if b["_kind"] == "紅線"]
        assert marks, (name, "一枚紅線徽章也沒有 —— 這一條會變成空掃")
        for badge in marks:
            assert badge.get("_slot") == "說明區", (name, badge)
            assert badge["text"] in logic.PAGE_REDLINES, badge


def test_本頁的紅線落點就是44第一節第三小節那一列的三枚():
    """`44` 1.3 那張表，標的探索那一列改寫後是 `G1†` `G2†` `G3†`。"""
    assert logic.PAGE_REDLINES == ("G1†", "G2†", "G3†")
    model = _model("full")
    assert "G2†" in {b["text"] for b in logic.find_block(model, "EXP-3")["badges"]}


# ═════════════════════ 五、元件層 ═════════════════════


def test_狀態徽章字面值落在44那七個之內_而且工廠會擋():
    for name, save_failed in _every_case():
        badges = [b for b in logic.collect_badges(_model(name, save_failed=save_failed))
                  if b["_kind"] == "狀態"]
        for badge in badges:
            assert badge["text"] in logic.STATUS_BADGE_LITERALS, badge
    for literal in logic.STATUS_BADGE_LITERALS:
        assert logic.status_badge(literal)["text"] == literal
    with pytest.raises(ValueError):
        logic.status_badge("未生效")


def test_本頁一枚狀態徽章也沒有掛_而且那是有理由的():
    """⛔ **這不是漏掛，是本頁沒有一種狀態徽章有觸發條件。** 理由見 `logic.status_badge` 的 docstring。

    本條把這個事實釘住：哪天有人掛了第一枚，這一條會紅，逼他去讀那段理由再決定。
    """
    seen = set()
    for name, save_failed in _every_case():
        seen |= {b["_kind"] for b in logic.collect_badges(_model(name, save_failed=save_failed))}
    assert seen == {"來源", "新鮮度", "紅線"}, seen
    assert "狀態" not in seen
    # 但那個守門員本身是活的（哪天要掛，它擋得住不在七個之內的字面值）。
    assert logic.status_badge("部分缺")["_kind"] == "狀態"
    with pytest.raises(ValueError):
        logic.status_badge("有結果")


def test_fixtures的source_tier落在44那四個值域之內():
    """`44` 2026-09-23 逐欄補上的封閉四值。

    ⚠️ **帶這一欄的是三張表**（`nav`／`market_indicator`／`fetch_log`）；
    `fund_profile` **沒有這一欄** —— 那是 `E-21` 那兩枚徽章只能畫成佔位的原因之一。
    """
    assert set(logic.SOURCE_TIERS) == {"淨值", "配息", "市場指標", "其他"}
    rows = fixtures.dataset_full()["nav"]
    assert rows, "一列 nav 也沒有 —— 這一條會變成空掃"
    for row in rows:
        assert row["source_tier"] in logic.SOURCE_TIERS, row
    # `44` 的欄位表裡真的有三列寫出這個值域（第四處命中在第五節的說明段，不是欄位表）。
    lines = _D44.read_text(encoding="utf-8").split("\n")
    in_table = [
        n for n, line in enumerate(lines, 1)
        if "四個之一：`淨值`／`配息`／`市場指標`／`其他`" in line
        and line.lstrip().startswith("| `source_tier` |")
    ]
    assert len(in_table) == 3, in_table
    # 而 `fund_profile` 那張表沒有這一欄。
    text = _D44.read_text(encoding="utf-8")
    profile_table = text.split("### 4.6 表 `fund_profile`")[1].split("**主鍵**")[0]
    assert "source_tier" not in profile_table


def test_未生效不是徽章而是列尾的一段文字():
    """⛔ `E-23`：`44` `EXP-7` 要「在列尾**寫** `未生效`」，而 `未生效` 不在 `狀態` 那七個字面值裡。"""
    model = _model("blankvalue")
    rows = logic.find_block(model, "EXP-7")["_rows"]
    assert rows, "沒有軌跡列 —— 這一條會變成空掃"
    tails = [r["tail_text"] for r in rows if r["tail_text"]]
    assert tails == [logic.TEXT_NOT_EFFECTIVE], tails
    badge_texts = {b["text"] for b in logic.collect_badges(model)}
    assert logic.TEXT_NOT_EFFECTIVE not in badge_texts


def test_按鈕類別八類之內_而且沒有一類寫入那四張唯讀表():
    """`44` 5.3 元件判準逐字（兩個分句）。"""
    for name, save_failed in _every_case():
        buttons = logic.collect_buttons(_model(name, save_failed=save_failed))
        assert buttons, (name, save_failed)
        for button in buttons:
            assert button["_action_kind"] in logic.BUTTON_KINDS, button
            assert not (button["_writes"] & set(logic.READONLY_TABLES)), button
    with pytest.raises(ValueError):
        logic._button("測試", "取消")


def test_按鈕停用時不隱藏而且帶得出停用原因():
    """`44` 5.3 元件判準第二分句：「把 `enabled` 設為假，按鈕仍在畫面上」。"""
    model = _model("nowatch")
    button = logic.find_button(model, logic.TEXT_ADD_WATCH)
    assert button["_enabled"] is False
    assert button["_visible"] is True
    assert button["disabled_reason"] == logic.TEXT_NO_PICK


def test_存檔類只寫user_setting():
    """`44` 5.3 禁止欄逐字：「`存檔` 類只寫 `user_setting`」。"""
    assert logic.SAVE_WRITES == {"user_setting"}
    for name, save_failed in _every_case():
        saves = [b for b in logic.collect_buttons(_model(name, save_failed=save_failed))
                 if b["_action_kind"] == "存檔"]
        assert saves, (name, save_failed, "一枚存檔鈕也沒有 —— 這一條會變成空掃")
        for button in saves:
            assert button["_writes"] == {"user_setting"}, button


def test_全頁一枚重新取數都沒有():
    """⛔ `E-22` 登記：`44` 5.1 卡片元件在 `資料未備` 態要掛「重新取數」，

    而本頁 `EXP-2`／`EXP-6` 缺的是 `nav` 與 `dividend` —— 兩張都在**唯讀**清單裡，
    那枚鈕按了不能寫它缺的表。`44` 5.5 同輪也裁了「各塊自己寫的優先於本表模板」，
    而本頁八塊的空狀態欄**沒有一格寫出按鈕**。
    ⇒ 本頁不掛那一枚。**這是登記，也是本條在守的東西。**
    """
    for name, save_failed in _every_case():
        kinds = {b["_action_kind"] for b in logic.collect_buttons(_model(name, save_failed=save_failed))}
        assert "取數" not in kinds, (name, save_failed, kinds)


def test_本頁用到的按鈕類別就是這三類():
    """反向：本頁用到哪幾類是可以列舉的，多一類少一類都要有人看見。"""
    used = set()
    for name, save_failed in _every_case():
        used |= {b["_action_kind"] for b in logic.collect_buttons(_model(name, save_failed=save_failed))}
    assert used == {"新增列", "清除", "存檔"}, sorted(used)


def test_對比逐組算過而且未達標為零():
    """客戶 2026-09-22 設計引導第一條。**值是本檔現算的，不是引用草稿上的數。**"""
    assert len(theme.CONTRAST_PAIRS) >= 30
    bad = []
    for name, foreground, background, floor in theme.CONTRAST_PAIRS:
        ratio = theme.contrast_ratio(foreground, background)
        if ratio < floor:
            bad.append((name, round(ratio, 2), floor))
    assert bad == [], bad


def test_對比函式本身算得對_負控():
    """黑白極值是 21，同色是 1 —— 一支永遠回 21 的函式會在這裡露餡。"""
    assert round(theme.contrast_ratio("#ffffff", "#000000"), 2) == 21.0
    assert round(theme.contrast_ratio("#161b22", "#161b22"), 2) == 1.0
    assert theme.contrast_ratio(theme.BORDER, theme.SURFACE) < theme.UI_FLOOR


def test_每一個用到的色都登記過對比():
    """⛔ 一個沒有登記過對比的色，等於沒有被客戶那三條拘束到。"""
    registered = set()
    for _name, foreground, background, _floor in theme.CONTRAST_PAIRS:
        registered.add(foreground)
        registered.add(background)
    # `BORDER` 是唯一刻意不在表裡的（草稿 §J 判為純裝飾分隔線），就地寫明。
    missing = set(theme.ALL_COLORS) - registered - {theme.BORDER}
    assert missing == set(), missing


def test_四狀態的顏色語意照44卡片那張表():
    assert logic.tone_for_state(logic.STATE_OK) == "中性"
    assert logic.tone_for_state(logic.STATE_MISSING) == "灰"
    assert logic.tone_for_state(logic.STATE_BIZ) == "黃"
    assert logic.tone_for_state(logic.STATE_ERROR) == "紅"
    assert set(theme.TONE_HEX) == {"中性", "灰", "黃", "紅"}


# ═════════════════════ 六、嚴重度：不替 `44` 排它沒排的 ═════════════════════


def test_worst_state在資料未備與業務例外同級時不挑一個充數():
    """⛔ **`44` :310 是全檔唯一排過卡片四狀態的地方，而它把中間兩個並列同級。**

    ⇒ 那是一個**偏序**。`worst_state` 在同級時回 `STATE_UNRANKED`，**不發明先後**。
    """
    assert logic.worst_state([logic.STATE_MISSING, logic.STATE_BIZ]) is logic.STATE_UNRANKED
    assert logic.worst_state([logic.STATE_BIZ, logic.STATE_MISSING]) is logic.STATE_UNRANKED
    # 最差那一級只有一個成員時照回那個成員。
    assert logic.worst_state([logic.STATE_OK, logic.STATE_MISSING]) == logic.STATE_MISSING
    assert logic.worst_state([logic.STATE_OK, logic.STATE_BIZ]) == logic.STATE_BIZ
    assert logic.worst_state([logic.STATE_MISSING, logic.STATE_ERROR]) == logic.STATE_ERROR
    assert logic.worst_state([logic.STATE_BIZ, logic.STATE_ERROR]) == logic.STATE_ERROR


def test_worst_state與輸入順序無關_全排列實跑():
    """一個看不見的 tie-break 會在這裡露餡。"""
    import itertools

    states = (logic.STATE_OK, logic.STATE_MISSING, logic.STATE_BIZ, logic.STATE_ERROR)
    checked = 0
    for size in (1, 2, 3, 4):
        for combo in itertools.combinations_with_replacement(states, size):
            answers = {logic.worst_state(list(p)) for p in itertools.permutations(combo)}
            assert len(answers) == 1, (combo, answers)
            checked += 1
    assert checked >= 60, checked


def test_worst_state吃得下哨符_不會KeyError():
    """⛔ 結論燈讀的那兩塊狀態**可能含哨符**。不處理就是 `KeyError: None`。"""
    assert logic.worst_state([logic.STATE_UNRANKED]) is logic.STATE_UNRANKED
    assert logic.worst_state([logic.STATE_UNRANKED, logic.STATE_ERROR]) == logic.STATE_ERROR
    assert logic.worst_state([logic.STATE_UNRANKED, logic.STATE_OK]) is logic.STATE_UNRANKED
    assert logic.block_tone([logic.STATE_UNRANKED, logic.STATE_OK]) == "中性"
    assert logic.tone_for_block(logic.STATE_UNRANKED, [logic.STATE_MISSING]) == "灰"


def test_每一個可能收到哨符的呼叫端都列出來而且都處理得了():
    """⛔ **這一條擋的是姊妹頁踩過兩次的那個坑：拆掉哨符時漏改呼叫端，整頁當掉。**

    做法：把 `logic.py` 原始碼裡呼叫 `worst_state(` 的地方全部找出來，
    逐一確認它的回傳值只會流進**吃得下 `None`** 的那兩支（`tone_for_block`／`_band`），
    或者流進塊的 `_state`（那是資料，不是查表）。
    ⚠️ 本條**不是**靠人記得有幾個呼叫端 —— 它**現場數**，多一個就要多一筆處置。
    """
    import ast

    tree = ast.parse(pathlib.Path(logic.__file__).read_text(encoding="utf-8"))
    callers = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name == "worst_state":
            callers.append(node)
    assert callers, "一個呼叫端也沒找到 —— 這一條會變成空掃（註解與 docstring 不算呼叫）"
    # 每一個呼叫都必須是某個關鍵字引數的值，而那個關鍵字只准是 `state`
    # （＝流進 `_block()` 的 `state=`，它接著只會進 `tone_for_block()`，而那一支吃得下哨符）。
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    # 往上爬到第一個「這個值被存到哪裡」的節點（中間可能夾著 `A if c else B` 這種運算式）。
    landed = []
    for call in callers:
        node = call
        while True:
            parent = parents.get(id(node))
            if parent is None or isinstance(parent, (ast.keyword, ast.Assign, ast.Return)):
                break
            node = parent
        landed.append((call, parent))
    assert len(landed) == len(callers)
    for call, parent in landed:
        if isinstance(parent, ast.keyword):
            where = f"keyword:{parent.arg}"
        elif isinstance(parent, ast.Assign):
            where = "assign:" + ",".join(
                t.id for t in parent.targets if isinstance(t, ast.Name)
            )
        elif isinstance(parent, ast.Return):
            where = "return"
        else:
            where = f"其他:{type(parent).__name__}"
        # ⛔ 只准落在名字叫 `state` 的地方 —— 那個名字接著只會流進 `_block(state=...)`，
        #    而 `_block()` 只把它交給 `tone_for_block()`，那一支吃得下哨符。
        assert where in ("keyword:state", "assign:state"), (
            ast.unparse(call),
            where,
            "這個 `worst_state()` 的回傳值流去了別的地方 —— 它可能是哨符 `None`，"
            "流進任何一個會拿它查表的地方就是 `KeyError: None`。",
        )
    # 而且 `_block()` 真的只把 `state` 交給 `tone_for_block()`，不拿它查任何表。
    block_source = inspect.getsource(logic._block)
    assert "tone_for_block(state, states)" in block_source
    assert "_TONE_BY_STATE[state]" not in block_source
    # 而且每一個塊的 `_state` 都真的吃得下哨符（直接把哨符餵進去畫顏色）。
    for state in (logic.STATE_UNRANKED, logic.STATE_OK, logic.STATE_MISSING,
                  logic.STATE_BIZ, logic.STATE_ERROR):
        assert logic.tone_for_block(state, [logic.STATE_OK]) in ("中性", "灰", "黃", "紅")


def test_哨符真的流過每一塊也不會炸():
    """⛔ **2026-09-24 突變測試抓到的洞：上面那條 AST 守衛比它 docstring 宣稱的弱一級。**

    它只檢查「`worst_state()` 的回傳值**第一次落在哪個名字**」，
    **落地之後被拿去做什麼它不看** —— 在同一個函式裡多加一行 `tone_for_state(state)`
    （收到哨符就 `KeyError: None`），**AST 守衛照樣綠**。

    本條改用**行為層**驗：把 `worst_state` 換成「永遠回哨符」，
    再把每一個情境的整頁模型建一次 —— **任何一個會拿哨符去查表的地方都會當場炸**。
    ⚠️ 這比 AST 強的地方：它不管你怎麼寫，只管「哨符流過去會不會死」。
    """
    original = logic.worst_state
    built = 0
    try:
        logic.worst_state = lambda states: logic.STATE_UNRANKED
        for name, save_failed in _every_case():
            model = _model(name, save_failed=save_failed)   # 炸了就是紅
            for block in model["blocks"]:
                # 哨符不得外洩成畫面文字（`44` 5.1 的四狀態是封閉列舉）。
                # ⛔ **2026-09-24 稽核抓到：這一句原本寫成**
                #    `assert logic.STATE_UNRANKED not in logic.collect_ui_strings(block)`
                #    —— 而 `STATE_UNRANKED is None`、`collect_ui_strings()` 只 append `str`。
                #    **型別上永遠不可能相等，這句結構上不可能失敗。**
                #    稽核的決定性突變：讓哨符真的變成畫面文字 → **那一句照樣綠**。
                #    現在改掃**字面**：哨符一旦被 `str()` 出去，畫面上就會出現 `"None"`。
                for _s in logic.collect_ui_strings(block):
                    assert "None" not in _s, (name, block["code"], _s)
                assert block["_tone"] in ("中性", "灰", "黃", "紅"), (name, block["code"], block["_tone"])
            built += 1
    finally:
        logic.worst_state = original
    assert built == len(fixtures.ALL_SCENARIO_NAMES) * len(fixtures.SAVE_FAIL_CHOICES), built
    # 還原確認：換回來之後行為與平常一致。
    assert logic.worst_state([logic.STATE_OK]) == logic.STATE_OK


def test_block_tone的顏色優先序逐組釘住():
    """⛔ **2026-09-24 稽核的突變抓到的洞：把 `block_tone` 的顏色優先序倒過來，測試不會紅。**

    它只在哨符時才被用到，而哨符**沒有任何情境走得到**
    （**本組實測**：全部情境出現過的 `_state` 只有 `ok`／`資料未備`／`系統錯誤` 三種）；
    當時唯二的斷言一個是空集合、一個只有一個顏色 —— **「取最顯眼的顏色」這個排序本身一次都沒被驗過。**
    ⚠️ **「158 全綠」那個數是稽核跑出來的，本組沒有重跑那一版**；本組自己驗到的是上面那句機制。
    """
    assert logic.block_tone([]) == "中性"
    assert logic.block_tone([logic.STATE_OK]) == "中性"
    assert logic.block_tone([logic.STATE_MISSING]) == "灰"
    assert logic.block_tone([logic.STATE_BIZ]) == "黃"
    assert logic.block_tone([logic.STATE_ERROR]) == "紅"
    # 逐組：越前面的越優先，而且與輸入順序無關。
    import itertools

    order = ["紅", "黃", "灰", "中性"]
    by_tone = {
        "紅": logic.STATE_ERROR, "黃": logic.STATE_BIZ,
        "灰": logic.STATE_MISSING, "中性": logic.STATE_OK,
    }
    pairs = 0
    for strong, weak in itertools.combinations(order, 2):
        combo = [by_tone[strong], by_tone[weak]]
        assert logic.block_tone(combo) == strong, (strong, weak)
        assert logic.block_tone(list(reversed(combo))) == strong, (strong, weak)
        pairs += 1
    assert pairs == 6, pairs
    # 哨符不參與顏色（它不是狀態），但不得讓整支炸。
    assert logic.block_tone([logic.STATE_UNRANKED, logic.STATE_ERROR]) == "紅"


def test_空狀態四種的嚴重度是全序_而且照44客戶裁示那一句():
    """`44` 5.5：「嚴重度由重到輕排定為 `系統錯誤` ＞ `來源缺` ＞ `算不出來` ＞ `部分缺`」。

    ⚠️ 這一把**是全序**（四種各自分得出先後），與上面卡片四狀態那一把**不是同一把尺**。
    """
    order = [logic.EMPTY_ERROR, logic.EMPTY_SOURCE, logic.EMPTY_UNCOMPUTABLE, logic.EMPTY_PARTIAL]
    for index, heavier in enumerate(order):
        for lighter in order[index + 1 :]:
            assert logic.worst_empty_state([heavier, lighter]) == heavier, (heavier, lighter)
            assert logic.worst_empty_state([lighter, heavier]) == heavier, (heavier, lighter)
    assert logic.worst_empty_state([]) is None
    # 顏色不參與排序：`來源缺` 是灰、`算不出來` 是黃，而灰比黃嚴。
    assert logic.worst_empty_state([logic.EMPTY_SOURCE, logic.EMPTY_UNCOMPUTABLE]) == logic.EMPTY_SOURCE


def test_本頁沒有任何情境產生業務例外_據實登記():
    """⛔ **這一條是登記，不是讚美。**

    `44` 本頁八塊的空狀態欄**沒有一句**寫 `⬜ 不適用`，所以 `業務例外` 在本頁沒有觸發路徑；
    連帶 `STATE_UNRANKED` 那條路**也沒有情境走得到**（它要 `資料未備` 與 `業務例外` 同時出現）。
    上面那幾條靠**直接呼叫**驗它，不是靠情境。**寫在這裡，免得下一個人以為情境覆蓋過它。**
    """
    seen = set()
    for name, save_failed in _every_case():
        model = _model(name, save_failed=save_failed)
        seen |= {b["_state"] for b in model["blocks"]}
        seen |= {n["_state"] for n in logic.value_nodes(model)}
    assert logic.STATE_BIZ not in seen, seen
    assert logic.STATE_UNRANKED not in seen, seen
    # 反空掃：另外三個狀態本頁都走得到。
    assert {logic.STATE_OK, logic.STATE_MISSING, logic.STATE_ERROR} <= seen, seen


# ═════════════════════ 七、EXP-0 篩選結果結論列 ═════════════════════


def test_EXP0判準a_零檔符合_文案與燈色與生效條件列():
    """`44` `EXP-0` 判準第一分句。"""
    block = logic.find_block(_model("zero"), "EXP-0")
    assert block["text"] == logic.TEXT_NO_MATCH
    assert block["_tone_override"] == "灰"
    assert block["condition_lines"], "沒有列出生效條件 —— 判準第一分句要求「下方列出生效條件」"
    assert len(block["condition_lines"]) == len(fixtures.RULES_ZERO)


def test_EXP0判準b_條件清空_文案是尚未設定條件而不是0檔():
    """`44` `EXP-0` 判準第二分句 ＋ 空狀態欄那一句優先序。"""
    block = logic.find_block(_model("nocond"), "EXP-0")
    assert block["text"] == logic.TEXT_NO_CONDITION
    assert "0" not in block["text"]
    assert logic.TEXT_NO_MATCH not in block["text"]
    assert block["_tone_override"] == "灰"


def test_EXP0判準c_至少一檔符合_燈由灰轉黃而文案只寫檔數():
    """`44` `EXP-0` 判準第三分句。"""
    zero = logic.find_block(_model("zero"), "EXP-0")
    one = logic.find_block(_model("onematch"), "EXP-0")
    assert zero["_tone_override"] == "灰"
    assert one["_tone_override"] == "黃"
    assert one["text"] == logic.conclusion_text(1)
    # 「不含任何評語」：這三個詞是 `44` 規則欄自己點名的。
    for word in ("太多", "太少", "剛好"):
        assert word not in one["text"], word


def test_EXP0判準d_一檔加到十檔_燈維持黃不隨檔數變色():
    """`44` `EXP-0` 判準第四分句。"""
    one = logic.find_block(_model("onematch"), "EXP-0")
    ten = logic.find_block(_model("tenmatch"), "EXP-0")
    assert logic.find_block(_model("tenmatch"), "EXP-2")["_rows"].__len__() == 10
    assert one["_tone_override"] == ten["_tone_override"] == "黃"
    assert ten["text"] == logic.conclusion_text(10)


def test_EXP0_讀到的那兩塊任一為系統錯誤時燈為紅並列出失敗的那一段():
    """`44` `EXP-0` 規則欄逐字第三色。"""
    block = logic.find_block(_model("profilefail"), "EXP-0")
    assert block["_tone_override"] == "紅"
    # ⚠️ 取數失敗那一族住 `fetch_fail_lines`，存檔失敗那一族才住 `error_lines` —— 兩族分開的鍵。
    assert block["fetch_fail_lines"], "紅燈卻沒有列出失敗的那一段"
    assert any(fixtures.FETCH_FAIL_MESSAGE in line for line in block["fetch_fail_lines"])
    assert any("EXP-2" in line for line in block["fetch_fail_lines"])


def test_EXP0只讀那兩塊_不自取數():
    """`44` `EXP-0` 來源欄逐字：「不自取數。只讀 `EXP-2` 的列數與 `EXP-1` 的條件列數」。

    做法：把 `_build_exp0` 的簽名列出來 —— 它拿得到的只有數、旗標與那兩塊的狀態。
    """
    params = set(inspect.signature(logic._build_exp0).parameters)
    assert params == {"dataset", "count", "has_rules", "rules", "read_states"}, params
    # `read_states` 真的只有兩個成員（那兩塊），不是三張卡。
    source = pathlib.Path(logic.__file__).read_text(encoding="utf-8")
    assert 'read_states=(exp1["_state"], exp2["_state"])' in source


def test_取數失敗圖示是禁止號_紅燈也是():
    """客戶 2026-09-24 裁示（`44` 第五節第五小節已同步）：取數失敗 ⛔、黃燈 ⚠。改回 ⚠ 這一條要紅。"""
    assert logic.fetch_failed_text("HTTP 503") == "⛔ 取數失敗：HTTP 503"
    assert logic.ERR_TEXT == "⛔ 取數失敗"
    reds = [
        logic.find_block(_model(name, save_failed=s), "EXP-0")
        for name, s in _every_case()
        if logic.find_block(_model(name, save_failed=s), "EXP-0")["_tone_override"] == "紅"
    ]
    assert reds and all(b["glyph"] == "⛔" for b in reds)


def test_EXP0的狀態同時有圖示與文字_不靠顏色單獨辨識():
    """客戶 2026-09-22 設計引導第二條。"""
    seen = set()
    for name, save_failed in _every_case():
        block = logic.find_block(_model(name, save_failed=save_failed), "EXP-0")
        assert block["glyph"], (name, "沒有圖示")
        assert block["state_word"], (name, "沒有狀態文字")
        seen.add(block["_tone_override"])
    assert seen == {"灰", "黃", "紅"}, seen


def test_EXP0的兩個顏色欄位永遠相等_畫面層挑哪一個都一樣():
    """⛔ **2026-09-24 第二輪稽核：這一條原本叫「只有一個顏色欄位」，與它自己的斷言不符。**

    塊上**確實有兩個**顏色鍵（`_tone` 與 `_tone_override`），而本條斷言的是**兩者相等**
    —— 也就是「留了兩個，但它們永遠說同一件事」，不是「只留一個」。
    **斷言是對的，錯的是名字。**（本輪第三隻同型：另兩隻在 `logic.py` 與 `test_exp_page.py`。）

    ⚠️ **這條驗的東西沒有變弱**：結論燈的顏色走 `44` 給本塊的三色規則、不走卡片那張四狀態表；
    兩個鍵只要有一次說不一樣，畫面層就可以挑，而挑錯的那一次不會有任何東西轉紅。
    """
    for name, save_failed in _every_case():
        block = logic.find_block(_model(name, save_failed=save_failed), "EXP-0")
        assert block["_tone"] == block["_tone_override"], (name, block["_tone"], block["_tone_override"])
    # 而且它真的與四狀態表算出來的不一樣（否則這一條沒有守到東西）。
    zero = logic.find_block(_model("zero"), "EXP-0")
    assert zero["_tone"] == "灰"
    assert logic.tone_for_state(zero["_state"]) == "中性", zero["_state"]


def test_EXP0的狀態文字不借卡片四狀態那一組字():
    """⛔ **`44` `EXP-0` 塊下方自己登記過：本塊的燈與前四枚方向相反。**

    前四枚灰＝正常、黃＝要注意；本塊灰＝什麼都沒有、黃＝有結果。
    把灰寫成「資料未備」會把那個相反的方向**又藏回去** ——
    條件未設的時候資料好端端的，缺的是使用者還沒輸入。**那句話是假的。**
    ⚠️ 那四句狀態文字 `44` 一句也沒有給（客戶裁的是三個**顏色**），是本組擬的。
    """
    words = {}
    for name, save_failed in _every_case():
        block = logic.find_block(_model(name, save_failed=save_failed), "EXP-0")
        words[block["state_word"]] = (block["_tone_override"], name)
    assert set(words) == {"條件未設", "零檔符合", "有檔符合", "取數失敗"}, words
    # 灰那一色底下有兩句不同的話（條件未設／零檔符合）—— 那正是不能只看顏色寫字的理由。
    grey = {word for word, (tone, _n) in words.items() if tone == "灰"}
    assert grey == {"條件未設", "零檔符合"}, grey
    # ⛔ 卡片四狀態那三個字一個也不准出現在這一枚燈的狀態文字上。
    for borrowed in (logic.STATE_MISSING, logic.STATE_BIZ, logic.STATE_ERROR):
        assert borrowed not in words, (borrowed, words)


def test_EXP0的N就是EXP2的列數():
    """`44` `EXP-0` 規則欄逐字：「N 為 `EXP-2` 的列數」。"""
    for name, save_failed in _every_case():
        model = _model(name, save_failed=save_failed)
        rows = len(logic.find_block(model, "EXP-2")["_rows"])
        block = logic.find_block(model, "EXP-0")
        if block["_tone_override"] == "黃":
            assert block["text"] == logic.conclusion_text(rows), (name, save_failed)


# ═════════════════════ 八、EXP-1 條件輸入卡 ═════════════════════


def test_EXP1判準a_首次開啟條件列數為零且沒有任何已勾選的選項():
    model = _model("nocond")
    block = logic.find_block(model, "EXP-1")
    assert block["_rows"] == []
    assert block["notes"], "一列也沒有時要顯示提示文字"
    assert logic.find_button(model, logic.TEXT_ADD_CONDITION)["_action_kind"] == "新增列"


def test_EXP1判準b_數值留空該列不生效且EXP2列數不因這一列改變():
    """`44` `EXP-1` 判準第二分句。"""
    blank = _model("blankvalue")
    three = _model("full")
    rows = logic.find_block(blank, "EXP-1")["_rows"]
    assert len(rows) == 4
    assert rows[-1]["tail_text"] == logic.TEXT_BLANK_VALUE
    assert [r["tail_text"] for r in rows[:3]] == ["", "", ""]
    # EXP-2 的列數不因這一列改變。
    assert len(logic.find_block(blank, "EXP-2")["_rows"]) == len(
        logic.find_block(three, "EXP-2")["_rows"]
    )


def test_EXP1判準c_存檔之後重新載入_條件列逐字相同且updated_at非空():
    """`44` `EXP-1` 判準第三分句。

    ⚠️ **這一頁沒有真的資料庫**，「存檔」的持久化由 `user_setting` 那一列代表。
    本條驗得到的是：**已存值重新載入之後逐字相同，而且那一鍵的 `updated_at` 非空**。
    ⛔ **本條不宣稱驗到了真的寫入** —— 那要有一個會寫的後端，本輪沒有。
    """
    dataset = fixtures.dataset_full()
    saved = logic.saved_rules(dataset)
    assert saved, "已存值是空的 —— 這一條會變成空掃"
    assert tuple(saved) == fixtures.RULES_THREE
    assert logic.setting_updated_at(dataset, "exp_filter_rules")
    reloaded = logic.build_page_model(dataset)  # 不給 draft ＝ 重新載入
    assert [r["text"] for r in logic.find_block(reloaded, "EXP-1")["_rows"]] == [
        logic.rule_text(rule) for rule in fixtures.RULES_THREE
    ]


def test_EXP1判準d_按存檔之後四張唯讀表的列數不變():
    """`44` `EXP-1` 判準第四分句：按「存檔」之後 `holding`、`policy`、`nav`、`dividend` 列數相同。"""
    model = _model("full")
    button = [b for b in logic.find_block(model, "EXP-1")["buttons"]
              if b["_action_kind"] == "存檔"]
    assert len(button) == 1, button
    assert button[0]["_writes"] == {"user_setting"}
    assert not (button[0]["_writes"] & set(logic.READONLY_TABLES))


def test_EXP1的存檔不宣告任何停用條件_照44塊下方那一筆判讀():
    """`44` `EXP-1` 塊下方「其一」已就地判讀為走 `SET-4` 那一種（不宣告停用條件），

    並註明那是本組判讀、可推翻。本條把那個判讀釘住：**條件一列也沒有時，存檔仍然可按。**
    """
    model = _model("nocond")
    button = [b for b in logic.find_block(model, "EXP-1")["buttons"] if b["_action_kind"] == "存檔"]
    assert len(button) == 1
    assert button[0]["_enabled"] is True


def test_EXP1存檔寫入失敗_訊息原文照印且條件列留在畫面上():
    """`44` `EXP-1` 空狀態欄第三句。"""
    plain = logic.find_block(_model("full"), "EXP-1")
    failed = logic.find_block(_model("full", save_failed=True), "EXP-1")
    assert failed["error_lines"], "開了失敗開關卻沒有失敗框"
    assert any(fixtures.SAVE_FAIL_MESSAGE in line for line in failed["error_lines"])
    # 條件列的當下內容留在畫面上不清掉。
    assert [r["text"] for r in failed["_rows"]] == [r["text"] for r in plain["_rows"]]
    # `EXP-2` 的列數不變。
    assert len(logic.find_block(_model("full", save_failed=True), "EXP-2")["_rows"]) == len(
        logic.find_block(_model("full"), "EXP-2")["_rows"]
    )


def test_EXP1每一條件列都有一枚清除鈕_而且那是本組加的_就地登記():
    """⛔ `E-18`：`44` 只寫「條件列由使用者新增」，**沒有寫怎麼刪、也沒有給字面**。"""
    rows = logic.find_block(_model("full"), "EXP-1")["_rows"]
    assert rows
    for row in rows:
        assert row["_button"]["_action_kind"] == "清除"
        assert row["_button"]["label"] == logic.TEXT_CLEAR_ROW
    source = pathlib.Path(logic.__file__).read_text(encoding="utf-8")
    assert "E-18" in source, "這一筆沒有在程式碼裡登記，那就只是憑空多出來的一顆鈕"


def test_EXP1的當下值與已存值不同時_畫面寫出選了哪一邊():
    """⛔ `44` `EXP-1` 塊下方「其二」就地標為**待客戶或總管裁決**。

    本頁取「當下值餵 `EXP-2`」，**並把這件事寫在畫面上** —— 一個沒有寫出來的選擇，
    下一個人會讀成規格。
    """
    block = logic.find_block(_model("draftdiffers"), "EXP-1")
    assert any("當下" in line and "已存" in line for line in block["detail_lines"]), block["detail_lines"]
    # 而且 `EXP-2` 真的跟著當下值走（`draftdiffers` 的當下值只留一檔）。
    assert len(logic.find_block(_model("draftdiffers"), "EXP-2")["_rows"]) == 1
    # 同一組資料、不給 draft ＝ 已存值，那是五檔。
    assert len(logic.find_block(logic.build_page_model(fixtures.dataset_full()), "EXP-2")["_rows"]) == 5
    # 兩邊一樣時不寫那一行（否則它會變成每一頁都有的雜訊）。
    assert not any("當下" in line and "已存" in line
                   for line in logic.find_block(_model("full"), "EXP-1")["detail_lines"])


def test_EXP1可選欄位取自fund_profile的欄位名清單():
    """`44` `EXP-1` 規則欄逐字。"""
    block = logic.find_block(_model("full"), "EXP-1")
    line = [l for l in block["detail_lines"] if "fund_profile" in l]
    assert line, block["detail_lines"]
    for field in logic.FUND_PROFILE_FIELDS:
        assert field in line[0], field
    # 而且那份清單就是 `44` 4.6 那張表的欄位。
    text = _D44.read_text(encoding="utf-8")
    for field in logic.FUND_PROFILE_FIELDS:
        assert f"| `{field}` |" in text, field


# ═════════════════════ 九、EXP-2 候選清單卡 ═════════════════════


def test_EXP2判準a_全欄列出_欄名集合乾淨():
    block = logic.find_block(_model("full"), "EXP-2")
    assert list(block["column_keys"]) == list(logic.COLUMN_ORDER)
    assert block["column_labels"] == [logic.COLUMN_LABELS[c] for c in logic.COLUMN_ORDER]
    for label in block["column_labels"]:
        for word in logic.FORBIDDEN_COLUMN_WORDS:
            assert word not in label


def test_EXP2判準b_抽掉某檔最近淨值_該檔仍在列上且淨值格為空方塊():
    """`44` `EXP-2` 判準第二分句 ＋ 空狀態欄第三句。"""
    block = logic.find_block(_model("full"), "EXP-2")
    codes = [r["_fund_code"] for r in block["_rows"]]
    assert fixtures.NO_NAV_FUND in codes, "那一檔被剔除了 —— `44` 逐字要求它仍列出"
    row = logic.find_row(block, fixtures.NO_NAV_FUND)
    assert row["_cells"]["nav_orig_ccy"]["text"] == "⬜"
    assert row["_cells"]["nav_orig_ccy"]["_state"] == logic.STATE_MISSING
    assert row["_cells"]["nav_date"]["text"] == "⬜"
    # 沒被抽掉的那幾檔照樣出數（否則這一條分不出「全部都是 ⬜」）。
    other = [r for r in block["_rows"] if r["_fund_code"] != fixtures.NO_NAV_FUND]
    assert other
    assert all(r["_cells"]["nav_orig_ccy"]["_state"] == logic.STATE_OK for r in other)


def test_EXP2判準c_每一列兩組勾選框各標對照與觀察清單():
    block = logic.find_block(_model("full"), "EXP-2")
    assert block["_rows"]
    for row in block["_rows"]:
        groups = row["_checkboxes"]
        assert set(groups) == {logic.GROUP_COMPARE, logic.GROUP_WATCH}, groups
        assert groups[logic.GROUP_COMPARE]["label"] == "對照"
        assert groups[logic.GROUP_WATCH]["label"] == "觀察清單"


def test_EXP2判準d_勾起對照那一組不改變同列觀察清單那一組():
    """`44` `EXP-2` 判準第四分句 ＋ 規則欄「兩組並存、互不連動」。"""
    block = logic.find_block(_model("full"), "EXP-2")
    row = logic.find_row(block, "F0025")  # 這一檔在 `COMPARE_THREE` 裡、不在 `WATCH_TWO` 裡
    assert row["_checkboxes"][logic.GROUP_COMPARE]["_checked"] is True
    assert row["_checkboxes"][logic.GROUP_WATCH]["_checked"] is False
    # 反過來也成立：只勾觀察清單的那一檔，對照那一組仍然未勾。
    only_watch = _model("full", compare_checked=(), watch_checked=("F0025",))
    row2 = logic.find_row(logic.find_block(only_watch, "EXP-2"), "F0025")
    assert row2["_checkboxes"][logic.GROUP_COMPARE]["_checked"] is False
    assert row2["_checkboxes"][logic.GROUP_WATCH]["_checked"] is True


def test_EXP2預設不排序時依fund_code字面值排列():
    """`44` `EXP-2` 規則欄逐字。"""
    block = logic.find_block(_model("full"), "EXP-2")
    codes = [r["_fund_code"] for r in block["_rows"]]
    assert codes == sorted(codes), codes
    assert len(codes) > 1, "只有一列的話這一條分不出排序"
    # 排序依據寫在畫面上（`E-08`：那一欄不在畫面的欄位清單裡）。
    # ⚠️ 它住在自己的鍵 `sort_caption`，**不是 `detail_lines` 的某一項** ——
    #    畫面層靠位置取行會在有人插一行說明時無聲畫錯地方。
    assert logic.DEFAULT_SORT_FIELD in block["sort_caption"], block["sort_caption"]
    assert logic.DEFAULT_SORT_FIELD not in block["column_keys"]
    assert all(logic.DEFAULT_SORT_FIELD not in line for line in block["detail_lines"])
    # 選了排序欄位時那一行換成該欄的欄名。
    picked = logic.find_block(_model("sortnav"), "EXP-2")
    assert logic.COLUMN_LABELS["nav_orig_ccy"] in picked["sort_caption"], picked["sort_caption"]


def test_EXP2自選排序欄位之後真的依那一欄排_而且不加冠詞():
    block = logic.find_block(_model("sortnav"), "EXP-2")
    navs = []
    for row in block["_rows"]:
        nav = logic.latest_nav(fixtures.dataset_sortnav(), row["_fund_code"])
        navs.append(nav["nav_orig_ccy"] if nav else None)
    present = [n for n in navs if n is not None]
    assert len(present) >= 2, navs
    assert present == sorted(present), navs
    assert navs[-1] is None, "缺值沒有排在最後 —— 本檔登記的那一邊沒有生效"
    for word in ("精選", "推薦", "最佳"):
        assert all(word not in label for label in block["column_labels"])
        assert all(word not in line for line in block["detail_lines"])


def test_五個可排序欄每一欄都真的被排過():
    """⛔ **2026-09-24 稽核的突變抓到的洞：`logic._sort_key` 整支從來沒有被執行過。**

    全套情境當時只有兩個帶 `sort_column`，兩者都是 `nav_orig_ccy`，而那一欄走獨立分支
    —— **五個可排序欄裡有四個從來沒有被排過**。
    **本組實測（量測日 2026-09-24，而且今天還能重現）**：在 `_sort_key` 上掛探針，
    **拿掉本條新加的四個情境**（`sortname`／`sortccy`／`sortdate`／`sortratio`）跑完
    全部情境 × 兩種存檔結果 → 它被呼叫 **0** 次；**四個情境加回去 → 46 次**。
    （所以這不是「當時才成立」的陳述，是可以現場複驗的。）
    ⚠️ **「改成回 `(0, "")` → 158 全綠」那個數是稽核跑出來的，本組沒有重跑那一版。**
    本條補上：每一欄都要有一個情境**真的依它排過**，而且排出來的順序**與預設排列不同**
    （同序的話，這一條分不出「有排」與「沒排」）。
    """
    expected_scenarios = {
        "fund_name": "sortname",
        "ccy": "sortccy",
        "nav_date": "sortdate",
        "nav_orig_ccy": "sortnav",
        "div_ratio_pct": "sortratio",
    }
    assert set(expected_scenarios) == set(logic.COLUMN_ORDER), set(expected_scenarios) ^ set(logic.COLUMN_ORDER)
    for column, name in expected_scenarios.items():
        block = logic.find_block(_model(name), "EXP-2")
        assert logic.saved_sort_column(fixtures.scenario(name)["dataset"]) == column, name
        codes = [row["_fund_code"] for row in block["_rows"]]
        assert len(codes) >= 3, (name, codes)
        assert codes != sorted(codes), (
            name, column, codes,
            "排出來的順序與預設的 fund_code 字面值排列相同 —— 這一欄的正控分不出有沒有排")
        assert logic.COLUMN_LABELS[column] in block["sort_caption"], (name, block["sort_caption"])


def test_配息比依數排不是依畫面字串排():
    """⛔ `_sort_key` 裡那句「這一欄拿**數**去排，不是拿畫面字串」原本**零測試背書**。

    現行資料裡數序與字串序**刻意相反**（`fixtures.RATIO_STRING_TRAP`：
    `9.5` 與 `12.5` —— 數上 9.5 小，字串上 `"12.50%" < "9.50%"`）。
    """
    block = logic.find_block(_model("sortratio"), "EXP-2")
    shown = [r["_cells"]["div_ratio_pct"]["text"] for r in block["_rows"]]
    present = [t for t in shown if t != "⬜"]
    assert len(present) >= 4, present
    # 依數排：把顯示字串剝回數，必須遞增。
    numbers = [float(t.split("%")[0]) for t in present]
    assert numbers == sorted(numbers), numbers
    # 而且**與依字串排的結果不同** —— 不然這一條驗不到差別。
    assert present != sorted(present), present
    # 缺值仍然排最後。
    assert shown[-1] == "⬜", shown


def test_EXP2依最近淨值排序時_把跨幣別比大小這件事寫在畫面上():
    """⛔ `E-06` 登記：`44` 允許使用者自選排序欄位，也沒有一條擋這一種。"""
    block = logic.find_block(_model("sortnav"), "EXP-2")
    assert any("幣別" in line for line in block["detail_lines"]), block["detail_lines"]
    # 沒有選那一欄時不寫（否則它會變成每一頁都有的雜訊）。
    assert not any("幣別" in line for line in logic.find_block(_model("full"), "EXP-2")["detail_lines"])


def test_EXP2條件未設與零檔符合是兩句不同的話():
    # ⚠️ `nocond` 那一組連欄位鍵都沒存過（全不勾）→ 依 `44` `EXP-4` 判準行，
    #    「目前只顯示基金名」那一行也會同時出現在 `EXP-2` 上。兩句都要在，而且是兩句。
    nocond = logic.find_block(_model("nocond"), "EXP-2")["notes"]
    assert logic.TEXT_NO_CONDITION in nocond, nocond
    assert logic.TEXT_NO_MATCH not in nocond, nocond
    zero = logic.find_block(_model("zero"), "EXP-2")["notes"]
    assert zero == [logic.TEXT_NO_MATCH], zero


def test_只顯示基金名那一行照44的判準行寫在EXP2():
    """⛔ **2026-09-24 就地更正：這一條原本主張「`44` 沒寫是哪一張卡」而把它寫在 `EXP-4`。**

    **那個理由是錯的 —— 我只讀了空狀態欄那一格，沒有讀判準行。**
    `44` `EXP-4` 判準行逐字：「取消全部欄位勾選，`EXP-2` 剩下基金名一欄且出現「目前只顯示基金名」」
    —— **主詞是 `EXP-2`**，「且出現」承的是同一個主詞。**44 把指代解開了，而且解向 `EXP-2`。**
    ⇒ 現在寫在 `EXP-2`。
    """
    model = _model("nocolumn")
    assert logic.TEXT_ONLY_FUND_NAME in logic.find_block(model, "EXP-2")["notes"]
    assert logic.TEXT_ONLY_FUND_NAME not in logic.find_block(model, "EXP-4")["notes"]
    # 前提釘住：`44` 的判準行真的把主詞寫成 `EXP-2`。
    text = _D44.read_text(encoding="utf-8")
    assert "取消全部欄位勾選，`EXP-2` 剩下基金名一欄且出現「目前只顯示基金名」" in text
    # 有勾欄位時那一行不出現。
    assert logic.TEXT_ONLY_FUND_NAME not in logic.find_block(_model("full"), "EXP-2")["notes"]


def test_EXP2來源表取數失敗時整塊進系統錯誤():
    """`44` 5.5 `系統錯誤` 的觸發條件逐字：「取數或計算本身失敗」。"""
    for name in ("profilefail", "navfail", "twofail"):
        block = logic.find_block(_model(name), "EXP-2")
        assert block["_state"] == logic.STATE_ERROR, name
        assert block["_tone"] == "紅", name
        assert any(logic.ERR_TEXT in line for line in block["notes"]), (name, block["notes"])


def test_上游取數失敗時_沒有一塊把它報成別的東西():
    """⛔ **§1 Fail Loud：一句把取數失敗報成別的東西的文案，比沒有文案更誤導。**

    `fund_profile` 取數失敗時，照各塊原本的空狀態文案走會印出三句**假話**：
    `EXP-2` 印「目前條件下沒有符合的基金」、`EXP-3` 印「勾選最多 3 檔以並排對照」、
    `EXP-6` 印「查無此 `fund_code`」—— **最後那一句最糟**：它對一檔基金
    **斷言了一件事實**（這個代碼不存在），而真相是我們根本沒查到。
    `EXP-7` 則會印出一串「0 → 0」的軌跡，什麼都不說。

    **法源**：`44` 5.5 那張表 `系統錯誤` 一列的觸發條件逐字「取數或計算本身失敗」，
    文案模板逐字 `⛔ 取數失敗：<訊息原文>`（2026-09-24 客戶裁示由 ⚠ 改 ⛔）。
    ⚠️ 本頁八塊只有 `EXP-0` 寫出 `系統錯誤` 這個字面（`E-14`），但 `44` `EXP-0` 塊下方
    已經就地撤回過「塊沒寫種類名 ⇒ 該狀態不會發生」這個推論。**所以這不是本組發明的狀態。**
    """
    model = _model("profilefail_picked")
    lies = {
        "EXP-2": (logic.TEXT_NO_MATCH, logic.TEXT_NO_CONDITION),
        "EXP-3": (logic.TEXT_PICK_THREE,),
        "EXP-6": (logic.TEXT_NO_SUCH_FUND,),
        "EXP-7": (logic.TEXT_NO_CONDITION,),
    }
    for code, forbidden in lies.items():
        block = logic.find_block(model, code)
        assert block["_state"] == logic.STATE_ERROR, (code, block["_state"])
        assert block["_tone"] == "紅", (code, block["_tone"])
        assert block["notes"], (code, "一句話也沒說 —— 那比說錯話好一點，但不是本條要的")
        assert any(logic.ERR_TEXT in note for note in block["notes"]), (code, block["notes"])
        assert any(fixtures.FETCH_FAIL_MESSAGE in note for note in block["notes"]), code
        for word in forbidden:
            assert all(word not in note for note in block["notes"]), (code, word, block["notes"])
    # `EXP-7` 連軌跡列都不列 —— 那三欄的數建立在一張掛掉的表上。
    assert logic.find_block(model, "EXP-7")["_rows"] == []
    # 對照組：沒有失敗的時候那幾句照舊印得出來（否則這一條會把正常路徑一起改掉而沒人發現）。
    fine = _model("zero")
    assert logic.TEXT_NO_MATCH in logic.find_block(fine, "EXP-2")["notes"]
    assert logic.TEXT_PICK_THREE in logic.find_block(fine, "EXP-3")["notes"]
    assert logic.TEXT_NO_SUCH_FUND in logic.find_block(_model("unknownfund"), "EXP-6")["notes"]
    assert logic.TEXT_NO_CONDITION in logic.find_block(_model("nocond"), "EXP-7")["notes"]


def test_EXP7的上游是推導出來的_就地登記():
    """⚠️ `44` `EXP-7` 的來源欄沒有點名 `fund_profile`，是本組從「候選檔數」推回去的。"""
    assert logic.BLOCK_SOURCE_TABLES["EXP-7"] == ("fund_profile",)
    source = pathlib.Path(logic.__file__).read_text(encoding="utf-8")
    assert "這一列是推導出來的" in source, "這個推導沒有在程式碼裡登記"


def test_兩張表同時失敗時兩行各自帶自己的表名():
    """⛔ **2026-09-24 就地更正：這一條原本叫「同一句失敗訊息在同一塊只印一次」，

    而它自己斷言的是 `len(hits) == 2` —— 測試名與它的斷言方向相反。**
    同一輪也拿掉了 `source_error_lines()` 裡那句去重：每行都帶表名前綴，
    而同一塊的來源表名必不相同，**那個條件結構上永遠為假**
    （**本組實測**：`twofail` 回的兩行是 `nav：…` 與 `dividend：…`，**前綴必不相同**；
    「拿掉它 158 條全綠存活」那個數是**稽核**跑出來的，本組沒有重跑那一版）。

    **真的不變量是這一條**：兩張表同時失敗時，兩行**各自帶自己的表名**
    —— 那也是它們不會變成一模一樣的原因。拿掉表名前綴，本條轉紅。
    """
    dataset = fixtures.dataset_twofail()
    errors = {k: v for k, v in dataset["errors"].items() if v}
    assert len(errors) == 2, errors
    assert len(set(errors.values())) == 1, errors
    block = logic.find_block(_model("twofail"), "EXP-2")
    lines = [l for l in block["notes"] if fixtures.FETCH_FAIL_MESSAGE in l]
    assert len(lines) == 2, lines
    # ⛔ 兩行不得相同，而且**各自以自己的表名開頭**。
    assert len(set(lines)) == 2, lines
    for table in sorted(errors):
        assert any(line.startswith(f"{table}：") for line in lines), (table, lines)
    # 訊息原文照印（`44` 4.4：不改寫成安撫語句、不截斷）。
    for line in lines:
        assert line.endswith(fixtures.FETCH_FAIL_MESSAGE), line


def test_EXP2的配息佔淨值比不是算出來的_而且那件事有登記():
    """⛔ `E-05`：`44` 只給了欄名，**沒有給算式**（三件事一件都沒寫）。"""
    source = pathlib.Path(logic.__file__).read_text(encoding="utf-8")
    assert "E-05" in source
    fixture_source = pathlib.Path(fixtures.__file__).read_text(encoding="utf-8")
    assert "不自行選一種算法" in fixture_source
    # 值真的來自 fixtures，不是 logic 算的。
    dataset = fixtures.dataset_full()
    ratios = dataset["div_ratio_pct"]
    block = logic.find_block(_model("full"), "EXP-2")
    row = logic.find_row(block, "F0025")
    assert logic.format_pct(ratios["F0025"]) in row["_cells"]["div_ratio_pct"]["text"]


def test_EXP2缺淨值時配息佔淨值比跟著缺_那是本組的讀法():
    """⚠️ 欄名逐字是「佔淨值比」，分母就是淨值；**`44` 沒有明寫這個連動**。"""
    row = logic.find_row(logic.find_block(_model("full"), "EXP-2"), fixtures.NO_NAV_FUND)
    assert row["_cells"]["div_ratio_pct"]["text"] == "⬜"
    # 而那一檔的示意比值其實是有的 —— 所以這一格是被刻意留空的，不是沒資料。
    assert fixtures.dataset_full()["div_ratio_pct"][fixtures.NO_NAV_FUND] is not None


# ═════════════════════ 十、EXP-3 並排對照卡 ═════════════════════


def test_EXP3判準a_對照勾滿三檔之後第四個停用且有停用原因_而觀察清單仍可勾():
    """`44` `EXP-3` 判準第一分句（2026-09-22 改寫後那一句）。"""
    block = logic.find_block(_model("full"), "EXP-2")
    rows = block["_rows"]
    assert len(rows) >= 4, "候選不足四列 —— 這一條驗不到上限"
    fourth = rows[3]
    compare = fourth["_checkboxes"][logic.GROUP_COMPARE]
    watch = fourth["_checkboxes"][logic.GROUP_WATCH]
    assert compare["_enabled"] is False
    assert compare["disabled_reason"] == f"同時最多對照 {logic.COMPARE_LIMIT} 檔"
    assert compare["_visible"] is True  # `44` 5.3：停用時不隱藏
    assert watch["_enabled"] is True, "同一列的觀察清單那一組被上限拖累了"
    # 前三列（已勾的）沒有被停用。
    for row in rows[:3]:
        assert row["_checkboxes"][logic.GROUP_COMPARE]["_enabled"] is True


def test_EXP3上限本身_最多只對照三檔():
    """`44` `EXP-3` 規則欄逐字：「同時最多對照 3 檔」。"""
    model = _model("full", compare_checked=("F0025", "F0050", "F0055", "F0124", "F0127"))
    columns = logic.find_block(model, "EXP-3")["_columns"]
    assert len(columns) == logic.COMPARE_LIMIT == 3


def test_EXP3判準b_兩檔不同幣別並排_欄頭各自出現幣別字面值且沒有跨欄合計():
    """`44` `EXP-3` 判準第二分句。"""
    model = _model("mixedccy")
    block = logic.find_block(model, "EXP-3")
    columns = block["_columns"]
    assert len(columns) == 2, columns
    currencies = {c["_ccy"] for c in columns}
    assert len(currencies) == 2, currencies
    for column in columns:
        assert column["_ccy"] in column["head_text"], column["head_text"]
    # 沒有任何跨欄合計或差額：全頁的數都歸屬得到某一檔，而且幣別對得上。
    assert logic.cross_currency_nodes(model) == []
    # 而且卡上沒有「合計」「平均」「差額」這幾個字。
    for word in ("合計", "平均", "差額"):
        assert all(word not in str(v) for v in logic.collect_ui_strings(block)
                   if "跨欄不做" not in str(v)), word


def test_EXP3勾選為零時的文案逐字():
    block = logic.find_block(_model("nocond"), "EXP-3")
    assert block["notes"] == [logic.TEXT_PICK_THREE]
    assert block["_columns"] == []


def test_EXP3某檔某指標缺時該格為空方塊而同列其他欄照出():
    """`44` `EXP-3` 空狀態欄第二句。"""
    model = _model("full")  # `F0055` 在 `COMPARE_THREE` 裡、而且沒有 nav
    block = logic.find_block(model, "EXP-3")
    target = [c for c in block["_columns"] if c["_fund_code"] == fixtures.NO_NAV_FUND]
    assert target, [c["_fund_code"] for c in block["_columns"]]
    cells = target[0]["_cells"]
    assert cells["nav_orig_ccy"]["text"] == "⬜"
    # 同列其他欄照出：另外兩檔的那一列有數。
    others = [c for c in block["_columns"] if c["_fund_code"] != fixtures.NO_NAV_FUND]
    assert others
    assert all(c["_cells"]["nav_orig_ccy"]["_has_number"] for c in others)
    # 同一檔的其他列照出（經理費率不靠 nav）。
    assert cells["mgmt_fee_rate_pct"]["_has_number"] is True


def test_EXP3的指標列是沿用草稿的四列_就地登記():
    """⛔ `E-16`：`44` 的來源欄只寫「對應欄」，**沒有列出是哪幾個指標**。"""
    block = logic.find_block(_model("full"), "EXP-3")
    assert list(block["row_keys"]) == [k for k, _l in logic.COMPARE_ROWS]
    assert len(block["row_labels"]) == 4
    assert any("對應欄" in line for line in block["detail_lines"]), block["detail_lines"]
    assert any("最近淨值日" in line and "日期" in line for line in block["detail_lines"])


def test_EXP3卡上不標示哪一欄比較好():
    """`44` `EXP-3` 規則欄逐字最後一句。"""
    checked = 0
    for name, save_failed in _every_case():
        block = logic.find_block(_model(name, save_failed=save_failed), "EXP-3")
        # ⚠️ **母體是對照矩陣本身**（欄頭、列名、格內的值），**不含說明區** ——
        #    說明區那一行就是在複述 `44` 的禁令（「卡上不標示哪一欄比較好」），
        #    把它算進來，這一條會被自己的禁令字面推翻。
        strings = [c["head_text"] for c in block["_columns"]]
        strings += list(block["row_labels"])
        strings += [n["text"] for c in block["_columns"] for n in logic.value_nodes(c)]
        for word in ("較佳", "比較好", "勝出", "領先", "優於", "第一名", "★", "分"):
            assert all(word not in s for s in strings), (name, word, strings)
        checked += len(strings)
    assert checked > 0, "一個字串也沒收到 —— 這一條會變成空掃"


# ═════════════════════ 十一、EXP-4 欄位與排序設定 ═════════════════════


def test_EXP4判準a_取消全部欄位勾選_EXP2剩基金名一欄且出現那一行字():
    """`44` `EXP-4` 判準第一分句。"""
    model = _model("nocolumn")
    exp2 = logic.find_block(model, "EXP-2")
    assert list(exp2["column_keys"]) == [logic.ALWAYS_SHOWN_COLUMN]
    assert logic.TEXT_ONLY_FUND_NAME in logic.find_block(model, "EXP-2")["notes"]
    # 對照組：有勾欄位時不會出現那一行，欄位也不只一欄。
    assert logic.TEXT_ONLY_FUND_NAME not in logic.find_block(_model("full"), "EXP-2")["notes"]
    assert len(logic.find_block(_model("full"), "EXP-2")["column_keys"]) == 5


def test_EXP4判準b_排序欄被取消勾選_排序回到不排序且出現說明文字():
    """`44` `EXP-4` 判準第二分句。"""
    model = _model("sortdropped")
    block = logic.find_block(model, "EXP-4")
    assert block["sort_shown"] == logic.TEXT_NO_SORT
    assert any(logic.TEXT_NO_SORT in note for note in block["notes"]), block["notes"]
    # 而且 `EXP-2` 真的沒有依那一欄排（它照 fund_code 字面值）。
    codes = [r["_fund_code"] for r in logic.find_block(model, "EXP-2")["_rows"]]
    assert codes == sorted(codes)
    # 前提釘住：那一鍵的已存值確實指到一個沒被勾的欄。
    dataset = fixtures.dataset_sortdropped()
    assert logic.saved_sort_column(dataset) == "nav_orig_ccy"
    assert "nav_orig_ccy" not in logic.saved_columns(dataset)


def test_EXP4判準c_一枚按鈕同時寫兩鍵_不拆成兩枚():
    """`44` `EXP-4` 規則欄逐字 ＋ 判準第三分句。"""
    block = logic.find_block(_model("full"), "EXP-4")
    saves = [b for b in block["buttons"] if b["_action_kind"] == "存檔"]
    assert len(saves) == 1, saves
    assert block["_save_keys"] == ("exp_visible_columns", "exp_sort_column")
    dataset = fixtures.dataset_sortnav()
    for key in block["_save_keys"]:
        assert logic.setting_updated_at(dataset, key), key


def test_EXP4判準d_存檔不寫那四張唯讀表():
    block = logic.find_block(_model("full"), "EXP-4")
    for button in block["buttons"]:
        assert not (button["_writes"] & set(logic.READONLY_TABLES)), button


def test_EXP4排序下拉不預先選定任何一欄():
    """`44` `EXP-4` 規則欄（2026-09-21 改寫後那一句）。"""
    block = logic.find_block(_model("nocond"), "EXP-4")
    assert block["sort_shown"] == logic.TEXT_NO_SORT
    assert block["sort_options"][0] == logic.TEXT_NO_SORT
    assert len(block["sort_options"]) == len(logic.COLUMN_ORDER) + 1


def test_EXP4可選欄位清單就是EXP2規則欄那五欄():
    """`44` `EXP-4` 規則欄（2026-09-23 新增那一句）。"""
    block = logic.find_block(_model("full"), "EXP-4")
    assert [o["_column"] for o in block["_options"]] == list(logic.COLUMN_ORDER)
    assert len(block["_options"]) == 5
    # 勾選框不算「欄」—— 所以這份清單不多出兩項（`44` `EXP-2` 塊下方那一筆待裁決）。
    assert "對照" not in [o["label"] for o in block["_options"]]
    assert "觀察清單" not in [o["label"] for o in block["_options"]]


def test_基金名那一欄是全不勾時的退路_不是永遠顯示():
    """⛔ **2026-09-24 就地更正：這一條原本叫「基金名勾與不勾對 EXP2 沒有差別」，那是假的。**

    **四行就看得出來（我自己重跑的）**：
    `columns=()` → `['fund_name']`；`('fund_name',)` → `['fund_name']`；
    **`('ccy',)` → `['ccy']`（基金名不見了）**；`('fund_name','ccy')` → `['fund_name','ccy']`。
    程式是 `... or [ALWAYS_SHOWN_COLUMN]` —— **那是全不勾時的退路，不是「永遠顯示」**。
    **舊表述只在一個角落成立**，而我把它寫成全稱句，還一路寫進註解、docstring 與測試名三處，
    測試也只覆蓋了那個角落。**這一條現在把四種組合都驗完。**
    """
    def cols(columns):
        model = logic.build_page_model(
            fixtures._dataset(rules=fixtures.RULES_THREE, columns=columns))
        return list(logic.find_block(model, "EXP-2")["column_keys"])

    assert cols(()) == ["fund_name"]
    assert cols(("fund_name",)) == ["fund_name"]
    # ⛔ 這一列就是舊表述被推翻的地方。
    assert cols(("ccy",)) == ["ccy"], "基金名應該在這裡消失 —— 它不是永遠顯示"
    assert cols(("fund_name", "ccy")) == ["fund_name", "ccy"]
    assert cols(("ccy", "nav_date")) == ["ccy", "nav_date"]
    # 成立的版本：**其他欄一個都沒勾時**，勾它與不勾它一樣。
    assert cols(()) == cols(("fund_name",))
    # 它確實在可選清單裡（所以那個框真的會動）。
    model = logic.build_page_model(fixtures._dataset(rules=fixtures.RULES_THREE, columns=("ccy",)))
    assert logic.ALWAYS_SHOWN_COLUMN in [o["_column"] for o in logic.find_block(model, "EXP-4")["_options"]]
    source = pathlib.Path(logic.__file__).read_text(encoding="utf-8")
    assert "那是全不勾時的退路，不是「永遠顯示」" in source, "這個更正沒有在程式碼裡登記"


def test_未設定與設成空在本頁畫起來一樣_就地登記():
    """⚠️ `44` 4.5 把「未設定」與「設成空」寫成同一件事（`setting_value` 為空），

    而 `EXP-4` 空狀態欄只寫了「欄位一個也沒勾」那一種。**兩者在本頁畫起來一樣。**
    ⛔ 本頁照 `44` 的字走，**不自行替「未設定」另立一種畫面**。
    """
    unset = fixtures._dataset(rules=fixtures.RULES_THREE, columns=None)
    empty = fixtures._dataset(rules=fixtures.RULES_THREE, columns=())
    assert logic.setting_value(unset, "exp_visible_columns") is None
    assert logic.setting_value(empty, "exp_visible_columns") == []
    assert logic.saved_columns(unset) == logic.saved_columns(empty) == ()
    for code in ("EXP-2", "EXP-4"):
        a = logic.find_block(logic.build_page_model(unset), code)
        b = logic.find_block(logic.build_page_model(empty), code)
        assert a["notes"] == b["notes"], (code, a["notes"], b["notes"])
    source = pathlib.Path(logic.__file__).read_text(encoding="utf-8")
    assert "把「未設定」與「設成空」寫成同一件事" in source


def test_對照上限的停用推廣到超過四列_歸屬就地更正():
    """⛔ **2026-09-24 就地更正歸屬：這一條原本叫「那一步是本組做的」，把授權寫小了。**

    `44` `EXP-3` 空狀態欄逐字是「該組的**第 4 個**勾選框停用」（單數），而清單可以超過四列。
    ✅ **推廣不是本組發明的** —— **已拍板草稿 `ui_prototype_exp.html` 的渲染碼就是同一條規則**
    （實讀：`var cOver = (!cOn && cmp.length >= 3);`，不是舊版的 `i === 3`），
    而該檔就地寫著「**這是照 `44` 修正，不是新設計**」。
    ⚠️ 我實讀到的授權字樣：那一筆的就地回修註記寫「決策者：AI 總管」，
    而它所在的第十六輪整輪是「客戶拍板草稿後併入」。**只寫讀到的，不替它歸給客戶。**
    ✅ 而且推廣是**唯一與 `44` 自洽**的讀法：只停第 4 列、留第 5 列可按，
    使用者按下去就會有 4 檔被勾 —— 違反同一格逐字的「同時最多對照 3 檔」。
    """
    block = logic.find_block(_model("full"), "EXP-2")
    rows = block["_rows"]
    assert len(rows) == 5, "候選不是五列，這一條就驗不到「第 5 個怎麼辦」"
    states = [r["_checkboxes"][logic.GROUP_COMPARE]["_enabled"] for r in rows]
    assert states == [True, True, True, False, False], states
    # 草稿的渲染碼真的是同一條規則（不是 `i === 3`）。
    draft = (_ROOT / "docs" / "v2" / "prototype" / "ui_prototype_exp.html").read_text(encoding="utf-8")
    assert "var cOver = (!cOn && cmp.length >= 3);" in draft
    # ⛔ **斷言要釘在「那一句話本身」，不是釘在它附近還會出現的詞。**
    #    本輪第一版斷言的是 `"已拍板草稿" in source and "cOver" in source` ——
    #    而把歸屬改回「本組發明的」的突變**只換掉那一行**，那兩個詞在後面幾行照樣在，
    #    於是那個突變全綠存活。
    source = pathlib.Path(logic.__file__).read_text(encoding="utf-8")
    assert "✅ **這不是本組發明的**" in source, "歸屬更正那一句不見了"
    assert "`44` 沒有逐字寫這一步" not in source, (
        "被更正掉的舊歸屬又回來了 —— 它把本頁的授權寫小了")


def test_可選欄位五項比已拍板草稿多一項_而那一句的決策者是總管不是客戶():
    """⚠️ **這一筆是要讓客戶看見的，不是內部備忘。**

    已拍板草稿 §H `T-09` 逐字「可選欄位**四項**」並寫明「取 `EXP-2` 那五欄**扣掉「基金名」**」。
    本頁是**五項**，依據是 `44` `EXP-4` 2026-09-23 那一句（母體＝五欄，含基金名）。
    ⛔ **而 `44` 自己把那一句標成「決策者：AI 總管，本輪派工指定」** —— **不是客戶裁的**。
    ⇒ 相對於客戶拍過的那張圖，**「基金名進入勾選集」是一次視覺元件增加**，
    授權來自總管的一筆派工指定。本頁照 `44` 做（44 是 SSOT），但這個事實不得被寫成「草稿沒跟上」了事。
    """
    assert len(logic.COLUMN_ORDER) == 5
    assert logic.ALWAYS_SHOWN_COLUMN in logic.COLUMN_ORDER
    # `44` 那一句的決策者確實是總管。
    text = _D44.read_text(encoding="utf-8")
    clause = text.split("可選欄位清單取")[1][:300]
    assert "決策者：AI 總管，本輪派工指定" in clause, clause[:160]
    # 草稿確實寫四項、且確實是扣掉基金名。
    draft = (_ROOT / "docs" / "v2" / "prototype" / "ui_prototype_exp.html").read_text(encoding="utf-8")
    assert "扣掉「基金名」" in draft
    # 其餘四項的相對順序與草稿相同（沒有順手重排）。
    assert [c for c in logic.COLUMN_ORDER if c != logic.ALWAYS_SHOWN_COLUMN] == [
        "ccy", "nav_date", "nav_orig_ccy", "div_ratio_pct"]
    source = pathlib.Path(logic.__file__).read_text(encoding="utf-8")
    assert "不是客戶裁的" in source, "這個關鍵事實沒有在程式碼裡登記"


def test_EXP4把兩個44沒解的缺口寫在畫面上():
    """⛔ `E-07`（排列依據）與 `E-17`（`value_kind` 六種都對不上）。"""
    lines = logic.find_block(_model("full"), "EXP-4")["detail_lines"]
    assert any("欄位名字面值" in line for line in lines), lines
    assert any("value_kind" in line for line in lines), lines
    # `E-17` 的前提釘住：那一鍵的 `value_kind` 真的不在封閉六種裡。
    row = logic._setting(fixtures.dataset_full(), "exp_sort_column")
    assert row["value_kind"] not in logic.VALUE_KINDS


def test_EXP4存檔寫入失敗_當下值留在畫面上且EXP2顯示的欄與排序不變():
    """`44` `EXP-4` 空狀態欄第三句。"""
    plain = _model("sortnav")
    failed = _model("sortnav", save_failed=True)
    block = logic.find_block(failed, "EXP-4")
    assert block["error_lines"]
    assert any(fixtures.SAVE_FAIL_MESSAGE in line for line in block["error_lines"])
    assert block["sort_shown"] == logic.find_block(plain, "EXP-4")["sort_shown"]
    assert [o["_checked"] for o in block["_options"]] == [
        o["_checked"] for o in logic.find_block(plain, "EXP-4")["_options"]
    ]
    assert logic.find_block(failed, "EXP-2")["column_keys"] == logic.find_block(plain, "EXP-2")["column_keys"]
    # 兩鍵一成一敗那一題 `44` 沒有寫 —— 畫面上要寫出來。
    # ⛔ **2026-09-24：那一句自本輪起住在 `save_fail_notes`，不在 `error_lines`。**
    #    理由是「一個鍵不裝兩種東西」（同 `fetch_fail_lines` 拆出來的理由）——
    #    `error_lines` 原本同時裝**真的失敗訊息**與**一句登記註記**，
    #    於是 `len(error_lines)` 對 `EXP-4` 會被讀成「兩個失敗框」。
    assert any("兩鍵" in line for line in block["save_fail_notes"]), block["save_fail_notes"]
    # 拆完之後 `error_lines` 只剩失敗訊息本身 ⇒ 現在數長度也是對的。
    assert len(block["error_lines"]) == 1, block["error_lines"]
    assert all("兩鍵" not in line for line in block["error_lines"])


# ═════════════════════ 十二、EXP-5 加入觀察清單 ═════════════════════


def test_EXP5判準a_按下之後holding表的列數與按下之前相同():
    """`44` `EXP-5` 判準第一分句 ＋ 規則欄「不寫入 `holding`」。"""
    block = logic.find_block(_model("full"), "EXP-5")
    assert len(block["buttons"]) == 1
    assert block["buttons"][0]["_writes"] == {"user_setting"}
    assert "holding" not in block["buttons"][0]["_writes"]


def test_EXP5判準b_同一檔按兩次_觀察清單裡該代碼只出現一次():
    """`44` `EXP-5` 判準第二分句。"""
    model = _model("watchall")  # 勾起來的那幾檔已經都在清單裡
    block = logic.find_block(model, "EXP-5")
    after = block["_after"]
    assert len(after) == len(set(after)), after
    for code in fixtures.WATCH_TWO:
        assert after.count(code) == 1, (code, after)
    # 而且前提成立：那幾檔本來就在清單裡（否則這一條驗不到去重）。
    watchlist = logic.saved_watchlist(fixtures.dataset_watchall())
    assert set(fixtures.WATCH_TWO) <= set(watchlist)


def test_EXP5判準c_對照勾滿三檔之後第四檔仍然加得進觀察清單():
    """`44` `EXP-5` 判準第三分句 —— **兩組不共用之後才成立的那個畫面**。"""
    model = _model("full")
    exp2 = logic.find_block(model, "EXP-2")
    fourth = exp2["_rows"][3]["_fund_code"]
    assert exp2["_rows"][3]["_checkboxes"][logic.GROUP_COMPARE]["_enabled"] is False
    assert fourth in fixtures.WATCH_TWO, fourth
    assert fourth in logic.find_block(model, "EXP-5")["_after"], fourth


def test_EXP5判準d_存檔之後那一鍵updated_at非空且重載後逐字相同():
    dataset = fixtures.dataset_watchall()
    assert logic.setting_updated_at(dataset, "exp_watchlist")
    assert tuple(logic.saved_watchlist(dataset)) == tuple(fixtures.surviving_codes())
    block = logic.find_block(_model("full"), "EXP-5")
    for button in block["buttons"]:
        assert not (button["_writes"] & set(logic.READONLY_TABLES))


def test_EXP5勾選為零時按鈕停用且停用原因逐字():
    """`44` `EXP-5` 空狀態欄第一句。"""
    block = logic.find_block(_model("nowatch"), "EXP-5")
    assert block["buttons"][0]["_enabled"] is False
    assert block["buttons"][0]["disabled_reason"] == logic.TEXT_NO_PICK
    # 有勾的時候是可按的（否則這一條分不出差別）。
    assert logic.find_block(_model("full"), "EXP-5")["buttons"][0]["_enabled"] is True


def test_EXP5已在觀察清單的那一檔_觀察清單那一組顯示已在觀察清單而對照那一組不受影響():
    """`44` `EXP-5` 空狀態欄第二句（2026-09-22 改寫後那一句）。"""
    model = _model("full")
    row = logic.find_row(logic.find_block(model, "EXP-2"), "F0050")
    assert "F0050" in logic.saved_watchlist(fixtures.dataset_full())
    assert row["_checkboxes"][logic.GROUP_WATCH]["note"] == logic.TEXT_ALREADY_WATCHED
    assert row["_checkboxes"][logic.GROUP_COMPARE]["_enabled"] is True
    assert row["_checkboxes"][logic.GROUP_COMPARE]["note"] == ""
    # 不在清單裡的那幾檔沒有那一句。
    other = logic.find_row(logic.find_block(model, "EXP-2"), "F0025")
    assert other["_checkboxes"][logic.GROUP_WATCH]["note"] == ""


def test_EXP5的按鈕標籤與action_kind是兩個不同的參數():
    """`44` `EXP-5` 塊下方逐字說明的那件事。"""
    button = logic.find_button(_model("full"), logic.TEXT_ADD_WATCH)
    assert button["label"] == "加入觀察清單"
    assert button["_action_kind"] == "存檔"


def test_EXP5按鈕停用時不出存檔失敗框_而且那是本組挑的一邊_有寫在畫面上():
    block = logic.find_block(_model("nowatch", save_failed=True), "EXP-5")
    assert block["error_lines"] == []
    assert any("停用" in line and "失敗" in line for line in block["detail_lines"]), block["detail_lines"]
    # 可按的時候就會出。
    assert logic.find_block(_model("full", save_failed=True), "EXP-5")["error_lines"]


# ═════════════════════ 十三、EXP-6 單檔基礎資料 ═════════════════════


def test_EXP6判準a_某欄清空該欄顯示空方塊而不是0或無():
    """`44` `EXP-6` 判準第一分句 ＋ `44` 4.6 表判準。"""
    block = logic.find_block(_model("nofee"), "EXP-6")
    assert block["_fund_code"] == fixtures.NO_FEE_FUND
    fee = [n for n in block["_fields"] if "mgmt_fee_rate_pct" in n["label"]]
    assert len(fee) == 1, block["_fields"]
    assert fee[0]["text"] == "⬜"
    assert fee[0]["text"] not in ("0", "0.00%", "無")
    # 其他五欄照出（否則這一條分不出「整塊都空」）。
    others = [n for n in block["_fields"] if "mgmt_fee_rate_pct" not in n["label"]]
    assert len(others) == 5
    assert all(n["text"] != "⬜" for n in others)


def test_EXP6判準b_不存在的代碼顯示查無此fund_code而不是空白區塊():
    """`44` `EXP-6` 判準第二分句。"""
    block = logic.find_block(_model("unknownfund"), "EXP-6")
    assert block["_fund_code"] == fixtures.MISSING_FUND_CODE
    assert logic.TEXT_NO_SUCH_FUND in block["notes"]
    assert block["_empty_kind"] == logic.EMPTY_SOURCE
    assert block["summary_text"] == logic.TEXT_NO_SUCH_FUND
    assert block["_fields"] == []
    # 前提釘住：那個代碼真的不在 `fund_profile` 裡。
    assert logic.profile_of(fixtures.dataset_unknownfund(), fixtures.MISSING_FUND_CODE) is None


def test_EXP6只畫44規則欄列的六欄_不自行加nav或dividend的格():
    """⛔ `E-11`：來源欄取了那兩張表，而規則欄列的六欄全部來自 `fund_profile`。"""
    block = logic.find_block(_model("full"), "EXP-6")
    assert [n["label"] for n in block["_fields"]] == [label for _k, label in logic.EXP6_FIELDS]
    assert len(block["_fields"]) == 6
    assert any("nav" in line and "dividend" in line for line in block["detail_lines"])


def test_EXP6顯示的是對照那一組勾起的第一檔_而且那是本組挑的():
    """⛔ `E-10`：`44` 的來源欄沒有說是哪一檔，而它的判準又要一個輸入位置。"""
    assert logic.exp6_fund_code(("F0050", "F0025")) == "F0025"
    assert logic.exp6_fund_code(()) is None
    block = logic.find_block(_model("full"), "EXP-6")
    assert block["_fund_code"] == sorted(fixtures.COMPARE_THREE)[0]
    assert any("層 4" in line for line in block["detail_lines"]), block["detail_lines"]
    # 一檔也沒勾時不硬挑一檔。
    empty = logic.find_block(_model("nocond"), "EXP-6")
    assert empty["_fund_code"] is None
    assert empty["_fields"] == []


def test_EXP6欄位值原樣顯示_dist與accum不翻成中文():
    """`44` `EXP-6` 規則欄逐字：「欄位值原樣顯示，不做任何換算與四捨五入以外的加工」。"""
    block = logic.find_block(_model("full"), "EXP-6")
    policy = [n for n in block["_fields"] if "dividend_policy" in n["label"]]
    assert len(policy) == 1
    assert policy[0]["text"] in ("dist", "accum"), policy[0]["text"]
    assert "配息" not in policy[0]["text"] and "累積" not in policy[0]["text"]


# ═════════════════════ 十四、EXP-7 篩選軌跡 ═════════════════════


def test_EXP7判準a_最後一列的套用後檔數與EXP0的N相等():
    """`44` `EXP-7` 判準第一分句。

    ⛔ **2026-09-24 就地更正兩件事**：
    (1) docstring 原寫「**十八個**情境」，而當時已經是 19（現在更多）—— **會漂移的數不寫進 docstring**。
    (2) 本條對「沒有軌跡列」的情境 `continue`，所以它**驗不到全部的格**。
        原本只寫 `checked >= 30` 這種下限，**看不出漏掉的是哪幾個、為什麼可以漏**。
        現在**逐一列出跳過的情境並說明理由**，而且要求「跳過的那幾個真的沒有軌跡列」。
    """
    checked, skipped = 0, []
    for name, save_failed in _every_case():
        model = _model(name, save_failed=save_failed)
        rows = logic.find_block(model, "EXP-7")["_rows"]
        if not rows:
            # 沒有條件列（或上游掛掉）→ 本來就沒有「最後一列」可以比。
            skipped.append((name, save_failed))
            continue
        expected = len(logic.find_block(model, "EXP-2")["_rows"])
        assert rows[-1]["_after"] == expected, (name, save_failed, rows[-1]["_after"], expected)
        assert rows[-1]["after_text"] == logic.hinted(logic.format_count(expected))
        checked += 1
    total = len(fixtures.ALL_SCENARIO_NAMES) * len(fixtures.SAVE_FAIL_CHOICES)
    assert checked + len(skipped) == total, (checked, len(skipped), total)
    # 被跳過的必須全部是「本來就沒有軌跡列」的那幾種，不能有別的混進來。
    skipped_names = {name for name, _sf in skipped}
    assert skipped_names <= {"nocond", "profilefail", "profilefail_picked"}, skipped_names
    for name in skipped_names:
        block = logic.find_block(_model(name), "EXP-7")
        assert block["_rows"] == [], name
        assert block["notes"], (name, "沒有軌跡列卻也什麼都沒說")
    assert checked >= total - 2 * len(skipped_names), (checked, skipped_names)


def test_EXP7判準b_數值清空那一列前後檔數相等且列尾寫未生效():
    """`44` `EXP-7` 判準第二分句。"""
    rows = logic.find_block(_model("blankvalue"), "EXP-7")["_rows"]
    assert len(rows) == 4
    blank = rows[-1]
    assert blank["_before"] == blank["_after"], blank
    assert blank["tail_text"] == logic.TEXT_NOT_EFFECTIVE
    # 生效的那幾列真的把檔數砍下來了（否則「相等」這件事驗不出差別）。
    effective = rows[:-1]
    assert any(r["_before"] != r["_after"] for r in effective), effective


def test_EXP7一列一條條件_順序照使用者新增的順序():
    """`44` `EXP-7` 規則欄逐字。"""
    rows = logic.find_block(_model("full"), "EXP-7")["_rows"]
    assert len(rows) == len(fixtures.RULES_THREE)
    for row, rule in zip(rows, fixtures.RULES_THREE):
        assert row["condition_text"] == logic.rule_text(rule)
    # 相鄰兩列銜接得上：上一列的套用後 ＝ 下一列的套用前。
    for previous, nxt in zip(rows, rows[1:]):
        assert previous["_after"] == nxt["_before"], (previous, nxt)


def test_EXP7條件一列也沒有時的文案與種類名_就地登記那個落差():
    """⛔ `E-12` 還開著的那一半：`44` 把一個「使用者還沒輸入」的畫面掛上 `來源缺`。"""
    block = logic.find_block(_model("nocond"), "EXP-7")
    assert block["notes"] == [logic.TEXT_NO_CONDITION]
    assert block["_empty_kind"] == logic.EMPTY_SOURCE  # 照 `44` 逐字，不自訂種類名
    assert any("來源缺" in line for line in block["detail_lines"]), block["detail_lines"]


def test_EXP7的三欄欄名():
    """`44` `EXP-7` 規則欄逐字「三欄：條件文字、套用前檔數、套用後檔數」。"""
    block = logic.find_block(_model("full"), "EXP-7")
    assert block["column_labels"] == ("條件", "套用前", "套用後")


# ═════════════════════ 十五、條件比較：不替 `44` 選缺值算不算過 ═════════════════════


def test_缺值進條件比較時直接炸掉_不靜默選一邊():
    """⛔ `E-09`：`44` **沒有寫**缺值在條件比較中算通過還是不通過。

    §1 Fail Loud：一個靜默的選擇會讓 `EXP-7` 的檔數與 `EXP-0` 的 N 悄悄對不起來。

    ⛔ **2026-09-24 稽核抓到的洞：這一條原本只用「小於」一個方向。**
    而「小於」**拿掉這道守衛也還是會炸** —— 它會掉進 `float(None)` 的 `except`，
    炸在**另一道**守衛上。於是 `pytest.raises` 照過，**這道守衛其實沒有被驗到**。
    稽核實測：把 `if left is None: raise` 整段關掉，六個方向裡
    **「等於→False、不等於→True、早於或等於→False、晚於→True」四個靜默選邊**，
    而整套測試 **131 passed、零紅**。
    ⇒ **一道寫著「炸掉比較誠實」的 §1 承重守衛，可以整個拿掉而全綠。**

    **現在改成逐方向釘**（體例比照隔壁 `test_六個比較方向的語意逐個釘住_含邊界`
    已經做對的封閉集寫法）：六個方向**每一個**都要因為**這道**守衛而炸，
    並斷言覆蓋到的方向集合 **等於** `fixtures.OPERATORS`（少一個就紅）。
    """
    # 逐方向：缺值進來，六個方向都必須炸在「這道」守衛上。
    covered = set()
    for op in fixtures.OPERATORS:
        with pytest.raises(logic.UnspecifiedComparison) as caught:
            logic._compare(None, op, "1.0")
        # ⛔ 關鍵：要炸在**缺值**那道，不是 `float()` 那道 —— 否則「小於」那種
        #    「換個理由照樣炸」的情形會讓這一條看起來有效、實際沒驗到東西。
        assert "欄位值為空" in str(caught.value), (op, str(caught.value))
        covered.add(op)
    assert covered == set(fixtures.OPERATORS), "有方向沒被驗到"

    # 同一件事走**真的篩選那條路**（不是只有單元層）。
    rows = [{"fund_code": "X", "mgmt_fee_rate_pct": None}]
    for op in fixtures.OPERATORS:
        with pytest.raises(logic.UnspecifiedComparison):
            logic.apply_rules(rows, [{"field": "mgmt_fee_rate_pct", "op": op, "value": "1.0"}])

    # 有值的時候照常比。
    rows2 = [{"fund_code": "X", "mgmt_fee_rate_pct": 0.5}]
    steps = logic.apply_rules(rows2, [{"field": "mgmt_fee_rate_pct", "op": "小於", "value": "1.0"}])
    assert steps[-1][2] == 1


def test_示意條件刻意只用可空為否的欄位_讓那一題不被偷偷決定掉():
    """⛔ 承上：所有會真的跑起來的示意條件，用的欄位在 `44` 4.6 都是「可空：否」。"""
    nullable = {"mgmt_fee_rate_pct"}
    used = set()
    for name in fixtures.ALL_SCENARIO_NAMES:
        dataset = fixtures.scenario(name)["dataset"]
        for rule in logic.saved_rules(dataset):
            if logic.rule_is_effective(rule):
                used.add(rule["field"])
    assert used, "一條生效條件也沒有 —— 這一條會變成空掃"
    assert not (used & nullable), used
    # 那個留空的、用到可空欄位的條件，**刻意不生效**（所以不會撞到上面那個例外）。
    blank = [r for r in fixtures.RULES_WITH_BLANK if not logic.rule_is_effective(r)]
    assert len(blank) == 1 and blank[0]["field"] in nullable, blank


def test_六個比較方向的語意逐個釘住_含邊界():
    """⛔ **2026-09-24 突變測試抓到的洞：本條的第一版只驗「回傳值是 bool」。**

    於是把「早於或等於」的 `<=` 改成 `<`（**漏掉等於那一邊**）之後，
    **157 條全綠存活** —— 因為示意資料裡沒有任何一檔的 `inception_on` 剛好等於條件的日期。
    ⇒ **一個只驗型別的測試，等於沒有驗。** 現在逐個方向、逐個邊界釘死。
    """
    cases = [
        # (左, 方向, 右, 期望)
        ("A", "等於", "A", True), ("A", "等於", "B", False),
        ("A", "不等於", "B", True), ("A", "不等於", "A", False),
        ("2", "大於", "1", True), ("1", "大於", "1", False), ("0", "大於", "1", False),
        ("0", "小於", "1", True), ("1", "小於", "1", False), ("2", "小於", "1", False),
        # ⛔ 這兩列就是突變活下來的那個邊界。
        ("2020-01-01", "早於或等於", "2020-01-01", True),
        ("2019-12-31", "早於或等於", "2020-01-01", True),
        ("2020-01-02", "早於或等於", "2020-01-01", False),
        ("2020-01-02", "晚於", "2020-01-01", True),
        ("2020-01-01", "晚於", "2020-01-01", False),
        ("2019-12-31", "晚於", "2020-01-01", False),
    ]
    assert {op for _l, op, _r, _e in cases} == set(fixtures.OPERATORS), "有方向沒被驗到"
    for left, op, right, expected in cases:
        assert logic._compare(left, op, right) is expected, (left, op, right, expected)
    # 數值比較用的是**數**不是字串（`"10" < "9"` 在字串上成立，在數上不成立）。
    assert logic._compare("10", "大於", "9") is True
    # 沒有第七個方向。
    with pytest.raises(logic.UnspecifiedComparison):
        logic._compare("A", "包含", "A")
    # 「大於／小於」碰到轉不成數的值 → 炸，不靜默選一邊。
    with pytest.raises(logic.UnspecifiedComparison):
        logic._compare("dist", "大於", "1")


def test_早於或等於的等號那一邊在真的篩選裡也走得到():
    """⛔ 承上：光有單元測試還不夠 —— **條件套用那條路**也要真的踩到等號那一邊。"""
    rows = [
        {"fund_code": "ON", "inception_on": "2014-12-31"},   # 剛好等於門檻
        {"fund_code": "BEFORE", "inception_on": "2014-12-30"},
        {"fund_code": "AFTER", "inception_on": "2015-01-01"},
    ]
    rule = {"field": "inception_on", "op": "早於或等於", "value": "2014-12-31"}
    kept = [r["fund_code"] for r in logic.apply_rules(rows, [rule])[-1][3]]
    assert kept == ["ON", "BEFORE"], kept


def test_fixtures濾出來的那一份與logic濾出來的一致():
    """`fixtures.surviving_codes()` 與 `logic.apply_rules()` 是同一套語意的兩份實作 —— 要對得上。"""
    expected = fixtures.surviving_codes()
    assert expected, "一檔也沒留下 —— 這一條會變成空掃"
    steps = logic.apply_rules(fixtures._universe(), fixtures.RULES_THREE)
    got = [row["fund_code"] for row in steps[-1][3]]
    assert got == expected, (got, expected)


# ═════════════════════ 十六、示意值標記 ═════════════════════


def test_每一個會隨資料變的數都帶示意兩個字():
    """已拍板草稿 §A 的分界：會隨資料變的數要標，`44` 逐字訂死的常數不標。"""
    for name, save_failed in _every_case():
        model = _model(name, save_failed=save_failed)
        numbers = logic.numeric_nodes(model)
        if not numbers:
            continue
        for node in numbers:
            assert logic.HINT in node["text"], (name, node["label"], node["text"])
    assert logic.numeric_nodes(_model("full")), "全頁一個數也沒有 —— 上面那一圈會變成空掃"


def test_44逐字訂死的常數不帶示意():
    """上限 3 檔與「近 12 個月」是規格不是資料 —— 標上（示意）反而會讓客戶以為連上限都還沒定。"""
    assert logic.COMPARE_LIMIT == 3
    assert logic.DIVIDEND_WINDOW_MONTHS == 12
    text = logic.TEXT_PICK_THREE
    assert "3" in text and logic.HINT not in text
    assert logic.HINT not in logic.COLUMN_LABELS["div_ratio_pct"]


# ═════════════════════ 十七、前向釘樁：整頁逐格 ═════════════════════


def _cell_digest(block) -> str:
    """一塊模型的全格摘要（正規化方式與產生期望值時逐字相同）。"""

    def scrub(obj):
        if isinstance(obj, dict):
            return {k: scrub(v) for k, v in sorted(obj.items())}
        if isinstance(obj, (list, tuple)):
            return [scrub(v) for v in obj]
        if isinstance(obj, set):
            return sorted(scrub(v) for v in obj)
        if obj is None or isinstance(obj, (str, int, float, bool)):
            return obj
        return repr(obj)

    blob = json.dumps(scrub(block), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def _dump_grid():
    """現行行為逐格 dump。**產生期望值用的就是這一支**，所以兩邊的正規化必然一致。"""
    out = {}
    for name, save_failed in _every_case():
        model = _model(name, save_failed=save_failed)
        for block in model["blocks"]:
            key = f"{name}|{int(save_failed)}|{block['code']}"
            out[key] = (block["_tone"], block["_state"], _cell_digest(block))
    return out


def test_前向釘樁_整頁逐格釘住():
    """⛔ **這是一張新頁，沒有「之前」可以比，所以這不叫反向控制。據實寫明。**

    它是**前向釘樁**：把現行行為整頁逐格釘住，往後任何一次無意的改動都會紅。
    **期望值的正確性由上面那幾十條正控背書，不由這一條自己背書。**

    ⚠️ 每一格比三樣：`_tone`、`_state`、以及**整塊模型的摘要**。
       只比前兩樣的話，一個「不改狀態、只改文案」的改動會全綠溜過去
       （姊妹頁實測過：把說明文案改一個詞，只比 `_tone`／`_state` 是綠的、加了摘要才轉紅）。
    ⚠️ 摘要對不上時看不出**哪裡**不同 —— 代價就地寫明：
       重跑一次 `_dump_grid()` 再 diff，**不要直接改期望值**。期望值改了，這條就廢了。
    """
    expected = _EXPECTED_GRID
    got = _dump_grid()
    assert set(expected) == set(got), (
        "格子的集合變了（多了或少了情境／塊）：\n"
        f"  少了：{sorted(set(expected) - set(got))}\n"
        f"  多了：{sorted(set(got) - set(expected))}"
    )
    assert len(expected) == len(fixtures.ALL_SCENARIO_NAMES) * 2 * 8, len(expected)
    for key in sorted(expected):
        assert got[key] == expected[key], (
            key, "整格內容變了", got[key], expected[key])


def test_前向釘樁那張網真的蓋到每一個情境與每一塊():
    """⛔ 一張漏了情境的網，會讓新做出來的畫面「沒有人看著」。"""
    keys = set(_EXPECTED_GRID)
    names = {k.split("|")[0] for k in keys}
    codes = {k.split("|")[2] for k in keys}
    flags = {k.split("|")[1] for k in keys}
    assert names == set(fixtures.ALL_SCENARIO_NAMES), names ^ set(fixtures.ALL_SCENARIO_NAMES)
    assert codes == set(logic.BLOCK_TITLES), codes ^ set(logic.BLOCK_TITLES)
    assert flags == {"0", "1"}, flags


# ═════════════════════ 十八、情境註冊表與名字集合 ═════════════════════


def test_情境表與ALL_SCENARIO_NAMES不得漂移():
    """`fixtures.scenario()` 內部那一行 assert 已經擋了一半；這一條從外面再擋一次。"""
    assert len(fixtures.ALL_SCENARIO_NAMES) == len(set(fixtures.ALL_SCENARIO_NAMES))
    for name in fixtures.ALL_SCENARIO_NAMES:
        assert "dataset" in fixtures.scenario(name), name
    with pytest.raises(KeyError):
        fixtures.scenario("沒有這個情境")


def test_每一個情境都有一個給人看的標籤():
    assert set(fixtures.SCENARIO_LABELS) == set(fixtures.ALL_SCENARIO_NAMES)


def test_存檔失敗開關是正交的_不是多出來的一種情境():
    assert fixtures.SAVE_FAIL_CHOICES == (False, True)
    for name in fixtures.ALL_SCENARIO_NAMES:
        plain = fixtures.scenario(name)
        failed = fixtures.with_save_failure(plain)
        assert not plain["dataset"].get("save_errors"), name
        assert failed["dataset"]["save_errors"], name
        # 疊開關不改原來那一份，也不改資料本身（同一個 list 物件）。
        assert not plain["dataset"].get("save_errors"), name
        assert plain["dataset"]["fund_profile"] is failed["dataset"]["fund_profile"], name
        assert set(failed["dataset"]["save_errors"]) == set(fixtures.SAVE_FAIL_KEYS), name


# 這幾條是**承重**的：它們一旦不見，整套就從「有檢查」退回「看起來有檢查」。
# ⚠️ **比的是名字的集合，不是數量** —— 姊妹頁出過一次無聲刪掉一整張網、
#    而測試總數剛好沒變的事（守衛由一條拆成兩條 ＋1、網 −1，淨 0）。
_LOAD_BEARING = (
    "test_標了逐字的引文_每一句都回比過44",
    "test_逐字豁免表沒有死條目而且每一筆都有理由",
    "test_全頁文字零方向詞零箭頭",
    "test_掃描器本身會咬_負控",
    "test_沒有任何一個跨幣別合成出來的數",
    "test_worst_state在資料未備與業務例外同級時不挑一個充數",
    "test_worst_state與輸入順序無關_全排列實跑",
    "test_worst_state吃得下哨符_不會KeyError",
    "test_每一個可能收到哨符的呼叫端都列出來而且都處理得了",
    "test_空狀態四種的嚴重度是全序_而且照44客戶裁示那一句",
    "test_本頁沒有任何情境產生業務例外_據實登記",
    "test_缺值進條件比較時直接炸掉_不靜默選一邊",
    "test_EXP7判準a_最後一列的套用後檔數與EXP0的N相等",
    "test_前向釘樁_整頁逐格釘住",
    "test_前向釘樁那張網真的蓋到每一個情境與每一塊",
    "test_五個可排序欄每一欄都真的被排過",
    "test_配息比依數排不是依畫面字串排",
    "test_哨符真的流過每一塊也不會炸",
    "test_block_tone的顏色優先序逐組釘住",
    "test_兩張表同時失敗時兩行各自帶自己的表名",
    "test_可選欄位五項比已拍板草稿多一項_而那一句的決策者是總管不是客戶",
    "test_基金名那一欄是全不勾時的退路_不是永遠顯示",
    "test_只顯示基金名那一行照44的判準行寫在EXP2",
    "test_跨幣別守衛的第二條路也真的會咬",
    "test_落單的刪除線標記不會吃掉它後面的引文",
    "test_44還是凍結的那一份",
    "test_EXP0的兩個顏色欄位永遠相等_畫面層挑哪一個都一樣",
    "test_上游取數失敗時_沒有一塊把它報成別的東西",
    "test_EXP0的狀態文字不借卡片四狀態那一組字",
    "test_六個比較方向的語意逐個釘住_含邊界",
    "test_早於或等於的等號那一邊在真的篩選裡也走得到",
)


def test_承重測試一條都不准無聲消失():
    """⛔ **「總數沒變」不是沒刪東西的證據。要比的是名字的集合。**"""
    here = {name for name in globals() if name.startswith("test_")}
    missing = [name for name in _LOAD_BEARING if name not in here]
    assert not missing, f"這幾條承重測試不見了：{missing}"
    assert len(here) >= 70, len(here)


# ═════════════════════ 期望值（由 `_dump_grid()` 產生） ═════════════════════

# ⚠️ **這一份是 `_dump_grid()` 現場 dump 出來的**（量測日 2026-09-24，本輪工作樹）。
# 它釘的是**本輪做出來的現行行為**，正確性由上面那幾十條正控背書。
# ⛔ 對不上時**重跑一次 `_dump_grid()` 再 diff，不要直接改這一份** —— 改了這一條就廢了。
# ⚠️ 2026-09-24 第二十一輪：客戶裁示取數失敗圖示 ⚠→⛔，受影響格的摘要已換新值（有意識的更正，不是漏刪）。
#    換之前先證明：把現行模型字串裡的 ⛔ 換回 ⚠ 再算摘要，本表舊值逐格全數重現（量測日 2026-09-24）；
#    故差異只有那個圖示。沒被取數失敗碰到的格一格未動。
_EXPECTED_GRID = {
    'blankvalue|0|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'blankvalue|0|EXP-1': ('中性', 'ok', '2c52d7f6b340'),
    'blankvalue|0|EXP-2': ('灰', '資料未備', '6cee62f4c74d'),
    'blankvalue|0|EXP-3': ('灰', '資料未備', '731328dfa464'),
    'blankvalue|0|EXP-4': ('中性', 'ok', '3f86aebf2140'),
    'blankvalue|0|EXP-5': ('中性', 'ok', '6691f3aa6866'),
    'blankvalue|0|EXP-6': ('中性', 'ok', '5d1726c91dad'),
    'blankvalue|0|EXP-7': ('中性', 'ok', '3462a1a98cca'),
    'blankvalue|1|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'blankvalue|1|EXP-1': ('中性', 'ok', 'e3aafbfb45c5'),
    'blankvalue|1|EXP-2': ('灰', '資料未備', '6cee62f4c74d'),
    'blankvalue|1|EXP-3': ('灰', '資料未備', '731328dfa464'),
    'blankvalue|1|EXP-4': ('中性', 'ok', '4559e64b5296'),
    'blankvalue|1|EXP-5': ('中性', 'ok', '5121c8ef9f93'),
    'blankvalue|1|EXP-6': ('中性', 'ok', '5d1726c91dad'),
    'blankvalue|1|EXP-7': ('中性', 'ok', '3462a1a98cca'),
    'draftdiffers|0|EXP-0': ('黃', 'ok', '442e661e8db5'),
    'draftdiffers|0|EXP-1': ('中性', 'ok', 'a6b85ed36c0d'),
    'draftdiffers|0|EXP-2': ('中性', 'ok', 'fe01b2173df7'),
    'draftdiffers|0|EXP-3': ('中性', 'ok', '438da47665c5'),
    'draftdiffers|0|EXP-4': ('中性', 'ok', '3f86aebf2140'),
    'draftdiffers|0|EXP-5': ('中性', 'ok', '1146352435cc'),
    'draftdiffers|0|EXP-6': ('中性', 'ok', '5d1726c91dad'),
    'draftdiffers|0|EXP-7': ('中性', 'ok', '311431c24b65'),
    'draftdiffers|1|EXP-0': ('黃', 'ok', '442e661e8db5'),
    'draftdiffers|1|EXP-1': ('中性', 'ok', '7bae5b518d33'),
    'draftdiffers|1|EXP-2': ('中性', 'ok', 'fe01b2173df7'),
    'draftdiffers|1|EXP-3': ('中性', 'ok', '438da47665c5'),
    'draftdiffers|1|EXP-4': ('中性', 'ok', '4559e64b5296'),
    'draftdiffers|1|EXP-5': ('中性', 'ok', '4590f0751d16'),
    'draftdiffers|1|EXP-6': ('中性', 'ok', '5d1726c91dad'),
    'draftdiffers|1|EXP-7': ('中性', 'ok', '311431c24b65'),
    'full|0|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'full|0|EXP-1': ('中性', 'ok', 'a90d80fbd86e'),
    'full|0|EXP-2': ('灰', '資料未備', 'bbf513f76cba'),
    'full|0|EXP-3': ('灰', '資料未備', '731328dfa464'),
    'full|0|EXP-4': ('中性', 'ok', '3f86aebf2140'),
    'full|0|EXP-5': ('中性', 'ok', '2d0ab3f58e7d'),
    'full|0|EXP-6': ('中性', 'ok', '5d1726c91dad'),
    'full|0|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'full|1|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'full|1|EXP-1': ('中性', 'ok', '4a8d308061ce'),
    'full|1|EXP-2': ('灰', '資料未備', 'bbf513f76cba'),
    'full|1|EXP-3': ('灰', '資料未備', '731328dfa464'),
    'full|1|EXP-4': ('中性', 'ok', '4559e64b5296'),
    'full|1|EXP-5': ('中性', 'ok', '55c994f1c1b4'),
    'full|1|EXP-6': ('中性', 'ok', '5d1726c91dad'),
    'full|1|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'mixedccy|0|EXP-0': ('黃', 'ok', '8941caf62a43'),
    'mixedccy|0|EXP-1': ('中性', 'ok', '7a3499fd177e'),
    'mixedccy|0|EXP-2': ('灰', '資料未備', '26f654b21e8c'),
    'mixedccy|0|EXP-3': ('中性', 'ok', 'ec325bca403b'),
    'mixedccy|0|EXP-4': ('中性', 'ok', '3f86aebf2140'),
    'mixedccy|0|EXP-5': ('中性', 'ok', '6691f3aa6866'),
    'mixedccy|0|EXP-6': ('中性', 'ok', 'ae793c0ceae1'),
    'mixedccy|0|EXP-7': ('中性', 'ok', 'c1435d2cd3fd'),
    'mixedccy|1|EXP-0': ('黃', 'ok', '8941caf62a43'),
    'mixedccy|1|EXP-1': ('中性', 'ok', '2340495c6968'),
    'mixedccy|1|EXP-2': ('灰', '資料未備', '26f654b21e8c'),
    'mixedccy|1|EXP-3': ('中性', 'ok', 'ec325bca403b'),
    'mixedccy|1|EXP-4': ('中性', 'ok', '4559e64b5296'),
    'mixedccy|1|EXP-5': ('中性', 'ok', '5121c8ef9f93'),
    'mixedccy|1|EXP-6': ('中性', 'ok', 'ae793c0ceae1'),
    'mixedccy|1|EXP-7': ('中性', 'ok', 'c1435d2cd3fd'),
    'navfail|0|EXP-0': ('紅', '系統錯誤', '09aad001d7f6'),
    'navfail|0|EXP-1': ('中性', 'ok', 'a90d80fbd86e'),
    'navfail|0|EXP-2': ('紅', '系統錯誤', '4080364f16cf'),
    'navfail|0|EXP-3': ('紅', '系統錯誤', 'a9128de86b07'),
    'navfail|0|EXP-4': ('中性', 'ok', '3f86aebf2140'),
    'navfail|0|EXP-5': ('中性', 'ok', '6691f3aa6866'),
    'navfail|0|EXP-6': ('紅', '系統錯誤', '21b787e2b450'),
    'navfail|0|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'navfail|1|EXP-0': ('紅', '系統錯誤', '09aad001d7f6'),
    'navfail|1|EXP-1': ('中性', 'ok', '4a8d308061ce'),
    'navfail|1|EXP-2': ('紅', '系統錯誤', '4080364f16cf'),
    'navfail|1|EXP-3': ('紅', '系統錯誤', 'a9128de86b07'),
    'navfail|1|EXP-4': ('中性', 'ok', '4559e64b5296'),
    'navfail|1|EXP-5': ('中性', 'ok', '5121c8ef9f93'),
    'navfail|1|EXP-6': ('紅', '系統錯誤', '21b787e2b450'),
    'navfail|1|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'nocolumn|0|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'nocolumn|0|EXP-1': ('中性', 'ok', 'a90d80fbd86e'),
    'nocolumn|0|EXP-2': ('中性', 'ok', '5abfe8c18167'),
    'nocolumn|0|EXP-3': ('灰', '資料未備', '731328dfa464'),
    'nocolumn|0|EXP-4': ('中性', 'ok', '0c22be50f88e'),
    'nocolumn|0|EXP-5': ('中性', 'ok', '6691f3aa6866'),
    'nocolumn|0|EXP-6': ('中性', 'ok', '5d1726c91dad'),
    'nocolumn|0|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'nocolumn|1|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'nocolumn|1|EXP-1': ('中性', 'ok', '4a8d308061ce'),
    'nocolumn|1|EXP-2': ('中性', 'ok', '5abfe8c18167'),
    'nocolumn|1|EXP-3': ('灰', '資料未備', '731328dfa464'),
    'nocolumn|1|EXP-4': ('中性', 'ok', '15dd174eee2f'),
    'nocolumn|1|EXP-5': ('中性', 'ok', '5121c8ef9f93'),
    'nocolumn|1|EXP-6': ('中性', 'ok', '5d1726c91dad'),
    'nocolumn|1|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'nocond|0|EXP-0': ('灰', '資料未備', 'e7e32ac758ee'),
    'nocond|0|EXP-1': ('中性', 'ok', '6dad78dae858'),
    'nocond|0|EXP-2': ('中性', 'ok', '0d2297f24f9a'),
    'nocond|0|EXP-3': ('中性', 'ok', '087fc85e35ef'),
    'nocond|0|EXP-4': ('中性', 'ok', '0c22be50f88e'),
    'nocond|0|EXP-5': ('中性', 'ok', '6691f3aa6866'),
    'nocond|0|EXP-6': ('中性', 'ok', 'e3f8d4dba583'),
    'nocond|0|EXP-7': ('灰', '資料未備', '6a1a34e8ef72'),
    'nocond|1|EXP-0': ('灰', '資料未備', 'e7e32ac758ee'),
    'nocond|1|EXP-1': ('中性', 'ok', '68da45ef8578'),
    'nocond|1|EXP-2': ('中性', 'ok', '0d2297f24f9a'),
    'nocond|1|EXP-3': ('中性', 'ok', '087fc85e35ef'),
    'nocond|1|EXP-4': ('中性', 'ok', '15dd174eee2f'),
    'nocond|1|EXP-5': ('中性', 'ok', '5121c8ef9f93'),
    'nocond|1|EXP-6': ('中性', 'ok', 'e3f8d4dba583'),
    'nocond|1|EXP-7': ('灰', '資料未備', '6a1a34e8ef72'),
    'nofee|0|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'nofee|0|EXP-1': ('中性', 'ok', 'a90d80fbd86e'),
    'nofee|0|EXP-2': ('灰', '資料未備', '51b9a598bb91'),
    'nofee|0|EXP-3': ('灰', '資料未備', '4e15633aeaf0'),
    'nofee|0|EXP-4': ('中性', 'ok', '3f86aebf2140'),
    'nofee|0|EXP-5': ('中性', 'ok', '6691f3aa6866'),
    'nofee|0|EXP-6': ('灰', '資料未備', 'ba268b16f981'),
    'nofee|0|EXP-7': ('中性', 'ok', '68222f6215a9'),
    'nofee|1|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'nofee|1|EXP-1': ('中性', 'ok', '4a8d308061ce'),
    'nofee|1|EXP-2': ('灰', '資料未備', '51b9a598bb91'),
    'nofee|1|EXP-3': ('灰', '資料未備', '4e15633aeaf0'),
    'nofee|1|EXP-4': ('中性', 'ok', '4559e64b5296'),
    'nofee|1|EXP-5': ('中性', 'ok', '5121c8ef9f93'),
    'nofee|1|EXP-6': ('灰', '資料未備', 'ba268b16f981'),
    'nofee|1|EXP-7': ('中性', 'ok', '68222f6215a9'),
    'nowatch|0|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'nowatch|0|EXP-1': ('中性', 'ok', 'a90d80fbd86e'),
    'nowatch|0|EXP-2': ('灰', '資料未備', '4f2eae133231'),
    'nowatch|0|EXP-3': ('灰', '資料未備', '731328dfa464'),
    'nowatch|0|EXP-4': ('中性', 'ok', '3f86aebf2140'),
    'nowatch|0|EXP-5': ('中性', 'ok', '1146352435cc'),
    'nowatch|0|EXP-6': ('中性', 'ok', '5d1726c91dad'),
    'nowatch|0|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'nowatch|1|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'nowatch|1|EXP-1': ('中性', 'ok', '4a8d308061ce'),
    'nowatch|1|EXP-2': ('灰', '資料未備', '4f2eae133231'),
    'nowatch|1|EXP-3': ('灰', '資料未備', '731328dfa464'),
    'nowatch|1|EXP-4': ('中性', 'ok', '4559e64b5296'),
    'nowatch|1|EXP-5': ('中性', 'ok', '4590f0751d16'),
    'nowatch|1|EXP-6': ('中性', 'ok', '5d1726c91dad'),
    'nowatch|1|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'onematch|0|EXP-0': ('黃', 'ok', '442e661e8db5'),
    'onematch|0|EXP-1': ('中性', 'ok', 'b56c159f64d0'),
    'onematch|0|EXP-2': ('中性', 'ok', 'fe01b2173df7'),
    'onematch|0|EXP-3': ('中性', 'ok', '438da47665c5'),
    'onematch|0|EXP-4': ('中性', 'ok', '3f86aebf2140'),
    'onematch|0|EXP-5': ('中性', 'ok', '6691f3aa6866'),
    'onematch|0|EXP-6': ('中性', 'ok', '5d1726c91dad'),
    'onematch|0|EXP-7': ('中性', 'ok', '311431c24b65'),
    'onematch|1|EXP-0': ('黃', 'ok', '442e661e8db5'),
    'onematch|1|EXP-1': ('中性', 'ok', '95b2653e5d73'),
    'onematch|1|EXP-2': ('中性', 'ok', 'fe01b2173df7'),
    'onematch|1|EXP-3': ('中性', 'ok', '438da47665c5'),
    'onematch|1|EXP-4': ('中性', 'ok', '4559e64b5296'),
    'onematch|1|EXP-5': ('中性', 'ok', '5121c8ef9f93'),
    'onematch|1|EXP-6': ('中性', 'ok', '5d1726c91dad'),
    'onematch|1|EXP-7': ('中性', 'ok', '311431c24b65'),
    'profilefail_picked|0|EXP-0': ('紅', '系統錯誤', 'dbbbdc3f545c'),
    'profilefail_picked|0|EXP-1': ('中性', 'ok', 'a90d80fbd86e'),
    'profilefail_picked|0|EXP-2': ('紅', '系統錯誤', '74720652b35f'),
    'profilefail_picked|0|EXP-3': ('紅', '系統錯誤', '7c1ec4b62003'),
    'profilefail_picked|0|EXP-4': ('中性', 'ok', '3f86aebf2140'),
    'profilefail_picked|0|EXP-5': ('中性', 'ok', 'd5a0a26ab46f'),
    'profilefail_picked|0|EXP-6': ('紅', '系統錯誤', 'ac23370ab7b1'),
    'profilefail_picked|0|EXP-7': ('紅', '系統錯誤', '438798d0705b'),
    'profilefail_picked|1|EXP-0': ('紅', '系統錯誤', 'dbbbdc3f545c'),
    'profilefail_picked|1|EXP-1': ('中性', 'ok', '4a8d308061ce'),
    'profilefail_picked|1|EXP-2': ('紅', '系統錯誤', '74720652b35f'),
    'profilefail_picked|1|EXP-3': ('紅', '系統錯誤', '7c1ec4b62003'),
    'profilefail_picked|1|EXP-4': ('中性', 'ok', '4559e64b5296'),
    'profilefail_picked|1|EXP-5': ('中性', 'ok', 'bb4a483b5c60'),
    'profilefail_picked|1|EXP-6': ('紅', '系統錯誤', 'ac23370ab7b1'),
    'profilefail_picked|1|EXP-7': ('紅', '系統錯誤', '438798d0705b'),
    'profilefail|0|EXP-0': ('紅', '系統錯誤', 'dbbbdc3f545c'),
    'profilefail|0|EXP-1': ('中性', 'ok', 'a90d80fbd86e'),
    'profilefail|0|EXP-2': ('紅', '系統錯誤', '74720652b35f'),
    'profilefail|0|EXP-3': ('紅', '系統錯誤', '7c1ec4b62003'),
    'profilefail|0|EXP-4': ('中性', 'ok', '3f86aebf2140'),
    'profilefail|0|EXP-5': ('中性', 'ok', '6691f3aa6866'),
    'profilefail|0|EXP-6': ('紅', '系統錯誤', 'a569c3abcfef'),
    'profilefail|0|EXP-7': ('紅', '系統錯誤', '438798d0705b'),
    'profilefail|1|EXP-0': ('紅', '系統錯誤', 'dbbbdc3f545c'),
    'profilefail|1|EXP-1': ('中性', 'ok', '4a8d308061ce'),
    'profilefail|1|EXP-2': ('紅', '系統錯誤', '74720652b35f'),
    'profilefail|1|EXP-3': ('紅', '系統錯誤', '7c1ec4b62003'),
    'profilefail|1|EXP-4': ('中性', 'ok', '4559e64b5296'),
    'profilefail|1|EXP-5': ('中性', 'ok', '5121c8ef9f93'),
    'profilefail|1|EXP-6': ('紅', '系統錯誤', 'a569c3abcfef'),
    'profilefail|1|EXP-7': ('紅', '系統錯誤', '438798d0705b'),
    'sortccy|0|EXP-0': ('黃', 'ok', '8941caf62a43'),
    'sortccy|0|EXP-1': ('中性', 'ok', '7a3499fd177e'),
    'sortccy|0|EXP-2': ('灰', '資料未備', '3b4af31911ba'),
    'sortccy|0|EXP-3': ('中性', 'ok', '087fc85e35ef'),
    'sortccy|0|EXP-4': ('中性', 'ok', '9c637d513619'),
    'sortccy|0|EXP-5': ('中性', 'ok', '6691f3aa6866'),
    'sortccy|0|EXP-6': ('中性', 'ok', 'e3f8d4dba583'),
    'sortccy|0|EXP-7': ('中性', 'ok', 'c1435d2cd3fd'),
    'sortccy|1|EXP-0': ('黃', 'ok', '8941caf62a43'),
    'sortccy|1|EXP-1': ('中性', 'ok', '2340495c6968'),
    'sortccy|1|EXP-2': ('灰', '資料未備', '3b4af31911ba'),
    'sortccy|1|EXP-3': ('中性', 'ok', '087fc85e35ef'),
    'sortccy|1|EXP-4': ('中性', 'ok', 'b67b39960ff8'),
    'sortccy|1|EXP-5': ('中性', 'ok', '5121c8ef9f93'),
    'sortccy|1|EXP-6': ('中性', 'ok', 'e3f8d4dba583'),
    'sortccy|1|EXP-7': ('中性', 'ok', 'c1435d2cd3fd'),
    'sortdate|0|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'sortdate|0|EXP-1': ('中性', 'ok', 'a90d80fbd86e'),
    'sortdate|0|EXP-2': ('灰', '資料未備', 'ee8ebdb077e0'),
    'sortdate|0|EXP-3': ('中性', 'ok', '087fc85e35ef'),
    'sortdate|0|EXP-4': ('中性', 'ok', 'ef920ad0345e'),
    'sortdate|0|EXP-5': ('中性', 'ok', '6691f3aa6866'),
    'sortdate|0|EXP-6': ('中性', 'ok', 'e3f8d4dba583'),
    'sortdate|0|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'sortdate|1|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'sortdate|1|EXP-1': ('中性', 'ok', '4a8d308061ce'),
    'sortdate|1|EXP-2': ('灰', '資料未備', 'ee8ebdb077e0'),
    'sortdate|1|EXP-3': ('中性', 'ok', '087fc85e35ef'),
    'sortdate|1|EXP-4': ('中性', 'ok', 'd28446088f98'),
    'sortdate|1|EXP-5': ('中性', 'ok', '5121c8ef9f93'),
    'sortdate|1|EXP-6': ('中性', 'ok', 'e3f8d4dba583'),
    'sortdate|1|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'sortdropped|0|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'sortdropped|0|EXP-1': ('中性', 'ok', 'a90d80fbd86e'),
    'sortdropped|0|EXP-2': ('中性', 'ok', 'b4c27c92a40e'),
    'sortdropped|0|EXP-3': ('中性', 'ok', '087fc85e35ef'),
    'sortdropped|0|EXP-4': ('中性', 'ok', '4088dc956e5c'),
    'sortdropped|0|EXP-5': ('中性', 'ok', '6691f3aa6866'),
    'sortdropped|0|EXP-6': ('中性', 'ok', 'e3f8d4dba583'),
    'sortdropped|0|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'sortdropped|1|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'sortdropped|1|EXP-1': ('中性', 'ok', '4a8d308061ce'),
    'sortdropped|1|EXP-2': ('中性', 'ok', 'b4c27c92a40e'),
    'sortdropped|1|EXP-3': ('中性', 'ok', '087fc85e35ef'),
    'sortdropped|1|EXP-4': ('中性', 'ok', 'f4dc2c738e80'),
    'sortdropped|1|EXP-5': ('中性', 'ok', '5121c8ef9f93'),
    'sortdropped|1|EXP-6': ('中性', 'ok', 'e3f8d4dba583'),
    'sortdropped|1|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'sortname|0|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'sortname|0|EXP-1': ('中性', 'ok', 'a90d80fbd86e'),
    'sortname|0|EXP-2': ('灰', '資料未備', '48f15c2f5e15'),
    'sortname|0|EXP-3': ('中性', 'ok', '087fc85e35ef'),
    'sortname|0|EXP-4': ('中性', 'ok', '964476d09d31'),
    'sortname|0|EXP-5': ('中性', 'ok', '6691f3aa6866'),
    'sortname|0|EXP-6': ('中性', 'ok', 'e3f8d4dba583'),
    'sortname|0|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'sortname|1|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'sortname|1|EXP-1': ('中性', 'ok', '4a8d308061ce'),
    'sortname|1|EXP-2': ('灰', '資料未備', '48f15c2f5e15'),
    'sortname|1|EXP-3': ('中性', 'ok', '087fc85e35ef'),
    'sortname|1|EXP-4': ('中性', 'ok', 'a14f8850f5df'),
    'sortname|1|EXP-5': ('中性', 'ok', '5121c8ef9f93'),
    'sortname|1|EXP-6': ('中性', 'ok', 'e3f8d4dba583'),
    'sortname|1|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'sortnav|0|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'sortnav|0|EXP-1': ('中性', 'ok', 'a90d80fbd86e'),
    'sortnav|0|EXP-2': ('灰', '資料未備', 'd67ad068fc09'),
    'sortnav|0|EXP-3': ('灰', '資料未備', '731328dfa464'),
    'sortnav|0|EXP-4': ('中性', 'ok', 'be8466efc5d4'),
    'sortnav|0|EXP-5': ('中性', 'ok', '6691f3aa6866'),
    'sortnav|0|EXP-6': ('中性', 'ok', '5d1726c91dad'),
    'sortnav|0|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'sortnav|1|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'sortnav|1|EXP-1': ('中性', 'ok', '4a8d308061ce'),
    'sortnav|1|EXP-2': ('灰', '資料未備', 'd67ad068fc09'),
    'sortnav|1|EXP-3': ('灰', '資料未備', '731328dfa464'),
    'sortnav|1|EXP-4': ('中性', 'ok', 'b2ddfd2e8b80'),
    'sortnav|1|EXP-5': ('中性', 'ok', '5121c8ef9f93'),
    'sortnav|1|EXP-6': ('中性', 'ok', '5d1726c91dad'),
    'sortnav|1|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'sortratio|0|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'sortratio|0|EXP-1': ('中性', 'ok', 'a90d80fbd86e'),
    'sortratio|0|EXP-2': ('灰', '資料未備', '00b88eb5fb96'),
    'sortratio|0|EXP-3': ('中性', 'ok', '087fc85e35ef'),
    'sortratio|0|EXP-4': ('中性', 'ok', 'f3faca260432'),
    'sortratio|0|EXP-5': ('中性', 'ok', '6691f3aa6866'),
    'sortratio|0|EXP-6': ('中性', 'ok', 'e3f8d4dba583'),
    'sortratio|0|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'sortratio|1|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'sortratio|1|EXP-1': ('中性', 'ok', '4a8d308061ce'),
    'sortratio|1|EXP-2': ('灰', '資料未備', '00b88eb5fb96'),
    'sortratio|1|EXP-3': ('中性', 'ok', '087fc85e35ef'),
    'sortratio|1|EXP-4': ('中性', 'ok', '33e4c8d35d56'),
    'sortratio|1|EXP-5': ('中性', 'ok', '5121c8ef9f93'),
    'sortratio|1|EXP-6': ('中性', 'ok', 'e3f8d4dba583'),
    'sortratio|1|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'tenmatch|0|EXP-0': ('黃', 'ok', '4223b3522bd3'),
    'tenmatch|0|EXP-1': ('中性', 'ok', '76c93a895b34'),
    'tenmatch|0|EXP-2': ('灰', '資料未備', '8daeb853ec23'),
    'tenmatch|0|EXP-3': ('灰', '資料未備', '731328dfa464'),
    'tenmatch|0|EXP-4': ('中性', 'ok', '3f86aebf2140'),
    'tenmatch|0|EXP-5': ('中性', 'ok', '6691f3aa6866'),
    'tenmatch|0|EXP-6': ('中性', 'ok', '5d1726c91dad'),
    'tenmatch|0|EXP-7': ('中性', 'ok', '0bd10720cae3'),
    'tenmatch|1|EXP-0': ('黃', 'ok', '4223b3522bd3'),
    'tenmatch|1|EXP-1': ('中性', 'ok', 'a500722fc4d1'),
    'tenmatch|1|EXP-2': ('灰', '資料未備', '8daeb853ec23'),
    'tenmatch|1|EXP-3': ('灰', '資料未備', '731328dfa464'),
    'tenmatch|1|EXP-4': ('中性', 'ok', '4559e64b5296'),
    'tenmatch|1|EXP-5': ('中性', 'ok', '5121c8ef9f93'),
    'tenmatch|1|EXP-6': ('中性', 'ok', '5d1726c91dad'),
    'tenmatch|1|EXP-7': ('中性', 'ok', '0bd10720cae3'),
    'twofail|0|EXP-0': ('紅', '系統錯誤', '1b96c328b147'),
    'twofail|0|EXP-1': ('中性', 'ok', 'a90d80fbd86e'),
    'twofail|0|EXP-2': ('紅', '系統錯誤', '85e6128bbf2c'),
    'twofail|0|EXP-3': ('紅', '系統錯誤', '1553cfcaae5d'),
    'twofail|0|EXP-4': ('中性', 'ok', '3f86aebf2140'),
    'twofail|0|EXP-5': ('中性', 'ok', '6691f3aa6866'),
    'twofail|0|EXP-6': ('紅', '系統錯誤', '0dc938d43817'),
    'twofail|0|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'twofail|1|EXP-0': ('紅', '系統錯誤', '1b96c328b147'),
    'twofail|1|EXP-1': ('中性', 'ok', '4a8d308061ce'),
    'twofail|1|EXP-2': ('紅', '系統錯誤', '85e6128bbf2c'),
    'twofail|1|EXP-3': ('紅', '系統錯誤', '1553cfcaae5d'),
    'twofail|1|EXP-4': ('中性', 'ok', '4559e64b5296'),
    'twofail|1|EXP-5': ('中性', 'ok', '5121c8ef9f93'),
    'twofail|1|EXP-6': ('紅', '系統錯誤', '0dc938d43817'),
    'twofail|1|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'unknownfund|0|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'unknownfund|0|EXP-1': ('中性', 'ok', 'a90d80fbd86e'),
    'unknownfund|0|EXP-2': ('灰', '資料未備', '640198291c7f'),
    'unknownfund|0|EXP-3': ('中性', 'ok', '087fc85e35ef'),
    'unknownfund|0|EXP-4': ('中性', 'ok', '3f86aebf2140'),
    'unknownfund|0|EXP-5': ('中性', 'ok', '6691f3aa6866'),
    'unknownfund|0|EXP-6': ('灰', '資料未備', '55d4d941a5a8'),
    'unknownfund|0|EXP-7': ('中性', 'ok', '68222f6215a9'),
    'unknownfund|1|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'unknownfund|1|EXP-1': ('中性', 'ok', '4a8d308061ce'),
    'unknownfund|1|EXP-2': ('灰', '資料未備', '640198291c7f'),
    'unknownfund|1|EXP-3': ('中性', 'ok', '087fc85e35ef'),
    'unknownfund|1|EXP-4': ('中性', 'ok', '4559e64b5296'),
    'unknownfund|1|EXP-5': ('中性', 'ok', '5121c8ef9f93'),
    'unknownfund|1|EXP-6': ('灰', '資料未備', '55d4d941a5a8'),
    'unknownfund|1|EXP-7': ('中性', 'ok', '68222f6215a9'),
    'watchall|0|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'watchall|0|EXP-1': ('中性', 'ok', 'a90d80fbd86e'),
    'watchall|0|EXP-2': ('灰', '資料未備', 'a66b8834d2a2'),
    'watchall|0|EXP-3': ('中性', 'ok', '087fc85e35ef'),
    'watchall|0|EXP-4': ('中性', 'ok', '3f86aebf2140'),
    'watchall|0|EXP-5': ('中性', 'ok', 'bb92f3d91d08'),
    'watchall|0|EXP-6': ('中性', 'ok', 'e3f8d4dba583'),
    'watchall|0|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'watchall|1|EXP-0': ('黃', 'ok', '1eeeb8fd0977'),
    'watchall|1|EXP-1': ('中性', 'ok', '4a8d308061ce'),
    'watchall|1|EXP-2': ('灰', '資料未備', 'a66b8834d2a2'),
    'watchall|1|EXP-3': ('中性', 'ok', '087fc85e35ef'),
    'watchall|1|EXP-4': ('中性', 'ok', '4559e64b5296'),
    'watchall|1|EXP-5': ('中性', 'ok', '8095c1b01d47'),
    'watchall|1|EXP-6': ('中性', 'ok', 'e3f8d4dba583'),
    'watchall|1|EXP-7': ('中性', 'ok', 'f312c8f27f65'),
    'zero|0|EXP-0': ('灰', 'ok', '949bfa7ba021'),
    'zero|0|EXP-1': ('中性', 'ok', '63078b1469c7'),
    'zero|0|EXP-2': ('中性', 'ok', '5590721e5447'),
    'zero|0|EXP-3': ('中性', 'ok', '087fc85e35ef'),
    'zero|0|EXP-4': ('中性', 'ok', '3f86aebf2140'),
    'zero|0|EXP-5': ('中性', 'ok', '6691f3aa6866'),
    'zero|0|EXP-6': ('中性', 'ok', 'e3f8d4dba583'),
    'zero|0|EXP-7': ('中性', 'ok', '957faa163386'),
    'zero|1|EXP-0': ('灰', 'ok', '949bfa7ba021'),
    'zero|1|EXP-1': ('中性', 'ok', 'dda4fa16f7f8'),
    'zero|1|EXP-2': ('中性', 'ok', '5590721e5447'),
    'zero|1|EXP-3': ('中性', 'ok', '087fc85e35ef'),
    'zero|1|EXP-4': ('中性', 'ok', '4559e64b5296'),
    'zero|1|EXP-5': ('中性', 'ok', '5121c8ef9f93'),
    'zero|1|EXP-6': ('中性', 'ok', 'e3f8d4dba583'),
    'zero|1|EXP-7': ('中性', 'ok', '957faa163386'),
}


def test_上游掛掉時EXP7的摘要不講成尚未設定條件():
    """⛔ **2026-09-24 本組自查抓到的 Fail-Loud 洞（與稽核給的十項無關，是第十一件事，我自己找到的）。**

    `EXP-7` 的 `summary_text` 原本只有兩支：有軌跡列 → 「N 條軌跡」，否則 →
    「尚未設定條件」。**上游取數失敗時軌跡列被清空，於是它掉進第二支** ——
    宣告「使用者還沒設條件」，而 `profilefail` 這個情境**設了三條規則**。
    **那是把取數失敗講成別的原因**，與同一輪替 `EXP-2`／`EXP-3`／`EXP-6` 修掉的四句同型。
    ⚠️ **當時為什麼漏了**：那一輪看的是 `_state`，而 `EXP-7` 的 `_state` 一直都正確地是
    `系統錯誤` —— **說謊的是文案，不是狀態**。狀態對不代表話沒講錯。

    本條把三支都釘住，並**反面驗**：條件真的沒設時那句話仍然要出現（否則這一條會變成
    「把那句話刪掉就永遠綠」）。
    """
    # 1) 上游掛掉：不得出現「尚未設定條件」，要出現取數失敗那一句。
    for name in ("profilefail", "profilefail_picked"):
        block = logic.find_block(_model(name), "EXP-7")
        assert block["_state"] == logic.STATE_ERROR, name
        assert block["summary_text"] == logic.ERR_TEXT, (name, block["summary_text"])
        assert logic.TEXT_NO_CONDITION not in block["summary_text"], name
        # 這個情境**真的設了條件** —— 否則上面那句話就不算謊，本條也就白驗了。
        rules = _rules_of(name)
        assert len(rules) == 3, (name, rules)

    # 2) 條件真的沒設：那句話仍然要在（反面，防「刪掉就綠」）。
    nocond = logic.find_block(_model("nocond"), "EXP-7")
    assert nocond["summary_text"] == logic.TEXT_NO_CONDITION
    assert nocond["_state"] == logic.STATE_MISSING
    assert _rules_of("nocond") == []

    # 3) 一切正常：走軌跡列那一支。
    full = logic.find_block(_model("full"), "EXP-7")
    assert "條軌跡" in full["summary_text"]
    assert full["_state"] == logic.STATE_OK


def _rules_of(name):
    """從情境的假資料裡讀出它到底設了幾條篩選規則（不經 logic，直接看來源）。"""
    dataset = dict(fixtures.scenario_with(name))["dataset"]
    for row in dataset.get("user_setting") or []:
        if row.get("setting_key") == "exp_filter_rules":
            return list(row.get("setting_value") or [])
    return []


def test_跨行起頭的逐字引文真的被抓到_收窄成同一行會紅():
    """⛔ **2026-09-24 第二輪稽核抓到：`_MIN_VERIFIED_QUOTES` 擋不住「收窄成只認同一行」。**

    `_quotes_introduced_by_verbatim()` 的整個設計理由就是「引文與『逐字』**可以不在同一行**」
    （見該函式 docstring 第一顆 bullet）。**但那件事從來沒有被任何測試釘住。**
    把連接字元表裡的 `\n` 拿掉（＝只認同一行），**verified 只從 66 掉到 60**，
    而下限是 50 ⇒ **整套測試照樣全綠**（本組實測，量測日 2026-09-24）。

    本條直接釘那個**能力**：跨行起頭的已驗證引文**必須真的存在且被抓到**。
    收窄之後那一類會掉到 0 ⇒ **本條轉紅**。
    ⚠️ 本條刻意**呼叫真正的抽取函式**（不自己重寫一份），所以不論收窄是改連接字元表、
       還是在函式裡加一個同行檢查，**兩種寫法都會被咬到**。
    """
    flat44 = _flat44(_D44.read_text(encoding="utf-8"))
    cross, same = 0, 0
    for rel, lineno, quote in _all_verbatim_quotes():
        if quote in _NOT_A_44_QUOTE or _flat44(quote) not in flat44:
            continue
        text = _unstruck_text((_ROOT / rel).read_text(encoding="utf-8"))
        idx = text.find("「" + quote + "」")
        quote_line = text[:idx].count("\n") + 1 if idx >= 0 else lineno
        if quote_line > lineno:
            cross += 1
        else:
            same += 1

    assert cross + same, "一句都沒抽到 —— 這一條會變成空掃"
    assert cross >= _MIN_CROSS_LINE_QUOTES, (
        f"跨行起頭的已驗證引文只剩 {cross} 句（下限 {_MIN_CROSS_LINE_QUOTES}）。"
        "抽取判定是不是被收窄成『只認同一行』了？那會讓一整類引文悄悄退出受檢集，"
        "而 `_MIN_VERIFIED_QUOTES` 擋不住它（實測收窄只掉 6 筆，下限離現值有 16 筆）。"
    )
    # 反面：同行起頭的也要在，否則代表抽取壞在另一邊。
    assert same >= cross, (cross, same)


def test_無呼叫者登記表與現況一致_既不漏登也不過期():
    """⛔ **2026-09-24 第二輪稽核：九個無呼叫者的東西原本是「靜默留著」。**

    本檔自己在 `status_badge` 上方訂過體例 ——「**留著、就地寫明為什麼，不是靜默留著**」，
    而那九筆留著、**一個字都沒寫**。稽核把其中六支改名 → **170 passed、零參照**。

    本條把 `KNOWN_NO_CALLER` 釘成**雙向**的：
      · **漏登**：表上沒有、但實際零呼叫者 → 紅（下一個死碼不會再靜默溜過去）；
      · **過期**：表上有、但實際已經有人用了 → 紅（用起來了就該從表上拿掉）。
    ⚠️ **本條只做 `44` §6 三層確認的第一層（grep caller）**，所以登記一律標「未確認」，
       **不標 `dead`**；`44` §6 指定的登記表是 `46_fund_live_dead.md`，
       而那個檔不在本組的檔案邊界內 —— **該衝突已回報，本組不自行刪除任何一筆。**
    """
    import re as _re
    sources = {
        rel: (_ROOT / rel).read_text(encoding="utf-8")
        for rel in ("ui_v2/exp/logic.py", "ui_v2/exp/fixtures.py",
                    "ui_v2/exp/page.py", "ui_v2/exp/theme.py", "ui_v2/app_exp.py")
    }
    blob = "\n".join(sources.values())

    def bare_uses(name):
        """數這個名字在**程式碼**裡出現幾次（去掉註解與 docstring 之後）。"""
        total = 0
        for text in sources.values():
            code = _re.sub(r'"""[\s\S]*?"""', "", text)
            code = _re.sub(r"#.*", "", code)
            # ⛔ **登記表自己不算一次使用。**
            #    它的鍵就是那些名字的字面值 —— 不扣掉的話，**登記一筆就會讓那一筆
            #    看起來「有人用了」**，於是這條測試會反過來叫人把它從表上拿掉。
            #    （本輪初稿就是這樣紅的：`KNOWN_CURRENCIES` 被自己的登記算成 2 處。）
            #    同 `CLAUDE.md` §-2.A 第 8 款：把掃描用的字串寫進文件，它就會自己命中。
            code = _re.sub(r"KNOWN_NO_CALLER\s*=\s*\{[\s\S]*?\n\}", "", code)
            total += len(_re.findall(rf"\b{_re.escape(name.split('.')[-1])}\b", code))
        return total

    assert logic.KNOWN_NO_CALLER, "登記表是空的 —— 這一條會變成空掃"
    # 表上每一筆都要寫出理由，而且真的還是零呼叫者（定義處那一次不算）。
    for name, reason in logic.KNOWN_NO_CALLER.items():
        assert reason.strip(), name
        assert bare_uses(name) <= 1, (
            f"{name} 已經有人用了，請把它從 KNOWN_NO_CALLER 拿掉（現在 {bare_uses(name)} 處）"
        )
    # 反面（防漏登）：本檔幾個公開名字若掉到零呼叫者，必須出現在表上。
    watched = ["empty_source_text", "not_applicable_text", "source_badge",
               "all_blocks", "non_ok_value_nodes", "checkbox_groups",
               "KNOWN_CURRENCIES", "STORAGE_TIMEZONE"]
    for name in watched:
        if bare_uses(name) <= 1:
            assert name in logic.KNOWN_NO_CALLER, f"{name} 零呼叫者卻沒有登記"
    # `KNOWN_CURRENCIES` 那句假註解不准回來：真正的跨幣別守衛不讀它。
    cross = blob[blob.index("def cross_currency_nodes"):][:1200]
    assert "KNOWN_CURRENCIES" not in cross, "跨幣別守衛若真的用了它，上面那筆登記就過期了"
