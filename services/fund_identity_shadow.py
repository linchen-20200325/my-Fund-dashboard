# -*- coding: utf-8 -*-
"""DG-2 Stage-1 Shadow comparator：現有各 parser 的結果 vs C+ resolver，只記錄差異（裁示第 9 項）。

輸出：raw input → current parser result → new resolver result → difference → reason。
本檔**不改任何 production 行為**：不寫 UI、不寫 Sheet、不改回傳值；只回傳 dict 或寫 `logging`。
唯一 production 接點：`services/v2_tables/fund_keys.py::resolve_full_keys` 尾端，由
`shared.fund_identity.DG2_SHADOW_ENABLED`（預設 False）把關 —— 關閉時連本檔都不 import。

層級：L2（`services/`）。往下呼叫 L1 parser 與 L0 `infra.cache` 合乎 `CLAUDE.md` §8.2；
通路表 `repositories.fund.sources._BANK_PLATFORM_CODES` 只在本檔綁定、注入給純 resolver，純 resolver 不 import 它。
被比對的 parser 皆為既有私有／公開函式，本檔只呼叫、不修改：
- `parse_moneydj_input`（code）、`canonicalize_moneydj_url`→`parse_moneydj_input`（code）
- `repositories.policy.v1._extract_code_from_url`（舊持股同步的代碼抽取）
- `fund_keys._resolve_one`（vNext；注入 `{}` 對照表，不讀 csv；hook 路徑則直接用 production 已算好的結果）
- `infra.cache._normalize_moneydj_url_for_cache`（cache key 正規化；production 0 呼叫者）
`fund_orchestration.fetch_fund_from_moneydj_url` 內的 fallback regex 是函式內嵌、不可單獨呼叫，未納入（見 `docs/v2/70`）。
"""

from __future__ import annotations

import logging

from infra.cache import _normalize_moneydj_url_for_cache
from repositories.fund.sources import _BANK_PLATFORM_CODES, canonicalize_moneydj_url, parse_moneydj_input
from repositories.policy.v1 import _extract_code_from_url
from services.fund_identity import resolve_fund_identity
from services.v2_tables import fund_keys as _fund_keys

logger = logging.getLogger(__name__)

PARSER_NAMES = ("parse_moneydj_input", "canonicalize_then_parse", "policy_v1_extract_code_from_url",
                "fund_keys_resolve", "cache_normalizer")


def _cache_key_code(raw) -> str:
    key = _normalize_moneydj_url_for_cache(raw)
    parts = key.split("|") if isinstance(key, str) else []
    return parts[1] if len(parts) == 3 and parts[0] == "fetch_fund" else key


def current_parser_results(raw, *, fund_keys_result: dict | None = None) -> dict:
    """各既有 parser 對 `raw` 得到的代碼字串（失敗／非字串輸入記為 None 或錯誤字串）。"""
    text = raw if isinstance(raw, str) else ""
    fk = fund_keys_result if fund_keys_result is not None else _fund_keys._resolve_one(raw, {})
    return {
        "parse_moneydj_input": parse_moneydj_input(text).get("code", ""),
        "canonicalize_then_parse": parse_moneydj_input(canonicalize_moneydj_url(text)).get("code", ""),
        "policy_v1_extract_code_from_url": _extract_code_from_url(text),
        "fund_keys_resolve": fk.get("full_key") if fk.get("ok") else None,
        "cache_normalizer": _cache_key_code(text),
    }


def shadow_compare(raw, *, fund_keys_result: dict | None = None, channel_table=None,
                   alias_mapping=None) -> dict:
    """單筆輸入的 shadow 紀錄。`channel_table` 預設綁定 L1 的 `_BANK_PLATFORM_CODES`。

    `alias_mapping`：hook 傳入 production `resolve_full_keys` 已載入的同一份對照表（不另讀檔）；
    單獨呼叫時預設 `{}`（不做別名）。不傳 `namespace`：裸的帶後綴代碼若不在通路表、也不是 MoneyDJ 網址，
    resolver 照實記 `namespace_unknown_suffix_not_stripped`（Sheet 代碼的命名空間屬 Stage-2 Decision Gate）。
    """
    table = _BANK_PLATFORM_CODES if channel_table is None else channel_table
    ident = resolve_fund_identity(raw, channel_table=table, source="dg2_shadow",
                                  alias_mapping=alias_mapping)
    current = current_parser_results(raw, fund_keys_result=fund_keys_result)
    resolver = {"base_fund_code": ident.base_fund_code, "original_code": ident.original_code,
                "platform_suffix": ident.platform_suffix, "channel_code": ident.channel_code,
                "page_type": ident.page_type, "verification_status": ident.verification_status,
                "error": ident.error}
    difference, reason = {}, []
    for name, value in current.items():
        if value == ident.original_code:
            continue
        difference[name] = value
        if ident.original_code is None:
            reason.append(f"{name}: resolver 判 unresolved（{ident.error}），parser 仍給 {value!r}")
        elif value == ident.base_fund_code:
            reason.append(f"{name}: 得 base {value!r}（剝掉後綴），resolver 保留 original_code {ident.original_code!r}")
        elif not value:
            reason.append(f"{name}: 得空值，resolver 得 {ident.original_code!r}")
        else:
            reason.append(f"{name}: 得 {value!r} ≠ resolver original_code {ident.original_code!r}")
    if ident.platform_suffix:
        reason.append(f"後綴 {ident.platform_suffix!r} 只作通路 metadata；base_fund_code ＝ {ident.base_fund_code!r}"
                      "（所有現有 parser 都保留完整代碼當身分，行動版網址的 canonicalize 例外）")
    return {"raw_input": raw, "current_parser_results": current, "resolver_result": resolver,
            "difference": difference, "reason": reason}


def log_shadow_for_fund_keys(fund_codes, out: dict, *, alias_mapping=None) -> None:
    """`resolve_full_keys` 的 shadow hook：逐筆寫一則 log；不改 `out`、不拋例外（失敗只記 log）。"""
    try:
        for raw, res in zip(fund_codes, out.get("results", [])):
            logger.info("dg2_shadow %r", shadow_compare(raw, fund_keys_result=res, alias_mapping=alias_mapping))
    except Exception:  # shadow 不得影響 production；不吞：完整 traceback 寫進 log
        logger.exception("dg2_shadow 失敗（production 結果未受影響）")
