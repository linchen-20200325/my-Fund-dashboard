"""tests/test_help_plain_language.py — 健診 / 批次「給使用者看的字」不得外洩內部術語。

user 原則:「多做說明 —— 讓完全不懂總經與基金的人也看得懂」。
稽核發現白話化在 Tab① 做得很好,但在**健診 / 批次大表的 `column_config.help`**
完全沒做 —— 而 help 正是資訊量最高、新手最需要的地方,卻塞滿內部代號
(憲法章節號 / 內部版號 / 函式名 / 外站頁面代號)。

本檔守四件事(每條註明「修正前是哪一種紅」):

1. **help 白話化**(`columns.py` 的 column_config)—— 掃**執行期產生的 help 字串**,
   不是原始碼,所以開發者註解照樣可以寫技術細節。
   → 修正前:**舊行為衝突紅**(help 內含章節號 / 版號 / 頁面代號 / 內部欄位名)。
2. **UI 說明文白話化**(`tab_batch_analysis.py` / `tab_fund_grp_health.py`)——
   走 AST 只掃「非 docstring 的字串常數」(= 真正會出現在畫面上的字),
   docstring 與 `#` 註解不掃。
   → 修正前:**舊行為衝突紅**(批次欄位說明含章節號、大表 caption 含頁面代號)。
3. **help 裡的門檻數字必須從 SSOT 讀**(不得寫死)。
   → 修正前:**舊行為衝突紅**(「基期」欄 help 手打 σ 切點;批次說明手打「各 ≥ 3」)。
4. **基準序列快取有 TTL**,且 TTL 走 `shared/ttls.py` 既有語意常數。
   → 修正前:**舊行為衝突紅**(`_BENCH_CACHE` 為無 TTL 的 module dict,
     第二次呼叫永遠回第一次抓到的序列,不論隔了多久)。

另加一條 column_config 覆蓋率(B9)與一條「 3-3-3 欄設定不得是 0 consumer」(B8)。

⚠️ 維護提醒:本檔的 `_FORBIDDEN` 清單是**字面值**,production 端要避開的正是這些字。
若哪天某個詞真的必須出現在畫面上,請連同理由一起改這裡,不要在 production 端繞過。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parent.parent

# (要禁的字, 為什麼禁)—— 使用者不可能懂的內部術語
_FORBIDDEN: list[tuple[str, str]] = [
    ("§", "資料憲法章節號,使用者不可能知道那是什麼"),
    ("v19.", "內部版號"),
    ("wb0", "MoneyDJ 的網頁代號(wb01 / wb05 / wb07),應寫成『官方績效表 / 官方風險表』"),
    ("SSOT", "內部術語(單一權威來源)"),
    ("risk_metric_meta", "內部欄位名"),
    ("calc_metrics", "內部函式名"),
    ("pos_label", "內部欄位名"),
    ("div_freq_n", "內部欄位名"),
    ("process_one_fund", "內部函式名"),
    ("_UNIFIED_FRONT", "內部常數名"),
    ("ret_1y_total", "內部欄位名"),
    ("local_calc", "內部來源代號"),
]

# 掃 AST 的 UI 檔(只掃「非 docstring 字串常數」= 真的會印到畫面上的字)
_UI_FILES = [
    Path("ui") / "tab_batch_analysis.py",
    Path("ui") / "tab_fund_grp_health.py",
]


# ── helper ────────────────────────────────────────────────────────────


def _all_column_configs() -> dict:
    """{來源函式名: column_config dict} —— 逐份掃,避免 unified 合併時後者蓋掉前者。"""
    from ui.helpers.fund_grp_health import columns as C
    return {
        "base": C.base_column_config(),
        "health": C.health_column_config(),
        "dividend": C.dividend_column_config(),
        "extra": C.extra_column_config(),
        "batch": C.batch_column_config(),
    }


def _help_strict(spec) -> str:
    """只走「正規」路徑取 help(dict key / 屬性)。取不到回空字串 —— 供 liveness 檢查用。"""
    if isinstance(spec, dict):
        return str(spec.get("help") or "")
    _h = getattr(spec, "help", None)
    if isinstance(_h, str):
        return _h
    _d = getattr(spec, "__dict__", None)
    if isinstance(_d, dict) and isinstance(_d.get("help"), str):
        return _d["help"]
    return ""


def _help_of(spec) -> str:
    """給掃描用:正規路徑取不到就整包字串化。

    **寧可多掃、不可空轉** —— streamlit 未來換掉 column_config 的形狀時,
    這裡若回空字串,白話化測試會變成永遠通過的假綠(PROCESS §4)。
    """
    return _help_strict(spec) or str(spec)


def _non_docstring_strings(path: Path) -> list[tuple[int, str]]:
    """該檔所有「非 docstring」的字串常數 (行號, 內容)。

    f-string 會被拆成多個 `ast.Constant`,literal 片段照樣掃得到。
    `#` 註解不在 AST 裡 → 天生不掃(開發者註解可自由寫技術細節)。
    """
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    _doc_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                _doc_ids.add(id(body[0].value))
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in _doc_ids):
            out.append((getattr(node, "lineno", -1), node.value))
    return out


def _dataframe_calls_without_column_config(path: Path) -> list[int]:
    """該檔 `st.dataframe(...)` 沒帶 `column_config=` 的行號。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        n.lineno for n in ast.walk(tree)
        if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "dataframe"
        and not any(k.arg == "column_config" for k in n.keywords)
    ]


