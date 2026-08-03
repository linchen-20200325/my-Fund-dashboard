"""services/regime_fit.py — 景氣位階「適配標籤」純邏輯(v19.425)。零 IO。

依基金屬性(資產類別 + 核心/衛星 + 上/下檔捕捉)給景氣適配傾向,對照當前景氣 → 順風/逆風/全景氣/
無法判定,並附**透明理由**(非黑箱)。§1:缺類別 / 無法對應 / 景氣未偵測 → ⬜ 無法判定,不亂猜。
**參考傾向,非買賣建議、非 % 配置**。常數走 `shared.regime_fit` SSOT。
"""
from __future__ import annotations

from shared.converters import safe_num as _num
from shared.regime_fit import (
    ASSET_BUCKETS,
    CAPTURE_AGGRESSIVE_BONUS,
    CAPTURE_DEFENSIVE_BONUS,
    DOWNSIDE_DEFENSIVE_MAX,
    FIT_LABELS,
    REGIME_ALIASES,
    REGIMES,
    UPSIDE_AGGRESSIVE_MIN,
)

_EMOJI = "🔵🟢🟡🔴⬜⚪🟠🟦 "


def normalize_regime(raw) -> "str | None":
    """任意偵測器景氣標籤(可帶 emoji)→ 正規位階(REGIMES 之一)或 None(未知/無法對應)。"""
    if not raw:
        return None
    _s = str(raw)
    for _ch in _EMOJI:
        _s = _s.replace(_ch, "")
    _s = _s.strip()
    if not _s or _s == "未知":
        return None
    if _s in REGIME_ALIASES:                 # 直配(含複合「復甦/擴張」)
        return REGIME_ALIASES[_s]
    for _k, _v in REGIME_ALIASES.items():    # 子字串 fallback(如剝 emoji 後「成長期」)
        if _k in _s:
            return _v
    return None


def asset_bucket(category):
    """基金類別 → (bucket 名, affinity dict|'ALL') 或 (None, None)。子字串首命中(最特定先)。"""
    _c = str(category or "").strip()
    if not _c:
        return None, None
    for _name, _kws, _aff in ASSET_BUCKETS:
        if any(_kw in _c for _kw in _kws):
            return _name, _aff
    return None, None                        # 無法對應 → 誠實 None(不強歸股票,§1)


def tag_regime_fit(category, role, upside_capture, downside_capture, current_regime) -> dict:
    """→ {best_fit_regimes, fit_vs_current(✅順風/⚠️逆風/⚪全景氣/⬜無法判定), rationale, asset_bucket, source}。"""
    _name, _aff = asset_bucket(category)
    if _name is None:
        return {"best_fit_regimes": [], "fit_vs_current": FIT_LABELS["na"], "asset_bucket": None,
                "source": None, "rationale": "缺基金類別或無法對應資產類別 → 無法判定景氣適配。"}

    if _aff == "ALL":                        # 平衡/多重資產 = 全景氣核心
        return {"best_fit_regimes": ["ALL"], "fit_vs_current": FIT_LABELS["all"], "asset_bucket": _name,
                "source": "平衡", "rationale": f"{category} → 平衡/多重資產(內建股債配置,全景氣可留)。"}

    _score = dict(_aff)                      # {regime: base}
    _cap_notes = []
    _dn = _num(downside_capture)
    _up = _num(upside_capture)
    if _dn is not None and _dn <= DOWNSIDE_DEFENSIVE_MAX:
        _score["高峰"] = _score.get("高峰", 0) + CAPTURE_DEFENSIVE_BONUS
        _score["衰退"] = _score.get("衰退", 0) + CAPTURE_DEFENSIVE_BONUS
        _cap_notes.append(f"下檔捕捉{_dn:.0f}%(抗跌)")
    if _up is not None and _up >= UPSIDE_AGGRESSIVE_MIN:
        _score["復甦"] = _score.get("復甦", 0) + CAPTURE_AGGRESSIVE_BONUS
        _score["擴張"] = _score.get("擴張", 0) + CAPTURE_AGGRESSIVE_BONUS
        _cap_notes.append(f"上檔捕捉{_up:.0f}%(追漲)")

    _mx = max(_score.values()) if _score else 0
    _best = [r for r in REGIMES if _score.get(r, 0) == _mx and _mx > 0]

    _rc = normalize_regime(current_regime)
    if "核心" in str(role or ""):            # 核心 = 全景氣可留(不論景氣)
        _fit, _src = FIT_LABELS["all"], "核心"
    elif _rc is None:                        # 景氣未偵測 → 無法判順逆(仍回 best_fit 供參考)
        _fit, _src = FIT_LABELS["na"], "類別+捕捉"
    elif _rc in _best:
        _fit, _src = FIT_LABELS["tail"], "類別+捕捉"
    else:
        _fit, _src = FIT_LABELS["head"], "類別+捕捉"

    _cap_str = ("、".join(_cap_notes) if _cap_notes else "捕捉率不足,僅依資產類別")
    _rationale = (f"{category} → 適配 {'/'.join(_best) or '—'};{_cap_str};"
                  f"目前景氣「{_rc or '未偵測'}」 → {_fit}(參考傾向,非買賣建議)")
    return {"best_fit_regimes": _best, "fit_vs_current": _fit, "asset_bucket": _name,
            "source": _src, "rationale": _rationale}
