# 論文寫作工作流程

`academic-writing-workflow` 是協助教育與社會科學實證論文的 Codex Skill，提供七個可依序執行或單獨進入的模式。支援繁體中文規畫及中英文稿件。

目前版本：**0.1.0**。

## 工作模式

| 模式 | 任務 | 主要產物 |
|---|---|---|
| question | 研究問題形成 | 問題簡報 |
| evidence | 文獻檢索、閱讀範圍與統整 | 檢索紀錄、文獻矩陣 |
| design | 問題、資料與方法對應 | 設計對照、分析計畫 |
| argument | 從實際結果建立論證 | 主張—證據表、大綱 |
| draft | 分章寫作、局部修改與翻譯 | 初稿及待補事項 |
| revise | 審查、核對、修訂與回覆 | 問題表、修訂稿 |
| submit | 定稿及投稿材料準備 | 材料矩陣及剩餘待辦 |

技能區分作者決定、AI 建議與已確認事實，記錄實際閱讀範圍及證據位置，並控制修改範圍。研究執行及資料分析需要真實資料與分析紀錄，不能由文字生成代替。

## 安裝與使用

將整個儲存庫目錄放入 Codex 的技能目錄，資料夾名稱保留為 `academic-writing-workflow`。請保留 `references/`、`assets/`、`scripts/` 及 `agents/`，不要只複製 SKILL.md。安裝後開啟新的對話。

```text
請使用 $academic-writing-workflow。
我目前只有研究方向，請先協助釐清問題，區分我的想法與你提出的建議，不先寫整篇論文。
```

```text
請使用 $academic-writing-workflow 的 revise 模式。
檢查這份稿件的研究設計與結論是否相稱，只給問題、位置、依據和建議，先不要修改原稿。
```

完整規則見 [SKILL.md](SKILL.md)。

## 本地工具

Python 3.10+，只使用標準函式庫，不呼叫外部 API 或付費服務。

```shell
python -X utf8 scripts/workflow_tools.py init /path/to/new-project --title "研究名稱"
python -X utf8 scripts/workflow_tools.py check /path/to/project/research.json --manuscript /path/to/project/draft.md
python -X utf8 scripts/workflow_tools.py diff /path/to/before.md /path/to/after.md --start-line 8 --end-line 12
```

- init：建立不存在的新專案與五份模板，拒絕覆寫既有目錄。
- check：檢查登記的引用鍵、重複識別碼、證據連結、修訂處置與檔案變動。
- diff：比較數值、顯式引用鍵及指定行範圍外的文字變更。

資料格式、退出碼及限制見 [紀錄與工具](references/records-and-tools.md)。

## 驗證

```shell
python -X utf8 scripts/test_workflow_tools.py
```

v0.1.0 已通過 21 項本地程式回歸測試、技能結構／UTF-8／內部連結檢查，以及三項獨立合成案例試跑。合成試跑包含問題形成、局部修改及不顯著結果的論證整理；不代表真實研究效果量測。

## 範圍與限制

- 本版以實證論文為主，沒有完整涵蓋系統性／範疇性回顧或後設分析方法。
- 程式只解析 `[@key]` 等顯式引用鍵，沒有解析一般 APA、中文作者年份、Word 引文域或 BibTeX／LaTeX。
- 程式不進行網路文獻核驗、統計推論或語義支持判定；機械通過不代表學術正確或可投稿。
- 相同數值被移到不同論點、純語義變化等仍需讀稿判斷。
- Word／PDF 製作、文獻檢索與資料分析需使用環境中合適工具。
- 投稿模式準備材料；實際提交需要使用者明確指示。

尚待以真實研究材料持續試用與修正。
