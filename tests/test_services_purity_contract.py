"""L2 純度契約守衛 —— `services/` 是「純計算層」這句話的機器證明。

═══════════════════════════════════════════════════════════════════════════
本檔在守什麼
═══════════════════════════════════════════════════════════════════════════
CLAUDE.md §8.2 硬規則寫死了 L2 Service 的兩條：

    ❌ L2 Service 不得 import requests / httpx / beautifulsoup / feedparser
       —— 純函式,無 I/O,需資料時走 L1 repository
    ❌ 跨層上行 import:L1 不得 import L2/L3、L2 不得 import L3

而 §8.2 末句寫死：**「禁止未經登錄的潛在『軟例外』。」**

本檔把上面這幾句從「文件裡的宣稱」變成「CI 會紅的斷言」。

═══════════════════════════════════════════════════════════════════════════
為什麼要新寫一份（既有守衛哪裡不夠）—— 這段是本檔存在的全部理由
═══════════════════════════════════════════════════════════════════════════
本批之前,`services/`(78 檔)全層唯一的純度守衛是
`tests/test_daily_key_alerts_v19_349.py::test_l2_purity`:

    text = _src('services/macro/daily_key_alerts.py')
    for banned in ('import streamlit', 'import requests', 'fetch_url'):
        assert banned not in text

它有三個結構性缺陷,**每一個都已經在本 repo 的憲法裡被記載過**:

1. **只守 1/78 檔。** 另外 77 檔完全沒有守衛。
2. **字面黑名單。** 字表只有 3 個詞。**黑名單永遠追不上新的 I/O 形態** ——
   `CLAUDE.md §-1.5.1c 判定 2` 的「方法缺陷」表逐字記載本 repo 因此漏抓兩次:
   第一次只 grep `import requests`,漏掉走 `infra.proxy.fetch_url` 的;
   第二次補了 `fetch_url`/`urlopen`/`feedparser`,**還是漏掉 `yfinance`**,
   因為「那條指令在結構上就掃不到它」。
   → **本檔改用 fail-closed 白名單:不在允許清單就紅。** 新引入的套件
   **預設違規**,不必有人記得去更新黑名單。
3. **純字串比對。** 註解、docstring 裡的字會誤命中;包在 helper 裡的呼叫則漏抓。
   → **本檔用 AST**(含函式內的巢狀 import),grep 只當補漏。

⚠️ 最值得記的一筆(本檔豁免表 GSPREAD_DEBT 就地記載):
`services/nav_history_gs.py` 的檔頭逐字寫著 gspread I/O
「**不在 §8.2「L2 禁 requests/httpx/bs4/feedparser」清單**」——
也就是**它引用「規則字表的不完整」當作自己的豁免理由**,
並拿 `auto_search_store_gs` 當先例,而那一檔同樣沒有登錄。
**兩檔互為背書,兩檔都不在 §8.2.A 例外表裡。** 這正是 §8.2 末句禁止的「軟例外」。
⚠️ 2026-08-31 事實更新:`services/auto_search_store_gs.py` 已整檔刪除
(production 0 caller,客戶 2026-08-31 授權死碼清理)。**上面這段教訓不因此失效** ——
它記的是「拿規則字表的漏洞當通行證」這個手法,不是那一個檔案;
`nav_history_gs.py` 的自授豁免**原封不動還在**,只是少了可背書的對象。
缺陷 2(黑名單)與這個自授例外是**同一件事的兩面**:
規則的漏洞一旦存在,就會被當成通行證。

═══════════════════════════════════════════════════════════════════════════
豁免表 = 技術債的可見化,**不是核准**
═══════════════════════════════════════════════════════════════════════════
下方每一張 `*_DEBT` 表登記的都是 **2026-08-28 實測存在的現況違規**。

    ⛔ 登記在表裡 **不等於** 這樣寫是對的。
    ⛔ 登記在表裡 **不等於** 它已通過 §8.2.A 的例外登錄程序
       (§8.2.A 例外要「(1) 在例外表登錄、(2) 對應檔案加註解指回該表、
        (3) PR 描述附理由」—— 下列各項**都沒有走完這個程序**)。
    ✅ 表的唯一作用是:**讓債被看見、讓它不會再長大**。

**ratchet 規則(雙向 `==`)**:每張表都斷言「實測集合 == 登記集合」。
    · 新增一處違規 → 實測多一項 → 紅。
    · 修好一處卻沒把它從表裡拿掉 → 實測少一項 → 紅。
**數字只准在「有人真的修好」時往下走。**

⚠️ **本批(建立守衛)刻意不修任何一項違規。** 把 gspread 持久化服務搬出 L2
是動到 NAV 歷史鏈的架構變更,屬 §8.4 step 4 的**範圍決定**,需客戶核准,
不在本批授權內。本檔只負責把現況變成可查證的債。

═══════════════════════════════════════════════════════════════════════════
⚠️ 本守衛看不到什麼（誠實列出,不讓後人事後才發現）
═══════════════════════════════════════════════════════════════════════════
**A. 執行期改寫 module namespace —— 靜態分析的絕對盲區。**
   `services/macro_composite_score.py` / `macro_validation.py` 兩個 shim 用
   `for _name in dir(_mod): globals()[_name] = getattr(_mod, _name)`
   把另一個模組的符號整包注入自己的 namespace。
   **任何靜態守衛(包含本檔)對這兩檔注入進來的東西都是瞎的。**
   ⚠️ 2026-08-31 更正:原文寫「**三個** shim」,第三個是
   `services/multi_factor_optimization.py` —— 該檔已於本日整檔刪除
   (auto_search 封閉死簇,production 0 caller;客戶 2026-08-31 授權死碼清理)。
   **盲區本身沒有變小,只是少了一個成員**;這種寫法一旦再出現,照樣要登記。
   → 故本檔另立 `test_no_runtime_namespace_injection`,把「這種寫法本身」當違規登記。
   它守的不是內容,是**盲區的邊界**。

**B. 間接 I/O —— 本檔只看一層。**
   `services/` 呼叫 `repositories.*` / `infra.*` / `fund_fetcher` 時,
   本檔**不追進去**看那邊有沒有發 HTTP。§8.2 明文允許 L2→L1 取數,
   所以「有沒有 I/O」在那個方向上本來就不是本檔的判準。
   **已知的例外是 `infra.llm`**(→ `requests.post` 打三家 LLM API),
   它已登記在 `IMPORT_DEBT`;但**其餘 `infra.*` / `repositories.*` 的間接往返本檔不追**。

**C. gspread 的 `.update()` 寫入呼叫。**
   `ws.update(...)` 是真的遠端寫入,但 `update` 與 `dict.update` / `pandas` 撞名
   (實測 `result.update` / `out.update` / `sources.update` 等 6 處純屬字典操作)。
   收進字表會製造大量假陽性 → 本檔的 gspread 字表**刻意不含 `update`**。
   實測結果:靠其餘辨識度高的方法名,**3 個 gspread 檔一個都沒漏**;
   但若日後有檔案**只用 `.update()`、不用任何其他 gspread 方法**,本檔會漏掉它。

**D. 動態 import。** `importlib.import_module(name)` / `__import__(var)` /
   `getattr` 取模組 —— 名稱在執行期才決定者,本檔看不到。

**E. `open()` 的 mode 由變數決定時。** `open(p, mode)` 其中 `mode` 是變數 ——
   本檔無法靜態判斷讀寫,一律歸「讀」以免假陽性(寫入會漏)。

**F. 本檔只掃 `services/**` 加上「反向規則」所需的 `repositories/**` 與
   根目錄 `fund_fetcher.py`。** 其餘各層不在本檔射程內。

**G. 本檔由單組產出,未經第二組獨立複驗**(§-2 規則 6)。
   下方所有「實測 N 處」的數字都是本組 2026-08-28 量測,
   **「services/ 沒有第 N+1 處」這句話本組沒有查證、也不宣稱。**

═══════════════════════════════════════════════════════════════════════════
本檔建立時的突變證明（2026-08-28，21/21 通過）
═══════════════════════════════════════════════════════════════════════════
「守衛有沒有真的守到東西」不能用宣稱的,要用**拔掉修復必須轉紅**來證。
建檔當下逐條注入違規,實測每一條都轉紅（注入後即還原,production code 零改動）:

  A1  services/ 內 module 層 `import requests`                  → 紅
  A2  **把 import 藏進 helper 函式** + `requests.get(...)`       → 紅  ← 擊敗字串黑名單的手法
  A3  `import yfinance`                                          → 紅  ← 本 repo 第二次教訓漏的就是它
  A4  `import gspread`                                           → 紅
  A5  `import subprocess`                                        → 紅
  A6  `import aiohttp`（從未出現在任何黑名單裡）                  → 紅  ← 白名單設計的價值在此
  A7  `client.open_by_key(sid).sheet1.get_all_values()`          → 紅  ← **不含任何禁用字**
  A8  `Path(...).write_text(...)`                                → 紅
  A9  `Path(...).unlink()`                                       → 紅
  A10 `pd.read_parquet(path)`                                    → 紅
  A11 `globals()["x"] = 1`                                       → 紅
  A12 `from ui.helpers import ...`（L2→L3 上行）                  → 紅
  A13 repositories/ 內 `from services.foo import bar`（L1→L2）    → 紅
  A14 `import streamlit as _st_mod` + `_st_mod.error(...)`        → 紅  ← **別名不敏感**
  A15 `import streamlit` + `streamlit.session_state[...]`        → 紅

**反方向同樣要驗（只證會紅、不證不會誤紅,等於沒驗）**:
  B1  純運算 + 允許的 import（numpy/pandas/shared/repositories）  → 綠
  B2  `df.to_csv(index=False)`（無 path,回傳字串）                → 綠  ← 記憶體序列化不是 I/O
      `pd.read_csv(io.BytesIO(raw))`（緩衝）                      → 綠
      `dict.update(...)` / `str.replace(...)`                     → 綠  ← 與 gspread/檔案系統撞名者不誤判
      （B2 對 5 條規則各跑一次,全綠）

**錨點自身也驗過**:把掃描 glob 改成掃不到任何檔,3 個 `*_is_not_vacuous`
連同 5 條規則共 8 個測試當場轉紅 —— 證明規則不會在「掃不到東西」時靜默變綠。

⚠️ 日後修改本檔的掃描邏輯後,**請重跑一次上述突變**;
只看到 22 個測試綠燈**不構成**「守衛still有效」的證據（那正是本檔要取代的那種宣稱）。

═══════════════════════════════════════════════════════════════════════════
與既有守衛的關係
═══════════════════════════════════════════════════════════════════════════
`tests/test_daily_key_alerts_v19_349.py::test_l2_purity` **原封不動保留**。
它守得窄,但**沒有錯** —— 它對 `daily_key_alerts.py` 的要求比本檔嚴
(本檔允許 `pathlib`,它連字面 `fetch_url` 都不准)。
**兩條並存、衝突處取嚴**,不互相取代。
"""

