"""ui/helpers/portfolio/fee_deduction.py — 持股頁「換扣款標的」決策區(v19.511)。L3。

把持倉 + T7 帳本轉成 `services.policy_fee_optimizer` 引擎輸入,依**保單**分組試算「這個月
該從哪一檔基金扣管理費、還是直接台幣現金扣」,渲染燈號 + 推薦 + 誠實免責。

設計(user 2026-08-22 三決策):
  1. **依保單分組、各自輸入每月管理費**(app 無此欄位 → UI 輸入,存 session;§4.1 TWD 金額)。
  2. **沒建 T7 帳本的檔** = 缺 units / 成本基礎 → **誠實標「需 T7 帳本」排除**(§1 不用
     invest_twd 硬估、不靜默),另列清單引導使用者去 T7 建帳本解鎖評分。
  3. **台幣基金納入扣款候選**(user「台幣基金也納入扣款候選」):TWD_CASH 情境下,若有足額、
     成本已知、非低檔(score>=0.90)的台幣基金,渲染引擎的 `twd_fund_alt`(依 loss_pct 挑擾動
     最小者)作「免匯率風險的保單內扣款替代」——**平行非優於現金**,現金仍首選(§1 三 AI 會審)。

§8.2:`build_fee_inputs` 為**純函式**(nav/fx 由 caller 注入 → 可單測、零 I/O、零 streamlit);
     render 才做 I/O(get_latest_nav / get_latest_fx)+ streamlit,與 T7 `_latest_nav_fx_t7`
     同精神(該函式為 render_t7_section 內 nested、不可 import,故此處等效重建注入器)。
§1:引擎已守 fee<=0 raise / 壞資料排除;本層再把「無帳本」與「抓不到 nav/匯率」誠實分流。
"""
from __future__ import annotations

from typing import Callable, Optional


def _pos_val(ledger, attr: str) -> Optional[float]:
    """安全取 ledger.position.<attr> → float 或 None(§1 不硬給)。"""
    try:
        v = getattr(getattr(ledger, "position", None), attr, None)
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def build_fee_inputs(funds: list, ledgers_by_pk: dict,
                     nav_fx_fn: Callable[[dict], tuple]) -> tuple:
    """持倉 → 引擎輸入。**純函式**(nav/fx 由 `nav_fx_fn(fund)->(nav_原幣, fx)` 注入)。

    Args:
        funds: 一組持倉 dict(通常同一保單);每筆需 code/name/currency,pk 由 fund_pk_str 算。
        ledgers_by_pk: {fund_pk_str: Ledger}——成本/單位來源(position.units/cost_unit/fx_avg)。
        nav_fx_fn: fund → (current_nav 原幣 or None, fx or None)。render 端注入真 I/O 解析器。

    Returns:
        (engine_funds, excluded, rate_map)
          engine_funds: [{id,name,currency,units,current_nav,cost_nav,cost_rate}] 可餵引擎。
          excluded:     [{id,name,reason}] 誠實排除(需帳本 / 抓不到 nav / 抓不到匯率)。
          rate_map:     {CCY: fx}——組引擎 exchange_rates(TWD 恆 1.0)。
    """
    from models.policy import fund_pk_str
    from services.currency import normalize_ccy

    engine_funds: list = []
    excluded: list = []
    rate_map: dict = {"TWD": 1.0}

    for f in funds or []:
        _pk = fund_pk_str(f)
        _name = str(f.get("name") or f.get("code") or _pk)
        _led = (ledgers_by_pk or {}).get(_pk)
        _units = _pos_val(_led, "units") if _led is not None else None
        # 決策②:無帳本 or 單位<=0 → 需 T7 帳本(§1 不用 invest_twd 硬估單位)
        if _led is None or _units is None or not (_units > 0):
            excluded.append({"id": _pk, "name": _name,
                             "reason": "需 T7 帳本(無持有單位/成本基礎)"})
            continue

        _ccy = normalize_ccy(f.get("currency", ""), default="")
        if not _ccy:
            excluded.append({"id": _pk, "name": _name, "reason": "缺計價幣別"})
            continue

        _nav, _fx = nav_fx_fn(f)
        try:
            _nav = float(_nav) if _nav is not None else None
        except (TypeError, ValueError):
            _nav = None
        if _nav is None or not (_nav > 0):
            excluded.append({"id": _pk, "name": _name, "reason": "抓不到目前淨值"})
            continue
        if _ccy != "TWD":
            try:
                _fx = float(_fx) if _fx is not None else None
            except (TypeError, ValueError):
                _fx = None
            if _fx is None or not (_fx > 0):
                excluded.append({"id": _pk, "name": _name, "reason": f"抓不到 {_ccy} 即期匯率"})
                continue
            rate_map[_ccy] = _fx

        # 成本基礎(帳本;None → 引擎走 is_cost_estimated,不假裝真實基期)
        engine_funds.append({
            "id": _pk,
            "name": _name,
            "currency": _ccy,
            "units": _units,
            "current_nav": _nav,                     # 原幣(引擎自乘匯率,勿預乘)
            "cost_nav": _pos_val(_led, "cost_unit"),
            "cost_rate": _pos_val(_led, "fx_avg"),
        })

    return engine_funds, excluded, rate_map


