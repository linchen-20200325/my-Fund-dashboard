"""11641 最小取數腳本（B-TDCC-REAL-NAV-S1）：境外基金淨值，本機單檔查詢。

⛔ 預設**不連網**。真實 OAS／資料請求仍 HOLD（DEC-2026-11-19-02），需客戶另行明示授權後，
由「改動 `LIVE_ENABLED`」的獨立 PR 開啟；本 PR 內 `LIVE_ENABLED = False`：
CLI 只做離線說明；**最後的 HTTP 送出點（`_single_get`）自身也強制檢查**，直接呼叫亦不會送出。
離線測試一律注入假 transport／假 pool。

規格來源（#1296）：rev2 #7131294864 → rev3 #7131668066 → rev3.1 #7132882773（Work PASS #7132928714）；
施工授權 #7133015104；Work QA #7148209178（MF1～MF5）。限制（全部沿用，不放寬）：
  * 全程至多 2 次 GET：R-0（OAS JSON，≤2 MiB）、R-1（唯一核證端點，≤16 MiB／≤100,000 列）；
    各步（GET＋解析＋IPC）20 s 硬牆鐘；0 重試、0 轉址、0 額外 GET；TLS verify；不走代理；不寫 key log。
  * R-1 前須有「自足 OAS」：版本、唯一明示引用 11641 的 GET、無必要參數／認證、200 回應為物件陣列
    且含必要欄位；URL 精確核證（拒完整 `.`／`..` 段、prepared URL 逐字一致）；任一缺證 ⇒ R-1＝0。
  * 只接受使用者親自確認「非持倉」（明示布林 True）的公開 ISIN；僅在本機比對；零 fallback；
    不讀持倉、Secrets、Sheet；零落盤（不寫任何檔）。
  * 級別獨立核證（rev2 §四）：文件層證據＋代碼↔ISIN 一對一＋逐日衝突＋最近 7 日有效日期＋有效幣別；
    不足 ⇒ `class_verified=False` ⇒ 扣下 NAV，只輸出技術聚合（含 7 個檢核布林）。
  * 權利：R2（本次、本檔、本機顯示）須具證據；R3／R4 各自獨立，不由 R2 推導；缺／UNKNOWN／DENY ⇒ 扣值。
  * 公式呼叫 0 次；最近 7 日資料不足長期健診。回存（GitHub）只限技術聚合：不含 ISIN、NAV、基金名稱。
  * CLI 無 R2 授權入口（永遠 UNKNOWN ⇒ 只顯示技術聚合）；本機顯示 NAV 須待另案授權後由呼叫端注入證據。

NOT VERIFIED（需實際 R-0 才能確認，**不得**以本檔內常數當作已驗證事實）：
R-0 實際 URL 與回應形態、OAS 是否真有唯一對應 11641 的操作、R-1 欄位名稱與日期／幣別格式、Windows。
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import secrets
import ssl
import sys
import threading
import uuid
import weakref
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Optional
from urllib.parse import urlsplit

# ── 開關：真網路（本 PR 必須為 False；開啟屬另案客戶授權）──────────────────────
LIVE_ENABLED = False

# ── 釘住常數（變更任何一項＝改變授權範圍，須重新取得授權）────────────────────────
ORIGIN_HOST = "openapi.tdcc.com.tw"
R0_URL = "https://openapi.tdcc.com.tw/tdcc-opendata-api-docs"  # 若非 JSON ⇒ R-0 失敗 ⇒ 零 R-1
DATASET_ID = "11641"
MAX_REQUESTS = 2
R0_MAX_BYTES = 2 * 1024 * 1024
R1_MAX_BYTES = 16 * 1024 * 1024
R1_MAX_ROWS = 100_000
STEP_WALL_SECONDS = 20.0
REAP_SECONDS = 2.0
IPC_MAX_BYTES = 64 * 1024
MAX_SELECTED_ROWS = 64
WINDOW_DAYS = 7
TAIPEI = _dt.timezone(_dt.timedelta(hours=8))
USER_AGENT = "tdcc-11641-min-fetch/1 (local read-only; no automation)"
# R-1 欄位名（NOT VERIFIED；缺任一 ⇒ 拒絕，不猜別名＝零 fallback）
KEY_CODE, KEY_ISIN, KEY_NAV, KEY_DATE, KEY_CCY, KEY_NAME = "基金代碼", "ISINCODE", "NAV", "日期", "計價幣別", "基金名稱"
REQUIRED_KEYS = (KEY_CODE, KEY_ISIN, KEY_NAV, KEY_DATE, KEY_CCY, KEY_NAME)
OGDL_LICENSE_URL = "https://data.gov.tw/license"
R2_PURPOSE = "local_display"
R2_SCOPE_FILE = "scripts/tdcc_11641_min_fetch.py"

# 有效 ISO 4217 現行字母碼（fail-closed：清單外＝無法辨識＝扣值；CNH 等非 ISO 碼亦扣）
ISO4217 = frozenset(
    "AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BRL BSD BTN BWP BYN BZD CAD CDF "
    "CHF CLP CNY COP CRC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD "
    "HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD "
    "MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN "
    "PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY "
    "TTD TWD TZS UAH UGX USD UYU UZS VES VND VUV WST XAF XCD XOF XPF YER ZAR ZMW ZWG".split()
)

_SEG = re.compile(r"^[A-Za-z0-9._~-]+$")
_FINAL = re.compile(r"^https://openapi\.tdcc\.com\.tw(/[A-Za-z0-9._~-]+)+$")
_DATASET_REF = re.compile(r"https?://data\.gov\.tw/dataset/(\d+)", re.I)
_ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
_OAS3 = re.compile(r"^3\.[01]\.\d+$")
_REASON = re.compile(r"^[A-Za-z0-9_:]{1,64}$")
RIGHTS_AXES = ("R2", "R3", "R4")


class FetchStop(Exception):
    """失敗即停止：帶機器可讀 reason；訊息不含 URL、ISIN 或回應內容。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# ───────────────────────── 純函式：ISIN／URL ──────────────────────────────────
def isin_format_ok(isin: Any) -> bool:
    return isinstance(isin, str) and bool(_ISIN.match(isin))


def isin_checksum_ok(isin: str) -> bool:
    """Luhn 檢查碼（字母轉兩位數字）。僅在格式通過時有意義。"""
    digits = "".join(str(int(c, 36)) for c in isin)
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
    return total % 10 == 0


def isin_valid(isin: Any) -> bool:
    return isin_format_ok(isin) and isin_checksum_ok(isin)


def _prepared_url(url: str) -> str:
    """實際 client（urllib3）準備送出的 URL（含 dot-segment 正規化）。"""
    from urllib3.util import parse_url

    return parse_url(url).url


def verify_pinned_url(url: str, *, prepare: Callable[[str], str] = _prepared_url) -> None:
    """送出點用：host 精確、路徑樣式、prepared URL 逐字一致；不符 raise。"""
    if not isinstance(url, str) or not _FINAL.fullmatch(url) or re.search(r"\.\.|/\./|/\.$|//.*//", url):
        raise FetchStop("url_not_pinned")
    if prepare(url) != url:
        raise FetchStop("prepared_url_mismatch")


def assemble_url(servers: Any, path: Any, *, prepare: Callable[[str], str] = _prepared_url) -> str:
    """組裝 R-1 URL 並驗證；任何不符 raise FetchStop（⇒ R-1＝0）。零網路。"""
    if not isinstance(servers, list) or len(servers) != 1 or not isinstance(servers[0], dict):
        raise FetchStop("server_not_unique")
    base = servers[0].get("url")
    if not isinstance(base, str):
        raise FetchStop("server_not_unique")
    if not isinstance(path, str) or not path.startswith("/") or "{" in path or "}" in path:
        raise FetchStop("path_template_or_relative")
    if re.search(r"%|\\|\s|\.\.|//|[?#@]", path):
        raise FetchStop("path_illegal_chars")
    if not path.isascii() or len(path) > 128:
        raise FetchStop("path_not_ascii_or_long")
    segs = [s for s in path.split("/") if s]
    if any(s in (".", "..") for s in segs):
        raise FetchStop("dot_segment")
    if not segs or not all(_SEG.match(s) for s in segs):
        raise FetchStop("path_segment_illegal")
    u = urlsplit(base)
    if u.scheme != "https":
        raise FetchStop("scheme_not_https")
    if u.username or u.password or u.port is not None or u.query or u.fragment:
        raise FetchStop("origin_has_userinfo_port_query")
    if (u.hostname or "").lower() != ORIGIN_HOST:
        raise FetchStop("host_mismatch")
    bp = u.path.rstrip("/")
    if bp:
        bsegs = [s for s in bp.split("/") if s]
        if any(s in (".", "..") for s in bsegs):
            raise FetchStop("dot_segment_base")
        if re.search(r"%|\\|\s|\.\.|//", bp) or not all(_SEG.match(s) for s in bsegs):
            raise FetchStop("base_path_illegal")
    url = f"https://{ORIGIN_HOST}{bp}{path}"
    if not _FINAL.fullmatch(url):
        raise FetchStop("final_url_pattern")
    if prepare(url) != url:
        raise FetchStop("prepared_url_mismatch")
    return url


