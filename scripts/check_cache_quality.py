#!/usr/bin/env python3
"""scripts/check_cache_quality.py — A1「離線唯讀快取品質檢查」.

授權依據：``DEC-2026-11-10-02``（客戶核准 A1：一支唯讀檢查腳本＋測試＋文件）；
研究依據：``docs/evidence/cache_quality_intraday_freeze_study_2026_11_10.md``。

本腳本只做一件事：**讀** ``data_cache/`` 下既有的 4 個 parquet 與 ``metadata.json``
（必要時以本機 ``git log`` / ``git show`` 唯讀回看歷史版本，以及讀入一份本機參考
``report.json``），產出一份「可重現的離線報告」。

硬邊界（違反任一條視同 bug）
============================
* **零網路**：不 import requests / yfinance / urllib.request / httpx，不開 socket。
* **零寫入**：不改 ``data_cache``、``metadata.json``、任何既有檔案；``--out`` 只准寫「不存在、
  且不在 cache-dir 內」的新檔。
* **不新增契約**：本腳本的 CONFIRMED / SUSPECTED / INSUFFICIENT_EVIDENCE 三級分類只是腳本
  內部的報告用列舉，**不是**正式資料 Schema、健康狀態契約或監控 Sheet 欄位。
* **缺資料不補 0、不當正常**：NaN 保持缺失；讀不到的東西一律標「證據不足」。
* **未發現不等於正常**：報告每一份都會明寫這句。
* **不判成因**：只描述「檔案裡有什麼」「與參考不同在哪」，不判誰對、不判為什麼。

用法
====
    python scripts/check_cache_quality.py [--cache-dir data_cache] [--reference PATH]
        [--out PATH] [--format json|md] [--as-of ISO] [--no-git] [--git-ref REF]
        [--gap-factor N]

輸出為決定性（排序固定、預設不含執行時間；時間只在 ``--as-of`` 注入時出現）。
parquet 讀取器可注入（``main(argv, reader=...)``／``run_checks(..., reader=...)``），預設用
``pandas.read_parquet``（需 pyarrow；缺 pyarrow 時各檔回報「證據不足」，不會崩潰）。
"""
from __future__ import annotations

import argparse
import ast
import base64
import datetime as dt
import hashlib
import io
import json
import math
import os
import statistics
import subprocess
import sys
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

# ════════════════════════════════════════════════════════════════
# 常數（優先 ast 讀自 scripts/update_macro_history.py，不 import 它 —— 它會 import requests）
# ════════════════════════════════════════════════════════════════
_SCRIPTS_DIR = Path(__file__).resolve().parent
_UPDATE_SCRIPT = _SCRIPTS_DIR / "update_macro_history.py"

# 最小複本：僅在 ast 讀取失敗時使用；tests/test_check_cache_quality.py 守住與原檔一致。
_FALLBACK_DATASETS: tuple = ("fred_indicators", "vix_history", "spx_history", "twii_history")
_FALLBACK_FRED_IDS: tuple = (
    "DGS10", "DGS2", "DGS3MO", "BAMLH0A0HYM2", "M2SL", "WALCL",
    "CPIAUCSL", "UNRATE", "DTWEXBGS", "PPIACO", "PCOPPUSDM",
)

FRED_DATASET = "fred_indicators"
INDEX_DATASETS = ("spx_history", "vix_history", "twii_history")
INDEX_COLUMNS = ("date", "close")
FRED_COLUMNS = ("date", "series_id", "value")
METADATA_FILENAME = "metadata.json"

# 快取為單精度（研究文件 §3.3 相等判準：差距 0.006 以內）。
REFERENCE_TOLERANCE = 0.006

# dataset → (市場代碼, 參考檔中的 Yahoo 符號)
REFERENCE_SYMBOL = {"spx_history": "^GSPC", "vix_history": "^VIX", "twii_history": "^TWII"}

# 各市場「當日常規盤」時段（當地時間，含端點）。假設見 docs：不含半日市、不含國定假日判斷。
MARKET_SESSIONS: dict[str, tuple[str, dt.time, dt.time]] = {
    "spx_history": ("America/New_York", dt.time(9, 30), dt.time(16, 0)),
    "vix_history": ("America/Chicago", dt.time(8, 30), dt.time(15, 15)),
    "twii_history": ("Asia/Taipei", dt.time(9, 0), dt.time(13, 30)),
}

# 三級分類（腳本內部列舉，非正式契約）＋ NO_FINDING。
CONFIRMED = "CONFIRMED"
SUSPECTED = "SUSPECTED"
INSUFFICIENT = "INSUFFICIENT_EVIDENCE"
NO_FINDING = "NO_FINDING"
LEVEL_ORDER = (CONFIRMED, SUSPECTED, INSUFFICIENT, NO_FINDING)
LEVEL_LABEL_ZH = {
    CONFIRMED: "已證實異常",
    SUSPECTED: "疑似異常",
    INSUFFICIENT: "證據不足",
    NO_FINDING: "未發現（不等於正常）",
}

DISCLAIMER = (
    "本報告是 A1 離線唯讀檢查輸出，不是正式資料契約、健康狀態或監控資料。",
    "未發現不等於正常：本腳本只檢查下列有限項目，沒被檢查到的東西沒有任何結論。",
    "只描述檔案內容與「與參考不同」，不判成因、不判誰對；不核准 Eligibility、日期規則或 FX Gate"
    "（FX_OBS_DATE_RULE_VERIFIED 維持 False）。",
    "SUSPECTED 為啟發式；CONFIRMED 指可由檔案本身或參考檔機械重現的事實，不代表成因已查明。",
)

ParquetBytesReader = Callable[[bytes], pd.DataFrame]


def load_declared_constants(script_path: Path = _UPDATE_SCRIPT) -> tuple[tuple, tuple, str]:
    """以 ast 讀 ``update_macro_history.py`` 的 ``DATASETS`` 與 ``FRED_SERIES_IDS``。

    回傳 ``(datasets, fred_ids, source)``；source 為 ``"ast"`` 或 ``"fallback_copy"``。
    任何失敗（檔案不在、語法錯、型別不符）都退回最小複本，不崩潰。
    """
    wanted = {"DATASETS": None, "FRED_SERIES_IDS": None}
    try:
        tree = ast.parse(script_path.read_text(encoding="utf-8"))
        for node in tree.body:
            target = None
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
            elif isinstance(node, ast.AnnAssign):
                target = node.target
            if isinstance(target, ast.Name) and target.id in wanted and node.value is not None:
                wanted[target.id] = tuple(ast.literal_eval(node.value))
        if all(isinstance(v, tuple) and v and all(isinstance(x, str) for x in v)
               for v in wanted.values()):
            return wanted["DATASETS"], wanted["FRED_SERIES_IDS"], "ast"
    except Exception:  # noqa: BLE001 — 讀不到就用複本，來源欄位會如實標示
        pass
    return _FALLBACK_DATASETS, _FALLBACK_FRED_IDS, "fallback_copy"


