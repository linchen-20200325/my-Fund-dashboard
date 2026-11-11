# 2026-11-11｜基金 New UI2 雙模式六項裁示 G1～G6（均選 A）

## 來源與 provenance

客戶 2026-11-11 六項裁示（G1～G6，均選 A）經 ChatGPT 對話轉達，repo 內無逐字存檔、不可獨立核對；內容為要點轉述，轉達人：ChatGPT 協作助手；單組整理，未經第二組驗證；客戶可推翻。不虛構引文；八項前置見 `docs/evidence/decisions/2026-11-11_new_ui2_dual_theme_t1_t5_ruling.md`，PoC 結果見 `docs/evidence/fund_newui2_dual_theme_poc_evidence_2026_11_11.md`（本批不改其數字）。正式登記：`DEC-2026-11-11-03`。

## 六項裁示

| Gate | 裁示 | 射程 |
|---|---|---|
| G1 正式深色色票 | **不核准** | PoC 色票、PoC 專用變體、紅／黃深色候選仍只是研究／測試候選，不得成為正式 token |
| G2 偏好保存 | **維持 session-only** | 不得使用 localStorage／cookie、JS、custom component、帳號設定、跨裝置同步；不得宣稱永久記住 |
| G3 切換入口 | **等 ⚙️ 設定頁** | 設定頁須另走設計／施工 Gate；不得新增入口、空殼設定頁、第六頁 |
| G4 原生 popover 小字 | **4.16:1 不接受為正式 PASS** | PoC 發現保留；正式驗收一般小字須 4.5:1；不得把未解問題記成成功；不得未授權以脆弱 CSS／JS 硬修；側欄功能性邊框 ＜3:1 仍列為風險 |
| G5 視覺方向 | 淺色模式＝淺色主內容＋深色側欄；深色模式＝深色主內容＋深色側欄 | **視覺方向裁示，不是施工授權** |
| G6 其他 | 12→13px 併下一個適當已授權 UI 批；`grey`／`neutral` 延後；G7 待正式 dark 實作＋非作者 QA 後且另行授權 | 本批皆未執行 |

## 授權與不授權

- **授權**：僅文件登記。
- **不授權**：任何 UI／Runtime 施工；改 `ui_v3`／`config.toml`／`ui_v2`／正式入口／`poc/`／tests；正式 dark token；任何偏好保存；新增入口或設定頁；G7 驗收。正式 dark 實作須另立 DEC／Gate。

## supersede 範圍

- `DEC-2026-10-27-09`（淺色主內容＋深色側欄）：仍為淺色模式與現行產品的契約；**只就未來深色模式的主內容方向**被 G5 取代，非整份取代。
- `DEC-2026-11-11-02`：T1～T5、V1～V3 除 G1／G2／G3／G6 的重申與具體化外不變；G4、G5 為新增。

## 未決與未驗證

- NOT RUN／NOT VERIFIED：Cloud／WebView／真機／螢幕閱讀器／其他瀏覽器／持久化／Streamlit 1.59.1／真實 `ui_v3` 頁。
- PoC 的 9 項既有測試失敗（於乾淨 main 相同）根因仍未驗證，不得稱已解決。
- #1212 最終 head 上 informational Slow／Visual lane 因 runner apt-DNS 失敗而 NOT RUN，不是 PASS。
- BL-0545 仍全域唯一 NEXT；Coverage／Digest／OneBrain 唯讀缺口稽核與靜默巡航根因治理批次仍延後。
