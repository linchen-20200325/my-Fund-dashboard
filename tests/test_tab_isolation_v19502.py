"""v19.502:app.py 每個 `with tab_*:` 分頁必須用 try/except 隔離(防一崩全崩)。

user 2026-08-21 回報「每個 Tab 小按鈕壓下就整個跳出來」。結構根因:st.tabs 單次 run
渲染全部分頁,任一未捕捉例外中止整個 script → 全頁崩。當時 7 分頁只有 2 個(macro/manage)
包 try/except,其餘 5 個裸露。本測試靜態守「所有 tab_* 分頁 body 皆含 try + friendly_error」,
防未來再加裸 Tab。另守 requirements.txt pandas/numpy 已鎖上界(py3.14 雲端防 C 擴充 segfault)。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _tab_with_blocks():
    """回傳 app.py 中所有 `with tab_*:` 的 (tab_name, With node)。"""
    tree = ast.parse((_ROOT / "app.py").read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        for item in node.items:
            ctx = item.context_expr
            if isinstance(ctx, ast.Name) and ctx.id.startswith("tab_"):
                out.append((ctx.id, node))
    return out


def test_all_tab_blocks_exist():
    """⚠️ **2026-08-31 由 WP-F 收斂:七 → 五。有意識的政策變更,不是漏改。**
    (日期 2026-08-31;決策者:**客戶 2026-08-31 拍板的五分頁動線線框**
    `docs/wireframes/fund-wireframe-final.html` §03)

    **舊斷言**(原地保留、加刪除線,不刪)::

        ~~# 7 個決策動線分頁(v19.502 當下)~~
        ~~expected = {"tab_macro", "tab_health", "tab_batch", "tab_single",~~
        ~~            "tab_portfolio", "tab_manage", "tab_ref"}~~
        ~~assert expected <= names, f"app.py 缺分頁 with 區塊:{expected - names}"~~

    **舊斷言的理由仍然成立**:它守的是「**每一個分頁都要有自己的 `with` 區塊**」——
    下面兩條的隔離檢查是逐個 `with tab_*:` 掃的,少一個 `with`,那個分頁就從隔離
    檢查裡整個消失(**漏檢不會紅,只會安靜地沒被守到**)。

    **被權衡掉的是那份寫死的 7 個變數名**:`tab_batch`／`tab_single` 併入
    `tab_research`、`tab_manage`／`tab_ref` 併入 `tab_settings`。
    **而且它本來就不該寫死** —— 分頁清單的 SSOT 是
    `ui/helpers/story_nav._TAB_LABELS`,在測試裡再抄一份 7 個名字就是「第二份標籤」,
    正是 2026-08-05／08-14 兩次稽核抓到的同型病。

    **改法:從 SSOT 導出、不再手抄** —— 分頁增減時本條自動跟上。
    ⚠️ 比較改用 `==` 而非舊的 `<=`:多出一個**沒登記在 SSOT** 的 `with tab_*:`
    同樣要紅(那代表有分頁沒進 SSOT)。**這比舊寫法嚴,不是放寬。**
    """
    from ui.helpers.story_nav import _TAB_LABELS

    names = {n for n, _ in _tab_with_blocks()}
    expected = {f"tab_{_k}" for _k in _TAB_LABELS}
    assert names == expected, (
        f"app.py 的 `with tab_*:` 與分頁 SSOT 對不上:"
        f"缺 {sorted(expected - names)}／多 {sorted(names - expected)}")


def test_every_tab_block_has_try_except():
    """每個 with tab_*: body 第一層必須含 Try(分頁隔離)。"""
    bare = []
    for name, node in _tab_with_blocks():
        has_try = any(isinstance(child, ast.Try) for child in node.body)
        if not has_try:
            bare.append(name)
    assert not bare, (
        f"以下分頁未用 try/except 隔離,任一例外會崩全站(v19.502 修的正是這個):{bare}"
    )


def test_every_tab_try_calls_friendly_error():
    """隔離的 except 必須走 friendly_error(§1 非靜默吞,顯式顯示 + traceback)。

    ⚠️ **2026-08-31 由 WP-F 收斂。有意識的政策變更,不是漏改。**
    (日期 2026-08-31;決策者:**客戶 2026-08-31 拍板的五分頁動線線框**)

    **舊寫法**(原地保留、加刪除線,不刪)::

        ~~src = (_ROOT / "app.py").read_text(encoding="utf-8")~~
        ~~# 7 分頁 → 至少 7 個 friendly_error import~~
        ~~n_fe = len(re.findall(r"friendly_error as _fe_", src))~~
        ~~assert n_fe >= 7, f"分頁隔離的 friendly_error 少於 7(實際 {n_fe})"~~

    **舊寫法的理由仍然成立**:分頁隔離的 `except` **不得靜默吞**,一定要有一個對
    使用者可見的告知。這件事一個字都沒有被推翻,本條下方仍然逐個分頁驗。

    **被權衡掉的有兩點,第二點比第一點重要**:
    (a) 寫死的「7」在七→五之後恆為假(5 個分頁不可能有 7 個 import);
    (b) **它數的是全檔的字串出現次數,不是「每個分頁都有」** —— 也就是說
        把其中一個分頁的 except 改成 `pass`、同時在別處多寫兩個 `_fe_` 別名,
        舊寫法照樣綠。**它從來沒有真的守到「每一個分頁」。**

    **改法:改用 AST 逐個 `with tab_*:` 檢查**,要求該分頁的 `except` 區塊裡
    確實有一個對 `friendly_error`(不論 alias)的**呼叫**。
    **範圍變窄、強度變強**,不是放寬 —— 突變自證見下方。

    突變實驗(2026-08-31 實跑,N2):把 `app.py` 某一分頁 except 內的 `_fe_xxx(...)`
    **呼叫**刪掉、**import 留著** → **本條轉紅**。

    ⚠️ 舊寫法在同一個突變下的表現,**據實寫清楚(初稿寫「仍是綠的」,不精確,已更正)**:
    舊寫法數的是 `friendly_error as _fe_` 這個字串的出現次數,而該突變**只刪呼叫、
    不刪 import** —— 實測**計數 5 → 5,完全沒變**。也就是說舊寫法**在結構上偵測不到
    這個突變**;它當時之所以會紅,是因為那個寫死的 `>= 7` 在五分頁下恆為假,
    **與這個 bug 無關**。**「因為別的原因紅」不等於「守到了」。**
    """
    bad: list[str] = []
    for name, node in _tab_with_blocks():
        _ok = False
        for _h in ast.walk(node):
            if not isinstance(_h, ast.ExceptHandler):
                continue
            # 該 handler 內 import 進來的 friendly_error 別名(可能就叫 friendly_error)
            _alias = {a.asname or a.name
                      for n2 in ast.walk(_h) if isinstance(n2, ast.ImportFrom)
                      for a in n2.names if a.name == "friendly_error"}
            _alias.add("friendly_error")
            # 該 handler 內是否真的**呼叫**了它(只 import 不呼叫 = 沒接出去)
            if any(isinstance(c, ast.Call)
                   and (getattr(c.func, "id", None) in _alias
                        or getattr(c.func, "attr", None) in _alias)
                   for c in ast.walk(_h)):
                _ok = True
        if not _ok:
            bad.append(name)
    assert not bad, (
        f"以下分頁的 except 沒有**呼叫** friendly_error(靜默吞或只 import 沒接):{bad}")

    # 順帶鎖數量:分頁數由 SSOT 導出,不再寫死 7
    from ui.helpers.story_nav import _TAB_LABELS
    assert len(_tab_with_blocks()) == len(_TAB_LABELS), (
        f"`with tab_*:` 區塊數 {len(_tab_with_blocks())} 與分頁 SSOT "
        f"{len(_TAB_LABELS)} 不符")


# ── requirements.txt 漂移鎖:pandas/numpy 必鎖上界(py3.14 雲端防 segfault)──────
def test_pandas_capped_below_3():
    req = (_ROOT / "requirements.txt").read_text(encoding="utf-8")
    m = re.search(r"^pandas\s*([<>=!,.\d ]+)$", req, re.M)
    assert m, "requirements.txt 找不到 pandas 行"
    spec = m.group(1).replace(" ", "")
    assert "<3.0" in spec, f"pandas 必須鎖 <3.0(未測 3.0 C 擴充 py3.14 segfault),實際 {spec}"
    assert ">=2.3.3" in spec, f"pandas 下界須 >=2.3.3(唯一具 cp314 wheel 的 2.x),實際 {spec}"


def test_numpy_capped():
    req = (_ROOT / "requirements.txt").read_text(encoding="utf-8")
    m = re.search(r"^numpy\s*([<>=!,.\d ]+)$", req, re.M)
    assert m, "requirements.txt 找不到 numpy 行"
    spec = m.group(1).replace(" ", "")
    assert "<2.6" in spec, f"numpy 須鎖上界 <2.6,實際 {spec}"
    assert ">=2.3.2" in spec, f"numpy 下界須 >=2.3.2(cp314 wheel 起點),實際 {spec}"