# ════════════════════════════════════════════════════════════════
# 報告資料結構
# ════════════════════════════════════════════════════════════════
@dataclass
class Finding:
    """一筆發現。``level`` 為本腳本內部列舉，不是正式契約。"""

    level: str
    dataset: str
    check: str
    summary: str
    series: Optional[str] = None
    detail: Any = None

    def sort_key(self) -> tuple:
        return (LEVEL_ORDER.index(self.level), self.dataset, self.series or "", self.check, self.summary)

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "level_zh": LEVEL_LABEL_ZH[self.level],
            "dataset": self.dataset,
            "series": self.series,
            "check": self.check,
            "summary": self.summary,
            "detail": self.detail,
        }


@dataclass
class GitHistory:
    """某個快取檔在 git 歷史中的「每個日期首次出現的提交」。"""

    status: str  # "ok" | "unavailable"
    reason: str = ""
    first_seen: dict = field(default_factory=dict)  # date -> (sha, epoch_utc_seconds)
    shallow_shas: frozenset = frozenset()
    commit_count: int = 0
    unreadable_commits: int = 0


@dataclass
class ReferenceData:
    """從探測 ``report.json`` 解出的參考序列（只讀；不重新抓取）。"""

    status: str  # "ok" | "unavailable"
    reason: str = ""
    info: dict = field(default_factory=dict)
    # symbol -> {"closes": {date: float}, "ambiguous": set(date), "problem": str|None}
    series: dict = field(default_factory=dict)


# ════════════════════════════════════════════════════════════════
# 小工具
# ════════════════════════════════════════════════════════════════
def default_reader(data: bytes) -> pd.DataFrame:
    """預設 parquet 讀取器（需 pyarrow/fastparquet；缺則丟 ImportError，由呼叫端轉為證據不足）。"""
    return pd.read_parquet(io.BytesIO(data))


def _first_line(exc: BaseException) -> str:
    msg = str(exc).strip().splitlines()
    return f"{type(exc).__name__}: {msg[0] if msg else ''}".strip()


def _iso(d: Any) -> str:
    if isinstance(d, pd.Timestamp):
        return d.date().isoformat()
    if isinstance(d, (dt.date, dt.datetime)):
        return (d.date() if isinstance(d, dt.datetime) else d).isoformat()
    return str(d)


def _num(x: Any) -> Optional[float]:
    """float → 6 位小數；NaN/None 保持 None（絕不轉 0）。"""
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return round(f, 6) if math.isfinite(f) else None


def _to_timestamps(series: pd.Series) -> pd.Series:
    """轉成 Timestamp（無法解析者為 NaT；不補值）。"""
    return pd.to_datetime(series, errors="coerce")


def load_frame(path: Path, reader: ParquetBytesReader) -> tuple[Optional[pd.DataFrame], str]:
    """讀一個 parquet；回 ``(df, "")`` 或 ``(None, 原因)``。"""
    if not path.exists():
        return None, "檔案不存在"
    try:
        data = path.read_bytes()
    except OSError as exc:
        return None, f"讀檔失敗 {_first_line(exc)}"
    try:
        df = reader(data)
    except Exception as exc:  # noqa: BLE001 — 讀取器失敗一律降級為證據不足
        return None, f"parquet 讀取失敗 {_first_line(exc)}"
    if not isinstance(df, pd.DataFrame):
        return None, "讀取器未回傳 DataFrame"
    return df, ""


def load_metadata(cache_dir: Path) -> tuple[dict, str]:
    """回 ``(datasets 區塊, 原因)``；失敗時區塊為空 dict 並附原因。"""
    path = cache_dir / METADATA_FILENAME
    if not path.exists():
        return {}, "metadata.json 不存在"
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {}, f"metadata.json 無法解析 {_first_line(exc)}"
    ds = obj.get("datasets") if isinstance(obj, dict) else None
    if not isinstance(ds, dict):
        return {}, "metadata.json 缺 datasets 區塊"
    return ds, ""


# ════════════════════════════════════════════════════════════════
# git 歷史（唯讀；僅本機 git，禁網路）
# ════════════════════════════════════════════════════════════════
GIT_ALLOWED_SUBCOMMANDS = frozenset({"rev-parse", "log", "show"})


def validate_git_ref(ref: str) -> Optional[str]:
    """使用者提供的 ref 的字串層檢查；回錯誤訊息或 None。

    拒絕空字串、以 ``-`` 開頭（會被 git 當成選項，例如 ``--output=<路徑>``）、含空白或控制字元者。
    """
    if not isinstance(ref, str) or not ref:
        return "git ref 不可為空"
    if ref.startswith("-"):
        return f"拒絕 git ref：不得以 '-' 開頭（{ref!r}）"
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in ref):
        return f"拒絕 git ref：不得含空白或控制字元（{ref!r}）"
    return None


def _git_env() -> dict:
    """唯讀、不連網的 git 環境：不延遲抓取、不提示輸入、不繼承會觸發網路的 helper／設定。"""
    env = dict(os.environ)
    env.update({
        "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "true", "SSH_ASKPASS": "true",
        "GIT_ALLOW_PROTOCOL": "none", "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
    })
    return env


def _git(args: list[str], cwd: Path, git_exe: str) -> subprocess.CompletedProcess:
    """唯一的 git 呼叫點：子命令白名單（rev-parse／log／show）＋ ``--no-optional-locks``。"""
    if not args or args[0] not in GIT_ALLOWED_SUBCOMMANDS:
        raise ValueError(f"不允許的 git 子命令：{args[:1]}")
    return subprocess.run(  # noqa: S603 — 固定 argv，無 shell
        [git_exe, "--no-optional-locks", *args], cwd=str(cwd), capture_output=True, timeout=120, check=False,
        env=_git_env(),
    )


