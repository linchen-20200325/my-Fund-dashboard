"""兩支 LINE 推播排程不得依賴 UI 層(客戶 2026-10-13 裁示)。

## 裁示原文

「兩支 LINE 推播保留：每週 LINE 換檔推播、每月配息日曆推播。核准把它們目前借用的
`ui/helpers` 必要函式搬到適當共用層。要求：不讓排程依賴 UI；不改推播業務語意；不新增資料來源；
搬移後建立回歸測試；舊 UI 刪除後兩支排程仍可獨立運作。」

## 守什麼(四層,缺一層就有一種退化看不見)

1. **靜態遞移閉包**:從兩支腳本出發,把**所有** import(含函式內 lazy import)一路追到底,
   不得碰到 `ui` / `ui_v2` / `app`。只看腳本第一層不夠 —— 原本的依賴正是藏在
   `ui.helpers.fund_grp_health.unified` → `.signals` → `ui.helpers.macro_helpers` 這種第三、四層。
2. **搬出去的模組本身**不得 import `streamlit` / `ui.*`,也不得 import L2 禁用的網路套件(§8.2)。
3. **執行期**:在子行程裡讓 `import ui…`(以及 `streamlit`)**直接失敗**,兩支腳本照樣能從
   讀代碼一路跑到推播組裝(網路與 LINE 全 stub)—— 這就是「舊 UI 刪除後仍可獨立運作」的模擬。
   用子行程是因為本測試行程早已被別的測試載入過 `ui.*`,在同一行程裡擋不乾淨。
4. **SSOT**:舊 UI 路徑拿到的必須是**同一個物件**(不是複製一份),所以舊 UI 既有的行為測試
   同時也在守排程用的那一份。

## 突變(已實跑)

把 `scripts/weekly_switch_notify.py` 任一個 `from services.fund_grp_health…` 改回
`from ui.helpers.fund_grp_health…` → 第 1、3 層轉紅;`dividend_calendar_notify.py` 的
`from scripts.dividend_calendar_png` 改回 `from ui.helpers.dividend_calendar_render` → 同。
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

SCRIPTS = ("scripts/weekly_switch_notify.py", "scripts/dividend_calendar_notify.py")

#: 本次(2026-10-13)由 `ui/helpers` 搬到 L2 的模組。
MOVED_MODULES = (
    "services/fund_calc_currency.py",
    "services/dividend_calendar_render.py",
    "services/fund_grp_health/__init__.py",
    "services/fund_grp_health/_utils.py",
    "services/fund_grp_health/capture.py",
    "services/fund_grp_health/quality.py",
    "services/fund_grp_health/risk.py",
    "services/fund_grp_health/signals.py",
    "services/fund_grp_health/unified.py",
)

#: 搬到編排層(scripts/)的:PNG 產圖要叫 L0 Chromium,L2 白名單不收(見該檔 docstring)。
#: 編排層可以 import infra,但同樣不得碰 UI / streamlit。
MOVED_TO_SCRIPTS = ("scripts/dividend_calendar_png.py",)

_UI_ROOTS = ("ui", "ui_v2", "app")
_L2_FORBIDDEN = ("streamlit", "ui", "ui_v2", "app", "requests", "httpx", "bs4", "feedparser")


def _hits(mod: str, roots) -> bool:
    return any(mod == r or mod.startswith(r + ".") for r in roots)


# ══════════════════════════════════════════════════════════════════
# 1. 靜態遞移閉包(AST;含函式內 import)
# ══════════════════════════════════════════════════════════════════
def _mod_to_path(mod: str, root: Path = ROOT):
    p = root.joinpath(*mod.split("."))
    if (p / "__init__.py").exists():
        return p / "__init__.py"
    if p.with_suffix(".py").exists():
        return p.with_suffix(".py")
    return None


def _path_to_mod(path: Path, root: Path = ROOT) -> str:
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _imports_of(path: Path, root: Path = ROOT) -> list:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    mod = _path_to_mod(path, root)
    pkg = mod if path.name == "__init__.py" else mod.rpartition(".")[0]
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out.extend(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            if n.level:
                base = pkg.split(".")
                if n.level > 1:
                    base = base[: len(base) - (n.level - 1)]
                m = ".".join(base + ([n.module] if n.module else []))
            else:
                m = n.module or ""
            out.append(m)
            out.extend(f"{m}.{a.name}" for a in n.names)   # `from pkg import submodule`
    return out


def _closure(start_files, root: Path = ROOT) -> dict:
    """{repo 模組名: 第一個把它拉進來的模組}(只追 repo 內的模組;第三方套件記名不追)。"""
    seen: dict = {}
    queue = []
    for rel in start_files:
        p = root / rel
        seen[_path_to_mod(p, root)] = None
        queue.append(p)
    while queue:
        p = queue.pop()
        src = _path_to_mod(p, root)
        for m in _imports_of(p, root):
            parts = m.split(".")
            for i in range(1, len(parts) + 1):
                mm = ".".join(parts[:i])
                if mm in seen:
                    continue
                if _hits(mm, _UI_ROOTS):            # 記下來(就算檔案已刪也要抓到)
                    seen[mm] = src
                    continue
                mp = _mod_to_path(mm, root)
                if mp is None:
                    continue
                seen[mm] = src
                queue.append(mp)
    return seen


def _chain(seen: dict, m: str) -> str:
    c = [m]
    while seen.get(c[-1]):
        c.append(seen[c[-1]])
    return " <- ".join(c)


@pytest.mark.parametrize("script", SCRIPTS)
def test_static_transitive_imports_never_reach_ui(script):
    seen = _closure([script])
    bad = sorted(m for m in seen if _hits(m, _UI_ROOTS))
    assert not bad, (f"{script} 的遞移 import 碰到 UI 層(客戶 2026-10-13 裁示:排程不得依賴 UI):\n"
                     + "\n".join(_chain(seen, m) for m in bad))


def test_closure_walker_is_alive(tmp_path):
    """守衛自檢:閉包工具真的追得到**多層、函式內**的 lazy import,也真的抓得到 `ui`。

    否則上一條會因為工具瞎掉而永遠綠。用一個迷你假 repo:腳本(函式內)→ 套件 a(函式內)→ ui。
    """
    (tmp_path / "scripts").mkdir()
    (tmp_path / "pkg").mkdir()
    (tmp_path / "ui" / "helpers").mkdir(parents=True)
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "ui" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "ui" / "helpers" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "ui" / "helpers" / "deep.py").write_text("X = 1\n", encoding="utf-8")
    (tmp_path / "scripts" / "job.py").write_text(
        "def run():\n    from pkg.a import f\n    return f()\n", encoding="utf-8")
    (tmp_path / "pkg" / "a.py").write_text(
        "def f():\n    from ui.helpers.deep import X\n    return X\n", encoding="utf-8")
    seen = _closure(["scripts/job.py"], root=tmp_path)
    assert "ui.helpers.deep" in seen and _chain(seen, "ui.helpers.deep").endswith("scripts.job")
    # 真實 repo:週報 → (函式內)services unified →(函式內)risk,兩層 lazy import 都有追到
    assert "services.fund_grp_health.risk" in _closure([SCRIPTS[0]])


# ══════════════════════════════════════════════════════════════════
# 2. 搬出去的模組:L2 乾淨
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("rel", MOVED_MODULES)
def test_moved_module_has_no_ui_streamlit_or_network_import(rel):
    imps = _imports_of(ROOT / rel)
    bad = sorted({m for m in imps if _hits(m, _L2_FORBIDDEN)})
    assert not bad, f"{rel} 不得 import {bad}(§8.2 L2 + 2026-10-13 裁示)"


@pytest.mark.parametrize("rel", MOVED_TO_SCRIPTS)
def test_moved_script_helper_has_no_ui_or_streamlit_import(rel):
    imps = _imports_of(ROOT / rel)
    bad = sorted({m for m in imps if _hits(m, ("streamlit",) + _UI_ROOTS)})
    assert not bad, f"{rel} 不得 import {bad}(2026-10-13 裁示:排程不得依賴 UI)"


# ══════════════════════════════════════════════════════════════════
# 3. 執行期:擋掉 ui / streamlit 後兩支排程照樣跑完(子行程)
# ══════════════════════════════════════════════════════════════════
_BLOCKER = r'''
import sys
_BLOCK = ("ui", "ui_v2", "app", "streamlit")
class _Block:
    def find_spec(self, name, path=None, target=None):
        if any(name == b or name.startswith(b + ".") for b in _BLOCK):
            raise ImportError("blocked by test (simulating deleted UI): " + name)
        return None
sys.meta_path.insert(0, _Block())
import os
for _k in ("LINE_CHANNEL_TOKEN", "LINE_CHANNEL_ACCESS_TOKEN", "LINE_USER_ID", "WATCH_CSV_URL",
           "GITHUB_TOKEN", "TARGET_MONTH"):
    os.environ.pop(_k, None)
import numpy as np
import pandas as pd
_bidx = pd.date_range("2016-01-01", periods=2600, freq="B")
_BENCH = pd.Series(100 * np.cumprod(1 + 0.0004 * np.sin(np.arange(2600) / 17.0) + 0.0002), index=_bidx)
def _series(seed, n=600, drift=0.0003):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-06-01", periods=n, freq="B")
    return pd.Series(10.0 * np.cumprod(1 + drift + 0.01 * rng.standard_normal(n)), index=idx)
def _divs(day, n=14):
    import datetime as _dt
    y, m, out = 2025, 1, []
    for _ in range(n):
        out.append({"ex_date": _dt.date(y, m, day).isoformat(),
                    "pay_date": _dt.date(y, m, day + 7).isoformat(), "amount": 0.05, "yield_pct": 6.0})
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out
'''

_WEEKLY = _BLOCKER + r'''
import json
import scripts.weekly_switch_notify as W
import services.crisis_backtest as CB
import services.fx_regime_service as FXR
import services.fund_row as FR
import repositories.pool_repository as PR
import infra.line_push as LP
CB.fetch_market_series = lambda market, years=10: _BENCH.copy()
FXR.fx_regime_by_ccy = lambda *a, **k: {}
_RAW = {
    "AAA111": {"fund_name": "甲基金", "series": _series(1), "dividends": _divs(7), "currency": "USD",
               "metrics": {"sharpe": 0.8, "std_1y": 9.5, "max_drawdown": -12.0, "currency": "USD"},
               "risk_metrics": {}},
    "BBB222": {"fund_name": "乙基金", "series": _series(2, drift=-0.0004), "dividends": _divs(14),
               "currency": "USD", "metrics": {"sharpe": -0.3, "std_1y": 14.0, "currency": "USD"},
               "risk_metrics": {}},
}
FR.process_one_fund = lambda code, principal, name_hint="", **k: (
    {"ok": True, "_fund_raw": _RAW[code]} if code in _RAW else {"ok": False, "error": "查無"})
W._load_client_and_sheet = lambda: ("client", "sid")
W._read_holdings = lambda c, s: ["AAA111", "BBB222"]
W._read_watchlist = lambda: []
PR.list_pool = lambda: []
_msgs = []
LP.push_text = lambda msg, dry_run=False: _msgs.append(msg) or {"sent": False, "reason": "dry-run"}
rc = W.main(["--dry-run", "--notify-empty"])
print("RESULT=" + json.dumps({
    "rc": rc, "msgs": _msgs,
    "ui_loaded": sorted(m for m in sys.modules if m in ("ui", "ui_v2", "app") or m.startswith(("ui.", "ui_v2."))),
    "streamlit_loaded": "streamlit" in sys.modules,
}, ensure_ascii=False))
'''

_DIVIDEND = _BLOCKER + r'''
import datetime as _dt
import json
import scripts.weekly_switch_notify as W
import scripts.dividend_calendar_notify as D
import services.moneydj_fetcher as MJ
import infra.html_to_png as H2P
import infra.asset_publish as AP
import infra.line_push as LP
W._load_client_and_sheet = lambda: ("client", "sid")
W._read_holdings = lambda c, s: ["AAA111"]
W._read_watchlist = lambda: ["BBB222"]
MJ.auto_fetch_moneydj = lambda code, *a, **k: {"fund_name": {"AAA111": "摩根甲", "BBB222": "安聯乙"}[code],
                                              "dividends": _divs({"AAA111": 7, "BBB222": 14}[code])}
D._now_tw = lambda: _dt.datetime(2026, 10, 28, 8, 23)
_png_calls = []
H2P.html_to_png = lambda html, **kw: _png_calls.append({"len": len(html), **kw}) or b"\x89PNG-fake"
AP.publish_asset = lambda png, path, message="": "https://example.invalid/" + path
_img = []
LP.push_image = lambda url, caption=None, dry_run=False, **k: _img.append((url, caption)) or {"sent": True, "reason": "ok"}
rc = D.main([])
print("RESULT=" + json.dumps({
    "rc": rc, "png_calls": _png_calls, "img": _img,
    "ui_loaded": sorted(m for m in sys.modules if m in ("ui", "ui_v2", "app") or m.startswith(("ui.", "ui_v2."))),
    "streamlit_loaded": "streamlit" in sys.modules,
}, ensure_ascii=False))
'''


def _run(code: str) -> dict:
    proc = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), capture_output=True,
                          text=True, timeout=300)
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT=")]
    assert proc.returncode == 0 and lines, (
        f"子行程失敗(rc={proc.returncode})\n--- stdout ---\n{proc.stdout[-3000:]}"
        f"\n--- stderr ---\n{proc.stderr[-5000:]}")
    return json.loads(lines[-1][len("RESULT="):])


def test_weekly_switch_push_runs_with_ui_and_streamlit_blocked():
    r = _run(_WEEKLY)
    assert r["rc"] == 0
    assert r["ui_loaded"] == [] and r["streamlit_loaded"] is False
    assert len(r["msgs"]) == 1, "推播組裝必須真的跑到(--notify-empty 一定有一則)"
    msg = r["msgs"][0]
    assert "換股顧問週報" in msg and "甲基金" in msg and "乙基金" in msg


def test_dividend_calendar_push_runs_with_ui_and_streamlit_blocked():
    r = _run(_DIVIDEND)
    assert r["rc"] == 0
    assert r["ui_loaded"] == [] and r["streamlit_loaded"] is False
    # 首選路徑(月曆圖)真的走到:HTML → L0 html_to_png(推播版型)→ 發佈 → push_image
    assert r["png_calls"] and r["png_calls"][0]["selector"] == ".wrap"
    assert r["png_calls"][0]["require_cjk"] is True and r["png_calls"][0]["scale"] == 2
    assert r["img"] and r["img"][0][0].endswith("dividend-calendar/2026-11.png")
    assert "摩根" in (r["img"][0][1] or "") and "安聯" in (r["img"][0][1] or "")


# ══════════════════════════════════════════════════════════════════
# 4. SSOT:舊 UI 路徑 = 同一個物件(不是複製一份)
# ══════════════════════════════════════════════════════════════════
def test_old_ui_paths_resolve_to_the_same_l2_objects():
    import services.dividend_calendar_render as SR
    import services.fund_calc_currency as SC
    import services.fund_grp_health._utils as SU
    import services.fund_grp_health.capture as SCap
    import services.fund_grp_health.quality as SQ
    import services.fund_grp_health.risk as SRisk
    import services.fund_grp_health.unified as SUn
    import ui.helpers.dividend_calendar_render as UR
    import ui.helpers.fund_grp_health._utils as UU
    import ui.helpers.fund_grp_health.capture as UCap
    import ui.helpers.fund_grp_health.quality as UQ
    import ui.helpers.fund_grp_health.risk as URisk
    import ui.helpers.fund_grp_health.unified as UUn
    import ui.helpers.portfolio.load as UL

    # 整檔搬移者:舊路徑就是同一個模組(monkeypatch 任一邊,兩邊都看得到)
    assert UR is SR and UU is SU and UCap is SCap and UQ is SQ
    # 部分搬移者:資料函式是同一個物件
    assert URisk.hwm_sigma_by_code is SRisk.hwm_sigma_by_code
    assert URisk.risk_compare_by_code is SRisk.risk_compare_by_code
    assert UUn.sharpe_provenance_by_code is SUn.sharpe_provenance_by_code
    assert UUn.reconcile_by_code is SUn.reconcile_by_code
    assert UL.fund_currency_for_calc is SC.fund_currency_for_calc
    assert UL.SHEET_CCY_CONFLICT_KEY == SC.SHEET_CCY_CONFLICT_KEY


def test_ui_and_l2_merged_columns_agree_without_phase(monkeypatch):
    """週報呼叫 `build_merged_extra_columns(funds, "", None)`:舊 UI 入口與 L2 入口輸出必須相同。

    兩者差在 UI 會注入讀 `st.session_state` 的訊號函式;phase="" 時那個函式不會被呼叫。
    """
    import numpy as np
    import pandas as pd

    import services.fund_grp_health.capture as SCap
    from services.fund_grp_health.unified import build_merged_extra_columns as svc
    from ui.helpers.fund_grp_health.unified import build_merged_extra_columns as ui

    idx = pd.date_range("2016-01-01", periods=2600, freq="B")
    bench = pd.Series(100 * np.cumprod(1 + 0.0003 + 0.0004 * np.sin(np.arange(2600) / 17.0)), index=idx)
    monkeypatch.setattr(SCap, "_benchmark_nav", lambda m: bench)
    rng = np.random.default_rng(7)
    fidx = pd.date_range("2023-06-01", periods=500, freq="B")
    funds = [
        {"code": "AAA", "name": "A", "series": pd.Series(10 * np.cumprod(1 + 0.01 * rng.standard_normal(500)), index=fidx),
         "metrics": {"sharpe": 0.5, "nav": 10.0, "buy1": 9.0}, "moneydj_raw": {"currency": "USD"},
         "risk_metrics": {}, "currency": "USD"},
        {"code": "BBB", "name": "B", "series": None, "metrics": {}, "moneydj_raw": {},
         "risk_metrics": {}, "currency": ""},
    ]
    assert ui(funds, "", None) == svc(funds, "", None)
