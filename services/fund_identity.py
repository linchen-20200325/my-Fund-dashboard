# -*- coding: utf-8 -*-
"""DG-2 Stage-1：C+ canonical fund identity resolver（L2 純函式，Shadow Mode）。

客戶裁示 `DEC-2026-10-28-05`（逐字：`docs/evidence/decisions/2026-10-28_dg2_identity_ruling.md`）：
`TLZF9`／`TLZF9-AL001`／`TLZF9-24A7` 原則上是同一檔核心基金，`base_fund_code = TLZF9`；
平台後綴另存為通路 metadata，**不得**當成新的基金身份；但有證據顯示後綴是不同 series 時
不得硬合併（例外 → Decision Gate）。ISIN 不依賴；currency／share class／配息／避險沒有可靠資料時一律 Unknown。

**本檔只回答「這是哪一檔基金」**（裁示第 11 項）。NAV 一致性另由 `check_cross_view_nav` 判，兩者不混。

**本階段（Shadow Mode）不接任何 production 路徑**：沒有任何 production 呼叫端使用本檔的結果；
唯一的 hook 在 `services/v2_tables/fund_keys.py`，且由 `shared.fund_identity.DG2_SHADOW_ENABLED`（預設 False）
把關、只寫 log（見 `services/fund_identity_shadow.py`）。

**復用既有邏輯（舊 UI 稽核分類 ADAPT，`docs/v2/70`〈舊 UI reuse matrix〉）**，不另造第三套文法：
- 輸入關卡：`services/v2_tables/fund_keys.py::_resolve_one`（ASCII 限定、只認查詢字串的 `a=`、`#` 片段切掉、
  多個 `a=` 不同即失敗、最終 `_is_pure_code`）。直接呼叫 `_resolve_one` 而非 `resolve_full_keys`，
  是為了不觸發該函式尾端的 shadow hook（hook 開啟時會回呼本檔 → 否則無窮遞迴）。
- 頁型：`repositories/fund/sources.py::parse_moneydj_input` 的 `page_type`（僅作 metadata）。
- 基本碼：第一個 `-` 之前＝基金碼（`canonicalize_moneydj_url` 的 `split("-", 1)[0]`；與 `fund_keys._is_pure_code`
  的 `partition("-")` 同一切法）——~~但**對所有輸入一致套用**，不只行動版網址。~~
  → 2026-10-28 獨立稽核 MUST 1（有意識的更正，不是漏刪）：**只在 MoneyDJ／平台代碼命名空間套用**。
  FundClear 級別碼 `AGIF-HT5`（累積）／`AGIF-HTG`（A 配息）也有 `-`，卻是**不同級別**；盲目剝會把它們合併。
  命名空間證據（任一即可）：呼叫端 `namespace="moneydj"`；網址被 `parse_moneydj_input` 認出 MoneyDJ 頁型；
  完整代碼在注入的通路表內。沒有證據 → `namespace_unknown_suffix_not_stripped`（不剝、不合併）；
  明示其他命名空間 → `out_of_scope_namespace`。無 `-` 的代碼不受影響。
- 2026-10-29 客戶最終裁示 `DEC-2026-10-29-01`（逐字：`docs/evidence/decisions/2026-10-29_dg2_final_ruling.md`）：
  (1) MoneyDJ 命名空間內也**只剝已驗證的後綴**（通路表命中，或 L0 `CUSTOMER_CONFIRMED_SUFFIXES`）；
  有 MoneyDJ 證據但後綴未驗 → `moneydj_suffix_unverified_not_stripped`（不剝、不合併）。
  (2) `input_source="sheet_fund_code_column"`＝呼叫端宣告值取自 Google Sheet「基金代號」欄 → 命名空間固定 MoneyDJ、
  值須為基本代碼；帶 `-`／網址／格式不符 → `sheet_code_contract_violation`（原值保留在 `raw_input`，不剝不截不改寫）。
  只適用於該欄，不得推廣到其他 code。(3) 頁型：網址明示者記 `page_type_source="url"` 與 `url_page_market`；
  裸碼一律 Unknown，不用前綴推斷（`docs/v2/70` 第 15 節）。
- 通路表：呼叫端注入（形狀同 `sources._BANK_PLATFORM_CODES`：`{base: [(domain, full_code, page_type), ...]}`）。
  本檔**不** import 那張 L1 私有表；綁定在 `services/fund_identity_shadow.py`。

規則（`CLAUDE.md` §1）：不猜、不補值；壞輸入給明確 `unresolved`；形狀錯的注入參數直接拋例外。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Optional

from repositories.fund.sources import parse_moneydj_input
from services.v2_tables import fund_keys as _fund_keys
from shared.fund_identity import (
    CANDIDATE_ACCEPTED,
    CANDIDATE_REJECTED,
    CANDIDATE_UNVERIFIED,
    CUSTOMER_CONFIRMED_SUFFIXES,
    IDENTITY_EXCEPTIONS,
    INPUT_SOURCE_NAMESPACES,
    MONEYDJ_PAGE_MARKET,
    NAMESPACE_MONEYDJ,
    NAV_CONFLICT,
    NAV_CONSISTENT,
    NAV_NOT_COMPARABLE,
    PAGE_TYPE_SOURCE_URL,
    SOURCE_CONFLICT_TEXT,
    STATUS_BASE_RESOLVED,
    STATUS_EXCEPTION,
    STATUS_NAMESPACE_UNKNOWN,
    STATUS_OUT_OF_SCOPE_NAMESPACE,
    STATUS_SHEET_CONTRACT_VIOLATION,
    STATUS_SUFFIX_UNVERIFIED,
    STATUS_UNRESOLVED,
    SUFFIX_PROVENANCE_CHANNEL_TABLE,
    UNKNOWN,
)

DEFAULT_SOURCE = "services.fund_identity.resolve_fund_identity"

# 身分屬性（不含 base 碼）；外部候選驗證與後綴證據都比這幾個。
_ATTRS = ("currency", "share_class", "distribution_type", "hedge_status")

# §4.3：浮點比較用容差，不用 ==。
_REL_TOL = 1e-9
_ABS_TOL = 1e-12

SAME = "same"
DIFFERENT = "different"
UNKNOWN_CMP = "unknown"

_UNSTRIPPED = frozenset({STATUS_NAMESPACE_UNKNOWN, STATUS_OUT_OF_SCOPE_NAMESPACE, STATUS_SUFFIX_UNVERIFIED})
_NO_CODE = frozenset({STATUS_UNRESOLVED, STATUS_SHEET_CONTRACT_VIOLATION})


@dataclass(frozen=True)
class CanonicalFundIdentity:
    """一筆輸入的身分解析結果。`canonical_key` 只在 `verification_status == STATUS_BASE_RESOLVED` 時有值。"""

    base_fund_code: Optional[str]
    original_code: Optional[str]  # 輸入裡的完整代碼（大寫；含後綴）
    platform_suffix: Optional[str]  # 第一個 `-` 之後；無後綴＝None
    channel_code: Optional[str]  # 通路表命中的平台網域；有後綴但查不到＝Unknown；無後綴＝None
    source_url: Optional[str]  # 網址輸入原樣保留；裸碼＝None
    currency: str = UNKNOWN
    share_class: str = UNKNOWN
    distribution_type: str = UNKNOWN
    hedge_status: str = UNKNOWN
    isin: Optional[str] = None  # optional verification attribute；缺了不警告、不影響 matching
    source: str = DEFAULT_SOURCE
    as_of: Optional[str] = None
    verification_status: str = STATUS_UNRESOLVED
    page_type: str = ""  # parse_moneydj_input 的頁型（metadata，不參與身分）
    raw_input: object = None
    error: Optional[str] = None
    # 2026-10-29（`DEC-2026-10-29-01`）新增，皆為 metadata／evidence，不參與 `same_canonical_fund`：
    input_source: Optional[str] = None  # 呼叫端宣告的輸入來源（目前只有 Sheet 基金代號欄）
    suffix_provenance: Optional[str] = None  # 剝後綴所依據的已驗證 mapping（channel_table／customer_confirmed_…）
    page_type_source: str = UNKNOWN  # "url"＝網址明示；裸碼＝Unknown（不推斷）
    url_page_market: str = UNKNOWN  # 網址頁型 yp010000→domestic、yp010001→offshore；其餘 Unknown

    @property
    def canonical_key(self) -> Optional[str]:
        return self.base_fund_code if self.verification_status == STATUS_BASE_RESOLVED else None


def is_unknown(value) -> bool:
    return value is None or value == UNKNOWN or (isinstance(value, str) and not value.strip())


def compare_attribute(a, b) -> str:
    """任一邊 Unknown → `unknown`（既不相同也不相異）；兩邊皆已知 → `same`／`different`。"""
    if is_unknown(a) or is_unknown(b):
        return UNKNOWN_CMP
    return SAME if str(a).strip().upper() == str(b).strip().upper() else DIFFERENT


def same_canonical_fund(a: CanonicalFundIdentity, b: CanonicalFundIdentity) -> Optional[bool]:
    """`True`／`False`／`None`（未定：任一邊 unresolved／Sheet 契約違反、命名空間未知、後綴未驗，或同 base 但任一邊是例外待裁）。

    命名空間未知／範圍外／後綴未驗的代碼只在**完整代碼逐字相同**時判 True，其餘一律 None（不剝後綴、不合併）。
    """
    if {a.verification_status, b.verification_status} & _NO_CODE:
        return None
    if {a.verification_status, b.verification_status} & _UNSTRIPPED:
        return True if (a.original_code is not None and a.original_code == b.original_code) else None
    if a.base_fund_code != b.base_fund_code:
        return False
    if STATUS_EXCEPTION in (a.verification_status, b.verification_status):
        return None
    return True


def _clean_attr(value, *, upper: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        return UNKNOWN
    v = value.strip()
    if v.upper() == UNKNOWN.upper():
        return UNKNOWN
    return v.upper() if upper else v


def _as_of_text(as_of) -> Optional[str]:
    if as_of is None:
        return None
    iso = getattr(as_of, "isoformat", None)
    return iso() if callable(iso) else str(as_of)


def _lookup_channel(channel_table, base: str, full_code: str) -> str:
    if channel_table is None:
        return UNKNOWN
    if not isinstance(channel_table, dict):
        raise TypeError(f"channel_table 須為 dict（收到 {type(channel_table).__name__}）")
    entries = channel_table.get(base, ())
    if not isinstance(entries, (list, tuple)):
        raise TypeError(f"channel_table[{base!r}] 須為 list／tuple（收到 {type(entries).__name__}）")
    for entry in entries:
        if not isinstance(entry, (list, tuple)) or len(entry) < 2:
            raise TypeError(f"channel_table[{base!r}] 的條目須為 (domain, full_code, ...)（收到 {entry!r}）")
        domain, code = entry[0], entry[1]
        if isinstance(code, str) and code.strip().upper() == full_code:
            return str(domain)
    return UNKNOWN


def _sheet_contract_violation(raw) -> Optional[str]:
    """Sheet「基金代號」欄的基本代碼契約（`DEC-2026-10-29-01` 第 4 項）。合格回 None；否則回原因（不改寫原值）。

    合格＝去前後空白後非空、ASCII、不是網址、不含 `-`、且符合 `fund_keys._is_pure_code`（`[A-Z0-9]{3,30}`）。
    大小寫與前後空白沿用 `fund_keys` 對照鏈第 0～2 步（`strip()`、`upper()`；L2 `alo_holdings._key_text` 也只去前後空白）
    —— 這是執行組讀法，未經客戶逐條確認。
    """
    if not isinstance(raw, str):
        return f"Sheet 基金代號欄的值不是字串（{type(raw).__name__}）"
    text = raw.strip()
    if not text:
        return "Sheet 基金代號欄的值是空白"
    if not text.isascii():
        return "Sheet 基金代號欄的值含非 ASCII 字元；原值保留、不改寫"
    if text.lower().startswith("http"):
        return "Sheet 基金代號欄的值是網址，不是 MoneyDJ 基本代碼；原值保留、不解析不改寫"
    if "-" in text:
        return "Sheet 基金代號欄的值含 '-'，不符 MoneyDJ 基本代碼契約；原值保留、不剝除不截斷"
    if not _fund_keys._is_pure_code(text.upper()):
        return "Sheet 基金代號欄的值不符 MoneyDJ 基本代碼格式（[A-Z0-9]{3,30}）；原值保留、不截斷"
    return None


def resolve_fund_identity(raw, *, channel_table=None, exceptions=None, as_of=None,
                          source: str = DEFAULT_SOURCE, alias_mapping=None, namespace=None,
                          input_source=None,
                          currency=None, share_class=None, distribution_type=None,
                          hedge_status=None, isin=None) -> CanonicalFundIdentity:
    """裸碼（任意大小寫）、帶後綴代碼、MoneyDJ 桌面／行動版／平台子網域網址、`#fragment`、`area=TW&a=CODE`
    → `CanonicalFundIdentity`。

    `currency`／`share_class`／`distribution_type`／`hedge_status`／`isin`：只有呼叫端握有**可靠來源**時才給；
    沒給一律 Unknown（`isin` 為 None）。本函式**不會**從名稱、後綴或幣別推任何一個（裁示第 4 項）。
    `alias_mapping`：`fund_keys` 形狀的別名表；預設 `{}`（不讀 csv、不做別名）。
    `exceptions`：`(base, suffix)` 集合；預設 `shared.fund_identity.IDENTITY_EXCEPTIONS`（空）。
    `namespace`：`None`（由網址頁型／通路表／客戶確認表找證據）、`"moneydj"`（呼叫端擔保是 MoneyDJ／平台代碼）、
    其他字串（明示非 MoneyDJ → 帶 `-` 者判 `out_of_scope_namespace`）。見檔頭「基本碼」一條。
    `input_source`：`None` 或 `shared.fund_identity.INPUT_SOURCE_NAMESPACES` 的鍵（目前只有
    `"sheet_fund_code_column"`）；給了即套該來源的契約與命名空間，與 `namespace` 衝突或未知值 → `ValueError`。
    後綴只在 MoneyDJ 證據**且**已驗證 mapping（通路表或客戶確認表）命中時才剝（`DEC-2026-10-29-01`）。
    """
    mapping = {} if alias_mapping is None else alias_mapping
    if alias_mapping is not None:
        _fund_keys._check_injected_mapping(mapping)
    excs = IDENTITY_EXCEPTIONS if exceptions is None else frozenset(exceptions)
    common = dict(source=source, as_of=_as_of_text(as_of), raw_input=raw, input_source=input_source)

    if input_source is not None:
        if input_source not in INPUT_SOURCE_NAMESPACES:
            raise ValueError(f"未知的 input_source {input_source!r}（只收 {sorted(INPUT_SOURCE_NAMESPACES)}）")
        declared = INPUT_SOURCE_NAMESPACES[input_source]
        if namespace is not None and namespace != declared:
            raise ValueError(f"input_source {input_source!r} 的命名空間是 {declared!r}，與 namespace={namespace!r} 衝突")
        namespace = declared
        violation = _sheet_contract_violation(raw)
        if violation:
            return CanonicalFundIdentity(base_fund_code=None, original_code=None, platform_suffix=None,
                                         channel_code=None, source_url=None,
                                         verification_status=STATUS_SHEET_CONTRACT_VIOLATION, error=violation,
                                         **common)

    gate = _fund_keys._resolve_one(raw, mapping)
    if not gate["ok"]:
        return CanonicalFundIdentity(base_fund_code=None, original_code=None, platform_suffix=None,
                                     channel_code=None, source_url=None,
                                     verification_status=STATUS_UNRESOLVED, error=gate["error"], **common)

    full_key = gate["full_key"]
    base, sep, tail = full_key.partition("-")
    suffix = tail if sep else None
    info = parse_moneydj_input(raw.strip())
    is_url = bool(info.get("is_url"))
    page_type = info.get("page_type", "") or ""
    page_meta = dict(page_type=page_type,
                     page_type_source=PAGE_TYPE_SOURCE_URL if (is_url and page_type) else UNKNOWN,
                     url_page_market=MONEYDJ_PAGE_MARKET.get(page_type, UNKNOWN) if is_url else UNKNOWN)
    attrs = dict(currency=_clean_attr(currency, upper=True), share_class=_clean_attr(share_class),
                 distribution_type=_clean_attr(distribution_type), hedge_status=_clean_attr(hedge_status))
    channel = _lookup_channel(channel_table, base, full_key) if suffix else None
    customer = CUSTOMER_CONFIRMED_SUFFIXES.get((base, suffix)) if suffix else None
    isin_v = isin.strip().upper() if isinstance(isin, str) and isin.strip() else None
    provenance = None
    if suffix:
        verified = channel != UNKNOWN or customer is not None
        if namespace is not None and namespace != NAMESPACE_MONEYDJ:
            unstripped = STATUS_OUT_OF_SCOPE_NAMESPACE
        elif not (namespace == NAMESPACE_MONEYDJ or (is_url and page_type) or verified):
            unstripped = STATUS_NAMESPACE_UNKNOWN
        elif not verified:
            unstripped = STATUS_SUFFIX_UNVERIFIED  # DEC-2026-10-29-01：MoneyDJ 證據有、後綴未驗 → 不剝
        else:
            unstripped = None
            provenance = (SUFFIX_PROVENANCE_CHANNEL_TABLE if channel != UNKNOWN else customer["provenance"])
        if unstripped:
            return CanonicalFundIdentity(
                base_fund_code=None, original_code=full_key, platform_suffix=None, channel_code=None,
                source_url=raw.strip() if is_url else None, isin=isin_v, verification_status=unstripped,
                **attrs, **page_meta, **common)
    status = STATUS_EXCEPTION if (suffix and (base, suffix) in excs) else STATUS_BASE_RESOLVED
    return CanonicalFundIdentity(
        base_fund_code=base, original_code=full_key, platform_suffix=suffix, channel_code=channel,
        source_url=raw.strip() if is_url else None, isin=isin_v, verification_status=status,
        suffix_provenance=provenance, **attrs, **page_meta, **common)


# ═══════════════ 例外路徑（裁示第 2 項）：有證據就不合併 ═══════════════


def _nav_float(value, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{where}：nav 須為數值（收到 {value!r}）")
    v = float(value)
    if not math.isfinite(v) or v <= 0:
        raise ValueError(f"{where}：nav 須為有限正數（收到 {value!r}）")
    return v


def evaluate_suffix_evidence(obs_a: dict, obs_b: dict, *, namespace: str = NAMESPACE_MONEYDJ,
                             channel_table=None) -> Optional[dict]:
    """同 base、不同完整代碼的兩筆觀測 → 若有**區分性證據**回例外紀錄，否則回 None。

    區分性證據：兩邊皆已知且不同的 currency／share_class／distribution_type／hedge_status；
    或同 `nav_date`、同已知 currency 下 NAV 不相等（容差 §4.3）。
    ⚠️ 回 None **不代表**已證明相同，只代表本次觀測沒有區分性證據。
    每筆觀測須含 `fund_code`；其餘鍵選填：`nav`／`nav_date`／`currency`／`share_class`／
    `distribution_type`／`hedge_status`／`source`。
    """
    # 2026-10-29（`DEC-2026-10-29-01`，有意識的更正，不是漏刪）：resolver 不再剝未驗證的後綴，
    # 本函式改以 MoneyDJ 文法的**候選切分**（第一個 `-`）比對 —— 只用於評估證據，不合併、不產生 canonical_key。
    # 命名空間未知／範圍外仍拋（`AGIF-HT5` 在 `namespace="fundclear"` 下照舊不是後綴證據）。
    splits = []
    for name, obs in (("obs_a", obs_a), ("obs_b", obs_b)):
        if not isinstance(obs, dict):
            raise TypeError(f"{name} 須為 dict（收到 {type(obs).__name__}）")
        ident = resolve_fund_identity(obs.get("fund_code"), channel_table=channel_table, namespace=namespace)
        if ident.verification_status not in (STATUS_BASE_RESOLVED, STATUS_EXCEPTION, STATUS_SUFFIX_UNVERIFIED):
            raise ValueError(f"{name} 的 fund_code 解析不出 MoneyDJ 基本碼（{ident.verification_status}）：{ident.error}")
        base, _sep, suf = ident.original_code.partition("-")
        splits.append((base, suf or None, ident.original_code))
    (a_base, a_suf, a_code), (b_base, b_suf, b_code) = splits
    if a_base != b_base:
        raise ValueError(f"兩筆觀測的 base 不同（{a_base!r} vs {b_base!r}）；不是後綴證據")
    if a_code == b_code:
        raise ValueError(f"兩筆觀測是同一個完整代碼 {a_code!r}；不是後綴證據")

    diffs = []
    for attr in _ATTRS:
        va, vb = obs_a.get(attr), obs_b.get(attr)
        if compare_attribute(va, vb) == DIFFERENT:
            diffs.append({"attribute": attr, "a": va, "b": vb})
    if obs_a.get("nav") is not None and obs_b.get("nav") is not None:
        na, nb = _nav_float(obs_a["nav"], "obs_a"), _nav_float(obs_b["nav"], "obs_b")
        same_date = obs_a.get("nav_date") is not None and str(obs_a.get("nav_date")) == str(obs_b.get("nav_date"))
        if (same_date and compare_attribute(obs_a.get("currency"), obs_b.get("currency")) == SAME
                and not math.isclose(na, nb, rel_tol=_REL_TOL, abs_tol=_ABS_TOL)):
            diffs.append({"attribute": "nav_same_date_same_currency", "a": na, "b": nb,
                          "nav_date": str(obs_a["nav_date"]), "currency": str(obs_a["currency"]).upper()})
    if not diffs:
        return None
    suffixes = sorted({s for s in (a_suf, b_suf) if s})
    return {
        "kind": STATUS_EXCEPTION,
        "base_fund_code": a_base,
        "codes": (a_code, b_code),
        "platform_suffixes": tuple(suffixes),
        "suggested_registry_entries": tuple((a_base, s) for s in suffixes),
        "differences": diffs,
        "evidence": (dict(obs_a), dict(obs_b)),
        "action": "不合併；須 Decision Gate 決定是否拆成不同 canonical identity（不得以「不同平台」直接合理化）",
    }


# ═══════════════ 外部候選驗證（裁示第 10 項）：不因 results[0] 就收 ═══════════════


def validate_external_candidate(identity: CanonicalFundIdentity, candidate: dict) -> dict:
    """外部來源（例：Morningstar 搜尋結果）是否屬於 `identity` 這檔基金。

    比對 `base_fund_code`／`isin`／`currency`／`share_class`／`distribution_type`／`hedge_status`：
    任一兩邊皆已知且不同 → `rejected`（留 conflict 紀錄、`display_text` ＝ 客戶指定文字）；
    沒有衝突且 `base_fund_code` 或 `isin` 兩邊皆已知且相同 → `accepted`；其餘（含只有幣別等非身分鍵相符）→ `unverified`
    （Unknown 對值：不衝突、也不確認）。
    本階段**只在 shadow 使用**，未接到任何 production 取數路徑。
    """
    if not isinstance(identity, CanonicalFundIdentity):
        raise TypeError(f"identity 須為 CanonicalFundIdentity（收到 {type(identity).__name__}）")
    if not isinstance(candidate, dict):
        raise TypeError(f"candidate 須為 dict（收到 {type(candidate).__name__}）")
    cand_source = candidate.get("source", "")
    freshness = candidate.get("as_of", candidate.get("freshness"))
    out = {"status": CANDIDATE_UNVERIFIED, "conflicts": [], "confirmed": [],
           "selected_source": identity.source, "candidate_source": cand_source, "rejected_source": None,
           "difference": [], "reason": "", "freshness": freshness, "display_text": None}
    if identity.verification_status == STATUS_UNRESOLVED:
        out["reason"] = "identity 未解析，無法驗證候選"
        return out
    checks = [("base_fund_code", identity.base_fund_code), ("isin", identity.isin)]
    checks += [(attr, getattr(identity, attr)) for attr in _ATTRS]
    for attr, mine in checks:
        theirs = candidate.get(attr)
        cmp = compare_attribute(mine, theirs)
        if cmp == DIFFERENT:
            out["conflicts"].append({"attribute": attr, "identity_value": mine, "candidate_value": theirs})
        elif cmp == SAME:
            out["confirmed"].append(attr)
    if out["conflicts"]:
        out.update(status=CANDIDATE_REJECTED, rejected_source=cand_source, difference=list(out["conflicts"]),
                   display_text=SOURCE_CONFLICT_TEXT,
                   reason="已知身分屬性明確衝突：" + "、".join(c["attribute"] for c in out["conflicts"]))
    elif {"base_fund_code", "isin"} & set(out["confirmed"]):
        out.update(status=CANDIDATE_ACCEPTED, reason="已知屬性相符：" + "、".join(out["confirmed"]))
    elif out["confirmed"]:
        # 2026-10-28 獨立稽核 MUST 2：只有幣別等非身分鍵相符不足以接受（同幣別的別檔基金很多）。
        out["reason"] = ("只有非身分鍵相符（" + "、".join(out["confirmed"]) +
                         "）；base_fund_code 或 isin 未確認 → 不接受")
    else:
        out["reason"] = "沒有任何兩邊皆已知的屬性可比對（Unknown 不算確認）"
    return out


# ═══════════════ Cross-view NAV（裁示第 11 項）：與 identity 分開 ═══════════════


def _obs_tuple(obs) -> tuple:
    if isinstance(obs, dict):
        return (obs.get("view"), obs.get("nav"), obs.get("nav_date"), obs.get("currency"), obs.get("source"))
    if isinstance(obs, (list, tuple)) and len(obs) == 5:
        return tuple(obs)
    raise TypeError(f"observation 須為 dict 或 (view, nav, nav_date, currency, source)（收到 {obs!r}）")


def check_cross_view_nav(base_fund_code: str, observations: Iterable) -> dict:
    """同一 base 在不同 view 的 NAV 觀測 → consistent／source_conflict／not_comparable。

    只有「同 nav_date＋同已知 currency」的觀測彼此可比；日期或幣別不同、或幣別 Unknown → not comparable
    （不是衝突，也不是一致）。可比組內 NAV 不相等 → source conflict 紀錄。本函式**不建立任何 identity**。
    """
    if not isinstance(base_fund_code, str) or not base_fund_code.strip():
        raise ValueError(f"base_fund_code 須為非空字串（收到 {base_fund_code!r}）")
    groups: dict = {}
    not_comparable = []
    for i, raw_obs in enumerate(observations):
        view, nav, nav_date, ccy, src = _obs_tuple(raw_obs)
        rec = {"view": view, "nav": _nav_float(nav, f"observations[{i}]"),
               "nav_date": None if nav_date is None else _as_of_text(nav_date),
               "currency": UNKNOWN if is_unknown(ccy) else str(ccy).strip().upper(), "source": src}
        if rec["nav_date"] is None or rec["currency"] == UNKNOWN:
            not_comparable.append(rec)
            continue
        groups.setdefault((rec["nav_date"], rec["currency"]), []).append(rec)
    conflicts, consistent = [], []
    for (nav_date, ccy), recs in sorted(groups.items()):
        if len(recs) < 2:
            not_comparable.extend(recs)
            continue
        navs = [r["nav"] for r in recs]
        if math.isclose(min(navs), max(navs), rel_tol=_REL_TOL, abs_tol=_ABS_TOL):
            consistent.append({"nav_date": nav_date, "currency": ccy, "observations": recs})
        else:
            conflicts.append({"base_fund_code": base_fund_code, "nav_date": nav_date, "currency": ccy,
                              "observations": recs, "display_text": SOURCE_CONFLICT_TEXT,
                              "reason": "同 base＋同 nav_date＋同幣別 NAV 不一致 → source conflict；"
                                        "不得以不同平台合理化，不建立第二個 canonical identity"})
    status = NAV_CONFLICT if conflicts else (NAV_CONSISTENT if consistent else NAV_NOT_COMPARABLE)
    return {"base_fund_code": base_fund_code, "status": status, "conflicts": conflicts,
            "consistent_groups": consistent, "not_comparable": not_comparable}
