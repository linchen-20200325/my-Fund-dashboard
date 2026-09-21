"""`docs/v2/*.md` 的計數／指令／全稱句守衛 —— 讓「數字沒釘 SHA、指令自己掃自己、
全稱句沒有反向檢查」在 CI 當場紅燈，不再靠人工複驗。

**前例**：`tests/test_constitution_file_refs.py`（憲法的檔案引用守衛）。
那一支靠 CI 逼出 22 處過期路徑 —— **那 22 處不是靠人回頭讀發現的，是紅燈逼出來的**。
本檔是同一個做法換一個對象：`docs/v2/` 底下的規格／裁決／稽核文件。

---
## 客戶 2026-09-21 裁示（本檔的法源，逐字，不得改寫）

    1. 所有計數釘 commit SHA，不寫「工作樹」「HEAD」「origin/main..HEAD」。
    2. 計數指令不准寫進被計數的檔。
    3. 凡「每一個」「所有」「全部」「都」開頭的斷言，
       必須附反向檢查指令與輸出。沒有反向檢查的，不准寫。

---
## 三道檢查（各自獨立成一個 test，一道紅不影響另外兩道的可讀性）

* **(A) `test_counting_sentences_pin_a_commit_sha`**
  一個**句段**若同時含「掃描指令」與「數字＋量詞」，它就是一句**計數**，
  必須在同一句段內出現 commit SHA（7–40 位十六進位、且至少含一個 `a`–`f`）。
  `origin/main` / `HEAD` / `工作樹` **不算釘** —— 它們是會移動的 ref，
  下一個人照跑會拿到不同的數字，那個計數就不可重現。

* **(B) `test_scan_commands_do_not_live_in_the_file_they_scan`**
  一個句段若同時含「掃描指令」與**該檔自己的檔名**，就是**指令自計**：
  掃 `X` 的指令寫進 `X` 自己，它會把自己算進去。
  `docs/v2/41_counters.md` 開頭的硬禁令講的就是這件事。

* **(C) `test_sentence_initial_universals_carry_a_reverse_check`**
  **句首**的「每一個／所有／全部／都」斷言，必須在它自己那一行起算的**視窗**內
  找得到「指令 ＋ 輸出」。沒有反向檢查的全稱句，不准寫。

## 「句首」怎麼定義（客戶寫的是「**開頭**」，這裡把語意寫死）

母體不是「這四個詞出現幾次」。把那四個詞（字面見下方 `_UNIVERSAL_HEADS`，
**刻意不在本段重印**，理由同 `CLAUDE.md` §-2.A 第 8 款：受測字串寫進文件就會被自己掃到）
交給 `git grep -ohE ... -- 'docs/v2/*.md' | wc -l`，在 `0d9753f` 上的**出現次數**是 **1915** 次；
但其中絕大多數是句中副詞（例：「三處**都**是…」），**不是**以它開頭的斷言。

本檔的「句首」＝ 把全文切成**句段**之後，**去掉排版裝飾**，第一個字就是那四個詞之一：

1. **切句段**：在換行、`。！？!?；;`、`<br>` 處切開；**只有 markdown 表格列**
   （該行第一個非空白字元是豎線的那種）**額外**在未跳脫的豎線處再切 ——
   表格一格就是一個獨立斷言。
   ⚠️ **非表格列一律不切豎線**：那裡的豎線是 shell pipeline 或 regex 的交替符號。
   本檔的負控抓到過這個：早期版本一律切，於是一條釘好 SHA 的
   `git show <sha>:path | grep -c …` 會被切成兩半，後半看不到 SHA 而被誤報。
2. **去排版裝飾**：反覆剝掉行首的空白、`>`、`#`、清單符號 `-`／`*`／`+`／`1.`、
   強調符號 `**`／`__`／`` ` ``／`~~`、`(1)`／`（1）` 這類序號、以及 emoji 與符號
   （⚠️ ⛔ ✅ ❌ 📌 ⭐ → 之類）。
3. **剩下的第一個字**是「每一個／所有/全部/都」之一，**且其後還有至少 2 個字**
   （擋掉表格裡只寫「全部」兩個字的那種格子 —— 那是欄位值，不是斷言）。

量測（**全部釘 `0d9753f`**，由本檔的 `--report` 與 `_is_sentence_initial_universal` 跑出來）：
本定義下**活的**句首斷言 **84** 句，其中已附反向檢查 **16** 句、缺 **68** 句。
`0d9753f` 上 **1915 → 84** 的收斂，來源只有「句首」這個限定，不是本檔偷偷放寬了什麼。

## 刪除線：被 `~~` 劃掉的一律不檢查

本 repo 的核心慣例是「舊條文保留不刪 ＋ 加刪除線」。**被劃掉的舊句是已正確退役的紀錄**，
拿它紅燈只會逼後人去刪歷史 —— 那是**不可逆**的傷害。
本檔沿用 `tests/test_constitution_file_refs.py` 的 `strike_mask` 做法（含它那兩個
「配不到伴的 `~~` 不吃掉後文」的上限），理由與該處相同。

---
## baseline：本守衛**只擋新增的**

上面那三條規則是 **2026-09-21** 才定下來的；`docs/v2/` 底下絕大多數文字寫在那之前。
**沒有 baseline 的話，這支守衛一上線就紅燈，永遠進不了 main，等於沒有守衛。**

* **baseline 內的** → 跳過（它是「已登記的歷史欠債」，不是「已修好」）。
* **不在 baseline 內的** → **紅燈**，並印出檔名、正規化後的句子、以及修法指引。

### baseline 的 key **刻意不用行號**

這個 repo 的行號每一輪都在漂 —— **那正是本守衛要治的病之一**。
key ＝ `sha256(檔案相對路徑 + "\\0" + 正規化後的句子)` 取前 16 位。

**正規化規則（本段即為權威定義，改這裡等於讓整份 baseline 失效）**：

1. 去掉 markdown 強調符號：`**`、`__`、`~~`、反引號 `` ` ``。
2. 去掉行首的清單符號／引用符號／序號（同上「去排版裝飾」那一套）。
3. 連續空白（含全形空白 `　`、不斷行空白 ` `）一律壓成一個半形空格。
4. 去掉頭尾空白。
5. **其餘一個字都不動** —— 不轉全半形、不去標點、不小寫化。
   （中文文件裡全半形與標點本身就帶語意，動了會讓兩句不同的話撞同一個 key。）

### key 含檔案路徑，是刻意的

同一句話搬到另一個檔會**重新紅燈**。理由：baseline 記的是「**這個位置的這句話**已登記」，
不是「這句話在全 repo 通行」。一份豁免若能跨檔通用，就會變成
「A 檔登記過 ⇒ B 檔照抄免驗」—— 那正是 `CLAUDE.md` §8.2.A.1 驗證段 ④ 點名的失效模式
（**條件只往外用、不往內用**）。
⚠️ **代價據實寫明**：同一檔內**逐字相同**的多句會收斂成同一個 key，
baseline 一筆會蓋住那一檔內的全部同字句。這是已知的、刻意接受的粗粒度。

### 怎麼重建 baseline

    python3 tests/test_doc_counters.py --update-baseline [<rev>]   # 省略 <rev> ＝ HEAD

**產生端讀的是釘死的 commit，不是工作樹**（見 `docs_at_sha` 的說明）——
一份要求別人釘 SHA 的守衛，自己的 baseline 若產生自工作樹，就沒有人能原樣重建它。
本檔隨附的那一份釘在 **`6880a2b`**，`_generated_from_sha` 欄自陳其出處。
⚠️ 若主線已經往前走，commit 本守衛的人請對**實際的 merge base** 重跑一次，
   並**逐句讀** `git diff` —— 那份 diff 會列出這段期間新欠的債。

⛔ **重建 baseline ＝ 承認新的違規，要有人明確決定。**
它不是「把紅燈弄綠」的按鈕：跑完之後 `git diff` 會列出每一筆新登記的句子，
**那份 diff 就是你在簽名承認的東西**，請逐句讀過再 commit。
本 repo 的正解一律是**先照 `_FIX_GUIDE_*` 修**，修不動才登記。

---
## ⚠️ 射程外（是「還沒解決」，不是「已解決」）

⛔ 下面三項**不得**被讀成「守衛已經涵蓋」。綠燈**不**代表 `docs/v2/` 的數字都查過了。

* **缺口 1｜(A) 只看「帶指令的」計數。** 一句「本表其餘 12 欄該指令確實回 0 行」
  沒有指令 token，**不會**被檢查。要補的人：把 `_COUNT_TOKEN` 的觸發條件放寬到
  「數字＋量詞」即可觸發，但那會把「3 個理由」這種非量測句一起抓進來，
  **必須先想好怎麼分辨量測與敘述**，不要直接放寬了事。
* **缺口 2｜(A) 只驗「有沒有 SHA」，不驗「那個 SHA 對不對」。**
  隨便寫一個 7 位十六進位字串就能過。要補的人：可用
  `git cat-file -e <sha>^{commit}` 驗存在性 —— 但那會讓本守衛依賴 git 物件庫，
  在 shallow clone（CI 預設）下可能誤紅，**先確認 fetch-depth 再做**。
* **缺口 3｜(C) 只驗「視窗內有指令與輸出」，不驗那個反向檢查**真的能推翻那句話。
  一條無關的指令貼在旁邊就能過。這一層需要讀懂語意，**機器判不到**。
* **缺口 4｜(B) 的判定分不出「釘 SHA 的快照自掃」與「讀工作樹的自掃」。**
  前者（形如 `git show <凍結 sha>:<自己>`）讀的是凍結的 blob，
  這個檔**現在**長什麼樣影響不了它的輸出 —— **機制上不可能自計**；
  後者（對工作樹跑的掃描）才是這個 repo 連續數輪在治的那個病。
  `find_self_scanning_commands` 目前**只在 `note` 字串裡**分辨兩者（那個 `snapshot` 布林），
  **判定一律紅燈**；而 baseline 每一筆只留 `file` 與 `text`、**不留 `note`** ⇒
  兩種形態進了 baseline 之後長得一模一樣，**後人分不出哪一筆是無害的**。
  要補的人從這裡開始：把 `snapshot` 從「只影響訊息」升成「影響分區」，
  例如讓快照自掃落進一個獨立分區、與真正讀工作樹的那種分開記。
  ⚠️ **改分區 key 等於讓既有 baseline 的該區整區失效**（全部變回「新違規」），
  所以必須**同一輪重建 baseline 並逐句讀 diff**，不能只改判定就走。
  ⚠️ 更要先決定的是**該不該放行**：客戶裁示裡
  「計數指令不准寫進被計數的檔」那一條，**字面上沒有為快照開後門** ——
  放行它是**放寬規則**，不是修 bug，那個決定不該由守衛自己做掉。
  在那個決定做出來之前，正解是照現況紅燈、逐筆登記 baseline 並寫明理由
  （本輪已對 5 筆這樣做，理由寫在 baseline 的 `why_safe` 欄）。
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs" / "v2"
DOCS_GLOB = "*.md"
BASELINE_PATH = Path(__file__).resolve().parent / "doc_counters_baseline.json"

# baseline 的三個分區 key（改名等於讓既有 baseline 的該區整區失效）
SEC_COUNTS = "counts_without_sha"
SEC_SELFSCAN = "self_scanning_commands"
SEC_UNIVERSALS = "universals_without_reverse_check"
# baseline 自陳它是從哪個 commit 產生的 —— 讓它可以被**原樣重建**。
META_SHA = "_generated_from_sha"


# ══════════════════════════════════════════════════════════════════════════
# 刪除線遮罩（做法與上限沿用 `tests/test_constitution_file_refs.py`）
# ══════════════════════════════════════════════════════════════════════════
# 兩個上限刻意有限：若有人寫出單邊的刪除線符號，全域貪婪配對會讓它後面**所有**
# 句子一起被當成「已退役」而不再檢查 —— 該檢查的變成不檢查，而且是無聲的。
# 有上限的話，配不到伴的那一個會被當成普通文字，影響只留在原地。
_MAX_STRIKE_NEWLINES = 2
_MAX_STRIKE_CHARS = 1500
_STRIKE = "~" * 2


def strike_mask(text: str) -> bytearray:
    """回傳與 ``text`` 等長的遮罩，被刪除線包住的位置為 1。"""
    mask = bytearray(len(text))
    i = 0
    while True:
        open_at = text.find(_STRIKE, i)
        if open_at < 0:
            return mask
        limit = min(len(text), open_at + 2 + _MAX_STRIKE_CHARS)
        close_at = text.find(_STRIKE, open_at + 2, limit)
        if close_at < 0 or text.count("\n", open_at, close_at) > _MAX_STRIKE_NEWLINES:
            i = open_at + 2
            continue
        for k in range(open_at, close_at + 2):
            mask[k] = 1
        i = close_at + 2


# ══════════════════════════════════════════════════════════════════════════
# 句段切分 ＋ 正規化
# ══════════════════════════════════════════════════════════════════════════
# **`|` 只在 markdown 表格列上才是切點** —— 表格一格就是一個獨立斷言，不切開會讓
# 「這一格有指令、那一格有數字」黏成同一句而被誤判。
# ⚠️ 但在**非表格列**上，`|` 是 shell pipeline 或 regex 的交替符號。
#    早期版本一律切 `|`，於是 `git show <sha>:path | grep -c 'X' → 7 處` 會被切成兩半，
#    後半「grep -c 'X' → 7 處」**看不到前半的 SHA** ⇒ 一個釘好 SHA 的計數被誤報。
#    這是本檔的負控當場抓到的（見 `test_control_A_unpinned_count_fires_and_pinned_count_does_not`）。
# ⚠️ 表格列內的 `\|`（跳脫的豎線）同樣是 pipeline，不切 —— 本 repo 的文件大量這樣寫。
_SENTENCE_SPLIT = re.compile(r"[。！？!?；;]|<br\s*/?>")
_TABLE_SPLIT = re.compile(r"[。！？!?；;]|<br\s*/?>|(?<!\\)\|")

# 行首排版裝飾：空白／引用／標題／清單符號／序號／強調符號／emoji 與箭頭符號／開括號。
# ⚠️ 這一串**必須反覆剝到不動為止**（見 `normalize`）——「`- **所有**…`」要剝三層
#    （清單符號 → 空白 → 強調符號）才看得到第一個實字。只剝一次會讓句首斷言漏抓。
_LEADING_FURNITURE = re.compile(
    r"^(?:"
    r"[\s\u3000\u00a0>#*+\-_`~]"
    r"|\d+[.)]"
    r"|[(（]\d+[)）]"
    r"|[\u2190-\u2BFF\uFE0F\u2000-\u206F\U0001F000-\U0001FAFF]"
    r"|[「『【（(\[]"
    r")+"
)

_EMPHASIS = re.compile(r"\*\*|__|" + _STRIKE + r"|`")
_WHITESPACE = re.compile(r"[\s\u3000\u00a0]+")


def normalize(segment: str) -> str:
    """把一個句段正規化成 baseline 的 key 素材。

    規則（與模組 docstring 的「正規化規則」逐條對應，**改這裡等於讓整份 baseline 失效**）：

    1. 反覆剝掉行首排版裝飾（清單符號／引用／序號／強調／emoji／開括號），剝到不動為止。
    2. 去掉所有 markdown 強調符號與反引號。
    3. 連續空白（含全形與不斷行空白）一律壓成一個半形空格。
    4. 去頭尾空白。

    其餘一個字都不動 —— 不轉全半形、不去標點、不小寫化。
    中文文件裡全半形與標點本身就帶語意，動了會讓兩句不同的話撞同一個 key，
    那會讓一筆 baseline 意外蓋住另一句它沒看過的話。
    """
    prev = None
    s = segment
    while prev != s:
        prev = s
        s = _LEADING_FURNITURE.sub("", s)
    s = _EMPHASIS.sub("", s)
    s = _WHITESPACE.sub(" ", s)
    return s.strip()


class Segment:
    """一個句段。

    * ``raw``  —— 原文（含被劃掉的部分）。
    * ``live`` —— **把被刪除線劃掉的字元拿掉之後**剩下的文字。三道檢查一律看這個。
    * ``text`` —— ``live`` 正規化後的結果，同時是 baseline key 的素材與錯誤訊息的顯示字串。
    * ``struck`` —— 整段都被劃掉（``live`` 是空的）。

    ⚠️ **為什麼是「拿掉劃掉的字」而不是「整段被劃掉才跳過」**：本 repo 最常見的退役寫法是
    `~~舊句~~ → 2026-09-21 更正，見 <sha>` —— **同一段裡一半死一半活**。
    用「整段」判，這種句子會被當成活的，而它正規化之後還是以那個全稱詞開頭 ⇒ 誤報。
    改看活文字之後，開頭那個詞已經隨刪除線一起消失，句子自然不再是句首斷言。
    做法與 `tests/test_constitution_file_refs.py` 同向（該檔判的是**每一個引用自己**的位置
    有沒有被劃掉，不是整行）。
    """

    __slots__ = ("line", "raw", "live", "text", "struck")

    def __init__(self, line: int, raw: str, live: str):
        self.line = line
        self.raw = raw
        self.live = live
        self.text = normalize(live)
        self.struck = not live.strip()


def split_segments(doc: str) -> list[Segment]:
    """把整份文件切成句段（逐行處理，表格列才切 `|`）。"""
    mask = strike_mask(doc)
    out: list[Segment] = []
    pos = 0
    for lineno, line in enumerate(doc.split("\n"), start=1):
        start = pos
        pos += len(line) + 1
        splitter = _TABLE_SPLIT if line.lstrip().startswith("|") else _SENTENCE_SPLIT
        spans, last = [], 0
        for m in splitter.finditer(line):
            spans.append((last, m.start()))
            last = m.end()
        spans.append((last, len(line)))
        for a, b in spans:
            raw = line[a:b]
            if not raw.strip():
                continue
            live = "".join(ch for i, ch in enumerate(raw, start=start + a) if not mask[i])
            out.append(Segment(lineno, raw, live))
    return out


# ══════════════════════════════════════════════════════════════════════════
# 三種 token
# ══════════════════════════════════════════════════════════════════════════
# 「掃描指令」—— 會產生一個數字的東西。刻意寧可多抓不可漏抓（同 `CLAUDE.md`
# §-1.5.1c 判定 2 的驗證指令慣例：**會多抓是設計，不是瑕疵**）。
_SCAN_CMD = re.compile(
    r"(?:"
    r"git\s+(?:grep|show|diff|ls-files|ls-tree|log|cat-file|rev-list)"
    r"|(?<![\w-])grep(?![\w-])"
    r"|(?<![\w-])rg(?![\w-])"
    r"|(?<![\w-])wc\s+-[lcmw]"
    r"|(?<![\w-])awk(?![\w-])"
    r"|(?<![\w-])sed\s+-n"
    r"|(?<![\w-])cmp(?![\w-])"
    r"|(?<![\w-])find\s+\S"
    r"|(?<![\w-])head\s+-\d"
    r"|(?<![\w-])tail\s+-"
    r"|(?<![\w-])diff\s+<?\("
    r")"
)

# 「數字＋量詞」—— 一個計數的結果長什麼樣。
# ⚠️ 三個 lookbehind 是用來擋掉**序數**（「第 1 條」「第 3 項」）—— 那是在**指涉**
#    某一條，不是在**數**東西。不擋的話，「違反同一批裁示的第 1 條」會被當成一句計數，
#    然後要求它釘 SHA —— 一個顯然荒謬的紅燈，會讓人學會忽略這支守衛。
#    （`0d9753f` 的工作樹上實測到 1 筆這種誤報，就是這樣被抓出來並修掉的。）
_COUNT_TOKEN = re.compile(
    r"(?:"
    r"(?<!第)(?<!第 )(?<!第\u3000)"
    r"\d{1,7}\s*[*`~_]{0,2}\s*(?:處|行|檔|筆|個|次|組|列|句|條|項|欄|命中|字元|字)"
    r"|命中\s*[*`~_]{0,2}\s*\d{1,7}"
    r")"
)

# commit SHA：7–40 位十六進位。
#
# ⚠️ **這裡原本多一條「至少含一個 a–f」的條件，已經拿掉 —— 負控當場證明它是錯的。**
# 當初加那條，是想擋掉「一串純數字剛好 7 位」被誤當成 SHA。
# 但本檔的負控用了 `4851465` 當釘樁（它是 `CLAUDE.md` §-2.A 實際引用的 commit），
# 而 **`4851465` 整串都是數字** —— 實測 `git cat-file -t 4851465` → `commit`。
# 也就是說那條件會把一個**真的釘好 SHA 的計數判成沒釘**，
# 而誤紅比漏抓更傷：它教人「這支守衛會亂叫」，然後所有人開始無視它。
#
# 換上的替代防線是下面那個 negative lookahead：一串十六進位數字若**緊接著量詞**
# （「1234567 筆」），那是計數不是 SHA，不算釘。
_SHA = re.compile(
    r"(?<![0-9a-zA-Z])"
    r"(?=[0-9a-f]{7,40}(?![0-9a-zA-Z]))"
    r"[0-9a-f]{7,40}"
    r"(?!\s*[*`~_]{0,2}\s*(?:處|行|檔|筆|個|次|組|列|句|條|項|欄|命中|字))"
)

# 會移動的 ref —— 客戶裁示第 1 條點名禁止的三種寫法。命中它們只是**加註診斷**，
# 判定仍然一律看「有沒有 SHA」：一句話可以同時寫 `origin/main` 與一個 SHA，
# 那樣是合規的（例：`git show <sha>:path`，而散文裡順帶提到主線）。
_MOVING_REF = re.compile(r"origin/main|(?<![\w])HEAD(?![\w])|工作樹")

# 反向檢查的「輸出」長什麼樣。
_OUTPUT_MARKER = re.compile(r"exit\s*=|→|⇒|無輸出|0\s*命中|回\s*非?\s*0|not found|No such")

# 句首全稱詞。⚠️ 這是本檔**唯一**寫出這四個字面的地方 —— 其餘各處一律以
# 「那四個詞」指稱，理由同 `CLAUDE.md` §-2.A 第 8 款（受測字串寫進文件就會被自己掃到）。
_UNIVERSAL_HEADS = ("每一個", "所有", "全部", "都")

# 句首斷言的最短長度：去掉開頭那個詞之後，還要剩至少這麼多字才算一句斷言。
# 擋掉的是表格裡只填兩個字當欄位值的格子 —— 那是**值**，不是斷言。
_MIN_ASSERTION_TAIL = 2

# (C) 的反向檢查視窗：從該句段所在行起算，往下看幾行。
# 取 8 行的理由：`docs/v2/41_counters.md` §41.3 的既有體例是
# 「全稱句一行 ＋ 反向檢查標題一行 ＋ 圍籬 3–5 行」，8 行放得下一整組，
# 又不會跨到下一個條目去撿別人的指令當自己的證據。
_REVERSE_CHECK_WINDOW = 8


class Finding:
    """一筆違規：哪個檔、哪一行、正規化後的句子、以及附註。"""

    __slots__ = ("doc", "line", "text", "note")

    def __init__(self, doc: str, line: int, text: str, note: str = ""):
        self.doc = doc
        self.line = line
        self.text = text
        self.note = note

    @property
    def key(self) -> str:
        """baseline key —— **不含行號**（行號每一輪都在漂，那正是本守衛要治的病）。"""
        raw = f"{self.doc}\0{self.text}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]

    def render(self) -> str:
        body = self.text if len(self.text) <= 160 else self.text[:157] + "…"
        note = f"\n\t\t└ {self.note}" if self.note else ""
        return f"  {self.doc}:{self.line}\t[{self.key}]\n\t\t{body}{note}"


def _own_name_tokens(doc_rel: str) -> tuple[str, str]:
    """回 (repo 相對路徑, 純檔名) —— 檢查 (B) 用來判斷「掃的是不是自己」。"""
    return doc_rel, doc_rel.rsplit("/", 1)[-1]


# ── (A) 計數句必須釘 SHA ────────────────────────────────────────────────
def find_counts_without_sha(doc_rel: str, doc: str) -> list[Finding]:
    """句段同時含「掃描指令」與「數字＋量詞」⇒ 它是一句計數 ⇒ 必須釘 SHA。"""
    out = []
    for seg in split_segments(doc):
        if seg.struck:
            continue
        if not (_SCAN_CMD.search(seg.live) and _COUNT_TOKEN.search(seg.live)):
            continue
        if _SHA.search(seg.live):
            continue
        moving = sorted({m.group(0) for m in _MOVING_REF.finditer(seg.live)})
        note = ("基準是會移動的 ref：" + "、".join(moving)) if moving else "整句找不到任何 commit SHA"
        out.append(Finding(doc_rel, seg.line, seg.text, note))
    return out


# ── (B) 掃描指令不得住在被掃描的檔裡 ──────────────────────────────────
def find_self_scanning_commands(doc_rel: str, doc: str) -> list[Finding]:
    """句段同時含「掃描指令」與「這個檔自己的名字」⇒ 指令自計。"""
    full, base = _own_name_tokens(doc_rel)
    out = []
    for seg in split_segments(doc):
        if seg.struck:
            continue
        if not _SCAN_CMD.search(seg.live):
            continue
        if base not in seg.live:
            continue
        which = full if full in seg.live else base
        # 兩種形態分開描述，讓人一眼判得出該修還是該登記：
        #   * `git show <sha>:<自己>` 讀的是**凍結的 blob**，機制上不會自計 ——
        #     但它**字面違反**客戶裁示第 3 條，故仍然紅燈；要放行請登記 baseline。
        #   * 其餘（對工作樹跑的 grep/wc/sed…）是**真的會把自己算進去**。
        snapshot = bool(re.search(r"git\s+show\s+[0-9a-f]{7,40}:", seg.live))
        note = (f"指令與被掃的檔（{which}）在同一句。"
                + ("這是釘 SHA 的**快照**自掃 —— 機制上不會自計，但字面違反裁示第 3 條"
                   if snapshot else
                   "它會把自己算進去 —— 掃 X 的指令住在 X 裡面"))
        out.append(Finding(doc_rel, seg.line, seg.text, note))
    return out


# ── (C) 句首全稱斷言必須附反向檢查 ────────────────────────────────────
def _is_sentence_initial_universal(text: str) -> str | None:
    """``text`` 已正規化。回傳開頭那個全稱詞，或 ``None``。"""
    for head in _UNIVERSAL_HEADS:
        if text.startswith(head):
            tail = text[len(head):].strip(" 　)）」』】]　")
            if len(tail) >= _MIN_ASSERTION_TAIL:
                return head
    return None


def find_universals_without_reverse_check(doc_rel: str, doc: str) -> list[Finding]:
    """句首全稱斷言，視窗內必須同時看得到「指令」與「輸出」。"""
    lines = doc.split("\n")
    out = []
    for seg in split_segments(doc):
        if seg.struck:
            continue
        head = _is_sentence_initial_universal(seg.text)
        if head is None:
            continue
        window = "\n".join(lines[seg.line - 1: seg.line - 1 + _REVERSE_CHECK_WINDOW])
        has_cmd = bool(_SCAN_CMD.search(window))
        has_out = bool(_OUTPUT_MARKER.search(window))
        if has_cmd and has_out:
            continue
        missing = []
        if not has_cmd:
            missing.append("指令")
        if not has_out:
            missing.append("輸出")
        out.append(Finding(
            doc_rel, seg.line, seg.text,
            f"以「{head}」開頭，但往下 {_REVERSE_CHECK_WINDOW} 行內找不到"
            + "與".join(missing)))
    return out


CHECKS = (
    (SEC_COUNTS, find_counts_without_sha),
    (SEC_SELFSCAN, find_self_scanning_commands),
    (SEC_UNIVERSALS, find_universals_without_reverse_check),
)


# ══════════════════════════════════════════════════════════════════════════
# 受檢檔案 ＋ baseline
# ══════════════════════════════════════════════════════════════════════════
def iter_docs() -> list[tuple[str, str]]:
    """回 [(repo 相對路徑, 內容)]，路徑排序固定。

    ⚠️ **目錄不見了一律 raise，不得靜默回空清單**（`CLAUDE.md` §1 Fail Loud）。
    靜默回空 ＝ 三道檢查全部變成 0 筆違規 ＝ **全綠，而且沒有人會發現**。
    一支綠燈但什麼都沒看的守衛，比一支紅燈的守衛危險得多。
    """
    if not DOCS_DIR.is_dir():
        raise FileNotFoundError(
            f"找不到受檢目錄 {DOCS_DIR.relative_to(REPO_ROOT)}。\n"
            "本守衛的全部價值來自「真的把那些檔讀完」。讀不到就直接炸掉，\n"
            "不要讓它靜默地變成一支什麼都沒檢查的綠燈測試。\n"
            "若目錄是**刻意**搬走或改名，請同步改 `DOCS_DIR`／`DOCS_GLOB`，\n"
            "並重新量測 `_MIN_DOCS` 的下限。")
    paths = sorted(DOCS_DIR.glob(DOCS_GLOB))
    return [(str(p.relative_to(REPO_ROOT)).replace("\\", "/"),
             p.read_text(encoding="utf-8")) for p in paths]


def collect(section: str) -> list[Finding]:
    """跑某一道檢查，回**全部**違規（還沒扣掉 baseline）。"""
    fn = dict(CHECKS)[section]
    out: list[Finding] = []
    for doc_rel, doc in iter_docs():
        out += fn(doc_rel, doc)
    return out


def load_baseline() -> dict[str, dict[str, dict[str, str]]]:
    """讀 baseline。**檔案不存在一律 raise** —— 理由同 `iter_docs`。

    若 baseline 不見了而本函式回空 dict，三道檢查會把**全部**歷史欠債當成新違規，
    一上線就滿江紅；反過來若有人為了變綠而砍掉 baseline 再重建，
    `git diff` 會把那件事攤在 PR 上 —— 那正是本設計要的效果。
    """
    if not BASELINE_PATH.is_file():
        raise FileNotFoundError(
            f"baseline 不見了：{BASELINE_PATH.relative_to(REPO_ROOT)}\n"
            "重建方式：python3 tests/test_doc_counters.py --update-baseline\n"
            "⛔ 重建 ＝ 承認當下所有違規，要有人明確決定（請逐句讀 git diff 再 commit）。")
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    for section, _ in CHECKS:
        data.setdefault(section, {})
    return data


def _new_findings(section: str) -> list[Finding]:
    """扣掉 baseline 之後**還在**的違規 —— 也就是本守衛真正要擋的東西。"""
    known = load_baseline()[section]
    return [f for f in collect(section) if f.key not in known]


_FIX_GUIDE_COMMON = """
⛔ **禁止**：直接把那一行刪掉。本 repo 的慣例是「舊條文保留不刪」，
   刪掉紀錄會讓後人失去「為什麼會變成這樣」的線索，而且是**不可逆**的。
   要退役就照慣例：**加刪除線保留** ＋ 註明「有意識的更正，不是漏刪」＋ 日期 ＋ 決策者
   ＋ 兩邊理由並陳。劃掉之後本守衛就不再檢查它 —— 那正是它該有的行為。

