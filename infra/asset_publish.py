"""infra/asset_publish.py — 把檔案發佈到 GitHub 公開分支,取得**永久可讀的圖片網址**。L0 infra。

用途:LINE 圖片訊息**只吃公開 HTTPS 網址**(不能夾 bytes),故月曆 PNG 需先上傳到可公開讀取的
位置。本模組走 **GitHub Contents API**(`PUT /repos/{owner}/{repo}/contents/{path}`)把 bytes
寫進指定分支,回傳 **commit SHA 釘死** 的 raw 網址:

    https://raw.githubusercontent.com/{owner}/{repo}/{sha}/{path}

**為什麼釘 SHA 而非分支名**:`raw.githubusercontent.com/.../{branch}/...` 走 CDN 快取,剛推上去
的新內容可能仍拿到舊圖(PROCESS.md 已記錄此坑)。釘 commit SHA 的網址內容不可變,LINE 抓到的
一定是這次產的圖。

**為什麼用 Contents API 而非 git CLI**:呼叫端(cron script)本身跑在一個 checkout 裡,用 git
切分支/orphan commit 會擾動工作區;Contents API 純 HTTP、不碰本地 git 狀態,也好測(可注入
`_requester`)。⚠️ 與 `export_db.yml` 的 orphan force-push 慣例**刻意不同**:那邊 `fund.db`
是「永遠只留最新一份」的單一產物,force-push 不留歷史剛好;本模組發佈的是**每月一張、且網址會
留在 LINE 對話紀錄裡**的圖 —— 若 force-push 蓋掉舊 commit,上個月訊息裡的圖會變成破圖。故本模組
**累加 commit 不 force-push**(每月一張 ~300KB,一年約 3MB,可忽略)。

§1 Fail-Loud:缺 token/repo、HTTP 非 2xx、回應缺 commit sha → raise `AssetPublishError`,
呼叫端據此退回 Flex/純文字,**絕不回一個猜的網址**(推出去會變成破圖,比不推更糟)。
"""
from __future__ import annotations

import base64 as _b64
import os as _os
import urllib.parse as _up

_API = "https://api.github.com"
_RAW = "https://raw.githubusercontent.com"
_DEFAULT_BRANCH = "push-assets"
_MAX_BYTES = 25 * 1024 * 1024        # Contents API 單檔上限(遠大於月曆 PNG,純防呆)


class AssetPublishError(RuntimeError):
    """發佈到 GitHub 失敗(缺憑證 / HTTP 非 2xx / 回應格式異常)。訊息不含 token。"""


def _resolve(name: str, override: "str | None") -> str:
    """明確參數 > 環境變數 > 空字串(GitHub Actions 會自動注入 GITHUB_TOKEN/GITHUB_REPOSITORY)。"""
    if override:
        return str(override).strip()
    return str(_os.environ.get(name, "")).strip()


def _default_requester():
    import requests

    def _req(method: str, url: str, *, headers=None, json=None, timeout=20.0):
        try:
            return requests.request(method, url, headers=headers, json=json, timeout=timeout)
        except Exception as _e:  # noqa: BLE001 — DNS/連線重置/逾時 → 統一成 AssetPublishError
            # §1:網路層錯誤也必須符合本模組宣告的 Raises 契約(對齊 infra/line_push.py 作法),
            # 否則 `except AssetPublishError` 的呼叫端會被 requests.* 例外打穿。訊息不含 token。
            raise AssetPublishError(f"GitHub API 網路錯誤:{type(_e).__name__}: {_e}") from _e
    return _req


def _json(resp) -> dict:
    try:
        _d = resp.json()
        return _d if isinstance(_d, dict) else {}
    except Exception:  # noqa: BLE001 — 非 JSON 回應 → 當空 dict,由 caller 依狀態碼判斷
        return {}


def _ok(resp) -> bool:
    _s = getattr(resp, "status_code", None)
    return _s is not None and 200 <= int(_s) < 300


def _ensure_branch(req, repo: str, branch: str, headers: dict, timeout: float) -> None:
    """分支不存在 → 從預設分支 HEAD 建立。已存在則不動(§1:建不出來就 raise,不靜默跳過)。"""
    _r = req("GET", f"{_API}/repos/{repo}/git/ref/heads/{_up.quote(branch)}",
             headers=headers, timeout=timeout)
    if _ok(_r):
        return
    if int(getattr(_r, "status_code", 0) or 0) != 404:
        raise AssetPublishError(
            f"查詢分支 {branch} 失敗 HTTP {getattr(_r, 'status_code', None)}:"
            f"{str(getattr(_r, 'text', ''))[:200]}")
    # 取預設分支 HEAD 當新分支起點
    _repo_r = req("GET", f"{_API}/repos/{repo}", headers=headers, timeout=timeout)
    if not _ok(_repo_r):
        raise AssetPublishError(f"讀 repo 資訊失敗 HTTP {getattr(_repo_r, 'status_code', None)}")
    _base = str(_json(_repo_r).get("default_branch") or "main")
    _head_r = req("GET", f"{_API}/repos/{repo}/git/ref/heads/{_up.quote(_base)}",
                  headers=headers, timeout=timeout)
    if not _ok(_head_r):
        raise AssetPublishError(f"讀預設分支 {_base} HEAD 失敗 "
                                f"HTTP {getattr(_head_r, 'status_code', None)}")
    _sha = str((_json(_head_r).get("object") or {}).get("sha") or "")
    if not _sha:
        raise AssetPublishError(f"預設分支 {_base} 回應缺 object.sha")
    _mk = req("POST", f"{_API}/repos/{repo}/git/refs", headers=headers, timeout=timeout,
              json={"ref": f"refs/heads/{branch}", "sha": _sha})
    if _ok(_mk):
        return
    # GET→POST 之間若有人搶先建好(並行 run / 手動跑),GitHub 回 422「Reference already exists」。
    # 那是「分支已存在」= 我們要的結果,不該當失敗把出圖路徑砍掉。
    if int(getattr(_mk, "status_code", 0) or 0) == 422 and \
            "already exists" in str(getattr(_mk, "text", "")).lower():
        return
    raise AssetPublishError(
        f"建立分支 {branch} 失敗 HTTP {getattr(_mk, 'status_code', None)}:"
        f"{str(getattr(_mk, 'text', ''))[:200]}")


