"""憲法（`CLAUDE.md`）檔案引用守衛 —— 讓「引用了不存在的檔案／指到檔尾之外的行號」在 CI 轉紅燈。

**為什麼要有這支測試**
`CLAUDE.md` 是本 repo 唯一沒有機器守衛的 SSOT：在本檔出現之前，全 repo 只有
`tests/test_retired_exception_ids.py` 會打開它，而那支只解析表格第一格的 `EX-` ID。
於是憲法可以無聲地過期 —— 一次重構把檔案搬走／改名，憲法不會有任何反應，
直到幾個月後某個人偶然讀到。§2.1「TW 出口 YoY」那一條就是這樣連續兩輪被當成事實派工。

**本守衛守的是未來，不是現在。** 它抓到的現存違規只是副產品；真正的價值是
「下一次搬檔案時，憲法會當場紅燈」。

---
## 檢查什麼

對 `CLAUDE.md` 內**活的**（見下）路徑引用：

* **(A) 存在性** —— 被引用的檔案必須存在。
* **(B) 行號界內** —— `路徑:行號` 的行號不得超過該檔實際行數（`起-迄` 取迄，逗號串取最大）。

## 「活的」是什麼意思 —— 本檔最重要的一條

本 repo 的核心慣例是「**舊條文保留不刪 ＋ 加刪除線**」（見 `CLAUDE.md` §-1.5 各處）。
因此檔內大量 `~~repositories/fund_repository.py~~` 是**已經被正確退役的紀錄**，
它們指向不存在的檔案**是正常的、是對的**。

**本守衛只檢查沒有被 `~~` 包住的引用。** 若不這樣做，這條守衛會逼著後人去刪歷史紀錄，
正好摧毀本 repo 最重要的那條慣例 —— 那是**不可逆**的傷害，遠大於漏抓一筆。

## 兩層嚴格度（為什麼 bare 檔名只給 warning，不紅燈）

* **Tier 1（紅燈）**：含 `/` 的路徑，例如 `services/fund_service.py`。
  這種寫法是明確的 repo 相對路徑，對錯可判定。
* **Tier 2（只印 warning，永不紅燈）**：不含 `/` 的裸檔名，例如 `sources.py`。

Tier 2 刻意不紅燈，理由**不是**「太吵」，而是**它在本 repo 結構上無法被滿足**：
`CLAUDE.md` §-1.5.1c 收錄了 user 的 v3 逐字頒布原文，該區塊明文規定
「**不得刪改或「優化」**」；而那段原文裡就寫著 `tab1_macro.py`、`tab3_portfolio.py`
（那是姊妹 repo `my-Fund-dashboard` 以外的檔名，本 repo 沒有這兩個檔）。
**一條要求修改 user 逐字封存才能變綠的守衛，是壞掉的守衛**，
它只會逼人去做憲法明文禁止的事。故裸檔名一律降為可見的 warning。

---
## ⚠️ 射程外：兩個**已知漏抓**（是「還沒解決」，不是「已解決」）

⛔ 下面兩項**不得**被讀成「守衛已經涵蓋」。它們是刻意留下的缺口，就地登記在這裡，
   免得後人從綠燈推論出「憲法的檔案引用已經全部查過了」——**那個推論是錯的**。

### 缺口 1｜Tier 2 裸檔名只印 warning，其中混著真違規

* **量測（量測日 2026-09-05）**：活的裸檔名 **200** 筆，其中 repo 根目錄找不到的 **78** 筆
  只會印 warning。裡面確實有真違規（例：`crisis_strategy_grid.py`、`auto_search_store_gs.py`
  ——都是已刪除的檔，卻以裸檔名活在憲法裡）。
* **為什麼不現在補**：降級理由是**結構性**的（見上方 Tier 2 段：v3 逐字頒布原文禁改，
  而那段原文內就有 `tab1_macro.py` / `tab3_portfolio.py`）。**先把它變紅是做不到的**，
  必須先解決「怎麼在不動逐字封存的前提下區分兩者」。
* **要擴 Tier 2 的人，從這裡開始（觸發點）**：
  1. 先決定**逐字封存區塊怎麼被排除** —— 目前檔內的 fenced code block 起訖可用
     ``` 圍籬配對取得（實測：7 組，v3 原文為第 1 組）；blockquote 形式的 v1 封存則沒有機器邊界，
     需要另立錨點（例如在 §-1.5.1 前後加不可見標記，或改用行號區間常數並由測試自我校驗）。
  2. 排除之後，再把 `Reference.is_tier1` 的判定放寬到「裸檔名 ＋ 能在 repo 內唯一 basename 解析」，
     多重 basename 命中維持 warning（那是真的沒辦法判定的）。
  3. **不要**用「把 78 筆塞進 EXEMPTIONS」的方式讓它變綠 —— 那是本檔明令禁止的作法。

### 缺口 2｜只驗「檔案在不在、行號界不界內」，**不驗語意**

* 憲法說「符號 X 住在檔 Y」而 **Y 存在、行號也在界內、但那一行根本不是 X**，
  本守衛**不會**發現。
* **這不是假設，本輪就踩到一個**：§3.2／§4.1 原寫 `services/portfolio_service.py:424`
  （該檔 933 行，行號完全界內 → 守衛綠燈），但 `sed -n '424p'` 實測那一行是
  `# ── 最大回撤 ──` 註解，**不是**它自稱的 jaccard/cosine 實作。
  那一筆是**人工實測補上的，不是守衛抓到的**。
* **要補的人，從這裡開始（觸發點）**：需要「路徑 ＋ 符號名」形式的引用（`檔案::符號`）
  才可能機器驗 —— 而憲法目前**混用**行號式與符號式。合理的順序是
  **先把行號式引用逐步換成符號式**（§8.2.A.0 規則 1 本來就要求這樣寫），
  換完之後再加一條「`::符號` 必須真的在該檔內以 AST 找得到」的守衛。
  **在那之前，任何『憲法的 evidence 已經驗過了』的宣稱都只涵蓋存在性與行號界線兩件事。**
"""

from __future__ import annotations

import bisect
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ══════════════════════════════════════════════════════════════════════════
# 憲法**不只一個檔**(2026-09-08 拆檔)
# ══════════════════════════════════════════════════════════════════════════
# `§8.2.A` 例外表與 `§8.3.P` 待判定表已搬到 `EXCEPTIONS.md`,`CLAUDE.md` 原位置
# 只留指標段。**兩個都要讀。**
#
# ⚠️ **這裡是本檔最容易安靜壞掉的地方,講清楚為什麼**:
# 拆檔當下若只留 `CLAUDE.md`,本守衛**不會紅燈** —— `hard` 照樣是 0、測試照樣綠。
# 它只是**少看了 229 筆活的 Tier-1 引用**(拆檔前全檔 413 筆的 **55.4%**),
# warning 由 80 掉到 57。**一支綠燈但少看一半的守衛,比一支紅燈的守衛危險得多** ——
# 下一個人會從綠燈推論出「憲法的檔案引用已經全部查過了」,而那個推論是錯的。
# → 故本檔除了讀多檔之外,另備一條 **liveness 下限**
#   (`test_guard_still_sees_the_whole_constitution`),見該處。
CONSTITUTION_FILES: tuple[Path, ...] = (
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "EXCEPTIONS.md",   # ← `8.2.A` 例外表 ＋ `8.3.P` 待判定表的現住址
)