⛔ **禁止**：直接跑 `--update-baseline` 讓它變綠。
   baseline 是**欠債登記簿**，不是豁免按鈕。登記一筆等於簽名承認
   「這句話現在不可重現，我知道」。先試著照上面修；真的修不動才登記，
   並在 PR 描述裡寫明為什麼修不動。
"""

_FIX_GUIDE_A = """
================================================================================
(A) 計數句沒釘 commit SHA —— 怎麼修
================================================================================
(a) **把基準換成 SHA**：`git show <sha>:<path> | grep -c '…' → N`。
    ⚠️ `origin/main` / `HEAD` / `origin/main..HEAD` / 「工作樹」**都不算釘** ——
       它們是會移動的 ref，下一個人照跑會拿到不同的數字。
(b) **兩點式兩端都釘**：`<merge-base sha>..<目標 sha>`，不要只釘一端。
(c) **本輪自己的 commit SHA 寫不出來**（它還沒產生）——
    沿用 `CLAUDE.md` §-2.A 容量登記的既有慣例：基準端釘死那個已存在的 SHA，
    目標端寫「本輪 commit」，並在**下一輪續記時把它換成真的 SHA**。
    這一種請登記進 baseline，並在 PR 描述說明。
""" + _FIX_GUIDE_COMMON

_FIX_GUIDE_B = """
================================================================================
(B) 掃描指令寫進了它自己要掃的那個檔 —— 怎麼修
================================================================================
(a) **把指令移出去**：只留結論與「見 `docs/v2/41_counters.md` §41.x」，
    指令本體寫到那個指標檔裡。這是客戶 2026-09-21 裁示第 3 條的標準走法。
