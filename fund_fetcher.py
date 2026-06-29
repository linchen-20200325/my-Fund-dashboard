# =================================================
# 【Cell 7】寫入 fund_fetcher.py（基金資料抓取引擎）
# 說明：生成基金資料抓取引擎，負責從 MoneyDJ/FundClear 抓取
#        淨值、配息、績效、風險指標等資料。
# 新手提示：直接執行即可，不需要修改。
#            若特定基金無法抓到資料，通常是網站結構變更，
#            請回報給開發者更新解析邏輯。
# =================================================
#!/usr/bin/env python3
"""fund_fetcher.py v6.23
v6.4 修正:
- fetch_performance_wb01(): 雙策略解析，多 URL fallback
- fetch_risk_metrics(): 更強健的欄位偵測，多 URL fallback
v6.3 修正:
- fetch_risk_metrics(): 修正 wb07 row-offset bug（row0=標題, row1=欄頭, row2+=資料）
- peer_compare / yearly_stats 同步修正
v6.2 修正:
- fetch_performance_wb01(): 從績效頁(wb01)取「含息報酬率」(1Y/3Y/5Y)
- fetch_risk_metrics(): 正確解析wb07全欄位(Alpha/Beta/R²/TE/Variance/同類排名/年度比較)
- wb05: 直接讀取「年化配息率%」欄存入 moneydj_div_yield
資料來源：
  搜尋：fundclear.com.tw REST API → MoneyDJ option 選單
  淨值：allianz/chubb子網域 → tcbbankfund.moneydj.com（公開可存取）
  結構：tcbbankfund.moneydj.com（持股/配置/績效）
"""


# ══════════════════════════════════════════════════════════════════
# v11.0 B-9a：TTL 快取裝飾器已搬至 infra/cache.py
# 此處 re-export 維持向後相容（@_ttl_cache / @register_cache decorators 仍可用）
# ══════════════════════════════════════════════════════════════════
from infra.cache import (  # noqa: F401  legacy re-export
    _ttl_cache,
    register_cache,
    clear_all_caches,
    get_all_cache_info,
    _CACHE_REGISTRY,
)

# ══════════════════════════════════════════════════════════════════
# v18.115 B-A：HTTP 層全收口到 infra/proxy.py（消除與 infra 的重複實作）
# 本檔保留 re-export 供向後相容；外部 caller（含 fund_repository）原樣呼叫
# ══════════════════════════════════════════════════════════════════
from infra.proxy import (  # noqa: F401  legacy re-export
    get_proxy_config,
    reset_proxy_cache,
    _proxies,
    _ssl_verify,
    make_retry_session as _make_retry_session,
    install_global_urllib_proxy as _install_global_urllib_proxy,
)


class DataValidationError(Exception):
    """資料驗證失敗：序列筆數不足 20 筆或為常數陣列，阻斷後續 AI 推論。"""
    pass


# ══════════════════════════════════════════════════════════════════
# v18.122 issue 4 真根因修補：HTTP headers / PORTAL_CFG / 子網域映射等常數
# 必須在 `from repositories.fund import ...`（line 219）之前定義
# 否則 fund_repository.py module-level `from fund_fetcher import HDR` 會
# 因 circular import 拿到 partially initialized module → NameError → 各
# _src_* adapter 全 crash → series=0 假象（修了 NAS Proxy / page_type 都沒用）
# ══════════════════════════════════════════════════════════════════
HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": "https://www.moneydj.com/",     # v13 排錯：加 Referer 降低被擋機率
}
HDR_JSON = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Referer": "https://www.fundclear.com.tw/",
}

PORTAL_CFG = {
    "allianz": {
        "base_url":  "https://tcbbankfund.moneydj.com",  # Fix: allianz→tcbbankfund
        "nav_path":  "/w/wf/wf01.djhtm?a={fk}",
        "div_path":  "/w/wh/wh06_4.djhtm?a={fk}",
    },
    "chubb": {
        "base_url":  "https://chubb.moneydj.com",
        "nav_path":  "/w/wf/wf01.djhtm?a={fk}",
        "div_path":  "/w/wh/wh06_4.djhtm?a={fk}",
    },
}
# 台灣合作金庫 MoneyDJ 子網域（公開可存取，同架構）
TCB_BASE = "https://tcbbankfund.moneydj.com"

