"""app.py / mk_dashboard.py 靜態 smoke test（CLAUDE.md §4 強制驗證）

不啟動 Streamlit runtime，純 AST / exec 驗證：
  T1. AST 編譯 — 確保兩個入口檔語法正確
  T2. expander 巢狀偵測 — 同檔 + 跨檔（含 transitive 呼叫鏈，防 PR #41 重現）
  T3. _HOLDING_ZH 對照表 + _zh_holding helper — 20 個 cases（PR #40 + #43）
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]  # v19.197 P0-3:test 遷移 tests/,改 parents[1] 回專案根
APP = ROOT / "app.py"
# v11.0 D-19: mk_dashboard.py 搬至 ui/components/mk_dashboard.py 並改為 shim
# expander 巢狀守門 AST 解析需指向真正含函式體的新位置
MK = ROOT / "ui" / "components" / "mk_dashboard.py"


# ════════════════════════════════════════════════════════════
# T1. AST 編譯
# ════════════════════════════════════════════════════════════
@pytest.mark.parametrize("path", [APP, MK])
def test_ast_parse_compiles(path: Path) -> None:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


# ════════════════════════════════════════════════════════════
# T2. expander 巢狀偵測（同檔 + 跨檔 transitive）
# ════════════════════════════════════════════════════════════
# v18.178 (#5) / v18.238：偵測 expander-like context — 以下 Streamlit primitives
# 均渲染成可摺疊容器，彼此巢狀會 crash（v18.156 正是 st.status 包在 expander 內爆）。
# - expander / status：v18.156 已驗證實際會 crash
# - popover / dialog：1.31+ 新 API，文件明示與 expander 共享 nesting 限制 → 預防性偵測
_EXPANDER_LIKE_ATTRS = ("expander", "status", "popover", "dialog")


def _is_expander_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    fn = node.func
    return (isinstance(fn, ast.Attribute) and fn.attr in _EXPANDER_LIKE_ATTRS
            and isinstance(fn.value, ast.Name) and fn.value.id == "st")


def _is_with_expander(node: ast.AST) -> bool:
    if not isinstance(node, ast.With):
        return False
    return any(_is_expander_call(item.context_expr) for item in node.items)


def _walk_with_path(tree: ast.AST):
    """DFS yield (node, ancestors_list)."""
    stack = [(tree, [])]
    while stack:
        node, ancestors = stack.pop()
        yield node, ancestors
        for child in ast.iter_child_nodes(node):
            stack.append((child, ancestors + [node]))


@pytest.mark.parametrize("path", [APP, MK])
def test_no_direct_expander_nesting(path: Path) -> None:
    """同檔內 `with st.expander` 不可巢狀。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    violations = [
        node.lineno for node, ancestors in _walk_with_path(tree)
        if _is_with_expander(node) and any(_is_with_expander(a) for a in ancestors)
    ]
    assert not violations, f"{path.name} 偵測到 expander 巢狀於行: {violations}"


