"""ui/helpers/portfolio/fee_deduction.py — 持股頁「換扣款標的」決策區(v19.511)。L3。

把持倉 + T7 帳本轉成 `services.policy_fee_optimizer` 引擎輸入,依**保單**分組試算「這個月
該從哪一檔基金扣管理費、還是直接台幣現金扣」,渲染燈號 + 推薦 + 誠實免責。

設計(user 2026-08-22 三決策):
  1. **依保單分組、各自輸入每月管理費**(app 無此欄位 → UI 輸入,存 session;§4.1 TWD 金額)。
  2. **沒建 T7 帳本的檔** = 缺 units / 成本基礎 → **誠實標「需 T7 帳本」排除**(§1 不用
     invest_twd 硬估、不靜默),另列清單引導使用者去 T7 建帳本解鎖評分。
  3. **台幣基金納入扣款候選**(user「台幣基金也納入扣款候選」):渲染引擎 `twd_fund_alt`
     (足額、成本已知、非低檔、依 loss_pct 挑擾動最小的台幣基金)作「免匯率風險的保單內扣款替代」。
  4. **同保單容錯併組 + 一律點名最適標的**(user 2026-08-23):
     - 分組鍵 `policy_id` 正規化(`_norm_policy_key`:大小寫/空白/全半形不分),同一張保單被打成
       'P1'/'p1' 等相近字串仍併回同一組,美元+台幣標的一起比;標題顯示實際 policy_id(非「未命名」)。
     - 一律點名引擎 `top_pick`(組內最高 S=匯率×淨值)並依分帶誠實標示(高檔停利 / 成本之上 /
       略低於成本實現虧損 / 低檔賤賣);is_cost_estimated 先於分帶標「成本未知」。現金/台幣基金
       退為 band-gated 次要(S<0.90 現金升強次要)。§1 三 AI 會審措辭(不用「最適」超級詞、不提「擾動最小」)。

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


def _norm_policy_key(policy_id) -> str:
    """保單代號正規化(僅供**分組**用,不改底層 policy_id / fund_pk):
    NFKC(全形→半形)+ 去頭尾/收斂內部空白 + casefold(大小寫不分)。
    目的:同一張保單在政策表被打成 'P1' / 'p1' / '　P1 ' 等相近字串時,仍併回同一組互比
    (user 2026-08-23 確認「同保單要一起比」);字串實質不同的 genuine 不同保單不會被誤併。
    """
    import unicodedata
    s = unicodedata.normalize("NFKC", str(policy_id or ""))
    s = " ".join(s.split())          # 收斂頭尾 + 內部連續空白
    return s.casefold()


def _group_funds_by_policy(funds: list) -> tuple:
    """依保單分組(policy_id 正規化容錯併組)。**純函式**,回 (groups, untagged)。

    groups: 保序 list[{key, display, funds, raw_ids}]
      key     = 正規化分組鍵(widget key / 迭代用)
      display = 組內第一個非空 policy_name;皆空 → 代表 policy_id(**原字串**非正規化)——
                對齊 app 其他處 `policy_name or policy_id`(tab3_portfolio:1486),不再顯示「未命名」。
      raw_ids = 組內出現過的原始 policy_id(去重保序);len>1 → UI 提示回 Sheet 統一。
    untagged: 缺 policy_id(正規化後空)的檔,誠實排除,不跨保單互比(§1 不靜默混戶)。
    """
    groups: list = []
    index: dict = {}          # norm_key → groups 索引
    untagged: list = []
    for f in funds or []:
        _raw = str(f.get("policy_id") or "").strip()
        _key = _norm_policy_key(_raw)
        if not _key:
            untagged.append(f)
            continue
        if _key not in index:
            index[_key] = len(groups)
            groups.append({"key": _key, "display": "", "funds": [], "raw_ids": []})
        g = groups[index[_key]]
        g["funds"].append(f)
        if _raw and _raw not in g["raw_ids"]:
            g["raw_ids"].append(_raw)
        if not g["display"]:                      # 第一個非空 policy_name 勝出
            _pn = str(f.get("policy_name") or "").strip()
            if _pn:
                g["display"] = _pn
    for g in groups:                              # display 收尾:退代表 policy_id(非「未命名」)
        if not g["display"]:
            g["display"] = g["raw_ids"][0] if g["raw_ids"] else g["key"]
    return groups, untagged


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
    st.caption("定期檢視:這個月的保單管理費,該從哪一檔標的扣 —— **依匯率(美元/台幣)× 淨值高低**"
               "排出組內 S 最高的標的並點名。**依保單各自試算**(管理費只能從同一張保單內扣)。")

    _funds = [f for f in (funds or []) if f.get("loaded") and not f.get("load_error")]
    if not _funds:
        st.info("尚無已載入的持倉 → 先在上方載入基金再回來試算。")
        return

    from services.policy_fee_optimizer import (
        SCORE_HIGH,
        SCORE_LOW,
        DISCLAIMER,
        optimize_policy_fee,
    )

    _ledgers = st.session_state.get("t7_ledgers", {}) or {}
    _nav_fx = _make_nav_fx_fn()

    # 依保單分組(policy_id 正規化容錯併組;user 2026-08-23「同一張保單要一起比」)。
    # 缺 policy_id 的檔**不**併成一個假保單跨比 —— 不同保單的基金互比會違反「管理費只能從
    # 同一張保單內扣」(§1 不靜默混戶),改另列提醒引導補標記。
    _groups, _untagged = _group_funds_by_policy(_funds)

    if _untagged:
        _un_names = "、".join(str(f.get("name") or f.get("code") or "?") for f in _untagged[:12])
        st.caption(f"⬜ {len(_untagged)} 檔缺保單標記(policy_id),未納入試算"
                   f"(避免不同保單的基金被跨保單互比):{_un_names}"
                   f"{' …' if len(_untagged) > 12 else ''}。→ 在政策表補 policy_id 即可歸戶試算。")

    if not _groups:
        st.info("目前沒有可歸戶到保單的持倉可試算(見上方缺標記清單)。")
        return

    for _g in _groups:
        _pfunds = _g["funds"]
        st.markdown(f"#### 📄 {_g['display']}")
        if len(_g["raw_ids"]) > 1:               # 併了相近但不同字串的 policy_id → 誠實揭露
            st.caption("⬜ 本組已合併相近的保單代號:「" + "」「".join(_g["raw_ids"]) + "」"
                       "(大小寫/空白/全半形差異,視為同一張保單一起比)。"
                       "建議到政策表把 policy_id 統一,其他頁面(如保單分組)才會一致。")
        _fee = st.number_input(
            "每月保單管理費(TWD)", min_value=0.0, step=100.0, value=0.0,
            key=f"_feeopt_fee_{_g['key']}",
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
                # ── 一律點名組內最適標的(user 2026-08-23「找到適合扣款的標的,匯率×淨值」)──
                # top_pick = 組內最高 S(依匯率×淨值)足額標的。誠實護欄(§1,AI 會審):
                #   - 標題**描述性**點名(不用「最適」超級詞,虧損時避免讀成「該賣」)。
                #   - 判斷由分帶 note 承擔;**不**提「擾動最小」(那是 loss_pct 軸=twd_fund_alt,非 S 軸)。
                #   - is_cost_estimated 先於分帶處理:S 為推定不可當高/低檔判斷。
                #   - 現金/台幣基金為 band-gated 次要選項;S<0.90 現金升為強次要。
                _top = _res.get("top_pick")
                if _top is None:
                    # 情境 C:無足額標的 → 誠實只能現金(不點名不存在的標的)
                    st.info("**💵 本保單目前無可扣標的**(全部餘額不足或資料異常)→ 只能用台幣現金扣款。")
                else:
                    _name = _top["name"]
                    _ccy = _top.get("currency") or ""
                    _s = _top.get("score")
                    _rf = _top.get("return_factor")
                    _fx = _top.get("fx_factor")
                    _est = bool(_top.get("is_cost_estimated"))
                    _decomp = (f"　(S={_s:.3f} = 淨值報酬 {_rf:.3f} × 匯兌 {_fx:.3f})"
                               if (_s is not None and _rf is not None and _fx is not None) else "")
                    _head = (f"**本月要從基金扣的話 → 【{_name}】({_ccy})**"
                             f"　組內依匯率×淨值排序最高{_decomp}")
                    _alt = _res.get("twd_fund_alt")
                    _alt_txt = (f"或改台幣基金【{_alt['name']}】扣(免匯率風險、台幣計價)"
                                if (_alt and _alt.get("name") != _name) else "")

                    if _est:                       # 成本未知:S 推定,不可當高/低檔
                        st.warning(_head)
                        st.caption("⬜ 此檔成本未知,S 以持平推定(≈1.0)、非真實高/低檔;僅代表組內排序首位,"
                                   "**不表示在成本之上**。建議先到「💼 T7 帳本」補此檔買入成本再判斷,"
                                   "或這個月先用台幣現金扣款。" + (("　" + _alt_txt) if _alt_txt else ""))
                    elif _s is not None and _s >= SCORE_HIGH:   # 🟢 高檔
                        # §1:不宣稱「贖回單位相對少」——贖回單位 = F/V 只跟當前單位市值有關、與 S 無關
                        # (engine docstring);高分只代表相對成本在高檔=順勢停利,不等於扣得單位少。
                        st.success(_head + "　🟢 目前在高檔(成本之上),從它扣=順勢停利,是相對最佳時機。")
                    elif _s is not None and _s >= 1.0:          # 🟡 成本之上、非高檔(1.0=損益兩平定義值)
                        st.info(_head + "　🟡 在成本之上、但非明顯高檔;要動基金就它最划算"
                                "(尚無未實現虧損),惟非明確停利點。")
                        _sec = "其他選項:也可用台幣現金扣款(零擾動、保留複利)"
                        st.caption(_sec + ((";" + _alt_txt) if _alt_txt else "") + "。")
                    elif _s is not None and _s >= SCORE_LOW:    # 🟠 略低於成本
                        st.warning(_head + "　🟠 已略低於成本,從它扣會實現小幅虧損(非停利點);"
                                   "它只是組內 S 最高。")
                        _sec = "其他選項:若手邊有現金,可優先付台幣現金(避免實現虧損、保留複利)"
                        st.caption(_sec + ((";" + _alt_txt) if _alt_txt else "") + "。")
                    else:                                       # 🔴 低檔(S<0.90)
                        st.warning(_head + f"　🔴 目前在低檔,扣任何標的都在賤賣;【{_name}】只是組內相對最不差。")
                        _sec = "建議優先用台幣現金扣款(避免低點實現虧損)"
                        st.caption(_sec + ((";" + _alt_txt) if _alt_txt else "") + "。")

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
            # ⚠️ 2026-08-28 顏色批次二之一：**刻意不改色,不是漏改**。同 checkup.py ——
            # 這行住在 `for _g in _groups:` 的逐保單迴圈裡,就地改紅 = N 張保單
            # N 個紅框（M1 的原病）。正解是彙總,屬結構改動,已登記待後批。
            # （上面那行 `except ValueError` 已經是 st.error,顏色本來就對。）
            st.caption(f"⬜ 本保單試算略過:[{type(_e).__name__}] {str(_e)[:80]}")