# 向後相容:檔內既有敘述與外部引用仍以 `CLAUDE.md` 為憲法主檔。
CONSTITUTION = CONSTITUTION_FILES[0]


def _read_constitution_files() -> list[tuple[str, str]]:
    """回 [(顯示用檔名, 內容)]。**缺檔一律 raise,不得靜默跳過**(§1 Fail Loud)。

    ⚠️ 這個 `raise` 是拆檔之後**唯一**擋得住「路徑寫錯 / 檔案被改名」的東西。
    若改成 `if p.exists()` 靜默跳過,把 `EXCEPTIONS.md` 打成任何錯字都不會有人發現:
    那一半的引用默默不再被檢查,而測試**照樣綠**。**寧可炸掉,不可假裝有讀到。**
    """
    missing = [str(p.relative_to(REPO_ROOT)) for p in CONSTITUTION_FILES
               if not p.is_file()]
    if missing:
        raise FileNotFoundError(
            "憲法檔不見了:" + "、".join(missing) + "\n"
            "本守衛的全部價值來自「真的把憲法讀完」。讀不到其中一個檔,"
            "它就會少檢查那個檔裡的所有引用,而且**不會紅燈** —— 故此處直接炸掉。\n"
            "若檔案是**刻意**改名或再拆,請同步改 `CONSTITUTION_FILES`,"
            "並重新量測 `_MIN_LIVE_TIER1_REFS` 的下限。")
    return [(str(p.relative_to(REPO_ROOT)), p.read_text(encoding="utf-8"))
            for p in CONSTITUTION_FILES]

# --------------------------------------------------------------------------
# 刪除線解析
# --------------------------------------------------------------------------
# 實測（量測日 2026-09-05，`CLAUDE.md` @ origin/main 3909339）：
#   130 組 `~~` 配對、全部平衡；跨行的只有 1 組（§-1.5.5 盲點 1，橫跨 2 行）；
#   最長一組 432 字元。
# 下面兩個上限給了充裕餘裕，但**刻意有限** —— 若日後有人寫出單邊 `~~`，
# 全域貪婪配對會讓它後面所有引用一起翻面（該檢查的變成不檢查）。
# 有上限的話，配不到伴的 `~~` 會被當成普通文字，影響只留在原地。
_MAX_STRIKE_NEWLINES = 2
_MAX_STRIKE_CHARS = 1500


def strike_mask(text: str) -> bytearray:
    """回傳與 ``text`` 等長的遮罩，被 ``~~ ~~`` 包住的位置為 1。"""
    mask = bytearray(len(text))
    i = 0
    while True:
        open_at = text.find("~~", i)
        if open_at < 0:
            return mask
        limit = min(len(text), open_at + 2 + _MAX_STRIKE_CHARS)
        close_at = text.find("~~", open_at + 2, limit)
        if close_at < 0 or text.count("\n", open_at, close_at) > _MAX_STRIKE_NEWLINES:
            # 配不到伴 → 視為普通文字，不吃掉後面的內容
            i = open_at + 2
            continue
        for k in range(open_at, close_at + 2):
            mask[k] = 1
        i = close_at + 2


# --------------------------------------------------------------------------
# 路徑抽取
# --------------------------------------------------------------------------
_EXT = "py|md|yml|yaml|json|txt|toml|cfg|ini|parquet|html|csv"

# 前置的 negative lookbehind 擋掉 glob 前綴（`ui/tab*.py`、`docs/*.md`）與
# 半個識別字被切開的情形；結尾的 lookahead 擋掉 `shared/schemas.SOME_CONST`
# 這種「有斜線但結尾不是副檔名」的模組路徑。
_PATH_RE = re.compile(
    r"(?<![\w/.*?\[\]-])"
    r"((?:\.?[\w.-]+/)*[\w.-]+\.(?:" + _EXT + r"))"
    r"(?![\w.])"
    r"(?::(\d+(?:[-,]\d+)*))?"
)


class Reference:
    __slots__ = ("md_line", "path", "linespec", "struck")

    def __init__(self, md_line: int, path: str, linespec: str | None, struck: bool):
        self.md_line = md_line
        self.path = path
        self.linespec = linespec
        self.struck = struck

    @property
    def cited(self) -> str:
        return f"{self.path}:{self.linespec}" if self.linespec else self.path

    @property
    def is_tier1(self) -> bool:
        return "/" in self.path

    def max_cited_line(self) -> int | None:
        if not self.linespec:
            return None
        return max(int(n) for n in re.findall(r"\d+", self.linespec))


def parse_references(text: str) -> list[Reference]:
    mask = strike_mask(text)
    starts = [0]
    for idx, ch in enumerate(text):
        if ch == "\n":
            starts.append(idx + 1)
    out = []
    for m in _PATH_RE.finditer(text):
        out.append(
            Reference(
                md_line=bisect.bisect_right(starts, m.start()),
                path=m.group(1),
                linespec=m.group(2),
                struck=bool(mask[m.start()]),
            )
        )
    return out


# --------------------------------------------------------------------------
# 豁免清單
# --------------------------------------------------------------------------
# ⚠️ 依 `CLAUDE.md` §8.2.A.0 規則 5：理由必須說明「**為什麼這個位置是對的**」，
#    不是「它長得像什麼」。豁免**不得**用來塞真違規。
# ⚠️ 未被用到的豁免會讓 `test_every_exemption_is_still_needed` 紅燈 ——
#    這是刻意的：清單只能因為「現在還需要」而存在，不能因為「以前需要過」而留著。
EXEMPTIONS: dict[str, str] = {
    "test_schemas_phase_a/b/b2/b3/b_foreign_flow/c.py": (
        "§3.1 的散文列舉縮寫，指 6 個檔（test_schemas_phase_a.py、…_b.py、…）。"
        "此處的 `/` 是**選項分隔符，不是目錄分隔符** —— 它從來不是一個路徑，"
        "是本守衛 parser 的形態誤判，不是憲法的錯。"
    ),
}

