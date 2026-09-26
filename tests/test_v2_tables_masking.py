# -*- coding: utf-8 -*-
"""services/v2_tables/masking.py：ACCEPTANCE.md 7.5 的 M1～M10（fast lane）。

M11（畫面與遮蔽後字串逐字相同、註記出現）在 `tests/ui_v2/test_mkt_live_page.py`（需要 streamlit）；
M12（突變：遮蔽函式改成原樣回傳）以突變腳本執行，結果記在回報與 ACCEPTANCE。
假金鑰、假帳密一律現場隨機產生，不寫死、不寫進文件（CLAUDE.md §-2.A 第 8 款）。
M1、M2 只連本機迴路位址。
"""

from __future__ import annotations

import pathlib
import secrets as _rnd
import socket
import string
import threading
import tomllib
from urllib.parse import quote, quote_plus

import pytest

from services.v2_tables import masking
from services.v2_tables.masking import MASK, mask_message, secret_values

_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _fake(n=24, alphabet=string.ascii_letters + string.digits):
    return "".join(_rnd.choice(alphabet) for _ in range(n))


def _unmask(masked: str, value: str) -> str:
    return masked.replace(MASK, value)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ── M1 ──
def test_M1_含金鑰網址的連線失敗例外字串():
    requests = pytest.importorskip("requests")
    key = _fake()
    port = _free_port()  # 綁完就關 → 沒有人在聽
    with pytest.raises(requests.exceptions.ConnectionError) as info:
        requests.get(f"http://127.0.0.1:{port}/fred", params={"api_key": key}, timeout=3,
                     proxies={"http": None, "https": None})
    raw = str(info.value)
    assert key in raw  # 前提：例外字串真的帶金鑰（7.6）
    masked = mask_message(raw, secret_values([{"FRED_API_KEY": key}]))
    assert key not in masked and MASK in masked
    assert _unmask(masked, key) == raw


