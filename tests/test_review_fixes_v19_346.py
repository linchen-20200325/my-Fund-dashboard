# -*- coding: utf-8 -*-
"""v19.346 — 第九份外部 review 查證屬實項修復的回歸鎖(基金側)。

涵蓋:
- fetch_nav / fetch_div:raw requests.get(無重試/無 403 降級/無 Big5 解碼)
  → fetch_url_with_retry(infra 統一鏈,同檔 wb01 既有慣例)
- fetch_holdings:sector_alloc Σpct ∉ [95,105]% → 掛旗標 + log(不丟資料)
- fetch_risk_metrics:解析結果缺核心鍵(標準差/Sharpe)→ 掛旗標 + log
- tab2_single_fund:6 處無註解裸 except:pass → 補 stderr log(§3.3)
- tab5_data_guard:_d5_cell fmt 死參數實作(狀態後附值)+ §⑤ session 快取誠實 caption
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _src(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def _fn_slice(text: str, fn_name: str) -> str:
    """取 def fn_name(... 到下一個同層 def 的原始碼切片(source-scan 用)。"""
    m = re.search(rf"^def {fn_name}\(", text, re.M)
    assert m, f"找不到 def {fn_name}"
    nxt = re.search(r"^def \w+\(", text[m.end():], re.M)
    return text[m.start(): m.end() + (nxt.start() if nxt else len(text))]


# ═════════════════════════════════════════════════════════════════
# fetch_nav / fetch_div → fetch_url_with_retry
# ═════════════════════════════════════════════════════════════════
def _live_lines(body: str) -> list[str]:
    """去掉純註解行(避免說明文字裡的字樣誤中掃描)。"""
    return [ln for ln in body.splitlines() if not ln.lstrip().startswith("#")]


class TestNavDivUseRetryHelper:
    def test_fetch_nav_no_raw_requests(self):
        body = _fn_slice(_src("repositories/fund/nav_metrics.py"), "fetch_nav")
        assert "fetch_url_with_retry(" in body
        assert not any("requests.get(" in ln for ln in _live_lines(body)), (
            "fetch_nav 不應再用 raw requests.get(無重試/無降級/無 Big5)")

    def test_fetch_div_no_raw_requests(self):
        body = _fn_slice(_src("repositories/fund/nav_metrics.py"), "fetch_div")
        assert "fetch_url_with_retry(" in body
        assert not any("requests.get(" in ln for ln in _live_lines(body))


# ═════════════════════════════════════════════════════════════════
# fetch_holdings sector Σ sanity(runtime,繞過 @_daily_cache 防污染)
# ═════════════════════════════════════════════════════════════════
_HOLD_HTML = """<html><body><!-- {pad} -->
<table>
<tr><td colspan="2">產業分布表</td></tr>
<tr><td>產業</td><td>比例</td></tr>
{rows}
</table>
</body></html>"""


class _FakeResp:
    def __init__(self, text):
        self.text = text
        self.status_code = 200


def _run_holdings(monkeypatch, rows_html: str) -> dict:
    import repositories.fund.nav_metrics as nm
    html = _HOLD_HTML.format(pad="x" * 600, rows=rows_html)
    monkeypatch.setattr(nm, "fetch_url_with_retry",
                        lambda *a, **k: _FakeResp(html))
    # __wrapped__:繞過 @_daily_cache — 測試資料不得流入 production cache(§3.3)
    return nm.fetch_holdings.__wrapped__("TEST99")


class TestHoldingsSectorSumSanity:
    def test_sum_out_of_band_flags_suspect(self, monkeypatch):
        out = _run_holdings(monkeypatch, (
            "<tr><td>科技</td><td>30.0</td></tr>"
            "<tr><td>金融</td><td>15.0</td></tr>"
            "<tr><td>傳產</td><td>5.0</td></tr>"))          # Σ=50%
        assert out.get("sector_alloc"), "資料不得因超帶被丟棄(§1 不誤殺)"
        assert out.get("sector_alloc_sum_suspect") is True
        assert abs(out.get("sector_alloc_sum_pct") - 50.0) < 1e-9

    def test_sum_in_band_no_flag(self, monkeypatch):
        out = _run_holdings(monkeypatch, (
            "<tr><td>科技</td><td>40.0</td></tr>"
            "<tr><td>金融</td><td>35.0</td></tr>"
            "<tr><td>傳產</td><td>25.0</td></tr>"))          # Σ=100%
        assert out.get("sector_alloc")
        assert "sector_alloc_sum_suspect" not in out
        assert "sector_alloc_sum_pct" not in out

    def test_band_in_source(self):
        assert "95.0 <= _pct_sum <= 105.0" in _src(
            "repositories/fund/nav_metrics.py")


# ═════════════════════════════════════════════════════════════════
# fetch_risk_metrics 核心鍵檢查(runtime,同樣繞 cache)
# ═════════════════════════════════════════════════════════════════
_RISK_HTML = """<html><body><!-- {pad} -->
<table>
<tr><td colspan="3">Sharpe 風險指標表</td></tr>
<tr><td>指標</td><td>一年</td><td>三年</td></tr>
{rows}
</table>
</body></html>"""


def _run_risk(monkeypatch, rows_html: str) -> dict:
    import repositories.fund.nav_metrics as nm
    html = _RISK_HTML.format(pad="x" * 600, rows=rows_html)
    monkeypatch.setattr(nm, "fetch_url_with_retry",
                        lambda *a, **k: _FakeResp(html))
    return nm.fetch_risk_metrics.__wrapped__("TEST99")


class TestRiskTableCoreKeys:
    def test_renamed_metric_flags_missing_core(self, monkeypatch):
        out = _run_risk(monkeypatch,
                        "<tr><td>夏普比率</td><td>1.23</td><td>0.98</td></tr>")
        assert out.get("risk_table"), "解析到的指標仍應回傳(§1 不誤殺)"
        assert out.get("risk_table_missing_core") is True

    def test_standard_metrics_no_flag(self, monkeypatch):
        out = _run_risk(monkeypatch,
                        "<tr><td>標準差</td><td>12.5</td><td>15.1</td></tr>")
        assert out.get("risk_table")
        assert "risk_table_missing_core" not in out


# ═════════════════════════════════════════════════════════════════
# tab2:無註解裸 except:pass 清零 + 6 個新 log tag
# ═════════════════════════════════════════════════════════════════
class TestTab2ExceptLogs:
    def test_no_undocumented_bare_pass(self):
        lines = _src("ui/tab2_single_fund.py").splitlines()
        offenders = []
        for i, ln in enumerate(lines[:-1]):
            if ln.strip() == "except Exception:" and \
                    lines[i + 1].strip() == "pass":   # 純 pass 無任何註解
                offenders.append(i + 1)
        assert not offenders, (
            f"無註解裸 except:pass 違 §3.3(行號 {offenders});"
            f"允許的沉默必須帶 smoke-allow-pass 等註解說明")

    def test_new_log_tags_present(self):
        text = _src("ui/tab2_single_fund.py")
        for tag in ("[tab2/freshness]", "[tab2/linkage]", "[tab2/income-calc]",
                    "[tab2/accum-calc]", "[tab2/ai-divsafety]", "[tab2/ai-hwm]"):
            assert tag in text, f"缺 {tag} log(§3.3 除錯留痕)"


# ═════════════════════════════════════════════════════════════════
# tab5:_d5_cell fmt 實作 + §⑤ 誠實 caption
# ═════════════════════════════════════════════════════════════════
class TestTab5Diagnostics:
    def test_d5_cell_fmt_applied(self):
        text = _src("ui/tab5_data_guard.py")
        assert "fmt(value)" in text, "_d5_cell fmt 參數不得再是死參數"
        assert "[tab5/_d5_cell]" in text, "fmt 失敗須留 stderr log(§3.3)"

    def test_section5_honest_session_cache_caption(self):
        text = _src("ui/tab5_data_guard.py")
        assert "本 session 已載入的快取" in text, (
            "§⑤ 只讀 session_state,須誠實標示非即時重抓(§2.4)")