(b) **真的必須在本檔出現**（例如客戶原話逐字碼塊、或正在指出它錯而重述它）——
    那就登記進 baseline，並在 PR 描述寫明是哪一類。

⚠️ **為什麼 SHA 釘死的自掃也照樣紅燈**：這些檔每一輪都在被改，
   而一條住在自己目標裡的指令，遲早會有人拿它對工作樹跑一次 ——
   那一刻它就把自己算進去了。**把指令搬出去是唯一結構上安全的走法。**
""" + _FIX_GUIDE_COMMON

_FIX_GUIDE_C = """
================================================================================
(C) 句首全稱斷言沒有反向檢查 —— 怎麼修
================================================================================
(a) **附反向檢查**（客戶 2026-09-21 裁示原文：沒有反向檢查的，不准寫）：
    在該句底下附**指令 ＋ 輸出 ＋ exit code**，讓這句話可以被推翻。
    體例見 `docs/v2/41_counters.md` §41.3。
(b) **把它改成不是全稱句**：改寫成「**已知的** N 處是…（非窮舉）」之類的
    分類敘述。這正是 `CLAUDE.md` §-1.5.1c 判定 2 的方法教訓：
    **能被一條 grep 推翻的全稱句，就不該寫**。
(c) **它本來就不是斷言**（表格欄位值、客戶原話逐字引用、wireframe 版面草稿裡的
    字樣）—— 那就登記進 baseline，並在 PR 描述寫明它是哪一種。