# v6.8: 保險公司 MoneyDJ 子網域推測（依代碼前綴）
_INSURANCE_SUBDOMAIN_HINTS = {
    "TL":  ["tlife", "twlife", "taiwanlife", "tlins", "tlinsfund"],   # 台灣人壽
    "FL":  ["franklintem", "franklin", "fltempleton", "flintl"],       # 富蘭克林坦伯頓
    "CT":  ["cathaylife", "ctbclife", "ctlife"],                        # 國泰/中信人壽
    "ANZ": ["anz", "anzfund"],                                          # ANZ 銀行
    "JF":  ["jpmorgan", "jpmf", "jpmfund"],                            # JP Morgan
    "NN":  ["ing", "nnfund", "nnip"],                                   # NN Investment
    "FS":  ["fslife", "fubon", "fubonlife"],                            # 富邦人壽
    "NS":  ["nanshan", "nanshanlife"],                                  # 南山人壽
    "CH":  ["chinalife", "chinalifeins"],                               # 中國人壽
    "SN":  ["sinon", "sinonlife"],                                      # 新光人壽
}


# ══════════════════════════════════════════════════════════════════
# v13 排錯補強：統一安全工具函式
# ══════════════════════════════════════════════════════════════════

def safe_float(value, default=None):
    """
    安全把字串轉 float，避免 N/A / -- / 空值 / % 造成 ValueError。
    所有從 MoneyDJ 抓回的欄位一律先走此函式，不要裸 float()。
    """
    if value is None:
        return default
    text = str(value).strip().replace(",", "").replace("%", "")
    if text in ("", "N/A", "n/a", "--", "－", "None", "null", "nan"):
        return default
    try:
        return float(text)
    except Exception:
        return default


def clean_risk_table(risk_table: dict) -> dict:
    """
    清洗 MoneyDJ 風險指標表：
    把 標準差/Sharpe/Alpha/Beta/R-squared/Tracking Error/Variance
    全部轉成 float or None，避免 N/A 字串流入計算。
    """
    NUMERIC = {"標準差", "Sharpe", "Alpha", "Beta",
               "R-squared", "Tracking Error", "Variance", "夏普值"}
    cleaned = {}
    for period, metrics in (risk_table or {}).items():
        cleaned[period] = {}
        for k, v in (metrics or {}).items():
            cleaned[period][k] = safe_float(v) if k in NUMERIC else v
    return cleaned


def fetch_url_with_retry(url, headers=None, params=None,
                         timeout=20, retries=3, sleep_sec=2):
    """MoneyDJ 特化 HTTP fetcher：infra.proxy.fetch_url 薄殼 + Big5 編碼後處理。

    v18.115 B-A：原 ~75 行重複實作（proxy / SSL / 5xx retry / 403 降級直連）已收口到
    infra.proxy.fetch_url；本函式僅保留 MoneyDJ 特化邏輯（Referer + Big5 encoding）。

    Args 同 infra.proxy.fetch_url；sleep_sec 已不使用（infra 內部處理 backoff），
    保留 signature 向後相容。
    """
    from infra.proxy import fetch_url as _infra_fetch_url
    _headers = {
        "Referer": "https://www.moneydj.com/",
    }
    if headers:
        _headers.update(headers)
    resp = _infra_fetch_url(url, headers=_headers, params=params,
                            timeout=timeout, retries=retries)
    if resp is None:
        return None
    # MoneyDJ 全站 Big5 編碼 — 必須強制解碼後文字才正確
    if "moneydj.com" in url:
        resp.encoding = "big5"
    else:
        resp.encoding = resp.apparent_encoding or "utf-8"
    return resp if resp.text.strip() else None


def is_valid_moneydj_page(html: str) -> bool:
    """
    v14.2: 驗證頁面是否為有效的 MoneyDJ 基金頁面。
    MoneyDJ 全站 Big5 編碼，正確解碼後中文可用；
    若編碼有問題則退回數字/日期 pattern 判斷。
    """
    if not html or len(html) < 500:
        return False
    import re as _re_v
    # 中文關鍵字（Big5 正確解碼後）
    keywords = ["淨值", "基金", "日期", "績效", "配息", "除息"]
    if sum(1 for k in keywords if k in html) >= 2:
        return True
    # 備用1：YYYY/MM/DD 日期 + 數字（淨值表格）
    if _re_v.search(r"\d{4}/\d{2}/\d{2}", html) and _re_v.search(r"[\d]{2}\.\d{4}", html):
        return True
    # 備用2：MoneyDJ URL pattern（確認是真正的基金頁）
    # v18.22: 放寬涵蓋 m.moneydj.com / chubb.moneydj.com / tcbbankfund 等子網域
    # —— path 1（中文 keyword）若 Big5 解碼失敗會落空，此 path 兜底
    if "moneydj.com" in html and len(html) > 2000:
        return True
    return False


