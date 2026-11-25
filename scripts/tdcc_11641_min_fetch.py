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
import ssl
import sys
import uuid
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


def _check_no_required_params_or_auth(oas: dict, op: dict, item: dict) -> None:
    """參數／認證結構須完整可驗：未宣告（鍵不存在）與宣告為 null／錯型別不同——後者＝證據不明＝停。"""
    for holder in (item, op):
        if "parameters" not in holder:
            continue  # 未宣告＝無參數（合法）
        plist = holder["parameters"]
        if not isinstance(plist, list):  # 含 null
            raise FetchStop("op_params_invalid")
        for p in plist:
            p = _resolve(p, oas)
            if (not isinstance(p, dict) or not _nonblank(p.get("name")) or p.get("in") not in _PARAM_IN
                    or not (isinstance(p.get("schema"), dict) or isinstance(p.get("content"), dict))):
                raise FetchStop("op_params_invalid")
            if "required" in p and not isinstance(p["required"], bool):
                raise FetchStop("op_params_invalid")
            if p.get("in") == "path" and p.get("required") is not True:
                raise FetchStop("op_params_invalid")  # OAS：path 參數必為 required
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


_SEP = r"[^，。；;,]"
# ISIN 說明須正向載明「唯一識別一個（單一）份額級別」；『各份額級別』『共用』等泛稱不算
_ISIN_UNIQUE = re.compile(
    rf"唯一(識別|對應|代表){_SEP}{{0,6}}(一個|單一)?份額級別"
    rf"|(一個|單一)份額級別{_SEP}{{0,6}}(對應|僅對應|只對應){_SEP}{{0,4}}(一個|唯一)\s*isin"
    r"|uniquely identifies (a|one|a single) share class",
    re.I)
# 代碼說明須載明其為基金／份額級別的身分代碼（不能只是「有說明」）
_CODE_IDENTITY = re.compile(rf"(基金|份額級別)(代碼|代號){_SEP}{{0,12}}(識別|代表|對應){_SEP}{{0,12}}(基金|份額級別)"
                            r"|fund code identifies (the|a) (fund|share class)", re.I)
_SHARED = ("各份額級別", "共用", "共享", "共同", "多個", "多支", "同一 isin", "同一isin", "shared", "multiple",
           "any class", "all classes", "行銷", "促銷", "活動", "campaign", "promo", "廣告")
_NEGATION = ("不代表", "不是", "並非", "非", "無法", "未", "沒有", "不含", "不具", "不為", "不屬", "不提供", "不包含",
             "not ", "no ", "n't", "cannot", "without", "unrelated")


def _clean_text(desc: Any) -> Optional[str]:
    """說明文字須為非空字串，且不含否定詞、共用／多對一／無關（行銷等）標記；否則視為無正向證據（fail-closed）。"""
    if not isinstance(desc, str) or not desc.strip():
        return None
    low = desc.lower()
    if any(n in low for n in _NEGATION) or any(x in low for x in _SHARED):
        return None
    return desc


def _isin_schema_structure_ok(sch: Any) -> bool:
    """結構佐證（不只靠文字）：ISIN 欄位須宣告固定 12 碼（minLength／maxLength 為 12，或 pattern 含 12／{10}）。"""
    if not isinstance(sch, dict):
        return False
    if sch.get("minLength") == 12 or sch.get("maxLength") == 12:
        return True
    pat = sch.get("pattern")
    return isinstance(pat, str) and ("{10}" in pat or "12" in pat)


def _class_doc_evidence(props: dict) -> bool:
    """文件層證據（rev2 §四.1）：ISIN＝正向『唯一識別單一份額級別』文字＋12 碼結構；代碼＝基金／級別身分語意。缺 ⇒ False。"""
    isin_txt = _clean_text(props[KEY_ISIN].get("description"))
    code_txt = _clean_text(props[KEY_CODE].get("description"))
    return bool(isin_txt and _ISIN_UNIQUE.search(isin_txt) and code_txt and _CODE_IDENTITY.search(code_txt)
                and _isin_schema_structure_ok(props[KEY_ISIN]))


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
        out["picked"] = {"nav": nav, "currency": ccy, "nav_date": latest, "fund_name": parsed[0][4]}
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


