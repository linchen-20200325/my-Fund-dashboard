"""11641 最小取數腳本（B-TDCC-REAL-NAV-S1）：境外基金淨值，本機單檔查詢。

⛔ 預設**不連網**。真實 OAS／資料請求仍 HOLD（DEC-2026-11-19-02），需客戶另行明示授權後，
由「改動 `LIVE_ENABLED`」的獨立 PR 開啟；本 PR 內 `LIVE_ENABLED = False`，CLI 只做離線說明，
任何 transport 都不會被建立。離線測試一律注入假 transport。

規格來源（#1296）：rev2 #7131294864 → rev3 #7131668066 → rev3.1 #7132882773（Work PASS #7132928714）；
施工授權 #7133015104。限制（全部沿用，不放寬）：
  * 全程至多 2 次 GET：R-0（OAS JSON，≤2 MiB）、R-1（唯一核證端點，≤16 MiB／≤100,000 列）；
    各 20 s 硬牆鐘；0 重試、0 轉址、0 額外 GET；TLS verify；不走代理；不寫 key log。
  * R-1 前必須有官方文件（R-0 的 OAS）**明示且唯一**引用 data.gov.tw 11641 的 GET 操作；
    組裝後 URL 須 https＋host 精確＋精確路徑，拒完整 `.`／`..` 段，
    且 client 準備送出的 URL 與已釘住 URL 逐字一致；證據不足 ⇒ R-1＝0。
  * 只接受使用者親自確認「非持倉」的公開 ISIN；僅在本機比對；零 fallback
    （不以基金代碼／名稱補比）；不讀持倉、Secrets、Sheet；零落盤（不寫任何檔）。
  * 權利（R2／R3／R4）由呼叫端注入；缺／UNKNOWN／DENY ⇒ 扣下數值並保留原因（腳本本身不宣告 ALLOWED）。
  * 公式（check_333_principle／classify_eating_principal）呼叫 0 次；最近 7 日資料不足長期健診。
  * 回存（GitHub）只限技術聚合狀態：不含 ISIN、NAV 值、基金名稱。

NOT VERIFIED（需實際 R-0 才能確認，**不得**以本檔內常數當作已驗證事實）：
R-0 實際 URL 與回應形態、OAS 是否真有唯一對應 11641 的操作、R-1 欄位名稱與日期／幣別格式。
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import ssl
import sys
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Optional
from urllib.parse import urlsplit

# ── 開關：真網路（本 PR 必須為 False；開啟屬另案客戶授權）──────────────────────
LIVE_ENABLED = False

# ── 釘住常數（變更任何一項＝改變授權範圍，須重新取得授權）────────────────────────
ORIGIN_HOST = "openapi.tdcc.com.tw"
# R-0：官方 OAS 文件位置（使用者提供之官方文件網址；若實際不是 JSON ⇒ R-0 內容檢查失敗 ⇒ R-1＝0）
R0_URL = "https://openapi.tdcc.com.tw/tdcc-opendata-api-docs"
DATASET_ID = "11641"
MAX_REQUESTS = 2
R0_MAX_BYTES = 2 * 1024 * 1024
R1_MAX_BYTES = 16 * 1024 * 1024
R1_MAX_ROWS = 100_000
STEP_WALL_SECONDS = 20.0
REAP_SECONDS = 2.0
USER_AGENT = "tdcc-11641-min-fetch/1 (local read-only; no automation)"
# R-1 欄位名（NOT VERIFIED；缺任一 ⇒ schema_mismatch，不猜別名＝零 fallback）
KEY_ISIN, KEY_NAV, KEY_DATE, KEY_CCY, KEY_NAME = "ISINCODE", "NAV", "日期", "計價幣別", "基金名稱"
REQUIRED_KEYS = (KEY_ISIN, KEY_NAV, KEY_DATE, KEY_CCY, KEY_NAME)

OGDL_LICENSE_URL = "https://data.gov.tw/license"
_SEG = re.compile(r"^[A-Za-z0-9._~-]+$")
_FINAL = re.compile(r"^https://openapi\.tdcc\.com\.tw(/[A-Za-z0-9._~-]+)+$")
_DATASET_REF = re.compile(r"https?://data\.gov\.tw/dataset/(\d+)", re.I)
_ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
RIGHTS_AXES = ("R2", "R3", "R4")
RIGHTS_VALUES = ("ALLOWED", "UNKNOWN", "DENY")


class FetchStop(Exception):
    """失敗即停止：帶機器可讀 reason；訊息不含 URL、ISIN 或回應內容。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# ───────────────────────── 純函式：ISIN／URL／綁定 ─────────────────────────────
