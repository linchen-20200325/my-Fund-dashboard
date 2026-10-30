# -*- coding: utf-8 -*-
"""🌍 市場與趨勢頁視覺層級模型（`ui_v2/mkt/overview.py`）純函式測試（fast lane；不需要 streamlit）。

BL-0525 Batch C（D1～D7，`DEC-2026-10-30-01`）。守的是：資訊存在且未遺失（detail 內含舊版圖下小字）、Missing／error 語意不變、
provenance 可追溯、一句主判讀不含日期與方向詞、BL-0517 三序列只用 B 線已寫的列（不新增來源）。
"""

from __future__ import annotations

import pathlib
import re
import sys
from datetime import date, timedelta

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from ui_v2 import presentation as P  # noqa: E402
from ui_v2.mkt import chart, logic, market_section as ms, overview as O  # noqa: E402


def _dom(domain, status="資料未備", **kw):
    base = {"domain": domain, "status": status, "reason_code": None, "reason": None, "source": None,
            "fetched_at": None, "obs_date": None, "value_unit": None, "points": []}
    base.update(kw)
    return base


def _points(start="2024-10-24", end="2026-10-23", base=16.0):
    d, out = date.fromisoformat(start), []
    while d <= date.fromisoformat(end):
        if d.weekday() < 5:
            out.append({"obs_date": d.isoformat(), "value_num": base + (d.toordinal() % 7) * 0.1})
        d += timedelta(days=1)
    return out


def _ok(domain, source, base, unit="index", **kw):
    return _dom(domain, "ok", source=source, fetched_at="2026-10-27T06:00:00+00:00", obs_date="2026-10-23",
                value_unit=unit, points=_points(base=base), **kw)


def _view(**over):
    doms = {
        "vix": _ok("vix", "Yahoo:^VIX", 16.0),
        "taiex": _ok("taiex", "Yahoo Finance (^TWII)", 22000.0),
        "sp500": _ok("sp500", "Yahoo Finance (^GSPC)", 5000.0),
        "us10y": _ok("us10y", "FRED (DGS10)", 4.0, "%"),
        "us2y": _ok("us2y", "FRED (DGS2)", 3.5, "%"),
    }
    for k in ("taiex_volume", "market_stats", "nasdaq", "msci_world", "msci_em", "eps_pe_scenario",
              "implied_trailing_index_earnings"):
        doms[k] = _dom(k)
    doms.update(over)
    order = ["vix", "taiex", "taiex_volume", "market_stats", "sp500", "us10y", "us2y", "nasdaq", "msci_world",
             "msci_em", "eps_pe_scenario", "implied_trailing_index_earnings"]
    return {"domains": [doms[k] for k in order]}


def _row(key, obs, value, release=None, fetched="2026-10-27T06:00:00Z"):
    return {"indicator_key": key, "obs_date": obs, "release_date": release or obs, "value_num": value,
            "value_unit": "pp", "source_tier": "T1", "is_revised": False, "fetched_at": fetched}


def _dataset(keys=O.RATES_KEYS, errors=None):
    rows = []
    for key in keys:
        rows += [_row(key, p["obs_date"], p["value_num"]) for p in _points(base=1.0)]
    return {"rows": rows, "errors": errors or {}}


# ───────────────────────── D3 一句主判讀 ─────────────────────────


def test_hero_只有計數與暫無完整判定_不含日期_不含方向詞():
    text = O.hero_sentence(_view())
    assert text == "5 項已取得、7 項資料未備；暫無完整市場綜合判定。"
    assert not re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}|資料截至|最新到", text)
    assert logic.scan_forbidden([text]) == {}
    assert P.is_one_sentence(text)


def test_hero_有取數失敗時多列一項_0項不寫():
    view = _view(vix=_dom("vix", "系統錯誤", reason="x"))
    assert O.hero_sentence(view) == "4 項已取得、7 項資料未備、1 項取數失敗；暫無完整市場綜合判定。"
    assert "業務例外" not in O.hero_sentence(view)


def test_hero_全部都取得時不寫資料未備():
    doms = {k: _ok(k, "s", 1.0) for k in ("taiex_volume", "market_stats", "nasdaq", "msci_world", "msci_em",
                                         "eps_pe_scenario", "implied_trailing_index_earnings")}
    assert O.hero_sentence(_view(**doms)) == "12 項已取得；暫無完整市場綜合判定。"


# ───────────────────────── D1 Primary ─────────────────────────


def test_Primary_五個序列_預設台股():
    assert O.PRIMARY_KEYS == ("taiex", "sp500", "vix", "us10y", "us2y") and O.DEFAULT_PRIMARY == "taiex"
    assert set(O.PRIMARY_OPTION_LABELS) == set(O.PRIMARY_KEYS)


