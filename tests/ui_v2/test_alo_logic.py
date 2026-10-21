# -*- coding: utf-8 -*-
"""資產配置（ALO）純邏輯測試。**不需要 streamlit**，系統直譯器跑得起來。

要跑起來：`pytest tests/ui_v2/test_alo_logic.py -q --noconftest`
（`--noconftest` 是因為 repo 根的 `tests/conftest.py` 會 import 舊 repo 的取數層。）

⚠️ 每一條都寫出它在驗 `44` 的哪一行判準或哪一條規則。
   每一道守衛本輪都在 scratchpad 的副本上**真的把實作改壞跑過一次**（突變測試），
   結果記在本輪回報裡；本檔不寫那些數字（會漂）。
"""

import ast
import copy
import csv
import io
import math
import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ui_v2.alo import fixtures, logic, theme  # noqa: E402

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_D44 = _ROOT / "docs" / "v2" / "44_fund_ui_ssot.md"
_ALO_DIR = _ROOT / "ui_v2" / "alo"
_APP = _ROOT / "ui_v2" / "app_alo.py"

# 本頁全部原始碼檔（逐字守衛、禁詞守衛、隔離守衛的母體都從這一份出發）。
_ALL_SOURCE_FILES = (
    _ALO_DIR / "__init__.py",
    _ALO_DIR / "fixtures.py",
    _ALO_DIR / "logic.py",
    _ALO_DIR / "theme.py",
    _ALO_DIR / "page.py",
    _APP,
)


def _model(name="full", *, save_failed=False, **override):
    dataset = fixtures.scenario_with(name, save_failed=save_failed)
    for key, value in override.items():
        dataset[key] = value
    return logic.build_page_model(dataset)


def _every_case():
    for name in fixtures.ALL_SCENARIO_NAMES:
        for save_failed in fixtures.SAVE_FAIL_CHOICES:
            yield name, save_failed


def _setting(dataset, key, value):
    for row in dataset["user_setting"]:
        if row["setting_key"] == key:
            row["setting_value"] = value
            row["updated_at"] = fixtures.UPDATED_AT if value is not None else None
            return dataset
    raise KeyError(key)


def _block(model, code):
    return logic.find_block(model, code)


# ═════════════════════ 一、分離與隔離 ═════════════════════

_BANNED_IMPORTS = (
    "from ui.",
    "from services.",
    "from repositories.",
    "from shared.",
    "from infra.",
    "import fund_fetcher",
    "import requests",
    "import httpx",
    "import urllib",
    "import yfinance",
    "import gspread",
    "import feedparser",
    "import socket",
    "import subprocess",
    "from ui_v2.mkt",
    "from ui_v2.hld",
    "from ui_v2.exp",
    "from ..mkt",
    "from ..hld",
    "from ..exp",
)


def _imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            out.add(("." * node.level) + (node.module or ""))
    return out


_OLD_ROOTS = {"ui", "services", "repositories", "shared", "infra", "fund_fetcher"}
_NET_ROOTS = {"requests", "httpx", "urllib", "urllib3", "yfinance", "gspread", "feedparser", "socket", "subprocess"}
_SISTER_PAGES = {"mkt", "hld", "exp"}