def load_git_history(
    cache_dir: Path,
    filename: str,
    reader: ParquetBytesReader,
    *,
    ref: str = "HEAD",
    all_refs: bool = False,
    git_exe: str = "git",
) -> GitHistory:
    """對 ``cache_dir/filename`` 求「每個日期首次出現的提交」。

    只用 ``git rev-parse`` / ``git log`` / ``git show``。git 不可用、不在工作樹、無歷史、
    全部歷史版本讀不出來時回 ``status="unavailable"``（呼叫端標證據不足）。
    ``ref`` 先經 :func:`validate_git_ref`（不合法丟 ``ValueError``，不呼叫任何 git），再以
    ``git rev-parse --verify --end-of-options <ref>^{commit}`` 解析成 commit sha 才使用；
    ``all_refs=True`` 為獨立旗標（``git log --all``），不經 ref 字串。
    """
    if not all_refs:
        err = validate_git_ref(ref)
        if err:
            raise ValueError(err)
    try:
        top = _git(["rev-parse", "--show-toplevel"], cache_dir, git_exe)
    except (OSError, subprocess.SubprocessError) as exc:
        return GitHistory("unavailable", f"git 不可用 {_first_line(exc)}")
    if top.returncode != 0:
        return GitHistory("unavailable", "cache-dir 不在 git 工作樹內")
    toplevel = Path(top.stdout.decode().strip()).resolve()
    try:
        rel = (cache_dir.resolve() / filename).relative_to(toplevel).as_posix()
    except ValueError:
        return GitHistory("unavailable", "無法求得檔案相對於 git 根目錄的路徑")

    shallow_shas: set[str] = set()
    common = _git(["rev-parse", "--git-common-dir"], toplevel, git_exe)
    if common.returncode == 0:
        shallow_file = (toplevel / common.stdout.decode().strip() / "shallow").resolve()
        if shallow_file.exists():
            shallow_shas = {ln.strip() for ln in shallow_file.read_text().splitlines() if ln.strip()}

    if all_refs:
        start = ["--all", "--"]  # --all 是選項，須在 --end-of-options 之前；其後無使用者輸入
    else:
        ver = _git(["rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"], toplevel, git_exe)
        if ver.returncode != 0:
            return GitHistory("unavailable", f"ref 無法解析為 commit（ref={ref}）", shallow_shas=frozenset(shallow_shas))
        start = ["--end-of-options", ver.stdout.decode().strip(), "--"]
    log = _git(["log", "--format=%H%x09%ct", *start, rel], toplevel, git_exe)
    if log.returncode != 0:
        return GitHistory("unavailable", f"git log 失敗（ref={'--all' if all_refs else ref}）", shallow_shas=frozenset(shallow_shas))
    commits: list[tuple[str, int]] = []
    for line in log.stdout.decode().splitlines():
        parts = line.split("\t")
        if len(parts) == 2 and parts[1].isdigit():
            commits.append((parts[0], int(parts[1])))
    if not commits:
        return GitHistory("unavailable", "git 歷史中沒有任何提交觸及此檔", shallow_shas=frozenset(shallow_shas))
    # 由舊到新；同秒者保持 git 回傳的相對順序（穩定排序）。
    commits = sorted(reversed(commits), key=lambda c: c[1])

    first_seen: dict = {}
    unreadable = 0
    readable = 0
    for sha, epoch in commits:
        blob = _git(["show", "--end-of-options", f"{sha}:{rel}"], toplevel, git_exe)
        if blob.returncode != 0:
            unreadable += 1
            continue
        try:
            df = reader(blob.stdout)
            if "date" not in df.columns:
                raise ValueError("缺 date 欄")
            dates = _to_timestamps(df["date"]).dropna().dt.date
        except Exception:  # noqa: BLE001
            unreadable += 1
            continue
        readable += 1
        for d in dates.unique():
            first_seen.setdefault(d, (sha, epoch))
    if readable == 0:
        return GitHistory("unavailable", "所有歷史版本皆無法讀取", unreadable_commits=unreadable,
                          commit_count=len(commits), shallow_shas=frozenset(shallow_shas))
    return GitHistory("ok", "", first_seen, frozenset(shallow_shas), len(commits), unreadable)


def in_regular_session(dataset: str, epoch_utc: int) -> tuple[bool, dt.date]:
    """該 UTC 時間點在該市場當地是否落在週一至週五的常規盤內；同時回當地日期。"""
    tz_name, start, end = MARKET_SESSIONS[dataset]
    local = dt.datetime.fromtimestamp(epoch_utc, tz=dt.timezone.utc).astimezone(ZoneInfo(tz_name))
    inside = local.weekday() < 5 and start <= local.time() <= end
    return inside, local.date()


def check_intraday_freeze(dataset: str, dates: Iterable[dt.date], history: Optional[GitHistory]) -> list[Finding]:
    """「可能凍結盤中值」的歷史證據（啟發式 → SUSPECTED）。

    判準：該列首次出現的提交時間，落在該市場「當日」常規盤內，且列日期＝提交當地日期
    （進行中的根只可能是當日那一根）。非當日列即使與盤中提交同批出現，也不標記。
    """
    if history is None:
        return [Finding(INSUFFICIENT, dataset, "intraday_freeze", "未啟用 git 歷史檢查（--no-git），無法判定盤中凍結證據")]
    if history.status != "ok":
        return [Finding(INSUFFICIENT, dataset, "intraday_freeze", f"git 歷史不可用，無法判定盤中凍結證據：{history.reason}")]
    flagged, boundary, unknown = [], 0, 0
    for d in sorted(set(dates)):
        seen = history.first_seen.get(d)
        if seen is None:
            unknown += 1
            continue
        sha, epoch = seen
        if sha in history.shallow_shas:
            boundary += 1
            continue
        inside, local_date = in_regular_session(dataset, epoch)
        if inside and local_date == d:
            tz_name = MARKET_SESSIONS[dataset][0]
            local = dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc).astimezone(ZoneInfo(tz_name))
            flagged.append({
                "date": d.isoformat(), "first_seen_commit": sha[:8],
                "commit_utc": dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "commit_local": local.strftime("%Y-%m-%d %H:%M:%S %Z"), "market_tz": tz_name,
            })
    out: list[Finding] = []
    if flagged:
        out.append(Finding(
            SUSPECTED, dataset, "intraday_freeze",
            f"{len(flagged)} 列的首次出現提交落在該市場當日常規盤內（疑似凍結盤中值；啟發式，非證實）",
            detail=flagged))
    if boundary:
        out.append(Finding(
            INSUFFICIENT, dataset, "intraday_freeze_shallow",
            f"git 為淺層：{boundary} 列的首見提交是淺層邊界提交，真實首見時間未知，未判定"))
    if unknown:
        out.append(Finding(
            INSUFFICIENT, dataset, "intraday_freeze_untracked",
            f"{unknown} 列在 git 歷史中找不到首見提交（可能尚未提交），未判定"))
    return out


# ════════════════════════════════════════════════════════════════
# 參考檔（探測 report.json）
# ════════════════════════════════════════════════════════════════
# 參考檔解壓後大小上限（專案 AI 建議值，非客戶裁示；防壓縮炸彈）。
MAX_REFERENCE_BYTES = 50 * 1024 * 1024


def _bounded_gunzip(data: bytes, limit: int) -> bytes:
    """gzip 解壓並限制輸出大小；超限丟 ValueError（不先全部展開）。"""
    d = zlib.decompressobj(wbits=31)
    out = d.decompress(data, limit + 1)
    if len(out) > limit or d.unconsumed_tail:
        raise ValueError(f"解壓後超過上限 {limit} bytes")
    return out