def classify_fetch_status(fund_data: dict) -> str:
    """
    v13.6: 依資料完整度分類抓取結果。
    **完整 (complete)** 必須同時具備：名稱 + ≥10筆歷史序列 + calc_metrics 指標。
    僅有最新淨值/risk_metrics 不夠，標為 partial（讓 UI 顯示明確提示）。
      'complete' → fund_name + series(≥10) + metrics(非空)
      'partial'  → 有名稱 或 有淨值 或 有 risk_metrics（任一，但缺 series/metrics）
      'failed'   → 幾乎什麼都沒有
    """
    has_name    = bool(fund_data.get("fund_name"))
    s           = fund_data.get("series")
    has_series  = s is not None and hasattr(s, "__len__") and len(s) >= 10
    has_metrics = bool(fund_data.get("metrics"))          # 必須是 calc_metrics 結果
    has_any     = (has_name or
                   fund_data.get("nav_latest") is not None or
                   bool(fund_data.get("risk_metrics")))

    if has_name and has_series and has_metrics:
        return "complete"
    if has_any:
        return "partial"
    return "failed"


def merge_non_empty(dst: dict, src: dict) -> dict:
    """
    v13.5: 欄位級合併，只用 src 中真正有值的欄位更新 dst。
    避免空字串、None、空陣列把已成功抓到的資料覆蓋掉。
    """
    if dst is None:
        dst = {}
    if not src:
        return dst
    for k, v in src.items():
        if v in (None, "", [], {}):
            continue
        dst[k] = v
    return dst


def normalize_result_state(result: dict) -> dict:
    """
    v13.5: 根據實際資料狀態修正 error / warning / status 欄位。
    核心邏輯：
      - complete → 清除所有錯誤
      - partial  → 把「全失敗」改為 warning（不顯示紅字）
      - failed   → 確保有 error 訊息
    """
    status = classify_fetch_status(result)
    _FULL_FAIL_MSG = "❌ 所有來源均無法取得資料"

    if status == "complete":
        result["error"]   = None
        result["warning"] = None
    elif status == "partial":
        # 有資料就不應顯示「全失敗」紅字，改為黃色 warning
        err = result.get("error") or ""
        if "所有來源" in err or err.startswith("❌"):
            result["error"] = None
        if not result.get("warning"):
            result["warning"] = "⚠️ 部分資料取得成功（淨值歷史或風險指標不完整）"
    else:  # failed
        if not result.get("error"):
            result["error"] = _FULL_FAIL_MSG

    result["status"] = status
    return result

# ═════════════════════════════════════════════════════════
# v11.0 B-9b-5：TDCC OpenAPI 整合已搬至 repositories/fund_repository.py
# ═════════════════════════════════════════════════════════
# v19.200 P1-5:repositories.fund_repository 已拆 fund 子套件,本 re-export 走
# try-except 防 circular(若 fund_repository shim init 觸發 fund 子套件 init,
# 期間 fund/sources.py 又從 fund_fetcher import 會 deadlock)。
# 實測 0 active caller `from fund_fetcher import _tdcc*` — 此 try block 為純安全網。
try:
    from repositories.fund import (  # noqa: F401  legacy re-export
        _tdcc_get,
        _src_tdcc_meta,
        tdcc_search_fund,
        tdcc_get_agents,
        _tdcc_resolve_fund_name,
    )
except ImportError:
    pass  # init-time circular — symbols resolve after fund 子套件 init 完成


# ── v11.0 C-12：_RF_ANNUAL + set_risk_free_rate 已搬至 services/fund_service.py ──
from services.fund_service import _RF_ANNUAL, set_risk_free_rate  # noqa: F401

# v18.122: HDR / HDR_JSON / PORTAL_CFG / TCB_BASE / _INSURANCE_SUBDOMAIN_HINTS
# 已搬至本檔頂部（class DataValidationError 後），避免 fund_repository
# circular import 時拿到 partially initialized module → NameError 鏈式崩壞。