# ───────────────────────── L3 render(streamlit + I/O)─────────────────────────

def _make_nav_fx_fn():
    """回傳 fund → (nav_原幣, fx) 的解析器(等效 T7 `_latest_nav_fx_t7`,該函式 nested 不可 import)。

    NAV:L2 `services.fund_service.get_latest_nav`(v19.511 稽核:走 L2 facade,不直呼 L1);
         失敗退 fund['series'] 末值。
    FX :L2 `services.fund_service.get_latest_fx`(內部自動補 `=X` + 正規化);TWD → 1.0。
         **抓不到即期匯率 → None**(§1:上層誠實排除,**不**用歷史買入匯率冒充現價 —— 這是
         與 T7 `_latest_nav_fx_t7` 刻意的分歧,避免把 avg buy-rate 當 spot 產生假市值)。
    """
    from services.currency import normalize_ccy
    from services.fund_service import get_latest_fx, get_latest_nav

    def _resolve(fund: dict) -> tuple:
        _code = str(fund.get("code", "")).strip()
        _ccy = normalize_ccy(fund.get("currency", ""), default="")
        _nav = None
        try:
            _nav = get_latest_nav(_code)
        except Exception:  # noqa: BLE001 — 抓不到 → 退 series(§1 由上層排除,不假值)
            _nav = None
        if _nav is None:
            _s = fund.get("series")
            try:
                if _s is not None and len(_s.dropna()):
                    _nav = float(_s.dropna().iloc[-1])
            except Exception:  # noqa: BLE001
                _nav = None
        if _ccy == "TWD":
            _fx = 1.0
        else:
            try:
                _fx = get_latest_fx(f"{_ccy}TWD") if _ccy else None
            except Exception:  # noqa: BLE001 — 抓不到 → None,上層排除(不冒充現價)
                _fx = None
        return _nav, _fx

    return _resolve