def load_reference(path: Path) -> ReferenceData:
    """讀入已入庫的探測 ``report.json``，解開 ``raw_gzip_b64`` 得各指數的日期→close。

    損毀、欄位缺、sha256 與檔內記載不符時回 ``unavailable`` 或該符號 ``problem``（證據不足），
    不崩潰。日期採「交易所當地日期」（meta.exchangeTimezoneName），與研究文件 §3.3 一致。
    """
    try:
        if Path(path).stat().st_size > MAX_REFERENCE_BYTES:
            return ReferenceData("unavailable", f"參考檔大小超過上限 {MAX_REFERENCE_BYTES} bytes")
        raw_bytes = Path(path).read_bytes()
        obj = json.loads(raw_bytes.decode("utf-8"))
    except (OSError, ValueError, RecursionError, MemoryError) as exc:
        return ReferenceData("unavailable", f"參考檔無法讀取或解析 {_first_line(exc)}")
    if not isinstance(obj, dict) or not isinstance(obj.get("requests"), list):
        return ReferenceData("unavailable", "參考檔缺 requests 清單（非預期的探測 report.json 格式）")
    info = {
        "file": Path(path).name,
        "file_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "probe": obj.get("probe"),
        "run_id": obj.get("run_id"),
        "started_at_utc": obj.get("started_at_utc"),
        "executed_sha": obj.get("executed_sha"),
    }
    series: dict = {}
    for req in obj["requests"]:
        if not isinstance(req, dict):
            continue
        sym = req.get("requested_index")
        entry = series.setdefault(sym, {"closes": {}, "ambiguous": set(), "problem": None})
        if not req.get("ok") or not req.get("raw_gzip_b64"):
            entry["problem"] = entry["problem"] or "該請求未成功或缺 raw_gzip_b64"
            continue
        try:
            raw = _bounded_gunzip(base64.b64decode(req["raw_gzip_b64"]), MAX_REFERENCE_BYTES)
            if req.get("raw_sha256") and hashlib.sha256(raw).hexdigest() != req["raw_sha256"]:
                entry["problem"] = "解開後 sha256 與參考檔記載不符"
                continue
            chart = json.loads(raw.decode("utf-8"))["chart"]["result"][0]
            stamps = chart["timestamp"]
            closes = chart["indicators"]["quote"][0]["close"]
            tz_name = chart.get("meta", {}).get("exchangeTimezoneName")
            tz = ZoneInfo(tz_name) if tz_name else dt.timezone.utc
            if len(stamps) != len(closes):
                raise ValueError("timestamp 與 close 長度不一致")
        except (Exception, RecursionError, MemoryError) as exc:  # noqa: BLE001
            entry["problem"] = f"raw_gzip_b64 無法解開 {_first_line(exc)}"
            continue
        for ts, c in zip(stamps, closes):
            if c is None:
                continue  # 缺值保持缺失，不補 0
            d = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).astimezone(tz).date()
            if d in entry["closes"] and abs(entry["closes"][d] - float(c)) > REFERENCE_TOLERANCE:
                entry["ambiguous"].add(d)  # 同符號多個請求對同日給不同值：不拿來比
            entry["closes"].setdefault(d, float(c))
    return ReferenceData("ok", "", info, series)


def compare_with_reference(dataset: str, df: pd.DataFrame, ref: Optional[ReferenceData]) -> tuple[list[Finding], list[dict], dict]:
    """快取與參考檔重疊日逐日比對；回 ``(findings, observations, facts)``。"""
    if ref is None:
        return [Finding(INSUFFICIENT, dataset, "reference_compare", "未提供 --reference，無法做重疊日比對")], [], {}
    if ref.status != "ok":
        return [Finding(INSUFFICIENT, dataset, "reference_compare", f"參考檔不可用：{ref.reason}")], [], {}
    sym = REFERENCE_SYMBOL[dataset]
    entry = ref.series.get(sym)
    if entry is None or not entry["closes"]:
        why = (entry or {}).get("problem") or "參考檔沒有此符號的序列"
        return [Finding(INSUFFICIENT, dataset, "reference_compare", f"參考檔無可用的 {sym} 序列：{why}")], [], {}
    cache = {}
    ts = _to_timestamps(df["date"])
    cl = pd.to_numeric(df["close"], errors="coerce")
    for t, c in zip(ts, cl):
        if pd.notna(t) and math.isfinite(c) and t.date() not in cache:
            cache[t.date()] = float(c)
    refc = entry["closes"]
    if not cache:
        return [Finding(INSUFFICIENT, dataset, "reference_compare", "快取沒有可比對的有效列")], [], {}
    lo, hi = max(min(cache), min(refc)), min(max(cache), max(refc))
    facts = {"symbol": sym, "window": [lo.isoformat(), hi.isoformat()] if lo <= hi else None}
    if lo > hi:
        return [Finding(INSUFFICIENT, dataset, "reference_compare", "快取與參考檔的日期範圍沒有重疊")], [], facts
    both = sorted(d for d in cache if d in refc and lo <= d <= hi and d not in entry["ambiguous"])
    diffs = [
        {"date": d.isoformat(), "cache_close": _num(cache[d]), "reference_close": _num(refc[d]),
         "abs_diff": _num(abs(cache[d] - refc[d]))}
        for d in both if abs(cache[d] - refc[d]) > REFERENCE_TOLERANCE
    ]
    facts.update({"overlap_days": len(both), "equal_days": len(both) - len(diffs),
                  "tolerance": REFERENCE_TOLERANCE})
    findings: list[Finding] = []
    if not both:
        findings.append(Finding(INSUFFICIENT, dataset, "reference_compare", "重疊視窗內沒有同日可比的列"))
    if diffs:
        findings.append(Finding(
            CONFIRMED, dataset, "reference_mismatch",
            f"{len(diffs)} 個重疊日的 close 與參考檔不同（只證實『與此參考不同』，不判誰對、不判成因）",
            detail=diffs))
    obs: list[dict] = []
    cache_only = sorted(d.isoformat() for d in cache if lo <= d <= hi and d not in refc)
    ref_only = sorted(d.isoformat() for d in refc if lo <= d <= hi and d not in cache)
    if cache_only:
        obs.append({"dataset": dataset, "check": "cache_only_in_reference_window",
                    "summary": f"參考視窗內快取有而參考無的日期 {len(cache_only)} 個（觀測，不判定）", "detail": cache_only})
    if ref_only:
        obs.append({"dataset": dataset, "check": "reference_only_in_reference_window",
                    "summary": f"參考視窗內參考有而快取無的日期 {len(ref_only)} 個（觀測，不判定）", "detail": ref_only})
    return findings, obs, facts