def isin_valid(isin: str) -> bool:
    """ISIN 格式＋Luhn 檢查碼（字母轉兩位數字）。"""
    if not isinstance(isin, str) or not _ISIN.match(isin):
        return False
    digits = "".join(str(int(c, 36)) for c in isin)
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            d = d - 9 if d > 9 else d
        total += d
    return total % 10 == 0


def _prepared_url(url: str) -> str:
    """實際 client（urllib3）準備送出的 URL（含 dot-segment 正規化）。"""
    from urllib3.util import parse_url

    return parse_url(url).url


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


def bind_dataset_operation(oas: Any) -> tuple[str, dict]:
    """在 OAS 中找「GET 操作且只明示引用 data.gov.tw 11641」者；恰 1 個才回 (path, operation)。

    引用＝操作內任一字串含 `https://data.gov.tw/dataset/<id>`；同名摘要、相似欄位一律不算。
    """
    if not isinstance(oas, dict) or not isinstance(oas.get("paths"), dict):
        raise FetchStop("oas_shape")
    hits: list[tuple[str, dict]] = []
    for path, item in oas["paths"].items():
        if not isinstance(item, dict) or not isinstance(item.get("get"), dict):
            continue
        op = item["get"]
        refs = {m for s in _walk_strings(op) for m in _DATASET_REF.findall(s)}
        if refs == {DATASET_ID}:
            hits.append((path, op))
    if not hits:
        raise FetchStop("binding_none")
    if len(hits) > 1:
        raise FetchStop("binding_ambiguous")
    return hits[0]


# ───────────────────────── 權利／顯名／列處理 ──────────────────────────────────
@dataclass(frozen=True)
class Rights:
    """四軸權利狀態；腳本不自行宣告 ALLOWED（呼叫端以有依據之授權注入）。"""

    r2: str = "UNKNOWN"
    r3: str = "UNKNOWN"
    r4: str = "UNKNOWN"
    basis_ref: Optional[str] = None
    synthetic: bool = False

    def normalized(self, *, test_mode: bool) -> dict[str, str]:
        out: dict[str, str] = {}
        for axis, val in zip(RIGHTS_AXES, (self.r2, self.r3, self.r4)):
            ok = val == "ALLOWED" and bool(self.basis_ref) and (test_mode or not self.synthetic)
            out[axis] = "ALLOWED" if ok else (val if val == "DENY" else "UNKNOWN")
        return out


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


def _parse_date(raw: Any, today: _dt.date) -> _dt.date:
    s = str(raw).strip() if raw is not None else ""
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            d = _dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
        if d > today + _dt.timedelta(days=1):
            raise FetchStop("nav_date_in_future")
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


def select_row(rows: list[Any], isin: str, today: _dt.date) -> dict[str, Any]:
    """零 fallback：只以 ISIN 精確比對；取最新日；同日異值＝衝突⇒扣下。"""
    matched = [r for r in rows if isinstance(r, dict) and str(r.get(KEY_ISIN, "")).strip().upper() == isin]
    if not matched:
        raise FetchStop("isin_not_found")
    parsed: list[tuple[_dt.date, Decimal, str, str]] = []
    for r in matched:
        ccy = str(r.get(KEY_CCY, "")).strip()
        name = str(r.get(KEY_NAME, "")).strip()
        if not re.fullmatch(r"[A-Z]{3}", ccy):
            raise FetchStop("ccy_unrecognized")
        if not name:
            raise FetchStop("class_unverified")
        parsed.append((_parse_date(r.get(KEY_DATE), today), _parse_nav(r.get(KEY_NAV)), ccy, name))
    if len({(c, n) for _, _, c, n in parsed}) != 1:
        raise FetchStop("class_conflict")
    latest = max(p[0] for p in parsed)
    at_latest = {(p[1], p[2]) for p in parsed if p[0] == latest}
    if len(at_latest) != 1:
        raise FetchStop("same_day_conflict")
    nav, ccy = next(iter(at_latest))
    return {"nav": nav, "currency": ccy, "nav_date": latest, "fund_name": parsed[0][3]}


# ───────────────────────── transport（可注入；真實版受 LIVE_ENABLED 守衛）──────────
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


