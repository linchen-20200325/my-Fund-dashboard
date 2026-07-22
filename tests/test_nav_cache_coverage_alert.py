"""回歸網 — v19.321:NAV 快取 Action 覆蓋過低時發 GitHub Actions warning。

背景(user #2 深挖):`cache/nav/` 長期只有 TLZF9 一檔,且 source=cache_only —— 代表
每日 Action 其實 fetch 全敗(GitHub 美國 IP 被台灣站點封鎖、PROXY_URL 未生效),
只重存舊快取,卻仍回綠勾。`_emit_coverage_alert` 把這個靜默失敗變成 GitHub Actions
warning annotation(§1 Fail-Loud / §5 可觀測),讓 user 知道要設 PROXY_URL secret。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch_nav_cache.py"


def _load_module():
    """scripts 非 package → 用 importlib 從檔案路徑載(不會跑 main:在 __main__ guard 下)。"""
    spec = importlib.util.spec_from_file_location("_fnc_under_test", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MOD = _load_module()


def test_low_coverage_emits_github_warning(capsys):
    """過半 code 沒抓到新資料 → 回 low=True 且印出 ::warning:: annotation。"""
    summary = [{"code": "TLZF9", "count": 10, "fresh": False}]
    summary += [{"code": f"C{i}", "count": 0, "fresh": False} for i in range(10)]  # 11 檔僅 0 fresh
    r = _MOD._emit_coverage_alert(summary)
    assert r["low"] is True
    assert r["total"] == 11 and r["fresh"] == [] and len(r["no_data"]) == 10
    out = capsys.readouterr().out
    assert "::warning" in out and "PROXY_URL" in out


def test_high_coverage_no_warning(capsys):
    """過半有新資料 → low=False,不發 warning。"""
    summary = [{"code": f"C{i}", "count": 100, "fresh": True} for i in range(10)]
    summary += [{"code": "X", "count": 0, "fresh": False}]  # 10/11 fresh
    r = _MOD._emit_coverage_alert(summary)
    assert r["low"] is False
    out = capsys.readouterr().out
    assert "::warning" not in out


def test_empty_summary_does_not_crash(capsys):
    """空 summary(理論上不會發生)→ 不炸、不誤報。"""
    r = _MOD._emit_coverage_alert([])
    assert r["low"] is False and r["total"] == 0


def test_writes_step_summary_when_env_set(tmp_path, monkeypatch, capsys):
    """GITHUB_STEP_SUMMARY 有設 → 低覆蓋時把診斷寫進 step summary 檔。"""
    step = tmp_path / "step_summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(step))
    summary = [{"code": "TLZF9", "count": 10, "fresh": False},
               {"code": "C1", "count": 0, "fresh": False}]
    _MOD._emit_coverage_alert(summary)
    assert step.exists()
    body = step.read_text(encoding="utf-8")
    assert "NAV 快取覆蓋過低" in body and "C1" in body  # C1 = 完全無快取(count 0)那檔


# ── v19.348：警告訊息依「代理實際狀態」誠實分流(修舊版無腦甩鍋 PROXY_URL 的誤導) ──
_LOW_SUMMARY = ([{"code": "TLZF9", "count": 10, "fresh": False}]
                + [{"code": f"C{i}", "count": 0, "fresh": False} for i in range(10)])


def test_proxy_off_message_blames_missing_proxy(monkeypatch, capsys):
    """未設 PROXY_URL → 訊息指向『設 PROXY_URL』且 proxy_on=False。"""
    monkeypatch.setattr(_MOD, "_PROXY_URL", "")
    r = _MOD._emit_coverage_alert(_LOW_SUMMARY)
    out = capsys.readouterr().out
    assert r["proxy_on"] is False
    assert "未啟用 proxy" in out and "設 PROXY_URL" in out


def test_proxy_on_message_does_not_blame_missing_proxy(monkeypatch, capsys):
    """PROXY_URL 已設(代理啟用)但覆蓋仍低 → 不可再說『未設代理』,要指向來源/NAS 可達性。"""
    monkeypatch.setattr(_MOD, "_PROXY_URL", "http://u:p@nas.example:3128")
    r = _MOD._emit_coverage_alert(_LOW_SUMMARY)
    out = capsys.readouterr().out
    assert r["proxy_on"] is True
    assert "已啟用" in out
    # 關鍵回歸:代理已開時，不得再誤導成「未設 PROXY_URL / 沒設代理」
    assert "未設" not in out and "未啟用 proxy" not in out


# ── v19.351：境內改走 AllianzGI(安聯官網);SITCA 確認為公司/月份下拉頁,已停用 ──
class _Resp:
    def __init__(self, text="", status=200, payload=None):
        self.text, self.status_code, self._payload = text, status, payload

    def raise_for_status(self):
        return None

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def test_sitca_history_now_skips(capsys):
    """v19.351:SITCA IN2213 確認公司/月份下拉頁,不支援單檔 → 直接 skip 回 []。"""
    rows = _MOD.fetch_sitca_history("ACTI71")
    out = capsys.readouterr().out
    assert rows == []
    assert "略過" in out


def test_allianzgi_json_api_parses_rows(monkeypatch):
    """安聯 Sitecore JSON API 回 ≥90 筆 → 直接解析短路(不需 ISIN,直接用內部碼)。"""
    payload = {"Data": [{"Date": f"2026-01-{(i % 28) + 1:02d}", "Nav": 10 + i * 0.01}
                        for i in range(95)]}
    _posted = {}

    def _fake_post(url, json=None, **k):
        _posted["url"] = url
        _posted["body"] = json
        return _Resp(payload=payload)

    monkeypatch.setattr(_MOD.SESSION, "post", _fake_post)
    rows = _MOD.fetch_allianzgi_history("ACTI71")
    assert len(rows) >= 28                                    # 去重後仍多筆
    assert all("date" in r and "nav" in r for r in rows)
    assert _posted["url"] == _MOD._ALLIANZ_NAV_API
    assert _posted["body"].get("FundCode") == "ACTI71"        # 直接用內部碼


def test_allianzgi_empty_returns_empty_list(monkeypatch):
    """安聯 API 全空 + yp004002 無資料 → 回 [](§1 不偽造)。"""
    monkeypatch.setattr(_MOD.SESSION, "post",
                        lambda *a, **k: _Resp(status=404))
    monkeypatch.setattr(_MOD.SESSION, "get",
                        lambda *a, **k: _Resp(text="<html></html>", status=200))
    rows = _MOD.fetch_allianzgi_history("ACTI71")
    assert rows == []


# ── v19.352：境外基金加 CnYES(境外主要來源,直接用內部碼) ──
def test_cnyes_parse_items_field_variants_and_timestamp():
    """_cnyes_parse_items:寬容欄位名 + Unix ms timestamp;去重 + 降冪。"""
    items = [
        {"date": "2026/07/20", "nav": "12.34"},          # 斜線 + 字串
        {"Date": "2026-07-19", "Nav": 12.30},            # 大寫欄位
        {"timestamp": 1_768_000_000_000, "value": 12.5}, # ms epoch → 轉日期
        {"date": "2026-07-20", "nav": 99},               # 同日重複 → 去重
        {"date": "2026-07-18", "nav": 0},                # nav<=0 → 丟
    ]
    out = _MOD._cnyes_parse_items(items)
    assert out[0]["date"] >= out[-1]["date"]              # 降冪
    _dates = [r["date"] for r in out]
    assert _dates.count("2026-07-20") == 1                # 去重
    assert all(r["nav"] > 0 for r in out)                # 無 0/負


def test_cnyes_fetch_walks_nested_json(monkeypatch):
    """fetch_cnyes_history:GET API → 遞迴找 nested nav list → 解析(≥30 才短路)。"""
    import datetime as _dt
    _base = _dt.date(2026, 1, 1)
    nested = {"data": {"items": [
        {"date": (_base + _dt.timedelta(days=i)).strftime("%Y-%m-%d"), "nav": 10 + i * 0.01}
        for i in range(60)]}}   # 60 個唯一日期(> 30 門檻)
    _got = {}

    def _fake_get(url, **k):
        _got["url"] = url
        return _Resp(payload=nested)

    monkeypatch.setattr(_MOD.SESSION, "get", _fake_get)
    rows = _MOD.fetch_cnyes_history("JFZN3")
    assert len(rows) >= 28 and all("date" in r and "nav" in r for r in rows)
    assert "api.cnyes.com" in _got["url"] and "JFZN3" in _got["url"]  # 直接用內部碼


def test_cnyes_fetch_empty_returns_empty(monkeypatch):
    """CnYES API 全無資料 → 回 [](§1)。"""
    monkeypatch.setattr(_MOD.SESSION, "get", lambda *a, **k: _Resp(status=404))
    assert _MOD.fetch_cnyes_history("CTZP0") == []