# ════════════════════════════════════════════════════════════════
# metadata 一致性
# ════════════════════════════════════════════════════════════════
def check_metadata(dataset: str, rows: int, last_date: Optional[dt.date], entry: Optional[dict], reason: str) -> list[Finding]:
    """metadata 的 row_count / last_updated 與檔案實況是否一致（皆為可機械重現的事實）。"""
    if entry is None:
        why = reason or "metadata.json 沒有此資料集條目"
        return [Finding(INSUFFICIENT, dataset, "metadata_consistency", f"缺 metadata，無法比對 row_count／last_updated：{why}")]
    out: list[Finding] = []
    rc = entry.get("row_count")
    if not isinstance(rc, int) or isinstance(rc, bool):
        out.append(Finding(INSUFFICIENT, dataset, "metadata_row_count", f"metadata.row_count 缺失或型別非整數：{rc!r}"))
    elif rc != rows:
        out.append(Finding(CONFIRMED, dataset, "metadata_row_count",
                           f"metadata.row_count={rc} 與檔案實際列數 {rows} 不符", detail={"metadata": rc, "file": rows}))
    lu = entry.get("last_updated")
    parsed = pd.to_datetime(lu, errors="coerce") if isinstance(lu, str) else pd.NaT
    if pd.isna(parsed):
        out.append(Finding(INSUFFICIENT, dataset, "metadata_last_updated", f"metadata.last_updated 缺失或無法解析：{lu!r}"))
    elif last_date is not None and parsed.date() != last_date:
        out.append(Finding(CONFIRMED, dataset, "metadata_last_updated",
                           f"metadata.last_updated={parsed.date().isoformat()} 與檔案最大日期 {last_date.isoformat()} 不符",
                           detail={"metadata": parsed.date().isoformat(), "file": last_date.isoformat()}))
    return out


# ════════════════════════════════════════════════════════════════
# 指數快取（spx / vix / twii）
# ════════════════════════════════════════════════════════════════
def check_index_dataset(
    dataset: str,
    df: Optional[pd.DataFrame],
    read_reason: str,
    meta_entry: Optional[dict],
    meta_reason: str,
    history: Optional[GitHistory],
    reference: Optional[ReferenceData],
) -> tuple[list[Finding], list[dict], dict, Optional[pd.Series]]:
    """檢查一個指數快取；回 ``(findings, observations, facts, 有效日期集合或 None)``。"""
    if df is None:
        return [Finding(INSUFFICIENT, dataset, "read", f"無法讀取：{read_reason}")], [], {"readable": False}, None
    missing = [c for c in INDEX_COLUMNS if c not in df.columns]
    if missing:
        return ([Finding(INSUFFICIENT, dataset, "columns", f"缺欄：{missing}（現有欄位 {sorted(map(str, df.columns))}）")],
                [], {"readable": True, "rows": len(df)}, None)
    if df.empty:
        return [Finding(INSUFFICIENT, dataset, "empty", "空表（0 列）")], [], {"readable": True, "rows": 0}, None

    findings: list[Finding] = []
    obs: list[dict] = []
    ts = _to_timestamps(df["date"])
    close = pd.to_numeric(df["close"], errors="coerce")
    valid_ts = ts.notna()
    n_bad_date = int((~valid_ts).sum())
    if n_bad_date:
        findings.append(Finding(CONFIRMED, dataset, "bad_date", f"{n_bad_date} 列 date 無法解析為日期",
                                detail={"row_positions": [int(i) for i in np.flatnonzero(~valid_ts.to_numpy())][:50]}))
    dates = ts[valid_ts]
    uniq_dates = sorted(set(dates.dt.date))
    dup = dates[dates.duplicated(keep=False)]
    if len(dup):
        dd = sorted(set(dup.dt.date))
        findings.append(Finding(CONFIRMED, dataset, "duplicate_dates", f"{len(dd)} 個日期有重複列",
                                detail=[d.isoformat() for d in dd]))
    if not dates.is_monotonic_increasing:
        findings.append(Finding(CONFIRMED, dataset, "not_sorted", "date 欄未依遞增排序"))

    nan_mask = close.isna()
    nonfinite_mask = ~np.isfinite(close.to_numpy(dtype=float)) & ~nan_mask.to_numpy()
    if nan_mask.any() or nonfinite_mask.any():
        bad = df.index[nan_mask.to_numpy() | nonfinite_mask]
        findings.append(Finding(
            CONFIRMED, dataset, "bad_close",
            f"{len(bad)} 列 close 缺值或非有限值（保持缺失，未補 0、未視為正常）",
            detail=[_iso(ts[i]) if pd.notna(ts[i]) else f"row{i}" for i in bad][:100]))
    nonpos = close.notna() & (close <= 0)
    if nonpos.any():
        findings.append(Finding(CONFIRMED, dataset, "nonpositive_close", f"{int(nonpos.sum())} 列 close <= 0",
                                detail=[{"date": _iso(ts[i]) if pd.notna(ts[i]) else f"row{i}", "close": _num(close[i])}
                                        for i in df.index[nonpos]][:100]))

    wk = dates[dates.dt.dayofweek >= 5]
    if len(wk):
        findings.append(Finding(
            SUSPECTED, dataset, "weekend_rows",
            f"{len(wk)} 列日期為週六或週日（日頻指數通常無週末根；啟發式，不判成因）",
            detail=sorted(d.isoformat() for d in set(wk.dt.date))))
    order = np.argsort(ts.to_numpy(dtype="datetime64[ns]"), kind="stable")
    sd = ts.iloc[order][valid_ts.iloc[order]]
    sc = close.iloc[order][valid_ts.iloc[order]]
    prev = sc.shift(1)
    flat = sd[(sc == prev) & sc.notna() & prev.notna()]
    if len(flat):
        findings.append(Finding(
            SUSPECTED, dataset, "flat_rows",
            f"{len(flat)} 列 close 等於前一列（相同值連續出現不必然是錯誤，單獨不足以判異常）",
            detail=[d.date().isoformat() for d in flat]))

    last_date = max(uniq_dates) if uniq_dates else None
    findings += check_metadata(dataset, len(df), last_date, meta_entry, meta_reason)
    findings += check_intraday_freeze(dataset, uniq_dates, history)
    rf, ro, rfacts = compare_with_reference(dataset, df, reference)
    findings += rf
    obs += ro

    facts = {"readable": True, "rows": len(df), "unique_dates": len(uniq_dates),
             "first_date": uniq_dates[0].isoformat() if uniq_dates else None,
             "last_date": last_date.isoformat() if last_date else None,
             "date_dtype": str(df["date"].dtype), "close_dtype": str(df["close"].dtype)}
    facts.update({f"reference_{k}": v for k, v in rfacts.items()})
    if meta_entry and meta_entry.get("last_error"):
        obs.append({"dataset": dataset, "check": "metadata_last_error",
                    "summary": "metadata.last_error 非空（觀測）", "detail": str(meta_entry.get("last_error"))})
    return findings, obs, facts, pd.Series(uniq_dates, dtype=object)