@pytest.mark.parametrize("key", O.PRIMARY_KEYS)
def test_Primary_每個序列_三枚chips_圖高300_沒有摘要句(key):
    view = _view()
    domain = ms.domain_by_key(view)[key]
    card = O.primary_card(domain, key, "1Y")
    assert card["kind"] == "chart_card" and 3 <= len(card["chips"]) <= P.MAX_CHIPS
    assert card["summary"] is None and card["spec"]["height"] == O.PRIMARY_CHART_HEIGHT == 300
    texts = [c["text"] for c in card["chips"]]
    assert texts[0].startswith("最新 ") and texts[2].startswith("資料日 10-23（")


def test_Primary_價格序列是百分比報酬_殖利率是百分點_VIX放單位說明():
    doms = ms.domain_by_key(_view())
    assert re.fullmatch(r"近1Y [+-]\d+\.\d%", O.primary_card(doms["taiex"], "taiex", "1Y")["chips"][1]["text"])
    assert re.fullmatch(r"近1Y [+-]?\d+\.\d\d pp", O.primary_card(doms["us10y"], "us10y", "1Y")["chips"][1]["text"])
    assert O.primary_card(doms["vix"], "vix", "1Y")["chips"][1]["text"] == O.TEXT_VIX_UNIT_CHIP


def test_Primary_detail不丟資訊_舊版圖下四到六行小字全在():
    doms = ms.domain_by_key(_view())
    for key in O.PRIMARY_KEYS:
        card = O.primary_card(doms[key], key, "1Y")
        old = O._MODEL_FN[key](doms[key], "1Y")["caption_lines"]
        in_detail = P.detail_texts(card["detail"])
        for line in old:
            assert line in in_detail, (key, line)
    taiex = O.primary_card(doms["taiex"], "taiex", "1Y")["detail"]
    assert any("期間漲跌" in t for t in P.detail_texts(taiex))
    assert ms.TEXT_FRESHNESS_THRESHOLD in P.detail_texts(taiex)
    assert [name for name, _ in taiex["groups"]] == ["為什麼", "來源", "限制"]


def test_Primary_期間不足_誠實說資料不足_不縮短冒充():
    doms = ms.domain_by_key(_view())
    card = O.primary_card(doms["taiex"], "taiex", "3Y")
    assert card["spec"] is None and card["message"] == chart.TEXT_INSUFFICIENT
    assert card["chips"][1]["text"] == "近3Y 資料不足" and card["availability"]["3Y"] is False


def test_Primary_取數失敗_只寫狀態_原文不上畫面_沒有圖():
    view = _view(taiex=_dom("taiex", "系統錯誤", reason="Yahoo:^TWII 失敗：HTTP 429 Too Many Requests"))
    card = O.primary_card(ms.domain_by_key(view)["taiex"], "taiex", "1Y")
    assert card["kind"] == "status" and card["spec"] is None
    assert [c["text"] for c in card["chips"]] == ["⛔ 取數失敗"] and card["chips"][0]["tone"] == "紅"
    blob = "\n".join(P.detail_texts(card["detail"])) + card["reason"]
    assert "429" not in blob and "Yahoo" not in blob
    assert P.is_one_sentence(card["reason"]) and any(n == "去哪補" for n, _ in card["detail"]["groups"])


def test_Primary_略過觀測的安靜說明保留_成為第四枚chip():
    view = _view(us10y=_ok("us10y", "FRED (DGS10)", 4.0, "%", reason="已略過 3 筆無法採用的觀測"))
    card = O.primary_card(ms.domain_by_key(view)["us10y"], "us10y", "1Y")
    assert len(card["chips"]) == 4 and card["chips"][3]["text"] == "已略過 3 筆無法採用的觀測"
    assert "已略過 3 筆無法採用的觀測" in P.detail_texts(card["detail"])


def test_Primary_不認得的序列拋錯():
    with pytest.raises(ValueError):
        O.primary_card(_dom("nasdaq"), "nasdaq", "1Y")


# ───────────────────────── D1／D6 Secondary ─────────────────────────


def test_Secondary_是迷你圖_沒有座標軸文字_沒有期間切換():
    doms = ms.domain_by_key(_view())
    card = O.secondary_card(doms["vix"], "vix", O.SECONDARY_RISK_TITLE)
    assert card["spark"].startswith("<svg") and "<text" not in card["spark"] and "axis" not in card["spark"]
    assert card["spec"] is None or card["spec"]["height"] != O.PRIMARY_CHART_HEIGHT
    assert len(card["chips"]) == 3
    assert O.MAX_SECONDARY == 3


def test_Secondary_取數失敗_只有狀態_沒有迷你圖():
    view = _view(sp500=_dom("sp500", "系統錯誤", reason="boom"))
    card = O.secondary_card(ms.domain_by_key(view)["sp500"], "sp500", O.SECONDARY_INTL_TITLE)
    assert card["kind"] == "status" and card["spark"] is None


