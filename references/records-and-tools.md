# 專案紀錄與本地工具

## 使用條件
Python 3.10+，全部使用標準函式庫。沒有網路、付費服務或固定磁碟路徑依賴。命令中的腳本路徑需替換成實際技能資料夾位置；資料放研究專案，不寫進技能本體。

```text
python /path/to/academic-writing-workflow/scripts/workflow_tools.py init /path/to/new-project --title "研究名稱"
python /path/to/academic-writing-workflow/scripts/workflow_tools.py check /path/to/project/research.json --manuscript /path/to/project/draft.md --output /path/to/project/check-report.json
python /path/to/academic-writing-workflow/scripts/workflow_tools.py diff /path/to/project/before.md /path/to/project/after.md --start-line 8 --end-line 12 --output /path/to/project/diff-report.json
```

init 只建立不存在的新目錄，拒絕覆蓋既有專案；先讀完五份模板才開始建立，但檔案系統寫入中斷仍可能留下部分專案，應檢查後另選新路徑。check / diff 不修改輸入；只在明確指定 output 時寫報告，並拒絕覆寫輸入檔。命令可用 PowerShell，含空白路徑加引號。

## research.json 格式
init 建立 schema_version=1、mode=question、標題及下列七個空陣列。沒有資料的空紀錄不代表研究完成。以下內容均為**合成格式示例**，不是有效文獻或實際研究；不要複製成自己的證據或作者決定。

```json
{
  "schema_version": 1,
  "skill_version": "0.1.0",
  "title": "合成示例",
  "mode": "argument",
  "sources": [{
    "id": "S1", "key": "SyntheticA2026", "title": "合成來源，不可引用",
    "doi": "", "access": "abstract", "read_locator": "摘要",
    "metadata_status": "not_checked", "version_status": "not_checked",
    "retraction_status": "not_checked"
  }],
  "results": [{
    "id": "R1", "text": "合成相關係數 r=.20",
    "locator": "synthetic-output.txt:1", "synthetic": true
  }],
  "claims": [{
    "id": "C1", "text": "合成關聯主張", "strength": "associational",
    "evidence": [{"kind": "result", "id": "R1", "locator": "synthetic-output.txt:1", "relation": "supporting"}]
  }],
  "decisions": [{
    "id": "D1", "text": "建議縮小主張", "origin": "ai_proposal",
    "provenance": "合成練習中的 AI 建議，未經作者採用"
  }],
  "issues": [{
    "id": "I1", "disposition": "pending", "status": "open",
    "response": "", "change_locator": ""
  }],
  "terms": [{"canonical": "生成式人工智慧", "variants": ["生成型人工智慧"]}],
  "artifacts": []
}
```

### 欄位語義
- mode：question / evidence / design / argument / draft / revise / submit。
- sources：id 與引用 key 唯一；key 只用英數及 `_:.+-`。access 記本次實讀 metadata / abstract / partial / full / unavailable。metadata_status 可為 verified / mismatch / not_checked / unavailable。verified 需有實際核對依據，程式不會上網替你判定。可額外保存 metadata_evidence（URL、查閱日期、比對紀錄）。版本與撤稿狀態保留已查來源和日期，不以未見提示當已查證。
- results：記實際結果 text 與原始資料／分析輸出 locator；synthetic=true 永遠只代表示例。
- claims：strength 為 descriptive / associational / causal。evidence 的 kind 為 source / result，id 指到來源或結果，附 locator 與 relation（supporting / contradicting / mixed / not_checked）。因果主張另寫 causal_basis，描述設計與識別假設；填字串不證明因果成立。
- decisions：origin 為 author / ai_proposal，text 記決定內容，provenance 記實際作者訊息／決策位置與日期。沒有作者採用不能設 author。
- issues：disposition 為 accept / partial / decline / pending；status 為 open / resolved / limitation。非 pending 處置附 decision_id，必須連到 author 決定；resolved 要有 response，accept／partial 解決時還需 change_locator。partial 未完全解決一般維持 open 或 limitation。
- terms：canonical 與 variants 用於提示非標準用語，不自動改稿；引句內合法變體仍可能被報出。
- artifacts：明確登記 path 與原始已接受內容的 sha256。相對路徑相對於 research.json；可另附 depends_on 紀錄人工判斷的依賴，但程式不自動推導依賴圖。以 Python hashlib.sha256(Path(...).read_bytes()).hexdigest() 計算，或 PowerShell Get-FileHash -Algorithm SHA256（轉小寫）。續作發現 hash 改變時先判斷影響，不直接更新 hash 抹去變動證據。

## check 的範圍與狀態
檢查登記表格式、唯一性、DOI 正規化後重複、主張證據連結與位置、閱讀不足、未決支持、作者處置、材料 hash，並回報各表筆數。

稿件引用只解析顯式 `[@key]` 或 `[@key; @other]`。會跳過一般 fenced code 與 inline code；不是完整 Markdown parser。APA 作者年份、中文自然語言引文、Word 引文域、BibTeX／LaTeX 不解析，不能宣稱已檢查。沒有顯式鍵時輸出 NO_EXPLICIT_KEYS；只有部分鍵也只涵蓋那些鍵，未登記主張的完整性不檢查。

退出碼：0=無機械發現，1=有發現，2=輸入／執行錯誤。即使退出碼 0，semantic_claim_support 仍是 not_checked_by_program，bibliographic_network_verification 仍是 not_performed。不得把退出碼 0 命名為全文正確或可投稿。

來源狀態是登記者提供的陳述；程式不證明它是真的。它不核對資料值、統計推論、主張支持或撤稿紀錄本身，只提示待檢項。

## diff 的範圍
列出前後數值 token 和顯式引用鍵的計數差，text_changed 表示全文是否改變。數值可能包含日期、文獻年份與編號；不解釋顯著性、不保證相同數字仍接在相同主張，也不會發現所有語義升格。

行範圍為舊稿 1-based、含首尾。指定兩個界線時，檢查新稿是否保留舊稿該範圍以外的前後文字，允許範圍內長度改變。比較為 UTF-8 解碼且換行形式正規化；不是位元組一致檢查。

diff 正常執行一律退出 0，差異見 JSON status 與 scope；輸入錯誤退出 2。no_tracked_difference 可能伴隨 text_changed=true，表示沒有偵測到所追蹤的數值／引用差異，仍需讀稿。

## 跨階段紀錄
紀錄只是可追溯材料，不是自動工作流程引擎。每次依實際工作更新 mode、證據和作者決定，保留前版或版本控制。改變問題／資料／主要主張時，列出受影響章節與尚待複核事項；不宣稱已做未實施的檢查。
