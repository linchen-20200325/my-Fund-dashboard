"""Tab2（單一基金深度分析）UI 契約守門。

本檔守的是「畫面說的話必須是真的」這一類缺陷 —— 它們全部通過 lint、通過既有
單元測試、每一段單獨看都正確，但線上呈現是錯的：

  * 資料新鮮度條讀了一個從來不存在的欄位 → 永遠顯示「未知」
  * 年化配息率取不到時被回退成數值 0 → 有配息的基金顯示 0.00%
  * metric 的 help 硬寫「官方」，但值可能是本地自算
  * 對帳 chip 被關在「有配息」分支裡 → 累積型基金永遠看不到
  * 一份憑印象填的常數表被當成市場統計印在畫面上
  * 服務層算好並實際生效的降級旗標，UI 端 0 consumer

多數測試走 AST 而非字串掃描：AST 會剝掉註解，測試才不會被「解釋這件事的註解」
自己弄紅，也不會因為文案微調就假性失敗。

執行環境：純靜態解析 + 一個純函式單元測試，不啟動 Streamlit runtime。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
TAB2 = ROOT / "ui" / "tab2_single_fund.py"


@pytest.fixture(scope="module")
def src() -> str:
    return TAB2.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def tree(src: str) -> ast.AST:
    return ast.parse(src, filename=str(TAB2))


# ══════════════════════════════════════════════════════════════
# 小工具
# ══════════════════════════════════════════════════════════════
def _calls_to_attr(tree: ast.AST, attr: str):
    """yield 所有 `<任意物件>.<attr>(...)` 的 Call node。"""
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == attr):
            yield node


def _calls_to_name(tree: ast.AST, names: set[str]):
    """yield 所有 `<name>(...)` 的 Call node（name 需在 names 內）。"""
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in names):
            yield node


def _first_arg_const(call: ast.Call):
    if call.args and isinstance(call.args[0], ast.Constant):
        return call.args[0].value
    return None


def _kwarg(call: ast.Call, key: str):
    for kw in call.keywords:
        if kw.arg == key:
            return kw.value
    return None


def _dict_keys(node: ast.AST) -> set[str]:
    if not isinstance(node, ast.Dict):
        return set()
    return {k.value for k in node.keys
            if isinstance(k, ast.Constant) and isinstance(k.value, str)}


def _mentions_name(node: ast.AST, name: str) -> bool:
    return any(isinstance(n, ast.Name) and n.id == name for n in ast.walk(node))


def _simple_assignments(tree: ast.AST) -> dict[str, ast.AST]:
    """`x = <expr>`（單一 Name target）→ {x: expr}，供解一層區域變數轉手。"""
    out: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            out.setdefault(node.targets[0].id, node.value)
    return out


def _mentions_name_resolved(node: ast.AST, name: str, assigns: dict[str, ast.AST],
                            depth: int = 3) -> bool:
    """檢查運算式是否（可能經過幾層區域變數轉手後）用到某個名字。"""
    if _mentions_name(node, name):
        return True
    if depth <= 0:
        return False
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and n.id in assigns:
            if _mentions_name_resolved(assigns[n.id], name, assigns, depth - 1):
                return True
    return False


# ══════════════════════════════════════════════════════════════
# T1. 資料新鮮度條必須讀得到 NAV 日期
# ══════════════════════════════════════════════════════════════
# 修正前：紅（舊行為衝突紅）。原本 nav_date / fetched_at 都從 `fd` 取，
# 而 session_state.fund_data 的字典字面量根本沒有這兩個 key，兩個欄位恆為空
# 字串 → banner 恆為「⬜ ?/—/—」。fetcher 是把它們寫在 moneydj_raw 裡的。
def test_freshness_banner_reads_nav_date_from_fetcher_payload(tree: ast.AST) -> None:
    calls = list(_calls_to_name(tree, {"render_mj_freshness_banner"}))
    assert calls, "Tab2 應仍渲染資料新鮮度條"

    assigns = _simple_assignments(tree)
    checked = 0
    for call in calls:
        assert call.args, "新鮮度條需傳入 items list"
        items = call.args[0]
        dicts = [n for n in ast.walk(items) if isinstance(n, ast.Dict)]
        assert dicts, "items 應為 dict 字面量組成的 list"
        for d in dicts:
            for k, v in zip(d.keys, d.values):
                if not (isinstance(k, ast.Constant) and k.value in ("nav_date", "fetched_at")):
                    continue
                checked += 1
                assert _mentions_name_resolved(v, "mj_raw", assigns), (
                    f"新鮮度條的 {k.value} 必須取自 fetcher 回傳的原始 payload"
                    "（Tab⑤ 組合層就是這樣取的）；只從 session 外層字典取會恆為空值。"
                )
    assert checked >= 2, "應同時檢查 nav_date 與 fetched_at 兩個欄位"


# ══════════════════════════════════════════════════════════════
# T2. 序列稀疏降級旗標必須有 UI consumer（PROCESS.md §4 接線驗證）
# ══════════════════════════════════════════════════════════════
# 修正前：紅（舊行為衝突紅）。fund_service 判定序列稀疏時會**真的**把
# sortino / calmar / 自算 sharpe / std_1y~5y 打成 None，但整個 ui/ 底下
# 0 命中 —— 使用者只看到欄位變「—」，看不到「是我們主動砍的」。
# 這條測試在「把那段 banner 拿掉」時必須變紅，否則它就是無效測試。
@pytest.mark.parametrize("flag", ["is_sparse", "sparse_reason", "nav_coverage"])
def test_sparse_downgrade_flags_have_ui_consumer(tree: ast.AST, flag: str) -> None:
    hits = [
        c for c in _calls_to_attr(tree, "get")
        if _first_arg_const(c) == flag
    ]
    assert hits, (
        f"metrics['{flag}'] 由服務層算好且會實際移除年化指標，"
        "UI 端必須讀出來告訴使用者，否則等於沉默降級。"
    )


# ══════════════════════════════════════════════════════════════
# T3. 1Y 報酬對帳不得被「有沒有配息」擋住
# ══════════════════════════════════════════════════════════════
# 修正前：紅（舊行為衝突紅）。chip 被包在 `if divs and len(divs) >= 1:` 內，
# 累積型 / 不配息基金永遠看不到這條對帳，即使兩套算法差很大。
def test_ret_1y_reconcile_not_gated_by_dividend_records(tree: ast.AST) -> None:
    def _is_div_gate(node: ast.AST) -> bool:
        """辨識 `if divs ...:` 這種以配息記錄為條件的分支。"""
        if not isinstance(node, ast.If):
            return False
        return any(isinstance(n, ast.Name) and n.id == "divs"
                   for n in ast.walk(node.test))

    gates = [n for n in ast.walk(tree) if _is_div_gate(n)]
    assert gates, "Tab2 應仍有以配息記錄為條件的分支（否則本測試失去對象）"

    offenders = []
    for gate in gates:
        for stmt in gate.body:
            for n in ast.walk(stmt):
                if isinstance(n, ast.Constant) and n.value == "ret_1y_reconcile":
                    offenders.append(gate.lineno)
    assert not offenders, (
        f"1Y 報酬對帳被關在配息分支內（行 {offenders}）。"
        "這條對帳比的是本地自算 1Y 報酬 vs 官方值，與有無配息無關。"
    )
    # 反向確認：它確實還在畫面上，不是被整條刪掉充數。
    assert any(isinstance(n, ast.Constant) and n.value == "ret_1y_reconcile"
               for n in ast.walk(tree)), "1Y 報酬對帳 chip 不應被移除"


# ══════════════════════════════════════════════════════════════
# T4. 年化配息率：缺值顯破折號 + help 必須說出實際來源
# ══════════════════════════════════════════════════════════════
_ADR_LABEL = "年化配息率"


def _adr_metric_calls(tree: ast.AST) -> list[ast.Call]:
    return [c for c in _calls_to_attr(tree, "metric")
            if _first_arg_const(c) == _ADR_LABEL]


# 修正前：紅（舊行為衝突紅）。原本末端 `or 0` 把三層都取不到的情況轉成數值 0，
# 而該分支的前提正是「這檔有配息記錄」→ 畫面主張「有配息、配息率是零」。
def test_annual_dividend_rate_has_missing_value_branch(tree: ast.AST) -> None:
    calls = _adr_metric_calls(tree)
    assert calls, f"Tab2 應仍顯示「{_ADR_LABEL}」metric"
    dash_branch = [
        c for c in calls
        if len(c.args) >= 2 and isinstance(c.args[1], ast.Constant)
        and c.args[1].value == "—"
    ]
    assert dash_branch, (
        f"「{_ADR_LABEL}」必須有一條「取不到 → 顯示破折號」的分支；"
        "回退成 0 會被讀成「這檔不配息」。"
    )


# 修正前：紅（舊行為衝突紅）。兩處 help 都是寫死的字串常數，其中一處宣稱值來自
# 官方欄位，但實際可能是本地自算 → provenance 說謊。
def test_annual_dividend_rate_help_declares_actual_source(tree: ast.AST) -> None:
    offenders = []
    for c in _adr_metric_calls(tree):
        value_arg = c.args[1] if len(c.args) >= 2 else None
        if not isinstance(value_arg, ast.JoinedStr):
            continue  # 顯示破折號的缺值分支不需要動態來源說明
        help_arg = _kwarg(c, "help")
        if not isinstance(help_arg, ast.JoinedStr):
            offenders.append(c.lineno)
    assert not offenders, (
        f"行 {offenders}：有數值時，「{_ADR_LABEL}」的 help 必須由實際命中的"
        "來源層動態組出（f-string），不可寫死成固定字串 —— 三層 fallback 走到"
        "第二/三層時，寫死的「官方」字樣就是在幫自算值掛官方背書。"
    )


# ══════════════════════════════════════════════════════════════
# T5. 吃本金結論不得繞過畫面同一組 SSOT
# ══════════════════════════════════════════════════════════════
# 修正前：紅（舊行為衝突紅）。AI 快照直接餵 metrics 原始欄位給吃本金判定，
# 而畫面 KPI 走的是兩個 SSOT helper → 同一頁可能一邊紅燈一邊說覆蓋充足。
def test_dividend_safety_not_fed_raw_metrics(tree: ast.AST) -> None:
    offenders = []
    for call in _calls_to_name(tree, {"div_safety_check"}):
        for key in ("total_return", "dividend_yield", "nav_change"):
            arg = _kwarg(call, key)
            if arg is None:
                continue
            # `m.get(...)` = 直接吃 metrics 原始欄位，繞過 SSOT
            if (isinstance(arg, ast.Call)
                    and isinstance(arg.func, ast.Attribute)
                    and arg.func.attr == "get"
                    and isinstance(arg.func.value, ast.Name)
                    and arg.func.value.id == "m"):
                offenders.append((call.lineno, key))
    assert not offenders, (
        f"{offenders}：吃本金判定的輸入必須與畫面 KPI 同源"
        "（含息總報酬 / 年化配息率兩個 SSOT helper），"
        "直接讀 metrics 原始欄位會讓 AI 解盤與同頁紅綠燈互相矛盾。"
    )


# ══════════════════════════════════════════════════════════════
# T6. 不得出現「字串 → 數字」的憑空常數對照表
# ══════════════════════════════════════════════════════════════
# 修正前：紅（舊行為衝突紅）。檔內有一份 11 筆的類別→費率對照表，自稱是市場
# 常見水準，但無來源、無抓取時間、無樣本、無定義，卻和旁邊真的抓來的經理費
# 並排顯示。§1 禁止「自行估一個合理值當常數」。
#
# 用結構特徵（key 全是字串常數、value 全是數字常數）而不是掃關鍵字，
# 這樣「解釋為什麼移除」的註解與說明文案不會把測試自己弄紅。
_LOOKUP_TABLE_MIN_ENTRIES = 4


def test_no_fabricated_string_to_number_lookup_table(tree: ast.AST) -> None:
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        if len(node.keys) < _LOOKUP_TABLE_MIN_ENTRIES:
            continue
        if any(k is None for k in node.keys):
            continue  # 有 **unpack，不是單純字面表
        keys_ok = all(isinstance(k, ast.Constant) and isinstance(k.value, str)
                      for k in node.keys)
        vals_ok = all(isinstance(v, ast.Constant)
                      and isinstance(v.value, (int, float))
                      and not isinstance(v.value, bool)
                      for v in node.values)
        if keys_ok and vals_ok:
            offenders.append(node.lineno)
    assert not offenders, (
        f"行 {offenders}：偵測到寫死在 UI 層的「名稱 → 數值」對照表。"
        "這類表通常是憑印象填的基準值，畫面上與真實抓取值無法區分。"
        "若確實是有來源的常數，請放進 shared/ 的 SSOT 模組並附出處與 as_of。"
    )


# ══════════════════════════════════════════════════════════════
# T7. 接近警戒門檻走 SSOT，不在 UI 端另刻一份
# ══════════════════════════════════════════════════════════════
# 修正前：紅（舊行為衝突紅）。UI 端 fallback 自己寫了一個與 SSOT 同義的浮點常數。
def test_near_threshold_imported_from_shared_ssot(tree: ast.AST) -> None:
    imported = {
        alias.name
        for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        and (node.module or "").startswith("shared.signal_thresholds")
        for alias in node.names
    }
    assert "NEAR_DIVIDEND_WARNING_PCT" in imported, (
        "買賣點「接近警戒」門檻的 fallback 必須 import shared SSOT，"
        "不可在 UI 端另寫一份同義數字（§3.3 反捏造）。"
    )


# ══════════════════════════════════════════════════════════════
# T8. 1Y 含息報酬 payload 不得漏欄位
# ══════════════════════════════════════════════════════════════
# 修正前：紅（舊行為衝突紅）。累積型分支那一次呼叫漏了 series / perf_source，
# 導致官方欄位與本地序列兩條路都走不到 → 同頁「1Y 含息報酬」有值，
# 「1Y 後預估市值」卻顯示破折號。
_TR1Y_REQUIRED_KEYS = {"metrics", "moneydj_raw", "series", "perf_source"}


def test_total_return_payload_always_complete(tree: ast.AST) -> None:
    aliases = {"compute_1y_total_return"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "compute_1y_total_return":
                    aliases.add(alias.asname or alias.name)

    calls = list(_calls_to_name(tree, aliases))
    assert calls, "Tab2 應仍透過共用 helper 取 1Y 含息報酬"

    offenders = []
    for call in calls:
        if not call.args or not isinstance(call.args[0], ast.Dict):
            continue
        missing = _TR1Y_REQUIRED_KEYS - _dict_keys(call.args[0])
        if missing:
            offenders.append((call.lineno, sorted(missing)))
    assert not offenders, (
        f"{offenders}：1Y 含息報酬 payload 缺欄位。"
        "缺 series / perf_source 會讓 fallback chain 提前斷掉，"
        "同一頁兩個本該一致的數字因此一個有值、一個顯示破折號。"
    )


# ══════════════════════════════════════════════════════════════
# T9. 摺疊處置 —— 資料型區塊不得預設收起
# ══════════════════════════════════════════════════════════════
# 修正前：紅（舊行為衝突紅）。個股新聞 / 微觀防護盾抓完仍要再點一次才看得到；
#  3-3-3 評估輸出的是結論卻預設收起。
#
# 允許維持收起的只有「輸入工具」與「推導過程」兩類（結論數字已在上方 metric）。
_ALLOWED_COLLAPSED_TITLES = {
    "🔍 關鍵字搜尋境外基金（TDCC / FundClear）",
    "📐 完整計算公式（含數字代入）",
}


def test_only_input_and_derivation_blocks_stay_collapsed(tree: ast.AST) -> None:
    offenders = []
    for call in _calls_to_attr(tree, "expander"):
        exp = _kwarg(call, "expanded")
        if not (isinstance(exp, ast.Constant) and exp.value is False):
            continue
        title = _first_arg_const(call)
        if title not in _ALLOWED_COLLAPSED_TITLES:
            offenders.append((call.lineno, title))
    assert not offenders, (
        f"{offenders}：資料 / 結論型摺疊區塊不得預設收起。"
        "抓完還要再點一次才看得到 = 使用者以為功能沒作用。"
        f"目前允許維持收起的只有：{sorted(_ALLOWED_COLLAPSED_TITLES)}"
    )


# ══════════════════════════════════════════════════════════════
# T10. 純函式單元測試（會真的 import 模組）
# ══════════════════════════════════════════════════════════════
# 修正前：紅（ImportError 紅）—— `_recon_zh` / `_RECON_STATUS_ZH` 當時不存在。
_RISK_TABLE_FIXTURE = {
    "一年": {"標準差": 12.5, "Sharpe": 0.61, "Alpha": 1.2,
             "Beta": 0.95, "Tracking Error": 3.4},
}


@pytest.fixture(scope="module")
def tab2_mod():
    """真正 import Tab2 模組（fund_fetcher 先載以解 circular，比照既有 smoke test）。"""
    import fund_fetcher  # noqa: F401
    import importlib
    return importlib.import_module("ui.tab2_single_fund")


def test_recon_status_translated_to_chinese(tab2_mod) -> None:
    _RECON_STATUS_ZH = tab2_mod._RECON_STATUS_ZH
    _recon_zh = tab2_mod._recon_zh
    for status in _RECON_STATUS_ZH:
        out = _recon_zh(status)
        assert status not in out, f"{status} 未被翻譯，英文狀態碼直接露到畫面上"
        assert out.strip(), "翻譯結果不可為空"


def test_recon_status_unknown_code_passes_through(tab2_mod) -> None:
    """未知碼原樣帶出 —— 不可靜默吞掉變空字串（§1）。"""
    assert "brand_new_status" in tab2_mod._recon_zh("brand_new_status")


def test_recon_status_map_covers_rendered_statuses(tab2_mod) -> None:
    """漂移鎖：UI 過濾用的白名單與翻譯表必須完全一致。"""
    assert set(tab2_mod._RECON_VALID) == set(tab2_mod._RECON_STATUS_ZH)
    # 兩邊都缺值時服務層另有一個狀態，UI 刻意不渲染（沒有任何可比的東西），
    # 因此它不該出現在白名單裡。
    assert "both_missing" not in tab2_mod._RECON_VALID


# 修正前：第一條紅（舊行為衝突紅）—— long 版原本也印 Sharpe，與上方帶期間標籤的
# Sharpe 格重複，而後者資訊嚴格較多。
def test_complete_view_risk_rows_omit_duplicated_sharpe(tab2_mod) -> None:
    html = tab2_mod._risk_1y_rows_html(_RISK_TABLE_FIXTURE, label_style="long")
    assert "Sharpe" not in html, "完整視圖的風險列不應再重複一次 Sharpe"
    assert "Alpha(1Y)" in html and "Beta(1Y)" in html, "其餘風險列必須保留"


def test_partial_view_risk_rows_keep_sharpe(tab2_mod) -> None:
    """partial 視圖上方沒有帶期間標籤的 Sharpe 格，所以這裡仍要留。"""
    html = tab2_mod._risk_1y_rows_html(_RISK_TABLE_FIXTURE)
    assert "Sharpe(1Y)" in html


def test_risk_rows_missing_table_renders_dashes(tab2_mod) -> None:
    """邊界：空表 / 缺欄位 → 一律破折號，不得填 0（§1）。"""
    html = tab2_mod._risk_1y_rows_html({})
    assert "—" in html
    assert ">0<" not in html and ">0.00<" not in html


def test_annual_dividend_source_labels_cover_ssot_chain(tab2_mod) -> None:
    """漂移鎖：來源說明表必須涵蓋 SSOT resolver 會回傳的每一個層級標籤。

    修正前：紅（ImportError 紅）—— 這張對照表當時不存在，畫面用寫死字串。
    """
    labels = tab2_mod._ADR_SRC_ZH
    expected = {"moneydj_wb05", "metrics_annual_div_rate", "divs_12m_sum"}
    assert expected <= set(labels), (
        f"年化配息率來源說明缺少：{sorted(expected - set(labels))}；"
        "缺哪一層，那一層命中時畫面就說不出自己的來源。"
    )
    assert all(v.strip() for v in labels.values())