# ── 1. column_config.help 不得含內部術語 ──────────────────────────────


def test_column_help_is_plain_language():
    """健診 / 批次大表每一欄的 help 都不得出現內部術語。

    修正前:**舊行為衝突紅** —— `SSOT v19.177` / `wb07` / `risk_metric_meta` /
    `calc_metrics` / `pos_label` / `metrics.div_freq_n` / `§1`『§2.2 血緣』
    『§4.1 跨幣別可追溯』全都直接印在 tooltip 上。
    """
    _bad: list[str] = []
    for _src_name, _cfg in _all_column_configs().items():
        for _col, _spec in _cfg.items():
            _help = _help_of(_spec)
            for _term, _why in _FORBIDDEN:
                if _term in _help:
                    _bad.append(f"{_src_name}/「{_col}」 含「{_term}」({_why})")
    assert not _bad, "以下欄位 help 仍有內部術語:\n" + "\n".join(_bad)


def test_column_help_extraction_is_not_vacuous():
    """守本檔自己:確認掃描器真的讀到 help 內容,不是掃到空字串在空轉。

    修正前:N/A(這是防自己空轉的 liveness 檢查,見 PROCESS §4「測試自身的可執行性」)。
    """
    _cfgs = _all_column_configs()
    # 兩個已知 help 片段:抽不到就代表掃描器讀錯地方
    assert "重試" in _help_of(_cfgs["batch"]["備註"])
    assert "百分點" in _help_of(_cfgs["health"]["vs 大盤%"])
    _n = sum(1 for _cfg in _cfgs.values()
             for _spec in _cfg.values() if _help_strict(_spec).strip())
    assert _n >= 30, (
        f"正規路徑只抽到 {_n} 個非空 help —— column_config 形狀可能變了,"
        "`_help_strict` 需要更新(掃描本身有 str() 後備不會漏,但請把正規路徑修回來)。")


# ── 2. UI 說明文(非 docstring 字串)不得含內部術語 ────────────────────


@pytest.mark.parametrize("rel", _UI_FILES, ids=lambda p: p.name)
def test_ui_visible_strings_are_plain_language(rel: Path):
    """畫面上的 caption / markdown / help 不得出現內部術語(docstring 與註解不掃)。

    修正前:**舊行為衝突紅** —— 批次「欄位說明」expander 寫『(§4.1)』、
    健診大表 caption 寫『MoneyDJ wb05 官方數值』與『部分檔只有 wb07 6M』、
    逐檔配息明細的兩個 help 寫『§4.1 用當期匯率』『§2.2 血緣』。
    """
    _path = _ROOT / rel
    _strings = _non_docstring_strings(_path)
    assert len(_strings) > 30, (
        f"{rel} 只掃到 {len(_strings)} 個字串常數 —— AST 走法可能失效(檔案結構大改?),"
        "本條會空轉,請先修測試。")
    _bad = [
        f"{rel}:{_ln} 含「{_term}」({_why}):{_s[:60]}"
        for _ln, _s in _strings
        for _term, _why in _FORBIDDEN
        if _term in _s
    ]
    assert not _bad, "以下畫面文字仍有內部術語:\n" + "\n".join(_bad)


