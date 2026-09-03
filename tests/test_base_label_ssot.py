"""「基期」用字只准有一份（2026-09-02 T29）。

## 病徵

`services.rotation.classify_base()` 回四個狀態（high / low / mid / unknown），
畫面用字原本**手抄了三份**，而且三份都是**函式內的區域變數** —— 誰也 import 不到誰：

| 手抄處 | 出現在哪張畫面 |
|---|---|
| `unified.build_merged_extra_columns` 的 `_BASE_LBL` | 健診大表「基期」欄 |
| `tab_fund_grp_health._render_low_base_screener` 的 `_base_map` | 🎯 選基金（低基期）表 |
| `fund_grp_health/rotation._render_pairs_body` 的 `_lbl` | 輪動配對「目前各檔基期」 |

而 `_render_low_base_screener` 的 caption 就寫著「本區標 🟢 低基期的，大表『基期』欄
**一定**也是 🟢」—— 那句宣稱的前提正是三處用字一致，靠的卻是三次手抄。

## 這裡守什麼（為什麼不是 `assert "BASE_LABELS" in src`）

「有 import 這個常數」證明不了「畫面上那個字真的來自它」—— 有人可以 import 完照樣
在下面寫死一份。所以本檔一律**把 SSOT 換成獨一無二的探針值，再看渲染出來的是不是探針**。
換句話說：驗的是**資料流**，不是**關鍵字**。

## ⚠️ 給下一個人：守衛是會無聲死掉的

把下面任一條斷言用 `if False:` 之類的死分支關掉，pytest 依然報 **PASSED**、
`--collect-only` 的條數**也不會變**。**唯一能偵測守衛還活著的方法就是突變測試**：
把任一處改回手抄字典，本檔必須轉紅。改動本檔時請重跑一次。
"""
from __future__ import annotations

import pytest

_PROBE = {"high": "ZZHIGH", "low": "ZZLOW", "mid": "ZZMID", "unknown": "ZZUNK"}

_FUND = {"code": "AAA111", "name": "PROBE", "series": [], "metrics": {},
         "moneydj_raw": {}, "risk_metrics": {}, "currency": "USD",
         "loaded": True, "invest_twd": 1_000_000.0}


@pytest.fixture()
def _probe_labels(monkeypatch):
    """把 `BASE_LABELS` 換成探針值（消費端是 function-local import，換得掉）。"""
    import ui.helpers.fund_grp_health._utils as _u
    monkeypatch.setattr(_u, "BASE_LABELS", dict(_PROBE), raising=True)
    return _PROBE