@dataclass
class Result:
    requests_used: int = 0
    r0_status: str = "not_run"
    r1_status: str = "not_run"
    binding: str = "not_evaluated"
    stop_reason: Optional[str] = None
    rows_seen: Optional[int] = None
    isin_matched: bool = False
    value_released: bool = False
    withheld_reason: Optional[str] = None
    rights: dict[str, str] = field(default_factory=dict)
    local_display: Optional[dict[str, Any]] = None  # 僅本機顯示；不得回存

    def aggregate(self) -> dict[str, Any]:
        """可回存的技術聚合狀態：不含 ISIN、NAV、基金名稱、URL。"""
        return {
            "schema": "tdcc_11641_min_fetch.aggregate.v1",
            "requests_used": self.requests_used,
            "requests_max": MAX_REQUESTS,
            "r0": self.r0_status,
            "binding": self.binding,
            "r1": self.r1_status,
            "stop_reason": self.stop_reason,
            "rows_seen": self.rows_seen,
            "isin_matched": self.isin_matched,
            "value_released": self.value_released,
            "withheld_reason": self.withheld_reason,
            "rights": dict(self.rights),
            "formulas_called": 0,
            "long_term_metrics": "not_computed_insufficient_history_7d",
            "persistence": "none",
        }


def run(
    isin: str,
    *,
    user_confirmed_non_holding: bool,
    transport: Transport,
    rights: Rights = Rights(),
    test_mode: bool = False,
    today: Optional[_dt.date] = None,
    now: Optional[Callable[[], _dt.datetime]] = None,
) -> Result:
    """執行 R-0／R-1 流程（transport 由呼叫端注入；run 本身不連網）。任何失敗＝停止，不降級。"""
    res = Result()
    res.rights = rights.normalized(test_mode=test_mode)
    clock = now or (lambda: _dt.datetime.now(_dt.timezone.utc))
    today = today or clock().date()
    try:
        if not user_confirmed_non_holding:
            raise FetchStop("user_confirmation_missing")
        isin = (isin or "").strip().upper()
        if not isin_valid(isin):
            raise FetchStop("isin_invalid")

        res.requests_used += 1  # R-0（送出前即計次；失敗也耗額）
        try:
            body0 = _check_response(transport(R0_URL, R0_MAX_BYTES), R0_MAX_BYTES)
            oas = json.loads(body0.decode("utf-8"))
        except FetchStop:
            res.r0_status = "failed"
            raise
        except (ValueError, UnicodeDecodeError):
            res.r0_status = "failed"
            raise FetchStop("r0_not_json") from None
        res.r0_status = "ok"

        try:
            path, _op = bind_dataset_operation(oas)
            url = assemble_url(oas.get("servers"), path)
        except FetchStop as e:
            res.binding = f"rejected:{e.reason}"
            raise
        res.binding = "unique_11641"

        res.requests_used += 1  # R-1
        try:
            body1 = _check_response(transport(url, R1_MAX_BYTES), R1_MAX_BYTES)
            rows = json.loads(body1.decode("utf-8"))
        except FetchStop:
            res.r1_status = "failed"
            raise
        except (ValueError, UnicodeDecodeError):
            res.r1_status = "failed"
            raise FetchStop("r1_not_json") from None
        if not isinstance(rows, list):
            res.r1_status = "failed"
            raise FetchStop("r1_not_list")
        if len(rows) > R1_MAX_ROWS:
            res.r1_status = "failed"
            raise FetchStop("too_many_rows")
        res.rows_seen = len(rows)
        if rows and not (isinstance(rows[0], dict) and all(k in rows[0] for k in REQUIRED_KEYS)):
            res.r1_status = "failed"
            raise FetchStop("schema_mismatch")
        res.r1_status = "ok"

        picked = select_row(rows, isin, today)
        res.isin_matched = True
        if res.rights["R2"] != "ALLOWED":
            raise FetchStop("rights_unverified")  # 權利不足：扣值，保留原因
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
        if e.reason in {"rights_unverified", "same_day_conflict", "class_conflict", "class_unverified",
                        "ccy_unrecognized", "nav_unreadable", "nav_not_positive", "nav_date_unreadable",
                        "nav_date_in_future", "isin_not_found"}:
            res.withheld_reason = e.reason
    return res