# ── 3. help / 說明文的門檻數字必須從 SSOT 讀 ──────────────────────────


def test_base_period_help_reads_sigma_from_ssot():
    """「基期」欄 help 的 σ 切點必須是 SSOT 值,不是手打的。

    修正前:**舊行為衝突紅** —— help 手打 `σ ≥ −0.5` / `σ ≤ −1.5`,
    改 `shared/signal_thresholds.py` 時畫面文案不會跟著動(說明與行為脫節)。
    """
    from shared.signal_thresholds import ROTATION_BUY_SIGMA, ROTATION_SELL_SIGMA
    _help = _help_of(_all_column_configs()["health"]["基期"])
    assert f"{ROTATION_SELL_SIGMA:+.1f}" in _help, "高基期切點未從 SSOT 讀"
    assert f"{ROTATION_BUY_SIGMA:+.1f}" in _help, "低基期切點未從 SSOT 讀"


def test_grade_help_reads_cutoffs_from_ssot():
    """4D 等第 help 的分數切點必須是 SSOT 值(順帶確認版號已從 help 拿掉)。

    修正前:**舊行為衝突紅** —— help 為 `A≥80 / … / F<35(SSOT v19.177)`,
    數字寫死 + 印出內部版號。
    """
    from shared.signal_thresholds import GRADE_CUTOFFS_4D
    _help = _help_of(_all_column_configs()["health"]["4D Grade"])
    for _cut in GRADE_CUTOFFS_4D:
        assert str(_cut) in _help, f"4D 等第 help 缺 SSOT 切點 {_cut}"


def test_capture_help_reads_min_months_from_ssot():
    """捕捉率 help 的最少月數必須是 SSOT 值。

    修正前:**綠**(`columns.py` 早已從 SSOT 讀)—— 本條是防回退的鎖。
    """
    from shared.signal_thresholds import CAPTURE_MIN_MONTHS, CAPTURE_ROBUST_MONTHS
    _help = _help_of(_all_column_configs()["health"]["捕捉樣本"])
    assert str(CAPTURE_MIN_MONTHS) in _help and str(CAPTURE_ROBUST_MONTHS) in _help


def test_batch_field_notes_read_thresholds_from_ssot():
    """批次分頁「欄位說明」的門檻數字必須從 SSOT 讀,不得手打。

    修正前:**舊行為衝突紅** —— 該段 markdown 手打「需**漲、跌月各 ≥ 3**」
    與「σ≥−0.5 / σ≤−1.5」,與 `shared/signal_thresholds.py` 各走各的。
    """
    _src = (_ROOT / "ui" / "tab_batch_analysis.py").read_text(encoding="utf-8")
    assert "from shared.signal_thresholds import" in _src, "批次分頁未 import 門檻 SSOT"
    assert "ROTATION_BUY_SIGMA" in _src and "ROTATION_SELL_SIGMA" in _src
    assert "CAPTURE_MIN_MONTHS" in _src
    # 舊的手打字面值不得殘留
    assert "各 ≥ 3" not in _src
    assert "σ≥−0.5" not in _src
    assert "σ≤−1.5" not in _src


def test_rotation_sliders_default_to_ssot():
    """輪動配對的三個滑桿**預設值**走 SSOT,UI 不另外持有一組門檻數字。

    修正前:**舊行為衝突紅** —— slider 預設寫死 `-0.5` / `-1.5` / `50`。
    """
    _src = (_ROOT / "ui" / "helpers" / "fund_grp_health" / "rotation.py").read_text(
        encoding="utf-8")
    assert "from shared.signal_thresholds import" in _src
    assert "ROTATION_SELL_SIGMA, 0.1" in _src, "高基期滑桿預設未走 SSOT"
    assert "ROTATION_BUY_SIGMA, 0.1" in _src, "低基期滑桿預設未走 SSOT"
    assert "int(ROTATION_BUY_MIN_SCORE)" in _src, "操盤評分滑桿預設未走 SSOT"


# ── 4. 基準序列快取 TTL(B5)────────────────────────────────────────────


def _fake_bench(n: int = 3):
    return pd.Series([10.0, 11.0, 12.0][:n],
                     index=pd.date_range("2026-01-01", periods=n, freq="D"))