def test_sparkline_缺值斷線_不補值_沒有任何文字():
    pts = [{"obs_date": f"2026-10-{d:02d}", "value_num": v} for d, v in
           ((1, 1.0), (2, 2.0), (3, None), (4, 3.0), (5, 2.5))]
    svg = chart.sparkline_svg(pts, aria_label="測試")
    path = re.search(r' d="([^"]+)"', svg).group(1)
    assert path.count("M") == 2                      # 斷成兩段
    assert "<text" not in svg and 'role="img"' in svg and 'aria-label="測試"' in svg
    for banned in ("目標價", "預測", "箭頭"):
        assert banned not in svg


def test_sparkline_沒有任何有值的點_拋錯_不畫空圖():
    with pytest.raises(ValueError):
        chart.sparkline_svg([{"obs_date": "2026-10-01", "value_num": None}], aria_label="x")


def test_sparkline_單點與常數序列不除以零():
    one = chart.sparkline_svg([{"obs_date": "2026-10-01", "value_num": 5.0}], aria_label="x")
    flat = chart.sparkline_svg([{"obs_date": "2026-10-01", "value_num": 5.0},
                                {"obs_date": "2026-10-02", "value_num": 5.0}], aria_label="x")
    assert "nan" not in one.lower() and "nan" not in flat.lower()


def test_sparkline_aria_label_轉義():
    svg = chart.sparkline_svg([{"obs_date": "2026-10-01", "value_num": 1.0}], aria_label='S&P "500" <x>')
    assert 'S&amp;P &quot;500&quot; &lt;x&gt;' in svg


# ───────────────────────── D2 利率與信用 ─────────────────────────


def test_利率與信用_三個子序列_預設期限利差_同時只顯示一個():
    assert O.RATES_KEYS == ("term_spread_pct", "credit_spread_pct", "policy_rate_pct")
    assert O.DEFAULT_RATES == "term_spread_pct"
    ds = _dataset()
    cards = [O.rates_card(ds, k) for k in O.RATES_KEYS]
    assert [c["title"] for c in cards] == [f"利率與信用｜{O.RATES_OPTION_LABELS[k]}" for k in O.RATES_KEYS]
    for c in cards:
        assert len(c["chips"]) == 3 and c["spark"].startswith("<svg")     # chips 只留值、期間變動、資料日


def test_利率與信用_來源標示與L2_INDICATOR_SPECS一致_不新增來源():
    from services.v2_tables import market_indicator as mi
    for key in O.RATES_KEYS:
        src = mi.INDICATOR_SPECS[key]
        assert O.RATES_SOURCE_LABELS[key] == f"{src['source'][0]} ({src['source'][1]})"
        assert O.RATES_UNIT_TEXT[key] == src["value_unit"]
        assert src["phase1"] == "write"          # B 線已正式取數寫列（不是本批新增）


def test_利率與信用_同一觀測日多個版次取公布日最晚():
    rows = [_row("credit_spread_pct", "2026-10-01", 3.0, release="2026-10-02"),
            _row("credit_spread_pct", "2026-10-01", 3.2, release="2026-10-09"),
            _row("credit_spread_pct", "2026-10-02", 3.1, release="2026-10-03")]
    dom = O.rates_domain({"rows": rows, "errors": {}}, "credit_spread_pct")
    assert dom["status"] == "ok" and dom["points"] == [{"obs_date": "2026-10-01", "value_num": 3.2},
                                                       {"obs_date": "2026-10-02", "value_num": 3.1}]
    assert dom["source"] == "FRED (BAMLH0A0HYM2)" and dom["obs_date"] == "2026-10-02"


def test_利率與信用_沒有列_資料層記了失敗就是取數失敗_否則資料未備_不借別的序列():
    err = O.rates_domain({"rows": [], "errors": {"term_spread_pct": "boom"}}, "term_spread_pct")
    miss = O.rates_domain({"rows": [], "errors": {}}, "term_spread_pct")
    assert err["status"] == "系統錯誤" and miss["status"] == "資料未備"
    card = O.rates_card({"rows": [], "errors": {"term_spread_pct": "boom"}}, "term_spread_pct")
    assert card["kind"] == "status" and "boom" not in str(card)
    # 只有信用利差有列時，期限利差仍是未備，不拿信用利差頂替
    only = {"rows": [_row("credit_spread_pct", "2026-10-01", 3.0)], "errors": {}}
    assert O.rates_domain(only, "term_spread_pct")["status"] == "資料未備"


def test_利率與信用_期間不足_說資料不足_沒有迷你圖():
    ds = {"rows": [_row("policy_rate_pct", "2026-09-01", 4.3)], "errors": {}}
    card = O.rates_card(ds, "policy_rate_pct")
    assert card["spark"] is None and card["message"] == chart.TEXT_INSUFFICIENT
    assert card["chips"][1]["text"] == "近1Y 資料不足"