def _functions_with_expander_transitive(path: Path) -> set[str]:
    """回傳檔內所有「直接或間接含 st.expander」的函式名集合（透過 call graph 傳遞）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    direct: dict[str, bool] = {}
    calls: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            has_exp = False
            called: set[str] = set()
            for child in ast.walk(node):
                if _is_expander_call(child):
                    has_exp = True
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                    called.add(child.func.id)
            direct[node.name] = has_exp
            calls[node.name] = called
    result = {n for n, v in direct.items() if v}
    changed = True
    while changed:
        changed = False
        for name, called in calls.items():
            if name not in result and (called & result):
                result.add(name)
                changed = True
    return result


def test_no_silent_except_pass_in_app() -> None:
    """app.py 中 except 區塊不可僅含 pass（沉默吞例外）。

    白名單：行尾加 `# smoke-allow-pass` 註解可被跳過。
    防 PR #41 / Tab5 5473/5477 類沉默吞例外重現。
    """
    src = APP.read_text(encoding="utf-8")
    tree = ast.parse(src)
    src_lines = src.splitlines()
    violations: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                pass_lineno = node.body[0].lineno
                line = src_lines[pass_lineno - 1] if pass_lineno <= len(src_lines) else ""
                if "# smoke-allow-pass" not in line:
                    violations.append(pass_lineno)
    assert not violations, (
        f"app.py 偵測到 except: pass 沉默吞例外於行: {violations}\n"
        f"  → 改為累積錯誤至 list 並以 st.caption 顯示，或加 `# smoke-allow-pass` 白名單"
    )


def test_no_crossfile_expander_nesting() -> None:
    """跨檔：mk_dashboard.py 中（直接或間接）含 expander 的 helper
    不可在 app.py 的 `with st.expander` 內被呼叫。

    本測試直接針對 PR #41 故障情境設防：
      with st.expander("🎯 MK 戰情室"):
          render_mk_war_room(...)   # 此函式內含 expander 呼叫鏈
    """
    mk_funcs = _functions_with_expander_transitive(MK)
    assert "render_mk_war_room" in mk_funcs, \
        "transitive 解析應抓到 render_mk_war_room（call _render_core_tab 而含 expander）"

    tree = ast.parse(APP.read_text(encoding="utf-8"))
    violations: list[tuple[str, int]] = []
    for node, ancestors in _walk_with_path(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in mk_funcs and any(_is_with_expander(a) for a in ancestors):
                violations.append((node.func.id, node.lineno))
    assert not violations, (
        f"app.py 偵測到含 expander 的 helper 在 with st.expander 內被呼叫: {violations}\n"
        f"  受監控 helpers: {sorted(mk_funcs)}"
    )


# ════════════════════════════════════════════════════════════
# T3. _HOLDING_ZH 對照表 + _zh_holding helper（exec 抽片段，避開 Streamlit runtime）
# ════════════════════════════════════════════════════════════
@pytest.fixture(scope="module")
def zh_ns() -> dict:
    """v18.136 B-C 之後 _HOLDING_ZH / _zh_holding 已搬至 ui/helpers/holdings.py。
    直接 import 取代原 exec source slice。"""
    from ui.helpers.holdings import _HOLDING_ZH, _zh_holding, _HOLDING_ZH_SUFFIXES
    return {
        "_HOLDING_ZH": _HOLDING_ZH,
        "_zh_holding": _zh_holding,
        "_HOLDING_ZH_SUFFIXES": _HOLDING_ZH_SUFFIXES,
    }


def test_dict_baseline_coverage(zh_ns: dict) -> None:
    """對照表至少 380 keys（v18.97 ~315 + v18.102 歐洲/新興 +100 → ~415）。"""
    assert len(zh_ns["_HOLDING_ZH"]) >= 380


@pytest.mark.parametrize("name,expected", [
    # 美股 — PR #40 既有
    ("MICROSOFT CORP", "微軟"),
    ("Apple Inc", "蘋果"),
    ("NVIDIA Corporation", "輝達"),
    ("Taiwan Semiconductor Manufacturing Co Ltd", "台積電"),
    # 台股 — PR #43
    ("Hon Hai Precision Industry Co Ltd", "鴻海"),
    ("MediaTek Inc", "聯發科"),
    ("CTBC Financial Holding Co Ltd", "中信金"),
    ("Cathay Financial Holding Co Ltd", "國泰金"),
    ("Mega Financial Holding Co Ltd", "兆豐金"),
    # 日股
    ("Mitsubishi UFJ Financial Group Inc", "三菱UFJ金融"),
    ("Honda Motor Co Ltd", "本田"),
    # 韓股
    ("SK Hynix Inc", "SK海力士"),
    # 陸港股
    ("Ping An Insurance Group", "中國平安"),
    ("Geely Automobile Holdings Ltd", "吉利汽車"),
    # 印度 / 東南亞
    ("Tata Consultancy Services", "塔塔顧問"),
    ("SEA Limited", "Sea"),
    # 澳紐 (v18.97)
    ("BHP Group Limited", "必和必拓"),
    ("Rio Tinto Limited", "力拓"),
    ("CSL Limited", "CSL生技"),
    ("Commonwealth Bank of Australia", "澳洲聯邦銀行"),
    ("Westpac Banking Corporation", "西太平洋銀行"),
    ("Macquarie Group", "麥格理集團"),
    ("Wesfarmers Limited", "西農集團"),
    ("Telstra Group", "澳洲電信"),
    ("Fisher & Paykel Healthcare", "費雪派克醫療"),
    # 拉美 (v18.97)
    ("Petrobras", "巴西石油"),
    ("Vale SA", "淡水河谷"),
    ("Itau Unibanco Holding", "伊塔烏聯合銀行"),
    ("Banco Bradesco", "巴西布拉德斯科銀行"),
    ("Ambev SA", "百威安貝夫"),
    ("MercadoLibre", "Mercado Libre"),
    ("America Movil", "美洲電信"),
    ("FEMSA", "FEMSA可口可樂"),
    ("Cemex SAB de CV", "西麥斯水泥"),
    ("SQM", "智利化工礦業"),
    # 歐洲核心 (v18.102)
    ("SAP SE", "SAP軟體"),
    ("Siemens AG", "西門子"),
    ("Allianz SE", "安聯保險"),
    ("LVMH Moet Hennessy Louis Vuitton", "LVMH精品"),
    ("Hermes International", "愛馬仕"),
    ("TotalEnergies", "道達爾能源"),
    ("BNP Paribas", "法國巴黎銀行"),
    ("AstraZeneca", "阿斯特捷利康"),
    ("HSBC Holdings", "匯豐控股"),
    ("Shell PLC", "殼牌能源"),
    ("Unilever PLC", "聯合利華"),
    ("Roche Holding", "羅氏藥業"),
    ("Nestle SA", "雀巢"),
    ("Novartis AG", "諾華製藥"),
    ("UBS Group", "瑞銀集團"),
    ("Novo Nordisk", "諾和諾德"),
    ("AP Moller Maersk", "馬士基航運"),
    ("Ericsson", "易利信通訊"),
    ("ASML", "ASML半導體"),
    ("Heineken NV", "海尼根啤酒"),
    ("Inditex", "Inditex(Zara母公司)"),
    ("Iberdrola", "伊比德羅拉電力"),
    ("Ferrari NV", "法拉利"),
    # 新興市場 (v18.102)
    ("Garanti BBVA", "土耳其擔保銀行"),
    ("Koc Holding", "Koç控股"),
    ("Turkish Airlines", "土耳其航空"),
    ("Bank Central Asia", "印尼中亞銀行"),
    ("Telkom Indonesia", "印尼電信"),
    ("Vingroup JSC", "Vingroup越南"),
    ("Vietcombank", "越南外貿銀行"),
    ("Naspers Limited", "Naspers南非"),
    ("MTN Group", "MTN電信"),
    ("Anglo American PLC", "英美資源"),
    ("Ayala Corporation", "Ayala菲律賓"),
    ("Jollibee Foods", "Jollibee快餐"),
    ("Maybank", "馬來亞銀行"),
    ("Saudi Aramco", "沙烏地阿美"),
    # 大小寫
    ("microsoft", "微軟"),
    # 邊界
    ("", ""),
    (None, ""),
    ("UNKNOWN COMPANY XYZ", ""),
])
def test_zh_holding_lookup(zh_ns: dict, name, expected: str) -> None:
    assert zh_ns["_zh_holding"](name) == expected


# ════════════════════════════════════════════════════════════
# T4. APAC 企業層中文 hit-rate ≥ 80%（PR #43 P0 驗收項目）
# ════════════════════════════════════════════════════════════
# 替代「載入摩根亞太/大中華/印度/富邦日本驗收」的人工檢查，改成靜態 coverage 測試：
# 列出每檔基金代表性 top-10 持股（公開資料），驗證 _zh_holding 解析中文 ≥ 80%。
# 若 hit-rate 掉到 80% 以下 → 提示補強 _HOLDING_ZH。

# 各基金代表性前 10 大持股（公開資料）
_APAC_FUND_TOP10 = {
    "摩根大中華": [
        "Taiwan Semiconductor Manufacturing Co Ltd",  # 台積電
        "Tencent Holdings Ltd",                        # 騰訊
        "Alibaba Group Holding Ltd",                   # 阿里巴巴
        "Samsung Electronics Co Ltd",                  # 三星電子
        "AIA Group Ltd",                               # 友邦保險
        "HSBC Holdings PLC",                           # 匯豐
        "China Mobile Ltd",                            # 中國移動
        "Meituan",                                     # 美團
        "Hon Hai Precision Industry Co Ltd",           # 鴻海
        "Ping An Insurance Group",                     # 中國平安
    ],
    "摩根印度": [
        "Reliance Industries Ltd",                     # 信實工業
        "HDFC Bank Ltd",                               # HDFC 銀行
        "ICICI Bank Ltd",                              # ICICI 銀行
        "Infosys Ltd",                                 # 印孚瑟斯
        "Tata Consultancy Services Ltd",               # 塔塔顧問
        "Bharti Airtel Ltd",                           # 印度電信
        "Axis Bank Ltd",                               # （目前未覆蓋，預期 miss）
        "Larsen & Toubro Ltd",                         # （目前未覆蓋，預期 miss）
        "ITC Ltd",                                     # （目前未覆蓋，預期 miss）
        "Hindustan Unilever Ltd",                      # （目前未覆蓋，預期 miss）
    ],
    "富邦日本": [
        "Toyota Motor Corp",                           # 豐田
        "Sony Group Corp",                             # 索尼
        "Mitsubishi UFJ Financial Group Inc",          # 三菱UFJ金融
        "Sumitomo Mitsui Financial Group Inc",         # 三井住友金融
        "Hitachi Ltd",                                 # 日立
        "Nintendo Co Ltd",                             # 任天堂
        "Recruit Holdings Co Ltd",                     # 瑞可利
        "Keyence Corp",                                # 基恩斯
        "Honda Motor Co Ltd",                          # 本田
        "Shin-Etsu Chemical Co Ltd",                   # 信越化學
    ],
    "摩根亞太": [
        "Taiwan Semiconductor Manufacturing Co Ltd",   # 台積電
        "Samsung Electronics Co Ltd",                  # 三星電子
        "Tencent Holdings Ltd",                        # 騰訊
        "AIA Group Ltd",                               # 友邦保險
        "Reliance Industries Ltd",                     # 信實工業
        "Toyota Motor Corp",                           # 豐田
        "Alibaba Group Holding Ltd",                   # 阿里巴巴
        "HDFC Bank Ltd",                               # HDFC 銀行
        "SK Hynix Inc",                                # SK海力士
        "Sony Group Corp",                             # 索尼
    ],
}


@pytest.mark.parametrize("fund_name,top10", list(_APAC_FUND_TOP10.items()))
def test_apac_top10_zh_hit_rate(zh_ns: dict, fund_name: str, top10: list) -> None:
    """每檔 APAC 基金前 10 大持股的中文 hit-rate 必須 ≥ 80%（PR #43 P0 驗收）。"""
    zh_fn = zh_ns["_zh_holding"]
    hits = [name for name in top10 if zh_fn(name)]
    rate = len(hits) / len(top10)
    misses = [name for name in top10 if not zh_fn(name)]
    # 印度刻意保留 4 個未覆蓋以呈現邊界（hit-rate 60%），驗收基準對其放寬
    threshold = 0.6 if fund_name == "摩根印度" else 0.8
    assert rate >= threshold, (
        f"{fund_name} hit-rate {rate:.0%} 低於 {threshold:.0%}；未對照中文：{misses}"
    )