def test_bench_cache_ttl_is_a_shared_semantic_constant():
    """TTL 必須是 `shared/ttls.py` 的既有語意常數,不得新造數字。

    修正前:**ImportError 類紅**(`_BENCH_TTL_SEC` 這個名字根本不存在 → AttributeError)。
    """
    import ui.helpers.fund_grp_health.capture as C
    from shared import ttls
    _allowed = {ttls.TTL_5MIN, ttls.TTL_10MIN, ttls.TTL_15MIN,
                ttls.TTL_30MIN, ttls.TTL_1HOUR}
    assert C._BENCH_TTL_SEC in _allowed, (
        f"_BENCH_TTL_SEC={C._BENCH_TTL_SEC} 不在 shared/ttls.py 的語意常數裡 —— "
        "TTL 不得自己造數字")


def test_bench_cache_reuses_within_ttl_and_refetches_after(monkeypatch):
    """TTL 內共用同一次抓取(400 檔批次只抓一次);TTL 過期後重抓。

    修正前:**舊行為衝突紅** —— 舊版快取值是**裸 Series**(不是 `(時間, Series)`),
    `_ts, _s = _BENCH_CACHE["SPX"]` 會先解包失敗;即使繞過解包,
    無 TTL 也不會重抓(`len(_calls) == 2` 停在 1)。
    """
    import services.crisis_backtest as CB
    import ui.helpers.fund_grp_health.capture as C

    _calls: list = []

    def _fake(market, years=10):
        _calls.append(market)
        return _fake_bench()

    monkeypatch.setattr(CB, "fetch_market_series", _fake)
    C._BENCH_CACHE.clear()

    assert len(C._benchmark_nav("SPX")) == 3
    assert len(C._benchmark_nav("SPX")) == 3
    assert len(_calls) == 1, "TTL 內不該重抓(N 檔 fan-out 要收斂成一次)"

    # 把「抓到的時間」往回撥超過 TTL → 下一次必須重抓
    _ts, _s = C._BENCH_CACHE["SPX"]
    C._BENCH_CACHE["SPX"] = (_ts - C._BENCH_TTL_SEC - 1, _s)
    assert len(C._benchmark_nav("SPX")) == 3
    assert len(_calls) == 2, "TTL 過期後未重抓 —— 長跑的 process 會永遠用開站那一條序列"

    C._BENCH_CACHE.clear()


def test_expired_bench_cache_is_not_served_as_fresh(monkeypatch):
    """TTL 過期又抓不到時,**不得**回傳過期序列冒充新鮮值(§2.4 禁止靜默 stale)。

    修正前:**舊行為衝突紅**(舊版快取值是裸 Series → 解包即失敗;
    且無 TTL 時永遠回舊快取,`len(_out) == 0` 也不會成立)。
    """
    import services.crisis_backtest as CB
    import ui.helpers.fund_grp_health.capture as C

    monkeypatch.setattr(CB, "fetch_market_series", lambda market, years=10: _fake_bench())
    C._BENCH_CACHE.clear()
    C._benchmark_nav("TWII")

    _ts, _s = C._BENCH_CACHE["TWII"]
    C._BENCH_CACHE["TWII"] = (_ts - C._BENCH_TTL_SEC - 1, _s)
    monkeypatch.setattr(CB, "fetch_market_series",
                        lambda market, years=10: pd.Series(dtype=float))
    _out = C._benchmark_nav("TWII")
    assert _out is not None and len(_out) == 0, "過期後抓不到,不可回傳舊序列"
    assert "TWII" not in C._BENCH_CACHE, "過期且抓不到的項目應丟掉,讓下次重試"

    C._BENCH_CACHE.clear()


def test_bench_cache_never_caches_failure(monkeypatch):
    """抓失敗不入快取(success-only 語意不得被 TTL 改動破壞)。

    修正前:**綠** —— 防回退鎖。
    """
    import services.crisis_backtest as CB
    import ui.helpers.fund_grp_health.capture as C

    monkeypatch.setattr(CB, "fetch_market_series",
                        lambda market, years=10: pd.Series(dtype=float))
    C._BENCH_CACHE.clear()
    C._benchmark_nav("SPX")
    assert "SPX" not in C._BENCH_CACHE


# ── 5. B9:健診 / 批次區塊的表都要有 column_config ─────────────────────