""" + _FIX_GUIDE_COMMON


def _fail(section: str, headline: str, findings: list[Finding], guide: str) -> None:
    lines = ["", headline, ""]
    for f in sorted(findings, key=lambda x: (x.doc, x.line)):
        lines.append(f.render())
    lines += [
        "",
        "（被刪除線劃掉的句子不算 —— 那是已正確退役的紀錄，本守衛不碰。）",
        f"（上面每一筆方括號裡的 16 位字串，就是它在 baseline `{section}` 區的 key。）",
        guide,
    ]
    raise AssertionError("\n".join(lines))


# ══════════════════════════════════════════════════════════════════════════
# 三道檢查（各自獨立，一道紅不影響另外兩道的可讀性）
# ══════════════════════════════════════════════════════════════════════════
def test_counting_sentences_pin_a_commit_sha():
    """(A) `docs/v2/*.md` 裡**新增的**計數句必須釘 commit SHA。"""
    new = _new_findings(SEC_COUNTS)
    if new:
        _fail(SEC_COUNTS,
              f"`docs/v2/` 有 {len(new)} 句**新增的**計數沒有釘 commit SHA。",
              new, _FIX_GUIDE_A)


def test_scan_commands_do_not_live_in_the_file_they_scan():
    """(B) 掃描指令不得寫在它自己要掃的那個檔裡。"""
    new = _new_findings(SEC_SELFSCAN)
    if new:
        _fail(SEC_SELFSCAN,
              f"`docs/v2/` 有 {len(new)} 句**新增的**指令，寫在它自己要掃的那個檔裡。",
              new, _FIX_GUIDE_B)


def test_sentence_initial_universals_carry_a_reverse_check():
    """(C) 句首全稱斷言必須附反向檢查（指令 ＋ 輸出）。"""
    new = _new_findings(SEC_UNIVERSALS)
    if new:
        _fail(SEC_UNIVERSALS,
              f"`docs/v2/` 有 {len(new)} 句**新增的**句首全稱斷言沒有反向檢查。",
              new, _FIX_GUIDE_C)


# ══════════════════════════════════════════════════════════════════════════
# ⭐ 保護這三道檢查本身的東西（不是第四道規則，是防止前三道無聲失效）
# ══════════════════════════════════════════════════════════════════════════
# 本守衛最危險的失效模式**不是**紅燈，是**綠燈而少看**：
# 有人把某條 regex 收窄、或把 `DOCS_GLOB` 改窄、或目錄被搬走，
# 三道檢查的命中數一起掉到 0，**測試全綠，而且沒有人會發現**。
# 下面的下限就是為了讓那種情況**跌破而紅燈**。
#
# 量測（**全部釘 `0d9753f`**，指令見本檔 `__main__` 的 `--report`）：
#     受檢檔 **25** 個；三道檢查的**違規**命中數 (A) **207**、(B) **30**、(C) **68**
#     （這是**違規數**，不是候選句數；(C) 的候選母體是 84 句，其中 16 句已附反向檢查）。
#     ⚠️ 上列數字**含**已登記進 baseline 的 —— `collect()` 不扣 baseline，下限才擋得住「少看」。
# 下限刻意設得低於現值一大截，理由據實寫出（不是隨手挑一個數）：
#   * 它**擋得住結構性損失** —— 少掉一個 regex 分支、或少掉一半的受檢檔，都會跌破。
#   * 它**擋不住、也刻意不擋逐筆的正常減少** —— 本 repo 鼓勵把過期句子加刪除線退役，
#     那會讓命中數變少。把下限貼著現值，等於把「正確退役」變成紅燈，逼人不敢退役。
# ⚠️ 若哪天真的掉到下限以下：**請改這些常數並在此寫下新的量測與理由**，
#    不要把下限一路往下調到 0 —— 那等於把這個保護拆掉。
_MIN_DOCS = 15
_MIN_TOTAL_FINDINGS = {SEC_COUNTS: 120, SEC_SELFSCAN: 15, SEC_UNIVERSALS: 50}


def test_guard_still_sees_the_documents_it_claims_to_check():
    """受檢檔數與三道檢查的總命中數都不得跌破下限（防「綠燈但少看」）。"""
    docs = iter_docs()
    assert len(docs) >= _MIN_DOCS, (
        f"只看到 {len(docs)} 個受檢檔，低於下限 {_MIN_DOCS}。\n"
        f"（`{DOCS_DIR.relative_to(REPO_ROOT)}/{DOCS_GLOB}`）\n"
        "檔案被搬走／改副檔名／glob 被改窄時，三道檢查會一起靜默失效。")
    for section, floor in _MIN_TOTAL_FINDINGS.items():
        total = len(collect(section))
        assert total >= floor, (
            f"檢查 `{section}` 的總命中數掉到 {total}，低於下限 {floor}。\n"
            "⚠️ 這**不一定**是好消息：命中數大幅下降的兩個成因，\n"
            "   一是真的把文件修好了（那請重新量測並改這裡的下限），\n"
            "   二是**偵測器被收窄了**（那是一次無聲的失效，正是本測試要擋的）。\n"
            "   兩者靠 `git diff` 分辨：改的是 `docs/v2/*.md` 還是本檔的 regex？")


def test_baseline_has_no_unknown_sections_and_is_readable():
    """baseline 結構完整、每一筆都帶得起人看的檔名與句子。"""
    data = load_baseline()
    known = {s for s, _ in CHECKS}
    unknown = {k for k in data if not k.startswith("_")} - known
    assert not unknown, (
        f"baseline 有本檔不認得的分區：{sorted(unknown)}\n"
        "（分區改名會讓那一整區的登記無聲失效 —— 全部變回「新違規」。）")
    for section in known:
        for key, entry in data[section].items():
            assert re.fullmatch(r"[0-9a-f]{16}", key), f"{section} 的 key 形態不對：{key!r}"
            assert isinstance(entry, dict) and entry.get("file") and entry.get("text"), (
                f"{section}/{key} 少了 `file` 或 `text` —— "
                "baseline 必須人讀得懂，否則沒有人能稽核它登記了什麼。")


def test_baseline_entries_that_no_longer_match_are_reported():
    """已修好／已改寫的 baseline 登記會變成「孤兒」，在這裡印出來提醒清理。

    ⚠️ **刻意只印不紅燈**（與 `tests/test_constitution_file_refs.py` 的
    `test_every_exemption_is_still_needed` 不同，理由在此寫明，不是漏抄）：
    那一支的豁免清單只有個位數，而本檔的 baseline 是三位數的**歷史欠債登記簿**。
    只要有人編輯一句已登記的話，它的正規化文字就變了 ⇒ 舊 key 變孤兒、新 key 同時觸發。
    把孤兒也設成紅燈，等於**每一次正常的文字編輯都罰兩次**，
    後果是沒有人敢動 `docs/v2/`。**少看的風險已由上面的下限測試擋住**，
    孤兒在這裡只需要可見。
    """
    data = load_baseline()
    for section, _ in CHECKS:
        live = {f.key for f in collect(section)}
        orphans = [(k, v) for k, v in data[section].items() if k not in live]
        if orphans:
            print(f"\n[warning] baseline `{section}` 有 {len(orphans)} 筆孤兒登記"
                  f"（已修好或已改寫，可以清掉）：")
            for k, v in orphans[:10]:
                print(f"  [{k}] {v['file']}  {v['text'][:80]}")
            if len(orphans) > 10:
                print(f"  …另有 {len(orphans) - 10} 筆未列出")


# ══════════════════════════════════════════════════════════════════════════
# ⭐ 正控 ＋ 負控 —— 沒有正控的綠燈 ＝ 沒有檢查
# ══════════════════════════════════════════════════════════════════════════
# 一支「什麼都抓不到」的守衛也會全綠。下面每一道檢查都配一個**刻意造的違規**
# （正控：必須被抓到）與一個**乾淨的句子**（負控：必須不被誤報）。
# ⚠️ 本段的字串**刻意長成違規的樣子** —— 那就是正控的定義。
#    故下方的自我合規測試把射程限在**模組 docstring**，並就地寫明，不藏。
_DEMO = "docs/v2/99_demo.md"


def test_control_A_unpinned_count_fires_and_pinned_count_does_not():
    bad = "實測 `git grep -n 'X' -- '*.py'` → **7 處**"
    good = "實測 `git show 4851465:CLAUDE.md | grep -c 'X'` → **7 處**"
    assert len(find_counts_without_sha(_DEMO, bad)) == 1, "正控失效：沒釘 SHA 的計數沒有被抓到"
    assert find_counts_without_sha(_DEMO, good) == [], "負控失效：釘了 SHA 的計數被誤報"


def test_control_A_moving_refs_are_not_accepted_as_pinned():
    for ref in ("origin/main", "HEAD", "工作樹"):
        doc = f"實測 `git grep -c 'X' {ref}` → **12 筆**"
        found = find_counts_without_sha(_DEMO, doc)
        assert len(found) == 1, f"正控失效：以 {ref} 當基準的計數沒有被抓到"
        assert "會移動的 ref" in found[0].note, f"診斷訊息沒有點名 {ref}"


def test_control_A_struck_through_count_does_not_fire():
    doc = "~~實測 `git grep -n 'X' -- '*.py'` → **7 處**~~ → 已於 4851465 撤銷"
    assert find_counts_without_sha(_DEMO, doc) == [], "負控失效：被劃掉的舊計數不該被檢查"


def test_control_B_self_scan_fires_and_scanning_another_file_does_not():
    bad = "實測 `grep -c 'X' docs/v2/99_demo.md` → **3 處**"
    good = "實測 `grep -c 'X' docs/v2/20_ui_spec.md` → **3 處**"
    assert len(find_self_scanning_commands(_DEMO, bad)) == 1, "正控失效：指令自計沒有被抓到"
    assert find_self_scanning_commands(_DEMO, good) == [], "負控失效：掃別的檔被誤報成自計"


def test_control_B_mentioning_own_name_without_a_command_does_not_fire():
    doc = "本節的結論寫在 docs/v2/99_demo.md 第二段，指令見 41_counters.md"
    assert find_self_scanning_commands(_DEMO, doc) == [], "負控失效：只提到自己檔名不算指令自計"


def test_control_C_bare_universal_fires_and_one_with_a_reverse_check_does_not():
    bad = "所有欄位都已經查過了"
    good = ("所有欄位都已經查過了\n"
            "- 反向檢查：`git grep -n 'Y' -- '*.py'` → **0 命中**，exit=1")
    assert len(find_universals_without_reverse_check(_DEMO, bad)) == 1, \
        "正控失效：沒有反向檢查的句首全稱斷言沒有被抓到"
    assert find_universals_without_reverse_check(_DEMO, good) == [], \
        "負控失效：附了反向檢查的全稱句被誤報"


def test_control_C_mid_sentence_universal_does_not_fire():
    """句**中**的副詞不是句首斷言 —— 這正是 1915 收斂到 86 的那一刀。"""
    doc = "本組三處實測結果都一致，沒有例外"
    assert find_universals_without_reverse_check(_DEMO, doc) == [], \
        "負控失效：句中副詞被誤判成句首斷言"


def test_control_C_table_cell_that_is_just_a_value_does_not_fire():
    doc = "| 射程 | 全部 | 見 §2 |"
    assert find_universals_without_reverse_check(_DEMO, doc) == [], \
        "負控失效：表格裡只填兩個字的欄位值被誤判成斷言"


def test_control_C_struck_through_universal_does_not_fire():
    doc = "~~所有欄位都已經查過了~~ → 2026-09-21 撤銷，見 4851465"
    assert find_universals_without_reverse_check(_DEMO, doc) == [], \
        "負控失效：被劃掉的舊全稱句不該被檢查"


def test_control_normalization_collapses_markup_but_not_wording():
    a = normalize("- **所有**　欄位　`都` 查過了")
    b = normalize("所有 欄位 都 查過了")
    assert a == b == "所有 欄位 都 查過了", f"正規化結果不如預期：{a!r} / {b!r}"
    assert normalize("所有欄位查過了") != a, "正規化不該把不同的句子壓成同一個 key"


def test_control_baseline_key_ignores_line_number_but_not_file():
    f1 = Finding("docs/v2/a.md", 10, "所有欄位都查過了")
    f2 = Finding("docs/v2/a.md", 999, "所有欄位都查過了")
    f3 = Finding("docs/v2/b.md", 10, "所有欄位都查過了")
    assert f1.key == f2.key, "key 不該隨行號改變（行號每一輪都在漂）"
    assert f1.key != f3.key, "key 必須含檔案路徑（豁免不得跨檔通用）"


# ══════════════════════════════════════════════════════════════════════════
# ⭐ 守衛自己不得違反它自己的三道規則
# ══════════════════════════════════════════════════════════════════════════
# 自我合規檢查的**唯一**豁免。體例與理由寫法沿用
# `tests/test_constitution_file_refs.py` 的 `EXEMPTIONS`：
# **理由必須說明「為什麼這個位置是對的」，不是「它長得像什麼」。**
#
# ⚠️ 只有一種東西進得來：**客戶原話的逐字引用**。
#    `CLAUDE.md` §-1.5.1／§-1.5.1a／§-1.5.1c 三處都明文寫著客戶頒布原文
#    「**不得刪改或「優化」**」。若本測試要求把客戶那句話改寫才會變綠，
#    它就是在逼人做憲法明文禁止的事 —— **那是一支壞掉的守衛**
#    （同前例對 Tier 2 裸檔名的處置理由：一條要求修改 user 逐字封存才能變綠的守衛，
#    是壞掉的守衛）。
# ⛔ **不得**把本組自己寫的句子加進來。自己的句子改寫得動，改寫就是了 ——
#    本輪就有一句（正規化規則第 3 條）是這樣改掉的，不是登記進來的。
_DOCSTRING_ALLOWED: dict[str, str] = {
    "c0b3736b72bd998b": (
        "客戶 2026-09-21 裁示第 1 條的**逐字原文**（本檔 docstring 開頭的法源引用）。"
        "它確實以那四個詞之一開頭、也確實沒有附反向檢查 —— 但它是**客戶頒布的規則本身**，"
        "不是本組對事實的斷言，本來就沒有東西可以反向檢查。"
        "而且 `CLAUDE.md` §-1.5.1／§-1.5.1a／§-1.5.1c 三處明文規定客戶原文"
        "「不得刪改或『優化』」⇒ **改寫它才能變綠是憲法禁止的解法**。"
    ),
}


def _docstring_findings() -> list[tuple[str, Finding]]:
    doc = __doc__ or ""
    out = []
    for section, fn in CHECKS:
        for f in fn("tests/test_doc_counters.py", doc):
            out.append((section, f))
    return out


def test_this_guards_own_docstring_obeys_the_three_rules():
    """本檔的**模組 docstring** 自己跑一次三道檢查，零容忍、不吃 baseline。

    **射程就是 docstring，不含檔內其餘部分 —— 這一句是界線，不是免責**：
    檔內那一整段正控／負控的字串**刻意**長成違規的樣子（那是正控的定義），
    把它們一起掃會讓本測試永遠紅。**守衛對外做的宣稱住在 docstring 裡**，
    所以那裡是零容忍的；`_DOCSTRING_ALLOWED` 是唯一的出口，而且只收客戶原話逐字引用。
    """
    doc = __doc__ or ""
    assert doc.strip(), "模組 docstring 不見了 —— 本測試會變成空掃"
    problems = [
        f"[{section}] docstring 第 {f.line} 行  [{f.key}]\n      {f.text[:140]}\n      ← {f.note}"
        for section, f in _docstring_findings() if f.key not in _DOCSTRING_ALLOWED
    ]
    assert not problems, (
        "\n本守衛的 docstring 自己違反了它自己的規則：\n    "
        + "\n    ".join(problems)
        + "\n\n⚠️ 這不是小事：本 repo 連續數輪栽在「治這個病的東西自己犯這個病」。\n"
          "   一份要求別人釘 SHA 的文件，自己的數字沒釘 SHA，就沒有立場要求任何人。\n"
          "   **修 docstring，不要改這個測試** —— 除非那句話是客戶原話逐字引用，\n"
          "   那才走 `_DOCSTRING_ALLOWED`（理由要寫清楚為什麼那個位置是對的）。")


def test_every_docstring_exemption_is_still_needed():
    """`_DOCSTRING_ALLOWED` 只能因為「現在還需要」而存在，不能因為「以前需要過」而留著。

    （體例取自 `tests/test_constitution_file_refs.py::test_every_exemption_is_still_needed`。
    豁免清單一旦可以留著沒人用的條目，就會慢慢變成一張沒有人敢動的白名單。）
    """
    live = {f.key for _, f in _docstring_findings()}
    stale = sorted(set(_DOCSTRING_ALLOWED) - live)
    assert not stale, (
        f"`_DOCSTRING_ALLOWED` 有 {len(stale)} 筆已經用不到了，請刪掉：\n  "
        + "\n  ".join(f"[{k}] {_DOCSTRING_ALLOWED[k]}" for k in stale))



# ══════════════════════════════════════════════════════════════════════════
# CLI —— 重建 baseline ／ 現況報表
# ══════════════════════════════════════════════════════════════════════════
_BASELINE_README = [
    "這是 tests/test_doc_counters.py 的 baseline —— 一份**歷史欠債登記簿**，不是豁免清單。",
    "每一筆代表：這句話在規則訂立之前就寫在那裡了，本守衛暫時不為它紅燈。",
    "登記一筆 ＝ 簽名承認「這句話現在不可重現／不可推翻，我知道」。",
    "",
    "key ＝ sha256(檔案相對路徑 + NUL + 正規化後的句子)[:16]。**刻意不含行號** ——",
    "這個 repo 的行號每一輪都在漂，那正是本守衛要治的病之一。",
    "正規化規則的權威定義在 tests/test_doc_counters.py 的模組 docstring 與 normalize()。",
    "",
    "重建：python3 tests/test_doc_counters.py --update-baseline [<rev>]（省略 <rev> ＝ HEAD）",
    "產生端讀的是 _generated_from_sha 那個 commit，**不是工作樹** —— 所以它可以被原樣重建。",
    "⛔ 重建等於承認當下**全部**違規。跑完請逐句讀 git diff 再 commit ——",
    "   那份 diff 就是你在簽名承認的東西。正解一律是先照 _FIX_GUIDE_* 修，修不動才登記。",
]


def _report() -> int:
    print(f"受檢目錄：{DOCS_DIR.relative_to(REPO_ROOT)}/{DOCS_GLOB}")
    docs = iter_docs()
    print(f"受檢檔數：{len(docs)}")
    try:
        base = load_baseline()
    except FileNotFoundError:
        base = {s: {} for s, _ in CHECKS}
        print("（baseline 尚未存在，下面的『新增』欄等同總數）")
    for section, _ in CHECKS:
        found = collect(section)
        new = [f for f in found if f.key not in base[section]]
        print(f"  {section:36s} 總命中 {len(found):4d}   已登記 {len(base[section]):4d}"
              f"   新增 {len(new):4d}")
    return 0


def _git(*args: str) -> str:
    r = subprocess.run(("git", "-C", str(REPO_ROOT)) + args,
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失敗（exit={r.returncode}）：{r.stderr.strip()}")
    return r.stdout


def docs_at_sha(sha: str) -> list[tuple[str, str]]:
    """從**釘死的 commit** 讀受檢檔，而不是讀工作樹。

    ⚠️ **這一段是本檔自己的裁示第 1 條**：baseline 是一份會被 commit 進 repo、
    被後人引用的清單 —— 它若產生自「工作樹」，就**沒有人能原樣重建它**，
    下一個人跑 `--update-baseline` 會拿到一份不一樣的清單而不知道為什麼。
    一份要求別人釘 SHA 的守衛，自己的 baseline 產生自工作樹，就沒有立場要求任何人。

    ⚠️ **測試本身仍然讀工作樹**（`iter_docs`）—— 那是對的：
    守衛要判的是**現在**的內容。釘 SHA 的只有 baseline 的產生端。
    """
    prefix = f"{DOCS_DIR.relative_to(REPO_ROOT)}/".replace("\\", "/")
    names = [n for n in _git("ls-tree", "-r", "--name-only", sha, "--", prefix).splitlines()
             if n.startswith(prefix) and n.endswith(DOCS_GLOB.lstrip("*"))
             and "/" not in n[len(prefix):]]
    if not names:
        raise RuntimeError(f"在 {sha} 上找不到任何 {prefix}{DOCS_GLOB} —— 拒絕產生一份空的 baseline。")
    return [(n, _git("show", f"{sha}:{n}")) for n in sorted(names)]


def _update_baseline(rev: str = "HEAD") -> int:
    sha = _git("rev-parse", rev).strip()
    docs = docs_at_sha(sha)
    print(f"baseline 來源：commit {sha}（{len(docs)} 個受檢檔）—— **不是工作樹**")
    data: dict[str, object] = {"_README": _BASELINE_README, META_SHA: sha}
    total = 0
    for section, fn in CHECKS:
        found: list[Finding] = []
        for doc_rel, doc in docs:
            found += fn(doc_rel, doc)
        entries: dict[str, dict[str, str]] = {}
        for f in sorted(found, key=lambda x: (x.doc, x.line)):
            entries.setdefault(f.key, {"file": f.doc, "text": f.text})
        data[section] = dict(sorted(entries.items(), key=lambda kv: (kv[1]["file"], kv[1]["text"])))
        total += len(entries)
        print(f"  {section:36s} 命中 {len(found):4d} → 去重後 {len(entries):4d} 筆")
    BASELINE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8")
    print(f"已寫入 {BASELINE_PATH.relative_to(REPO_ROOT)}（合計 {total} 筆）")
    print("⛔ 請逐句讀 `git diff` 再 commit —— 那份 diff 就是你在簽名承認的東西。")
    return 0


if __name__ == "__main__":
    _args = sys.argv[1:]
    if _args and _args[0] == "--update-baseline" and len(_args) <= 2:
        raise SystemExit(_update_baseline(_args[1] if len(_args) == 2 else "HEAD"))
    if _args == ["--report"] or not _args:
        raise SystemExit(_report())
    print(__doc__)
    print("用法：python3 tests/test_doc_counters.py [--report | --update-baseline [<rev>]]")
    raise SystemExit(2)