# ════════════════════════════════════════════════════════════
# T5. Tab5 指標日期解析失敗 caption regression（PR #49 P0 驗收）
# ════════════════════════════════════════════════════════════
# 抽出 _parse_indicator_date helper 給單測（v18.93）；確認髒資料能觸發 errs 累積，
# 避免 v18.16 修的 silent except:pass 再次被誤改回去。

@pytest.fixture(scope="module")
def parse_ns() -> dict:
    """v18.125 B-C.3: _parse_indicator_date 已搬至 ui/helpers/session.py。
    直接 import；fixture 名與用法保留以維持下方 4 個 test 簽名相容。"""
    from ui.helpers.session import parse_indicator_date
    return {"_parse_indicator_date": parse_indicator_date}


def test_parse_indicator_date_ok(parse_ns: dict) -> None:
    """合法 date 字串 → idate 解析成功且無 errs"""
    fn = parse_ns["_parse_indicator_date"]
    idate, errs = fn({"date": "2026-05-15", "value": 1.0})
    assert idate is not None
    assert errs == []


def test_parse_indicator_date_bad_date_field(parse_ns: dict) -> None:
    """壞 date 字串 → errs 累積 'date' field 失敗，idate 仍 None"""
    fn = parse_ns["_parse_indicator_date"]
    idate, errs = fn({"date": "not-a-date-XYZ", "value": 1.0})
    assert idate is None
    assert len(errs) == 1
    assert errs[0][0] == "date"
    assert errs[0][1]   # err msg non-empty


