# -*- coding: utf-8 -*-
"""預覽殼層（BL-0484／BL-0479；D1 方案 A）的靜態與純邏輯守衛（fast lane；不需要 streamlit、瀏覽器）。

客戶裁示：`DEC-2026-10-27-01`（方案 A）、`-09`（深色主側欄＋淺色主內容區，只限視覺 theme）、`-10`（第二層先用 44 既有區塊
標題、不自創文案）、`-11`（手機底部導航五主頁、主要目的地 ≤2 次互動、390px 實測）、`-12`（風險觀察不顯示）。
畫面層（390／1280 真瀏覽器）的對應守衛在 `test_shell_page.py`（slow lane）。

本檔釘住：
1. 第一層＝`app_preview.PAGES` 的順序與頁名，殼層不另寫、不新增任何頁名或文案；
2. 客戶已裁示不進導覽的名稱（風險觀察／再平衡／台股趨勢／國際趨勢）沒有出現在導覽、殼層程式或殼層樣式；
3. 殼層只動導覽：兩個殼層檔的 import 隔離（只有 `streamlit`、標準庫、`ui_v2.shell_nav`）、不呼叫任何 AI／網路／query params；
4. 手機斷點與 44 第二節 2.1 的「≤768：單欄」同值；觸控目標 ≥ 44px；「目前頁」除顏色外另有粗體與底線；
5. `app_preview.main` 的接法（原生導覽 `position="hidden"`、殼層先於頁面、側欄說明字面不變）；
6. 淺色主內容區／深色側欄：`.streamlit/config.toml` 與五頁 `theme.py` 的底色同值，殼層色票的對比達標。

每一條都附正控（守衛真的抓得到），避免它在結構上就是空的。
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys
import tomllib

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT))

from ui_v2 import shell_nav  # noqa: E402  純邏輯，不 import streamlit
from ui_v2.alo import theme as alo_theme  # noqa: E402  只借它的 WCAG 對比函式

_PREVIEW = _ROOT / "ui_v2" / "app_preview.py"
_SHELL = _ROOT / "ui_v2" / "shell.py"
_SHELL_NAV = _ROOT / "ui_v2" / "shell_nav.py"
_SPEC44 = _ROOT / "docs" / "v2" / "44_fund_ui_ssot.md"
_CONFIG = _ROOT / ".streamlit" / "config.toml"


def _tree(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _preview_pages() -> list:
    """`app_preview.PAGES` 逐格讀（含函式名，不能整個 literal_eval）→ `[(slug, title)]`。"""
    node = next(n for n in _tree(_PREVIEW).body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "PAGES" for t in n.targets))
    return [(ast.literal_eval(e.elts[0]), ast.literal_eval(e.elts[1])) for e in node.value.elts]


def _imports(path: pathlib.Path) -> set:
    """一個檔的 import：`import a.b` → `a.b`；`from a import b` → `a.b`（`__future__` 取模組名本身）。"""
    out = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                out.add("__future__")
            else:
                out |= {f"{node.module}.{a.name}" for a in node.names}
    return out


# ═══════════════════════ 1. 第一層＝PAGES，不新增文案 ═══════════════════════


def test_第一層順序與頁名就是PAGES_一個字不改():
    pages = _preview_pages()
    # → 2026-10-30 Batch D（`DEC-2026-10-30-02`；有意識的政策變更，不是漏刪）：舊五項 ["🌍 市場與趨勢", "⚖️ 資產配置", "💼 我的持股",
    #   "🔍 找基金", "⚙️ 設定"] 的第 2、3 項併成「💼 我的資產」（44 之二十其一的正式頁序）；順序與頁名仍逐字取自 PAGES。
    assert [t for _s, t in pages] == ["🌍 市場與趨勢", "💼 我的資產", "🔍 找基金", "⚙️ 設定"]
    items = shell_nav.build_items(pages, "💼 我的資產")
    assert [(i["slug"], i["title"]) for i in items] == pages
    # 名稱與圖示切開後再接回去必須與 PAGES 的頁名逐字相同（不新增、不改字）。
    for item in items:
        assert f'{item["icon"]} {item["name"]}' == item["title"]


@pytest.mark.parametrize("title,want", [
    ("🌍 市場與趨勢", ("🌍", "市場與趨勢")),
    ("⚖️ 資產配置", ("⚖️", "資產配置")),
    ("⚙️ 設定", ("⚙️", "設定")),
    ("設定", ("", "設定")),          # 沒有圖示：整串當名稱，不猜、不補
    ("Home page", ("", "Home page")),   # 第一段是文字不是 emoji：不當圖示（Streamlit 會對非 emoji 的 icon 拋例外）
    ("設定 說明", ("", "設定 說明")),
    ("", ("", "")),
])
def test_split_title(title, want):
    assert shell_nav.split_title(title) == want


def test_目前頁恰好一項_找不到就一項都沒有():
    pages = _preview_pages()
    for _slug, title in pages:
        items = shell_nav.build_items(pages, title)
        assert [i["current"] for i in items].count(True) == 1
        assert next(i for i in items if i["current"])["title"] == title
    assert [i["current"] for i in shell_nav.build_items(pages, "不存在的頁")] == [False] * len(pages)   # 不猜
    assert [i["current"] for i in shell_nav.build_items(pages, "")] == [False] * len(pages)
    assert shell_nav.build_items([], "x") == []


def test_容器key_目前頁多一個結尾_兩個導覽不重複():
    keys = []
    for prefix in (shell_nav.SIDEBAR_KEY_PREFIX, shell_nav.BOTTOM_ITEM_PREFIX):
        for slug, _ in _preview_pages():
            for current in (False, True):
                keys.append(shell_nav.container_key(prefix, slug, current))
    assert len(keys) == len(set(keys)) == 4 * len(_preview_pages())   # 兩個導覽 × 每頁（目前／非目前）
    assert shell_nav.container_key("shell-side", "mkt", True).endswith(shell_nav.CURRENT_SUFFIX)
    assert not shell_nav.container_key("shell-side", "mkt", False).endswith(shell_nav.CURRENT_SUFFIX)
    # 底部導覽容器本身的 key 不能與任何一項的 key 重複。
    assert shell_nav.BOTTOM_KEY not in keys


# ═══════════════════════ 2. 客戶已裁示不進導覽的名稱 ═══════════════════════


def test_裁示不進導覽的名稱_不在頁名_不在殼層程式碼_不在樣式():
    assert shell_nav.NOT_IN_NAV == ("風險觀察", "再平衡", "台股趨勢", "國際趨勢")
    titles = " ".join(t for _s, t in _preview_pages())
    shell_source = _SHELL.read_text(encoding="utf-8")
    for name in shell_nav.NOT_IN_NAV:
        assert name not in titles, name
        assert name not in shell_source, name
        assert name not in shell_nav.SHELL_CSS, name
    # `shell_nav.py` 自己的字面只有 `NOT_IN_NAV` 那一個 tuple 與說明文字；其餘字串常數（導覽內容、樣式）不得含這些名稱。
    tree = _tree(_SHELL_NAV)
    allowed = {n for n in shell_nav.NOT_IN_NAV}
    docstring_nodes = {id(n.body[0].value) for n in ast.walk(tree)
                       if isinstance(n, (ast.Module, ast.FunctionDef)) and n.body
                       and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstring_nodes:
            if node.value in allowed:
                continue                      # NOT_IN_NAV 自己的元素
            if any(name in node.value for name in allowed):
                bad.append(node.value[:60])
    assert bad == [], bad


def test_正控_導覽裡出現被禁名稱就抓得到():
    pages = _preview_pages() + [("risk", "🛡️ 風險觀察")]
    titles = " ".join(t for _s, t in pages)
    assert any(name in titles for name in shell_nav.NOT_IN_NAV)


# ═══════════════════════ 3. 殼層只動導覽 ═══════════════════════


def test_shell_nav_不import任何東西_純標準庫():
    assert _imports(_SHELL_NAV) <= {"__future__"}, _imports(_SHELL_NAV)


def test_shell_只import_streamlit與shell_nav():
    allowed = {"__future__", "streamlit", "ui_v2.shell_nav"}
    assert _imports(_SHELL) <= allowed, _imports(_SHELL) - allowed


_BANNED_CALLS = ("query_params", "session_state", "secrets", "switch_page", "rerun", "cache_data", "cache_resource",
                 "text_input", "button", "form", "write", "html", "components")


def test_殼層不讀寫狀態_不取資料_不呼叫AI_只畫連結():
    source = _SHELL.read_text(encoding="utf-8")
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
    code = re.sub(r'""".*?"""', "", code, flags=re.S)
    for banned in _BANNED_CALLS:
        assert f"st.{banned}" not in code, banned
        assert f".{banned}(" not in code, banned
    for banned in ("gemini", "llm", "ai_service", "requests", "fixtures", "source"):
        assert banned not in " ".join(_imports(_SHELL)).lower(), banned
    # 只允許這幾個 streamlit 呼叫。
    called = {n.func.attr for n in ast.walk(_tree(_SHELL)) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and isinstance(n.func.value, ast.Name) and n.func.value.id == "st"}
    assert called == {"markdown", "container", "page_link", "columns"}, called


def test_殼層沒有預留AI區_沒有任何AI字樣():
    """`DEC-2026-10-27-25`：全站 AI 區屬殼層，但第 1 批不確定就不預留 —— 殼層不畫任何空 AI 區。"""
    for path in (_SHELL, _SHELL_NAV):
        text = path.read_text(encoding="utf-8")
        body = re.sub(r'""".*?"""', "", text, flags=re.S)
        body = "\n".join(line for line in body.splitlines() if not line.lstrip().startswith("#"))
        assert re.search(r"\bAI\b", body) is None, path.name
        assert re.search(r"\bai_|_ai\b|\bgemini\b|\bllm\b", body.lower()) is None, path.name


# ═══════════════════════ 4. 斷點、觸控目標、非顏色辨識 ═══════════════════════


def test_手機斷點與44第二節同值():
    text = _SPEC44.read_text(encoding="utf-8")
    assert "≤768：單欄" in text      # 44 2.1 客戶 2026-09-22 最終版（逐字）
    assert shell_nav.MOBILE_MAX_PX == 768
    assert f"max-width: {shell_nav.MOBILE_MAX_PX}px" in shell_nav.SHELL_CSS
    # 桌機（> 斷點）不畫底部導覽：基底樣式 display:none，媒體查詢內才 display:block。
    css = shell_nav.SHELL_CSS
    base = css.index(f".st-key-{shell_nav.BOTTOM_KEY} {{ display: none; }}")
    media = css.index("@media (max-width")
    assert base < media
    assert re.search(rf"@media \(max-width: 768px\) \{{\s*\.st-key-{shell_nav.BOTTOM_KEY} \{{\s*display: block", css)


def test_觸控目標至少44px():
    assert shell_nav.TOUCH_MIN_PX >= 44
    assert shell_nav.BOTTOM_NAV_ITEM_MIN_PX >= 44
    assert f"min-height: {shell_nav.TOUCH_MIN_PX}px" in shell_nav.SHELL_CSS
    assert f"min-height: {shell_nav.BOTTOM_NAV_ITEM_MIN_PX}px" in shell_nav.SHELL_CSS


def test_目前頁除了顏色另有粗體與底線_兩個導覽都有():
    css = shell_nav.SHELL_CSS
    now = f'[class*="{shell_nav.CURRENT_SUFFIX}"]'
    side_block = css[css.index(f'[data-testid="stSidebar"] {now} [data-testid="stPageLink-NavLink"] p'):]
    side_block = side_block[:side_block.index("}")]
    assert "font-weight: 700" in side_block and "text-decoration: underline" in side_block
    bottom_start = css.index(f'.st-key-{shell_nav.BOTTOM_KEY} {now} [data-testid="stPageLink-NavLink"] p')
    bottom_block = css[bottom_start:css.index("}", bottom_start)]
    assert "font-weight: 700" in bottom_block and "text-decoration: underline" in bottom_block
    # 色條（形狀）也在：側欄左側、底部上緣。
    assert "border-left: 4px solid" in css and "border-top: 3px solid" in css


def test_底部導覽五格等寬同一列_不被頁面自己的窄寬度堆疊規則吃掉():
    css = shell_nav.SHELL_CSS
    key = f".st-key-{shell_nav.BOTTOM_KEY}"
    assert f'{key} [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important;' in css
    assert "width: 20% !important" in css
    assert "padding-bottom: calc(" in css          # 內容底部讓出導覽的高度，不被蓋住


def test_shell_css_是常數_不依賴執行期狀態():
    assert shell_nav.shell_css() == shell_nav.SHELL_CSS == shell_nav.shell_css()


# ═══════════════════════ 5. app_preview.main 的接法 ═══════════════════════


def _main_calls() -> list:
    main = next(n for n in _tree(_PREVIEW).body if isinstance(n, ast.FunctionDef) and n.name == "main")
    return [ast.unparse(n) for n in ast.walk(main) if isinstance(n, ast.Call)]


def test_main_原生導覽position_hidden_殼層在頁面之前_側欄說明字面不變():
    calls = _main_calls()
    nav = next(c for c in calls if c.startswith("st.navigation("))
    assert "position='hidden'" in nav or 'position="hidden"' in nav
    order = [c.split("(")[0] for c in calls if c.split("(")[0] in
             ("st.navigation", "shell.render", "st.sidebar.info", "navigation.run")]
    assert order == ["st.navigation", "shell.render", "st.sidebar.info", "navigation.run"], order
    info = next(c for c in calls if c.startswith("st.sidebar.info("))
    assert info == "st.sidebar.info(PREVIEW_NOTE)"
    # 殼層吃的 entries 順序與頁名取自 PAGES（zip PAGES 與 pages），不另寫一份。
    render = next(c for c in calls if c.startswith("shell.render("))
    assert "PAGES" in render and "current_title=navigation.title" in render


def test_main_沒有留下原生側欄導覽的預設位置():
    """沒有 `position="hidden"` 的 `st.navigation` 會讓原生側欄導覽與自繪導覽並存（兩套導覽）。"""
    navs = [c for c in _main_calls() if c.startswith("st.navigation(")]
    assert len(navs) == 1
    assert "hidden" in navs[0]


def test_PAGES之外沒有其他導覽來源():
    """`app_preview.py` 的 `st.Page(...)` 只在 `main`／`_settings_page`／`_page_links` 由 PAGES 建。"""
    src = _PREVIEW.read_text(encoding="utf-8")
    assert len(re.findall(r"\bst\.Page\(", src)) == 3


# ═══════════════════════ 6. 淺色主內容區、深色側欄 ═══════════════════════


def _config() -> dict:
    return tomllib.loads(_CONFIG.read_text(encoding="utf-8"))


def test_config_主內容區淺色_側欄深色():
    theme = _config()["theme"]
    assert theme["base"] == "light"
    assert alo_theme.relative_luminance(theme["backgroundColor"]) > 0.8
    assert alo_theme.relative_luminance(theme["textColor"]) < 0.1
    side = theme["sidebar"]
    assert alo_theme.relative_luminance(side["backgroundColor"]) < 0.05
    assert alo_theme.relative_luminance(side["textColor"]) > 0.7
    assert side["backgroundColor"] == shell_nav.NAV_BG
    assert side["secondaryBackgroundColor"] == shell_nav.NAV_BG_RAISED


@pytest.mark.parametrize("page", ["alo", "exp", "hld", "set", "mkt"])
def test_config底色與各頁theme的APP_BG同值(page):
    """頁面自己的 `<style>` 會畫 `.stApp { background: APP_BG }`；與 config 不同值會在載入瞬間閃色。"""
    mod = __import__(f"ui_v2.{page}.theme", fromlist=["APP_BG"])
    assert mod.APP_BG == _config()["theme"]["backgroundColor"]
    assert alo_theme.relative_luminance(mod.APP_BG) > 0.8


def test_殼層色票對比達標():
    c = alo_theme.contrast_ratio
    assert c(shell_nav.NAV_TEXT, shell_nav.NAV_BG) >= 4.5
    assert c(shell_nav.NAV_TEXT, shell_nav.NAV_BG_RAISED) >= 4.5
    assert c(shell_nav.NAV_TEXT_MUTED, shell_nav.NAV_BG) >= 4.5
    assert c(shell_nav.NAV_ACCENT, shell_nav.NAV_BG) >= 3.0          # 非文字（色條）門檻 3
    assert c(shell_nav.NAV_ACCENT, shell_nav.NAV_BG_RAISED) >= 3.0


def test_亮青是客戶逐字指定值_殼層沿用():
    assert shell_nav.NAV_ACCENT == "#5fd3d0"
    assert shell_nav.NAV_BG == "#0e1117"


def test_五頁theme的青色兩值沒動():
    for page in ("alo", "exp", "hld", "set", "mkt"):
        mod = __import__(f"ui_v2.{page}.theme", fromlist=["TEAL_DARK"])
        assert mod.TEAL_DARK == "#0f6b6c" and mod.TEAL_BRIGHT == "#5fd3d0", page


@pytest.mark.parametrize("page", ["alo", "exp", "hld", "set", "mkt"])
def test_頁面CSS不再把亮青當主內容區文字色(page):
    """亮青 #5fd3d0 在淺底上對比不足；主內容區一律用 `TEAL_DARK`（`DEC-2026-10-27-09`）。"""
    src = (_ROOT / "ui_v2" / page / "page.py").read_text(encoding="utf-8")
    assert "theme.TEAL_BRIGHT" not in src
    assert "theme.TEAL_DARK" in src