# ══════════════════════════════════════════════════════════════════════
# 多來源抓取架構 v13.2
# 依照《基金多來源抓取架構說明書》：
#   來源1 → FundClear / TDCC API（最穩，Colab 友善）
#   來源2 → 鉅亨網 cnyes（Colab 友善）
#   來源3 → tcbbankfund.moneydj.com（MoneyDJ 子網域）
#   來源4 → www.moneydj.com（主站）
#   來源5 → SITCA 公開資料（境內基金）
#   本地快取 → 每日快取，避免重複失敗請求
# ══════════════════════════════════════════════════════════════════════
# v11.0 B-9b-1：disk cache helpers 已搬至 infra/cache.py
# 此處 re-export 維持向後相容（fund_fetcher 內部 _src_* adapter 仍可呼叫）
# ══════════════════════════════════════════════════════════════════════
from infra.cache import (  # noqa: F401  legacy re-export
    _CACHE_DIR,
    _FUND_SNAPSHOT,
    _cache_path,
    _cache_load_nav,
    _cache_save_nav,
    _cache_load_div,
    _cache_save_div,
    _cache_load_meta,
    _cache_save_meta,
)




# ══════════════════════════════════════════════════════════════════════
# v11.0 B-9b-2：Fundclear / AllianzGI adapters 已搬至 repositories/fund_repository.py
# 此處 re-export 維持向後相容（聚合層 _fetch_fund_single 等內部 caller 不變）
# ══════════════════════════════════════════════════════════════════════
try:
    from repositories.fund import (  # noqa: F401  legacy re-export
        _src_fundclear_nav,
        _src_fundclear_meta,
        _src_fundclear_div,
        _src_allianzgi_nav,
        _src_allianzgi_meta,
        _FUND_COMPANY_URLS,
        _ALLIANZ_NAV_ENDPOINT,
        _ALLIANZ_NAV_API,
    )
except ImportError:
    pass  # v19.200 P1-5 circular-safe re-export(0 active caller)


# ════════════════════════════════════════════════════════════
# v11.0 C-12：calc_health_from_manual 已搬至 services/fund_service.py
# ════════════════════════════════════════════════════════════
from services.fund_service import calc_health_from_manual  # noqa: F401

# ══════════════════════════════════════════════════════════════════════
# v11.0 B-9b-3：cnyes / cache_files / bank_platform / Morningstar /
#              Yahoo / Alphavantage adapters 已搬至 repositories/fund_repository.py
# ══════════════════════════════════════════════════════════════════════
try:
    from repositories.fund import (  # noqa: F401  legacy re-export
        _cnyes_parse_navs,
        _cnyes_resolve_code,
        fetch_nav_cnyes,
        fetch_div_cnyes,
        _src_cnyes_nav,
        _src_cnyes_div,
        _src_cache_files,
        _src_bank_platform_nav,
        _morningstar_search_secid,
        _src_morningstar_nav,
        _src_yahoo_finance_nav,
        _src_alphavantage_nav,
        _src_morningstar_meta,
    )
except ImportError:
    pass  # v19.200 P1-5 circular-safe re-export(0 active caller)


# ══════════════════════════════════════════════════════════════════════
# v11.0 B-9b-4：保險公司 / URL canonicalize / 30day / TCB / SITCA adapters
#              已搬至 repositories/fund_repository.py（17 函式）
# ══════════════════════════════════════════════════════════════════════
try:
    from repositories.fund import (  # noqa: F401  legacy re-export
        # 保險公司直連
        probe_insurance_urls,
        _src_taiwanlife_nav,
        _src_franklin_nav,
        _src_jpmorgan_nav,
        # URL canonicalize / domestic code 系列
        load_fund_code_mapping,
        canonicalize_moneydj_url,
        parse_moneydj_input,
        _src_direct_moneydj_url,
        normalize_domestic_code,
        _is_domestic_code,
        get_page_types_to_try,
        # 30day NAV / TCB / SITCA
        _src_nav_30day,
        _src_tcb_nav,
        _src_tcb_meta,
        _src_tcb_div,
        _src_sitca_meta,
        _src_sitca_nav,
    )
except ImportError:
    pass  # v19.200 P1-5 circular-safe re-export(0 active caller)

# ══════════════════════════════════════════════════════════════════════
# v11.0 B-9b-5：多源聚合 + 主入口已搬至 repositories/fund_repository.py
# ══════════════════════════════════════════════════════════════════════
try:
    from repositories.fund import (  # noqa: F401  legacy re-export
        fetch_fund_multi_source,
        _src_insurance_subdomain_nav,
        _fetch_fund_single,
        _finish_metrics,
        fetch_fund_from_moneydj_url,
    )