# ───────────────────────── OAS 證據（MF-3）────────────────────────────────────
def _walk_strings(node: Any, depth: int = 0):
    if depth > 12:
        return
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _walk_strings(v, depth + 1)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_strings(v, depth + 1)


def _resolve(node: Any, root: Any, depth: int = 0) -> Any:
    """只解析文件內的 `#/...` 參照；外部參照＝取不到自足 OAS ⇒ 停。"""
    if depth > 8:
        raise FetchStop("schema_ref_depth")
    if isinstance(node, dict) and "$ref" in node:
        ref = node["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            raise FetchStop("external_ref")
        cur = root
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(cur, dict) or part not in cur:
                raise FetchStop("ref_unresolved")
            cur = cur[part]
        return _resolve(cur, root, depth + 1)
    return node


def bind_dataset_operation(oas: Any) -> tuple[str, dict, dict]:
    """找「GET 操作且只明示引用 data.gov.tw 11641」者；恰 1 個才回 (path, operation, path_item)。"""
    if not isinstance(oas, dict) or not isinstance(oas.get("paths"), dict):
        raise FetchStop("oas_shape")
    hits: list[tuple[str, dict, dict]] = []
    for path, item in oas["paths"].items():
        if not isinstance(item, dict) or not isinstance(item.get("get"), dict):
            continue
        op = item["get"]
        refs = {m for s in _walk_strings(op) for m in _DATASET_REF.findall(s)}
        if refs == {DATASET_ID}:
            hits.append((path, op, item))
    if not hits:
        raise FetchStop("binding_none")
    if len(hits) > 1:
        raise FetchStop("binding_ambiguous")
    return hits[0]


_PARAM_IN = ("query", "header", "path", "cookie")


_TOKEN = r"[A-Za-z0-9!#$%&'*+.^_`|~-]+"
# RFC 9110 media-type：type/subtype 後接零或多個 `; token=(token|quoted-string)`；無值參數（如 `; charset`）不合法
_MEDIA_TYPE = re.compile(rf"{_TOKEN}/{_TOKEN}(?:\s*;\s*{_TOKEN}=(?:{_TOKEN}|\"[^\"\\\r\n]*\"))*")


_SCHEMA_TYPES = frozenset({"array", "boolean", "integer", "number", "object", "string"})
_SCHEMA_KEYS = frozenset({
    "$ref", "type", "format", "title", "description", "default", "example", "nullable", "deprecated", "readOnly",
    "writeOnly", "enum", "multipleOf", "maximum", "minimum", "exclusiveMaximum", "exclusiveMinimum", "maxLength",
    "minLength", "pattern", "maxItems", "minItems", "uniqueItems", "maxProperties", "minProperties", "required",
    "properties", "additionalProperties", "items", "allOf", "oneOf", "anyOf", "not", "discriminator", "xml",
    "externalDocs"})
_SCHEMA_NONNEG_INT = ("maxLength", "minLength", "maxItems", "minItems", "maxProperties", "minProperties")
# OAS 3.0：exclusiveMaximum／exclusiveMinimum 為布林（3.1 的數值寫法尚無法正確驗證 ⇒ 保守拒絕，不擴張支援）
_SCHEMA_BOOL = ("nullable", "deprecated", "readOnly", "writeOnly", "uniqueItems", "exclusiveMaximum",
                "exclusiveMinimum")
_SCHEMA_NUM = ("maximum", "minimum")
_XML_KEYS = {"name": str, "namespace": str, "prefix": str, "attribute": bool, "wrapped": bool}


def _is_real(v: Any) -> bool:
    return not isinstance(v, bool) and isinstance(v, (int, float)) and v == v and v not in (float("inf"), float("-inf"))


def _check_aux_objects(node: dict) -> None:
    """multipleOf、xml、externalDocs、discriminator 的值結構（無法正確驗證者一律保守拒絕）。"""
    if "multipleOf" in node and not (_is_real(node["multipleOf"]) and node["multipleOf"] > 0):
        raise FetchStop("schema_invalid")  # multipleOf 須為 > 0 的數值（0、負數、字串、布林皆拒）
    if "xml" in node:
        x = node["xml"]
        if not isinstance(x, dict) or any(
                (k not in _XML_KEYS and not (isinstance(k, str) and k.startswith("x-")))
                or (k in _XML_KEYS and (type(v) is not _XML_KEYS[k])) for k, v in x.items()):
            raise FetchStop("schema_invalid")
    if "externalDocs" in node:
        d = node["externalDocs"]
        if (not isinstance(d, dict) or not isinstance(d.get("url"), str) or not d["url"].strip()
                or ("description" in d and not isinstance(d["description"], str))
                or any(k not in ("url", "description") and not (isinstance(k, str) and k.startswith("x-")) for k in d)):
            raise FetchStop("schema_invalid")
    if "discriminator" in node:
        d = node["discriminator"]
        if (not isinstance(d, dict) or not isinstance(d.get("propertyName"), str) or not d["propertyName"].strip()
                or any(k not in ("propertyName", "mapping") and not (isinstance(k, str) and k.startswith("x-"))
                       for k in d)
                or ("mapping" in d and (not isinstance(d["mapping"], dict) or not all(
                    isinstance(k, str) and isinstance(v, str) for k, v in d["mapping"].items())))):
            raise FetchStop("schema_invalid")


def _validate_schema_object(node: Any, oas: dict, seen: Optional[set] = None, budget: Optional[list] = None,
                            depth: int = 0) -> None:
    """OAS 3.0 Schema Object 結構驗證（跟隨 `$ref`，每個解析終點都必須是合法 Schema Object）。

    非物件（字串／陣列／數字／null）、未知鍵（`x-` 擴充除外）、型別錯誤、`type` 不在集合、`array` 缺 `items`、
    `$ref` 外部／無法解析／終點非 Schema Object ⇒ 一律停（⇒ R-1＝0）。含防環、節點數與深度上限。
    """
    seen = set() if seen is None else seen
    budget = [600] if budget is None else budget
    budget[0] -= 1
    if budget[0] < 0 or depth > 12:
        raise FetchStop("schema_too_complex")
    if not isinstance(node, dict):
        raise FetchStop("schema_not_object")
    if "$ref" in node:
        ref = node["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            raise FetchStop("external_ref")
        if ref in seen:
            return
        seen.add(ref)
        _validate_schema_object(_resolve(node, oas), oas, seen, budget, depth + 1)
        return
    if any(not isinstance(k, str) or (k not in _SCHEMA_KEYS and not k.startswith("x-")) for k in node):
        raise FetchStop("schema_unknown_keyword")
    t = node.get("type")
    if "type" in node and (not isinstance(t, str) or t not in _SCHEMA_TYPES):
        raise FetchStop("schema_invalid")
    for k in _SCHEMA_NONNEG_INT:
        if k in node and (type(node[k]) is not int or node[k] < 0):
            raise FetchStop("schema_invalid")
    for k in _SCHEMA_BOOL:
        if k in node and not isinstance(node[k], bool):
            raise FetchStop("schema_invalid")
    for k in _SCHEMA_NUM:
        if k in node and not _is_real(node[k]):
            raise FetchStop("schema_invalid")
    _check_aux_objects(node)
    for k in ("format", "title", "description", "pattern"):
        if k in node and not isinstance(node[k], str):
            raise FetchStop("schema_invalid")
    if "enum" in node and (not isinstance(node["enum"], list) or not node["enum"]):
        raise FetchStop("schema_invalid")
    if "required" in node and (not isinstance(node["required"], list) or not node["required"]
                               or not all(isinstance(x, str) for x in node["required"])):
        raise FetchStop("schema_invalid")
    if t == "array" and "items" not in node:
        raise FetchStop("schema_invalid")
    if "items" in node:
        _validate_schema_object(node["items"], oas, seen, budget, depth + 1)
    if "properties" in node:
        props = node["properties"]
        if not isinstance(props, dict):
            raise FetchStop("schema_invalid")
        for v in props.values():
            _validate_schema_object(v, oas, seen, budget, depth + 1)
    if "additionalProperties" in node and not isinstance(node["additionalProperties"], bool):
        _validate_schema_object(node["additionalProperties"], oas, seen, budget, depth + 1)
    for k in ("allOf", "oneOf", "anyOf"):
        if k in node:
            lst = node[k]
            if not isinstance(lst, list) or not lst:
                raise FetchStop("schema_invalid")
            for v in lst:
                _validate_schema_object(v, oas, seen, budget, depth + 1)
    if "not" in node:
        _validate_schema_object(node["not"], oas, seen, budget, depth + 1)


def _check_param_representation(p: dict, oas: dict) -> None:
    """OAS 3.0.3 Parameter Object：`schema` 與 `content` **互斥且恰一**；content 只允許單一有效 media object。"""
    has_schema, has_content = "schema" in p, "content" in p
    if has_schema == has_content:  # 同存或皆無
        raise FetchStop("op_params_invalid")
    if has_schema:
        if not isinstance(p["schema"], dict):
            raise FetchStop("op_params_invalid")
        _validate_schema_object(p["schema"], oas)
        return
    c = p["content"]
    if not isinstance(c, dict) or len(c) != 1:  # 空、或多個 media entries
        raise FetchStop("op_params_invalid")
    (mt, mo), = c.items()
    if not isinstance(mt, str) or not _MEDIA_TYPE.fullmatch(mt) or not isinstance(mo, dict):
        raise FetchStop("op_params_invalid")
    if "schema" in mo:
        if not isinstance(mo["schema"], dict):
            raise FetchStop("op_params_invalid")
        _validate_schema_object(mo["schema"], oas)


def _check_no_required_params_or_auth(oas: dict, op: dict, item: dict) -> None:
    """參數／認證結構須完整可驗：未宣告（鍵不存在）與宣告為 null／錯型別不同——後者＝證據不明＝停。"""
    for holder in (item, op):
        if "parameters" not in holder:
            continue  # 未宣告＝無參數（合法）
        plist = holder["parameters"]
        if not isinstance(plist, list):  # 含 null
            raise FetchStop("op_params_invalid")
        seen: set = set()
        for p in plist:
            p = _resolve(p, oas)
            if (not isinstance(p, dict) or not _nonblank(p.get("name")) or p.get("in") not in _PARAM_IN):
                raise FetchStop("op_params_invalid")
            _check_param_representation(p, oas)
            if "required" in p and not isinstance(p["required"], bool):
                raise FetchStop("op_params_invalid")
            if p.get("in") == "path" and p.get("required") is not True:
                raise FetchStop("op_params_invalid")  # OAS：path 參數必為 required
            ident = (p["name"].lower() if p["in"] == "header" else p["name"], p["in"])
            if ident in seen:
                raise FetchStop("op_params_invalid")  # 同層 name＋in 不得重複
            seen.add(ident)
            if p.get("required") is True or p.get("in") == "path":
                raise FetchStop("op_requires_params")
    for sec in ((op["security"],) if "security" in op else ()) + (
            (oas["security"],) if "security" in oas and "security" not in op else ()):
        if not isinstance(sec, list) or not all(isinstance(x, dict) for x in sec):
            raise FetchStop("op_security_invalid")
        if any(x for x in sec):
            raise FetchStop("op_requires_security")


def _effective_servers(oas: dict, item: dict, op: dict) -> Any:
    """OAS3：operation > pathItem > 全域。多層宣告且內容不同＝衝突＝停；回傳有效 servers。"""
    levels = [x["servers"] for x in (op, item, oas) if isinstance(x, dict) and "servers" in x]
    if not levels:
        raise FetchStop("server_not_unique")  # 未宣告＝OAS 預設相對路徑，無法釘住 origin
    if any(lv != levels[0] for lv in levels[1:]):
        raise FetchStop("server_conflict")
    return levels[0]


_KEY_TYPES = {KEY_NAV: ("string", "number", "integer")}


def _response_schema_props(oas: dict, op: dict) -> dict:
    """200 回應須為「物件陣列」且 properties 含全部必要欄位；回傳 properties（已解析 $ref）。"""
    resp = op.get("responses")
    r200 = _resolve(resp.get("200"), oas) if isinstance(resp, dict) and "200" in resp else None
    content = r200.get("content") if isinstance(r200, dict) else None
    if not isinstance(content, dict):
        raise FetchStop("response_schema_missing")
    jsons = [v for k, v in content.items() if isinstance(k, str) and k.lower().startswith("application/json")]
    if len(jsons) != 1 or not isinstance(jsons[0], dict) or "schema" not in jsons[0]:
        raise FetchStop("response_schema_missing")
    sch = _resolve(jsons[0]["schema"], oas)
    if not isinstance(sch, dict) or sch.get("type") != "array":
        raise FetchStop("response_not_array")
    items = _resolve(sch.get("items"), oas)
    if not isinstance(items, dict) or items.get("type") not in ("object", None) or "properties" not in items:
        raise FetchStop("response_items_not_object")
    props = items["properties"]
    if not isinstance(props, dict):
        raise FetchStop("response_items_not_object")
    if not all(k in props for k in REQUIRED_KEYS):
        raise FetchStop("response_keys_missing")
    out = {}
    for k in REQUIRED_KEYS:
        v = _resolve(props[k], oas)
        if not isinstance(v, dict) or v.get("type") not in _KEY_TYPES.get(k, ("string",)):
            raise FetchStop("response_key_schema_invalid")  # 必要欄位 schema 不可為 null／缺型別
        out[k] = v
    return out


# 說明文字須是「單一子句、整句符合」的正向身分陳述；多子句／附註／矛盾／設計目標／沿用母基金／無關代碼一律不採證。
_ISIN_FULL = re.compile(
    r"(isin\s*(碼|代碼)?\s*[：:]?\s*)?唯一(識別|對應|代表)(一個|單一)份額級別[。.]?"
    r"|isin\s*(碼|代碼)?\s*[：:]?\s*(一個|單一)份額級別唯一對應(一個|唯一)\s*isin[。.]?"
    r"|the isin uniquely identifies (a|one|a single) share class\.?",
    re.I)
_CODE_FULL = re.compile(
    r"(基金|份額級別)(代碼|代號)\s*[：:]?\s*(用以|用於)?(識別|代表|對應)(該)?(基金|份額級別)(份額級別)?[。.]?"
    r"|fund code identifies (the|a) (fund|share class)\.?",
    re.I)
_SHARED = ("各份額級別", "共用", "共享", "共同", "多個", "多支", "同一 isin", "同一isin", "shared", "multiple",
           "any class", "all classes", "行銷", "促銷", "活動", "campaign", "promo", "廣告",
           # 矛盾／來源不明／設計目標類
           "無關", "不識別", "沿用", "母基金", "子基金", "設計目標", "目標", "僅為", "僅供", "參考", "附註", "註記",
           "預留", "保留", "暫", "待", "未來", "將", "計畫", "規劃", "草案", "inherit", "parent", "goal", "design",
           "target", "reserved", "planned", "legacy", "deprecated", "todo", "tbd", "note:")
_NEGATION = ("不代表", "不是", "並非", "非", "無法", "未", "沒有", "不含", "不具", "不為", "不屬", "不提供", "不包含",
             "不能", "不可", "不得", "不保證", "not ", "no ", "n't", "cannot", "without", "unrelated")
_DESC_MAX = 80


def _clean_text(desc: Any) -> Optional[str]:
    """說明須為非空、短（≤80 字）、單一子句字串，且不含否定／共用／無關／矛盾／設計目標標記；否則無正向證據。"""
    if not isinstance(desc, str) or not desc.strip() or len(desc) > _DESC_MAX:
        return None
    low = desc.lower()
    if any(n in low for n in _NEGATION) or any(x in low for x in _SHARED):
        return None
    if re.search(r"[，；;,\n]", desc.strip().rstrip("。.")):
        return None  # 多子句／附加說明（可夾帶矛盾）一律不採證
    return desc.strip()


# 可證固定寬度的保守 pattern 子集（不以有限樣本冒充完整證明）：
#   ^ (原子)+ $，原子＝[字元類] 或 [字元類]{n}（n 為單一正整數）；字元類僅含 A-Z／a-z／0-9／單一英數字元的範圍。
#   不允許 | ( ) ? * + . \ 、{n,m}、{n,} 等任何可變寬度或無法簡單證明的語法。寬度＝各原子 n（缺省 1）之和。
_CLASS_BODY = r"(?:[A-Za-z0-9](?:-[A-Za-z0-9])?)+"
_ATOM = re.compile(rf"\[({_CLASS_BODY})\](?:\{{([1-9][0-9]{{0,2}})\}})?")
_ISIN_SCHEMA_KEYS = frozenset({"type", "description", "minLength", "maxLength", "pattern", "format", "title",
                               "example", "examples"})


def _class_body_ok(body: str) -> bool:
    """字元類 A-Z 這類範圍須由小到大且同類（大寫／小寫／數字），避免反向或跨類範圍造成語意不明。"""
    for m_ in re.finditer(r"([A-Za-z0-9])-([A-Za-z0-9])", body):
        lo, hi = m_.group(1), m_.group(2)
        same = (lo.isdigit() and hi.isdigit()) or (lo.isupper() and hi.isupper()) or (lo.islower() and hi.islower())
        if not same or lo > hi:
            return False
    return True


def _provable_pattern_width(pat: Any) -> Optional[int]:
    """回傳可證的固定寬度；不在保守子集內一律 None（＝不採證）。"""
    if not isinstance(pat, str) or not (3 <= len(pat) <= 64) or not (pat.startswith("^") and pat.endswith("$")):
        return None
    inner, pos, width = pat[1:-1], 0, 0
    if not inner:
        return None
    while pos < len(inner):
        m_ = _ATOM.match(inner, pos)
        if not m_ or not _class_body_ok(m_.group(1)):
            return None
        width += int(m_.group(2)) if m_.group(2) else 1
        pos = m_.end()
    return width


def _isin_schema_restricts_12(sch: Any) -> bool:
    """結構佐證（不只靠文字）：ISIN 欄位 schema 須以**可證**方式限制為固定 12 碼，且不得自相矛盾。

    - 只允許已知安全鍵；出現 enum／const／oneOf／anyOf／allOf／not／$ref／nullable 等無法證明恆定長度的鍵＝不採證。
    - 任一已宣告鍵的值為 null（`pattern: null`、`minLength: null`…）＝不採證。
    - `minLength`／`maxLength` 宣告任一則須兩者皆為整數 12。
    - `pattern` 宣告則須落在上述保守子集且可證寬度恰為 12（如 `^[A-Z]{2}[A-Z0-9]{9}[0-9]$`）；
      `([A-Z0-9]{2})?` 這類可選尾、可變寬度或無法證明的樣式一律不採證。
    - 至少一種可證限制成立，且已宣告的每一種都必須成立。
    """
    if not isinstance(sch, dict) or sch.get("type") != "string":
        return False
    if set(sch) - _ISIN_SCHEMA_KEYS or any(v is None for v in sch.values()):
        return False
    lo, hi = sch.get("minLength"), sch.get("maxLength")
    declared_len = "minLength" in sch or "maxLength" in sch
    ok_len = type(lo) is int and type(hi) is int and lo == 12 and hi == 12
    if declared_len and not ok_len:
        return False
    ok_pat = False
    if "pattern" in sch:
        ok_pat = _provable_pattern_width(sch["pattern"]) == 12
        if ok_pat:  # 寬度已可證；另以合法 ISIN 範例做健全性檢查（僅排除字元集明顯不符者，不作為證明）
            rx = re.compile(sch["pattern"])
            ok_pat = all(rx.fullmatch(x) for x in ("US0378331005", "JP3633400001"))
        if not ok_pat:
            return False
    return ok_len or ok_pat


def _class_doc_evidence(props: dict) -> bool:
    """文件層證據（rev2 §四.1）：ISIN 說明＝整句正向『唯一識別單一份額級別』；代碼說明＝整句基金／級別身分陳述；
    ISIN schema 確實限制合法 12 碼。任一缺或矛盾 ⇒ False（扣值）。"""
    isin_txt = _clean_text(props[KEY_ISIN].get("description"))
    code_txt = _clean_text(props[KEY_CODE].get("description"))
    return bool(isin_txt and _ISIN_FULL.fullmatch(isin_txt) and code_txt and _CODE_FULL.fullmatch(code_txt)
                and _isin_schema_restricts_12(props[KEY_ISIN]))


def process_r0(body: bytes) -> dict[str, Any]:
    """R-0 解析（於 worker 內、受牆鐘約束）：回傳可 JSON 序列化的精簡證據；缺證 raise。"""
    try:
        oas = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise FetchStop("r0_not_json") from None
    if not isinstance(oas, dict):
        raise FetchStop("oas_shape")
    ver = oas.get("openapi")
    if not isinstance(ver, str) or not _OAS3.match(ver):
        raise FetchStop("oas_version_unsupported")
    info = oas.get("info")
    if not isinstance(info, dict) or not isinstance(info.get("version"), str) or not info["version"].strip():
        raise FetchStop("oas_info_version_missing")
    path, op, item = bind_dataset_operation(oas)
    if "$ref" in item:
        raise FetchStop("path_item_ref")
    servers = _effective_servers(oas, item, op)
    _check_no_required_params_or_auth(oas, op, item)
    props = _response_schema_props(oas, op)
    return {
        "oas_version": ver,
        "servers": servers,
        "path": path,
        "class_doc_ok": _class_doc_evidence(props),
    }


# ───────────────────────── R-1 解析與級別核證（MF-1）────────────────────────────
def process_r1(body: bytes, isin: str) -> dict[str, Any]:
    """R-1 全表掃描（於 worker 內、受牆鐘約束）：逐列驗證；回傳被選 ISIN 的列與配對統計。"""
    try:
        rows = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise FetchStop("r1_not_json") from None
    if not isinstance(rows, list):
        raise FetchStop("r1_not_list")
    if len(rows) > R1_MAX_ROWS:
        raise FetchStop("too_many_rows")
    selected: list[dict[str, str]] = []
    for r in rows:
        if not isinstance(r, dict) or not all(k in r for k in REQUIRED_KEYS):
            raise FetchStop("row_schema_mismatch")  # 逐列驗證（不只首列）
        if not all(isinstance(r[k], str) for k in (KEY_CODE, KEY_ISIN, KEY_NAME, KEY_CCY, KEY_DATE)) or \
                isinstance(r[KEY_NAV], bool) or not isinstance(r[KEY_NAV], (str, int, float)):
            raise FetchStop("row_type_mismatch")  # 身分欄型別不符不字串化，一律停（不放行）
        if r[KEY_ISIN].strip().upper() == isin:
            if len(selected) >= MAX_SELECTED_ROWS:
                raise FetchStop("too_many_selected")
            selected.append({k: str(r[k]) for k in REQUIRED_KEYS})
    codes = {s[KEY_CODE].strip() for s in selected}
    code_isins: dict[str, set[str]] = {c: set() for c in codes}
    for r in rows:
        c = r[KEY_CODE].strip()
        if c in code_isins:
            code_isins[c].add(r[KEY_ISIN].strip().upper())
    return {"rows_seen": len(rows), "selected": selected,
            "code_isin_max": max((len(v) for v in code_isins.values()), default=0)}


def _parse_date(raw: Any, today: _dt.date) -> _dt.date:
    s = str(raw).strip() if raw is not None else ""
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            d = _dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
        if d > today:
            raise FetchStop("nav_date_in_future")
        if d < today - _dt.timedelta(days=WINDOW_DAYS):
            raise FetchStop("nav_date_stale")
        return d
    raise FetchStop("nav_date_unreadable")


def _parse_nav(raw: Any) -> Decimal:
    try:
        d = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        raise FetchStop("nav_unreadable") from None
    if not d.is_finite() or d <= 0:
        raise FetchStop("nav_not_positive")  # missing ≠ 0：非正值不當 0 顯示
    return d


@dataclass
class Checks:
    """檢核布林（None＝未評估；未評估 ≠ False）。可回存。"""

    isin_format_ok: Optional[bool] = None
    checksum_ok: Optional[bool] = None
    found: Optional[bool] = None
    pairing_unambiguous: Optional[bool] = None
    class_verified: Optional[bool] = None
    nav_conflict: Optional[bool] = None
    date_ok: Optional[bool] = None


def evaluate_selection(info: dict[str, Any], class_doc_ok: bool, today: _dt.date, checks: Checks) -> dict[str, Any]:
    """級別獨立核證：全部成立才 class_verified。回傳 {'reason': 首個失敗原因|None, 'picked': ...}。"""
    sel = info["selected"]
    stops: list[str] = []

    def note(r: str) -> None:
        if r not in stops:
            stops.append(r)

    dates_ok = len(sel) <= WINDOW_DAYS
    if not dates_ok:
        note("too_many_dates")
    parsed = []
    for r in sel:
        d = nav = None
        try:
            d = _parse_date(r[KEY_DATE], today)
        except FetchStop as e:
            dates_ok = False
            note(e.reason)
        try:
            nav = _parse_nav(r[KEY_NAV])
        except FetchStop as e:
            note(e.reason)
        ccy = r[KEY_CCY].strip()
        if ccy not in ISO4217:
            note("ccy_unrecognized")
        if not r[KEY_NAME].strip() or not r[KEY_CODE].strip():
            note("class_unverified")
        parsed.append((d, nav, ccy, r[KEY_CODE].strip(), r[KEY_NAME].strip()))
    checks.date_ok = dates_ok

    by_date: dict[Any, set] = {}
    for d, nav, ccy, _c, _n in parsed:
        if d is not None and nav is not None:
            by_date.setdefault(d, set()).add((nav, ccy))
    checks.nav_conflict = any(len(v) > 1 for v in by_date.values())  # 逐日（含較舊日）
    if checks.nav_conflict:
        note("same_day_conflict")
    if len({(c, n, ccy) for _d, _v, ccy, c, n in parsed}) > 1:
        note("class_conflict")
    codes = {p[3] for p in parsed}
    checks.pairing_unambiguous = len(codes) == 1 and "" not in codes and info.get("code_isin_max") == 1
    if not checks.pairing_unambiguous:
        note("pairing_ambiguous")
    if not class_doc_ok:
        note("class_evidence_insufficient")
    checks.class_verified = not stops
    out: dict[str, Any] = {"reason": stops[0] if stops else None, "distinct_dates": len(by_date)}
    if not stops:
        latest = max(by_date)
        nav, ccy = next(iter(by_date[latest]))
        out["picked"] = {"nav": nav, "currency": ccy, "nav_date": latest, "fund_name": parsed[0][4],
                         # fund_code 候選：只取既有「代碼↔ISIN 一對一」核證通過者（pairing_unambiguous）；不猜、不補、不以 ISIN 代替
                         "fund_code": parsed[0][3] if checks.pairing_unambiguous else None}
    return out


# ───────────────────────── 權利／顯名 ──────────────────────────────────────────
@dataclass(frozen=True)
class R2Evidence:
    """R2（本次、本檔、本機顯示）證據：缺任一欄＝不成立。"""

    run_id: str = ""
    purpose: str = ""
    scope_file: str = ""
    consent_ref: str = ""


def _nonblank(x: Any) -> bool:
    return isinstance(x, str) and bool(x.strip())


@dataclass(frozen=True)
class Rights:
    """四軸權利狀態；腳本不自行宣告 ALLOWED（呼叫端以有依據之授權注入）。"""

    r2: str = "UNKNOWN"
    r3: str = "UNKNOWN"
    r4: str = "UNKNOWN"
    basis_ref: Optional[str] = None
    synthetic: bool = False
    r2_evidence: Optional[R2Evidence] = None

    def normalized(self, *, test_mode: bool, run_id: str) -> dict[str, str]:
        base_ok = _nonblank(self.basis_ref) and (test_mode or self.synthetic is not True)
        ev = self.r2_evidence
        r2_ev_ok = (isinstance(ev, R2Evidence) and ev.run_id == run_id and _nonblank(run_id)
                    and ev.purpose == R2_PURPOSE and ev.scope_file == R2_SCOPE_FILE and _nonblank(ev.consent_ref))
        out: dict[str, str] = {}
        for axis, val in zip(RIGHTS_AXES, (self.r2, self.r3, self.r4)):
            ok = val == "ALLOWED" and base_ok and (axis != "R2" or r2_ev_ok)
            out[axis] = "ALLOWED" if ok else ("DENY" if val == "DENY" else "UNKNOWN")
        return out


def use_decisions(rights: dict[str, str]) -> dict[str, bool]:
    """用途：顯示←R2；衍生←R2∧R3；AI←R2∧R3∧R4（R3／R4 不由 R2 推導）。"""
    r2, r3, r4 = (rights.get(a) == "ALLOWED" for a in RIGHTS_AXES)
    return {"display": r2, "derive": r2 and r3, "ai": r2 and r3 and r4}


STRUCTURED_ATTRIBUTION_FIELDS = ("release_year", "dataset_version", "metadata_updated_on")


def _unstated(reason: str) -> dict[str, Any]:
    """供應方未載明的結構化欄位：`stated=False` 且 `value=None`（不是占位字串，下游不得靠字串判斷）。"""
    return {"value": None, "stated": False, "reason": reason}


def attribution_block() -> dict[str, Any]:
    """OGDL 顯名區塊（只用既有可回查證據；未取得者如實標示，不猜）。

    年份／資料集版本／詮釋資料更新日是**三個獨立欄位**：目前都沒有可回查的供應方原值，故一律 `stated=False`、`value=None`；
    **不得**以詮釋資料更新日（或上架日、授權條款版本號）代替年份或版本。最終必備顯名集合以正式 DEC 為準，本函式不補造免責／修改標示。
    """
    return {
        "license_statement": "本資料由提供機關公開釋出，依《政府資料開放授權條款－第1版》提供；須遵循該條款方可利用。",
        "license_url": OGDL_LICENSE_URL,
        "agency": "金融監督管理委員會證券期貨局",
        "source_org": "臺灣集中保管結算所",
        "dataset": "境外基金淨值（data.gov.tw 11641）",
        "release_year": _unstated("not_stated_by_supplier"),
        "dataset_version": _unstated("not_stated_by_supplier"),
        "metadata_updated_on": _unstated("conflict_pending_review"),
    }


# ───────────────────────── 來源層 → 顯示端 handoff（M2 離線候選；純函式）─────────────────────────
HANDOFF_SCHEMA = "tdcc_11641_min_fetch.display_handoff.v1"
# 目前最終必備顯名集合（正式 DEC 決定 6）尚未生效：保守採「年份與資料集版本必須有供應方原值」，否則不放行；生效後只改這個常數與測試。
HANDOFF_STATED_REQUIRED = ("release_year", "dataset_version")
_HANDOFF_TEXT_ATTR = ("license_statement", "agency", "source_org", "dataset")
# 與 UI `ui_v3/adapters/fund_lookup.py::L2_PURE_CODE_PATTERN` 逐字相同（來源層不 import UI；測試鎖定兩邊字串一致）。
# UI 在比對前先 `raw.strip(" ").upper()`；本層同樣先正規化再比對，並以正規化後的大寫代碼輸出（🔍 的 loader 以此為鍵）。
UI_PURE_CODE_PATTERN = r"^([A-Z0-9]{3,30}(?:-[A-Z0-9]{2,20})?)$"
_UI_CODE = re.compile(UI_PURE_CODE_PATTERN)
_STAMP_OK = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z$")
_YEAR_OK = re.compile(r"^(19|20)\d{2}$")


# ── 逐次 nonce（S3）：真實模式不接受呼叫端自選／重用的 run_id；只有 `prepare_run()` 發出、且尚未消耗者有效 ──
_NONCE_LOCK = threading.Lock()
_NONCES: dict[str, str] = {}        # nonce -> "issued" | "consumed"
_NONCE_MAX_OUTSTANDING = 64
_NONCE_MAX_KNOWN = 1024


def prepare_run() -> str:
    """受控預備（來源層唯一發證點）：回傳本次 nonce。客戶本人的逐次同意（R2Evidence.run_id／consent_ref）須綁這個值；
    呼叫端不可自選真實 run_id。本函式不取數、不連網、不代發同意、不落盤。"""
    with _NONCE_LOCK:
        if sum(1 for v in _NONCES.values() if v == "issued") >= _NONCE_MAX_OUTSTANDING:
            raise FetchStop("too_many_prepared_runs")
        if len(_NONCES) >= _NONCE_MAX_KNOWN:  # 只清已消耗者（被清掉的重放仍會被拒：變成「未發證」）
            for k in [k for k, v in _NONCES.items() if v == "consumed"]:
                del _NONCES[k]
        nonce = secrets.token_hex(16)
        _NONCES[nonce] = "issued"
        return nonce


def _consume_nonce(run_id: Any) -> Optional[str]:
    """成功消耗回 None（永久標記 consumed：失敗後也不得重用）；否則回拒絕原因碼。明確條件，不用 assert。"""
    with _NONCE_LOCK:
        state = _NONCES.get(run_id) if isinstance(run_id, str) else None
        if state is None:
            return "run_id_not_issued"
        if state != "issued":
            return "run_id_consumed"
        _NONCES[run_id] = "consumed"
        return None


# ── sealed 登記（S1／S2）：handoff 只信「本次 run() 內部登記」的不可變內容，不讀 Result 上可被事後改寫的欄位 ──
@dataclass(frozen=True)
class _Sealed:
    test_mode: Optional[bool]
    refusal: Optional[str]            # None＝放行
    decisions: tuple                  # (("ai", bool), ("derive", bool), ("display", bool))
    payload_json: Optional[str]       # 放行時的固定鍵 payload（序列化字串＝不可變）
    owner: Any                        # 指向「本次 run() 真正產出的那個 Result 實例」的弱引用（r101 L1）：handoff 以 `is` 比對；實例已釋放＝拒收


_SEAL_LOCK = threading.Lock()
_SEALED: "OrderedDict[str, _Sealed]" = OrderedDict()
_SEAL_MAX = 256                       # 超過就丟最舊者（之後 handoff 該 Result＝not_issued_by_run＝拒收，fail-closed）
_DEAD: "deque[tuple[str, Any]]" = deque()   # r108：owner 釋放當下登記表正被持鎖操作時，延後清除的 (handle, owner 參照)；deque.append 不需鎖
_GATE_REASONS = frozenset({"attribution_malformed", "attribution_substituted", "attribution_not_stated", "no_paired_code",
                           "retrieved_at_invalid", "payload_incomplete"})


def _purge(handle: str, owner_ref: Any) -> None:
    """（呼叫端須持有 `_SEAL_LOCK`）只在登記的 owner 參照就是 `owner_ref` 時才刪；handle 不存在、或是別人的參照＝什麼都不做。"""
    rec = _SEALED.get(handle)
    if rec is not None and rec.owner is owner_ref:
        del _SEALED[handle]


def _drain_dead() -> None:
    """（呼叫端須持有 `_SEAL_LOCK`）處理先前因鎖被占用而延後的清除。"""
    while True:
        try:
            handle, owner_ref = _DEAD.popleft()
        except IndexError:
            return
        _purge(handle, owner_ref)


def _owner_gone(handle: str, owner_ref: Any) -> None:
    """`Result` 實例被釋放（含循環 GC）時由弱引用 callback 呼叫：即時清除其登記（連同 `payload_json`）。

    callback 可能在任何執行緒、任何配置點觸發，包含「本執行緒已持有 `_SEAL_LOCK` 正在改登記表」的當下；因此**不阻塞取鎖**：
    取不到鎖就改丟進 `_DEAD`，由下一次持鎖的登記表操作清掉（不改動進行中的 OrderedDict、不死鎖）。callback 只抓 handle 與弱引用，不抓 Result。
    """
    if _SEAL_LOCK.acquire(blocking=False):
        try:
            _purge(handle, owner_ref)
        finally:
            _SEAL_LOCK.release()
    else:
        _DEAD.append((handle, owner_ref))


def _seal(res: "Result", payload: Optional[dict[str, Any]]) -> str:
    mode = res.test_mode
    if mode is None:
        refusal: Optional[str] = "test_mode_unmarked"
    elif mode is True:
        refusal = "test_mode_synthetic"
    elif payload is not None:
        refusal = None
    else:
        refusal = res.stop_reason if res.stop_reason in _GATE_REASONS else "no_value_released"
    dec = use_decisions(res.rights) if res.rights else {"display": False, "derive": False, "ai": False}
    handle = secrets.token_hex(16)
    rec = _Sealed(mode, refusal, tuple(sorted(dec.items())),
                  json.dumps(payload, ensure_ascii=False, sort_keys=True) if (payload is not None and refusal is None) else None,
                  weakref.ref(res, lambda wr, _h=handle: _owner_gone(_h, wr)))
    with _SEAL_LOCK:
        _drain_dead()
        _SEALED[handle] = rec
        while len(_SEALED) > _SEAL_MAX:
            _SEALED.popitem(last=False)
    return handle


def _handoff_refuse(reason: str, decisions: Optional[dict[str, bool]] = None) -> dict[str, Any]:
    return {"schema": HANDOFF_SCHEMA, "released": False, "reason": reason,
            "decisions": dict(decisions or {"display": False, "derive": False, "ai": False}), "payload": None}


def _attribution_problem(attr: Any) -> Optional[str]:
    """結構化顯名檢查；回傳第一個問題碼，無問題回 None。不信任任何字串占位。"""
    if not isinstance(attr, dict):
        return "attribution_malformed"
    for k in _HANDOFF_TEXT_ATTR:
        v = attr.get(k)
        if not _nonblank(v) or str(v).strip().startswith("未載明"):
            return "attribution_malformed"
    if attr.get("license_url") != OGDL_LICENSE_URL:
        return "attribution_malformed"
    stated_values: dict[str, Any] = {}
    for k in STRUCTURED_ATTRIBUTION_FIELDS:
        f = attr.get(k)
        if not isinstance(f, dict) or type(f.get("stated")) is not bool or "value" not in f:
            return "attribution_malformed"
        v = f["value"]
        if f["stated"] is True:
            if not _nonblank(v) or str(v).strip().startswith("未載明") or str(v).strip().upper() in ("N/A", "NA", "NONE", "NULL", "-"):
                return "attribution_malformed"  # 宣稱已載明卻沒有（或只有占位的）值＝虛假 stated
            if k == "release_year" and not _YEAR_OK.match(str(v).strip()):
                return "attribution_malformed"
        elif v is not None:
            return "attribution_malformed"  # stated=False 卻帶值＝不一致，不放行
        stated_values[k] = v if f["stated"] is True else None
    meta = stated_values.get("metadata_updated_on")
    if meta is not None and meta in (stated_values.get("release_year"), stated_values.get("dataset_version")):
        return "attribution_substituted"  # 詮釋資料更新日不得冒充年份／版本
    for k in HANDOFF_STATED_REQUIRED:
        if stated_values.get(k) is None:
            return "attribution_not_stated"
    return None


def _release_gate(rights: Any, ld: Any) -> tuple[Optional[str], Optional[dict[str, Any]]]:
    """真實模式的顯示閘（純函式）：回 (拒絕原因碼, None) 或 (None, 固定鍵 payload)。不使用 assert、不做 I/O。"""
    if not isinstance(rights, dict) or not isinstance(ld, dict):
        return "no_value_released", None
    dec = use_decisions(rights)
    if not dec["display"] or rights.get("R2") != "ALLOWED":
        return "rights_unverified", None
    raw_code = ld.get("fund_code")
    code = raw_code.strip(" ").upper() if isinstance(raw_code, str) else ""
    if not _UI_CODE.fullmatch(code) or isin_valid(code):
        return "no_paired_code", None  # 無一對一代碼、與 🔍 的代碼文法不相容，或長得像 ISIN（不以 ISIN 代替）
    problem = _attribution_problem(ld.get("attribution"))
    if problem:
        return problem, None
    stamp = ld.get("fetched_at_utc")
    if not isinstance(stamp, str) or not _STAMP_OK.match(stamp):
        return "retrieved_at_invalid", None
    for k in ("nav", "currency", "nav_date", "fund_name", "source"):
        if not _nonblank(ld.get(k)):
            return "payload_incomplete", None
    payload = {"fund_code": code, "nav": ld["nav"], "currency": ld["currency"], "nav_date": ld["nav_date"],
               "fund_name": ld["fund_name"], "source": ld["source"], "retrieved_at_utc": stamp,
               "attribution": {k: (dict(v) if isinstance(v, dict) else v) for k, v in ld["attribution"].items()}}
    return None, payload


def display_handoff(res: Any) -> dict[str, Any]:
    """**唯一對外顯示出口**：把「本次 `run()` 內部登記」的結果轉成顯示端可吃的固定鍵集合；任何條件不足一律 `released=False` 並給封閉原因碼。

    - 只信 `run()` 內部登記的不可變內容（`_Sealed`）；手造 `Result`、事後改寫 `res.rights`／`res.local_display`／`res.test_mode` 一律無效（`not_issued_by_run`）。
    - 只有 `test_mode is False`（呼叫端明示的真實模式）且顯示閘通過才放行；`True`（合成）與 `None`（未標明）一律拒絕。
    - 權利由來源層 `use_decisions`（R2→顯示；R2∧R3→衍生；R2∧R3∧R4→AI）給出，**R3／R4 不由 R2 推導**；顯示端不得重算。
    - 輸出不含 ISIN、`consent_ref`、`basis_ref`、`run_id`；只有固定鍵。純函式：不連網、不落盤。**不使用 assert**。
    handle 綁定登記當時的 `Result` 實例（弱引用＋`is`）：把他人的 handle 貼到另一個 `Result`、淺拷貝、或實例已被釋放，皆拒收；原持有者照原核證結果。
    實例一被釋放（含循環 GC），其登記（含 `payload_json`）即被清除，不在登記表留下 NAV 內容（r108）。
    不宣稱抵禦同進程的惡意任意程式碼（那種程式可直接讀登記表或原實例）。
    """
    if not isinstance(res, Result):
        return _handoff_refuse("not_a_result")
    handle = res.handle
    with _SEAL_LOCK:
        _drain_dead()
        rec = _SEALED.get(handle) if isinstance(handle, str) else None
    if rec is None:
        return _handoff_refuse("not_issued_by_run")
    if rec.owner() is not res:  # r101 L1：handle 只對「登記當時的那個 Result 實例」有效；他人 handle 貼到別的 Result／淺拷貝／實例已釋放者一律拒收
        return _handoff_refuse("not_issued_by_run")
    decisions = dict(rec.decisions)
    if rec.refusal is not None or rec.payload_json is None:
        return _handoff_refuse(rec.refusal or "no_value_released", decisions)
    return {"schema": HANDOFF_SCHEMA, "released": True, "reason": None, "decisions": decisions, "payload": json.loads(rec.payload_json)}


# ───────────────────────── transport／runner ───────────────────────────────────
@dataclass
class Response:
    status: int
    content_type: str
    body: bytes
    content_encoding: str = "identity"


Transport = Callable[[str, int], Response]  # (url, max_bytes) -> Response


def _check_response(resp: Response, max_bytes: int) -> bytes:
    if 300 <= resp.status < 400:
        raise FetchStop("redirect_refused")
    if resp.status != 200:
        raise FetchStop(f"http_status_{resp.status}")
    if (resp.content_encoding or "identity").lower() != "identity":
        raise FetchStop("content_encoding_refused")
    if "json" not in (resp.content_type or "").lower():
        raise FetchStop("content_type_not_json")
    if len(resp.body) > max_bytes:
        raise FetchStop("oversize")
    return resp.body


class InProcessRunner:
    """離線／測試用：以注入的 transport 在本行程內執行（與 live 共用同一組 process_*）。"""

    def __init__(self, transport: Transport) -> None:
        self._t = transport

    def r0(self, url: str) -> dict[str, Any]:
        return process_r0(_check_response(self._t(url, R0_MAX_BYTES), R0_MAX_BYTES))

    def r1(self, url: str, isin: str) -> dict[str, Any]:
        return process_r1(_check_response(self._t(url, R1_MAX_BYTES), R1_MAX_BYTES), isin)


@dataclass
class Result:
    requests_used: int = 0
    r0_status: str = "not_run"
    r1_status: str = "not_run"
    binding: str = "not_evaluated"
    oas_version: Optional[str] = None
    class_doc_evidence: Optional[bool] = None
    stop_reason: Optional[str] = None
    rows_seen: Optional[int] = None
    n_selected_rows: Optional[int] = None
    distinct_dates: Optional[int] = None
    checks: Checks = field(default_factory=Checks)
    isin_matched: bool = False
    value_released: bool = False
    withheld_reason: Optional[str] = None
    rights: dict[str, str] = field(default_factory=dict)
    # 執行模式：True＝測試（可接受合成權利）；False＝**呼叫端明示**的真實模式；None＝未標明（不得出任何真 payload）。預設 None，不是 False。
    test_mode: Optional[bool] = None
    handle: Optional[str] = field(default=None, repr=False)  # 本次 run() 內部登記的不可猜 token（handoff 憑它查 sealed 內容）
    local_display: Optional[dict[str, Any]] = None  # 僅本機顯示；不得回存。真實模式下只有顯示閘放行才會有值（S1）

    def aggregate(self) -> dict[str, Any]:
        """可回存的技術聚合狀態：不含 ISIN、NAV、基金名稱、URL。"""
        return {
            "schema": "tdcc_11641_min_fetch.aggregate.v2",
            "requests_used": self.requests_used,
            "requests_max": MAX_REQUESTS,
            "r0": self.r0_status,
            "binding": self.binding,
            "oas_version": self.oas_version,
            "class_doc_evidence": self.class_doc_evidence,
            "r1": self.r1_status,
            "stop_reason": self.stop_reason,
            "rows_seen": self.rows_seen,
            "n_selected_rows": self.n_selected_rows,
            "distinct_dates": self.distinct_dates,
            "checks": vars(self.checks).copy(),
            "isin_matched": self.isin_matched,
            "value_released": self.value_released,
            "withheld_reason": self.withheld_reason,
            "rights": dict(self.rights),
            "use_decisions": use_decisions(self.rights) if self.rights else {},
            "formulas_called": 0,
            "long_term_metrics": "not_computed_insufficient_history_7d",
            "persistence": "none",
        }


def run(
    isin: str,
    *,
    user_confirmed_non_holding: Any,
    transport: Optional[Transport] = None,
    runner: Any = None,
    rights: Rights = Rights(),
    test_mode: Optional[bool] = None,
    run_id: Optional[str] = None,
    today: Optional[_dt.date] = None,
    now: Optional[Callable[[], _dt.datetime]] = None,
) -> Result:
    """執行 R-0／R-1 流程（runner／transport 由呼叫端注入；run 本身不連網）。任何失敗＝停止，不降級。"""
    res = Result()
    run_id = run_id or uuid.uuid4().hex
    mode = test_mode if type(test_mode) is bool else None  # 只認布林本身；"false"／0／1／物件等一律＝未標明（不得冒充真實模式）
    res.test_mode = mode
    res.rights = rights.normalized(test_mode=(mode is True), run_id=run_id)
    clock = now or (lambda: _dt.datetime.now(_dt.timezone.utc))
    today = today or clock().astimezone(TAIPEI).date()
    runner = runner or (InProcessRunner(transport) if transport is not None else None)
    stage_after_r1 = False
    payload_for_seal: Optional[dict[str, Any]] = None
    try:
        if mode is False:  # S3：真實模式只接受 `prepare_run()` 發出且尚未消耗的 nonce；一律在任何請求之前消耗（失敗後也不得重用）
            why = _consume_nonce(run_id)
            if why is not None:
                raise FetchStop(why)
        if runner is None:
            raise FetchStop("no_runner")
        if user_confirmed_non_holding is not True:  # 明示布林真值；字串／1／"yes" 皆不算
            raise FetchStop("user_confirmation_missing")
        isin = isin.strip().upper() if isinstance(isin, str) else ""
        res.checks.isin_format_ok = isin_format_ok(isin)
        if not res.checks.isin_format_ok:
            raise FetchStop("isin_invalid")
        res.checks.checksum_ok = isin_checksum_ok(isin)
        if not res.checks.checksum_ok:
            raise FetchStop("isin_invalid")

        res.requests_used += 1  # R-0（送出前即計次；失敗也耗額）
        try:
            info0 = runner.r0(R0_URL)
        except FetchStop:
            res.r0_status = "failed"
            raise
        res.r0_status = "ok"
        res.oas_version = info0.get("oas_version")
        res.class_doc_evidence = bool(info0.get("class_doc_ok"))
        try:
            url = assemble_url(info0.get("servers"), info0.get("path"))
        except FetchStop as e:
            res.binding = f"rejected:{e.reason}"
            raise
        res.binding = "unique_11641"

        res.requests_used += 1  # R-1
        try:
            info1 = runner.r1(url, isin)
        except FetchStop:
            res.r1_status = "failed"
            raise
        res.r1_status = "ok"
        stage_after_r1 = True
        res.rows_seen = info1["rows_seen"]
        res.n_selected_rows = len(info1["selected"])
        res.checks.found = res.n_selected_rows > 0
        if not res.checks.found:
            raise FetchStop("isin_not_found")
        res.isin_matched = True
        ev = evaluate_selection(info1, bool(info0.get("class_doc_ok")), today, res.checks)
        res.distinct_dates = ev["distinct_dates"]
        if ev["reason"]:
            raise FetchStop(ev["reason"])
        if not use_decisions(res.rights)["display"]:
            raise FetchStop("rights_unverified")  # 權利不足：扣值，保留原因
        if res.test_mode is None:
            raise FetchStop("test_mode_unmarked")  # 明確條件（非 assert，-O 不會移除）：未標明模式不得出任何真 payload
        picked = ev["picked"]
        fund_code = picked.get("fund_code")
        if not _nonblank(fund_code) or str(fund_code).strip().upper() == isin:
            fund_code = None  # 無可核證的一對一代碼，或代碼字串等於 ISIN（＝以 ISIN 代替代碼）⇒ 不提供 fund_code
        display = {
            "fund_code": fund_code.strip() if fund_code else None,
            "nav": str(picked["nav"]),
            "currency": picked["currency"],
            "nav_date": picked["nav_date"].isoformat(),
            "fund_name": picked["fund_name"],
            "source": "TDCC OpenAPI／data.gov.tw 11641",
            "fetched_at_utc": clock().astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
            "attribution": attribution_block(),
            "derived_metrics": "未計算（最近 7 日資料不足，不硬算 3-3-3／吃本金）",
        }
        if res.test_mode is False:  # S1：真實模式的唯一出口＝顯示閘；拒收時 Result 不暴露 NAV／基金名稱，也不誤報 value_released
            gate_reason, gate_payload = _release_gate(res.rights, display)
            if gate_reason is not None:
                raise FetchStop(gate_reason)
            payload_for_seal = gate_payload
        res.value_released = True
        res.local_display = display
    except FetchStop as e:
        if res.stop_reason is None:
            res.stop_reason = e.reason
        if stage_after_r1:
            res.withheld_reason = e.reason
    res.handle = _seal(res, payload_for_seal)
    return res


# ───────────────────────── 真實 transport（僅 LIVE_ENABLED 才可使用）───────────────
def live_guard_errors(env: Optional[dict[str, str]] = None) -> list[str]:
    """key log／代理環境變數出現即拒絕。"""
    env = os.environ if env is None else env
    errs = []
    if env.get("SSLKEYLOGFILE"):
        errs.append("sslkeylogfile_set")
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        if env.get(k):
            errs.append("proxy_env_set")
            break
    return errs


def assert_live_allowed(env: Optional[dict[str, str]] = None) -> None:
    """最後送出點與 factory 共用的授權守衛。"""
    if not LIVE_ENABLED:
        raise FetchStop("live_disabled")
    errs = live_guard_errors(env)
    if errs:
        raise FetchStop(errs[0])


def build_tls_context() -> ssl.SSLContext:
    """顯式 TLS：驗憑證與主機名、不寫 key log。"""
    import certifi

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.check_hostname = True
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_verify_locations(cafile=certifi.where())
    if hasattr(ctx, "keylog_filename"):
        ctx.keylog_filename = None  # type: ignore[attr-defined]
    return ctx


def _single_get(url: str, max_bytes: int, timeout: float) -> Response:
    """最後 HTTP 送出點：先守衛，再送；狀態／編碼／型別／宣告長度不符＝**不讀 body**；實讀至多 max_bytes+1。"""
    assert_live_allowed()
    verify_pinned_url(url)
    import urllib3

    parts = urlsplit(url)
    pool = urllib3.HTTPSConnectionPool(
        ORIGIN_HOST, port=443, ssl_context=build_tls_context(), cert_reqs="CERT_REQUIRED",
        retries=False, timeout=urllib3.Timeout(connect=timeout, read=timeout),
    )
    r = pool.request(
        "GET", parts.path, headers={"Accept": "application/json", "Accept-Encoding": "identity",
                                    "User-Agent": USER_AGENT},
        redirect=False, retries=False, preload_content=False,
    )
    try:
        if 300 <= r.status < 400:
            raise FetchStop("redirect_refused")
        if r.status != 200:
            raise FetchStop(f"http_status_{r.status}")
        enc = (r.headers.get("Content-Encoding") or "identity").lower()
        if enc not in ("", "identity"):
            raise FetchStop("content_encoding_refused")
        ctype = r.headers.get("Content-Type", "")
        if "json" not in ctype.lower():
            raise FetchStop("content_type_not_json")
        cl = r.headers.get("Content-Length")
        if cl is not None:
            try:
                if int(cl) > max_bytes:
                    raise FetchStop("oversize")
            except ValueError:
                raise FetchStop("content_length_invalid") from None
        buf = bytearray()
        while len(buf) < max_bytes + 1:
            chunk = r.read(min(64 * 1024, max_bytes + 1 - len(buf)), decode_content=False)
            if not chunk:
                break
            buf += chunk
        if len(buf) > max_bytes:
            raise FetchStop("oversize")
        return Response(r.status, ctype, bytes(buf), enc or "identity")
    finally:
        r.release_conn()
        r.close()


# ── worker 行程：頂層可 pickle（spawn 相容），整步（GET＋解析＋IPC）受同一牆鐘約束 ──────
def _entry_r0(url: str) -> dict[str, Any]:
    return process_r0(_check_response(_single_get(url, R0_MAX_BYTES, STEP_WALL_SECONDS), R0_MAX_BYTES))


def _entry_r1(url: str, isin: str) -> dict[str, Any]:
    return process_r1(_check_response(_single_get(url, R1_MAX_BYTES, STEP_WALL_SECONDS), R1_MAX_BYTES), isin)


_TLV_MAX_DEPTH = 8


def _tlv_encode(obj: Any, depth: int = 0) -> bytes:
    """worker 端：把純資料編成長度前綴二進位（TLV）。供監督者以**內建運算**解碼，不經 json／pickle。"""
    if depth > _TLV_MAX_DEPTH:
        raise ValueError("depth")
    if obj is None:
        return b"N"
    if obj is True:
        return b"T"
    if obj is False:
        return b"F"
    if isinstance(obj, int):
        return b"I" + obj.to_bytes(8, "big", signed=True)
    if isinstance(obj, str):
        raw = obj.encode("utf-8")
        return b"S" + len(raw).to_bytes(4, "big") + raw
    if isinstance(obj, list):
        return b"L" + len(obj).to_bytes(4, "big") + b"".join(_tlv_encode(x, depth + 1) for x in obj)
    if isinstance(obj, dict):
        if not all(isinstance(k, str) for k in obj):
            raise ValueError("key")
        return b"D" + len(obj).to_bytes(4, "big") + b"".join(
            _tlv_encode(k, depth + 1) + _tlv_encode(v, depth + 1) for k, v in obj.items())
    raise ValueError("type")


def _worker_main(conn: Any, entry: Callable[..., Any], args: tuple) -> None:
    try:
        payload = b"R" + _tlv_encode(entry(*args))
        if len(payload) > IPC_MAX_BYTES - 16:
            payload = b"Sresult_oversize"
    except FetchStop as e:
        payload = b"S" + e.reason.encode()
    except BaseException:  # noqa: BLE001 — 任何其他失敗只回固定碼，不夾帶訊息
        payload = b"E"
    conn.send_bytes(payload)
    conn.close()


def run_in_worker(entry: Callable[..., Any], args: tuple = (), *, wall: float = STEP_WALL_SECONDS,
                  reap: float = REAP_SECONDS, ctx: Any = None, worker: Callable[..., None] = _worker_main) -> Any:
    """於子行程執行 entry(*args)；牆鐘涵蓋啟動、執行、IPC 接收與結果還原；固定錯誤碼；有界回收。

    **監督者行程不對子行程產出做任何 json／pickle／第三方反序列化**：
      - IPC 只用 `Connection.recv_bytes`（I/O，釋放 GIL；上限 IPC_MAX_BYTES）。
      - 結果為 worker 以 TLV 編碼的純資料，由本函式內的巢狀解碼器以**內建運算**（切片、`int.from_bytes`、
        `bytes.decode`）還原；長度嚴格檢查、深度與總量有上限，僅處理 ≤64 KiB 且不經任何可替換的模組函式。
      - 因此監督期限、worker 截斷與有界回收不依賴任何「可能持有 GIL 的反序列化」：
        `multiprocessing.connection._ForkingPickler.loads`、`json.loads`、本模組任何函式被替換成持 GIL 的呼叫，
        皆不影響本函式的回傳時刻。
      - 到期即 kill worker 並進入回收；逾期任何結果一律拒絕（`wall_clock_timeout`）。
      - 回收：join(reap) → kill → join(reap)；仍存活 ⇒ UNREAPED（優先於其他碼，硬停）。
    """
    import multiprocessing as mp
    import threading
    import time

    ctx = ctx or mp.get_context("spawn")
    t0 = time.monotonic()
    parent, child = ctx.Pipe(duplex=False)
    p = ctx.Process(target=worker, args=(child, entry, tuple(args)), daemon=True)
    p.start()
    child.close()
    box: dict[str, Any] = {}

    def _rx() -> None:
        try:
            box["raw"] = parent.recv_bytes(IPC_MAX_BYTES)
        except EOFError:
            box["err"] = "ipc_truncated"
        except OSError as e:
            msg = str(e)
            box["err"] = ("ipc_oversize" if "bad message length" in msg
                          else "ipc_truncated" if ("end of file" in msg or isinstance(e, ConnectionResetError))
                          else "ipc_error")
        except BaseException:  # noqa: BLE001
            box["err"] = "ipc_error"

    class _Bad(Exception):
        pass

    def _unpack(buf: bytes) -> Any:  # 巢狀＝無法被模組層替換；僅內建運算
        n, pos = len(buf), 0

        def item(depth: int) -> Any:
            nonlocal pos
            if depth > _TLV_MAX_DEPTH or pos >= n:
                raise _Bad
            t = buf[pos:pos + 1]
            pos += 1
            if t == b"N":
                return None
            if t == b"T":
                return True
            if t == b"F":
                return False
            if t == b"I":
                if pos + 8 > n:
                    raise _Bad
                v = int.from_bytes(buf[pos:pos + 8], "big", signed=True)
                pos += 8
                return v
            if t in (b"S", b"L", b"D"):
                if pos + 4 > n:
                    raise _Bad
                k = int.from_bytes(buf[pos:pos + 4], "big")
                pos += 4
                if t == b"S":
                    if pos + k > n:
                        raise _Bad
                    sv = buf[pos:pos + k].decode("utf-8")
                    pos += k
                    return sv
                if k > n:  # 元素數不可能超過總長
                    raise _Bad
                if t == b"L":
                    return [item(depth + 1) for _ in range(k)]
                out: dict = {}
                for _ in range(k):
                    key = item(depth + 1)
                    if not isinstance(key, str):
                        raise _Bad
                    out[key] = item(depth + 1)
                return out
            raise _Bad

        v = item(0)
        if pos != n:
            raise _Bad
        return v

    rx = threading.Thread(target=_rx, daemon=True)
    rx.start()
    rx.join(max(0.0, wall - (time.monotonic() - t0)))
    timed_out = rx.is_alive()
    result: Any = None
    err: Optional[str] = None
    if not timed_out:
        if "raw" in box:
            raw = box["raw"]
            tag, body = raw[:1], raw[1:]
            if tag == b"R":
                try:
                    result = _unpack(body)
                except (_Bad, UnicodeDecodeError, RecursionError):
                    err = "ipc_bad_payload"
            elif tag == b"S":
                reason = body.decode("utf-8", "replace")
                err = reason if _REASON.match(reason) else "step_error"
            else:
                err = "step_error"
        else:
            err = box.get("err") or "ipc_error"
    if (time.monotonic() - t0) > wall:
        timed_out = True  # 逾期任何結果一律不用
    if timed_out or p.is_alive():
        _safe_kill(p)
    p.join(reap)
    unreaped = False
    if p.is_alive():
        _safe_kill(p)
        p.join(reap)
        unreaped = p.is_alive()
    _safe_close(parent)
    if unreaped:
        raise FetchStop("UNREAPED")
    if timed_out:
        raise FetchStop("wall_clock_timeout")
    if err is not None:
        raise FetchStop(err)
    return result


def _safe_close(c: Any) -> None:
    try:
        c.close()
    except Exception:  # noqa: BLE001
        pass


def _safe_kill(p: Any) -> None:
    try:
        p.kill()
    except Exception:  # noqa: BLE001
        pass


class WorkerRunner:
    """live 用：每步一個 spawn 子行程；送出點另有授權守衛。"""

    def r0(self, url: str) -> dict[str, Any]:
        return run_in_worker(_entry_r0, (url,))

    def r1(self, url: str, isin: str) -> dict[str, Any]:
        return run_in_worker(_entry_r1, (url, isin))


def make_live_runner() -> WorkerRunner:
    """建立真實 runner；`LIVE_ENABLED` 為 False 時一律拒絕（本 PR 預設）。"""
    assert_live_allowed()
    return WorkerRunner()


# ───────────────────────── CLI ─────────────────────────────────────────────────
def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="11641 最小取數（預設離線；真網路另案授權）。注意：CLI 無 R2 授權入口，永遠只輸出技術聚合。")
    ap.add_argument("--isin", required=True, help="使用者親自確認之『非持倉』公開 ISIN（只在本機比對）")
    ap.add_argument("--confirm-non-holding", action="store_true",
                    help="聲明：此 ISIN 由使用者本人確認非持倉")
    ns = ap.parse_args(argv)
    try:
        runner = make_live_runner()
    except FetchStop as e:
        print(json.dumps({"schema": "tdcc_11641_min_fetch.aggregate.v2", "requests_used": 0,
                          "stop_reason": e.reason, "persistence": "none"}, ensure_ascii=False))
        return 2
    res = run(ns.isin, user_confirmed_non_holding=bool(ns.confirm_non_holding), runner=runner)
    print("# 可回存（技術聚合）：")
    print(json.dumps(res.aggregate(), ensure_ascii=False, indent=2))
    handoff = display_handoff(res)  # S1：唯一對外顯示出口；拒收時不印任何 NAV／基金名稱
    if handoff["released"]:
        print("# 僅本機顯示（勿回存／外傳）：")
        print(json.dumps(handoff["payload"], ensure_ascii=False, indent=2))
    return 0 if res.stop_reason is None else 1


if __name__ == "__main__":
    sys.exit(main())