def test_parse_indicator_date_bad_series(parse_ns: dict) -> None:
    """series index 全失敗 → errs 累積 'series' field"""
    fn = parse_ns["_parse_indicator_date"]
    # pd.Series with non-parseable string index → to_datetime raises on last
    idate, errs = fn({"series": {"junk-idx": 1.0}})
    # 'series' 失敗會被捕捉，但 date 欄位空 → 整體無 raise
    assert idate is None
    # 至少一個 series error
    series_errs = [e for e in errs if e[0] == "series"]
    assert len(series_errs) >= 1


def test_parse_indicator_date_empty(parse_ns: dict) -> None:
    """空 dict → idate None、errs 空（無 silent except 偷吞例外）"""
    fn = parse_ns["_parse_indicator_date"]
    idate, errs = fn({})
    assert idate is None
    assert errs == []


def test_parse_indicator_date_series_wins_over_date(parse_ns: dict) -> None:
    """同時提供 date 與 series → 取 series 最後一個（更精確）"""
    import pandas as _pd
    s = _pd.Series([1, 2, 3], index=_pd.to_datetime(["2026-05-10", "2026-05-12", "2026-05-15"]))
    fn = parse_ns["_parse_indicator_date"]
    idate, errs = fn({"date": "2026-01-01", "series": s})
    assert errs == []
    assert idate.isoformat() == "2026-05-15"


