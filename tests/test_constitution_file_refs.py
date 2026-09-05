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
CONSTITUTION = REPO_ROOT / "CLAUDE.md"

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
    """CLAUDE.md 內**活的**路徑引用，必須指向存在的檔案與界內的行號。"""
    text = CONSTITUTION.read_text(encoding="utf-8")
    hard, warns, _ = audit(text, REPO_ROOT)

    if warns:
        print(f"\n[warning] Tier 2 裸檔名引用 {len(warns)} 筆（不影響成敗，僅供追蹤）：")
        for ref, why in warns[:20]:
            print(f"  CLAUDE.md:{ref.md_line}  {ref.cited}  — {why}")
        if len(warns) > 20:
            print(f"  …另有 {len(warns) - 20} 筆未列出")

    if hard:
        lines = [
            "",
            f"CLAUDE.md 有 {len(hard)} 筆**活的**引用指向不存在的檔案或界外的行號。",
            "（被 `~~刪除線~~` 包住的引用不算 —— 那是已正確退役的紀錄，本守衛不碰。）",
            "",
        ]
        for ref, why in sorted(hard, key=lambda r: r[0].md_line):
            lines.append(f"  CLAUDE.md:{ref.md_line}\t{ref.cited}\n\t\t→ {why}")
        lines.append(_FIX_GUIDE)
        raise AssertionError("\n".join(lines))


def test_every_exemption_is_still_needed():
    """豁免清單不得腐爛：列在 EXEMPTIONS 卻已經用不到的，必須移除。

    沒有這條，豁免清單會變成一個只進不出的垃圾桶 —— 而一份會說謊的豁免清單，
    正是 §8.2.A.0 規則 2/3 點名的失效模式（人工維護的窮舉清單必然過期）。
    """
    text = CONSTITUTION.read_text(encoding="utf-8")
    _, _, used = audit(text, REPO_ROOT)
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
