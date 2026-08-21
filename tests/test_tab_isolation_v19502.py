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
    names = {n for n, _ in _tab_with_blocks()}
    # 7 個決策動線分頁(v19.502 當下)
    expected = {"tab_macro", "tab_health", "tab_batch", "tab_single",
                "tab_portfolio", "tab_manage", "tab_ref"}
    assert expected <= names, f"app.py 缺分頁 with 區塊:{expected - names}"


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
    """隔離的 except 必須走 friendly_error(§1 非靜默吞,顯式顯示 + traceback)。"""
    src = (_ROOT / "app.py").read_text(encoding="utf-8")
    # 7 分頁 → 至少 7 個 friendly_error import(macro/health/batch/single/portfolio/manage/ref)
    n_fe = len(re.findall(r"friendly_error as _fe_", src))
    assert n_fe >= 7, f"分頁隔離的 friendly_error 少於 7(實際 {n_fe})—— 有分頁沒接錯誤處理"


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