# ⛔ **一個被考慮過、而且刻意否決的豁免類別，寫在這裡免得下一個人重新發明它**
#
# 檔內有一整類引用，長成「這句話本身就在說該檔已經不存在」，例如：
#   * §2.1「**實測**：`ls repositories/fund_repository.py` → No such file」
#   * §8.3「`repositories/tw_macro_repository.py` 已因 production 0 caller 實體刪除」
#   * §8.2.A.1「`.github/workflows/fetch_nav_cache.yml` 在本次量測時已不存在」
#
# 這些敘述**為真且現行**，直覺上會想豁免它們。本守衛**不豁免**，三個理由：
#
# 1. **憲法自己已經有正解，而且已經在用。** §-1.5.1c 判定 4 與 §8.2 的
#    `~~repositories/tw_macro_repository.py~~ / …` 就是把**路徑本身**劃掉、
#    **句子照留**。劃掉的是「這個路徑現在指得到東西」這個宣稱，不是那句話的內容。
#    所以這一類根本不需要豁免 —— 它需要的是**把既有慣例套用完整**。
#    本守衛抓到的正是「同一個檔，§8.2 劃掉了、§8.3 沒劃掉」這種**憲法自己的不一致**。
#
# 2. **判定它需要讀懂語意，而語意規則會被繞過。** 若改成偵測「不存在／已刪除／
#    No such file」等字樣就放行，那任何人只要在句子裡加四個字就能讓守衛閉嘴 ——
#    比起「在豁免清單加一行」，這是更隱蔽、更難稽核的逃生口。
#
# 3. **不對稱地用同一把尺，是本 repo 點名過的失效模式。** §8.2.A.1 驗證段 ④ 記載：
#    「例外表最常見的失效模式不是『條件寫錯』，是『**條件只往外用、不往內用**』。」
#    豁免了 `.github/workflows/…`、卻讓形態完全相同的 `tw_macro_repository.py` 紅燈，
#    就是那個失效模式本身。要嘛三個都豁免，要嘛三個都不豁免 —— 本守衛選後者。


# --------------------------------------------------------------------------
# 檢查
# --------------------------------------------------------------------------
def _line_count(path: Path) -> int:
    data = path.read_bytes()
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def audit(text: str, root: Path):
    """回傳 (hard_violations, tier2_warnings, used_exemptions)。"""
    hard, warns, used = [], [], set()
    for ref in parse_references(text):
        if ref.struck:
            continue
        if ref.path in EXEMPTIONS:
            used.add(ref.path)
            continue
        target = root / ref.path
        if not ref.is_tier1:
            if not target.exists():
                warns.append((ref, "裸檔名，repo 根目錄下找不到（Tier 2：只提醒，不紅燈）"))
            continue
        if not target.exists():
            hard.append((ref, "檔案不存在"))
            continue
        cited = ref.max_cited_line()
        if cited is not None:
            actual = _line_count(target)
            if cited > actual:
                hard.append((ref, f"行號超出檔尾：引用第 {cited} 行，該檔實際只有 {actual} 行"))
    return hard, warns, used


_FIX_GUIDE = """
================================================================================
怎麼修（下面三條都合法，挑一條；**不要**自創第四條）
================================================================================
(a) **更正成現行路徑／行號** —— 該檔只是被搬走或改名，把引用指到它現在的位置。
    ⚠️ 依 `CLAUDE.md` §8.2.A.0 規則 1，**新的引用請不要再寫行號** ——
       行號在任何一次重構後就失效，而重構不會觸發本清單更新。
       改用「檔案路徑 ＋ 符號名 ＋ 模式描述」。

(b) **依本檔慣例退役** —— 該引用講的是一段已經結束的歷史，那就
    **加刪除線保留**（`~~舊路徑~~`）＋ 註明「**有意識的更正，不是漏刪**」
    ＋ 日期 ＋ 決策者 ＋ **兩邊理由並陳**（舊表述當時為什麼是對的、被權衡掉的是什麼）。
    劃掉之後本守衛就不再檢查它 —— 那正是它該有的行為。

(c) **這句話本來就是在說「該檔已經沒了」** —— 那就只把**路徑**劃掉、**句子照留**：
    `~~repositories/tw_macro_repository.py~~ 已因 production 0 caller 實體刪除`。
    劃掉的是「這個路徑現在指得到東西」這個宣稱，不是那句話的內容 ——
    敘述仍然為真、仍然看得到，而守衛不再把它當成一個活的路徑。
    ⚠️ 這不是新發明的寫法：`CLAUDE.md` §8.2 對**同一個檔**已經是這樣寫的，
       只是 §8.3 那一處沒跟上。本守衛抓到的就是這種**憲法自己的前後不一致**。

⛔ **禁止**：直接把那一行刪掉。
   本 repo 的慣例是「舊條文保留不刪」；刪掉紀錄會讓後人失去「為什麼會變成這樣」的線索，
   而且是**不可逆**的。

⛔ **禁止**：把它加進本檔的 `EXEMPTIONS` 了事。
   豁免只給「引用本身沒有錯、是守衛看錯」的情形（例如散文縮寫被誤判成路徑），
   **不給**「這個檔真的不見了但我不想處理」。
================================================================================
"""


def test_constitution_has_no_dangling_file_references():
    """憲法各檔內**活的**路徑引用，必須指向存在的檔案與界內的行號。

    ⚠️ 2026-09-08 起憲法是多個檔（見 `CONSTITUTION_FILES`）—— **每一個都要掃**。
    """
    all_hard: list[tuple[str, Reference, str]] = []
    all_warns: list[tuple[str, Reference, str]] = []
    for fname, text in _read_constitution_files():
        hard, warns, _ = audit(text, REPO_ROOT)
        all_hard += [(fname, r, w) for r, w in hard]
        all_warns += [(fname, r, w) for r, w in warns]

    if all_warns:
        print(f"\n[warning] Tier 2 裸檔名引用 {len(all_warns)} 筆（不影響成敗，僅供追蹤）：")
        for fname, ref, why in all_warns[:20]:
            print(f"  {fname}:{ref.md_line}  {ref.cited}  — {why}")
        if len(all_warns) > 20:
            print(f"  …另有 {len(all_warns) - 20} 筆未列出")

    if all_hard:
        lines = [
            "",
            f"憲法有 {len(all_hard)} 筆**活的**引用指向不存在的檔案或界外的行號。",
            "（被 `~~刪除線~~` 包住的引用不算 —— 那是已正確退役的紀錄，本守衛不碰。）",
            "",
        ]
        for fname, ref, why in sorted(all_hard, key=lambda x: (x[0], x[1].md_line)):
            lines.append(f"  {fname}:{ref.md_line}\t{ref.cited}\n\t\t→ {why}")
        lines.append(_FIX_GUIDE)
        raise AssertionError("\n".join(lines))


