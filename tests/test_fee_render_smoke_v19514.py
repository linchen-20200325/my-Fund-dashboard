"""v19.514:換扣款決策 render 冒煙測試 —— 5 分帶 + 情境 C 誠實措辭不炸、標記正確。

render_fee_deduction_section 需 streamlit;此處以 fake st + stub nav/fx 驅動整條 render 路徑
(真 build_fee_inputs + 真引擎),驗證「一律點名 top_pick」各分帶不 crash 且措辭符合 §1:
  - 高檔/成本之上/略低於成本/低檔/成本未知 各自的燈號與誠實字眼
  - top_pick=None(情境 C)→ 只提現金、不點名不存在的標的
"""
import sys

import pytest

from models.policy import fund_pk_str


class _Pos:
    def __init__(self, units, cost_unit, fx_avg):
        self.units, self.cost_unit, self.fx_avg = units, cost_unit, fx_avg


class _Led:
    def __init__(self, units, cost_unit, fx_avg=1.0):
        self.position = _Pos(units, cost_unit, fx_avg)


class _FakeST:
    """最小 streamlit 替身:記錄 (method, text),number_input 回固定月費,expander 為 ctx。"""
    def __init__(self, fee, session):
        self._fee = fee
        self.session_state = session
        self.outputs = []

    def divider(self):
        pass

    def _rec(self, kind):
        def _f(s="", *a, **k):
            self.outputs.append((kind, str(s)))
        return _f

    def __getattr__(self, name):
        # markdown/caption/info/success/warning/error/dataframe 皆記錄
        if name in ("markdown", "caption", "info", "success", "warning", "error", "dataframe"):
            return self._rec(name)
        raise AttributeError(name)

    def number_input(self, *a, **k):
        return self._fee

    def expander(self, *a, **k):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fund(code="TW_A", ccy="TWD", pid="POL1", pname="測試保單"):
    return {"code": code, "name": code, "currency": ccy, "policy_id": pid,
            "policy_name": pname, "loaded": True, "load_error": None}


def _run(monkeypatch, fund, ledger, nav, fx, fee=1000.0):
    import ui.helpers.portfolio.fee_deduction as mod
    monkeypatch.setattr(mod, "_make_nav_fx_fn", lambda: (lambda _f: (nav, fx)))
    session = {"t7_ledgers": {fund_pk_str(fund): ledger}} if ledger else {"t7_ledgers": {}}
    fake = _FakeST(fee=fee, session=session)
    monkeypatch.setitem(sys.modules, "streamlit", fake)
    mod.render_fee_deduction_section([fund])
    return fake.outputs


def _alltext(outputs):
    return "\n".join(t for _, t in outputs)


# ── 🟢 高檔(score>=1.15)→ success + 停利字眼,點名標的 ─────────────────────────
def test_band_high(monkeypatch):
    f = _fund()
    out = _run(monkeypatch, f, _Led(units=10000.0, cost_unit=10.0), nav=13.0, fx=1.0)  # 1.3
    txt = _alltext(out)
    assert any(k == "success" for k, _ in out)
    assert "TW_A" in txt and "高檔" in txt and "順勢停利" in txt
    # §1 regression guard(稽核發現並修):高分≠贖回單位少(units=F/V 與 S 無關)。
    # 只檢查燈號 note 本身(細節表有「贖回單位」欄=factual、免責也提「最低贖回單位」,皆合法)。
    _band_note = "\n".join(t for k, t in out if k == "success")
    assert "贖回單位" not in _band_note
    # §1:標題/燈號/section caption 不得用「最適」超級詞(虧損時該檔可能是 🔴 賤賣)。
    _headline_txt = "\n".join(t for k, t in out if k in ("success", "info", "warning", "markdown", "caption"))
    assert "最適" not in _headline_txt