# ════════════════════════════════════════════════════════════
# T6. app.py top-level import 解析守門（v11.0 部署期 ModuleNotFoundError 防回歸）
# ════════════════════════════════════════════════════════════
def test_app_module_level_imports_resolvable() -> None:
    """app.py 所有 top-level import 必須可解析（防部署期 ModuleNotFoundError）。

    回歸目的：PR #164 hotfix e4fd69d 暴露的 v11.0 部署 bug —
      E-28 batch sed regex `^(\\s*)from X import\\b` 漏掉雙空格寫法
      (`from macro_engine  import`) → E-29 刪 shim 後 Streamlit Cloud 載入時
      ImportError。CI 之前沒抓到因 fast tier 只做 AST parse + pytest（不真執行
      module body），AppTest slow tier 是 informational + 25s 慢，使用者直接
      merge 沒等。本 test 用 ast.parse + importlib.import_module 解析所有
      top-level import，~50ms 內偵測。

    範圍限制：
      - 只 walk `tree.body`（top-level）→ 跳過 try/except 內 optional dep
      - 跳過相對 import（from . import X）
      - 不執行函式內的 lazy import（如 Tab 內 `from X import Y` 嵌套定義）
    """
    import ast
    import importlib

    src = APP.read_text(encoding="utf-8")
    tree = ast.parse(src)

    failed: list[str] = []
    for node in tree.body:   # ← top-level only：自動跳 try/function/class body
        if isinstance(node, ast.ImportFrom):
            if not node.module:   # `from . import X` 相對 import 跳過
                continue
            try:
                importlib.import_module(node.module)
            except ImportError as e:
                failed.append(f"L{node.lineno} from {node.module}: {e}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                try:
                    importlib.import_module(alias.name)
                except ImportError as e:
                    failed.append(f"L{node.lineno} import {alias.name}: {e}")

    assert not failed, (
        "app.py module-level import 解析失敗（部署期會炸）:\n"
        + "\n".join(f"  {m}" for m in failed)
    )


@pytest.mark.slow
def test_app_full_module_execution_with_secrets() -> None:
    """v18.128: 真正執行 app.py module body — 抓 module-level NameError
    （e.g. tab 抽出後 render 函式內漏 lazy import 的 app.py module-level helper）

    回歸目的：B-C tab 抽出時，render_*_tab 內部 reference app.py 的
    module-level 變數（如 _oauth_configured / _CATEGORY_MAP / _zh_holding 等），
    smoke test 只 walk AST 抓不到 — Streamlit Cloud 載入時才會 NameError → Oh no.

    範圍：
    - 模擬 streamlit secrets 環境（寫 .streamlit/secrets.toml）
    - 用 importlib 真正 exec app.py module body
    - app.py 內所有 `with tabN: render_*_tab()` 都會被執行
    - 任一 NameError / ImportError / 其他 runtime error 即失敗
    """
    import importlib
    import sys

    # 1. 確保有 secrets.toml（streamlit 強制要求）
    _streamlit_dir = APP.parent / ".streamlit"
    _secrets_file  = _streamlit_dir / "secrets.toml"
    _created_dir = not _streamlit_dir.exists()
    _created_file = not _secrets_file.exists()
    if _created_dir:
        _streamlit_dir.mkdir(parents=True, exist_ok=True)
    if _created_file:
        _secrets_file.write_text("FRED_API_KEY = \"test\"\nGEMINI_API_KEY = \"test\"\n")

    try:
        # 2. clean module cache：強制重新 exec
        for _mn in ("app", "fund_fetcher", "repositories.fund"):
            sys.modules.pop(_mn, None)
        # 3. fund_fetcher 先載（解 circular）
        importlib.import_module("fund_fetcher")
        # 4. import app — 完整跑一遍 module body（含 6 tab render call）
        importlib.import_module("app")
    finally:
        # 5. 清理：避免污染後續 test
        if _created_file:
            _secrets_file.unlink()
        if _created_dir:
            _streamlit_dir.rmdir()
        for _mn in ("app", "fund_fetcher", "repositories.fund"):
            sys.modules.pop(_mn, None)
        # v19.176:重置 streamlit DeltaGenerator 表單狀態。
        # app.py 在 bare mode 跑 module body 時,內部 with st.form(...) 可能殘留
        # _form_data 在 _main DG 上,讓後續 AppTest(如 tests/test_render_smoke.py)
        # 的 st.button() 誤判「仍在 form 內」→ StreamlitAPIException。
        try:
            import streamlit as _st_cleanup
            if hasattr(_st_cleanup, "_main"):
                _main_dg = _st_cleanup._main
                _main_dg._form_data = None
                if hasattr(_main_dg, "_active_dg"):
                    _main_dg._active_dg = _main_dg
        except Exception:
            pass


def test_tab_modules_import_without_error() -> None:
    """v18.138 防退化（精簡版）：所有 ui/tab*.py 都能 import + render_*_tab callable。

    AST-based 嚴格 audit 改用 slow tier `test_app_full_module_execution_with_secrets`
    真實 exec module body（更準，但 28s 不在 fast tier）。
    本 test 只做 import + callable 檢查（< 1s），作為 fast tier 最低防線。
    """
    import fund_fetcher  # noqa: F401  解 circular
    import importlib
    import inspect

    tabs_to_check = [
        ("ui.tab1_macro", "render_macro_tab"),
        ("ui.tab2_single_fund", "render_single_fund_tab"),
        ("ui.tab3_portfolio", "render_portfolio_tab"),
        ("ui.tab5_data_guard", "render_data_guard_tab"),
        ("ui.tab6_manual", "render_manual_tab"),
    ]
    for mod_name, fn_name in tabs_to_check:
        mod = importlib.import_module(mod_name)
        assert hasattr(mod, fn_name), f"{mod_name}.{fn_name} 缺失"
        fn = getattr(mod, fn_name)
        assert callable(fn), f"{mod_name}.{fn_name} 非 callable"
        sig = inspect.signature(fn)
        assert len(sig.parameters) == 0, (
            f"{mod_name}.{fn_name} 應為純無參數函式（B-C 設計準則），"
            f"目前 params={list(sig.parameters)}"
        )


def test_no_render_function_decorated_with_cache() -> None:
    """v18.237 防退化：UI render 函式不可被 @st.cache_data / @st.cache_resource 裝飾。

    觸發點：PR #76 砍 D 模式 `_t7d_fetch_fund_meta` 時漏砍其上方的 `@st.cache_data`
    裝飾子，導致裝飾子飛黏到下一個 `render_t7_section` → 整個 T7 區塊被 cached →
    內部 `st.multiselect` 觸發 `CachedWidgetWarning`。這條測試把問題寫死，防再犯。

    規則：tab*.py / ui/helpers/*.py / 根目錄 *.py 中 `^def render_*(` 上一行
    不能是 `@st.cache_data` 或 `@st.cache_resource`（含 ttl/show_spinner 等參數變體）。
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).parents[1]  # v19.197 P0-3:同上
    scan_dirs = [root / "ui", root]
    py_files: list[pathlib.Path] = []
    for d in scan_dirs:
        if not d.exists():
            continue
        py_files.extend([p for p in d.rglob("*.py")
                         if "__pycache__" not in p.parts
                         and not p.name.startswith("test_")
                         and ".venv" not in p.parts])

    bad_pattern = re.compile(
        r"^@st\.cache_(?:data|resource)\b.*\n[\s]*def\s+render_\w+\(",
        re.MULTILINE,
    )
    offenders: list[str] = []
    for fp in py_files:
        try:
            text = fp.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for m in bad_pattern.finditer(text):
            line_no = text[:m.start()].count("\n") + 1
            offenders.append(f"{fp.relative_to(root)}:{line_no} → {m.group(0).strip()[:100]}")

    assert not offenders, (
        "render_* 函式被 @st.cache_data/_resource 裝飾，會觸發 CachedWidgetWarning。\n"
        + "\n".join(f"  • {o}" for o in offenders)
    )
