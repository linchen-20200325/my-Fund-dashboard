# 獨立 QA 紀錄：OneBrain OB-B 最小離線切片（程式 PR 前稽核）｜2026-11-20

稽核者：fund-independent-qa（非作者；唯讀 Read／Grep／Glob；無法執行測試、查 CI 或 git 物件）
風險分級：AI 行為邊界（DEC-2026-10-16-05：至少 1 組獨立稽核）
被審 head：feat/onebrain-obb-offline，commit 7ce29b598c68959d0818e54ff917b5bab591292e（以 .git refs 核對一致）；base main 429e92c7 無法於檔案層驗證（NOT VERIFIED）
獨立性限制：與主 session 共享派工來源，不等同人類層級獨立

## 結論：Must-Fix 0；Should-Fix 6；Nit 8
程式碼層未發現禁止項、硬矛盾或會觸發既有守衛之處。

## FACT
- 白名單：services/onebrain/ 恰 4 個 .py；tests/test_onebrain_* 恰 3 個；行數合計 12+129+26+90+669+375+302 = 1603，與作者宣稱吻合；「僅新增、未動既有檔」無法驗（無 git diff 能力），無矛盾證據。
- 禁止項：4 個程式檔 import 僅 __future__／abc／dataclasses／enum／typing 與絕對 services.onebrain 自引；無 I/O、時間、隨機、logging、環境變數、網路、金鑰、prompt、Digest、UI、SDK；型別欄位不含 token usage／cost／trace／confidence／action／Risk Cap／configuration policy／structured-output capability。
- FAKE 隔離：名稱 FAKE-OFFLINE-PROVIDER、is_fake=True、固定標記含「FAKE」「非 AI 分析」；失敗路徑亦標 FAKE（ProviderFailure.is_fake 為作者新增，Gate 卡未列，也不在禁列）。
- 離線守衛：AST import 白名單、BANNED_NAMES／ATTRS、金鑰樣式 regex、38 條變異負控與 8 條乾淨對照呼叫同一偵測函式（非同義反覆）；孤立性守衛涵蓋 31 種正對照匯入形式（import／as／from／from services import onebrain／屬性存取／importlib／__import__／sys.modules 下標／相對匯入依檔案位置解析），無法解析之檔 fail-closed。
- 豁免區與 Gate 卡字面一致：頂層 tests/ 與 services/onebrain/；相似名稱不豁免。
- 型別驗證：空字串／錯型別／bool 冒充 int／NaN／零或負 timeout／負 retries／kind 非 Enum 皆 raise；ProviderOutcome 恰一者非空。
- L2 純度守衛（7 條規則）靜態推演不會觸發，「不需改守衛」成立；ssot_3a_333／audit_20260805_*／retired_exception_ids 推演不觸發。
- docstring 無「已驗收」「production 可用」宣稱。

## Should-Fix
- SF-1 測試中「核准的欄位集合／核准清單」措辭與 DEC 計法註「未經使用者逐項核准」不一致；PR 描述須明揭欄位清單與 ProviderFailure.is_fake 為本批設計。
- SF-2 offline_guard 的盲區自陳不完整（變數別名、sys.modules.get、檔案路徑載入器、exec／eval 字串、目錄名排除任何深度、.claude/worktrees 整棵跳過、非 .py 檔）。
- SF-3 頂層 tests/ 整體豁免（Gate 卡字面）意味任何頂層測試可 import services.onebrain；收緊為比 Gate 卡更嚴，屬客戶／總管決定。
- SF-4 FORBIDDEN_OUTPUT_WORDS 內「無法判定」是 Gate 卡 §3-6 待定歧義；移除或標「作者暫定，待總管確認」。
- SF-5 test_services_purity_whitelist_would_also_accept_every_package_import 未讀 ALLOWED_IMPORTS，名稱宣稱「交叉核對」過強；更名或實際比對。
- SF-6 PR 描述須明揭：測試位置採 Gate 卡預設（DEC 要求確認）；fast lane「9 failed／48 errors」為環境判斷，CI 為裁判；QA 未見任何測試輸出。

## Nit
N-1 金鑰 regex 兩條（gh[pousr]_、xox）無對應變異。N-2 禁用詞比對區分大小寫。N-3 timeout_seconds 接受 inf。N-4 text／input_text 允許空字串。N-5 守衛 docstring「負控只活在測試內，不寫進任何文件」說法過強。N-6 白名單斷言只看 *.py。N-7 全 repo 掃描多次執行之時間成本待 CI 觀察。N-8 區域變數名為 services 時屬性偵測只會多報。

## NOT VERIFIED
所有測試實際結果；base 與 git diff；pre-commit 實跑；全 repo 無其他 importer（單組字面搜尋）；孤立性掃描在 CI 全 repo 是否因無法解析檔誤紅；Change Gate；全稱句單組未驗。

## 開 PR 條件
程式與測試層面無 Must-Fix，可開 PR（PR 描述須處理 SF-1、SF-6）。治理前置仍須：稽核紀錄所列 SF-1／SF-2／N 措辭項於白名單核對時處理；白名單核對含測試位置確認；Model／Mode／Effort Change Gate；全部 CI 成功。本紀錄不授權程式 PR。

---

## 處置狀態（入庫時附記；2026-11-20；以上為逐字原文，本節為執行組事後補記）

- Must-Fix：0。
- 已於 commit `9ed8529d`（PR #1294）處置：SF-1、SF-2、SF-4、SF-5、N-1、N-2、N-3、N-5。
- 保留不改：SF-3（頂層 `tests/` 整體豁免為 Gate 卡字面；是否收緊屬客戶／總管決定）。
- 已於 PR 描述揭露：SF-6。
- 僅以 docstring 標註、未改行為：N-4、N-6、N-7、N-8。
- 本節為執行組補記，未經第二組複驗；處置結果以 PR #1294 的 exact-head 與 CI 為準。本紀錄不授權程式 PR、不構成合併授權。
