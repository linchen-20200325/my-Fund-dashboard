# -*- coding: utf-8 -*-
"""preset 基金清單防漂移鎖 —— `config/` 與 `templates/` 兩份必須同源且對得上官方。

背景(2026-08-04 稽核)
=====================
`ACCP138` 在兩檔 JSON 被逐字寫成「聯博全球高收益債券基金 AT 級別 美元」,但 MoneyDJ /
FundDJ 官方(https://www.moneydj.com/funddj/yp/yp011000.djhtm?a=ACCP138)為
**瀚亞多重收益優化組合基金B配息(美元)**(瀚亞投信,**境內**證券投資信託基金,
成立 2018/09/26)。兩者不同投信、不同資產類別、連境內外法規體系都不同 —— 屬 §1
「Never Fake」等級的錯標(線上實測 Tab2 即時抓取顯示的正是「瀚亞多重收益優化組合基金B配」,
證明是 preset 錯、不是抓取錯)。

`templates/preset_funds_sample.json` 是**會被複製傳播**的樣板(templates/README.md:
「用此檔取代 repo 的 config/preset_funds.json」),錯值會擴散,故兩檔一起鎖。

另 `JFZN3`:MoneyDJ 同名(摩根投資基金-多重收益基金A股(美元對沖))對應 **5 個代號**
—— JFZA6 累計 / **JFZN3 穩定月配** / JFZA5 每月派息 / JFZA3 每季派息 / JFZK2 利率入息。
代號沒錯,但名稱字串不帶配息方式就無法唯一還原,任何以名稱 join 的下游會 1 對 5 撞號。

⚠️ 本檔只鎖「已實際查證」的兩筆 + 兩檔同源。其餘 6 筆(ACDD01 / ACDD19 / ACTI71 /
ACTI94 / TLZF9 / ALBT8)稽核已逐一比對官方為一致,不另加斷言(避免鎖死 user 合法編輯)。
"""
from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_CONFIG = _ROOT / "config" / "preset_funds.json"
_SAMPLE = _ROOT / "templates" / "preset_funds_sample.json"

# 官方查證值(2026-08-04):瀚亞投信,境內,成立 2018/09/26
_ACCP138_OFFICIAL = "瀚亞多重收益優化組合基金B配息(美元)"
# 錯值黑名單:曾被寫死的「聯博全球高收益債券基金 AT 級別 美元」相關特徵字
_ACCP138_WRONG_TOKENS = ("聯博", "高收益", "AT 級別")


def _funds(path: Path) -> "dict[str, str]":
    """讀 preset JSON → {CODE: name}。壞檔直接 raise(§1:不吞例外)。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    out: "dict[str, str]" = {}
    for d in data["funds"]:
        code = str(d["code"]).strip().upper()
        assert code, f"{path.name} 有空 code"
        assert code not in out, f"{path.name} code 重複:{code}"
        out[code] = str(d.get("name", "") or "").strip()
    return out


# ── ACCP138 = 瀚亞(非聯博高收益)—— 本次 P0 的核心鎖 ──────────────
def test_accp138_name_is_official_in_config():
    assert _funds(_CONFIG)["ACCP138"] == _ACCP138_OFFICIAL


def test_accp138_name_is_official_in_sample():
    """樣板檔會被複製回 config/,錯值會傳播 → 同鎖。"""
    assert _funds(_SAMPLE)["ACCP138"] == _ACCP138_OFFICIAL


def test_accp138_has_no_wrong_issuer_tokens():
    """防「又被改回去」:兩檔皆不得再出現聯博 / 高收益 / AT 級別 等錯值特徵。"""
    for _p in (_CONFIG, _SAMPLE):
        _name = _funds(_p)["ACCP138"]
        assert "瀚亞" in _name, f"{_p.name}: ACCP138 應為瀚亞投信基金"
        for _tok in _ACCP138_WRONG_TOKENS:
            assert _tok not in _name, f"{_p.name}: ACCP138 名稱殘留錯值特徵「{_tok}」"


# ── JFZN3 必須帶配息方式(同名 5 代號,不帶則 1 對 5 撞號)────────
def test_jfzn3_name_carries_distribution_class():
    for _p in (_CONFIG, _SAMPLE):
        _name = _funds(_p)["JFZN3"]
        assert "穩定月配" in _name, (
            f"{_p.name}: JFZN3 名稱須含「穩定月配」—— 否則與 JFZA6/JFZA5/JFZA3/JFZK2 同名撞號"
        )


# ── 兩檔同源(SSOT)────────────────────────────────────────────
def test_config_and_sample_are_identical():
    """`templates/` 樣板與 `config/` 實際清單必須逐筆一致 —— 否則複製即回退錯值。"""
    assert _funds(_CONFIG) == _funds(_SAMPLE)


def test_all_codes_upper_and_named():
    """code 大寫(fund_history._load_default_funds 會 .upper());name 不得空白。"""
    for _p in (_CONFIG, _SAMPLE):
        for _code, _name in _funds(_p).items():
            assert _code == _code.upper(), f"{_p.name}: {_code} 應為大寫"
            assert _name, f"{_p.name}: {_code} 缺名稱"
