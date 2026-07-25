"""mcp_server/tools_macro.py — macro 工具的**純邏輯**(不依賴 fastmcp,可單元測試)。

`build_macro_snapshot` 只做「呼 L2 → 組 dict」的 orchestration,零業務判斷、零 IO 自寫:
指標抓取(`fetch_all_indicators`)、加權評分(`calculate_composite_score`)、位階
(`calc_macro_phase`)、買賣燈(`macro_action_light`)、regime、雙演算法對帳
(`reconcile_composite_score`)全部走既有 `services/macro/*`(和 Streamlit UI 同一批函式)。

§1 Fail-Loud:缺 FRED_API_KEY 或全源失敗 → **raise**(不回半空的假分數)。
raise 由 server.py 的 `error_envelope` 攔成結構化錯誤回給 AI caller。
"""
from __future__ import annotations

import os

# ── L2 imports(和 UI 同一批;放 module top 讓測試可 monkeypatch)──────────
from services.macro import (
    calc_macro_phase,
    fetch_all_indicators,
    identify_regime,
    macro_action_light,
)
from services.macro.composite_score import (  # composite_score 未在 __init__ re-export
    calculate_composite_score,
    composite_verdict,
    reconcile_composite_score,
)


class MacroSnapshotError(RuntimeError):
    """macro 快照無法產生(缺 key / 全源失敗)—— §1 誠實炸掉,不回假數字。"""


def build_macro_snapshot(fred_api_key: str | None = None) -> dict:
    """組出當前美國總經健康度快照(供 MCP `get_macro_snapshot` 工具呼叫)。

    Args:
        fred_api_key: FRED API key;None → 讀 `os.environ["FRED_API_KEY"]`
                      (headless 路徑,不走 st.secrets)。

    Returns:
        dict — composite_score / verdict / phase / action_light / regime /
        reconciliation / alerts / provenance。**尚未** JSON 正規化,
        交給 `error_envelope`→`to_json_safe` 在邊界統一處理。

    Raises:
        MacroSnapshotError: 缺 FRED key,或 `fetch_all_indicators` 回空
                            (全來源失敗)—— §1 不以半空假分數矇混。
    """
    key = fred_api_key if fred_api_key is not None else os.environ.get("FRED_API_KEY", "")
    if not key:
        raise MacroSnapshotError(
            "FRED_API_KEY 未設定 —— 無法抓取總經指標。請在環境變數設定後重試。"
        )

    ind = fetch_all_indicators(key)
    if not ind or not isinstance(ind, dict):
        raise MacroSnapshotError(
            "fetch_all_indicators 回傳空 —— 所有總經來源失敗(FRED / Yahoo / PMI fallback 全敗)。"
        )

    # 加權健康度總分 + opt-in provenance 側車(§2.2)
    prov: dict = {}
    total = calculate_composite_score(ind, provenance_out=prov)
    icon, level, _color, action_text = composite_verdict(total)

    # 景氣位階(0-10)→ 餵買賣燈
    phase = calc_macro_phase(ind) or {}
    phase_score = phase.get("score")
    light = macro_action_light(ind, phase_score)

    regime = identify_regime(ind)
    recon = reconcile_composite_score(ind)

    return {
        "composite_score": total,
        "verdict": {"icon": icon, "level": level, "action": action_text},
        "phase": {
            "score_10": phase_score,
            "name": phase.get("phase"),
            "phase_en": phase.get("phase_en"),
            "rec_prob_pct": phase.get("rec_prob"),
        },
        "action_light": light,
        "regime": regime,
        "reconciliation": recon,
        "alerts": phase.get("alerts", []),
        "provenance": {
            "sources": prov.get("sources"),
            "fetched_at_latest": prov.get("fetched_at_latest"),
            "n_indicators": prov.get("n_indicators"),
        },
    }