# ══════════════════════════════════════════════════════════════════════════
# ⭐ liveness 下限 —— 本檔在 2026-09-08 拆檔前**沒有**這一條，而那正是它最大的洞
# ══════════════════════════════════════════════════════════════════════════
# 量測（量測日 2026-09-08，拆檔前 `CLAUDE.md` @ ba3b06d）：
#     活的 Tier-1 引用 **413** 筆 = `CLAUDE.md` 其餘各節 184 ＋ §8.2.A 124 ＋ §8.3.P 105。
# 也就是說：**拆檔時若漏掉 `EXCEPTIONS.md`，這支守衛會少看 229 筆（55.4%）而照樣綠燈。**
#
# 下限刻意設在 **300**，理由據實寫出（不是隨手挑一個數）：
#   * 它**擋得住結構性損失** —— 掉任一個憲法檔都會跌破它
#     （少了 `EXCEPTIONS.md` → 184；少了 `CLAUDE.md` → 229；兩者都 < 300）。
#   * 它**擋不住、也刻意不擋逐筆的正常增減** —— 本 repo 鼓勵把過期引用
#     加刪除線退役（那會讓活的引用變少），把下限貼著現值會把「正確退役」變成紅燈，
#     逼人不敢退役。**那是反效果。**
# ⚠️ 若哪天憲法真的瘦到 300 以下：**請改這個常數並在此寫下新的量測與理由**，
#    不要把這條測試刪掉或改成 `>= 0`。刪掉它 = 把 2026-09-08 這個教訓一起刪掉。
_MIN_LIVE_TIER1_REFS = 300

# ── 第二道：per-file 下限 ──────────────────────────────────────────────
# ⛔⛔ **射程：這三道數量下限（總／per-file／ratchet）擋的是「引用被靜默漏檢」，
#      不是「內容完整性」。** 2026-09-08 第三輪稽核實測：
#        * `§-1.5` 整節（**全檔 49.6%**、客戶三份逐字頒布原文）只含 28 筆引用
#          ⇒ 剪掉它，三道下限**一個都不會動**；
#        * 以現行下限，最大可靜默搬走的**連續**區塊是 `CLAUDE.md` 的 **56.9%**（實測）。
#      ⇒ **內容完整性由 `test_declared_sections_all_present` 與
#          `test_declared_registry_ids_all_present` 負責，不是由這三道。**
#      ⛔ 本檔任何地方都不得再暗示數量下限保護內容完整性。
# 總下限擋的是「**整個檔**沒被讀到」。它擋**不住**「**一半內容**被搬到第三個檔、
# 而那個檔忘了登記」—— 2026-09-08 實測該情境：守衛看得到 315、看不到 111（26.1%），
# `315 >= 300` ⇒ **全綠**。故補這一道：**每個已登記的檔，各自不得縮到下限以下。**
#
# ⚠️ **這些數字會漂移，本檔刻意不寫「現在是幾筆」**（`CLAUDE.md` 引的姊妹 repo
#    §8.2.A.0 規則 4：會漂移的量測值一律標日期或不寫）。上一版在註解裡寫了
#    「`EXCEPTIONS.md` 242」，**在同一個 PR 內就過期了**（變成 251）——
#    一個會自己說謊的註解，比沒有註解糟。**要現值請跑下面那條指令。**
#
#    現場量測：
#        python3 -c "import importlib.util as u,pathlib; \
#          s=u.spec_from_file_location('g','tests/test_constitution_file_refs.py'); \
#          g=u.module_from_spec(s); s.loader.exec_module(g); \
#          print({f: sum(1 for r in g.parse_references(pathlib.Path(f).read_text('utf-8')) \
#                        if not r.struck and r.is_tier1) for f in g._MIN_LIVE_TIER1_PER_FILE})"
#
# 下限的選法（2026-09-08 訂）：取當時實測值向下留約 20~25% 餘裕。餘裕**不能是 0**——
# 本 repo 鼓勵把過期引用加刪除線退役，那會讓活的引用變少；貼著現值會把「正確退役」
# 變成紅燈，逼人不敢退役。實測 `CLAUDE.md` 最近 25 個 commit 只有 1 步是負的、幅度 −6。
_MIN_LIVE_TIER1_PER_FILE: dict[str, int] = {
    "CLAUDE.md": 150,
    "EXCEPTIONS.md": 200,
}

# ⚠️ **餘裕的 ratchet（雙向）** —— 這一條解的是稽核點名的「**餘裕隨檔案長大而增加**」：
# 下限是絕對值，檔案越長，「可以靜默搬走多少」就越多，而**沒有人會回頭調它**。
# 故加一個上界：**實測值不得超過下限的 `_PER_FILE_FLOOR_MAX_SLACK` 倍**。
# 檔案長大到超出這個帶寬時，CI 會**要求你把下限往上調**（而不是安靜地讓保護力衰減）。
# ⚠️ 這是**刻意的維護負擔**，不是 bug：本 repo 已有同型前例（`test_every_exemption_is_still_needed`
# 逼你清掉沒用的豁免；`test_wf05_settings_skeleton` 的「放寬條文已經沒有用途，請把它降回來」
# 也自稱雙向 ratchet）。**把衰減變成一次看得見的紅燈，是這條的全部意義。**
_PER_FILE_FLOOR_MAX_SLACK = 1.6


# ══════════════════════════════════════════════════════════════════════════
# ⛔⛔ 讀這一段再改下面任何一行 —— 這道守衛的歷史
# ══════════════════════════════════════════════════════════════════════════
# **這道守衛已經被三組獨立稽核分別繞過 5 次、1 次、7 次，每一次都是在前一組
#   「全部轉紅」之後。**
# ⛔ **任何人看到它全綠，都不得據此推論「憲法不會被靜默搬走」。**
#
# 每一輪都是同一個劇本：作者想得到的突變全部轉紅 → 換一組人來 → 當場繞過。
# 第三輪最貴的一課是：**前兩輪都在調門檻，而門檻量的東西從一開始就是錯的**——
# 下限數的是「**引用筆數**」，我們真正怕的是「**內容被搬走**」，兩者不成比例：
#   實測（2026-09-08）：`CLAUDE.md` 的 `§-1.5` 整節 ＝ **141,198 bytes ＝ 全檔 49.6%**
#   （裡面是客戶三份逐字頒布原文 v1/v2/v3、兩則裁決、七個判定），
#   但它只含 **28 筆**活的 Tier-1 引用 ⇒ 整節剪進一個沒登記的檔 → **20 passed 全綠**。
#   **半部憲法可以無聲消失，而所有數量下限都不會動。**
#
# → 故本檔的**主防線不是數量，是內容清單**（`test_declared_sections_all_present`）。
#   數量下限**保留**，但它們擋的是「**引用被靜默漏檢**」，**不是**「內容完整性」。
# ══════════════════════════════════════════════════════════════════════════