# ───────────────────────── 真實 transport（僅 LIVE_ENABLED 才可建立）─────────────────
def live_guard_errors(env: Optional[dict[str, str]] = None) -> list[str]:
    """開啟真網路前的守衛：key log／代理環境變數出現即拒絕。"""
    env = os.environ if env is None else env
    errs = []
    if env.get("SSLKEYLOGFILE"):
        errs.append("sslkeylogfile_set")
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        if env.get(k):
            errs.append("proxy_env_set")
            break
    return errs


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
    """單次 GET：無轉址／無重試／無代理／identity 編碼；串流讀取並以上限截斷判定。"""
    import urllib3

    parts = urlsplit(url)
    if parts.scheme != "https" or (parts.hostname or "") != ORIGIN_HOST or parts.port is not None:
        raise FetchStop("origin_not_pinned")
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
        buf = bytearray()
        for chunk in r.stream(64 * 1024, decode_content=False):
            buf += chunk
            if len(buf) > max_bytes:
                raise FetchStop("oversize")
        return Response(r.status, r.headers.get("Content-Type", ""), bytes(buf),
                        r.headers.get("Content-Encoding", "identity"))
    finally:
        r.release_conn()
        r.close()


def run_step_with_wall_clock(fn: Callable[[], Any], *, wall: float = STEP_WALL_SECONDS,
                             reap: float = REAP_SECONDS) -> Any:
    """於子行程執行單一 HTTP 步驟；牆鐘逾時即終止並回收，回收失敗 ⇒ UNREAPED（硬停）。"""
    import multiprocessing as mp

    ctx = mp.get_context("spawn" if sys.platform == "win32" else "fork")
    parent, child = ctx.Pipe(duplex=False)

    def _target() -> None:
        try:
            child.send_bytes(b"R" + _dump(fn()))
        except FetchStop as e:
            child.send_bytes(b"S" + e.reason.encode())
        except BaseException:  # noqa: BLE001 — 子行程任何失敗都只回固定碼，不夾帶訊息
            child.send_bytes(b"E")

    p = ctx.Process(target=_target, daemon=True)
    p.start()
    got = parent.poll(wall)
    data = parent.recv_bytes() if got else None
    if not got:
        p.terminate()
        p.join(reap)
        if p.is_alive():
            p.kill()
            p.join(reap)
            if p.is_alive():
                raise FetchStop("UNREAPED")
        raise FetchStop("wall_clock_timeout")
    p.join(reap)
    if data[:1] == b"R":
        return _load(data[1:])
    if data[:1] == b"S":
        raise FetchStop(data[1:].decode())
    raise FetchStop("step_error")


def _dump(obj: Any) -> bytes:
    if isinstance(obj, Response):
        return json.dumps({"s": obj.status, "t": obj.content_type, "e": obj.content_encoding,
                           "b": obj.body.hex()}).encode()
    return json.dumps(obj).encode()


def _load(raw: bytes) -> Any:
    d = json.loads(raw.decode())
    if isinstance(d, dict) and set(d) == {"s", "t", "e", "b"}:
        return Response(d["s"], d["t"], bytes.fromhex(d["b"]), d["e"])
    return d


def make_live_transport() -> Transport:
    """建立真實 transport；`LIVE_ENABLED` 為 False 時一律拒絕（本 PR 預設）。"""
    if not LIVE_ENABLED:
        raise FetchStop("live_disabled")
    errs = live_guard_errors()
    if errs:
        raise FetchStop(errs[0])

    def _t(url: str, max_bytes: int) -> Response:
        return run_step_with_wall_clock(lambda: _single_get(url, max_bytes, STEP_WALL_SECONDS))

    return _t


# ───────────────────────── CLI ─────────────────────────────────────────────────
def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="11641 最小取數（預設離線；真網路另案授權）")
    ap.add_argument("--isin", required=True, help="使用者親自確認之『非持倉』公開 ISIN（只在本機比對）")
    ap.add_argument("--confirm-non-holding", action="store_true",
                    help="聲明：此 ISIN 由使用者本人確認非持倉")
    ns = ap.parse_args(argv)
    try:
        transport = make_live_transport()
    except FetchStop as e:
        print(json.dumps({"schema": "tdcc_11641_min_fetch.aggregate.v1", "requests_used": 0,
                          "stop_reason": e.reason, "persistence": "none"}, ensure_ascii=False))
        return 2
    res = run(ns.isin, user_confirmed_non_holding=ns.confirm_non_holding, transport=transport)
    print("# 可回存（技術聚合）：")
    print(json.dumps(res.aggregate(), ensure_ascii=False, indent=2))
    if res.local_display:
        print("# 僅本機顯示（勿回存／外傳）：")
        print(json.dumps(res.local_display, ensure_ascii=False, indent=2))
    return 0 if res.stop_reason is None else 1


if __name__ == "__main__":
    sys.exit(main())