# ════════════════════════════════════════════════════════════════
# FRED 長格式快取
# ════════════════════════════════════════════════════════════════
def _freq_label(median_gap: Optional[float]) -> str:
    if median_gap is None:
        return "不足以推定"
    if median_gap <= 3:
        return "日頻"
    if median_gap <= 10:
        return "週頻"
    if 20 <= median_gap <= 40:
        return "月頻"
    if 80 <= median_gap <= 100:
        return "季頻"
    return "其他"


def check_fred_dataset(
    df: Optional[pd.DataFrame],
    read_reason: str,
    meta_entry: Optional[dict],
    meta_reason: str,
    declared_ids: Iterable[str],
    *,
    gap_factor: float = 1.5,
    min_rows: int = 50,
    late_start_days: int = 365,
) -> tuple[list[Finding], list[dict], dict]:
    """FRED 長格式（date, series_id, value）逐 series 普查；不改變任何 series 值。"""
    ds = FRED_DATASET
    if df is None:
        return [Finding(INSUFFICIENT, ds, "read", f"無法讀取：{read_reason}")], [], {"readable": False}
    missing = [c for c in FRED_COLUMNS if c not in df.columns]
    if missing:
        return ([Finding(INSUFFICIENT, ds, "columns", f"缺欄：{missing}（現有欄位 {sorted(map(str, df.columns))}）")],
                [], {"readable": True, "rows": len(df)})
    if df.empty:
        return [Finding(INSUFFICIENT, ds, "empty", "空表（0 列）")], [], {"readable": True, "rows": 0}

    findings: list[Finding] = []
    obs: list[dict] = []
    ts = _to_timestamps(df["date"])
    val = pd.to_numeric(df["value"], errors="coerce")
    sid = df["series_id"].astype(str)
    n_bad_date = int(ts.isna().sum())
    if n_bad_date:
        findings.append(Finding(CONFIRMED, ds, "bad_date", f"{n_bad_date} 列 date 無法解析為日期"))
    dup = df.assign(_t=ts, _s=sid)[ts.notna()].duplicated(subset=["_t", "_s"], keep=False)
    if dup.any():
        dd = df.assign(_t=ts, _s=sid)[ts.notna()][dup]
        findings.append(Finding(
            CONFIRMED, ds, "duplicate_keys", f"{int(dd.drop_duplicates(['_t', '_s']).shape[0])} 組 (date, series_id) 重複",
            detail=sorted({f"{s}@{t.date().isoformat()}" for s, t in zip(dd["_s"], dd["_t"])})[:100]))
    nan_by_series = sid[val.isna()].value_counts().to_dict()
    if nan_by_series:
        findings.append(Finding(CONFIRMED, ds, "nan_values",
                                f"{int(val.isna().sum())} 列 value 缺值或非數值（保持缺失，未補 0）",
                                detail={k: int(v) for k, v in sorted(nan_by_series.items())}))

    ok = ts.notna() & val.notna()
    per_series: dict[str, list[pd.Timestamp]] = {}
    for s, t in zip(sid[ok], ts[ok]):
        per_series.setdefault(s, []).append(t)
    stats: dict[str, dict] = {}
    for s, lst in per_series.items():
        u = sorted(set(lst))
        gaps = [(b - a).days for a, b in zip(u, u[1:])]
        med = float(statistics.median(gaps)) if gaps else None
        stats[s] = {"rows": len(lst), "start": u[0], "end": u[-1], "unique": u, "gaps": gaps, "median": med}

    declared = list(declared_ids)
    present = set(sid)
    zero = sorted(s for s in declared if s not in present)
    all_missing = sorted(s for s in declared if s in present and s not in stats)
    if all_missing:
        findings.append(Finding(CONFIRMED, ds, "declared_series_all_missing",
                                f"宣告於 FRED_SERIES_IDS 且快取有列，但全部列的日期或 value 缺失／無法解析的 series：{len(all_missing)} 項"
                                "（與零列不同；保持缺失，未補 0）", detail=all_missing))
    if zero:
        findings.append(Finding(CONFIRMED, ds, "declared_series_zero_rows",
                                f"宣告於 FRED_SERIES_IDS（{len(declared)} 項）但快取零列的 series：{len(zero)} 項",
                                detail=zero))
    extra = sorted(s for s in stats if s not in declared)
    if extra:
        obs.append({"dataset": ds, "check": "undeclared_series", "summary": f"快取有而未宣告的 series：{extra}（觀測）",
                    "detail": extra})
    obs.append({"dataset": ds, "check": "declared_vs_parquet_series_count",
                "summary": f"FRED_SERIES_IDS 宣告 {len(declared)} 項；快取內有資料的 series {len(stats)} 項",
                "detail": {"declared": len(declared), "in_parquet": len(stats)}})

    common_max = max(v["end"] for v in stats.values()) if stats else None
    min_start = min(v["start"] for v in stats.values()) if stats else None
    series_table = []
    for s in sorted(stats):
        v = stats[s]
        label = _freq_label(v["median"])
        threshold = max(gap_factor * (v["median"] if v["median"] is not None else 1.0), 7.0)
        big = [{"from": a.date().isoformat(), "to": b.date().isoformat(), "days": (b - a).days}
               for a, b in zip(v["unique"], v["unique"][1:]) if (b - a).days > threshold]
        if big:
            findings.append(Finding(
                SUSPECTED, ds, "gaps", f"間距超過 max({gap_factor}×中位數, 7) = {threshold:g} 天的缺漏區間 {len(big)} 個（頻率為推定）",
                series=s, detail=big))
        lag = (common_max - v["end"]).days if common_max is not None else None
        if lag is not None and lag > threshold:
            findings.append(Finding(
                SUSPECTED, ds, "lag_behind_common_max",
                f"最新日期 {v['end'].date().isoformat()} 落後共同最大日期 {common_max.date().isoformat()} 達 {lag} 天（> {threshold:g}）；"
                "候選：『全表最大日期＋1』增量起點盲點（成因不判）",
                series=s, detail={"lag_days": lag, "threshold_days": threshold}))
        if min_start is not None and (v["start"] - min_start).days > late_start_days:
            findings.append(Finding(
                SUSPECTED, ds, "late_start",
                f"起點 {v['start'].date().isoformat()} 晚於同批最早起點 {min_start.date().isoformat()} 達 {(v['start'] - min_start).days} 天",
                series=s, detail={"start": v["start"].date().isoformat(), "dataset_min_start": min_start.date().isoformat()}))
        if v["rows"] < min_rows:
            findings.append(Finding(SUSPECTED, ds, "few_rows", f"僅 {v['rows']} 列（< {min_rows}）", series=s,
                                    detail={"rows": v["rows"], "min_rows": min_rows}))
        weekend = [t for t in v["unique"] if t.dayofweek >= 5]
        if label == "日頻" and weekend:
            month_end = [t for t in weekend if (t + pd.Timedelta(days=1)).day == 1]
            obs.append({"dataset": ds, "series": s, "check": "weekend_observations",
                        "summary": f"日頻 series 有 {len(weekend)} 個週末日期（其中月底日 {len(month_end)}）；觀測，不判定",
                        "detail": [t.date().isoformat() for t in weekend]})
        series_table.append({
            "series_id": s, "rows": v["rows"], "start": v["start"].date().isoformat(), "end": v["end"].date().isoformat(),
            "median_gap_days": _num(v["median"]), "inferred_frequency": label,
            "lag_vs_common_max_days": lag, "declared": s in declared,
            "weekend_dates": sum(1 for t in v["unique"] if t.dayofweek >= 5),
        })

    last_date = common_max.date() if common_max is not None else None
    findings += check_metadata(ds, len(df), last_date, meta_entry, meta_reason)
    facts = {"readable": True, "rows": len(df), "series_count": len(stats),
             "common_max_date": last_date.isoformat() if last_date else None, "series": series_table}
    return findings, obs, facts