from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"

# ═══════════════════════════════════════════════════════════════════════════
# 掃描骨架
# ═══════════════════════════════════════════════════════════════════════════


def _services_files() -> list[pathlib.Path]:
    """services/ 全層 .py（排序穩定；不含 __pycache__）。

    ⚠️ 刻意**不做任何路徑名稱條件判斷**（不看 worktree 名、不看 clone 目錄名）。
    本 repo 已實證:帶條件的 skip 清單會在某些 clone 路徑下失明並產生假綠。
    """
    return sorted(
        p
        for p in SERVICES.rglob("*.py")
        if "__pycache__" not in p.parts
    )


def _rel(p: pathlib.Path) -> str:
    return p.relative_to(ROOT).as_posix()


def _parse(p: pathlib.Path) -> ast.Module:
    return ast.parse(p.read_text(encoding="utf-8"), filename=str(p))


def _context_map(tree: ast.Module) -> dict[int, str]:
    """node id -> 最近的封閉函式名（`foo()`）或 `<module>`。

    ⚠️ 用符號名而不是行號 —— 行號在任何一次重構後就失效,而重構不會觸發本表更新
    （CLAUDE.md §8.2.A.0 規則 1:禁止寫行號）。
    """
    out: dict[int, str] = {}

    def walk(node: ast.AST, ctx: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                inner = f"{child.name}()"
                out[id(child)] = inner
                walk(child, inner)
            elif isinstance(child, ast.ClassDef):
                out[id(child)] = ctx
                walk(child, ctx)
            else:
                out[id(child)] = ctx
                walk(child, ctx)

    walk(tree, "<module>")
    return out


def _dotted(node: ast.AST) -> str:
    """盡力還原一個運算式的點號路徑（`ws.get_all_values` / `pd.read_parquet`）。"""
    parts: list[str] = []
    cur: ast.AST = node
    while True:
        if isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        elif isinstance(cur, ast.Name):
            parts.append(cur.id)
            break
        elif isinstance(cur, ast.Call):
            cur = cur.func
        elif isinstance(cur, ast.Subscript):
            cur = cur.value
        else:
            parts.append("<expr>")
            break
    return ".".join(reversed(parts))


def _imported_modules(tree: ast.Module) -> set[tuple[str, str]]:
    """回傳 {(完整模組路徑, 封閉函式)}。

    **含函式內的巢狀 import** —— `ast.walk` 走全樹,所以把 `import requests`
    藏進 helper 函式裡並不能繞過（那正是既有字串守衛擋不住、而本檔要擋的手法）。
    **含相對 import**（`level > 0`）—— 以 `.` 前綴表示。
    """
    found: set[tuple[str, str]] = set()
    ctx = _context_map(tree)
    for node in ast.walk(tree):
        where = ctx.get(id(node), "<module>")
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add((alias.name, where))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                found.add(("." * node.level + (node.module or ""), where))
            elif node.module:
                found.add((node.module, where))
    return found


def _site(rel: str, where: str) -> str:
    return f"{rel}::{where}"


def _fmt(items) -> str:
    return "\n".join(f"    {s}" for s in sorted(items)) or "    (空)"


def _assert_ratchet(found: set[str], registered: set[str], rule: str) -> None:
    """雙向 `==` ratchet —— 綁「違規站點」,不綁「所有站點」。

    綁所有站點會讓**合規的新檔**也把測試弄紅;綁違規站點則是:
      · 多一處違規 → 紅（新債被擋下）
      · 少一處違規 → 紅（修好了要把表降下來,不准偷偷放著）
    """
    new = found - registered
    fixed = registered - found
    msg = []
    if new:
        msg.append(
            f"【{rule}】發現 {len(new)} 處**未登記**的違規。\n"
            f"這是新債,預設不予豁免 —— 請修掉它,而不是把它加進豁免表。\n"
            f"（真的必須豁免時,依 §8.2.A 走完登錄程序:例外表 + 檔內註解 + PR 理由。）\n"
            f"{_fmt(new)}"
        )
    if fixed:
        msg.append(
            f"【{rule}】豁免表裡有 {len(fixed)} 處**已不存在**的登記。\n"
            f"若是修好了 → 恭喜,請把它從本檔的豁免表刪掉（ratchet 只准往下走）。\n"
            f"若是重構搬家了 → 請更新登記鍵,不要直接刪。\n"
            f"{_fmt(fixed)}"
        )
    assert not msg, "\n\n".join(msg)


# ═══════════════════════════════════════════════════════════════════════════
# 規則 1：import 白名單（fail-closed）
# ═══════════════════════════════════════════════════════════════════════════
# ⚠️ 這是本檔的核心設計。既有守衛是**黑名單**（列出禁用的字），
#    本檔是**白名單**（列出允許的字）。差別在於:
#      黑名單 → 新的 I/O 套件預設**合法**，要有人記得去補字表（本 repo 已因此漏抓兩次）
#      白名單 → 新的套件預設**違規**，要有人主動決定放行
#    `import yfinance` / `import gspread` / `import aiohttp` 不必出現在任何清單裡,
#    只要不在下面這張表，就會紅。

ALLOWED_IMPORTS: frozenset[str] = frozenset(
    {
        # ── 純運算 / 資料結構 stdlib ────────────────────────────────
        "__future__", "abc", "bisect", "calendar", "collections", "contextlib",
        "copy", "csv", "dataclasses", "datetime", "decimal", "difflib", "enum",
        "fractions", "functools", "hashlib", "heapq", "html", "inspect",
        "itertools", "json", "logging", "math", "numbers", "operator", "random",
        "re", "statistics", "string", "textwrap", "time", "traceback", "types",
        "typing", "unicodedata", "uuid", "warnings", "weakref", "zoneinfo",
        # `io` = 記憶體緩衝（BytesIO/StringIO），不是檔案系統
        "io",
        # `sys` = stderr 稽核 log（§1 要求）
        "sys",
        # `pathlib` 本身只是路徑代數,不做 I/O；真正的讀寫由規則 2 的**呼叫**層攔
        "pathlib",
        # ── 併發（非 I/O）────────────────────────────────────────────
        "concurrent", "queue", "threading",
        # ── 第三方純運算 ───────────────────────────────────────────
        "dateutil", "holidays", "numpy", "pandas", "pandera", "pytz", "scipy",
        # ── 內部:同層與更低層（§8.2 允許 L2→L0 / L2→L1）───────────
        "shared",        # L0 常數 / TTL / 門檻
        "models",        # L0 dataclass
        "services",      # 同層
        "repositories",  # L1 —— §8.2 明文「需資料時走 L1 repository」
        "fund_fetcher",  # L1 legacy re-export shim（§8.3 F-GRAY-1）
        # ── infra（L0）採**子模組**粒度,見 _import_key ─────────────
        "infra.cache",
        "infra.config",
        "infra.gspread_retry",
    }
)


def _import_key(module: str) -> str:
    """決定拿什麼字串去比對白名單。

    `infra` 取**兩層**（`infra.llm` 會發 HTTP,`infra.cache` 不會 —— 粒度不能只到 `infra`）；
    其餘取頂層。相對 import（`.` 開頭）原樣保留,一律不在白名單內 → 預設紅。
    """
    if module.startswith("."):
        return module
    parts = module.split(".")
    if parts[0] == "infra":
        return ".".join(parts[:2])
    return parts[0]


# ── 豁免表：實測現況的 import 債（2026-08-28 量測）──────────────────
# ⚠️ 登記 ≠ 核准。見檔頭「豁免表 = 技術債的可見化」。
IMPORT_DEBT: dict[str, str] = {
    "services/ai_service.py::<module> -> infra.llm":
        "L2 經 infra.llm 間接發 HTTP（infra/llm.py 內 requests.post ×3,打三家 LLM API）。"
        "§8.2「L2 不得 I/O」的實質違反 —— 只是把 requests 藏在一層封裝後面,"
        "字面上就不會出現在任何 requests 黑名單裡。**未登錄於 §8.2.A 例外表。**",
    "services/ai_service.py::get_gemini_keys() -> os":
        "L2 直讀程序環境變數 os.environ.get('GEMINI_API_KEY' / 'GEMINI_API_KEYS' / "
        "'GEMINI_API_KEY_{i}')。純函式層不該依賴程序環境；本 repo 已有 infra.config "
        "的 get_secret/require_secret 統一入口,此處繞過了它。**未登錄於 §8.2.A 例外表。**",
}

# 量測日 2026-08-28 的錨點：services/ 檔數與 import 陳述數的下限。
# ⚠️ 沒有這個錨點,有人把掃描條件改壞（例如 glob 打錯、或全被 skip 掉）時,
#    規則會「對空氣生效」而天天綠。錨點讓那種失效變成紅燈。
_ANCHOR_SERVICES_FILES = 70          # 實測 78
_ANCHOR_IMPORT_STATEMENTS = 400      # 實測 536（含函式內巢狀 import）


def _scan_imports() -> tuple[set[str], int]:
    bad: set[str] = set()
    total = 0
    for path in _services_files():
        rel = _rel(path)
        for module, where in _imported_modules(_parse(path)):
            total += 1
            if _import_key(module) not in ALLOWED_IMPORTS:
                bad.add(f"{_site(rel, where)} -> {module}")
    return bad, total


def test_services_import_allowlist_is_not_vacuous():
    """錨點：掃描真的看到東西了（防規則對空氣生效還天天綠）。"""
    files = _services_files()
    assert len(files) >= _ANCHOR_SERVICES_FILES, (
        f"services/ 只掃到 {len(files)} 檔（量測日 2026-08-28 為 78,錨點 "
        f"{_ANCHOR_SERVICES_FILES}）。掃描條件可能壞了,規則正在對空氣生效。"
    )
    _, total = _scan_imports()
    assert total >= _ANCHOR_IMPORT_STATEMENTS, (
        f"services/ 只掃到 {total} 個 import 陳述（量測日 2026-08-28 為 536,錨點 "
        f"{_ANCHOR_IMPORT_STATEMENTS}）。AST 走訪可能壞了。"
    )


def test_services_imports_are_allowlisted():
    """§8.2「L2 不得 I/O」的 fail-closed 版本：不在白名單就紅。

    這條同時擋掉 `import requests` / `import yfinance` / `import gspread` /
    `import aiohttp` / `import subprocess` …… **不需要它們出現在任何黑名單裡**。
    也擋得住藏在函式內的巢狀 import（AST 走全樹）。
    """
    bad, _ = _scan_imports()
    _assert_ratchet(bad, set(IMPORT_DEBT), "L2 import 白名單")


# ═══════════════════════════════════════════════════════════════════════════
# 規則 2：檔案系統呼叫（讀 / 寫分開登記）
# ═══════════════════════════════════════════════════════════════════════════
# ⚠️ 只收**辨識度高**的方法名。`update` / `replace` / `rename` / `copy` / `remove`
#    與 dict / str / pandas 大量撞名（實測會產生 30+ 假陽性）,一律不收 —— 見檔頭盲區 C。

_FS_WRITE_METHODS = frozenset(
    {
        "write_text", "write_bytes", "unlink", "mkdir", "rmdir", "touch",
        "makedirs", "removedirs", "rmtree", "symlink_to", "hardlink_to",
        "chmod", "write_parquet",
        "to_parquet", "to_excel", "to_pickle", "to_feather", "to_hdf", "to_stata",
    }
)
# 這幾個沒有 path 參數時是「序列化成字串/bytes」,有 path 才是寫檔 → 需看引數
_FS_WRITE_MAYBE = frozenset({"to_csv", "to_json"})

_FS_READ_METHODS = frozenset(
    {
        "read_text", "read_bytes", "read_parquet", "read_excel", "read_pickle",
        "read_feather", "read_hdf", "read_stata", "read_orc",
        "glob", "rglob", "iterdir", "scandir", "listdir", "walk",
        "exists", "is_file", "is_dir", "lstat", "samefile",
    }
)
_FS_READ_MAYBE = frozenset({"read_csv", "read_json", "read_table", "read_fwf"})

_INMEM_BUFFERS = frozenset({"BytesIO", "StringIO"})


def _is_in_memory(call: ast.Call, callee_last: str) -> bool:
    """判斷 pandas 讀寫是「記憶體緩衝」還是「檔案系統」。

    · `df.to_csv()` 無位置引數 → 回傳字串,不碰檔案系統。
    · `pd.read_csv(io.BytesIO(b))` → 讀記憶體緩衝。
    ⚠️ 這是啟發式,見檔頭盲區 E：路徑由變數帶入時無法靜態分辨,一律歸「檔案系統」（從嚴）。
    """
    positional = [a for a in call.args if not isinstance(a, ast.Starred)]
    kw = {k.arg for k in call.keywords if k.arg}
    if not positional:
        # to_csv() / to_json() 無 path → 序列化成字串
        if callee_last in (_FS_WRITE_MAYBE | _FS_READ_MAYBE) and not (
            kw & {"path_or_buf", "path", "filepath_or_buffer"}
        ):
            return True
        return False
    first = positional[0]
    if isinstance(first, ast.Call):
        return _dotted(first.func).split(".")[-1] in _INMEM_BUFFERS
    return False


def _open_is_write(call: ast.Call) -> bool | None:
    """`open(...)` 的 mode 判讀。回傳 True=寫 / False=讀 / None=無法靜態判斷。"""
    mode: ast.AST | None = None
    if len(call.args) >= 2:
        mode = call.args[1]
    for kw in call.keywords:
        if kw.arg == "mode":
            mode = kw.value
    if mode is None:
        return False  # 預設 'r'
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return any(c in mode.value for c in "wax+")
    return None  # 變數 mode → 見盲區 E


def _scan_fs() -> tuple[set[str], set[str], int]:
    writes: set[str] = set()
    reads: set[str] = set()
    candidates = 0
    for path in _services_files():
        rel = _rel(path)
        tree = _parse(path)
        ctx = _context_map(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            dotted = _dotted(node.func)
            last = dotted.split(".")[-1]
            head = dotted.split(".")[0]
            site = _site(rel, ctx.get(id(node), "<module>"))

            if last in _FS_WRITE_METHODS:
                # shutil.copy / os.remove 等需限定 receiver,避免撞 pandas
                candidates += 1
                writes.add(site)
            elif last in _FS_WRITE_MAYBE:
                candidates += 1
                if not _is_in_memory(node, last):
                    writes.add(site)
            elif last in ("remove", "rename", "replace") and head in ("os", "shutil"):
                candidates += 1
                writes.add(site)
            elif last in _FS_READ_METHODS:
                candidates += 1
                reads.add(site)
            elif last in _FS_READ_MAYBE:
                candidates += 1
                if not _is_in_memory(node, last):
                    reads.add(site)
            elif dotted == "open" or last == "open" and head in ("io", "codecs", "gzip"):
                candidates += 1
                verdict = _open_is_write(node)
                (writes if verdict else reads).add(site)
    return writes, reads, candidates


# ── 豁免表：檔案系統**寫入/刪除**（2026-08-28 實測）─────────────────
# ⚠️ 登記 ≠ 核准。寫入與刪除是 L2 純度最嚴重的一類違反 —— 它讓「純函式」有了副作用。
FS_WRITE_DEBT: dict[str, str] = {
    "services/fund_history.py::_save()":
        "L2 寫使用者查詢歷史 JSON（_CACHE_DIR.mkdir + _HIST_FILE.write_text）。持久化職責屬 L1。",
    "services/fund_history.py::clear_history()":
        "L2 刪除歷史檔（_HIST_FILE.unlink）。不可逆副作用。",
    "services/fund_history.py::promote_to_preset()":
        "L2 寫 preset funds JSON（parent.mkdir + write_text）。持久化職責屬 L1。",
    "services/nav_history_store.py::_save_cache_series()":
        "L2 寫 NAV 本地快取（_CACHE_DIR.mkdir + _path.write_text）。"
        "快取寫入依 §8.2 應集中在 L1（EX-CACHE-1 的精神）。",
    "services/nav_history_store.py::clear_cache()":
        "L2 刪除快取檔（p.unlink）。不可逆副作用。",
}

# ── 豁免表：檔案系統**讀取**（2026-08-28 實測）───────────────────────
# ⚠️ 讀取的門檻比寫入寬（無副作用、可重現）,但仍是 I/O,仍屬 §8.2 所禁,故一併登記。
FS_READ_DEBT: dict[str, str] = {
    "services/fund_history.py::_load()":
        "L2 讀取使用者查詢歷史 JSON（_HIST_FILE.exists + read_text）。持久化讀取職責屬 L1。",
    "services/fund_history.py::_load_default_funds()":
        "L2 讀取 preset funds JSON（_PRESET_FUNDS_JSON.exists + read_text）。"
        "預設清單屬設定資料,依 §3.3 應走 shared/* SSOT 或由 caller 注入。",
    "services/fund_history.py::clear_history()":
        "L2 對歷史檔做存在性探測（_HIST_FILE.exists）。與同名的寫入登記是同一函式的兩面:"
        "先探測再刪檔,兩個動作都是純計算層不該有的檔案系統副作用。",
    "services/fund_history.py::export_preset_funds_json()":
        "L2 讀取 preset JSON 原始 bytes（exists + read_bytes）供匯出。同為檔案系統讀取。",
    "services/fund_history.py::promote_to_preset()":
        "L2 讀取 preset JSON（exists + read_text）後改寫。與同名寫入登記為同一函式的讀那一半。",
    "services/macro/validation.py::_load_vix_calibrated_thresholds()":
        "L2 讀校準門檻 JSON（path.exists + path.read_text）。"
        "門檻常數依 §3.3 應走 shared/* SSOT 或由 caller 注入,不該由 L2 自己讀檔。",
    "services/macro/validation.py::load_indicators_from_parquet()":
        "L2 直讀 parquet 快照（pd.read_parquet ×2 + exists ×2）。"
        "**這是 §8.2「L2 需資料時走 L1 repository」最直接的反例** —— L2 自己開檔取數。",
    "services/macro/weights_store.py::load_active()":
        "L2 讀取 active.json 權重覆寫檔（_ACTIVE_PATH.exists + read_text）。"
        "權重門檻依 §3.3 應由 shared/* SSOT 提供或由 caller 注入,不該由 L2 自行開檔。",
    "services/nav_history_store.py::_load_cache_series()":
        "L2 讀取 NAV 本地快取檔（_path.exists + read_text）。快取讀寫依 §8.2 應集中於 L1。",
    "services/nav_history_store.py::clear_cache()":
        "L2 列舉快取目錄（_CACHE_DIR.glob）以決定刪哪些。與同名的刪除登記為同一函式的讀那一半。",
    "services/nav_history_store.py::list_cache_codes()":
        "L2 列舉本地 NAV 快取目錄（_CACHE_DIR.glob）。目錄列舉屬檔案系統 I/O。",
}

_ANCHOR_FS_CANDIDATES = 25  # 實測 42；floor 取約一半,只在掃描結構性壞掉時才跳


def test_fs_scan_is_not_vacuous():
    """錨點：檔案系統掃描真的看到候選點了。"""
    _, _, candidates = _scan_fs()
    assert candidates >= _ANCHOR_FS_CANDIDATES, (
        f"檔案系統掃描只找到 {candidates} 個候選呼叫（量測日 2026-08-28 為 42,"
        f"錨點 {_ANCHOR_FS_CANDIDATES}）。"
        f"字表或 AST 走訪可能壞了,規則正在對空氣生效。"
    )


def test_no_unregistered_filesystem_writes():
    """L2 不得寫入/刪除檔案系統（純函式不該有持久化副作用）。"""
    writes, _, _ = _scan_fs()
    _assert_ratchet(writes, set(FS_WRITE_DEBT), "L2 檔案系統寫入/刪除")


def test_no_unregistered_filesystem_reads():
    """L2 不得讀取檔案系統（需資料時走 L1 repository —— §8.2）。"""
    _, reads, _ = _scan_fs()
    _assert_ratchet(reads, set(FS_READ_DEBT), "L2 檔案系統讀取")


# ═══════════════════════════════════════════════════════════════════════════
# 規則 3：遠端 SDK 呼叫（gspread 等 —— 不含任何禁用「字」也要抓得到）
# ═══════════════════════════════════════════════════════════════════════════
# ⚠️ 這一條是本檔相對既有守衛最關鍵的補強:
#    `client.open_by_key(sid)` / `ws.get_all_values()` **不含 requests / httpx /
#    fetch_url / urlopen 任何一個字**,任何字面黑名單都掃不到它,
#    但它是**貨真價實的 Google Sheets API 網路往返**（含寫入）。

_REMOTE_SDK_METHODS = frozenset(
    {
        # gspread —— 刻意不含 `update`（撞 dict.update,見檔頭盲區 C）
        "open_by_key", "open_by_url", "get_all_values", "get_all_records",
        "append_row", "append_rows", "add_worksheet", "del_worksheet",
        "acell", "update_acell", "row_values", "col_values", "worksheets",
        "batch_update", "update_cells", "values_update", "get_worksheet",
        "get_gspread_client", "service_account", "service_account_from_dict",
        "authorize", "insert_row", "delete_rows", "clear",
        # yfinance / 其他資料 SDK 的典型入口
        "Ticker", "download",
        # 泛用 HTTP client 方法（受 receiver 限定,見掃描邏輯）
        "urlopen", "fetch_url", "request",
    }
)
_HTTP_RECEIVERS = frozenset({"requests", "httpx", "urllib", "session", "_session", "aiohttp"})


def _scan_remote_sdk() -> tuple[set[str], int]:
    hits: set[str] = set()
    candidates = 0
    for path in _services_files():
        rel = _rel(path)
        tree = _parse(path)
        ctx = _context_map(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            dotted = _dotted(node.func)
            last = dotted.split(".")[-1]
            head = dotted.split(".")[0]
            site = _site(rel, ctx.get(id(node), "<module>"))
            if last in _REMOTE_SDK_METHODS:
                if last in ("request", "clear") and head not in _HTTP_RECEIVERS:
                    continue  # `cache.clear()` / `dict.clear()` 之類
                candidates += 1
                hits.add(site)
            elif last in ("get", "post", "put", "delete", "patch", "head") and head in _HTTP_RECEIVERS:
                candidates += 1
                hits.add(site)
    return hits, candidates


# ── 豁免表：遠端 SDK 往返（2026-08-28 實測）──────────────────────────
# ⚠️ 登記 ≠ 核准。這是本檔債務表裡**性質最重**的一類:它同時是網路 I/O 與持久化寫入。
GSPREAD_DEBT: dict[str, str] = {
    # ── services/nav_history_gs.py ────────────────────────────────
    # ⚠️ 這一檔的檔頭自陳理由必須就地記下來,因為它示範了一種特定的失效模式:
    #    它寫「gspread I/O 為持久化職責,**不在 §8.2「L2 禁 requests/httpx/bs4/
    #    feedparser」清單**,且有 auto_search_store_gs 先例。」
    #    —— 那不是豁免理由,那是**規則字表的漏洞被拿來當通行證**。
    #    §8.2 的字表不完整（本 repo 憲法 §-1.5.1c 判定 2 已記載它漏抓兩次）,
    #    「不在清單裡」證明的是清單不全,不是這樣寫是對的。
    #    ⚠️ 2026-08-31 事實更新（**論證未變,只更正它引用的事實**）:它引用的「先例」
    #    `services/auto_search_store_gs.py` **已於本日整檔刪除**(auto_search 封閉死簇,
    #    production 0 caller;客戶 2026-08-31 授權死碼清理)。該檔當年**同樣沒有登錄在
    #    §8.2.A 例外表** —— 兩檔曾互為背書,兩檔都是 §8.2 末句明文禁止的「未經登錄的軟例外」。
    #    **先例消失不等於本檔的豁免變成正當**:本檔的登記理由與處置一字未改,
    #    它現在只是**少了那個可以拿來背書的對象**。
    "services/nav_history_gs.py::_get_sheet()":
        "L2 建立 gspread client 並開啟試算表（get_gspread_client + client.open_by_key "
        "+ oauth_client.open_by_key）。**未登錄於 §8.2.A 例外表**；檔頭以「不在 §8.2 "
        "字表清單內」自授豁免（見上方長註）。",
    "services/nav_history_gs.py::_get_worksheet()":
        "L2 建立工作表（sh.add_worksheet）—— 遠端**寫入**。同上,未登錄。",
    "services/nav_history_gs.py::append_points()":
        "L2 遠端寫入 NAV 點位（ws.append_rows + ws.get_all_values）。同上,未登錄。",
    "services/nav_history_gs.py::load_points()":
        "L2 遠端讀取（ws.get_all_values）。同上,未登錄。",
    # ── services/macro/weights_store.py ───────────────────────────
    "services/macro/weights_store.py::_gs_get_worksheet()":
        "L2 建立 gspread client + 開表 + 建工作表（get_gspread_client + "
        "client.open_by_key + sh.add_worksheet）。未登錄於 §8.2.A 例外表。",
    "services/macro/weights_store.py::_gs_load()":
        "L2 遠端讀取單格（ws.acell）。未登錄。",
}

# ~~_ANCHOR_REMOTE_SITES = 10  # 實測候選 24 / 判定違規 14~~
# ⚠️ **2026-08-31 改為自我校準,絕對下限退役(有意識的變更,不是漏刪;決策者:總管裁定)。**
#
# **活性檢查的目的完全保留** —— 本 repo 憲法 §-1.5.1c 判定 2 逐字記載過:
# 這類字表**漏抓過兩次**(2026-08-27 只掃 `import requests`、2026-08-28 字表沒有 `yfinance`),
# 所以「掃描器有沒有真的看到東西」這道檢查**必須留著**。換掉的只是**會誤傷的實作**。
#
# **為什麼絕對下限 10 必須退役(實測,不是假想)**:
#   2026-08-31 刪除 auto_search 死簇後,候選數 24 → 11,**距離 floor 只剩 1 格**。
#   稽核**實跑模擬**了本 repo 已具名列為待辦的下一步工作
#   (把 `services/nav_history_gs.py` 的 gspread 持久化搬出 L2):
#   候選 **11 → 4,本斷言當場轉紅**,而它吐出的訊息是「**字表或 AST 走訪可能壞了**」——
#   **那是假診斷**:掃描器完全正常,是債務真的被清掉了。
#   下一個工程師會去追一個**不存在的掃描器 bug**。
#   ⚠️ 這不是假想情境 —— 那份工作就寫在 `services/nav_history_gs.py` 檔頭與 `TODO.md` D-1。
#
# **改法(稽核已在兩個時點實測皆成立)**:下限改綁 `len(GSPREAD_DEBT)`。
#   **每一個登記在案的違規,依定義必然是一個候選點** —— 所以
#   「候選數 >= 登記數」恆成立;清債時兩邊**同步下降**,永不誤傷。
#   而掃描器若真的壞掉(字表漏抓 / AST 走訪斷掉),候選數會掉到登記數以下 → **照樣轉紅**。
#   實測:現況 11 >= 6 ✓;模擬搬走 nav_history_gs 後 4 >= 2 ✓。


def test_remote_sdk_scan_is_not_vacuous():
    """錨點：遠端 SDK 掃描真的看到候選點了（自我校準,見上方長註）。"""
    _, candidates = _scan_remote_sdk()
    floor = len(GSPREAD_DEBT)
    assert candidates >= floor, (
        f"遠端 SDK 掃描只找到 {candidates} 個候選呼叫,**少於豁免表登記的 {floor} 項**。\n"
        f"每個登記在案的違規依定義都必然是一個候選點,所以這個不等式恆該成立 ——\n"
        f"掉到登記數以下,代表**字表或 AST 走訪真的壞了**(而不是債務被清掉了)。\n"
        f"⚠️ 請先查掃描器,不要直接調這個數字:它是自我校準的,沒有可調的常數。"
    )


def test_no_unregistered_remote_sdk_calls():
    """L2 不得直接做遠端 SDK 往返（gspread / yfinance / HTTP client）。"""
    hits, _ = _scan_remote_sdk()
    _assert_ratchet(hits, set(GSPREAD_DEBT), "L2 遠端 SDK 往返")


# ═══════════════════════════════════════════════════════════════════════════
# 規則 4：真 UI 呼叫（**別名不敏感**）
# ═══════════════════════════════════════════════════════════════════════════
# ⚠️ 刻意**不寫死 `st.` 前綴**。本 repo 憲法 §8.2.A.1 驗證段 ① 逐字記載:
#    `ui/helpers/macro/ndc.py` 用的是 `@_st_mod.cache_data`,
#    「`@st\.cache_data` 這種寫法掃不到它」—— 綁前綴的規則會失明。
#    本檔改為:先從 import 陳述解析出 streamlit **被綁到哪些名字**,再看那些名字。

_UI_ATTRS = frozenset(
    {
        "session_state", "error", "markdown", "rerun", "warning", "success",
        "info", "write", "columns", "button", "dataframe", "metric", "caption",
        "expander", "tabs", "sidebar", "stop", "form", "toast", "plotly_chart",
        "container", "text_input", "selectbox", "checkbox", "radio", "slider",
        "spinner", "experimental_rerun", "set_page_config", "download_button",
        "file_uploader", "progress", "empty", "header", "subheader", "title",
    }
)


def _streamlit_aliases(tree: ast.Module) -> set[str]:
    """找出本模組把 streamlit 綁到哪些名字上（任何別名皆可）。"""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "streamlit":
                    names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] == "streamlit":
                for alias in node.names:
                    names.add(alias.asname or alias.name)
    return names


def _scan_ui() -> set[str]:
    hits: set[str] = set()
    for path in _services_files():
        rel = _rel(path)
        tree = _parse(path)
        ctx = _context_map(tree)
        aliases = _streamlit_aliases(tree)
        for node in ast.walk(tree):
            where = ctx.get(id(node), "<module>")
            # (a) import streamlit 本身（任何別名）
            if isinstance(node, (ast.Import, ast.ImportFrom)) and _streamlit_aliases(
                ast.Module(body=[node], type_ignores=[])
            ):
                hits.add(f"{_site(rel, where)} [import streamlit]")
            # (b) 綁定名上的真 UI 屬性存取
            if isinstance(node, ast.Attribute) and node.attr in _UI_ATTRS:
                base = _dotted(node.value)
                if base.split(".")[-1] in aliases:
                    hits.add(f"{_site(rel, where)} [{_dotted(node)}]")
    return hits


# ── 豁免表：真 UI 呼叫（2026-08-28 實測 = 空）────────────────────────
# ✅ services/ 全層目前**沒有任何** streamlit import 或 UI 呼叫 —— 這一條是乾淨的。
#    空表不代表規則沒作用:它代表**現況合規**,而 ratchet 會讓任何新增當場轉紅。
UI_DEBT: dict[str, str] = {}


def test_no_streamlit_or_ui_calls_in_services():
    """L2 不得 import streamlit 或做真 UI 呼叫（別名不敏感）。"""
    _assert_ratchet(_scan_ui(), set(UI_DEBT), "L2 真 UI 呼叫")


def test_ui_alias_detection_is_alias_insensitive():
    """自證：別名解析真的看得到 `import streamlit as _st_mod` 這種寫法。

    ⚠️ 這條測的是**守衛本身**,不是 production code。
    沒有它,`_streamlit_aliases` 壞掉時規則會靜默失效（現況空表 → 永遠綠）。
    """
    for src, expected in [
        ("import streamlit", {"streamlit"}),
        ("import streamlit as st", {"st"}),
        ("import streamlit as _st_mod", {"_st_mod"}),
        ("from streamlit import session_state as _ss", {"_ss"}),
        ("import pandas as pd", set()),
    ]:
        assert _streamlit_aliases(ast.parse(src)) == expected, src


# ═══════════════════════════════════════════════════════════════════════════
# 規則 5：跨層上行 import（雙向）
# ═══════════════════════════════════════════════════════════════════════════
# §8.2 硬規則第 5 條：「L1 不得 import L2/L3、L2 不得 import L3」
# 加上第 4 條的精神（L3 UI 不得直呼 L1）,方向必須是單向下行。

_L1_SCAN_TARGETS = ("repositories",)   # 目錄
_L1_SCAN_FILES = ("fund_fetcher.py",)  # 根目錄 legacy shim


def _l1_files() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for d in _L1_SCAN_TARGETS:
        out.extend(
            p for p in (ROOT / d).rglob("*.py") if "__pycache__" not in p.parts
        )
    out.extend(ROOT / f for f in _L1_SCAN_FILES if (ROOT / f).exists())
    return sorted(out)


def _scan_downward_violation() -> set[str]:
    """services/（L2）→ ui/ 或 app（L3）—— 上行,違憲。"""
    hits: set[str] = set()
    for path in _services_files():
        rel = _rel(path)
        for module, where in _imported_modules(_parse(path)):
            top = module.split(".")[0]
            if top in ("ui", "app"):
                hits.add(f"{_site(rel, where)} -> {module}")
    return hits


def _scan_upward_violation() -> set[str]:
    """repositories/ + fund_fetcher.py（L1）→ services（L2）—— 上行,違憲。"""
    hits: set[str] = set()
    for path in _l1_files():
        rel = _rel(path)
        for module, where in _imported_modules(_parse(path)):
            if module == "services" or module.startswith("services."):
                hits.add(f"{_site(rel, where)} -> {module}")
    return hits


# ── 豁免表：L2 → L3 上行（2026-08-28 實測 = 空）──────────────────────
SERVICES_TO_UI_DEBT: dict[str, str] = {}

# ── 豁免表：L1 → L2 上行（2026-08-28 實測）──────────────────────────
# ⚠️ 登記 ≠ 核准。這是 §8.2 硬規則第 5 條的直接違反。
#    `tests/conftest.py` 檔頭就地承認這條鏈有 latent 循環 import。
L1_TO_L2_DEBT: dict[str, str] = {
    "fund_fetcher.py::<module> -> services.fund_service":
        "L1 legacy re-export shim（§8.3 F-GRAY-1）在 **module 層**回頭 import L2。"
        "實測同檔 4 個 import 陳述皆為 module-level 且都指向 services.fund_service:"
        "`_RF_ANNUAL` + `set_risk_free_rate` / `calc_health_from_manual` / "
        "legacy re-export 群組 / `calc_dividend_estimate`。"
        "module-level 上行是 latent 循環 import 的來源 —— 同檔上方已有 "
        "`except ImportError: pass  # init-time circular` 的補丁在承接這個問題。",
    "repositories/portfolio_perf_repository.py::_gs_enabled() -> services.macro.weights_store":
        "L1 在函式內 lazy import L2 的 `_gs_enabled`。lazy import **不改變依賴方向**,"
        "只是把上行藏進函式體、躲過 module-level 掃描"
        "（同 CLAUDE.md 姊妹 repo 的 V-L0-NAME-1 記載的手法）。"
        "⚠️ 另一組正在動 repositories/,此列若因其改動而變動請一併更新。",
}


def test_l1_scan_is_not_vacuous():
    """錨點：反向掃描真的看到 L1 檔案了。"""
    files = _l1_files()
    assert len(files) >= 20, (
        f"L1 只掃到 {len(files)} 檔（量測日 2026-08-28 為 31）。掃描條件可能壞了。"
    )
    assert any(p.name == "fund_fetcher.py" for p in files), (
        "根目錄 fund_fetcher.py 沒被掃到 —— 反向規則正在對空氣生效。"
    )


def test_services_does_not_import_ui_or_app():
    """§8.2 硬規則 5：L2 不得 import L3（ui / app）。"""
    _assert_ratchet(_scan_downward_violation(), set(SERVICES_TO_UI_DEBT), "L2→L3 上行 import")


def test_l1_does_not_import_services():
    """§8.2 硬規則 5 的反方向：L1（repositories / fund_fetcher）不得 import L2。"""
    _assert_ratchet(_scan_upward_violation(), set(L1_TO_L2_DEBT), "L1→L2 上行 import")


# ═══════════════════════════════════════════════════════════════════════════
# 規則 6：執行期改寫 module namespace —— **守衛的盲區本身**
# ═══════════════════════════════════════════════════════════════════════════
# `for _name in dir(_mod): globals()[_name] = getattr(_mod, _name)`
# 把另一個模組的符號整包注入本模組。
# **任何靜態守衛（包含本檔上面全部規則）對這樣注入進來的東西都是瞎的。**
# 故本條把「這種寫法本身」當成違規登記 —— 它守的不是內容,是盲區的邊界。


def _scan_namespace_injection() -> set[str]:
    hits: set[str] = set()
    for path in _services_files():
        rel = _rel(path)
        tree = _parse(path)
        ctx = _context_map(tree)
        for node in ast.walk(tree):
            targets: list[ast.AST] = []
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                targets = [node.target]
            for tgt in targets:
                if (
                    isinstance(tgt, ast.Subscript)
                    and isinstance(tgt.value, ast.Call)
                    and isinstance(tgt.value.func, ast.Name)
                    and tgt.value.func.id in ("globals", "vars", "locals")
                ):
                    hits.add(_site(rel, ctx.get(id(node), "<module>")))
            # setattr(sys.modules[...], ...) 也是同一類手法
            if isinstance(node, ast.Call) and _dotted(node.func) == "setattr":
                if node.args and isinstance(node.args[0], ast.Subscript):
                    if "sys.modules" in _dotted(node.args[0].value):
                        hits.add(_site(rel, ctx.get(id(node), "<module>")))
    return hits


# ── 豁免表：執行期 namespace 注入（2026-08-28 實測）──────────────────
# ⚠️ 登記 ≠ 核准。這三檔是**本檔全部規則的盲區**。
NAMESPACE_INJECTION_DEBT: dict[str, str] = {
    "services/macro_composite_score.py::<module>":
        "向後相容 shim:`for _name in dir(_mod): globals()[_name] = getattr(_mod, _name)`。"
        "**靜態分析看不穿** —— 被注入的符號若帶 I/O,本檔上面所有規則都掃不到。",
    "services/macro_validation.py::<module>":
        "同型向後相容 shim,同樣用 globals() 整包注入,同樣是本檔所有規則的盲區。"
        "被它注入的符號若帶 I/O,上面每一條規則都掃不到。",
}


def test_no_runtime_namespace_injection():
    """L2 不得在執行期改寫 module namespace（那會讓所有靜態守衛失明）。"""
    _assert_ratchet(
        _scan_namespace_injection(), set(NAMESPACE_INJECTION_DEBT), "L2 執行期 namespace 注入"
    )


# ═══════════════════════════════════════════════════════════════════════════
# 規則 7：豁免表本身的自我檢查
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "table_name,table",
    [
        ("IMPORT_DEBT", IMPORT_DEBT),
        ("FS_WRITE_DEBT", FS_WRITE_DEBT),
        ("FS_READ_DEBT", FS_READ_DEBT),
        ("GSPREAD_DEBT", GSPREAD_DEBT),
        ("UI_DEBT", UI_DEBT),
        ("SERVICES_TO_UI_DEBT", SERVICES_TO_UI_DEBT),
        ("L1_TO_L2_DEBT", L1_TO_L2_DEBT),
        ("NAMESPACE_INJECTION_DEBT", NAMESPACE_INJECTION_DEBT),
    ],
)
def test_debt_entries_carry_a_reason_and_no_line_numbers(table_name, table):
    """每一列債務都要有實質理由,且鍵不得含行號（§8.2.A.0 規則 1）。"""
    for key, reason in table.items():
        assert "::" in key, f"{table_name}['{key}'] 的鍵格式應為 `相對路徑::函式()`"
        head = key.split(" ")[0]
        assert not any(
            part.isdigit() for part in head.replace("::", ":").split(":")
        ), f"{table_name}['{key}'] 的鍵含行號 —— 行號保證會過期,改用符號名"
        assert len(reason) >= 20, (
            f"{table_name}['{key}'] 的理由太短。"
            f"豁免表是技術債的可見化,必須寫清楚**債在哪**,不是寫「已知」兩個字帶過。"
        )


def test_debt_tables_are_debt_not_approval():
    """本檔的立場宣告：豁免表登記的是債,不是核准。

    這條測試沒有掃描動作,它把「數字只准在有人真的修好時往下走」這件事
    釘成一個會被讀到的斷言 —— 並記錄量測日的債務總量,讓後人一眼看出趨勢。
    """
    total = (
        len(IMPORT_DEBT) + len(FS_WRITE_DEBT) + len(FS_READ_DEBT)
        + len(GSPREAD_DEBT) + len(UI_DEBT) + len(SERVICES_TO_UI_DEBT)
        + len(L1_TO_L2_DEBT) + len(NAMESPACE_INJECTION_DEBT)
    )
    # ~~2026-08-28 建表當下的實測總量 = 45。~~ → **2026-08-31 下修為 28。**
    # **只准往下,不准往上。** 往上 = 有人新增違規並把它加進豁免表 —— 那正是本檔要擋的事。
    #
    # ⚠️ **2026-08-31 由 45 下修為 28 的理由(有意識的變更,不是漏刪;決策者:總管裁定)**:
    #   這 17 格的下降是 **auto_search 封閉死簇整簇刪除的機械衍生值,不是債務被修復** ——
    #   `auto_search{,_store_gs,_store_local}.py` / `calibration/multi_factor.py` /
    #   `multi_factor_optimization.py` 五檔 production 0 caller 被實體刪除,
    #   登記在案的違規**隨載體一起消失**。**沒有任何一項是被修好的。**
    #   ⛔ **不得**把這個數字下降讀成 L2 純度有任何實質改善;剩下 28 項一項都沒被處理。
    #
    # **為什麼天花板必須跟著降(這是本次補正的重點)**:
    #   若留在 45,就等於留下 **17 格空檔**。主守衛(`_assert_ratchet`)雙向有牙,
    #   新違規**無法不登記地混入**;但**登記之後**的新違規會同時通過主守衛與這道天花板,
    #   要累積滿 17 個才會被擋 —— 而本斷言自陳的契約是
    #   「**數字只准在有人真的修好時往下走**」。空檔是刪檔那一批造成的,
    #   留著等於靜默鬆掉一道剛被移動過的 ratchet。
    assert total <= 28, (
        f"豁免表總量 {total} 超過現行上限 28 項(2026-08-31 由 45 下修)。\n"
        f"豁免表是**技術債的可見化,不是核准** —— 新違規請修掉,不要登記。\n"
        f"真的必須豁免時,依 §8.2.A 走完登錄程序,並在本斷言就地說明為何調高上限。\n"
        f"⚠️ 調高上限前先問:這個數字上一次下降,是**有人修好了**,還是**載體被刪掉了**?"
        f"後者不構成調高的理由。"
    )