# ── 第三道：檔案集合綁定（**檔頭標記**，不依賴任何散文措辭）───────────────
# **帶標記的 `.md/.markdown`（全 repo、大小寫不敏感）與 `CONSTITUTION_FILES`
#   兩份名單必須完全相等。**
#
# ⚠️ 這一道 2026-09-08 被換過兩次，兩次的原因都寫在這裡，免得有人改回去：
#   **第一版**靠「搬至 `X.md`」這個**散文句式**建白名單 → 第二輪稽核五組繞過全綠
#   （`搬至 X 與 Y` 非貪婪只抓第一個／`移至` 換動詞／不寫指標／`現住址`（守衛自己的詞）／
#     移進 `docs/` 讓 per-file key 對不上）。**根因是「靠人寫的散文」。**
#   **第二版**（標記 ＋ `Path.glob("*.md")`）→ 第三輪稽核再兩組：
#     **(A1)** `Path.glob` **大小寫敏感** ⇒ 帶標記的 `GOVERNANCE.MD` 完全隱形（實測全綠）。
#             ⚠️ `.MD` 在 macOS／Windows 上**會自然發生，不必有人故意**。
#     **(A2)** 標記用**子字串**比對 ⇒ 任何根目錄 `.md` 只要**提到**這個標記就誤紅（實測）。
#   → 現行版：**全 repo 掃、副檔名與大小寫都不敏感、標記必須是檔頭的獨立一行**。
_CONSTITUTION_MARKER = "<!-- CONSTITUTION-FILE -->"

# 副檔名一律小寫比對；`.markdown` 一併涵蓋。⚠️ 不要改回單一 `"*.md"` glob（見 A1）。
_MARKDOWN_SUFFIXES = {".md", ".markdown"}
# 標記必須出現在檔頭前 N 行、且是**獨立一行**（見 A2：子字串比對會誤殺說明文件）。
_MARKER_HEAD_LINES = 20
_SCAN_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__",
                   ".pytest_cache", "site-packages", ".mypy_cache", ".ruff_cache"}


