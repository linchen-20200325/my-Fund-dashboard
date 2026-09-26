# -*- coding: utf-8 -*-
"""市場總覽正式模式的執行期測試（slow lane；需要 streamlit）。

依據 docs/v2/49_data_integration_plan.md §4.7 第 4 點：
把 `page` 模組上的 `fixtures` 屬性換成「一存取就拋錯」的替身，再以 stub 載入函式呼叫
`page.render(load_dataset=...)`。只要正式模式的任何一條路徑讀了 fixtures，這裡就紅。
這一條補的是 import 掃描抓不到的東西：`page.py` 本來就 import `fixtures`（示範模式要用），
「有沒有 import」證明不了「正式模式有沒有呼叫」。

另附正控：同一個替身之下**不傳**載入函式（示範模式）必須炸 —— 證明替身真的會咬人。
stub 只回一份最小的合法資料，不呼叫 `source`、不打任何網路。
"""

import pathlib
import sys

import pytest

# 整檔標 slow：畫面測試不進 fast lane（守衛：tests/ui_v2/test_ui_v2_lane_guards.py）。
pytestmark = pytest.mark.slow

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

from ui_v2.mkt import page  # noqa: E402

_MARK = "正式路徑碰到 fixtures"


class _FixturesThatBite:
    """任何屬性存取都拋錯的 fixtures 替身。"""

    def __getattr__(self, name):
        raise RuntimeError(f"{_MARK}：{name}")


_SCRIPT_LIVE = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
from ui_v2.mkt import page

def _stub_loader():
    return {{
        "dataset": {{
            "rows": [{{
                "indicator_key": "vol_index", "obs_date": "2026-09-24",
                "release_date": "2026-09-24", "value_num": 43.21, "value_unit": "index",
                "source_tier": "市場指標", "is_revised": False,
                "fetched_at": "2026-09-25T06:00:00+00:00",
            }}],
            "errors": {{"credit_spread_pct": {{MASKED!r}}}},
        }},
        "notes": {{
            "pending": {{"leading_index": "ndc_no_release_date",
                         "coincident_index": "ndc_no_release_date",
                         "fx_twd_per_usd": "fx_obs_date_rule",
                         "policy_rate_pct": "fred_release_date",
                         "term_spread_pct": "fred_release_date"}},
            "masked_keys": ["credit_spread_pct"],
            "cooldowns": [],
        }},
    }}

page.render(load_live=_stub_loader)
"""

_SCRIPT_DEMO = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
from ui_v2.mkt import page
page.render()
"""


def _masked_message():
    """M11（MKT 版）：真的走 L2 遮蔽函式產生一條遮蔽後的訊息（假金鑰現場隨機產生）。"""
    import secrets as _rnd

    masking = pytest.importorskip("services.v2_tables.masking")
    key = _rnd.token_hex(12)
    raw = f"HTTPSConnectionPool(host='127.0.0.1'): /fred?api_key={key} 連線被拒"
    masked = masking.mask_message(raw, masking.secret_values([{"FRED_API_KEY": key}]))
    return key, masked


def _run(script, monkeypatch):
    from streamlit.testing.v1 import AppTest

    # AppTest 在同一個行程裡跑腳本，腳本 import 到的就是這一個 page 模組物件。
    monkeypatch.setattr(page, "fixtures", _FixturesThatBite())
    at = AppTest.from_string(script.replace("{MASKED!r}", repr(_MASKED[1])), default_timeout=60)
    at.run()
    return at


_MASKED = None


@pytest.fixture(autouse=True)
def _masked(monkeypatch):
    global _MASKED
    _MASKED = _masked_message()


def _rendered(at):
    out = [e.value for e in at.markdown] + [e.value for e in at.caption]
    out += [e.label for e in at.button] + [e.label for e in at.expander]
    return out


def test_正式模式_fixtures一碰就炸的情況下照樣渲染完成(monkeypatch):
    at = _run(_SCRIPT_LIVE, monkeypatch)
    assert not at.exception, [e.value for e in at.exception]
    text = "\n".join(_rendered(at))
    assert "43.2" in text                       # stub 的值真的上了畫面（MKT-1 小數 1 位）
    assert _MARK not in text


def test_草稿1_頁首只留提問句(monkeypatch):
    at = _run(_SCRIPT_LIVE, monkeypatch)
    sub = [e.value for e in at.markdown if e.value.startswith('<div class="mkt-page-sub">')]
    assert sub == ['<div class="mkt-page-sub">現在的市場環境，和我上次看的時候比，變了哪裡</div>']
    text = "\n".join(_rendered(at))
    assert "情境" not in text and "示意值" not in text


def test_M11_MKT版_畫面上的訊息與遮蔽後字串逐字相同_下一行加註(monkeypatch):
    key, masked = _MASKED
    at = _run(_SCRIPT_LIVE, monkeypatch)
    card = [e.value for e in at.markdown if "高收益信用利差" in e.value]
    assert len(card) == 1
    html_masked = __import__("html").escape("⛔ 取數失敗：" + masked, quote=True)
    assert html_masked in card[0]               # 逐字（經 HTML 跳脫）
    assert key not in "\n".join(_rendered(at))
    after = card[0].split(html_masked, 1)[1]
    assert after.lstrip().startswith("</div>") and "已遮蔽憑證" in after.split("mkt-badge")[0]


def test_草稿3_資料未備下一行寫原因(monkeypatch):
    at = _run(_SCRIPT_LIVE, monkeypatch)
    text = "\n".join(_rendered(at))
    assert "原因：來源不提供公布日" in text
    assert "原因：觀測日切日規則待以真實資料驗證" in text
    assert "原因：公布日尚未接上，暫不寫入" in text


def test_草稿4與5_存檔與重新取數停用並寫原因_沒有in_memory說明(monkeypatch):
    at = _run(_SCRIPT_LIVE, monkeypatch)
    save = [b for b in at.button if b.key == "mkt4_save"]
    assert len(save) == 1 and save[0].disabled
    assert save[0].help == "設定存檔尚未接上，存了也留不到下次開頁"
    retry = [b for b in at.button if b.label == "重新取數"]
    assert retry and all(b.disabled and b.help == "重新取數尚未接上" for b in retry)
    text = "\n".join(_rendered(at))
    assert "in-memory" not in text and "updated_at" not in text
    assert "舊資料" not in text                 # 草稿 6


def test_正控_同一個替身之下示範模式一定會炸(monkeypatch):
    at = _run(_SCRIPT_DEMO, monkeypatch)
    assert at.exception, "替身沒有咬人 ⇒ 上一條是空的"
    assert any(_MARK in e.value for e in at.exception)


def test_不傳載入函式時_render的預設值就是None():
    import inspect

    param = inspect.signature(page.render).parameters["load_live"]
    assert param.default is None
    assert param.kind is inspect.Parameter.KEYWORD_ONLY