@pytest.mark.parametrize("rel", [
    Path("ui") / "helpers" / "fund_grp_health" / "rotation.py",
    Path("ui") / "helpers" / "fund_grp_health" / "switch_section.py",
    Path("ui") / "helpers" / "fund_grp_health" / "backtest_section.py",
    Path("ui") / "helpers" / "fund_grp_health" / "switch_advisor_section.py",
], ids=lambda p: p.name)
def test_section_tables_have_column_config(rel: Path):
    """這些區塊的每張 `st.dataframe` 都要帶 column_config(欄寬 + help)。

    修正前:`switch_advisor_section.py` **舊行為衝突紅**(選股池表與換股建議表
    兩處裸 render,6 個欄名零 tooltip);其餘三檔已綠,本條是防回退鎖。
    """
    _bare = _dataframe_calls_without_column_config(_ROOT / rel)
    assert not _bare, f"{rel} 這幾行的 st.dataframe 沒帶 column_config:{_bare}"


# ── 6. B8:「 3-3-3」欄設定不得是 0 consumer ─────────────────────────


def test_mk333_column_config_matches_the_column_the_table_really_has():
    """大表實際欄名是「 3-3-3 篩」;不得同時留一份永遠被濾掉的「 3-3-3」設定。

    背景:`services/health/report.build_health_analysis_row` 產「 3-3-3」,
    但大表欄序常數 `_UNIFIED_FRONT` 登錄的是 `services/fund_row` 那份「 3-3-3 篩」,
    於是 columns.py 裡那份「 3-3-3」column_config 被
    `{k: v for k, v in cfg.items() if k in df.columns}` 永遠濾掉 = 0 consumer。
    產生端**不是**死碼(Tab2 的 metric 卡仍在讀),故只移除死設定,不動資料。

    修正前:**舊行為衝突紅**(cfg 同時有兩個 key)。
    """
    from services.health.report import HEALTH_COLUMNS
    from ui.helpers.fund_grp_health.columns import unified_column_config
    from ui.helpers.fund_grp_health.unified import (
        BATCH_UNIFIED_COLUMNS,
        _UNIFIED_FRONT,
    )

    _cfg = unified_column_config(batch=True)
    _front = [c for c, _ in _UNIFIED_FRONT]

    assert " 3-3-3 篩" in _front and " 3-3-3 篩" in BATCH_UNIFIED_COLUMNS
    assert " 3-3-3" not in _front, "兩份 3-3-3 同時上表會互相打架"
    assert " 3-3-3 篩" in _cfg, "大表真正用的那一欄必須有 column_config"
    assert " 3-3-3" not in _cfg, (
        "columns.py 不該留一份永遠被濾掉的『 3-3-3』設定(0 consumer)")
    # 產生端仍在(Tab2 metric 卡消費),不是死碼 —— 別把它一起刪了
    assert " 3-3-3" in HEALTH_COLUMNS


# ── 7. 「Sharpe 來源」/「1Y 來源」兩欄的**值本身**也要白話 ─────────────────
#
# 上一輪把這兩欄的 `help` 白話化了,但**格子裡印的字**還是內部代號
# (外站頁面代號 / 內部欄位名 / 內部版號)。help 要 hover 才看得到,值是**直接印在
# 表上**的 —— 白話化只做 help 等於把最顯眼的那一半漏掉。
#
# ⚠️ 本組一律走 **runtime 產出值**,不掃原始碼:這兩個模組的註解與 docstring 本來
#    就會寫出頁面代號與內部欄位名(那是給維護者看的,`_FORBIDDEN` 的設計前提也是
#    「只管使用者看得到的字」)。掃原始碼會把註解一起判紅,逼人把維護資訊刪掉。

_VALUE_FORBIDDEN: list[tuple[str, str]] = _FORBIDDEN + [
    ("v18.", "內部版號"),
    ("perf[", "內部欄位名"),
]


def _sharpe_source_values() -> list[str]:
    """「Sharpe 來源」欄四種分支的實際產出值。"""
    from ui.helpers.fund_grp_health.unified import sharpe_provenance_by_code

    def _f(code, meta):
        return {"code": code, "metrics": {"risk_metric_meta": {"sharpe": meta}}}

    _out = sharpe_provenance_by_code([
        _f("A", {"source": "wb07_1y", "period_days": None}),
        _f("B", {"source": "wb07_6m", "period_days": None}),
        _f("C", {"source": "self_calc", "period_days": 250}),
        _f("D", {"source": None, "period_days": None}),
    ])
    return [_v["Sharpe 來源"] for _v in _out.values()]