def test_Secondary合併detail_三個利率子序列的來源與限制全在():
    blocks = O.secondary_detail_blocks(_view(), _dataset())
    titles = [t for t, _ in blocks]
    assert titles == [O.SECONDARY_RISK_TITLE, O.SECONDARY_INTL_TITLE,
                      *[f"利率與信用｜{O.RATES_OPTION_LABELS[k]}" for k in O.RATES_KEYS]]
    blob = "\n".join(x for _t, d in blocks for x in P.detail_texts(d))
    for src in O.RATES_SOURCE_LABELS.values():
        assert src in blob
    assert O.TEXT_RATES_OBS_NOTE in blob and ms.TEXT_FRESHNESS_THRESHOLD in blob


# ───────────────────────── D4 尚未取得 ─────────────────────────


def test_尚未取得群組_EPS_PE排最前_標題列點名每一項_七項都在():
    group = O.missing_group(_view())
    assert group["keys"][0] == "eps_pe_scenario" and len(group["keys"]) == 7
    for key in group["keys"]:
        assert ms.LABELS[key] in group["title"]
    assert group["title"].endswith("（7 項）") and group["title"].startswith("▸ ")


def test_尚未取得群組_已取得的項目不列_全部取得則不畫():
    doms = {k: _ok(k, "s", 1.0) for k in O.MISSING_GROUP_KEYS}
    assert O.missing_group(_view(**doms)) is None
    part = O.missing_group(_view(nasdaq=_ok("nasdaq", "s", 1.0)))
    assert "nasdaq" not in part["keys"] and len(part["keys"]) == 6


# ───────────────────────── 守衛 ─────────────────────────


def test_page_strings_無方向詞_無箭頭_無目標價_無頁級日期詞():
    strings = O.page_strings(_view(), _dataset())
    assert logic.scan_forbidden(strings) == {}
    joined = "\n".join(strings)
    for word in ("目標價", "預測", "偏多", "偏空", "資料截至", "最新到"):
        assert word not in joined, word


def test_overview不import_streamlit也不import舊樹():
    import ast
    tree = ast.parse((_ROOT / "ui_v2/mkt/overview.py").read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            roots.add((node.module or "").split(".")[0])
    assert not roots & {"streamlit", "ui", "services", "repositories", "shared", "infra", "requests"}, roots


# ───────────────────────── 非 OK 路徑不丟 L2 reason（D7：不得刪除依據內容）─────────────────────────


@pytest.mark.parametrize("status", ["資料未備", "業務例外"])
def test_非OK卡_L2_reason進detail限制組_主卡只有chip加一句短原因(status):
    why = "歷史不足 5y：XYZ原因"
    view = _view(sp500=_dom("sp500", status, reason=why, reason_code="x"))
    domain = ms.domain_by_key(view)["sp500"]
    for card in (O.primary_card(domain, "sp500", "1Y"), O.secondary_card(domain, "sp500", O.SECONDARY_INTL_TITLE)):
        assert card["kind"] == "status"
        assert why in P.detail_texts(card["detail"]) or f"原因：{why}" in P.detail_texts(card["detail"])
        assert why not in card["reason"] and all(why not in c["text"] for c in card["chips"])   # 不在主卡常駐
        assert ("限制" in [n for n, _ in card["detail"]["groups"]])


def test_取數失敗_原文不上一般畫面_含展開區_原文走進階診斷():
    why = "Yahoo:^TWII 失敗：HTTP 429"
    domain = ms.domain_by_key(_view(taiex=_dom("taiex", "系統錯誤", reason=why)))["taiex"]
    card = O.primary_card(domain, "taiex", "1Y")
    assert "429" not in "\n".join(P.detail_texts(card["detail"]))
    assert why in [e["text"].split("：", 1)[1] for e in ms.raw_entries({"domains": [domain]})]


def test_利率與信用_Missing路徑_沒有reason可丟_狀態與去哪補在detail():
    card = O.rates_card({"rows": [], "errors": {}}, "credit_spread_pct")
    texts = P.detail_texts(card["detail"])
    assert "狀態：⬜ 資料未備" in texts and any("設定與診斷" in t for t in texts)


def test_尚未取得群組_各項仍逐項用既有固定文案_與各項資料狀態列_沒有新的reason遺失():
    view = _view()
    domains = ms.domain_by_key(view)
    for key in O.missing_group(view)["keys"]:
        assert ms.missing_copy(domains[key])          # 逐項文案（沿用 market_section，一字未改）
    assert [r["label"] for r in ms.conclusion_model(view)["rows"]] == [ms.LABELS[d["domain"]] for d in view["domains"]]