def _module_of(path) -> str:
    rel = path.relative_to(_ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _import_targets(source: str, module: str, *, is_package=False):
    """AST 解析每一條 import，把**相對寫法換算成絕對模組名**，連 `from X import Y` 的 Y 也算成 `X.Y`。

    回 [(絕對目標, 原寫法)]。不用字串前綴：`from .. import exp`、`from ui_v2 import exp`、
    `import ui_v2.hld` 三種寫法都換算成 `ui_v2.exp`／`ui_v2.hld` 再判。
    """
    package = module if is_package else module.rpartition(".")[0]
    out = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((alias.name, f"import {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                base = base[: len(base) - (node.level - 1)]
                root = ".".join(base + ([node.module] if node.module else []))
            else:
                root = node.module or ""
            out.append((root, f"from {'.' * node.level}{node.module or ''} import ..."))
            for alias in node.names:
                out.append((f"{root}.{alias.name}", f"from {'.' * node.level}{node.module or ''} import {alias.name}"))
    return out


def _forbidden_import(target: str) -> bool:
    parts = target.split(".")
    if parts[0] in _OLD_ROOTS | _NET_ROOTS:
        return True
    return len(parts) >= 2 and parts[0] == "ui_v2" and parts[1] in _SISTER_PAGES


def test_六個檔都沒有import舊repo或網路或姊妹頁():
    """母體＝本頁全部六個原始碼檔（含 page.py 與 app_alo.py）。AST 換算成絕對模組名再判。"""
    assert len(_ALL_SOURCE_FILES) == 6
    seen = 0
    for path in _ALL_SOURCE_FILES:
        source = path.read_text(encoding="utf-8")
        targets = _import_targets(source, _module_of(path), is_package=path.name == "__init__.py")
        seen += len(targets)
        bad = [raw for target, raw in targets if _forbidden_import(target)]
        assert not bad, (path.name, bad)
    assert seen >= 10, seen  # 真的走過了 import（空掃會是 0）


def test_logic與fixtures與theme與init都沒有import_streamlit():
    for path in _ALL_SOURCE_FILES[:4]:
        mods = _imported_modules(path)
        assert not any(m.split(".")[0] == "streamlit" for m in mods), (path.name, mods)
        assert "import streamlit" not in path.read_text(encoding="utf-8"), path.name


def test_隔離掃描器本身會咬_負控():
    """每一種跨頁與舊 repo 的寫法都要被判出來；本頁自己的相對 import 不得被誤判。"""
    page_mod = "ui_v2.alo.page"
    must_catch = (
        "from ui_v2 import exp",
        "from .. import exp",
        "from ..hld import logic",
        "from ..mkt.logic import x",
        "import ui_v2.hld",
        "import ui_v2.exp.logic as el",
        "from ui_v2.mkt import fixtures",
        "from services.macro import x",
        "import requests",
        "import urllib.request",
        "from infra import proxy",
    )
    for line in must_catch:
        targets = _import_targets(line + "\n", page_mod)
        assert any(_forbidden_import(t) for t, _raw in targets), line
    for line in ("from . import fixtures, logic, theme", "import html", "from ui_v2.alo import page", "import streamlit as st"):
        targets = _import_targets(line + "\n", page_mod)
        assert not any(_forbidden_import(t) for t, _raw in targets), line


def test_fixtures不import_logic_假資料不依賴判定層():
    source = (_ALO_DIR / "fixtures.py").read_text(encoding="utf-8")
    assert "import logic" not in source
    assert "from . import" not in source


def test_44還是凍結的那一份():
    import hashlib

    # 2026-10-13 解凍（市場總覽 MKT-4／MKT-5 客戶裁示落字，同日再落稽核 G 回修：觀察窗上限、一致性憑證鍵、標題寫已存值、不預勾等，只在既有行內擴寫、行數不變）；舊值 795614090627cb6368bd2021244e9217。
    # 2026-10-13 再解凍（標的探索客戶裁示落字，`EXP-1`／`EXP-2`／第四節第六小節，只動標的探索相關段落；既有行內擴寫、行數不變，全文寫在檔尾；同日再補「其五」與「其三之一」，分支上兩版 c2c11310ac729e08459b0bafc185fba8、47d1641ec12c968cd03c9fb9e88c3bc2、ef8e245fe754be97fa8c85f0b31a7d52、87088e958697b98050166e8b5381d803）；上一個主線值 77aad71ba0c99b7324f031165aad6dc3。
    # 2026-10-14 再解凍（標的探索 C2 接線紀錄，檔尾追加第七節第三小節之三；前文一字未動；分支上前三版 2c5803f3d0bac6b40cc88fb09b929cfc、e5193b6e2a2f0804b89855d065ed41ae、095bdedc0865a369dbf02bc7f63c4c3a）；上一個主線值 cd7bd86bea69ef4157ca0debc8657842。
    # 2026-10-15 #966 修正輪 2：7.3.3 末條 Q7 半句加刪除線並追加更正與白話化補正（只動檔尾標的探索段落）。
    # 2026-10-15 Phase 1.5（客戶 2026-10-15 裁示 A+ 修正版）：方向性條文改寫為現況＋准入條件；前文只做行內擴寫、行數不變，檔尾追加第七節第三小節之四；上一個主線值 11c523139f2dae27a551ba9af5d90568（同 PR 稽核回修前分支值 df58130ed9c4e815da5bf078257094a8）。
    # 2026-10-16 客戶裁示第 6、7 點（黃色「不適用」改中性灰、MKT-0 三塊皆空 → 灰）：前文只做行內擴寫、行數不變，檔尾追加第七節第三小節之五；上一個主線值 336328ba155069407bcc7433501898bb。
    # 2026-10-16 客戶裁示第 2、5、8 點與資產配置第 3、9 點紀錄：前文只在第 583、587、700 行行內擴寫、行數不變，檔尾追加第七節第三小節之六；上一個值 cefdabe36f5a37a228fddcc69ad10a94。
    # 同日 PR #976 稽核後回修：只在檔尾第七節第三小節之六行內補句、行數不變；上一個分支值 ec324b23e62254d92412a6e5c28e6665。
    # 2026-10-17 再解凍（客戶 2026-10-17 Phase 3 UI/UX 八題裁示 DEC-2026-10-17-03，第 (1)(3)(4)(5)(8) 題範圍：前 4521 行只做行內擴寫、行數不變，檔尾追加第七節第三小節之七）；上一個主線值 6373dacde0cf797d363962aca63d01f9。
    # 同日稽核回修：前 4521 行只插字（劃線只加記號），檔尾之七內補句；上一個分支值 9283b993982581b87c96a079a79e9736。
    # 2026-10-17 第二輪解凍（客戶核准 60 第二輪解凍提案八題 DEC-2026-10-17-07：前 4624 行只做行內擴寫、行數不變，檔尾追加第七節第三小節之八）；上一個值 5f5ca5acd3cdc5b18a5eb5d2c9b8ed8a。
    # 同日獨立稽核回修：前 4624 行只插字（劃線只加記號），檔尾之八內改句、行數不變；上一個分支值 060128a19f3e69c9881d7a755b0ddbdf。
    # 2026-10-17 ◆／◇ 小批（DEC-2026-10-17-03 第 (3)(4) 題、DEC-2026-10-17-07 (c-2)）：之七其七第 15、19、25 條三處舊字面劃線、之八 (c-2) 行內補狀態與總管三點內部決定、獨立稽核回修補第 2323 行狀態字，
    # 只在既有行內插字、行數不變；上一個值 fe24652733c72b98b4d838786498d63a。
    # 2026-10-18 P1-④ Answer-first 實作批（DEC-2026-10-17-07 (a-1)～(a-4)）：第二節硬規則第二條、節判準、斷點表層 3 兩格、第五節第四小節元件判準的舊字面劃線、之八開頭第 6 條行內補落地狀態，
    # 只在既有行內插字、行數不變；上一個值 63ed86f5fabf8afc29430e165d6ca39b。
    # 同批獨立稽核回修（2026-10-18）：HLD-0 來源欄、規則欄與之八其一 (a-2) 第 1 條的 j 定義劃線更正，只在既有行內插字、行數不變；上一個值 fe409e047453fb27ea0cb8f5297626fc。
    # 2026-10-18 P1-⑥ 設定與診斷頁重排實作批（DEC-2026-10-17-07 (b-1)～(b-4)、(c-1)）：設定與診斷層表三列、`SET-0` 規則欄的舊字面劃線、之八開頭第 6 條與其二 (b-2) 第 3 條行內補落地狀態，
    # 只在既有行內插字、行數不變；上一個值 73562681440d104e3bdc5b2a81ff8a3e。
    # 同批獨立稽核回修（2026-10-18）：之八其二 (b-2) 第 3 條「舊字面待實作批劃線」劃線並補狀態，只在既有行內插字、行數不變；上一個值 7499e14aa9af739f5b6120a302891563。
    # 2026-10-18 客戶裁示批（DEC-2026-10-18-01；BL-0371、BL-0373、BL-0374 的 S1／S4／C1／C2）：MKT-0、MKT-7、SET-0、SET-1 格尾行內擴寫、之八揭露段加指標（前 4730 行行數不變），檔尾新增之九；上一個值 bc9282479ae9f9a1271dadfba3f6ab0e、4731。
    # 同批回修（2026-10-18，總管指示）：BL-0371 不限正式模式 —— MKT-0／SET-0 舊字面劃線；BL-0373 逐頁審 —— MKT-6、HLD-2、HLD-6、HLD-7 格尾指標；之九補兩條；前 4730 行行數不變；上一個值 d7fc4af080c0757784c5d847a76e76a6、4788。
    # 同批第二次回修（2026-10-18，獨立稽核後總管裁定）：MKT-5、HLD-5 格尾指標、MKT-6 格尾劃線改寫、之九其二第 5 條改寫為統一規則與末段計數更正；前 4730 行行數不變；上一個值 c99a564df35497fb116e65f09c9b260b、4790。
    # 同批第三次回修（2026-10-18）：HLD-6、HLD-7 格尾指標改為「全是取數失敗才整塊 ⛔、混合時照之九其二第 5 條」，之九其二第 5 條補一句；行數不變；上一個值 00bfc756c9ddf530b519d7972f4dd701。
    # 2026-10-18 客戶第二筆裁示批（DEC-2026-10-18-02；BL-0374 C3、BL-0375）：第七節第三小節之三「舊淨值」那一條、之九開頭 C3 那一條與其三第 6 條行內指標、之九其二第 6 條舊字面劃線並加指標（前 4789 行行數不變），檔尾新增之十；上一個值 de716b0786e03505846aa5ac688b1d91、4789。
    # 同批獨立稽核回修（2026-10-18）：之十其二第 1 條補「只在累積表併入閘門關閉時成立」與 BL-0376 指標，只在檔尾之十行內插字、行數不變；上一個值 e3865ed04a8846a0361c079c3039ca84。
    # 2026-10-19 BL-0250 回修批次 2（DEC-2026-10-19-04 G1；文字類 U1／U2／U3／U5／U6）：前 4832 行只做行內擴寫、行數不變（第一節第三小節欄名劃線改寫），檔尾新增之十一；上一個值 b7f284de423fce1ea17459965b98126a、4832。
    # 同批獨立稽核回修（2026-10-19，總管裁定）：前 4832 行只插字（七處舊字面劃線，原字保留），檔尾之十一第 5 條更正、其三補 EXP-1 一條（多 1 行）；上一個分支值 26d0af1d8b6de6e85f1d9037edfe85bf、4899。
    # 同批第二次稽核回修（2026-10-19，總管裁定 ALO-1 採方案 (a)）：ALO-1 那一行取消劃線改行內註明，之十一第 5 條與其三行內補理由；行數不變；上一個值是未提交的中間值 99f89610ccc5d55baa4e4eac88decd56（工作樹裡量的，沒有進任何提交，不能用 git show 驗證）；上一個已提交的分支值 26d0af1d8b6de6e85f1d9037edfe85bf（2ef65a4a）。
    # 同批第三次稽核回修（2026-10-19，第二次獨立稽核不通過後總管裁定）：之十一第 5 條不再複述 ALO-1 那一行的字面、ALO-7 規則欄劃線後補「→ 三欄：項目……」讓「（updated_at）」讀得通；行數不變；上一個值 3d81b53db6f1bf91c55239944fd4e422（aedc40bb）。
    # BL-0250 批次 3-A（2026-10-19，客戶批次 3 裁示 `DEC-2026-10-19-05`）：前 4900 行只做行內擴寫（行數不變；`HLD-4` 規則欄一處括號劃線、原字保留），檔尾新增第七節第三小節之十二（多 78 行）；上一個值 977a794616998468652e265a536d7405、4900 行（507473a4）。本批工作樹裡量過兩個未提交的中間值 b2fa56be681a7cb0bba57af3eb75f7c4、b9f0d5ba1f211a0e4115755480fbb2d5（沒有進任何提交，不能用 git show 驗證；後者之後只把之十二裡逐字複述的畫面文案改成轉述，CLAUDE.md §-2.A 第 8 款）。
    # 同批總管裁定（2026-10-19，決策者：AI 總管（適用客戶 DEC-2026-10-19-05 第 2／3 點）；44 之十二其九）：前 4900 行只做行內擴寫（行數不變；之九其二第 1 條、之九其三第 3 條、第五節第一小節本批加的那一句劃線改寫），檔尾之十二新增其九並劃線更正幾處（多 8 行）；上一個值 ae0fe813a0a5fd085f7814c49f715fc7、4978 行（446f6a2f）。
    # 同批稽核回修（2026-10-19，兩組獨立稽核後總管指示；決策者 AI 總管）：撤回之十二其九第 2、3 條（之九其三第 3 條還原為改寫前字面、只留一個行內指標）、檔尾新增其十並補幾處行內指標（前 4900 行行數不變）；上一個值 ace67bdeb356a6636bc9e36ff6dbc6cf、4986 行（3d01f6ee）。
    # 同批第二次稽核回修（2026-10-19，決策者 AI 總管；總管派工單自身錯誤的就地更正）：之十二其十第 1 條射程收窄、其九第 3 條撤回理由更正、第五節第一小節那一句跟著改（行數不變）；上一個值 9a9727206827b57e88636dab0dc9e16e、4995 行（e606e6ec）。
    # BL-0250 批次 3-B（2026-10-19，客戶批次 3 裁示 `DEC-2026-10-19-05`；多選清單、結果清單每列來源展開）：前 4995 行只做行內擴寫（行數不變；十處行內指標，前文沒有劃線），檔尾新增第七節第三小節之十三（多 65 行）；上一個值 aaf306cf99fdc76cf711ecb148d88818、4995 行（23c351b9）。
    # BL-0250 批次 3-B 同批總管裁定（2026-10-19，決策者 AI 總管）：前 4995 行只做行內擴寫（行數不變；第五節第二小節 來源 那一列與之十二其一第 1 條各插一個指標），檔尾之十三新增其五之一～之三並補幾處行內更正（多 19 行）；上一個值 ffedfba54a082182aaa667a3053eecda、5060 行。
    # BL-0250 批次 3-B 總管第二輪裁定（2026-10-19，決策者 AI 總管）：前 4995 行只做行內擴寫（行數不變；第三節第五小節層表層 2 那一列、`SET-0` 來源欄、第七節第一小節計數表兩列各插一個指標），檔尾之十三新增其五之四、之五、其七（含新塊 `SET-8` 的標題、四件事與判準）並補幾處行內指標（多 35 行）；上一個值 cc8655420e27446de46339569ac2e787、5079 行（c1738ba2）。
    # BL-0250 批次 3-B 稽核回修（2026-10-20，be9dc9de；決策者 AI 總管）：稽核回修輪前文首次劃線（第三節第零小節節判準行內插字、之十二其七行內劃線），檔尾之十三新增其八並補多處行內指標（多 23 行）；上一個值 aa3b11b92d9675179d078e04f7535511、5114 行（7332b9f8）。
    # BL-0250 批次 3-B 總管裁定標的探索 4.2（2026-10-20，50b1c513）：檔尾其八新增第 13 條並補一處行尾指標（多 1 行）；上一個值 c269a3ed8bfddc6285c0511e046b9129、5137 行（be9dc9de）。
    # BL-0250 批次 3-B 第二輪稽核回修（2026-10-20，b905e6a3）：前文只做行內插字（第七節第一小節計數表兩列改成 ~~41~~ → 42、第七節第三小節之十三其五之三（檔尾，非前文）那一處轉述改字「見」），檔尾其八新增第 14～21 條並補多處行內劃線與指標（多 8 行）；上一個值 992f7ad77107b080ed3ac976cbcaa371、5138 行（50b1c513）。
    # BL-0250 批次 3-B 複驗回修（2026-10-20，1aef67cd）：只動檔尾之十三（其六補第 12 條、其八第 18／20 條行內劃線、新增第 22 條；多 2 行）；上一個值 341dafb108e781dbe90e96fafdaf713b、5146 行（b905e6a3）。
    # BL-0250 批次 3-B 客戶驗收裁示第 1 題（2026-10-20，d904f249；DEC-2026-10-20-01，決策者：客戶）：只動檔尾之十三（開頭第 2 條、其五之四第 2 條、其五之五第 6 條行內劃線與指標，其六新增第 13 條、其八新增第 23 條、「維持現況，只登記」第一項劃線；多 2 行）；上一個值 caff3be14d08977510bccf9d99d860da、5148 行（1aef67cd）。
    # 同批獨立稽核回修（2026-10-20，本輪）：只動檔尾之十三（其五之四標題行與第 2 條補劃線加指標、其六第 13 條、其八第 23 條補註、凍結不變量補一句；行數不變）；上一個值 63b929e0abd3dd15020b476e7e40e6aa、5150 行（d904f249）。
    # BL-0250 批次 3-C（2026-10-21；DEC-2026-10-21-01、-02，決策者：客戶）：前 5150 行只做行內擴寫（行數不變；第五節第一小節 `ok` 列、第五節第四小節元件判準、`HLD-6`／`HLD-8` 規則欄、之三「來源標示」、之七其二第 4 條、之十二其十第 6 條、之十三其二／其三／其四／其五之一／其七／其八多處行內劃線與指標），檔尾新增第七節第三小節之十四（多 74 行）；上一個值 c8d96840cf19db01408285f2790dde08、5150 行（ce6ffc32）。
    # 同批總管裁定回修（2026-10-21，獨立稽核之後）：只動檔尾之十四（其一第 6 條、其二第 2 條、其四第 2 條、其七第 2 條行內劃線與指標，揭露段與凍結不變量各補一句；行數不變）；上一個值 a1bf519202a879a6ddb7ec5d6fbfd2c0、5224 行（8b6534e8）。
    # BL-0250 批次 3-D（2026-10-21；DEC-2026-10-21-03、-04，決策者：客戶）：前 5224 行只做行內擴寫（行數不變；第五節第一小節 `資料未備`／`系統錯誤` 兩列、第五節第五小節 `來源缺`／`部分缺`／`系統錯誤` 三列、之七其二第 3 條、MKT-1～3／HLD-1～3／EXP-1／ALO-2～3／SET-1 空狀態欄的行內指標，前文沒有劃線），檔尾新增第七節第三小節之十五（多 57 行）；上一個值 6b9f012cb501022e82439ecbbe1f6abb、5224 行（5c058c69）。
    # 同批獨立稽核回修（2026-10-21，決策者 AI 總管）：只動檔尾之十五（凍結不變量那一行補記紅線標記與不帶 † 代號字樣的計數；其一第 5、6 條補記取數失敗不被吞、狀態族句條件、◇ 不消失；行數不變）；上一個值 1825fd79db135a52e8bf348106080e58、5281 行（7d4b4fc1）。
    # 客戶 2026-10-21 第二筆裁示 Q5～Q7（DEC-2026-10-21-05，決策者：客戶）：只動檔尾之十五（其二第 3 條、其三標題、其五第 2 條、末段揭露行內更正，新增其九；多 6 行）；上一個值 22b8908950063d8b817f96504afa636c、5281 行（394603df）。
    # 同批稽核複驗回修（2026-10-21，決策者 AI 總管依稽核指正）：只動檔尾之十五其九第 1、3 條行內劃線與更正（Q7「與標頭對得上」不實、④ 比照改保守預設；行數不變）；上一個值 97d41f7e417a9c11db0bd0c6f3e1798b、5287 行（0f43b381）。
    assert hashlib.md5(_D44.read_bytes()).hexdigest() == "17acbb8c2a8f307f1bec13976467506c"


def test_取數失敗圖示是禁止號_黃燈仍是警告號():
    """客戶 2026-09-24 裁示（`44` 第五節第五小節已同步）：取數失敗 ⛔、黃燈 ⚠。改回 ⚠ 這一條要紅。"""
    assert logic.FETCH_FAIL_GLYPH == "⛔"
    assert logic.fetch_failed_text("HTTP 503") == "⛔ 取數失敗：HTTP 503"
    assert _block(_model("holdfail"), "ALO-0")["glyph"] == "⛔"
    assert _block(_model("full"), "ALO-0")["glyph"] == "⚠"


def test_存檔寫入失敗圖示是禁止號_與取數失敗同一個常數_畫面層不寫字面():
    """客戶 2026-09-25 裁示：存檔寫入失敗 ⚠ → ⛔，⚠ 只留給黃燈。改回 ⚠ 這一條要紅。
    畫面層的實際渲染由 `test_alo_page.py` 量（slow lane）；本條是 fast lane 上的那一道。"""
    assert logic.SAVE_FAIL_GLYPH == "⛔"
    assert logic.SAVE_FAIL_GLYPH == logic.FETCH_FAIL_GLYPH
    assert logic.SAVE_FAIL_GLYPH != logic.WARN_GLYPH
    import pathlib as _pl

    page_src = _pl.Path(logic.__file__).with_name("page.py").read_text(encoding="utf-8")
    assert "{logic.SAVE_FAIL_GLYPH} {_esc(line)}" in page_src
    assert 'role="alert">⚠' not in page_src


def test_holding取數失敗_照44第五節系統錯誤模板畫在受影響的塊_不整頁炸():
    """登記 `ALO-GAP-取數失敗`：`⛔ 取數失敗：<訊息原文>`、紅；不畫重新取數（空狀態欄整格為準）。"""
    model = _model("holdfail")
    text = "⛔ 取數失敗：" + fixtures.FETCH_FAIL_MESSAGE
    for code in ("ALO-2", "ALO-6"):
        node = _block(model, code)["placeholder"]
        assert node["text"] == text and node["_empty_kind"] == "系統錯誤" and node["_tone"] == "紅", code
    assert _block(model, "ALO-3")["placeholder"]["text"] == text
    assert _block(model, "ALO-4")["fail_nodes"][0]["text"] == text
    assert _block(model, "ALO-5")["buttons"][0]["_enabled"] is False
    assert not [b for b in logic.collect_buttons(model) if b["_action_kind"] == "取數"]


def test_holding取數失敗時燈不說尚未建立任何持倉_導覽鈕照掛():
    """登記 `ALO-GAP-失敗時導覽鈕`／`ALO-GAP-無紅燈`：取數失敗不等於持倉表為空；燈沒有紅。
    `44` 現行（第二十一輪）空與不空都掛導覽鈕 ⇒ 不知道是哪一種也照掛；但摘要不寫缺 holding。"""
    model = _model("holdfail")
    lamp = _block(model, "ALO-0")
    assert lamp["text"] == "⛔ 取數失敗：" + fixtures.FETCH_FAIL_MESSAGE
    assert logic.TEXT_NO_HOLDING not in logic.collect_ui_strings(lamp)
    assert lamp["_tone"] == "灰"
    assert (logic.TEXT_GOTO_SHEETS, "導覽") in _buttons_of(model, "ALO-4")
    assert "缺 holding" not in _block(model, "ALO-4")["summary_text"]


def test_市值基準下匯率取數失敗_ALO2與ALO6與ALO4照模板_成本基準不受影響():
    model = _model("fxfail")
    text = "⛔ 取數失敗：" + fixtures.FETCH_FAIL_MESSAGE
    assert _block(model, "ALO-2")["placeholder"]["text"] == text
    assert _block(model, "ALO-6")["placeholder"]["text"] == text
    assert _block(model, "ALO-4")["fail_nodes"][0]["text"] == text
    dataset = fixtures.scenario("fxfail")
    _setting(dataset, "alo_basis", logic.BASIS_COST)
    cost = logic.build_page_model(dataset)
    assert _block(cost, "ALO-2")["placeholder"] is None and _block(cost, "ALO-2")["_rows"]


def test_本頁沒有畫法的取數失敗才炸():
    dataset = fixtures.scenario("full")
    dataset["errors"] = {"fetch_log": "HTTP 503（示意）"}
    with pytest.raises(ValueError, match="取數失敗"):
        logic.build_page_model(dataset)


# ═════════════════════ 二、逐字引文守衛 ═════════════════════

_QUOTE_CONNECTORS = set(" \t\r\n#：:是寫著引的為，,。－—-*~`＝=（(")
# 本頁引的不是 `44` 的逐字句（例如引線框、引姊妹頁）才准登記在這裡，而且要寫出它在引什麼。
_NOT_A_44_QUOTE: dict = {}
_MIN_VERIFIED_QUOTES = 10


def _strip_struck(text: str) -> str:
    """把成對的 `~~…~~` 之間的字挖掉（可跨行；`44` 有兩處跨兩行的刪除線）。"""
    return re.sub(r"~~.*?~~", "", text, flags=re.DOTALL)


def _flat(text: str) -> str:
    text = re.sub(r"\n\s*#\s*", "", text)
    text = text.replace("『", "「").replace("』", "」")
    return re.sub(r"\s+", "", re.sub(r"\*\*|~~|`|\*|_", "", text))


def _quotes_introduced_by_verbatim(text: str):
    out = []
    for match in re.finditer("逐字", text):
        j = match.end()
        while j < len(text) and j - match.end() <= 12 and text[j] in _QUOTE_CONNECTORS:
            j += 1
        if j >= len(text) or text[j] != "「":
            continue
        depth, k = 0, j
        while k < len(text):
            if text[k] == "「":
                depth += 1
            elif text[k] == "」":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        if k < len(text):
            out.append((match.start(), text[j + 1 : k]))
    return out


def _all_verbatim_quotes():
    out = []
    for path in _ALL_SOURCE_FILES:
        text = path.read_text(encoding="utf-8")
        for pos, quote in _quotes_introduced_by_verbatim(text):
            out.append((path.name, text[:pos].count("\n") + 1, quote))
    return out


def _check_quote(quote: str, d44: str) -> str:
    """回 'live'（在現行文字裡）、'struck_only'（只在刪除線內）、'absent'。"""
    q = _flat(quote)
    if q in _flat(_strip_struck(d44)):
        return "live"
    if q in _flat(d44):
        return "struck_only"
    return "absent"


def test_標了逐字的引文_每一句都在44現行文字裡_而且不落在刪除線內():
    d44 = _D44.read_text(encoding="utf-8")
    found = _all_verbatim_quotes()
    assert found, "一句也沒抽到 —— 會變成空掃"
    bad, verified = [], 0
    for name, lineno, quote in found:
        if quote in _NOT_A_44_QUOTE:
            continue
        verdict = _check_quote(quote, d44)
        if verdict == "live":
            verified += 1
        else:
            bad.append(f"{name}:{lineno} [{verdict}] {quote!r}")
    assert not bad, "\n".join(bad)
    assert verified >= _MIN_VERIFIED_QUOTES, verified


def test_逐字守衛本身會咬_刪除線內的舊條文與捏造的句子都判不合法():
    """正控：一句 `44` 裡**只在刪除線內**的舊條文（`ALO-7` 退役的回答什麼）、一句捏造的句子。"""
    d44 = _D44.read_text(encoding="utf-8")
    retired = "我上次是什麼時候、把目標從多少改成多少"
    assert retired in d44  # 它確實在檔裡（在刪除線裡）
    assert _check_quote(retired, d44) == "struck_only"
    assert _check_quote("本塊一律依系統推算的比重排列", d44) == "absent"
    assert _check_quote("燈不指出該往哪個方向調", d44) == "live"
    # 抽取器也要會抽：一句由「逐字」引進來、跨行起頭的。
    sample = "# 44 逐字\n# 「燈不指出該往哪個方向調」\n"
    assert [q for _p, q in _quotes_introduced_by_verbatim(sample)] == ["燈不指出該往哪個方向調"]


def test_逐字豁免表沒有死條目():
    live = {q for _n, _l, q in _all_verbatim_quotes()}
    assert not (set(_NOT_A_44_QUOTE) - live)


def test_八塊的塊名逐字引44():
    text = _D44.read_text(encoding="utf-8")
    assert len(logic.BLOCK_TITLES) == 8
    for code, title in logic.BLOCK_TITLES.items():
        assert f"#### 塊 {code}｜{title}" in text, (code, title)


def test_八塊的回答什麼逐字引44現行那一句():
    d44 = _D44.read_text(encoding="utf-8")
    assert len(logic.ANSWERS) == 8
    for code, answer in logic.ANSWERS.items():
        assert _check_quote(answer, d44) == "live", (code, answer)
    # ALO-7 的回答什麼有一句被劃掉的舊版，本頁引的必須是現行那一句。
    assert logic.ANSWERS["ALO-7"] == "現在的目標配置是什麼"


def test_頁的回答什麼與不負責什麼逐字引44():
    d44 = _D44.read_text(encoding="utf-8")
    assert logic.PAGE_TITLE == "資產配置"
    assert _check_quote(logic.PAGE_ANSWERS, d44) == "live"
    for line in logic.NOT_RESPONSIBLE:
        assert _check_quote(line, d44) == "live", line


def test_44逐字的文案常數每一句都在現行文字裡():
    d44 = _D44.read_text(encoding="utf-8")
    assert logic.VERBATIM_TEXTS, "空的 —— 會變成空掃"
    for name, text in logic.VERBATIM_TEXTS.items():
        assert _check_quote(text, d44) == "live", (name, text)


# ═════════════════════ 三、層次、四層通則、斷點 ═════════════════════


def test_層次分佈照44那張表():
    model = _model("full")
    assert logic.codes_in_layer(model, 1) == ["ALO-0"]
    assert logic.codes_in_layer(model, 2) == ["ALO-1", "ALO-2", "ALO-3"]
    assert logic.codes_in_layer(model, 3) == ["ALO-4", "ALO-5"]
    assert logic.codes_in_layer(model, 4) == ["ALO-6", "ALO-7"]


def test_初次載入展開的剛好是結論燈與三張核心卡():
    for name, save_failed in _every_case():
        model = _model(name, save_failed=save_failed)
        opened = [b["code"] for b in model["blocks"] if b["_default_open"]]
        assert opened == ["ALO-0", "ALO-1", "ALO-2", "ALO-3"], (name, opened)


def test_斷點欄數照客戶最終版三段():
    got = [logic.layer_columns(2, w) for w in (1280, 1279, 769, 768, 375, 374)]
    assert got == [3, 2, 2, 1, 1, 1], got
    edges = {w for w in range(2, 2000) if logic.columns_for_width(w) != logic.columns_for_width(w - 1)}
    assert edges == {769, 1280}
    for width in (374, 768, 1279, 1920):
        assert logic.layer_columns(1, width) == 1
        assert logic.layer_columns(4, width) == 1
        assert logic.layer_columns(3, width) <= 2


def test_層3與層4每一塊都有收合摘要():
    for name, save_failed in _every_case():
        model = _model(name, save_failed=save_failed)
        for code in ("ALO-4", "ALO-5", "ALO-6", "ALO-7"):
            assert _block(model, code)["summary_text"], (name, code)


def test_收合摘要在資料缺時寫出缺的來源鍵():
    """`44` 5.4 元件判準：把某個收合區內的資料抽掉，收合狀態下的摘要那一行寫出缺的來源鍵。"""
    first = _model("first")
    assert "holding" in _block(first, "ALO-6")["summary_text"]
    assert "alo_basis" in _block(first, "ALO-4")["summary_text"]
    assert "alo_target_weights" in _block(first, "ALO-7")["summary_text"]
    assert "fx_twd_per_usd" in _block(_model("nofx"), "ALO-4")["summary_text"]


# ═════════════════════ 四、紅線 ═════════════════════


def test_現況守衛_目前B線v1沒有未授權方向性輸出_全頁模型零方向詞零箭頭():
    """現況守衛（2026-10-15 客戶裁示 Phase 1.5 起）：目前 B 線 v1 沒有未授權方向性輸出 —— 全頁模型文字對不上方向詞、語氣詞與箭頭。

    這不是「方向性判斷永久封死」：日後經正式規格核准、證據足夠、新鮮度與出處合格的方向性輸出塊，
    走帶證據的准入路徑進畫面（`44` 第七節第三小節之四），不是把字從字表裡拿掉。
    箭頭照舊不准（不得偷偷取代尚未核准的方向性模型）。
    """
    for name, save_failed in _every_case():
        strings = logic.collect_ui_strings(_model(name, save_failed=save_failed))
        assert strings
        assert logic.scan_forbidden(strings) == {}, (name, save_failed)


def test_掃描器本身會咬_負控():
    assert {"應該調整", "應調"} <= set(logic.FORBIDDEN_ADVICE_WORDS)
    for word in logic.FORBIDDEN_DIRECTION_WORDS + logic.FORBIDDEN_ARROWS + logic.FORBIDDEN_ADVICE_WORDS:
        assert logic.scan_forbidden([f"這一句含 {word} 這個詞"]) != {}, word


def _strip_forbidden_defs(text):
    """挖掉 `FORBIDDEN_*` 那幾個模組層定義本身（禁詞字表住在那裡，不該掃到自己）。"""
    lines = text.split("\n")
    drop = set()
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id.startswith("FORBIDDEN_") for t in node.targets
        ):
            drop.update(range(node.lineno - 1, node.end_lineno))
    return "\n".join(line for i, line in enumerate(lines) if i not in drop)


def _source_without_forbidden_defs(path):
    return _strip_forbidden_defs(path.read_text(encoding="utf-8"))


# 原始碼層級的禁語：`44` 1.2 禁方向詞與禁箭頭 ＋ 1.1 按鈕四禁詞 ＋ 派工單點名的兩個語氣詞。
def _source_forbidden_words():
    """⚠️ 按鈕四禁詞裡的「一鍵」**不收進原始碼層級的掃描**：`44` 4.1 的「業務唯一鍵」、
    「一枚按鈕同時寫兩鍵」這類字面必然撞到它（量「鍵」的數量，不是那個按鈕詞）。
    按鈕標籤那一層的「一鍵」照樣由 `test_按鈕標籤零禁詞_而且工廠會擋` 與畫面測試掃。"""
    button_words = tuple(w for w in logic.FORBIDDEN_BUTTON_WORDS if w != "一鍵")
    assert len(button_words) == 3
    return (
        logic.FORBIDDEN_DIRECTION_WORDS
        + logic.FORBIDDEN_ARROWS
        + logic.FORBIDDEN_ADVICE_WORDS
        + button_words
        + ("目標價", "建議")
    )


def test_原始碼六個檔零禁詞_母體含page與app_alo():
    """⛔ 交接檔 §8.1：姊妹頁的禁詞原始碼掃描漏了 page.py。本條的母體是六個檔，數目寫死。"""
    assert len(_ALL_SOURCE_FILES) == 6
    assert _ALO_DIR / "page.py" in _ALL_SOURCE_FILES and _APP in _ALL_SOURCE_FILES
    hits = []
    for path in _ALL_SOURCE_FILES:
        body = _source_without_forbidden_defs(path)
        for word in _source_forbidden_words():
            if word in body:
                hits.append((path.name, word))
    assert not hits, hits


def test_原始碼禁詞掃描本身會咬_負控():
    """在字串副本裡塞一個禁詞，同一支挖除函式留下它；FORBIDDEN_ 定義本身要被挖掉。
    （真的把禁詞塞進 page.py 副本那一次突變，記在本輪回報。）"""
    words = _source_forbidden_words()
    for word in words:
        probe = (
            "x = 1\nFORBIDDEN_DIRECTION_WORDS = (\n    " + repr(word) + ",\n)\n"
            "LABEL = " + repr("含" + word) + "\n"
        )
        body = _strip_forbidden_defs(probe)
        assert word in body, word
        assert "FORBIDDEN_DIRECTION_WORDS" not in body
        assert body.count(word) == 1, word


def test_按鈕標籤零禁詞_而且工廠會擋():
    for name, save_failed in _every_case():
        buttons = logic.collect_buttons(_model(name, save_failed=save_failed))
        assert buttons
        for button in buttons:
            for word in logic.FORBIDDEN_BUTTON_WORDS:
                assert word not in button["label"], (name, button["label"])
    for word in logic.FORBIDDEN_BUTTON_WORDS:
        with pytest.raises(ValueError):
            logic._button(f"測試{word}", "存檔")


def test_按鈕類別八類之內_而且沒有一類寫入那四張唯讀表():
    for name, save_failed in _every_case():
        for button in logic.collect_buttons(_model(name, save_failed=save_failed)):
            assert button["_action_kind"] in logic.BUTTON_KINDS
            assert not (button["_writes"] & set(logic.READONLY_TABLES)), button
    with pytest.raises(ValueError):
        logic._button("某個鈕", "再平衡")


def test_本頁沒有套用類按鈕():
    """`44` ALO-1／ALO-3 規則欄逐字「本頁沒有「套用」類按鈕」。"""
    for name, save_failed in _every_case():
        kinds = {b["_action_kind"] for b in logic.collect_buttons(_model(name, save_failed=save_failed))}
        assert "套用" not in kinds, name


def test_首次開啟那個情境沒有一列輸入欄帶非空的預設值():
    """`44` 1.1 節判準。"""
    inputs = logic.collect_inputs(_model("first"))
    assert inputs, "一個輸入欄也沒有 —— 會變成空掃"
    for field in inputs:
        assert field["_value"] in (None, ""), field


def test_紅線徽章只在說明區_而且是本頁那三枚():
    model = _model("full")
    marks = [b["text"] for b in logic.collect_badges(model) if b["_kind"] == "紅線"]
    assert sorted(set(marks)) == ["G1†", "G2†", "G3†"]
    for block in model["blocks"]:
        for row in block.get("_rows", ()):
            assert "†" not in "".join(v for v in row.values() if isinstance(v, str))


def test_狀態徽章字面值落在44那七個之內():
    for name, save_failed in _every_case():
        for badge in logic.collect_badges(_model(name, save_failed=save_failed)):
            if badge["_kind"] == "狀態":
                assert badge["text"] in logic.STATUS_BADGE_LITERALS
    with pytest.raises(ValueError):
        logic.status_badge("推薦")


def test_合成前一律換成新臺幣_每一個金額格都寫出TWD_而且假資料真的混兩種幣別():
    """客戶設計引導第三條：同卡不把不同幣別的數拿去合成。本頁的合成一律先換成新臺幣，格內寫出 TWD。"""
    assert {h["ccy"] for h in fixtures.scenario("full")["holding"]} == {"USD", "TWD"}
    checked = 0
    for name in ("full", "mvbasis", "partial"):
        model = _model(name)
        for row in _block(model, "ALO-6")["_rows"]:
            assert row["value_text"].endswith(" TWD"), (name, row["value_text"])
            checked += 1
        for row in _block(model, "ALO-3")["input_rows"]:
            if row["amount_text"] != "⬜":
                assert row["amount_text"].endswith(" TWD"), row
                checked += 1
    assert checked >= 12, checked
    # 市值基準：美元那兩檔真的乘了匯率（不是把原幣直接加總）。
    rows = {r["_fund_code"]: r for r in _block(_model("mvbasis"), "ALO-6")["_rows"]}
    assert math.isclose(rows["AAAA"]["_value"], 1000 * 15.20 * fixtures.FX_USED)
    assert math.isclose(rows["BBBB"]["_value"], 10000 * 21.50)


# ═════════════════════ 五、對比 ═════════════════════


def test_對比逐組算過而且未達標為零():
    failures = [
        (name, round(theme.contrast_ratio(fg, bg), 3), floor)
        for name, fg, bg, floor in theme.CONTRAST_PAIRS
        if theme.contrast_ratio(fg, bg) < floor
    ]
    assert not failures, failures
    assert len(theme.CONTRAST_PAIRS) >= 20


def test_每一個狀態色都以文字門檻對頁底與卡底各驗過一次():
    """狀態色會以文字出現在頁底（空狀態框、燈）與卡底（卡頭）上；四個語意色各要有這兩組、門檻 4.5。"""
    pairs = {(fg, bg, floor) for _n, fg, bg, floor in theme.CONTRAST_PAIRS}
    for tone, color in theme.TONE_HEX.items():
        for bg in (theme.APP_BG, theme.SURFACE):
            assert (color, bg, theme.TEXT_FLOOR) in pairs, (tone, color, bg)
    names = {n for n, _f, _b, _l in theme.CONTRAST_PAIRS}
    assert len(names) == len(theme.CONTRAST_PAIRS), "對比組名稱重複"


def test_對比函式本身算得對_負控():
    assert math.isclose(theme.contrast_ratio("#000000", "#ffffff"), 21.0, rel_tol=1e-9)
    assert math.isclose(theme.contrast_ratio("#777777", "#777777"), 1.0, rel_tol=1e-9)
    # 一組已知不過 4.5 的（灰字配灰底）必須判得出來。
    assert theme.contrast_ratio("#8b949e", "#6e7681") < theme.TEXT_FLOOR


def test_每一個用到的色都登記過對比():
    registered = {fg for _n, fg, _b, _f in theme.CONTRAST_PAIRS} | {bg for _n, _f, bg, _l in theme.CONTRAST_PAIRS}
    for color in theme.ALL_COLORS:
        if color == theme.BORDER:
            continue  # 純裝飾分隔線，見 theme.py 的登記
        assert color in registered, color
    page_source = (_ALO_DIR / "page.py").read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{6}\b", page_source), "page.py 不得寫色碼字面值"


def test_紅只出現在取數失敗的情境_而且燈永遠不紅():
    """登記 `ALO-GAP-無紅燈`：`ALO-0` 規則欄只給灰與黃；紅只來自 `44` 5.5 系統錯誤模板。"""
    red_cases = set()
    for name, save_failed in _every_case():
        model = _model(name, save_failed=save_failed)
        assert _block(model, "ALO-0")["_tone"] in ("灰", "黃"), name
        tones = {n["_tone"] for n in logic._walk(model) if "_tone" in n}
        assert tones <= set(theme.TONE_HEX), (name, tones)
        if "紅" in tones:
            red_cases.add(name)
    assert red_cases == {"holdfail", "fxfail", "settingfail", "policyfail"}, red_cases


_FAIL_TEXT = "⛔ 取數失敗：" + fixtures.FETCH_FAIL_MESSAGE


def _fail_blocks(model):
    """哪幾塊的畫面文字裡出現失敗文案。"""
    return {b["code"] for b in model["blocks"] if any(_FAIL_TEXT in s for s in logic.collect_ui_strings(b))}


def test_每一種取數失敗_受影響的塊逐塊點名():
    """依各塊來源判定（44 來源欄 ＋ 本頁登記的依賴）。ALO-0 經 ALO-2、ALO-3 讀 ALO-2。"""
    expected = {
        "holdfail": {"ALO-0", "ALO-2", "ALO-3", "ALO-4", "ALO-6"},
        "fxfail": {"ALO-0", "ALO-2", "ALO-3", "ALO-4", "ALO-6"},
        "settingfail": {"ALO-0", "ALO-1", "ALO-2", "ALO-3", "ALO-4", "ALO-6", "ALO-7"},
        "policyfail": {"ALO-6"},
    }
    for name, codes in expected.items():
        assert _fail_blocks(_model(name)) == codes, (name, _fail_blocks(_model(name)))
    assert _fail_blocks(_model("full")) == set()


def test_user_setting取數失敗_不說成未設定_不畫輸入欄():
    """登記 `ALO-GAP-設定取數失敗`：值取不到，不是沒設定。"""
    model = _model("settingfail")
    for code in ("ALO-1", "ALO-3", "ALO-4"):
        block = _block(model, code)
        assert logic.TEXT_UNSET not in logic.collect_ui_strings(block), code
        assert block.get("inputs") == [], code
    assert model["top_lines"] == []
    assert _block(model, "ALO-7")["placeholder"]["_empty_kind"] == "系統錯誤"
    assert (logic.TEXT_ADD_SCENARIO, "新增列") not in _buttons_of(model, "ALO-3")


def test_policy取數失敗只影響ALO6():
    model, ok = _model("policyfail"), _model("full")
    assert _block(model, "ALO-6")["placeholder"]["text"] == _FAIL_TEXT
    for code in ("ALO-0", "ALO-1", "ALO-2", "ALO-3", "ALO-4", "ALO-7"):
        assert logic.collect_ui_strings(_block(model, code)) == logic.collect_ui_strings(_block(ok, code)), code


def test_取數失敗時燈的狀態字不寫中性():
    """登記 `ALO-GAP-燈狀態字`。"""
    for name in ("holdfail", "fxfail", "settingfail"):
        lamp = _block(_model(name), "ALO-0")
        assert lamp["_tone"] == "灰"
        assert "中性" not in lamp["state_word"] and lamp["state_word"] == "狀態：取數失敗", name
        assert lamp["glyph"] == "⛔"
    assert _block(_model("inband"), "ALO-0")["state_word"] == "狀態：中性"


def test_tone_hex查不到就炸_不退回中性色():
    for tone in ("中性", "灰", "黃", "紅"):
        assert theme.tone_hex(tone).startswith("#")
    with pytest.raises(KeyError):
        theme.tone_hex("綠")
    with pytest.raises(KeyError):
        theme.tone_hex("")


# ═════════════════════ 六、ALO-0 差距結論燈 ═════════════════════


def test_ALO0只讀ALO2():
    model = _model("full")
    assert _block(model, "ALO-0")["_reads"] == ("ALO-2",)
    sig = list(__import__("inspect").signature(logic.conclusion_light).parameters)
    assert sig == ["alo2"], sig


def test_ALO0判準_放寬容許帶到涵蓋全部差距_燈轉灰且文案為各類別皆在容許帶內():
    lamp = _block(_model("inband"), "ALO-0")
    assert lamp["_tone"] == "灰"
    assert lamp["text"] == "各類別皆在容許帶內"


def test_ALO0判準_收緊容許帶_文案點名的類別與ALO2絕對差距最大那一列同名():
    model = _model("full")
    lamp, alo2 = _block(model, "ALO-0"), _block(model, "ALO-2")
    assert lamp["_tone"] == "黃"
    diffs = [(abs(r["_diff"]), r["_bucket"]) for r in alo2["_rows"] if r["_diff"] is not None]
    assert diffs
    top = max(diffs)[1]
    assert lamp["text"].startswith(top + " 與目標差 ")
    assert lamp["text"].endswith(" 個百分點")
    assert lamp["text"] == f"{fixtures.CORE} 與目標差 6.0 個百分點"


def test_ALO0判準_全新環境三句同時命中_出的是尚未建立任何持倉():
    lamp = _block(_model("first"), "ALO-0")
    assert lamp["text"] == "尚未建立任何持倉"
    assert lamp["_tone"] == "灰"


def test_ALO0的三句灰態依序取第一句():
    assert _block(_model("noholding"), "ALO-0")["text"] == "尚未建立任何持倉"
    assert _block(_model("notarget"), "ALO-0")["text"] == "尚未設定目標"
    assert _block(_model("notol"), "ALO-0")["text"] == "尚未設定容許帶"


def test_ALO0不帶正負號也不帶方向():
    """`44` ALO-0 規則欄逐字「燈不指出該往哪個方向調（G3†）」；差 N 取絕對值（登記 `ALO-GAP-燈的正負號`）。"""
    dataset = fixtures.scenario("full")
    _setting(dataset, "alo_target_weights", [
        {"bucket": fixtures.CORE, "weight_ratio": 0.75},
        {"bucket": fixtures.SATELLITE, "weight_ratio": 0.22},
        {"bucket": fixtures.CASH, "weight_ratio": 0.03},
    ])
    lamp = _block(logic.build_page_model(dataset), "ALO-0")
    assert lamp["text"] == f"{fixtures.CORE} 與目標差 9.0 個百分點"  # 66 − 75 ＝ −9，燈上不帶號
    assert "-" not in lamp["text"] and "+" not in lamp["text"]


def test_ALO0狀態同時有圖示與文字():
    for name, _s in _every_case():
        lamp = _block(_model(name), "ALO-0")
        assert lamp["glyph"] and lamp["state_word"] and lamp["text"], name


def test_ALO0在基準未選與缺匯率時不宣稱皆在容許帶內():
    """登記 `ALO-GAP-燈讀不到差距`：`44` 沒有寫這兩種情形的燈文案；本頁不宣稱一句沒有算過的話。"""
    for name in ("nobasis", "nofx"):
        lamp = _block(_model(name), "ALO-0")
        assert lamp["text"] != "各類別皆在容許帶內", name
        assert lamp["_tone"] == "灰"
    assert _block(_model("nobasis"), "ALO-0")["text"] == "⬜ 不適用：尚未選定比重基準"


def test_容許帶端點_差距剛好等於容許帶算帶內_不炸():
    """登記 `ALO-GAP-端點`（本頁判讀）：44 寫「超出容許帶 → 燈為黃」，相等不算超出。"""
    dataset = fixtures.scenario("full")
    _setting(dataset, "alo_tolerance_pp", 6.0)  # 核心的差距剛好是 +6.0
    model = logic.build_page_model(dataset)
    core = [r for r in _block(model, "ALO-2")["_rows"] if r["_bucket"] == fixtures.CORE][0]
    assert math.isclose(abs(core["_diff"]), 6.0, abs_tol=1e-9)
    assert core["band_text"] == "內"
    assert _block(model, "ALO-0")["_tone"] == "灰"
    assert _block(model, "ALO-0")["text"] == "各類別皆在容許帶內"
    # 正控：比端點再小一點就超出。
    _setting(dataset, "alo_tolerance_pp", 5.9)
    assert _block(logic.build_page_model(dataset), "ALO-0")["_tone"] == "黃"


def _two_bucket_dataset(tolerance):
    """兩類別、目標合計 1：目前比重必然一正一負、絕對值相同（±d）。"""
    dataset = fixtures.scenario("full")
    dataset["holding"] = [h for h in dataset["holding"] if h["bucket"] != fixtures.CASH]
    _setting(dataset, "alo_bucket_names", [fixtures.SATELLITE, fixtures.CORE])
    _setting(dataset, "alo_target_weights", [
        {"bucket": fixtures.CORE, "weight_ratio": 0.6},
        {"bucket": fixtures.SATELLITE, "weight_ratio": 0.4},
    ])
    _setting(dataset, "alo_tolerance_pp", tolerance)
    return dataset


def test_同差並列_帶外時燈黃_依類別名稱順序全列_不炸():
    """登記 `ALO-GAP-同差並列`：帶外並列點名方式 44 未寫，本頁全列，依 `alo_bucket_names` 順序。"""
    model = logic.build_page_model(_two_bucket_dataset(4.0))
    rows = [r for r in _block(model, "ALO-2")["_rows"] if r["_diff"] is not None]
    assert len(rows) == 2
    assert math.isclose(rows[0]["_diff"], -rows[1]["_diff"], abs_tol=1e-9)
    lamp = _block(model, "ALO-0")
    d = abs(rows[0]["_diff"])
    assert lamp["_tone"] == "黃"
    assert lamp["text"] == f"{fixtures.SATELLITE}、{fixtures.CORE} 與目標差 {d:.1f} 個百分點"


def test_同差並列_帶內時照44寫各類別皆在容許帶內():
    model = logic.build_page_model(_two_bucket_dataset(20.0))
    lamp = _block(model, "ALO-0")
    assert lamp["_tone"] == "灰" and lamp["text"] == "各類別皆在容許帶內"


def test_全部差0時燈灰_各類別皆在容許帶內():
    dataset = fixtures.scenario("full")
    _setting(dataset, "alo_target_weights", [
        {"bucket": fixtures.CORE, "weight_ratio": 0.66},
        {"bucket": fixtures.SATELLITE, "weight_ratio": 0.29},
        {"bucket": fixtures.CASH, "weight_ratio": 0.05},
    ])
    model = logic.build_page_model(dataset)
    assert all(math.isclose(r["_diff"], 0.0, abs_tol=1e-9) for r in _block(model, "ALO-2")["_rows"])
    lamp = _block(model, "ALO-0")
    assert lamp["_tone"] == "灰" and lamp["text"] == "各類別皆在容許帶內"


def test_ALO0三句兩兩相撞_持倉空與目標未設_取持倉空():
    dataset = fixtures.scenario("noholding")
    _setting(dataset, "alo_target_weights", None)
    assert _block(logic.build_page_model(dataset), "ALO-0")["text"] == "尚未建立任何持倉"


def test_ALO0三句兩兩相撞_持倉空與容許帶未設_取持倉空():
    dataset = fixtures.scenario("noholding")
    _setting(dataset, "alo_tolerance_pp", None)
    assert _block(logic.build_page_model(dataset), "ALO-0")["text"] == "尚未建立任何持倉"


def test_ALO0三句兩兩相撞_目標未設與容許帶未設_取目標未設():
    dataset = fixtures.scenario("notarget")
    _setting(dataset, "alo_tolerance_pp", None)
    assert _block(logic.build_page_model(dataset), "ALO-0")["text"] == "尚未設定目標"


# ═════════════════════ 七、ALO-1 目標輸入卡 ═════════════════════


def test_ALO1判準a_首次開啟目標列數為零且卡上沒有任何比重數字():
    card = _block(_model("first"), "ALO-1")
    assert card["_rows"] == []
    text = "".join(logic.collect_ui_strings(card))
    assert not re.search(r"\d\.\d|\d%", text), text


def test_ALO1判準b_合計0點9_卡上出現合計與差額而各列未被改寫():
    dataset = fixtures.scenario("full")
    _setting(dataset, "alo_target_weights", [
        {"bucket": fixtures.CORE, "weight_ratio": 0.5},
        {"bucket": fixtures.SATELLITE, "weight_ratio": 0.3},
        {"bucket": fixtures.CASH, "weight_ratio": 0.1},
    ])
    model = logic.build_page_model(dataset)
    card = _block(model, "ALO-1")
    assert card["sum_lines"] == ["合計 0.9", "差額 -0.1"]
    assert [r["weight_text"] for r in card["_rows"]] == ["0.5", "0.3", "0.1"]
    assert model["top_lines"] == ["目標合計 90%"]


def test_ALO1判準_合計改回1那一行灰字消失():
    model = _model("full")
    assert model["top_lines"] == []
    assert _block(model, "ALO-1")["sum_lines"] == []


def test_ALO1某列比重留空_該列不計入合計且列尾資料未備():
    card = _block(_model("partial"), "ALO-1")
    blank = [r for r in card["_rows"] if r["_weight"] is None]
    assert len(blank) == 1
    assert blank[0]["tail_text"] == "⬜ 資料未備"
    assert card["sum_lines"][0] == "合計 0.9"
    assert _model("partial")["top_lines"] == ["目標合計 90%"]


def test_ALO1判準_說明文字在目標列數為零時照樣在畫面上():
    for name in fixtures.ALL_SCENARIO_NAMES:
        assert _block(_model(name), "ALO-1")["intro_line"] == "以下依序：目標 → 對照 → 試算"


def test_ALO1只掛一枚存檔_同時寫兩鍵():
    card = _block(_model("full"), "ALO-1")
    assert [(b["label"], b["_action_kind"]) for b in card["buttons"]] == [("存檔", "存檔")]
    assert card["buttons"][0]["_writes"] == {"user_setting"}
    assert card["buttons"][0]["_keys"] == ("alo_target_weights", "alo_tolerance_pp")


def test_ALO1_user_setting改值後重建模型_輸入欄讀出的是新的已存值():
    """⚠️ 本頁沒有後端，驗不到「按存檔真的寫進去」。本條驗的是讀的那一半：
    `user_setting` 那兩鍵換成新值（＝存檔後的樣子）再建模型，輸入欄讀出的就是新值、`updated_at` 非空。"""
    dataset = fixtures.scenario("full")
    new_targets = [{"bucket": fixtures.CORE, "weight_ratio": 0.7}, {"bucket": fixtures.CASH, "weight_ratio": 0.3}]
    for row in dataset["user_setting"]:
        if row["setting_key"] == "alo_target_weights":
            row["setting_value"], row["updated_at"] = new_targets, "2026-09-24T03:00:00Z"
        if row["setting_key"] == "alo_tolerance_pp":
            row["setting_value"], row["updated_at"] = 2.5, "2026-09-24T03:00:00Z"
    card = _block(logic.build_page_model(dataset), "ALO-1")
    values = [f["_value"] for f in card["inputs"]]
    assert values == [fixtures.CORE, 0.7, fixtures.CASH, 0.3, 2.5]
    assert card["tolerance_text"] == "2.5"
    for key in ("alo_target_weights", "alo_tolerance_pp"):
        assert logic.setting_updated_at(dataset, key)


def test_ALO1存檔寫入失敗_訊息原文照印_輸入留著_ALO2與ALO3數值不變():
    ok, failed = _model("full"), _model("full", save_failed=True)
    card = _block(failed, "ALO-1")
    assert card["error_lines"] == ["存檔寫入失敗：" + fixtures.SAVE_FAIL_MESSAGE]
    assert [f["_value"] for f in card["inputs"]] == [f["_value"] for f in _block(ok, "ALO-1")["inputs"]]
    for code in ("ALO-2", "ALO-3"):
        assert _block(failed, code)["_rows"] == _block(ok, code)["_rows"], code
    assert _block(ok, "ALO-1")["error_lines"] == []


def test_ALO1目標未設時卡上寫未設定():
    card = _block(_model("notarget"), "ALO-1")
    assert "⬜ 未設定" in card["unset_lines"]


# ═════════════════════ 八、ALO-2 目標對照卡 ═════════════════════


def test_ALO2四欄欄名():
    assert _block(_model("full"), "ALO-2")["column_labels"] == ["類別", "目前比重", "目標比重", "差額", "容許帶內外"]


def test_ALO2全齊時三列的算術():
    rows = {r["_bucket"]: r for r in _block(_model("full"), "ALO-2")["_rows"]}
    assert rows[fixtures.CORE]["current_text"] == "66.0%"
    assert rows[fixtures.CORE]["target_text"] == "60.0%"
    assert rows[fixtures.CORE]["diff_text"] == "+6.0 pp"
    assert rows[fixtures.CORE]["band_text"] == "外"
    assert rows[fixtures.SATELLITE]["diff_text"] == "-1.0 pp"
    assert rows[fixtures.SATELLITE]["band_text"] == "內"
    assert rows[fixtures.CASH]["diff_text"] == "-5.0 pp"
    assert rows[fixtures.CASH]["band_text"] == "外"


def test_ALO2判準_清空某檔bucket_出現未分類一列且檔數為1():
    card = _block(_model("unbkt"), "ALO-2")
    buckets = [r["_bucket"] for r in card["_rows"]]
    assert logic.UNCLASSIFIED in buckets
    assert "未分類 1 檔" in card["tail_lines"]


def test_ALO2判準_差額欄字元集合只有數字小數點正負號與百分點符號():
    checked = 0
    for name, _s in _every_case():
        for row in _block(_model(name), "ALO-2")["_rows"]:
            text = row["diff_text"]
            if row["_diff"] is None:
                continue
            assert re.fullmatch(r"[+-]\d+\.\d pp", text), (name, text)
            assert not (set(text) - set("0123456789.+- p")), text
            checked += 1
    assert checked >= 40, checked


def test_ALO2判準_市值基準而沒有任何匯率_含外幣的類別資料未備_不以1硬算():
    card = _block(_model("nofx"), "ALO-2")
    rows = {r["_bucket"]: r for r in card["_rows"]}
    for bucket in (fixtures.CORE, fixtures.SATELLITE):  # 各含一檔 USD
        assert rows[bucket]["current_text"] == "⬜ 資料未備：缺換算匯率 fx_twd_per_usd"
        assert rows[bucket]["_current_pct"] is None
    # 其餘類別照算，並在卡上註明合計未涵蓋該類。
    assert rows[fixtures.CASH]["current_text"] == "100.0%"
    assert any(line.startswith("合計未涵蓋") and fixtures.CORE in line for line in card["tail_lines"])


def test_ALO2部分類別缺基準值_有值的類別照判內外_缺值的類別寫資料未備_不整張不判():
    """客戶 2026-10-16 裁示（ALO-GAP-部分缺的內外判讀，已裁結案）：有基準值的類別照常判斷帶內／帶外，
    缺基準值的類別顯示「⬜ 資料未備」；不要因一個缺值就整張都不判。
    `nofx` 情境：核心、衛星各含一檔外幣 ⇒ 缺換算匯率；現金只有新臺幣 ⇒ 有值。"""
    card = _block(_model("nofx"), "ALO-2")
    assert card["placeholder"] is None                         # 不是整張空狀態
    rows = {r["_bucket"]: r for r in card["_rows"]}
    valued = [r for r in card["_rows"] if r["_current_pct"] is not None]
    missing = [r for r in card["_rows"] if r["_current_pct"] is None]
    assert valued and missing                                   # 前提：真的是「部分缺」
    for row in valued:
        assert row["band_text"] in ("內", "外"), row
        assert row["_diff"] is not None, row
    for row in missing:
        assert row["current_text"].startswith("⬜ 資料未備"), row
        assert row["band_text"] == "⬜", row                    # 內外格維持兩字限制內的「⬜」（44 ALO-2）
    assert rows[fixtures.CASH] in valued
    assert any(line.startswith("合計未涵蓋") for line in card["tail_lines"])


def test_ALO2判準_目標合計0點9_每一列差額仍是當前減目標_不先歸一():
    dataset = fixtures.scenario("full")
    _setting(dataset, "alo_target_weights", [
        {"bucket": fixtures.CORE, "weight_ratio": 0.5},
        {"bucket": fixtures.SATELLITE, "weight_ratio": 0.3},
        {"bucket": fixtures.CASH, "weight_ratio": 0.1},
    ])
    card = _block(logic.build_page_model(dataset), "ALO-2")
    for row in card["_rows"]:
        assert math.isclose(row["_diff"], row["_current_pct"] - row["_target_pct"], abs_tol=1e-9)
    core = [r for r in card["_rows"] if r["_bucket"] == fixtures.CORE][0]
    assert core["diff_text"] == "+16.0 pp"  # 66 − 50，而不是 66 − 50/0.9
    assert card["column_labels"].count("差額") == 1


def test_ALO2市值基準取不晚於淨值日的最近一筆匯率():
    """`44` ALO-2 來源欄逐字「取 `obs_date` 不晚於 `nav.nav_date` 的最近一筆」。"""
    dataset = fixtures.scenario("mvbasis")
    assert logic.fx_for_date(dataset, fixtures.NAV_DATE) == fixtures.FX_USED
    rows = {r["_bucket"]: r for r in _block(logic.build_page_model(dataset), "ALO-2")["_rows"]}
    core_value = 1000 * 15.20 * 32.00 + 10000 * 21.50
    total = core_value + 3000 * 3.10 * 32.00 + 5000 * 10.01
    assert math.isclose(rows[fixtures.CORE]["_current_pct"], core_value / total * 100, rel_tol=1e-12)


def test_ALO2目標未設時整卡不適用():
    card = _block(_model("notarget"), "ALO-2")
    assert card["_rows"] == []
    assert card["placeholder"]["text"] == "⬜ 不適用：尚未設定目標"


def test_ALO2基準未選時整卡不適用():
    card = _block(_model("nobasis"), "ALO-2")
    assert card["_rows"] == []
    assert card["placeholder"]["text"] == "⬜ 不適用：尚未選定比重基準"


def test_ALO2持倉表為空時是來源缺_嚴重度高於算不出來():
    card = _block(_model("first"), "ALO-2")
    assert card["placeholder"]["text"] == "⬜ 資料未備：holding 尚無資料"
    assert card["placeholder"]["_empty_kind"] == "來源缺"
    assert not [b for b in card["buttons"] if b["_action_kind"] == "取數"]


def test_ALO2容許帶未設時內外欄未設定_差額照算():
    rows = _block(_model("notol"), "ALO-2")["_rows"]
    assert rows and all(r["band_text"] == "⬜ 未設定" for r in rows)
    assert all(r["_diff"] is not None for r in rows)


def test_ALO2未分類那一列沒有目標_三格不填數字():
    row = [r for r in _block(_model("unbkt"), "ALO-2")["_rows"] if r["_bucket"] == logic.UNCLASSIFIED][0]
    assert row["_target_pct"] is None and row["_diff"] is None
    assert row["target_text"].startswith("⬜") and row["diff_text"].startswith("⬜")


def test_ALO2內外欄不著色():
    for row in _block(_model("full"), "ALO-2")["_rows"]:
        assert row["_band_tone"] == "中性"


def test_ALO2類別一個也沒定義時每一檔併入未分類():
    card = _block(_model("nobucket"), "ALO-2")
    unc = [r for r in card["_rows"] if r["_bucket"] == logic.UNCLASSIFIED][0]
    assert unc["current_text"] == "100.0%"
    assert "未分類 4 檔" in card["tail_lines"]


def test_ALO2寫明讀的是已存值():
    """登記 `ALO-GAP-當下值或已存值`（`44` 塊下方「其二」）：本頁取已存值，畫面上寫出來。"""
    assert any("已存值" in line for line in _block(_model("full"), "ALO-2")["detail_lines"])


# ═════════════════════ 九、ALO-3 情境試算卡 ═════════════════════


def test_ALO3判準a_首次開啟試算輸入列數為零且卡上沒有任何金額數字():
    card = _block(_model("first"), "ALO-3")
    assert card["input_rows"] == [] and card["_rows"] == []
    assert not re.search(r"\d", re.sub(r"ALO-\d", "", "".join(logic.collect_ui_strings(card))))


def test_ALO3輸入一列也沒有時_提示文字與一枚新增假設():
    dataset = fixtures.scenario("full")
    _setting(dataset, "alo_scenario_input", None)
    card = _block(logic.build_page_model(dataset), "ALO-3")
    kinds = [(b["label"], b["_action_kind"]) for b in card["buttons"]]
    assert ("新增假設", "新增列") in kinds
    assert card["_rows"] == []
    assert card["unset_lines"] == ["⬜ 未設定"]


def test_ALO3判準b_負向金額超出現值_該列不適用而其餘列照算():
    card = _block(_model("partial"), "ALO-3")
    tails = [r["tail_text"] for r in card["input_rows"]]
    assert "⬜ 不適用：假設金額超出該類別現值" in tails
    assert "⬜ 資料未備" in tails
    assert card["_rows"], "其餘列要照算"


def test_ALO3試算算術():
    """衛星 +100,000、現金 +50,000，總額 1,150,000。"""
    rows = {r["_bucket"]: r for r in _block(_model("full"), "ALO-3")["_rows"]}
    assert math.isclose(rows[fixtures.SATELLITE]["_share_pct"], 390000 / 1150000 * 100)
    assert math.isclose(rows[fixtures.CASH]["_share_pct"], 100000 / 1150000 * 100)
    assert math.isclose(rows[fixtures.CORE]["_share_pct"], 660000 / 1150000 * 100)
    assert rows[fixtures.CORE]["new_diff_text"] == f"{660000 / 1150000 * 100 - 60:+.1f} pp"


def test_ALO3目標未設時不適用尚未設定目標():
    assert _block(_model("notarget"), "ALO-3")["placeholder"]["text"] == "⬜ 不適用：尚未設定目標"


def test_ALO3卡上不排先動哪一個_結果列照ALO2的類別順序():
    model = _model("full")
    assert [r["_bucket"] for r in _block(model, "ALO-3")["_rows"]] == [
        r["_bucket"] for r in _block(model, "ALO-2")["_rows"]
    ]


def test_ALO3存檔寫一鍵_寫入失敗時輸入與試算結果不變():
    ok, failed = _model("full"), _model("full", save_failed=True)
    card = _block(failed, "ALO-3")
    save = [b for b in card["buttons"] if b["_action_kind"] == "存檔"]
    assert len(save) == 1 and save[0]["_keys"] == ("alo_scenario_input",)
    assert card["error_lines"] == ["存檔寫入失敗：" + fixtures.SAVE_FAIL_MESSAGE]
    assert card["_rows"] == _block(ok, "ALO-3")["_rows"]
    assert card["input_rows"] == _block(ok, "ALO-3")["input_rows"]


def test_ALO3金額逐格標新臺幣():
    for row in _block(_model("full"), "ALO-3")["input_rows"]:
        assert row["amount_text"].endswith(" TWD")


def test_ALO3試算類別不在清單_該列不適用而其餘列照算_不整頁炸():
    """登記 `ALO-GAP-ALO3類別不在清單`。"""
    dataset = fixtures.scenario("full")
    _setting(dataset, "alo_scenario_input", [
        {"bucket": "拼錯的類別", "amount_twd": 1000},
        {"bucket": fixtures.CASH, "amount_twd": 50000},
    ])
    card = _block(logic.build_page_model(dataset), "ALO-3")
    assert card["input_rows"][0]["tail_text"] == logic.TEXT_NA_UNKNOWN_BUCKET
    assert card["input_rows"][0]["_effective"] is False
    assert card["input_rows"][1]["_effective"] is True
    assert card["_rows"]


def test_ALO3試算後總額為零_卡上不適用_不出任何比重_不整頁炸():
    """登記 `ALO-GAP-試算總額`。"""
    dataset = fixtures.scenario("full")
    _setting(dataset, "alo_scenario_input", [
        {"bucket": fixtures.CORE, "amount_twd": -660000},
        {"bucket": fixtures.SATELLITE, "amount_twd": -290000},
        {"bucket": fixtures.CASH, "amount_twd": -50000},
    ])
    card = _block(logic.build_page_model(dataset), "ALO-3")
    assert card["placeholder"]["text"] == logic.TEXT_NA_ZERO_TOTAL
    assert card["_rows"] == []


# ═════════════════════ 十、ALO-4 分組定義 ═════════════════════


def _buttons_of(model, code):
    return [(b["label"], b["_action_kind"]) for b in _block(model, code)["buttons"]]


def test_ALO4導覽鈕持倉表空或不空都出現():
    """`44` ALO-4 規則欄與判準新兩步（2026-09-24 第二十一輪客戶裁示）。⚠️ 線框缺空持倉那一種，照 `44`。
    holding 取數失敗（空或不空不知道）也照掛（登記 `ALO-GAP-失敗時導覽鈕`）。"""
    goto = (logic.TEXT_GOTO_SHEETS, "導覽")
    kinds = set()
    for name, save_failed in _every_case():
        model = _model(name, save_failed=save_failed)
        dataset = fixtures.scenario(name)
        assert goto in _buttons_of(model, "ALO-4"), (name, save_failed)
        kinds.add("fail" if dataset["errors"].get("holding") else ("empty" if not dataset["holding"] else "rows"))
    # 三種都真的走到：持倉表為空、有資料、holding 取數失敗。
    assert kinds == {"empty", "rows", "fail"}, kinds


def test_ALO4持倉表空或不空都兩枚並存():
    for name in ("first", "full", "holdfail"):
        assert _buttons_of(_model(name), "ALO-4") == [(logic.TEXT_GOTO_SHEETS, "導覽"), ("存檔", "存檔")], name


def test_ALO4導覽鈕下方那一行說明逐字():
    for name in ("first", "full"):
        assert _block(_model(name), "ALO-4")["goto_note"] == "持倉資料在 Sheets 維護，本儀表板唯讀", name


def test_ALO4判準_導覽與存檔都不寫holding():
    for button in _block(_model("first"), "ALO-4")["buttons"]:
        assert "holding" not in button["_writes"]
    goto = _block(_model("first"), "ALO-4")["buttons"][0]
    assert goto["_writes"] == set()
    for button in _block(_model("full"), "ALO-4")["buttons"]:
        assert "holding" not in button["_writes"]


def test_ALO4判準_切換比重基準_ALO2目前比重改變而目標比重不變():
    cost = {r["_bucket"]: r for r in _block(_model("full"), "ALO-2")["_rows"]}
    mv = {r["_bucket"]: r for r in _block(_model("mvbasis"), "ALO-2")["_rows"]}
    assert cost[fixtures.CORE]["current_text"] != mv[fixtures.CORE]["current_text"]
    for bucket in cost:
        assert cost[bucket]["target_text"] == mv[bucket]["target_text"]


def test_ALO4判準_取消某檔指派_出現在未指派清單且ALO2未分類加1():
    model = _model("unbkt")
    block = _block(model, "ALO-4")
    assert any(fixtures.UNBUCKETED_FUND in line for line in block["unassigned_lines"])
    assert "未分類 1 檔" in _block(model, "ALO-2")["tail_lines"]
    assert _block(_model("full"), "ALO-4")["unassigned_lines"] == []


def test_ALO4判準_指派欄是唯讀_輸入元件只有基準與類別名稱():
    """本塊的輸入元件逐一點名：一個基準二選一 ＋ 每個類別名稱一格。沒有任何一格對應到某一檔。"""
    for name in ("full", "unbkt", "nobucket"):
        block = _block(_model(name), "ALO-4")
        names = [f["name"] for f in block["inputs"]]
        expected = ["alo_basis"] + [f"alo_bucket_name_{i}" for i in range(len(logic.setting_value(fixtures.scenario(name), "alo_bucket_names") or ()))]
        assert names == expected, (name, names)
        codes = {h["fund_code"] for h in fixtures.scenario(name)["holding"]}
        for field in block["inputs"]:
            assert not any(code in field["name"] or code in field["label"] for code in codes)
        assert len(block["_assign_rows"]) == 4
        assert all(r["_readonly"] is True for r in block["_assign_rows"])


def test_ALO4卡上明寫目前用的是哪一個基準():
    assert _block(_model("full"), "ALO-4")["basis_line"] == "目前基準：成本（cost_twd）"
    assert "市值" in _block(_model("mvbasis"), "ALO-4")["basis_line"]
    assert _block(_model("nobasis"), "ALO-4")["basis_line"] == "目前基準：⬜ 未設定"


def test_ALO4市值基準缺匯率_不自動退回成本():
    block = _block(_model("nofx"), "ALO-4")
    assert "⬜ 資料未備：缺換算匯率" in block["detail_lines"]
    assert "市值" in block["basis_line"]


def test_ALO4存檔寫兩鍵_寫入失敗時當下值留著():
    ok, failed = _model("full"), _model("full", save_failed=True)
    block = _block(failed, "ALO-4")
    save = [b for b in block["buttons"] if b["_action_kind"] == "存檔"][0]
    assert save["_keys"] == ("alo_basis", "alo_bucket_names")
    assert block["error_lines"] == ["存檔寫入失敗：" + fixtures.SAVE_FAIL_MESSAGE]
    assert [f["_value"] for f in block["inputs"]] == [f["_value"] for f in _block(ok, "ALO-4")["inputs"]]
    assert _block(failed, "ALO-2")["_rows"] == _block(ok, "ALO-2")["_rows"]


# ═════════════════════ 十一、ALO-5 試算結果匯出 ═════════════════════


def _export_labels(text):
    rows = list(csv.reader(io.StringIO(text)))
    return rows


def test_ALO5判準_匯出檔欄名集合與畫面欄名集合相同():
    model = _model("full")
    block = _block(model, "ALO-5")
    rows = _export_labels(block["_export_text"])
    screen = set(_block(model, "ALO-2")["column_labels"]) | set(_block(model, "ALO-3")["column_labels"])
    headers = set()
    for row in rows:
        if row and row[0] == "類別":
            headers |= set(row)
    assert headers == screen


def test_ALO5判準_匯出前後holding與user_setting列數相同_而且不改資料():
    dataset = fixtures.scenario("full")
    before = copy.deepcopy(dataset)
    logic.build_page_model(dataset)
    assert dataset == before
    assert len(dataset["holding"]) == len(before["holding"])
    assert len(dataset["user_setting"]) == len(before["user_setting"])


def test_ALO5匯出內容與畫面上的列逐格相同():
    model = _model("full")
    rows = _export_labels(_block(model, "ALO-5")["_export_text"])
    alo2 = _block(model, "ALO-2")
    body = [r for r in rows if r and r[0] in {x["bucket_text"] for x in alo2["_rows"]}]
    screen = [[x["bucket_text"], x["current_text"], x["target_text"], x["diff_text"], x["band_text"]]
              for x in alo2["_rows"]]
    assert body[: len(screen)] == screen


def test_ALO5畫面上無列時按鈕停用_原因逐字():
    button = _block(_model("notarget"), "ALO-5")["buttons"][0]
    assert button["_action_kind"] == "匯出"
    assert button["_enabled"] is False
    assert button["disabled_reason"] == "目前沒有可匯出的列"
    assert _block(_model("full"), "ALO-5")["buttons"][0]["_enabled"] is True


def test_ALO5未試算時匯出只含ALO2並在檔首註明未含試算():
    dataset = fixtures.scenario("full")
    _setting(dataset, "alo_scenario_input", None)
    text = _block(logic.build_page_model(dataset), "ALO-5")["_export_text"]
    first = text.splitlines()[0]
    assert first == "未含試算"
    assert "試算後比重" not in text


# ═════════════════════ 十二、ALO-6 歸屬明細 ═════════════════════


def test_ALO6判準_表尾總體佔比合計顯示為1():
    block = _block(_model("full"), "ALO-6")
    assert "總體佔比合計 1" in block["footer_lines"]
    assert len(block["_rows"]) == 4


def test_ALO6判準_抽掉某檔基準值_該列空方塊_表尾寫被排除檔數_兩個合計仍為1():
    block = _block(_model("nofx"), "ALO-6")
    missing = [r for r in block["_rows"] if r["_value"] is None]
    assert len(missing) == 2
    assert all(r["value_text"].startswith("⬜") for r in missing)
    assert "被排除 2 檔" in block["footer_lines"]
    assert "總體佔比合計 1" in block["footer_lines"]
    subtotal_lines = [line for line in block["footer_lines"] if line.startswith("類別內佔比合計")]
    assert len(subtotal_lines) == 2, block["footer_lines"]  # 核心剩一檔、現金一檔
    for line in subtotal_lines:
        assert line.endswith(" 1"), line


def test_ALO6各類別內佔比合計為1():
    block = _block(_model("full"), "ALO-6")
    sums = {}
    for row in block["_rows"]:
        sums[row["_bucket"]] = sums.get(row["_bucket"], 0.0) + row["_in_bucket"]
    for value in sums.values():
        assert math.isclose(value, 1.0, abs_tol=1e-9)


def test_ALO6無任何持倉是來源缺_不掛重新取數():
    block = _block(_model("first"), "ALO-6")
    assert block["placeholder"]["text"] == "⬜ 資料未備：holding 尚無資料"
    assert block["placeholder"]["_empty_kind"] == "來源缺"
    assert not [b for b in block["buttons"] if b["_action_kind"] == "取數"]


def test_ALO6不畫44沒有的幣別欄_保單名照來源欄():
    """登記 `ALO-GAP-ALO6幣別`：44 規則欄未列幣別欄，本頁不顯示。"""
    block = _block(_model("full"), "ALO-6")
    assert block["column_labels"] == ["基金", "保單", "類別", "基準值", "佔所屬類別", "佔總體"]
    assert "幣別" not in block["column_labels"]
    for row in block["_rows"]:
        assert "ccy_text" not in row
        assert row["policy_text"] in ("直接持有", "示意投資型保單甲")


# ═════════════════════ 十三、ALO-7 目標修改紀錄 ═════════════════════


def test_ALO7固定兩列三欄():
    block = _block(_model("full"), "ALO-7")
    assert block["column_labels"] == ["鍵名", "當前值", "最後修改時間"]
    assert [r["key_text"] for r in block["_rows"]] == ["alo_target_weights", "alo_tolerance_pp"]


def test_ALO7判準_容許帶那一列的當前值與ALO1卡上顯示的容許帶逐字相同():
    for name in ("full", "inband", "partial"):
        model = _model(name)
        row = _block(model, "ALO-7")["_rows"][1]
        assert row["value_text"] == _block(model, "ALO-1")["tolerance_text"], name
        shown = [f for f in _block(model, "ALO-1")["inputs"] if f["name"] == "alo_tolerance_pp"][0]
        assert shown["value_text"] == row["value_text"], name  # 輸入欄裡畫的也是同一個字串


def test_ALO7判準_不改任何鍵重建模型_兩列的值與時間就是user_setting那兩列():
    """重新載入＝同一份 `user_setting` 再建一次模型。本條不只比兩次模型相等，
    還對回 `user_setting` 本身（值與 `updated_at` 換算後的字串）。"""
    dataset = fixtures.scenario("full")
    a = _block(logic.build_page_model(dataset), "ALO-7")["_rows"]
    b = _block(logic.build_page_model(copy.deepcopy(dataset)), "ALO-7")["_rows"]
    assert a == b and len(a) == 2
    assert a[1]["value_text"] == "4"
    assert a[1]["time_text"] == logic.format_time(fixtures.UPDATED_AT) == "2026-09-20 14:00（UTC+8）"
    assert a[0]["value_text"] == f"{fixtures.CORE} 0.6／{fixtures.SATELLITE} 0.3／{fixtures.CASH} 0.1"


def test_ALO7判準_改一次容許帶_該列當前值與時間格跟著改而仍只有兩列():
    dataset = fixtures.scenario("full")
    for row in dataset["user_setting"]:
        if row["setting_key"] == "alo_tolerance_pp":
            row["setting_value"] = 5.5
            row["updated_at"] = "2026-09-24T02:00:00Z"
    model = logic.build_page_model(dataset)
    rows = _block(model, "ALO-7")["_rows"]
    assert len(rows) == 2
    assert rows[1]["value_text"] == "5.5" == _block(model, "ALO-1")["tolerance_text"]
    assert rows[1]["time_text"] == "2026-09-24 10:00（UTC+8）"


def test_ALO7兩鍵皆空是來源缺_文案尚未設定目標():
    block = _block(_model("first"), "ALO-7")
    assert block["placeholder"]["text"] == "尚未設定目標"
    assert block["placeholder"]["_empty_kind"] == "來源缺"
    assert block["_rows"] == []


def test_ALO7某一鍵為空_值格未設定_時間格空方塊():
    rows = _block(_model("notol"), "ALO-7")["_rows"]
    assert rows[1]["value_text"] == "⬜ 未設定"
    assert rows[1]["time_text"] == "⬜"
    assert rows[0]["value_text"] != "⬜ 未設定"


def test_ALO7有值但updated_at為空_時間格資料未備尚未設定過_值格照印():
    dataset = fixtures.scenario("full")
    for row in dataset["user_setting"]:
        if row["setting_key"] == "alo_tolerance_pp":
            row["updated_at"] = None
    rows = _block(logic.build_page_model(dataset), "ALO-7")["_rows"]
    assert rows[1]["time_text"] == "⬜ 資料未備：尚未設定過"
    assert rows[1]["value_text"] == "4"


# ═════════════════════ 十四、情境表與登記 ═════════════════════


def test_情境表與ALL_SCENARIO_NAMES不得漂移_每一個都有標籤():
    assert set(fixtures.SCENARIO_LABELS) == set(fixtures.ALL_SCENARIO_NAMES)
    for name in fixtures.ALL_SCENARIO_NAMES:
        fixtures.scenario(name)
    with pytest.raises(KeyError):
        fixtures.scenario("nope")


def test_每一個情境都建得出模型而且八塊齊全():
    for name, save_failed in _every_case():
        model = _model(name, save_failed=save_failed)
        assert [b["code"] for b in model["blocks"]] == list(logic.BLOCK_TITLES), name


def _block_has_numbers(block) -> bool:
    strings = [s for s in logic.collect_ui_strings({k: v for k, v in block.items() if k != "code"})]
    strings = [re.sub(r"ALO-\d|UTC\+8", "", s) for s in strings if s != logic.HINT_NOTE]
    return any(re.search(r"\d", s) for s in strings)


def test_示意標記_頁首一行_而且每一塊畫面上有數字的塊都有一行本塊數字皆為示意值():
    """登記 `ALO-GAP-示意標記`：實作與登記一致 —— 頁首一行涵蓋全頁，有數字的塊各一行。"""
    assert "頁首一行" in logic.GAPS["ALO-GAP-示意標記"]
    checked = 0
    for name, save_failed in _every_case():
        model = _model(name, save_failed=save_failed)
        assert model["hint_note"] == logic.PAGE_HINT_NOTE
        for block in model["blocks"]:
            if _block_has_numbers(block):
                assert logic.HINT_NOTE in block["detail_lines"], (name, block["code"])
                checked += 1
    assert checked >= 100, checked


def test_示意守衛本身會咬_負控():
    model = _model("full")
    block = copy.deepcopy(_block(model, "ALO-7"))
    assert _block_has_numbers(block)
    block["detail_lines"] = [line for line in block["detail_lines"] if line != logic.HINT_NOTE]
    assert logic.HINT_NOTE not in block["detail_lines"]


def test_缺口登記表每一筆都在原始碼裡被引用():
    """`logic.GAPS` 是本頁替 `44` 登記的缺口與矛盾；每一筆的代號都要在程式碼某處被用到，
    不然它就是一張沒有人讀的清單。"""
    assert len(logic.GAPS) >= 10
    sources = "".join(p.read_text(encoding="utf-8") for p in _ALL_SOURCE_FILES)
    for gap_id, text in logic.GAPS.items():
        assert sources.count(gap_id) >= 2, gap_id  # 定義一次 ＋ 至少一處使用
        assert len(text) >= 20, gap_id


def test_fixtures的欄位照44第四節():
    dataset = fixtures.scenario("full")
    assert set(dataset["holding"][0]) == {
        "holding_id", "policy_id", "fund_code", "fund_name", "ccy", "units_shares",
        "cost_orig_ccy", "cost_twd", "opened_on", "bucket", "last_synced_at",
    }
    assert set(dataset["nav"][0]) == {
        "fund_code", "nav_date", "nav_orig_ccy", "ccy", "source_tier", "is_estimated", "fetched_at",
    }
    assert set(dataset["market_indicator"][0]) == {
        "indicator_key", "obs_date", "release_date", "value_num", "value_unit",
        "source_tier", "is_revised", "fetched_at",
    }
    assert set(dataset["user_setting"][0]) == {"setting_key", "setting_value", "value_kind", "updated_at"}
    for row in fixtures.scenario("first")["user_setting"]:
        assert row["setting_value"] is None and row["updated_at"] is None


# ═════════════════════ 兩鍵存檔恰好一鍵失敗（客戶 2026-10-09 裁示）═════════════════════
#
# 恰好一鍵失敗 → 該鍵原位印 `44` 既有的「⛔ 取數失敗：<原文>」（`fetch_failed_text`），卡片層不再印；
# 兩鍵都失敗、或單鍵卡（ALO-3）失敗 → 卡片層「存檔寫入失敗：…」一字不變。

_PARTIAL_MSG = "HTTP 503 upstream unavailable（已遮蔽）"


def _partial(*failed_keys):
    return _model("full", save_errors={key: _PARTIAL_MSG for key in failed_keys})


@pytest.mark.parametrize("code,keys", [
    ("ALO-1", ("alo_target_weights", "alo_tolerance_pp")),
    ("ALO-4", ("alo_basis", "alo_bucket_names")),
])
def test_恰好一鍵失敗_該鍵原位印取數失敗原文_卡片層不印(code, keys):
    ok = _block(_model("full"), code)
    for failed_key in keys:
        card = _block(_partial(failed_key), code)
        assert card["key_error_lines"] == {failed_key: [logic.fetch_failed_text(_PARTIAL_MSG)]}, failed_key
        assert card["key_error_lines"][failed_key] == ["⛔ 取數失敗：" + _PARTIAL_MSG]
        assert card["error_lines"] == [], failed_key
        # 失敗的鍵維持可重新儲存：按鈕照舊可按、照舊一枚寫兩鍵（`44`：不拆成兩枚）。
        save = [b for b in card["buttons"] if b["_writes"]]
        assert len(save) == 1 and save[0]["_enabled"] and save[0]["_keys"] == keys
        assert [f["_value"] for f in card["inputs"]] == [f["_value"] for f in ok["inputs"]]
    for other in ("ALO-2", "ALO-3"):
        assert _block(_partial(keys[0]), other)["_rows"] == _block(_model("full"), other)["_rows"], other


@pytest.mark.parametrize("code,keys", [
    ("ALO-1", ("alo_target_weights", "alo_tolerance_pp")),
    ("ALO-4", ("alo_basis", "alo_bucket_names")),
])
def test_兩鍵皆失敗_維持卡片層存檔寫入失敗_不走逐鍵(code, keys):
    card = _block(_partial(*keys), code)
    assert card["error_lines"] == [logic.TEXT_SAVE_FAILED + "：" + _PARTIAL_MSG]
    assert card["key_error_lines"] == {}


def test_另一張卡的鍵失敗_不影響這一張卡():
    alo1 = _block(_partial("alo_basis"), "ALO-1")
    assert alo1["error_lines"] == [] and alo1["key_error_lines"] == {}


def test_單鍵卡ALO3失敗_照舊卡片層_沒有逐鍵欄位():
    card = _block(_partial("alo_scenario_input"), "ALO-3")
    assert card["error_lines"] == [logic.TEXT_SAVE_FAILED + "：" + _PARTIAL_MSG]
    assert "key_error_lines" not in card


def test_示範模式savefail_五鍵全失敗_畫面行為不變():
    """`?savefail=1` 五鍵全失敗 ⇒ 兩鍵卡都是「兩鍵皆失敗」，逐鍵一行都不出、卡片層照舊。"""
    model = _model("full", save_failed=True)
    for code in ("ALO-1", "ALO-3", "ALO-4"):
        card = _block(model, code)
        assert card["error_lines"] == ["存檔寫入失敗：" + fixtures.SAVE_FAIL_MESSAGE], code
        assert not card.get("key_error_lines"), code


# ═══════════ 總管 2026-10-13 裁決：淨值過期而不納入 ≠ nav 尚無資料（字面可區分，與持倉體檢頁一致；不改計算行為） ═══════════


def _mv_two_missing(not_ready_codes, days=10):
    """市值基準；前兩檔的淨值列拿掉，其中 `not_ready_codes` 標成「淨值過期而不納入」。"""
    ds = copy.deepcopy(fixtures.scenario("mvbasis"))
    codes = [h["fund_code"] for h in ds["holding"]][:2]
    ds["nav"] = [r for r in ds["nav"] if r["fund_code"] not in codes]
    ds["nav_not_ready"] = {"codes": [c for c in codes if c in not_ready_codes], "days": days}
    return ds, codes


def _alo6_rows(ds):
    return logic.find_block(logic.build_page_model(ds), "ALO-6")["_rows"]


def test_過期而不納入_與_缺淨值_ALO6理由各寫各的():
    probe, codes = _mv_two_missing(())
    stale, missing = codes
    ds, _ = _mv_two_missing({stale})
    reasons = {r["_fund_code"]: r["_reason"] for r in _alo6_rows(ds)}
    assert reasons[stale] == "⬜ 資料未備：最近淨值已超過 10 日"
    assert reasons[missing] == logic.empty_source_text(["nav"])     # 真正缺淨值：原字面一字未動
    # 計算行為不變：每一列的基準值與「兩檔都只是缺」時逐格相同。
    assert [(r["_fund_code"], r["_value"]) for r in _alo6_rows(ds)] == [
        (r["_fund_code"], r["_value"]) for r in _alo6_rows(probe)]


def test_過期字面的天數取交進來的值_不寫死():
    ds, codes = _mv_two_missing(())
    ds["nav_not_ready"] = {"codes": [codes[0]], "days": 7}
    assert {r["_fund_code"]: r["_reason"] for r in _alo6_rows(ds)}[codes[0]] == "⬜ 資料未備：最近淨值已超過 7 日"


def test_沒有nav_not_ready鍵或為空_畫面一格不變():
    ds = copy.deepcopy(fixtures.scenario("mvbasis"))
    without = copy.deepcopy(ds)
    del without["nav_not_ready"]
    assert logic.build_page_model(ds) == logic.build_page_model(without)


@pytest.mark.parametrize("bad, exc", [
    ({"codes": ["AAAA"], "days": None}, ValueError),
    ({"codes": ["AAAA"], "days": True}, ValueError),
    ({"codes": "AAAA", "days": 10}, TypeError),
    ({"codes": ["AAAA"]}, TypeError),
    (["AAAA"], TypeError),
])
def test_nav_not_ready形狀不對_raise(bad, exc):
    ds = copy.deepcopy(fixtures.scenario("mvbasis"))
    ds["nav_not_ready"] = bad
    with pytest.raises(exc):
        logic.nav_not_ready(ds)


# ═════════════════════ 客戶 2026-10-16 裁示第 7 點：黃色「不適用」改中性灰 ═════════════════════


def test_第7點_算不出來的空狀態是中性灰_文案照舊():
    """`44` 5.5 `算不出來`（文案 `⬜ 不適用：<原因>`）的顏色由黃改灰；文案一字不動（顏色不是唯一資訊）。"""
    assert _block(_model("notarget"), "ALO-2")["placeholder"] == {
        "text": logic.TEXT_NA_NO_TARGET, "_empty_kind": "算不出來", "_tone": "灰"}
    assert _block(_model("nobasis"), "ALO-2")["placeholder"] == {
        "text": logic.TEXT_NA_NO_BASIS, "_empty_kind": "算不出來", "_tone": "灰"}
    dataset = fixtures.scenario("full")
    _setting(dataset, "alo_scenario_input", [
        {"bucket": fixtures.CORE, "amount_twd": -660000},
        {"bucket": fixtures.SATELLITE, "amount_twd": -290000},
        {"bucket": fixtures.CASH, "amount_twd": -50000},
    ])
    note = _block(logic.build_page_model(dataset), "ALO-3")["placeholder"]
    assert note["_empty_kind"] == "算不出來" and note["_tone"] == "灰"
    assert note["text"].startswith("⬜ 不適用：")


def test_第7點_不適用徽章是灰_其他黃徽章與部分缺照舊是黃():
    """防改過頭：只有「不適用」改灰；`推估`／`修正過`／`部分缺`／`未定義` 與 `部分缺` 空狀態照舊是黃。"""
    assert logic.status_badge("不適用")["_tone"] == "灰"
    assert logic.status_badge("資料未備")["_tone"] == "灰"
    for text in ("推估", "修正過", "部分缺", "未定義"):
        assert logic.status_badge(text)["_tone"] == "黃", text
    assert logic._EMPTY_TONE == {"來源缺": "灰", "算不出來": "灰", "部分缺": "黃", "系統錯誤": "紅"}


@pytest.mark.parametrize("rows, tail", [
    ([{"bucket": "拼錯的類別", "amount_twd": 1000}, {"bucket": fixtures.CASH, "amount_twd": 50000}],
     logic.TEXT_NA_UNKNOWN_BUCKET),
    ([{"bucket": fixtures.CASH, "amount_twd": -10_000_000}, {"bucket": fixtures.SATELLITE, "amount_twd": 1000}],
     logic.TEXT_NA_OVERFLOW),
])
def test_第7點_ALO3列尾不適用推導的卡片色是中性灰(rows, tail):
    """列尾 `⬜ 不適用：…`（類別不在清單／假設金額超出現值）推導出的卡片色由黃改灰，
    與同卡總額為零的 `算不出來` placeholder 同色；列尾文字照舊（稽核 #974 必修 M1）。"""
    dataset = fixtures.scenario("full")
    _setting(dataset, "alo_scenario_input", rows)
    card = _block(logic.build_page_model(dataset), "ALO-3")
    tails = [r["tail_text"] for r in card["input_rows"]]
    assert tail in tails and tail.startswith("⬜ 不適用")
    assert not any(t.startswith("⬜ 資料未備") for t in tails), tails  # 不讓別的灰蓋住這一條
    assert card["placeholder"] is None
    assert card["_tone"] == "灰"