def attribution_block() -> dict[str, Any]:
    """OGDL 顯名區塊（只用既有可回查證據；未取得者如實標示，不猜）。"""
    missing = "未載明（本次未取得）"
    return {
        "license_statement": "本資料由提供機關公開釋出，依《政府資料開放授權條款－第1版》提供；須遵循該條款方可利用。",
        "license_url": OGDL_LICENSE_URL,
        "agency": "金融監督管理委員會證券期貨局",
        "source_org": "臺灣集中保管結算所",
        "dataset": "境外基金淨值（data.gov.tw 11641）",
        "release_year": missing,
        "dataset_version": missing,
        "metadata_updated_on": "未載明（有衝突，待覆核）",
    }


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
    local_display: Optional[dict[str, Any]] = None  # 僅本機顯示；不得回存

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
    test_mode: bool = False,
    run_id: Optional[str] = None,
    today: Optional[_dt.date] = None,
    now: Optional[Callable[[], _dt.datetime]] = None,
) -> Result:
    """執行 R-0／R-1 流程（runner／transport 由呼叫端注入；run 本身不連網）。任何失敗＝停止，不降級。"""
    res = Result()
    run_id = run_id or uuid.uuid4().hex
    res.rights = rights.normalized(test_mode=test_mode, run_id=run_id)
    clock = now or (lambda: _dt.datetime.now(_dt.timezone.utc))
    today = today or clock().astimezone(TAIPEI).date()
    runner = runner or (InProcessRunner(transport) if transport is not None else None)
    stage_after_r1 = False
    try:
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
        picked = ev["picked"]
        res.value_released = True
        res.local_display = {
            "nav": str(picked["nav"]),
            "currency": picked["currency"],
            "nav_date": picked["nav_date"].isoformat(),
            "fund_name": picked["fund_name"],
            "source": "TDCC OpenAPI／data.gov.tw 11641",
            "fetched_at_utc": clock().astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
            "attribution": attribution_block(),
            "derived_metrics": "未計算（最近 7 日資料不足，不硬算 3-3-3／吃本金）",
        }
    except FetchStop as e:
        if res.stop_reason is None:
            res.stop_reason = e.reason
        if stage_after_r1:
            res.withheld_reason = e.reason
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


def _worker_main(conn: Any, entry: Callable[..., Any], args: tuple) -> None:
    try:
        payload = b"R" + json.dumps(entry(*args), ensure_ascii=False).encode("utf-8")
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
    """於子行程執行 entry(*args)；牆鐘涵蓋啟動、執行、解析與 IPC 接收；固定錯誤碼；有界回收。

    - 一律 spawn（跨平台一致；entry 須為頂層可 pickle 函式）。
    - 父行程關閉自己手上的寫端：子行程一死即得 EOF。
    - 監督者（本函式）**不**同步等待接收：接收在 daemon 執行緒，監督者以 `join(剩餘牆鐘)` 自行計時；
      到期即 kill 子行程並進入回收，**不論接收執行緒是否已退出**（回收不再受接收阻塞）。
    - 逾期後即使收到完整 frame 亦拒絕（`wall_clock_timeout`），不回傳任何結果。
    - 回收：join(reap) → kill → join(reap)；仍存活 ⇒ UNREAPED（優先於其他碼，硬停）。
    """
    import multiprocessing as mp
    import threading
    import time

    ctx = ctx or mp.get_context("spawn")
    parent, child = ctx.Pipe(duplex=False)
    t0 = time.monotonic()
    p = ctx.Process(target=worker, args=(child, entry, tuple(args)), daemon=True)
    p.start()
    child.close()
    box: dict[str, Any] = {}

    def _rx() -> None:
        try:
            data = parent.recv_bytes(IPC_MAX_BYTES)
            tag, body = data[:1], data[1:]
            if tag == b"R":  # JSON 解碼也在受牆鐘約束的執行緒內
                box["ok"] = json.loads(body.decode("utf-8"))
            elif tag == b"S":
                reason = body.decode("utf-8", "replace")
                box["err"] = reason if _REASON.match(reason) else "step_error"
            else:
                box["err"] = "step_error"
        except EOFError:
            box["err"] = "ipc_truncated"
        except (ValueError, UnicodeDecodeError):
            box["err"] = "ipc_bad_payload"
        except OSError as e:
            msg = str(e)
            box["err"] = ("ipc_oversize" if "bad message length" in msg
                          else "ipc_truncated" if ("end of file" in msg or isinstance(e, ConnectionResetError))
                          else "ipc_error")
        except BaseException:  # noqa: BLE001
            box["err"] = "ipc_error"

    rx = threading.Thread(target=_rx, daemon=True)
    rx.start()
    rx.join(max(0.0, wall - (time.monotonic() - t0)))
    elapsed = time.monotonic() - t0
    timed_out = rx.is_alive() or elapsed > wall  # 以接收＋解碼完成後的時刻判定；逾期任何結果一律不用
    if timed_out:
        _safe_kill(p)  # 接收／解碼未完成或已逾期：先殺，再獨立回收
    p.join(reap)
    if p.is_alive():
        _safe_kill(p)
        p.join(reap)
        if p.is_alive():
            _safe_close(parent)
            raise FetchStop("UNREAPED")
    _safe_close(parent)
    if timed_out:
        raise FetchStop("wall_clock_timeout")
    if "ok" in box:
        return box["ok"]
    raise FetchStop(box.get("err") or "ipc_error")


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
    if res.local_display:
        print("# 僅本機顯示（勿回存／外傳）：")
        print(json.dumps(res.local_display, ensure_ascii=False, indent=2))
    return 0 if res.stop_reason is None else 1


if __name__ == "__main__":
    sys.exit(main())