def _existing_sha(req, repo: str, path: str, branch: str, headers: dict, timeout: float) -> str:
    """同路徑檔案已存在 → 回其 blob sha(Contents API 覆寫時必填);**確定不存在(404)** → ""。

    §1:**只有 404 才算「檔案不存在」**。403(次級速率限制)/5xx 也回 "" 會讓後續 PUT 少帶 sha,
    GitHub 回 422「sha wasn't supplied」—— log 上看到的是 422,真因(403)卻被吃掉,誤導排查。
    故非 404 一律 raise(與 `_ensure_branch` 同一準則)。
    """
    _r = req("GET", f"{_API}/repos/{repo}/contents/{_up.quote(path)}?ref={_up.quote(branch)}",
             headers=headers, timeout=timeout)
    if _ok(_r):
        return str(_json(_r).get("sha") or "")
    _status = int(getattr(_r, "status_code", 0) or 0)
    if _status == 404:
        return ""                                   # 確定是新檔
    raise AssetPublishError(
        f"查詢既有檔案 {path} 失敗 HTTP {_status}:{str(getattr(_r, 'text', ''))[:200]}")


def publish_asset(data: bytes, dest_path: str, *, branch: str = _DEFAULT_BRANCH,
                  repo: "str | None" = None, token: "str | None" = None,
                  message: "str | None" = None, timeout: float = 20.0,
                  dry_run: bool = False, _requester=None) -> str:
    """把 bytes 發佈到 GitHub 分支,回傳 **commit SHA 釘死的公開 raw 網址**。

    Args:
        data: 檔案內容(如 PNG bytes)。空 → raise(§1 不發空檔)。
        dest_path: repo 內路徑,如 `dividend-calendar/2026-09.png`。
        branch: 發佈分支(預設 `push-assets`);不存在會自動從預設分支建立。
        repo / token: 省略則讀環境變數 `GITHUB_REPOSITORY` / `GITHUB_TOKEN`(Actions 自動注入)。
            workflow 需宣告 `permissions: contents: write`,否則 PUT 會 403。
        dry_run: 只驗參數不打 API,回傳**假的**預覽網址(內含 `DRYRUN`,呼叫端不可拿去推播)。
    Returns:
        `https://raw.githubusercontent.com/{repo}/{sha}/{dest_path}`
    Raises:
        AssetPublishError — 缺憑證 / HTTP 非 2xx / 回應缺 commit sha(§1 絕不回猜的網址)。
    """
    if not data:
        raise AssetPublishError("空內容,拒絕發佈(§1 不推空檔案)")
    if len(data) > _MAX_BYTES:
        raise AssetPublishError(f"檔案過大({len(data)} bytes > {_MAX_BYTES})")
    _path = str(dest_path or "").strip().lstrip("/")
    if not _path:
        raise AssetPublishError("dest_path 不可為空")

    _repo = _resolve("GITHUB_REPOSITORY", repo)
    if dry_run:
        # 刻意回**非 https** scheme:`push_image` 只驗 startswith("https://"),若這裡回一個長得像
        # 真網址的字串,誤用就會推出一張永久破圖。回 dry-run:// 讓誤用在 LINE 端被擋下(結構性
        # 防呆,不只靠 docstring 警語)。
        return f"dry-run://{_repo or 'OWNER/REPO'}/{_path}"
    _token = _resolve("GITHUB_TOKEN", token)
    if not _repo or not _token:
        raise AssetPublishError(
            "缺 GITHUB_REPOSITORY / GITHUB_TOKEN —— 無法發佈圖片(workflow 需 "
            "`permissions: contents: write` 並以 token checkout)")

    _req = _requester or _default_requester()
    _headers = {"Authorization": f"Bearer {_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"}

    _ensure_branch(_req, _repo, branch, _headers, timeout)
    _payload = {
        "message": str(message or f"chore(assets): publish {_path} [skip ci]"),
        "content": _b64.b64encode(data).decode("ascii"),
        "branch": branch,
    }
    _sha = _existing_sha(_req, _repo, _path, branch, _headers, timeout)
    if _sha:                                    # 同路徑已存在 → 覆寫需帶舊 blob sha
        _payload["sha"] = _sha

    _r = _req("PUT", f"{_API}/repos/{_repo}/contents/{_up.quote(_path)}",
              headers=_headers, json=_payload, timeout=timeout)
    if not _ok(_r):
        raise AssetPublishError(
            f"發佈失敗 HTTP {getattr(_r, 'status_code', None)}:"
            f"{str(getattr(_r, 'text', ''))[:300]}")
    _commit_sha = str(((_json(_r).get("commit") or {}).get("sha")) or "")
    if not _commit_sha:
        # §1:沒拿到 SHA 就無法組出不可變網址;退用分支名會踩 CDN 快取拿到舊圖 → 寧可失敗
        raise AssetPublishError("發佈回應缺 commit.sha,無法組出釘死版本的網址")
    return f"{_RAW}/{_repo}/{_commit_sha}/{_up.quote(_path)}"


__all__ = ["publish_asset", "AssetPublishError"]