except ImportError:
    pass  # v19.200 P1-5 circular-safe re-export(0 active caller)

# ════════════════════════════════════════════════════════════
# v11.0 B-9b-6：search / parse_nav / fetch_nav / fetch_div 已搬至 repositories/fund_repository.py
# ════════════════════════════════════════════════════════════
try:
    from repositories.fund import (  # noqa: F401  legacy re-export
        search_fundclear,
        search_moneydj_by_name,
        _parse_nav_html,
        fetch_nav,
        fetch_div,
    )
except ImportError:
    pass  # v19.200 P1-5 circular-safe re-export(0 active caller)


# ════════════════════════════════════════════════════════════
# v11.0 B-9b-6：perf / risk / holdings 已搬至 repositories/fund_repository.py
# ════════════════════════════════════════════════════════════
try:
    from repositories.fund import (  # noqa: F401  legacy re-export
        _fetch_domestic_perf,
        fetch_performance_wb01,
        fetch_risk_metrics,
        fetch_holdings,
    )
except ImportError:
    pass  # v19.200 P1-5 circular-safe re-export(0 active caller)

# ════════════════════════════════════════════════════════════
# v11.0 C-12：calculate_fund_total_return + calc_metrics 已搬至 services/fund_service.py
# ════════════════════════════════════════════════════════════
from services.fund_service import (  # noqa: F401  legacy re-export
    calculate_fund_total_return,
    calc_metrics,
)

# ════════════════════════════════════════════════════════════
# v11.0 B-9b-6：fund_by_key / fund_by_code 已搬至 repositories/fund_repository.py
# ════════════════════════════════════════════════════════════
try:
    from repositories.fund import (  # noqa: F401  legacy re-export
        fetch_fund_by_key,
        fetch_fund_by_code,
    )
except ImportError:
    pass  # v19.200 P1-5 circular-safe re-export(0 active caller)


# ════════════════════════════════════════════════════════════
# v11.0 B-9b-6：structure 已搬至 repositories/fund_repository.py
# ════════════════════════════════════════════════════════════
try:
    from repositories.fund import (  # noqa: F401  legacy re-export
        STRUCTURE_PAGES,
        _parse_pct_table,
        fetch_fund_structure,
    )
except ImportError:
    pass  # v19.200 P1-5 circular-safe re-export(0 active caller)

# ════════════════════════════════════════════════════════════
# v11.0 C-12：calc_dividend_estimate 已搬至 services/fund_service.py
# ════════════════════════════════════════════════════════════
from services.fund_service import calc_dividend_estimate  # noqa: F401

# ════════════════════════════════════════════════════════════
# v11.0 B-10：fetch_market_news 已抽至 repositories/news_repository.py
# 此處 re-export 維持向後相容（caller 從 fund_fetcher import fetch_market_news 仍可用）
# ════════════════════════════════════════════════════════════
from repositories.news_repository import fetch_market_news  # noqa: F401


# ══════════════════════════════════════════════════════════════════════
# v11.0 B-9b-6：Universal Ledger 已搬至 repositories/fund_repository.py
# ══════════════════════════════════════════════════════════════════════
try:
    from repositories.fund import (  # noqa: F401  legacy re-export
        get_latest_fx,
        get_latest_nav,
    )
except ImportError:
    pass  # v19.200 P1-5 circular-safe re-export(0 active caller)


# ════════════════════════════════════════════════════════════════════════
# v19.200 P1-5:PEP 562 lazy __getattr__ — 延遲 repositories.fund_repository
# re-export 至 caller 取用時(避免 fund_repository shim 拆 fund 子套件後的
# init-time circular import)。
# ════════════════════════════════════════════════════════════════════════
def __getattr__(name: str):
    """延遲 attribute 解析:caller `from fund_fetcher import X` 觸發本 fn,
    動態 forward 至 repositories.fund subpackage(v19.235 R1:shim 已退役)。"""
    if name.startswith('__'):
        raise AttributeError(f"module 'fund_fetcher' has no attribute {name!r}")
    try:
        from repositories import fund as _fr
        return getattr(_fr, name)
    except (ImportError, AttributeError):
        raise AttributeError(f"module 'fund_fetcher' has no attribute {name!r}")