# ════════════════════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════════════════════
def run_checks(
    cache_dir: Path,
    *,
    reader: ParquetBytesReader = default_reader,
    reference_path: Optional[Path] = None,
    as_of: Optional[str] = None,
    use_git: bool = True,
    git_ref: str = "HEAD",
    git_all_refs: bool = False,
    git_exe: str = "git",
    gap_factor: float = 1.5,
    min_rows: int = 50,
    late_start_days: int = 365,
) -> dict:
    """對 ``cache_dir`` 跑全部檢查並回傳可 JSON 序列化的報告 dict（決定性）。"""
    cache_dir = Path(cache_dir)
    datasets, fred_ids, const_src = load_declared_constants()
    meta_ds, meta_reason = load_metadata(cache_dir)
    reference = load_reference(Path(reference_path)) if reference_path else None

    findings: list[Finding] = []
    observations: list[dict] = []
    facts: dict[str, dict] = {}
    date_sets: dict[str, set] = {}
    evaluated: dict[str, bool] = {}

    for name in sorted(datasets):
        path = cache_dir / f"{name}.parquet"
        df, why = load_frame(path, reader)
        entry = meta_ds.get(name) if isinstance(meta_ds.get(name), dict) else None
        if name == FRED_DATASET:
            f, o, fa = check_fred_dataset(df, why, entry, meta_reason, fred_ids, gap_factor=gap_factor,
                                          min_rows=min_rows, late_start_days=late_start_days)
            evaluated[name] = bool(fa.get("rows"))
        elif name in INDEX_DATASETS:
            hist = load_git_history(
                cache_dir, f"{name}.parquet", reader, ref=git_ref, all_refs=git_all_refs, git_exe=git_exe,
            ) if use_git else None
            f, o, fa, dset = check_index_dataset(name, df, why, entry, meta_reason, hist, reference)
            evaluated[name] = dset is not None
            if dset is not None:
                date_sets[name] = set(dset)
        else:
            f, o, fa = [Finding(INSUFFICIENT, name, "unknown_dataset", "update_macro_history.DATASETS 有此名稱但本腳本無對應檢查")], [], {}
            evaluated[name] = False
        findings += f
        observations += o
        facts[name] = fa

    if "vix_history" in date_sets and "spx_history" in date_sets:
        v_only = sorted(d.isoformat() for d in date_sets["vix_history"] - date_sets["spx_history"])
        s_only = sorted(d.isoformat() for d in date_sets["spx_history"] - date_sets["vix_history"])
        observations.append({"dataset": "vix_history", "check": "date_set_vs_spx",
                             "summary": f"VIX 有而 SPX 無的日期 {len(v_only)} 個；SPX 有而 VIX 無的日期 {len(s_only)} 個"
                                        "（各市場假日性質，僅觀測，不判定資料錯誤）",
                             "detail": {"vix_not_in_spx": v_only, "spx_not_in_vix": s_only}})

    for name in sorted(datasets):
        if evaluated.get(name) and not any(
                x.dataset == name and x.level in (CONFIRMED, SUSPECTED) for x in findings):
            n_insuf = sum(1 for x in findings if x.dataset == name and x.level == INSUFFICIENT)
            note = f"另有 {n_insuf} 項證據不足，" if n_insuf else ""
            findings.append(Finding(NO_FINDING, name, "all", f"本腳本已執行的檢查項目未發現問題；{note}未發現不等於正常"))

    findings.sort(key=Finding.sort_key)
    observations.sort(key=lambda o: (o["dataset"], str(o.get("series", "")), o["check"]))
    counts: dict[str, dict[str, int]] = {n: {lv: 0 for lv in LEVEL_ORDER} for n in sorted(datasets)}
    for fd in findings:
        counts.setdefault(fd.dataset, {lv: 0 for lv in LEVEL_ORDER})[fd.level] += 1
    totals = {lv: sum(c[lv] for c in counts.values()) for lv in LEVEL_ORDER}

    ref_info: dict = {"provided": False}
    if reference is not None:
        ref_info = {"provided": True, "status": reference.status, "reason": reference.reason, **reference.info}
    return {
        "report_kind": "cache_quality_a1_offline",
        "disclaimer": list(DISCLAIMER),
        "as_of": as_of,
        "cache_dir": str(cache_dir),
        "constants_source": const_src,
        "parameters": {"gap_factor": gap_factor, "min_rows": min_rows, "late_start_days": late_start_days,
                       "reference_tolerance": REFERENCE_TOLERANCE, "git_enabled": use_git, "git_ref": ("--all" if git_all_refs else git_ref) if use_git else None},
        "reference": ref_info,
        "datasets": facts,
        "summary": {"counts_by_dataset": counts, "counts_total": totals},
        "findings": [f.to_dict() for f in findings],
        "observations": observations,
    }


# ════════════════════════════════════════════════════════════════
# 輸出
# ════════════════════════════════════════════════════════════════
def render_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _fmt_detail(detail: Any, limit: int = 12) -> str:
    if detail is None:
        return ""
    if isinstance(detail, list):
        shown = ", ".join(json.dumps(x, ensure_ascii=False, sort_keys=True) if isinstance(x, (dict, list)) else str(x)
                          for x in detail[:limit])
        more = f" …（共 {len(detail)} 筆，完整清單見 --format json）" if len(detail) > limit else ""
        return f"[{shown}]{more}"
    return json.dumps(detail, ensure_ascii=False, sort_keys=True)