# ── M2 ──
class _Proxy407(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]

    def run(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                conn.recv(65536)
                conn.sendall(b"HTTP/1.1 407 Proxy Authentication Required\r\n"
                             b"Proxy-Authenticate: Basic realm=\"x\"\r\n"
                             b"Content-Length: 0\r\nConnection: close\r\n\r\n")


def test_M2_407代理驗證失敗():
    requests = pytest.importorskip("requests")
    user, password, key = _fake(10), _fake(), _fake()
    proxy = _Proxy407()
    proxy.start()
    proxy_url = f"http://{user}:{password}@127.0.0.1:{proxy.port}"
    try:
        with pytest.raises(requests.exceptions.RequestException) as info:
            requests.get("https://example.invalid/api", params={"api_key": key}, timeout=5,
                         proxies={"http": proxy_url, "https": proxy_url})
    finally:
        proxy.sock.close()
    raw = str(info.value)
    values = secret_values([{"PROXY_URL": proxy_url, "FRED_API_KEY": key}])
    masked = mask_message(raw, values)
    for secret in (user, password, key):
        assert secret not in masked
    # 其餘字元逐字保留：把出現過的秘密依序換回去，要與原字串相同
    restored = raw
    for secret in sorted(values, key=len, reverse=True):
        restored = restored.replace(secret, MASK)
    assert restored == masked


# ── M3 ──
def test_M3_代理帳密直接出現在訊息裡_主機與埠保留():
    user, password = _fake(8), _fake(16, string.ascii_letters + "+/=")
    url = f"http://{user}:{password}@nas.example.test:3128"
    msg = f"proxy={url} enc={quote(password, safe='')} plus={quote_plus(password)}"
    masked = mask_message(msg, secret_values([{"PROXY_URL": url}]))
    assert user not in masked and password not in masked
    assert quote(password, safe="") not in masked and quote_plus(password) not in masked
    assert "@nas.example.test:3128" in masked


def test_M3b_舊格式proxy區段():
    user, password = _fake(8), _fake()
    masked = mask_message(f"auth {user}:{password} at h:1",
                          secret_values([{"proxy": {"username": user, "password": password,
                                                    "endpoint": "h:1"}}]))
    assert masked == f"auth {MASK}:{MASK} at h:1"


# ── M4 ──
def test_M4_金鑰以百分比編碼出現():
    key = _fake(10) + "+/=" + _fake(10)
    msg = f"a={quote(key, safe='')} b={quote_plus(key)} c={key}"
    masked = mask_message(msg, [key])
    assert masked == f"a={MASK} b={MASK} c={MASK}"


def test_M4b_含空白的值_quote_plus形態與quote不同_也要遮():
    """稽核登記 1：上一條的值沒有空白時，`quote` 與 `quote_plus` 兩種編碼**逐字相同**，
    於是「只拿掉 quote_plus 形態」的突變照樣綠。含空白時兩者才不同（`%20` 對 `+`）。"""
    key = _fake(8) + " " + _fake(8)
    assert quote(key, safe="") != quote_plus(key)  # 前提：兩種形態確實不同
    msg = f"only_plus={quote_plus(key)} end"
    assert mask_message(msg, [key]) == f"only_plus={MASK} end"
    msg = f"only_quote={quote(key, safe='')} end"
    assert mask_message(msg, [key]) == f"only_quote={MASK} end"


# ── M5 ──
def test_M5_服務帳戶私鑰_真實換行與反斜線n兩種():
    pk = f"-----BEGIN PRIVATE KEY-----\n{_fake(40)}\n{_fake(40)}\n-----END PRIVATE KEY-----\n"
    pk_id = _fake(40, "0123456789abcdef")
    escaped = pk.replace("\n", "\\n")
    msg = f"raw:{pk}|json:{escaped}|id:{pk_id}"
    for source in ({"google_service_account": {"private_key": pk, "private_key_id": pk_id}},
                   {"GSPREAD_SA_JSON": '{"private_key": %s, "private_key_id": "%s"}'
                    % (__import__("json").dumps(pk), pk_id)}):
        masked = mask_message(msg, secret_values([source]))
        assert masked == f"raw:{MASK}|json:{MASK}|id:{MASK}", source.keys()


# ── M6 ──
def test_M6_OAuth敏感欄遮_client_id與redirect_uri保留():
    cs, at, rt, cid = _fake(), _fake(), _fake(), _fake(12)
    redirect = "https://app.example.test/callback"
    msg = f"{cs} {at} {rt} {cid} {redirect}"
    values = secret_values([{"google_oauth": {"client_secret": cs, "client_id": cid,
                                              "redirect_uri": redirect}}],
                           oauth_tokens={"access_token": at, "refresh_token": rt})
    assert mask_message(msg, values) == f"{MASK} {MASK} {MASK} {cid} {redirect}"
    custom = secret_values([], custom_oauth_cfg={"client_secret": cs})
    assert mask_message(cs, custom) == MASK


# ── M7 ──
def test_M7_沒有秘密值的訊息逐字相同():
    msg = ("HTTPSConnectionPool(host='x', port=443)：全形　空白\n換行\t" * 200)
    assert mask_message(msg, secret_values([{"FRED_API_KEY": _fake()}])) == msg
    assert not masking.is_masked(msg)


# ── M8 ──
def test_M8_空值不參與():
    msg = "abc def"
    assert secret_values([{"FRED_API_KEY": "", "GEMINI_API_KEYS": " , ,"}]) == []
    assert mask_message(msg, ["", None]) == msg


# ── M9 ──
def test_M9_互為子字串_長的整段換成一個記號():
    short = _fake(12)
    long = short + _fake(12)
    assert mask_message(f"x{long}y{short}z", [short, long]) == f"x{MASK}y{MASK}z"


# ── M10 ──
def test_M10_多次出現全部換掉():
    key = _fake()
    assert mask_message(f"{key}-{key}-{key}", [key]) == f"{MASK}-{MASK}-{MASK}"


def test_多把Gemini與編號鍵都收():
    a, b, c = _fake(), _fake(), _fake()
    values = secret_values([{"GEMINI_API_KEYS": f"{a}, {b}", "GEMINI_API_KEY_7": c}])
    assert set(values) == {a, b, c}


def test_讀不到的來源不炸():
    class Broken:
        def get(self, key):
            raise FileNotFoundError("no secrets.toml")

    assert secret_values([Broken(), None]) == []


def test_非字串訊息當場炸():
    with pytest.raises(TypeError):
        mask_message(None, [])


def test_自寫的百分比編碼與urllib逐字相同():
    samples = [_fake(40, string.printable), "中文 金鑰+/=?&", " ", "~._-", _fake(5) + "\n" + _fake(5)]
    for value in samples:
        assert masking._quote(value, plus=False) == quote(value, safe=""), value
        assert masking._quote(value, plus=True) == quote_plus(value), value


# ── 鍵名表 vs 兩張範本 ──
def _template_keys(path):
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    keys = []
    for k, v in data.items():
        if isinstance(v, dict):
            keys.extend(f"{k}.{sub}" for sub in v)
        else:
            keys.append(k)
    return keys


def test_兩張範本的每個鍵都落在遮或不遮的表裡():
    covered = set(masking.MASKED_WHOLE_VALUE_KEYS) | set(masking.MASKED_COMMA_LIST_KEYS) \
        | set(masking.MASKED_URL_USERINFO_KEYS) | set(masking.MASKED_SA_JSON_KEYS) \
        | {f"{s}.{f}" for s, fs in masking.MASKED_SECTION_FIELDS.items() for f in fs} \
        | set(masking.NOT_MASKED_KEYS)
    seen = 0
    for rel in ("secrets.toml.example", ".streamlit/secrets.toml.example"):
        for key in _template_keys(_ROOT / rel):
            seen += 1
            assert key in covered, (rel, key)
    assert seen >= 10  # 空掃防呆


def test_遮與不遮兩張表不重疊():
    masked = set(masking.MASKED_WHOLE_VALUE_KEYS) | {
        f"{s}.{f}" for s, fs in masking.MASKED_SECTION_FIELDS.items() for f in fs}
    assert not masked & set(masking.NOT_MASKED_KEYS)