def _iter_markdown_files():
    """全 repo 的 markdown 檔（副檔名大小寫不敏感）。"""
    for p in REPO_ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(part in _SCAN_SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in _MARKDOWN_SUFFIXES:
            yield p


def _has_marker(path: Path) -> bool:
    """標記必須是**檔頭前 N 行內的獨立一行** —— 不是「檔案裡有提到這串字」。"""
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= _MARKER_HEAD_LINES:
                    return False
                if line.strip() == _CONSTITUTION_MARKER:
                    return True
    except OSError:
        return False
    return False


def _marked_files() -> set[str]:
    return {str(p.relative_to(REPO_ROOT)) for p in _iter_markdown_files() if _has_marker(p)}


def _registered_files() -> set[str]:
    return {str(p.relative_to(REPO_ROOT)) for p in CONSTITUTION_FILES}


def test_constitution_file_set_is_bidirectionally_bound():
    """**雙向綁定**：帶標記的檔 ＝ 已登記的檔。少一個或多一個都紅。"""
    marked, registered = _marked_files(), _registered_files()
    assert marked, (
        f"全 repo 找不到任何檔頭帶 `{_CONSTITUTION_MARKER}` 的 markdown。\n"
        "**這幾乎一定是標記被刪掉，而不是憲法真的不存在** —— 本條會因此安靜地停止工作。")
    only_marked, only_reg = sorted(marked - registered), sorted(registered - marked)
    assert not only_marked and not only_reg, (
        "憲法檔名單對不上：\n"
        + (f"  **帶標記但沒登記**：{only_marked}\n"
           "    ⇒ 這些檔完全沒有被檢查。修法：加進 `CONSTITUTION_FILES`，"
           "並在 `_MIN_LIVE_TIER1_PER_FILE` 替它設下限。\n" if only_marked else "")
        + (f"  **登記了但檔頭沒有標記**：{only_reg}\n"
           "    ⇒ 檔案被改名／搬走／標記被刪，或標記不在檔頭前"
           f"{_MARKER_HEAD_LINES} 行、不是獨立一行。\n" if only_reg else ""))


def test_per_file_floor_keys_match_registered_files_exactly():
    """`_MIN_LIVE_TIER1_PER_FILE` 的 key **必須恰好等於** `CONSTITUTION_FILES`。

    ⚠️ 擋一個實測過的靜默失效：把 `EXCEPTIONS.md` 移到 `docs/`、**兩支守衛路徑都同步改對**
    → key 變成 `docs/EXCEPTIONS.md`、字典裡是 `EXCEPTIONS.md` ⇒ 舊寫法 `if f in dict`
    讓它**直接沒有下限**，全綠、112 筆不再受保護。
    """
    keys, registered = set(_MIN_LIVE_TIER1_PER_FILE), _registered_files()
    assert keys == registered, (
        "`_MIN_LIVE_TIER1_PER_FILE` 的 key 與 `CONSTITUTION_FILES` 不一致：\n"
        f"  有登記但沒下限：{sorted(registered - keys)}\n"
        f"  有下限但沒登記：{sorted(keys - registered)}\n"
        "「不在字典裡就等於沒有下限」是一個會安靜生效的漏洞。")


# ══════════════════════════════════════════════════════════════════════════
# ⭐ 主防線：內容清單 —— 章節名不見了就紅，不看任何量測值
# ══════════════════════════════════════════════════════════════════════════
# **為什麼這是主防線、而數量下限不是**（2026-09-08 第三輪稽核逼出來的結論）：
#   * 我們真正怕的是「**某一節整個消失**」。**章節是內容形狀的，不會因為檔案長大而失效。**
#   * 數量下限量的是引用筆數，而引用密度與內容量**不成比例** ——
#     `§-1.5` 佔全檔 49.6% 卻只有 28 筆引用，剪掉它所有下限都不動。
#   * ⛔ **刻意不用位元組數當主防線**：那同樣是量測值，同樣要有人回頭調，
#     同樣會在檔案長大之後變鬆 —— 那正是前兩輪失敗的原因。
#
# **兩個方向都要紅**（同標記綁定的精神：比對兩份名單，不是比對一個門檻）：
#   * 清單裡有、憲法裡找不到 → 有人把那一節搬走／刪掉了；
#   * 憲法裡有、清單裡沒有   → 新增了頂層章節，**請有意識地把它加進清單**。
#
# ⚠️ **這一條擋得到什麼、擋不到什麼，講清楚**：
#   擋得到「**整節連標題一起消失**」（B1 那種：`§-1.5` 整段剪走 → 標題沒了 → 紅）。
#   **擋不到「留下標題、把內文掏空」** —— 那需要另一種檢查，本檔沒有做。
#   ⛔ 不得從本條全綠推論出「每一節的內容都還在」。
_DECLARED_SECTIONS: tuple[str, ...] = (
    # `CLAUDE.md` 頂層（`^## §…`）
    "§-2", "§-1.5", "§-1", "§0", "§1", "§2", "§3", "§4", "§5", "§6", "§7", "§8",
    # `§-1.5` 底下承載**客戶逐字頒布原文與總管裁決**的小節 —— 這幾節是 B1 那次
    # 被整段剪走的東西，單看頂層 `§-1.5` 在不在並不夠。
    "§-1.5.0", "§-1.5.1", "§-1.5.1a", "§-1.5.1b", "§-1.5.1c",
    "§-1.5.2", "§-1.5.3", "§-1.5.4", "§-1.5.5",
    # 2026-09-08 搬到 `EXCEPTIONS.md` 的兩張表（`CLAUDE.md` 原位置留有同名指標段，
    # 兩邊任一個在即可 —— 這正是「留指標」這個慣例該有的效果）。
    "8.2.A", "8.3.P",
)

# ⚠️ 刻意用字串串接而不是 `.format()` —— regex 裡的 `{1,6}` 會被 `.format()` 當成欄位名
#    （初稿就是這樣炸的：`KeyError: '1,6'`）。
_SECTION_ANCHOR_PREFIX = r"^(?:#{1,6}[ \t]*|\*\*)"   # markdown 標題，或本檔慣用的粗體行
# 邊界：`§-2.` 這種「ID 後面接句點再接空白」要命中；`§-1` 不得命中 `§-1.5`、
# `§-1.5.1` 不得命中 `§-1.5.1a`。⇒ 不可被字母數字/連字號接續，且不可被「點＋字母數字」接續。
_SECTION_ANCHOR_SUFFIX = r"(?![0-9A-Za-z\-])(?!\.[0-9A-Za-z])"


def _sections_present() -> set[str]:
    import re as _re
    texts = [txt for _f, txt in _read_constitution_files()]
    found = set()
    for sec in _DECLARED_SECTIONS:
        pat = _re.compile(_SECTION_ANCHOR_PREFIX + _re.escape(sec) + _SECTION_ANCHOR_SUFFIX, _re.M)
        if any(pat.search(txt) for txt in texts):
            found.add(sec)
    return found


def test_declared_sections_all_present():
    """⭐ **主防線**：清單裡的每一個章節，都必須在某一個憲法檔裡找得到標題。

    **這一條是 2026-09-08 第三輪稽核逼出來的。** 在它之前，把 `§-1.5`（全檔 **49.6%**，
    客戶三份逐字頒布原文 ＋ 兩則裁決 ＋ 七個判定）整段剪進一個沒標記、沒登記的
    `GOVERNANCE.md`，**所有守衛 20 passed 全綠** —— 因為那一整節只含 28 筆引用，
    數量下限一個都沒被觸發。
    """
    missing = [s for s in _DECLARED_SECTIONS if s not in _sections_present()]
    assert not missing, (
        f"下列憲法章節在**所有**憲法檔裡都找不到標題：{missing}\n"
        "⇒ 最可能的原因：**那幾節被搬到一個沒有登記的檔，或被刪掉了。**\n"
        "**數量下限擋不住這個** —— 引用密度與內容量不成比例"
        "（實測：`§-1.5` 佔全檔 49.6%，卻只有 28 筆引用）。\n"
        "修法：把它搬回來，或（若是**有意識**的拆檔）把新檔加標記 ＋ 登記進 "
        "`CONSTITUTION_FILES`，章節標題就會重新被找到。\n"
        "⛔ 不要為了讓測試變綠而把章節名從 `_DECLARED_SECTIONS` 刪掉。")


def test_declared_section_list_has_no_unlisted_top_level_sections():
    """反向：憲法裡出現了清單沒有的**頂層**章節 → 紅，逼人有意識地更新清單。

    只有兩份名單互相綁死，這條規則才不會隨時間鬆掉 —— 同標記綁定的道理。
    """
    import re as _re
    seen = set()
    for _f, txt in _read_constitution_files():
        for m in _re.finditer(r"^##\s+(§-?[0-9][0-9A-Za-z.\-]*)\.", txt, _re.M):
            seen.add(m.group(1))
    unlisted = sorted(seen - set(_DECLARED_SECTIONS))
    assert not unlisted, (
        f"憲法裡有頂層章節不在 `_DECLARED_SECTIONS` 清單裡：{unlisted}\n"
        "新增頂層章節時請**同時**把它加進清單 —— 否則它從一開始就不受主防線保護。")


# ── 主防線之二：登記簿的**每一列**（`EX-*` / `P-*` / `GAP-*` ID）────────────
# **為什麼章節清單還不夠**（2026-09-08 第三輪稽核 B3）：
#   章節清單擋得住「整節連標題一起消失」，**擋不住「從一節的尾巴剪掉一半的列」** ——
#   實測：把 `8.3.P` 尾端 **53 筆引用 / 38,634 bytes** 剪進未登記的 `PENDING.md`
#   （標題還在、per-file 259→206 仍高於下限 200）⇒ **22 passed 全綠**。
#
# → 兩張表的**內容單位就是那些 ID**，而它們是機器可讀的（`test_retired_exception_ids.py`
#   早就在解析同一批東西）。**ID 消失 ＝ 那一列被搬走或刪掉，直接紅。**
#   這仍然是「**比對兩份名單**」，不是門檻 —— 不會因為檔案長大而失效。
#
# ⚠️ **方向刻意只有一個（不得消失，可以新增）**，理由據實寫明：
#   新增 `P-*` 列是**常態**（本 PR 自己就加了 3 列），要求每加一列就改測試會製造
#   高頻 churn，而「多一個 ID」**不會讓任何內容消失** —— 它不是我們怕的那件事。
#   ⇒ 這裡的不對稱是**有理由的**，與章節清單的雙向綁定不同，不要「順手對齊」。
_DECLARED_REGISTRY_IDS: frozenset[str] = frozenset({
    # `8.2.A` 例外表 —— 生效中的
    "EX-CACHE-1", "EX-AI-1", "EX-CRUD-1", "EX-PASSTHRU-1",
    "EX-UICACHE-1", "EX-CISCRIPT-1",
    # 同表**已退役**、依本 repo 慣例加刪除線保留在表上的兩列。**這裡列它們不是拿它們當授權**，
    # 是要確保那兩列**不會被人順手刪掉** —— 退役紀錄消失，就沒有人知道當初為什麼豁免過。
    # （⚠️ 本行的「已退役」三個字是 `test_retired_exception_ids.py` 要求的退役標記；
    #   初稿沒寫，被那支守衛當場抓到 —— 一個守衛抓到另一個守衛的作者，照實記在這裡。）
    "EX-POLICY-1", "EX-L1ORCH-1",  # ← 兩者皆**已退役**（此處只保護該列不被刪，不是引用其授權）
    # `8.3.P` 待判定表
    "P-NAVCACHE-1", "P-NDCCACHE-1", "P-UIHTTP-1", "P-UIGSPREAD-1", "P-UISUBPROC-1",
    "P-YFDUPE-1", "P-BENCHTZ-1", "P-WHERECONTENT-1", "P-GREYSCENARIO-1",
    "P-SINKGRAIN-1", "P-RETRYKIND-1", "P-WSTOREWRITE-1", "P-AIKEYCI-1",
    "P-CONCURGUARD-1", "P-GRIDPRESENCE-1", "P-CALLSTATIC-1",
    "GAP-SEARCH-CACHE-1", "P-AIFLAG-1", "P-POOLCACHE-1", "P-LEDGERNAV-1",
    "P-PASSTHRUSCOPE-1",
    # 2026-09-08 拆檔輪新增
    "P-PHANTOMSEC-1", "P-FROZENTABREF-1", "P-SPLITSLACK-1",
})

_REGISTRY_ID_RE = __import__("re").compile(r"\b(?:EX|P|GAP)-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")


def _registry_ids_present() -> set[str]:
    """憲法各檔的**表格第一格**裡出現的登記簿 ID（與 `test_retired_exception_ids.py` 同一條路徑）。"""
    out: set[str] = set()
    for _f, txt in _read_constitution_files():
        for line in txt.split("\n"):
            s = line.lstrip()
            if not s.startswith("|"):
                continue
            out |= set(_REGISTRY_ID_RE.findall(s[1:].split("|", 1)[0]))
    return out


def test_declared_registry_ids_all_present():
    """⭐ **主防線之二**：登記簿的每一列都不得靜默消失。

    **這一條是 2026-09-08 第三輪稽核 B3 逼出來的。** 在它之前，把 `8.3.P` 尾端
    53 筆引用 / 38,634 bytes 剪進未登記的檔（**逐字照著約定的措辭寫指標**）
    → **22 passed 全綠**：章節標題還在、per-file 下限還沒破。
    """
    missing = sorted(_DECLARED_REGISTRY_IDS - _registry_ids_present())
    assert not missing, (
        f"下列登記簿 ID 在**所有**憲法檔的表格裡都找不到了：{missing}\n"
        "⇒ 最可能的原因：**那幾列被搬到一個沒有登記的檔，或被刪掉了。**\n"
        "數量下限與章節清單都擋不住這個（實測：剪掉 53 筆引用、標題還在 ⇒ 全綠）。\n"
        "修法：搬回來，或（若是**有意識**的拆檔）把新檔加標記 ＋ 登記進 `CONSTITUTION_FILES`。\n"
        "⛔ 退役一列請照本 repo 慣例**加刪除線保留在表上**，不要把 ID 整個刪掉 ——"
        "本條讀的是表格第一格，劃線的列**照樣算存在**。")


def test_guard_still_sees_the_whole_constitution():
    """**反空轉**：確認本守衛真的還在看整部憲法，而不是安靜地只看了一半。

    這一條擋的不是「憲法寫錯」，是「**守衛自己壞了但沒人發現**」。
    2026-09-08 拆檔實測：只讀 `CLAUDE.md` 的話 `hard` 仍是 0、測試全綠，
    但覆蓋率掉掉 55.4%。**沒有這一條，那次退化不會有任何訊號。**
    """
    per_file: dict[str, int] = {}
    for fname, text in _read_constitution_files():
        per_file[fname] = sum(
            1 for r in parse_references(text) if not r.struck and r.is_tier1
        )
    total = sum(per_file.values())

    empty = sorted(f for f, n in per_file.items() if n == 0)
    assert not empty, (
        f"下列憲法檔**一筆活的 Tier-1 引用都沒有**：{empty}\n"
        "這幾乎一定是「檔案被讀到了，但內容不是預期的那份」——"
        "例如路徑指到一個空殼、或內容被搬走而 `CONSTITUTION_FILES` 沒跟著改。\n"
        f"各檔實測：{per_file}")

    # ⚠️ 這裡**不寫** `if f in _MIN_LIVE_TIER1_PER_FILE` —— 「不在字典裡就等於沒有下限」
    #    正是 2026-09-08 實測過的靜默漏洞（把檔案移進 `docs/` 之後 key 對不上、全綠）。
    #    key 一致性由 `test_per_file_floor_keys_match_registered_files_exactly` 保證，
    #    此處直接索引：真的少了 key 就 `KeyError` 炸掉，**不會安靜跳過**。
    shrunk = sorted(
        (f, n, _MIN_LIVE_TIER1_PER_FILE[f])
        for f, n in per_file.items()
        if n < _MIN_LIVE_TIER1_PER_FILE[f]
    )
    assert not shrunk, (
        "下列憲法檔的活 Tier-1 引用掉到它自己的下限以下："
        + "、".join(f"{f} {n} < {lo}" for f, n, lo in shrunk) + "\n"
        "最可能的原因：**這個檔的一部分被搬到別的檔了，而那個檔沒有被登記** ——"
        "總下限擋不住這種『搬走一半』（2026-09-08 實測：看得到 315、看不到 111，仍然全綠）。\n"
        "先確認 `CONSTITUTION_FILES` 列全了；確認之後若真的是有意識的瘦身，"
        "再現場重新量測並下修這個檔的下限，**同時註明量測日與理由**。")

    assert total >= _MIN_LIVE_TIER1_REFS, (
        f"本守衛目前只看得到 {total} 筆活的 Tier-1 引用，低於下限 "
        f"{_MIN_LIVE_TIER1_REFS}（各檔：{per_file}）。\n"
        "最可能的原因：**憲法內容被搬走了，但 `CONSTITUTION_FILES` 沒跟著更新** ——"
        "那會讓本守衛安靜地少檢查一整批引用，而其他測試**全部照樣綠燈**。\n"
        "先確認 `CONSTITUTION_FILES` 列全了；確認之後若憲法是真的變小了，"
        "再**有意識地**下修 `_MIN_LIVE_TIER1_REFS` 並就地寫明新的量測與理由。")

    # ── 餘裕 ratchet：檔案長大時，逼下限跟著長 ──────────────────────────
    too_slack = sorted(
        (f, n, _MIN_LIVE_TIER1_PER_FILE[f])
        for f, n in per_file.items()
        if n > _MIN_LIVE_TIER1_PER_FILE[f] * _PER_FILE_FLOOR_MAX_SLACK
    )
    assert not too_slack, (
        "下列憲法檔已經長到遠高於它自己的下限，**保護力正在安靜地衰減**："
        + "、".join(f"{f} 實測 {n} > 下限 {lo} × {_PER_FILE_FLOOR_MAX_SLACK}" for f, n, lo in too_slack)
        + "\n下限是絕對值：檔案越大，『可以被靜默搬走而不觸發紅燈』的量就越多。\n"
        "**請把該檔的下限往上調**，並就地註明量測日與理由。\n"
        "⚠️ **新下限必須「只升不降」：取 `max(現行下限, 現值×0.8)`。**\n"
        "   ⛔ **不要**照舊版寫的「取現值的 75~80%」直接算 —— 那句話 2026-09-08 被實測推翻：\n"
        "   `CLAUDE.md` 現值 185、現行下限 150，而 185×0.75 ＝ 138 **比現行下限還低**，\n"
        "   照著做等於**放寬**。實測後果：最大可靜默搬走的連續區塊由 **56.9% 變成 73.8%**。\n"
        "   **一條寫在守衛裡的補救建議，自己是個放寬指令 —— 這是本檔踩過最貴的一次。**\n"
        "⛔ 不要改大 `_PER_FILE_FLOOR_MAX_SLACK` 來閉嘴 —— 那正好是這條要防的動作。")


def test_every_exemption_is_still_needed():
    """豁免清單不得腐爛：列在 EXEMPTIONS 卻已經用不到的，必須移除。

    沒有這條，豁免清單會變成一個只進不出的垃圾桶 —— 而一份會說謊的豁免清單，
    正是 §8.2.A.0 規則 2/3 點名的失效模式（人工維護的窮舉清單必然過期）。
    """
    used: set[str] = set()
    for _fname, text in _read_constitution_files():
        _, _, u = audit(text, REPO_ROOT)
        used |= u
    stale = sorted(set(EXEMPTIONS) - used)
    assert not stale, (
        "下列豁免已經沒有作用（CLAUDE.md 內已經沒有這個活的引用了），請從 EXEMPTIONS 移除：\n  "
        + "\n  ".join(stale)
    )


# --------------------------------------------------------------------------
# 合成樣本：刪除線判定的兩個方向
# --------------------------------------------------------------------------
# 這兩條是本檔的核心行為守衛。**兩個方向都要測**：
#   * 只測「會紅」→ 守衛可能過緊，會逼人刪歷史紀錄（不可逆傷害）。
#   * 只測「不會紅」→ 守衛可能全程空轉，等於沒有守衛。
_GHOST = "services/this_file_does_not_exist_zzz.py"


def test_struck_through_reference_to_missing_file_does_not_fire(tmp_path):
    """劃掉的引用即使指向不存在的檔案，也**不得**紅燈 —— 那是已正確退役的紀錄。"""
    text = f"| ~~舊欄位~~ | ~~`{_GHOST}:33-38`~~ | **v19.251 退役** |"
    hard, _, _ = audit(text, tmp_path)
    assert hard == [], f"劃掉的引用被誤判為違規：{[(r.cited, w) for r, w in hard]}"


def test_live_reference_to_missing_file_does_fire(tmp_path):
    """沒劃掉的引用指向不存在的檔案，**必須**紅燈。"""
    text = f"見 `{_GHOST}` 的實作。"
    hard, _, _ = audit(text, tmp_path)
    assert [r.cited for r, _ in hard] == [_GHOST]


def test_same_line_mixed_struck_and_live_are_separated(tmp_path):
    """同一行同時有劃掉與沒劃掉的引用時，只有沒劃掉的那個算數。

    這是 `CLAUDE.md` §2.1 表格最常見的形態（一格劃掉、隔壁格還活著），
    也是「整行含 `~~` 就跳過」這種偷懶作法會漏掉真違規的地方。
    """
    text = f"| ~~`{_GHOST}`~~ 已退役 | 現行見 `services/still_missing_zzz.py` |"
    hard, _, _ = audit(text, tmp_path)
    assert [r.cited for r, _ in hard] == ["services/still_missing_zzz.py"]


def test_multiline_strikethrough_is_honoured(tmp_path):
    """刪除線可以跨行（`CLAUDE.md` §-1.5.5 盲點 1 就是這種寫法）。"""
    text = f"1. 本次授權僅此一檔。~~見 `{_GHOST}`\n   （詳見末列）；~~ 其餘未掃。"
    hard, _, _ = audit(text, tmp_path)
    assert hard == []


def test_unpaired_strikethrough_does_not_swallow_later_references(tmp_path):
    """單邊 `~~` 不得把後面的內容整片吃掉變成「不檢查」。

    若採全域貪婪配對，一個手滑的單邊 `~~` 會讓它之後所有引用集體翻面 ——
    守衛會安靜地停止工作，而且沒有人會發現。
    """
    # 樣本刻意這樣排：單邊 `~~` → 中間一個**活的**壞引用 → 後面一組正常的 `~~…~~`。
    # 全域貪婪配對會把「單邊 `~~`」跟後面那組的**開頭** `~~` 配成一對，
    # 於是中間那個活的壞引用被整片吃掉、安靜地不再被檢查。
    text = (
        "一個手滑的 ~~ 單邊標記\n"
        + ("填充說明文字\n" * 40)
        + f"這個是活的、必須被抓到 `{_GHOST}`\n"
        + ("更多填充\n" * 40)
        + "| ~~services/already_retired_zzz.py~~ | 已退役 |"
    )
    hard, _, _ = audit(text, tmp_path)
    assert [r.cited for r, _ in hard] == [_GHOST]


def test_line_number_beyond_eof_fires(tmp_path):
    """行號超出檔尾要紅燈；界內則不紅。"""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text("a\nb\nc\n", encoding="utf-8")
    over, _, _ = audit("見 `pkg/mod.py:99`", tmp_path)
    assert len(over) == 1 and "行號超出檔尾" in over[0][1]
    ok, _, _ = audit("見 `pkg/mod.py:2`", tmp_path)
    assert ok == []


def test_globs_and_dotted_module_paths_are_not_treated_as_files(tmp_path):
    """glob 與模組路徑不是檔案引用，不得誤判。

    `ui/tab*.py`、`docs/*.md` 是樣式；`shared/schemas.TW_PMI_RACE_SOURCES` 是
    「路徑 + 符號名」，結尾不是副檔名。三者都不該進入存在性檢查。
    """
    text = "`ui/tab*.py` 與 `docs/*.md`，以及 `shared/schemas.TW_PMI_RACE_SOURCES`"
    hard, warns, _ = audit(text, tmp_path)
    assert hard == [] and warns == []


def test_bare_filename_is_warning_not_failure(tmp_path):
    """裸檔名只給 warning —— 理由見本檔 docstring（Tier 2 段）。"""
    hard, warns, _ = audit("如 tab1_macro.py 或 tab3_portfolio.py 中的私有取數", tmp_path)
    assert hard == []
    assert {r.cited for r, _ in warns} == {"tab1_macro.py", "tab3_portfolio.py"}