class TestBaseLabelsAreOneSource:
    def test_ssot_exists_and_covers_classify_base_outputs(self):
        """SSOT 必須涵蓋 `classify_base()` 的**全部**回傳值，一個都不能少。

        突變：從 `BASE_LABELS` 拿掉 `"mid"` → 本條轉紅（`KeyError` 式的缺項報告）。
        """
        from services.rotation import classify_base
        from shared.signal_thresholds import ROTATION_BUY_SIGMA, ROTATION_SELL_SIGMA

        from ui.helpers.fund_grp_health._utils import BASE_LABELS

        # ⚠️ 取樣點**由門檻算出來**，不是寫死幾個數字。
        #    第一版寫死了 `(None, -9.0, -0.2, 9.0)`，而現行門檻是
        #    sell=-0.5 / buy=-1.5 —— 那四個點**一個都落不進 mid 區間**，
        #    於是「少了 mid」這個突變照樣全綠（本輪突變實測抓到）。
        #    這正是本檔 docstring 在講的那件事：一道看起來有跑的檢查，
        #    結構上看不到它要檢查的東西。
        _samples = (None,
                    ROTATION_BUY_SIGMA - 1.0,                       # → low
                    (ROTATION_BUY_SIGMA + ROTATION_SELL_SIGMA) / 2,  # → mid
                    ROTATION_SELL_SIGMA + 1.0)                      # → high
        produced = {
            classify_base(v, ROTATION_SELL_SIGMA, ROTATION_BUY_SIGMA)
            for v in _samples
        }
        assert produced == {"unknown", "low", "mid", "high"}, (
            f"取樣沒有覆蓋 classify_base 的四個狀態（實際只產出 {produced}）—— "
            "這條檢查在對空氣生效，先修取樣再談 SSOT"
        )
        missing = produced - set(BASE_LABELS)
        assert not missing, f"BASE_LABELS 少了 classify_base 會回的狀態：{missing}"

    def test_big_table_base_column_comes_from_the_ssot(self, _probe_labels):
        """健診大表的「基期」欄必須來自 SSOT。

        突變：把 `unified.build_merged_extra_columns` 內的 import 改回手抄字典 →
        本條轉紅（`AssertionError: 大表「基期」欄沒有吃 SSOT …`）。
        """
        from ui.helpers.fund_grp_health.unified import build_merged_extra_columns

        _order, combined = build_merged_extra_columns([_FUND], "", None)
        got = {v.get("基期") for v in combined.values()}
        assert got <= set(_PROBE.values()), (
            f"大表「基期」欄沒有吃 SSOT（實際渲染出：{got}）"
        )

    def test_low_base_screener_table_comes_from_the_ssot(self, monkeypatch,
                                                         _probe_labels):
        """🎯 選基金（低基期）表的「基期」欄必須來自**同一份** SSOT。

        這一條就是那句 caption（「本區標 🟢 低基期的，大表『基期』欄一定也是 🟢」）
        的機器版本 —— 兩處吃同一份，那句話才是真的。

        突變：把 `_render_low_base_screener` 內的 import 改回手抄字典 → 本條轉紅。
        """
        import streamlit as st

        import ui.tab_fund_grp_health as T

        shown: list = []
        monkeypatch.setattr(st, "dataframe",
                            lambda df, **k: shown.append(df), raising=True)
        monkeypatch.setattr(st, "download_button", lambda *a, **k: None, raising=True)
        monkeypatch.setattr(st, "multiselect", lambda *a, **k: [], raising=True)
        monkeypatch.setattr(st, "checkbox", lambda *a, **k: False, raising=True)
        monkeypatch.setattr(st, "form", lambda *a, **k: _NullCtx(), raising=True)
        monkeypatch.setattr(st, "form_submit_button", lambda *a, **k: False, raising=True)
        monkeypatch.setattr(st, "columns",
                            lambda spec, **k: [_NullCtx() for _ in range(
                                spec if isinstance(spec, int) else len(spec))],
                            raising=True)

        T._render_low_base_screener([{
            "code": "AAA111", "基金名": "PROBE", "ccy": "USD",
            "_fund_raw": {"fund_name": "PROBE",
                          "series": [{"date": "2026-01-0%d" % d, "nav": 10.0 + d}
                                     for d in range(1, 9)],
                          "currency": "USD", "moneydj_raw": {"category": "全球股票"}},
        }])
        assert shown, "選基金表沒有渲染 —— 這一區壞了，不是通過"
        vals = set(shown[0]["基期"].tolist())
        assert vals <= set(_PROBE.values()), (
            f"選基金表的「基期」欄沒有吃 SSOT（實際渲染出：{vals}）"
        )

    def test_rotation_labels_are_derived_not_a_fourth_copy(self):
        """輪動用的那一組必須是**衍生**，不是第四份手抄。

        規則：`BASE_LABELS_ROTATION[k]` 必須含有 `BASE_LABELS[k]` 的**基底文字**
        （high/low 只允許在後面加行動提示；unknown 只允許插入一個限定詞）。

        突變：把 `BASE_LABELS_ROTATION` 改成寫死四個字面值、且把 `low` 的 emoji 換掉 →
        本條轉紅（`AssertionError: 輪動標籤已與基底脫鉤 …`）。
        """
        from ui.helpers.fund_grp_health._utils import (
            BASE_LABELS,
            BASE_LABELS_ROTATION,
        )

        assert set(BASE_LABELS_ROTATION) == set(BASE_LABELS), "兩份的 key 不一致"
        drifted = []
        for _k, _base in BASE_LABELS.items():
            _rot = BASE_LABELS_ROTATION[_k]
            # emoji（第一個字）必須一樣；文字部分必須整段包含在衍生值裡
            # （unknown 允許插入限定詞，故只比對去掉 emoji 之後的尾段）。
            if _rot[0] != _base[0] or not _rot.endswith(_base.split(" ", 1)[-1][-3:]):
                if _base.split(" ", 1)[-1] not in _rot:
                    drifted.append((_k, _base, _rot))
        assert not drifted, f"輪動標籤已與基底脫鉤（不是衍生，是另一份手抄）：{drifted}"

    def test_rotation_pairs_body_consumes_the_rotation_ssot(self, monkeypatch):
        """輪動配對的「目前各檔基期」必須來自 `BASE_LABELS_ROTATION`。

        突變：把 `rotation._render_pairs_body` 內的 import 改回手抄字典 → 本條轉紅。
        """
        import streamlit as st

        import ui.helpers.fund_grp_health._utils as _u
        import ui.helpers.fund_grp_health.rotation as _rot

        monkeypatch.setattr(_u, "BASE_LABELS_ROTATION", dict(_PROBE), raising=True)
        caps: list[str] = []
        for _n in ("caption", "info", "markdown", "warning"):
            monkeypatch.setattr(st, _n,
                                lambda body="", *a, **k: caps.append(str(body)),
                                raising=True)
        monkeypatch.setattr(st, "divider", lambda *a, **k: None, raising=True)

        _rot._render_pairs_body(
            [{"code": "AAA111", "name": "PROBE", "σ rank": None},
             {"code": "BBB222", "name": "PROBE2", "σ rank": None}],
            [], -1.0, 1.0, key_prefix="probe_", offer_download=False)
        joined = "\n".join(caps)
        assert any(v in joined for v in _PROBE.values()), (
            f"輪動配對的基期標籤沒有吃 SSOT（實際輸出：{caps}）"
        )


class _NullCtx:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def checkbox(self, *a, **k):
        return False

    def multiselect(self, *a, **k):
        return []
