# PROJECT_RULES／docs/v2/81 被取代片段（歷史；2026-11-03）

> ⛔ **NOT CURRENT — Historical evidence only — not current contract.** 本檔是 2026-11-03 Canonical Rule Convergence 批從現行區**逐字搬出**的舊內容（客戶 2026-11-03 指示；`DEC-2026-11-03-08`）。**不得作為 implementation authority、不得當現行規則引用**；現行規則看 `PROJECT_RULES.md` 0.4 的「現行規則索引」。內容與「搬出前」位置的原文逐位元組相同（基準 commit `82ba783f`），每一段的 sha256 記在下方 `MOVED-BEGIN` 標記與 `README.md` 清冊，由 `tests/test_canonical_rule_consistency.py` 機械比對，防止搬移遺失。
> 取代關係與原因：見 `docs/DECISIONS.md` `DEC-2026-11-03-08`；原位置現行區只留 `superseded:` 指標。

## P1｜`PROJECT_RULES.md` 13.2 第 1 點（舊五頁敘述；含兩個疊加指標）

被 `DEC-2026-10-29-06`、`DEC-2026-10-29-07` 取代（現行五頁＝🌍／💼 我的資產／🔍／🤖／⚙️）；舊頁名 ⚖️ 資產配置、💼 我的持股不是現行 top-level page。

<!-- MOVED-BEGIN id=P1 source=PROJECT_RULES.md#13.2-第1點@82ba783f sha256=0bebe3e11680fe41e248e7ac38bb271dbd6a194ee84526d64b3a31b4f0a321fe bytes=1232 -->
1. **五頁資訊架構與職責**：🌍 市場與趨勢、⚖️ 資產配置、💼 我的持股、🔍 找基金、⚙️ 設定（順序見 `DEC-2026-10-24-02`）。新功能優先歸入既有五頁，不輕易增第六頁；頁面名稱與主要責任應保持穩定；不以 API／資料源／模型限制或「程式比較好接」改造資訊架構。（→ **2026-10-27 指標**：此順序與五頁名稱已由客戶 `DEC-2026-10-27-02` 定為 `docs/v2/44_fund_ui_ssot.md` 的正式頁序與頁名，44 依該條有限解凍（只限頁序、頁名與 D1 導覽殼直接需要的條文／守衛，見 44 第七節第三小節之十七）；本小節首段「不解凍 44」指本小節自身不構成解凍授權，仍為真。🌍 後續內容見 `DEC-2026-10-27-03`）（→ **2026-10-29 指標**（客戶 Gate 1 方案 A，`DEC-2026-10-29-06`；有意識的政策變更，不是漏刪；本句原文不改）：⚖️ 資產配置併入「💼 我的資產」成為頁內區段，內容頁為 🌍 市場與趨勢、💼 我的資產、🔍 找基金、⚙️ 設定；🤖 AI 投資總結的入口形式待單一最小 Gate（BL-0526）。正式條文 `docs/v2/44_fund_ui_ssot.md` 第七節第三小節之二十。）
<!-- MOVED-END id=P1 -->

## P2｜`PROJECT_RULES.md` 0.5「Supersession hygiene」舊文（(1)(2) 為「舊內容保留、就地標示」）

被客戶 2026-11-03 Latest-Rule-Only 指示取代（總管讀法，待客戶確認；`DEC-2026-11-03-08`）。

<!-- MOVED-BEGIN id=P2 source=PROJECT_RULES.md#0.5-hygiene@82ba783f sha256=6ce12209ed91aceba684bc4f6b0304c05d0665f40c0ec6b62d523be38750dae0 bytes=363 -->
**Supersession hygiene（同裁示）**：(1) 舊內容保留歷史，不刪；(2) 被新裁示取代時，在舊內容就地標示「superseded by <DEC-ID>」；(3) 現行入口（本表、`docs/HANDOFF.md` 等）只能指向最新有效條文；(4) 不允許兩個看似同時有效的版本並存；(5) 不新增第五份治理 SSOT（現行四份見 0.4）。
<!-- MOVED-END id=P2 -->

## W1｜`docs/v2/81` 3.1／3.2 線框中已被 Q5 B 取代的首屏「延遲 N 日」舊線框行

被 `DEC-2026-11-03-01` Q5 B 取代。

<!-- MOVED-BEGIN id=W1 source=docs/v2/81_new_ui2_wireframe_01_market.md#wireframe-q5a-lines@82ba783f sha256=2665c216f5375611eb965154d7eff7ec2bec836ceb57da189561310640a67caf bytes=488 -->
~~│ 擬：資料新鮮度 台股 延遲 ‹n› 日  │ [Gate Q5] 只放延遲，不放日期~~
~~│           S&P 500 延遲 ‹n› 日    │~~
~~│           ⬜ 門檻待裁示          │ [語] 80 §5；rules.threshold_pending~~
（→ 2026-11-03 Q5 B 刪除上三行的「延遲 N 日」；狀態更新，不是漏刪；改為下一行）
│ ~~擬：資料新鮮度 台股 延遲 ‹n› 日｜S&P 500 延遲 ‹n› 日 ⬜ 門檻待裁示~~（→ Q5 B，見下一行）│
<!-- MOVED-END id=W1 -->