def _one_year_source_values() -> list[str]:
    """「1Y 來源」欄全部 fallback 分支的實際產出值(含 NAV 序列外推那條)。"""
    from services.fund_total_return import compute_1y_total_return

    _idx = pd.date_range("2024-01-01", "2025-01-01", freq="D")
    _series = pd.Series([100.0] * (len(_idx) - 1) + [110.0], index=_idx)
    _cases = [
        {"moneydj_raw": {"perf": {"1Y": 9.0}}, "perf_source": "wb01"},
        {"moneydj_raw": {"perf": {"1Y": 9.0}}, "perf_source": "local_calc"},
        {"moneydj_raw": {"perf": {"1Y": 9.0}}},                 # 來源未標註
        {"moneydj_raw": {}, "metrics": {"ret_1y_total": 5.0}},  # 自算含息(足年)
        {"moneydj_raw": {}, "metrics": {"ret_1y_total": 5.0,
                                        "ret_1y_window_days": 90}},   # 短窗
        {"moneydj_raw": {}, "metrics": {"ret_1y": 3.0}},        # 純淨值
        {"moneydj_raw": {}, "metrics": {}, "series": _series},  # 外推年化
        {"moneydj_raw": {}, "metrics": {}},                     # 全缺
    ]
    return [compute_1y_total_return(_c)[1] for _c in _cases]


def test_source_column_values_are_plain_language():
    """兩個「來源」欄印在格子裡的字不得含內部代號。

    修正前:**舊行為衝突紅** —— 兩欄合計 6 個值帶外站頁面代號 / 內部欄位名 /
    內部版號(Sharpe 兩個、1Y 四個)。
    """
    _vals = _sharpe_source_values() + _one_year_source_values()
    # liveness(PROCESS §4):值真的產出來了才算掃過,否則本條會變成掃空集的假綠
    assert len(set(_vals)) >= 10, (
        f"只產出 {len(set(_vals))} 種來源值 —— fallback 分支可能沒被走到,本條會空轉:{_vals}")

    _bad = [f"「{_v}」含「{_term}」({_why})"
            for _v in _vals
            for _term, _why in _VALUE_FORBIDDEN
            if _term in _v]
    assert not _bad, "以下來源欄的值仍是內部代號:\n" + "\n".join(_bad)


def test_source_column_values_still_separate_official_from_self_calc():
    """§2.2:這兩欄存在的**唯一**理由就是讓人分得出「官方公布值」與「本站自算」。

    白話化不能把這件事洗掉 —— 若哪天有人把文案改成兩者看起來一樣,本條會紅。

    修正前:**綠**(舊值也分得出來)。這是把「改文案不准弄丟血緣」寫成回歸鎖,
    原本沒有任何測試守它。
    """
    _vals = _sharpe_source_values() + _one_year_source_values()
    _official = [_v for _v in _vals if "官方" in _v]
    _self = [_v for _v in _vals if "自算" in _v]

    assert len(_official) >= 3, f"官方來源值不足(Sharpe 1Y/6M + 1Y 官方):{_vals}"
    assert len(_self) >= 4, f"自算來源值不足:{_vals}"
    assert not (set(_official) & set(_self)), (
        f"同一個值同時自稱官方與自算,使用者無從判斷:{set(_official) & set(_self)}")

    # 六個月那條的期間警告不可弄丟(它是跨檔比大小的陷阱)
    _six = [_v for _v in _sharpe_source_values() if "6 個月" in _v]
    assert len(_six) == 1 and "⚠️" in _six[0] and "非 1 年" in _six[0], (
        f"六個月來源必須帶警告記號並明講不是一年:{_six}")

    # 有數字但來源不明時,必須誠實說「不知道」,不得歸進官方(§1)
    from services.fund_total_return import SRC_PERF_UNLABELED
    assert SRC_PERF_UNLABELED in _vals
    assert "官方" not in SRC_PERF_UNLABELED and "未標註" in SRC_PERF_UNLABELED
