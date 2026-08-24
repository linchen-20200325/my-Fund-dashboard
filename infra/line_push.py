"""infra/line_push.py — LINE Messaging API 主動推播(v19.432)。L0 infra(外部 I/O)。

用途:NAS 週 cron 算出換股建議後,推一則 text 到你的 LINE。**LINE Notify 已於 2025/03 停用**,
本模組走 **Messaging API**(`POST /v2/bot/message/push`)。

前置(你在 LINE Developers Console 做一次):
  1. 建一個 **Messaging API** channel → 拿 **Channel access token(long-lived)**
  2. 把該 bot 官方帳號**加為好友**
  3. 拿你自己的 **userId**(webhook 事件 / 「基本資料」頁)
環境變數(或 infra.config secrets):`LINE_CHANNEL_TOKEN`(**別名相容** `LINE_CHANNEL_ACCESS_TOKEN`)、`LINE_USER_ID`。

§1 Fail-Loud:token/user_id 缺 → 不靜默假裝成功,回 sent=False + 明確 reason(cron log 看得到);
HTTP 非 2xx → raise `LinePushError`(帶狀態碼 + LINE 回應),讓 cron 信/log 有線索,下次再試。
dry-run(或缺憑證)→ 只印出**不送**,方便本機/CI 驗流程不觸網。
"""
from __future__ import annotations

_PUSH_URL = "https://api.line.me/v2/bot/message/push"
_LINE_TEXT_MAX = 5000          # LINE text message 硬上限


class LinePushError(Exception):
    """LINE 推播失敗(HTTP 非 2xx / 網路錯誤)。訊息不含 token。"""


def _resolve(name: str, override: "str | None") -> str:
    """憑證解析:明確參數 > infra.config secret > 環境變數 > 空字串。"""
    if override:
        return str(override).strip()
    try:
        from infra.config import get_secret
        _v = get_secret(name)
        if _v:
            return str(_v).strip()
    except Exception:  # noqa: BLE001 — 沒有 infra.config / secret 不存在 → 退環境變數
        pass
    import os
    return str(os.environ.get(name, "")).strip()


def _post_messages(messages: list, *, preview: str, token: "str | None", user_id: "str | None",
                   dry_run: bool, timeout: float, _poster) -> dict:
    """共用:憑證解析 + dry-run/缺憑證 short-circuit + POST + §1 錯誤處理。

    messages:LINE messages 陣列(text / flex / image …皆可,≤5 則)。preview:dry-run/log 純文字預覽。
    """
    # 別名相容:優先 LINE_CHANNEL_TOKEN,退 LINE_CHANNEL_ACCESS_TOKEN(spec / GitHub secret 常用後者)
    _token = _resolve("LINE_CHANNEL_TOKEN", token) or _resolve("LINE_CHANNEL_ACCESS_TOKEN", None)
    _uid = _resolve("LINE_USER_ID", user_id)

    if dry_run or not _token or not _uid:
        _why = ("dry-run" if dry_run else
                "缺 LINE_CHANNEL_TOKEN" if not _token else "缺 LINE_USER_ID")
        print(f"[line_push] {_why} → 不送,訊息預覽:\n{preview}")
        return {"sent": False, "dry_run": bool(dry_run), "status": None, "reason": _why}

    _payload = {"to": _uid, "messages": messages}
    _headers = {"Authorization": f"Bearer {_token}", "Content-Type": "application/json"}

    _post = _poster
    if _post is None:
        import requests
        _post = requests.post
    try:
        _resp = _post(_PUSH_URL, headers=_headers, json=_payload, timeout=timeout)
    except Exception as _e:  # noqa: BLE001 — 網路層錯誤 → 統一成 LinePushError(不洩 token)
        raise LinePushError(f"LINE 推播網路錯誤:{type(_e).__name__}: {_e}") from _e

    _status = getattr(_resp, "status_code", None)
    if _status is None or not (200 <= int(_status) < 300):
        _body = str(getattr(_resp, "text", ""))[:300]
        raise LinePushError(f"LINE 推播失敗 HTTP {_status}:{_body}")
    return {"sent": True, "dry_run": False, "status": int(_status), "reason": "ok"}


def push_text(text: str, *, token: "str | None" = None, user_id: "str | None" = None,
              dry_run: bool = False, timeout: float = 10.0, _poster=None) -> dict:
    """推一則 text 到指定 LINE user。

    Returns:
        {"sent": bool, "dry_run": bool, "status": int|None, "reason": str}
    Raises:
        LinePushError — 憑證齊全且非 dry-run 但 HTTP 非 2xx / 網路錯誤(§1 不靜默)。
    """
    _text = str(text or "").strip()
    if not _text:
        return {"sent": False, "dry_run": bool(dry_run), "status": None,
                "reason": "空訊息,未送"}
    if len(_text) > _LINE_TEXT_MAX:                     # LINE 硬上限 → 截斷帶省略號(不讓 API 4xx)
        _text = _text[:_LINE_TEXT_MAX - 1] + "…"
    return _post_messages([{"type": "text", "text": _text}], preview=_text, token=token,
                          user_id=user_id, dry_run=dry_run, timeout=timeout, _poster=_poster)


def push_flex(contents: dict, alt_text: str, *, token: "str | None" = None,
              user_id: "str | None" = None, dry_run: bool = False, timeout: float = 10.0,
              _poster=None) -> dict:
    """推一則 **Flex Message**(彩色卡片)到指定 LINE user。

    Args:
        contents: Flex container dict(bubble / carousel),由 caller(L2)組好。
        alt_text: 通知列 / 無法渲染 Flex 的裝置退化用純文字(LINE altText 上限 400 字)。
    Returns / Raises 同 push_text。憑證與端點與 text 推播共用,**無需新增 secret**。
    """
    _alt = (str(alt_text or "").strip() or "LINE 通知")[:400]   # 非空 + LINE altText 硬上限 400
    if not isinstance(contents, dict) or not contents:
        return {"sent": False, "dry_run": bool(dry_run), "status": None,
                "reason": "空 Flex 內容,未送"}
    _msg = {"type": "flex", "altText": _alt, "contents": contents}
    return _post_messages([_msg], preview=_alt, token=token, user_id=user_id,
                          dry_run=dry_run, timeout=timeout, _poster=_poster)


__all__ = ["push_text", "push_flex", "LinePushError"]