# ── 🟡 成本之上非高檔(1.0<=score<1.15)→ info + 「其他選項:也可用台幣現金」──────────
def test_band_above_cost(monkeypatch):
    f = _fund()
    out = _run(monkeypatch, f, _Led(units=10000.0, cost_unit=10.0), nav=10.5, fx=1.0)  # 1.05
    txt = _alltext(out)
    assert any(k == "info" for k, _ in out)
    assert "成本之上" in txt and "台幣現金" in txt


# ── 🟠 略低於成本(0.90<=score<1.0)→ warning + 實現小幅虧損 + 優先現金 ──────────────
def test_band_below_cost(monkeypatch):
    f = _fund()
    out = _run(monkeypatch, f, _Led(units=10000.0, cost_unit=10.0), nav=9.5, fx=1.0)  # 0.95
    txt = _alltext(out)
    assert any(k == "warning" for k, _ in out)
    assert "略低於成本" in txt and "實現小幅虧損" in txt and "台幣現金" in txt


# ── 🔴 低檔(score<0.90)→ warning + 賤賣 + 建議優先台幣現金 ─────────────────────
def test_band_danger(monkeypatch):
    f = _fund()
    out = _run(monkeypatch, f, _Led(units=10000.0, cost_unit=10.0), nav=8.0, fx=1.0)  # 0.8
    txt = _alltext(out)
    assert any(k == "warning" for k, _ in out)
    assert "低檔" in txt and "賤賣" in txt and "建議優先" in txt and "台幣現金" in txt


# ── ⬜ 成本未知(cost_unit=None)→ 先於分帶標「成本未知」,不宣稱在成本之上 ────────────
def test_band_cost_estimated(monkeypatch):
    f = _fund()
    out = _run(monkeypatch, f, _Led(units=10000.0, cost_unit=None, fx_avg=None), nav=10.0, fx=1.0)
    txt = _alltext(out)
    assert "成本未知" in txt and "不表示在成本之上" in txt
    assert "T7" in txt                                   # 引導補成本


# ── 情境 C:市值不足 → top_pick None → 只提現金,不點名標的 ─────────────────────────
def test_scenario_c_no_deductible(monkeypatch):
    f = _fund()
    out = _run(monkeypatch, f, _Led(units=50.0, cost_unit=9.0), nav=10.0, fx=1.0)  # M=500<fee
    txt = _alltext(out)
    assert "無可扣標的" in txt and "台幣現金" in txt


# ── 美元高檔:decomp 顯示匯兌倍數(user 要看匯率×淨值)+ 點名美元標的 ─────────────────
def test_usd_high_shows_fx_decomp(monkeypatch):
    f = _fund(code="US_A", ccy="USD")
    out = _run(monkeypatch, f, _Led(units=1000.0, cost_unit=20.0, fx_avg=30.0), nav=25.0, fx=33.0)
    txt = _alltext(out)
    assert "US_A" in txt and "匯兌" in txt and "淨值報酬" in txt   # S 拆解揭露


# ── 併組:同保單相近 policy_id(大小寫)→ 併一組 + 揭露已合併 ──────────────────────
def test_merged_policy_disclosure(monkeypatch):
    import ui.helpers.portfolio.fee_deduction as mod
    monkeypatch.setattr(mod, "_make_nav_fx_fn", lambda: (lambda _f: (11.0, 1.0)))
    f1 = _fund(code="A", pid="POL1", pname="")
    f2 = _fund(code="B", pid="pol1", pname="")            # 只差大小寫 → 應併同組
    leds = {fund_pk_str(f1): _Led(10000.0, 10.0), fund_pk_str(f2): _Led(10000.0, 10.0)}
    fake = _FakeST(fee=1000.0, session={"t7_ledgers": leds})
    monkeypatch.setitem(sys.modules, "streamlit", fake)
    mod.render_fee_deduction_section([f1, f2])
    txt = _alltext(fake.outputs)
    assert "已合併相近的保單代號" in txt                   # 揭露併組(§1)