def render_fee_deduction_section(funds: list) -> None:
    """持股頁「🔻 換扣款標的決策」區:依保單分組,各自輸入月費 → 引擎試算 → 燈號 + 推薦。

    §1:引擎/建構器的誠實旗標全渲染(排除清單、成本未知、免責);任何例外收成 caption 不炸 Tab3。
    """
    import streamlit as st

    st.divider()
    st.markdown("### 🔻 換扣款標的決策(每月保單管理費要從哪扣)")
    st.caption("定期檢視:這個月的保單管理費,該從哪一檔基金扣(挑高檔停利減損)、還是直接台幣現金扣。"
               "**依保單各自試算**(管理費只能從同一張保單內扣)。")

    _funds = [f for f in (funds or []) if f.get("loaded") and not f.get("load_error")]
    if not _funds:
        st.info("尚無已載入的持倉 → 先在上方載入基金再回來試算。")
        return

    from services.policy_fee_optimizer import DISCLAIMER, optimize_policy_fee

    _ledgers = st.session_state.get("t7_ledgers", {}) or {}
    _nav_fx = _make_nav_fx_fn()

    # 依保單分組(policy_id → (policy_name, [funds]))。
    # v19.511 稽核修:缺 policy_id 的檔**不**併成一個假保單跨比 —— 不同保單的基金互比會違反
    # 「管理費只能從同一張保單內扣」(§1 不靜默混戶),改另列提醒引導補標記。
    _by_policy: dict = {}
    _untagged: list = []
    for f in _funds:
        _pid = str(f.get("policy_id") or "").strip()
        if not _pid:
            _untagged.append(f)
            continue
        _pname = str(f.get("policy_name") or "").strip() or "(未命名保單)"
        _by_policy.setdefault(_pid, (_pname, []))[1].append(f)

    if _untagged:
        _un_names = "、".join(str(f.get("name") or f.get("code") or "?") for f in _untagged[:12])
        st.caption(f"⬜ {len(_untagged)} 檔缺保單標記(policy_id),未納入試算"
                   f"(避免不同保單的基金被跨保單互比):{_un_names}"
                   f"{' …' if len(_untagged) > 12 else ''}。→ 在政策表補 policy_id 即可歸戶試算。")

    if not _by_policy:
        st.info("目前沒有可歸戶到保單的持倉可試算(見上方缺標記清單)。")
        return

    for _pid, (_pname, _pfunds) in _by_policy.items():
        st.markdown(f"#### 📄 {_pname}")
        _fee = st.number_input(
            "每月保單管理費(TWD)", min_value=0.0, step=100.0, value=0.0,
            key=f"_feeopt_fee_{_pid}",
            help="保險公司每月固定收取的管理/行政規費(台幣)。app 無此欄位,請自行輸入。",
        )
        if not (_fee > 0):
            st.caption("↑ 輸入每月管理費即開始試算(管理費 > 0)。")
            continue

        try:
            _engine_funds, _excluded, _rates = build_fee_inputs(_pfunds, _ledgers, _nav_fx)
            if not _engine_funds:
                st.warning("本保單目前**無可評估標的**(全部缺 T7 帳本或抓不到淨值/匯率,見下方清單)。")
            else:
                _res = optimize_policy_fee(_fee, _rates, _engine_funds)
                # ── 一句話結論(user 2026-08-22「只要一句話結論」;細節收進下方摺疊)──
                if _res["recommendation"] == "FUND_DEDUCTION":
                    st.success(f"**✅ 本月建議:從【{_res['top_pick_name']}】扣款**"
                               "　—— 該檔目前在高檔,贖回單位最少(等於高點停利)。")
                else:
                    st.info("**💵 本月建議:用台幣現金扣款**"
                            "　—— 目前沒有基金在高檔,從基金扣等於低點賤賣單位,不如付現金保住部位。")
                    # 台幣基金安全扣款候選(user 2026-08-22「台幣基金也納入扣款候選」)。
                    # 現金仍是首選(零擾動、保留複利);此為「保單只能內扣 / 不想動現金」時的
                    # 免匯率風險替代,**平行非優於現金**(§1 誠實護欄,三位 AI 專家會審)。
                    _alt = _res.get("twd_fund_alt")
                    if _alt:
                        _sub = ""
                        # 0.90<=score<1.0:略低於成本 → 賣它會實現小幅虧損(非停利點);>=1.0 才是無虧損賣點。
                        if _alt.get("score") is not None and _alt["score"] < 1.0:
                            _sub = (f" ⚠️ 此檔目前略低於成本(評分 {_alt['score']:.2f}),從中扣款會實現"
                                    "小幅虧損,僅省去匯率風險、非停利點。")
                        st.markdown(
                            f"🏦 **或改從台幣基金【{_alt['name']}】扣**:台幣計價、免匯率風險,"
                            f"對部位擾動最小(佔比 {_alt['loss_pct']:.2f}%)。{_sub}")
                        st.caption("(平行選項,非優於現金:付現金零擾動、保留複利;從台幣基金扣仍會贖回"
                                   "單位、放棄該部位複利,差別只在「動用保單內部位」還是「外部現金」,"
                                   "依手邊現金是否充裕自行取捨。)")

                with st.expander("看細節(判斷理由 / 各檔燈號 / 評分拆解 / 免責)", expanded=False):
                    st.caption(_res["annotation"])
                    import pandas as pd

                    def _badge_zh(fe):
                        if fe.get("error"):
                            return "⚠️ 資料異常"
                        if fe.get("is_cost_estimated"):
                            return "⬜ 成本未知"
                        return {"SUCCESS": "🟢 高檔", "WARNING": "🟡 正常",
                                "DANGER": "🔴 低檔"}.get(fe.get("badge_level"), "—")

                    _rows = [{
                        "基金": fe["name"][:20],
                        "幣別": fe["currency"],
                        "燈號": _badge_zh(fe),
                        "評分 S": (f"{fe['score']:.3f}" if fe.get("score") is not None else "—"),
                        "└基金報酬×匯兌": (
                            f"{fe['return_factor']:.3f}×{fe['fx_factor']:.3f}"
                            if fe.get("return_factor") is not None else "—"),
                        "扣款佔比%": (f"{fe['loss_pct']:.2f}%" if fe.get("loss_pct") is not None else "—"),
                        "贖回單位": (f"{fe['units_deduct']:.4f}" if fe.get("units_deduct") is not None else "—"),
                        "市值TWD": (f"{fe['market_value_twd']:,.0f}" if fe.get("market_value_twd") is not None else "—"),
                        "足額": ("✔ 足額" if fe.get("is_sufficient") else "✗ 不足"),
                    } for fe in _res["funds"]]
                    st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)
                    st.caption(DISCLAIMER)

            if _excluded:
                _names = "、".join(f"{e['name']}({e['reason']})" for e in _excluded[:12])
                st.caption(f"⬜ 未納入試算 {len(_excluded)} 檔:{_names}"
                           f"{' …' if len(_excluded) > 12 else ''}。"
                           "→ 到上方「💼 T7 帳本」為這些檔建立買入紀錄,即可解鎖成本評分。")
        except ValueError as _e:   # 引擎 §1 fail-loud(理論上 fee>0 已擋)
            st.error(f"試算失敗:[{type(_e).__name__}] {str(_e)[:80]}")
        except Exception as _e:    # noqa: BLE001 — 任何例外收成提示,不炸 Tab3
            st.caption(f"⬜ 本保單試算略過:[{type(_e).__name__}] {str(_e)[:80]}")