def render_markdown(report: dict) -> str:
    """Markdown 報告（決定性；明列聲明與『未發現不等於正常』）。"""
    L: list[str] = ["# 離線唯讀快取品質檢查報告（A1）", ""]
    L += [f"> {line}" for line in report["disclaimer"]]
    L += ["", f"- cache-dir：`{report['cache_dir']}`", f"- as-of：{report['as_of'] or '（未注入）'}",
          f"- 常數來源：{report['constants_source']}（`update_macro_history.py` 的 `DATASETS`／`FRED_SERIES_IDS`）"]
    ref = report["reference"]
    if ref.get("provided"):
        L.append(f"- 參考檔：`{ref.get('file')}`（sha256 `{ref.get('file_sha256')}`；probe {ref.get('probe')}；"
                 f"run_id {ref.get('run_id')}；狀態 {ref.get('status')}{('：' + ref['reason']) if ref.get('reason') else ''}）")
    else:
        L.append("- 參考檔：未提供")
    p = report["parameters"]
    L.append(f"- 參數：gap_factor={p['gap_factor']}、min_rows={p['min_rows']}、late_start_days={p['late_start_days']}、"
             f"tolerance={p['reference_tolerance']}、git={'on ref ' + str(p['git_ref']) if p['git_enabled'] else 'off'}")
    L += ["", "## 摘要", "", "| 資料集 | 已證實異常 | 疑似異常 | 證據不足 | 未發現 |", "|---|---|---|---|---|"]
    for name, c in report["summary"]["counts_by_dataset"].items():
        L.append(f"| {name} | {c[CONFIRMED]} | {c[SUSPECTED]} | {c[INSUFFICIENT]} | {c[NO_FINDING]} |")
    t = report["summary"]["counts_total"]
    L += [f"| **合計** | {t[CONFIRMED]} | {t[SUSPECTED]} | {t[INSUFFICIENT]} | {t[NO_FINDING]} |", ""]
    L += ["## 各資料集事實", ""]
    for name, fa in report["datasets"].items():
        if name == FRED_DATASET and len(fa.get("series", [])) > 0:
            L += [f"### {name}（{fa['rows']} 列、{fa['series_count']} 個 series、共同最大日期 {fa['common_max_date']}）", "",
                  "| series | 列數 | 起 | 迄 | 中位間距(天) | 推定頻率 | 落後共同最大日期(天) | 週末日期數 |", "|---|---|---|---|---|---|---|---|"]
            for r in fa["series"]:
                L.append(f"| {r['series_id']} | {r['rows']} | {r['start']} | {r['end']} | {r['median_gap_days']} | "
                         f"{r['inferred_frequency']} | {r['lag_vs_common_max_days']} | {r['weekend_dates']} |")
            L.append("")
        else:
            L.append(f"- **{name}**：{json.dumps(fa, ensure_ascii=False, sort_keys=True)}")
    L.append("")
    for lv in LEVEL_ORDER:
        items = [f for f in report["findings"] if f["level"] == lv]
        L += [f"## {LEVEL_LABEL_ZH[lv]}（{lv}，{len(items)} 筆）", ""]
        if not items:
            L += ["（無）", ""]
            continue
        for f in items:
            who = f["dataset"] + (f"／{f['series']}" if f["series"] else "")
            L.append(f"- **[{who}] {f['check']}**：{f['summary']}")
            d = _fmt_detail(f["detail"])
            if d:
                L.append(f"  - 明細：{d}")
        L.append("")
    L += ["## 觀測（不分級、不判定資料錯誤）", ""]
    if not report["observations"]:
        L += ["（無）", ""]
    for o in report["observations"]:
        who = o["dataset"] + (f"／{o['series']}" if o.get("series", "") != "" else "")
        L.append(f"- [{who}] {o['check']}：{o['summary']}")
        d = _fmt_detail(o.get("detail"))
        if d:
            L.append(f"  - 明細：{d}")
    L += ["", "---", "未發現不等於正常。本報告不判成因、不核准任何規則。", ""]
    return "\n".join(L)


# ════════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════════
def _validate_out(out: Path, cache_dir: Path) -> Optional[str]:
    """``--out`` 保護：不得位於 cache-dir 內、不得覆寫既有檔、父目錄須存在。"""
    out_r, cache_r = out.resolve(), cache_dir.resolve()
    if out_r == cache_r or cache_r in out_r.parents:
        return f"拒絕寫入：--out 位於 cache-dir（{cache_dir}）內"
    if out.exists() or out.is_symlink():
        return f"拒絕寫入：--out 已存在（{out}）；本腳本不覆寫既有檔"
    if not out_r.parent.is_dir():
        return f"拒絕寫入：--out 的父目錄不存在（{out_r.parent}）"
    return None


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="離線唯讀快取品質檢查（A1）；零網路、零寫入 cache。")
    ap.add_argument("--cache-dir", default="data_cache")
    ap.add_argument("--reference", default=None, help="本機探測 report.json（選用）")
    ap.add_argument("--out", default=None, help="輸出檔（須不存在且不在 cache-dir 內）；省略則只印 stdout")
    ap.add_argument("--format", choices=("json", "md"), default="md")
    ap.add_argument("--as-of", default=None, help="注入報告內的時間字串（預設不含時間，以保決定性）")
    ap.add_argument("--no-git", action="store_true", help="不讀 git 歷史（盤中凍結證據標證據不足）")
    ap.add_argument("--git-ref", default="HEAD", help="git 歷史的起點 ref（預設 HEAD）")
    ap.add_argument("--git-all-refs", action="store_true",
                    help="git 歷史改用 --all（含所有本機分支；淺層 clone 的 HEAD 歷史可能不完整時使用）")
    ap.add_argument("--gap-factor", type=float, default=1.5, help="缺漏區間門檻倍數（預設 1.5×中位數，且至少 7 天）")
    return ap


def main(argv: Optional[list[str]] = None, *, reader: ParquetBytesReader = default_reader) -> int:
    args = build_parser().parse_args(argv)
    cache_dir = Path(args.cache_dir)
    if not cache_dir.is_dir():
        print(f"cache-dir 不存在或不是目錄：{cache_dir}", file=sys.stderr)
        return 2
    if not args.no_git and not args.git_all_refs:
        err = validate_git_ref(args.git_ref)
        if err:
            print(err, file=sys.stderr)
            return 2
    if args.out:
        err = _validate_out(Path(args.out), cache_dir)
        if err:
            print(err, file=sys.stderr)
            return 2
    report = run_checks(cache_dir, reader=reader, reference_path=Path(args.reference) if args.reference else None,
                        as_of=args.as_of, use_git=not args.no_git,
                        git_ref=args.git_ref, git_all_refs=args.git_all_refs, gap_factor=args.gap_factor)
    text = render_json(report) if args.format == "json" else render_markdown(report)
    if args.out:
        with open(args.out, "x", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print(f"已寫入 {args.out}（{len(text)} 字元）", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
