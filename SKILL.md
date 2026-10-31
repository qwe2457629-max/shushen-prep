---
name: shushen-prep
description: Prepare written review packages for Taiwan graduate-school admissions (研究所甄試、推甄、書審、備審資料) without fabricating anything. Use when the user is applying, or helping someone apply, to Taiwanese master's programs and needs to read admission brochures (簡章), build a requirements and deadline table across several programs, write or revise a 讀書計畫, 研究計畫, 自傳 or 個人資料表, fill 報名系統文字欄, then typeset Chinese/English PDFs, merge or reorder supporting documents, and check page, word, file-size, bookmark and hyperlink limits before upload. Every claim is traced to a fact sheet and proof documents, and the applicant has the final say on every fact.
---

# 書審準備

把一位申請人的真實背景，整理成好幾個系所都過得了規範檢查、口試也答得出來的書審資料。

## 0. 核心原則（先讀這段，其他步驟都從這裡來）

- **申請人寫什麼就是什麼。** 事實由申請人決定，你不替他決定。他的說法跟你手上資料對不起來時，把差異講清楚、問他，不要自己挑一個版本。他改了說法，先改事實表，再把所有文件一起改。但「申請人決定事實」不等於「申請人決定要寫多大」：他想寫得比證明更多（草案寫成已試用、聯繫寫成合作、估計寫成實數）時，不照寫。告訴他委員看得到證明、口試會被追問，給他一個照實的寫法讓他選。
- **不捏造。** 沒有的經歷、獎項、分數、名次、發表、合作對象，一個字都不加。缺的東西列進「要問申請人」或「要補件」，不要先寫進去再說。
- **每一句都追得到。** 文件裡每個具體說法，都要能指回事實表的一列，而那一列要有證明文件或申請人親口確認。追不到的句子，刪掉或改成追得到的說法。
- **口試會被問的，就是你寫的。** 委員拿著書審問問題。寫進去的每個名詞、數字、文獻、方法，申請人都要能自己講三分鐘。他沒讀過的文獻、不會的方法，就不要寫。

你是幫手，不是代筆。成品要像申請人自己會說的話，申請人要對內容真實性負責，所以最後每份文件都要他本人看過、點頭。

## 流程總覽

| 步驟 | 產出 | 用到的檔案 |
|---|---|---|
| 1. 收集背景 | 申請人填好的背景表＋證明文件 | `templates/intake_form.md` |
| 2. 建事實表 | 唯一事實來源 | `templates/fact_sheet.md` |
| 3. 讀簡章 | 要求對照表、截止日與撞期表 | `templates/requirements_table.md`、`templates/deadline_tracker.md`、`scripts/pdf_pages.py` |
| 4. 查系所 | 有網址的系所重點 | 官網 |
| 5. 撰寫 | 各系所 Markdown 原稿 | `references/writing_rules.md` |
| 6. 對抗式審查 | 分級的審查意見、修正後原稿 | `references/review_checklist.md` |
| 7. 排版與檢查 | PDF、頁數字數、合併檔 | `scripts/*.py` |
| 8. 上傳前檢查 | 欄位對應表、文字欄檢查 | `references/upload_checklist.md`、`scripts/check_text.py` |
| 9. 交付 | 檔案清單＋三張待辦清單 | — |

一個系所走完一輪大約是這個順序。好幾個系所時，看最後的「多系所的節奏」。

### 工作資料夾

申請人的資料**不要放在這個 skill 資料夾裡**。另開一個工作資料夾，例如：

```
~/Documents/書審_<申請人代號>/
├── _source/               ← 只有你和使用者看，不分享給申請人
│   ├── 事實表.md           ← 唯一事實來源（含內部評語）
│   ├── 要求對照表.md
│   ├── 截止日與撞期.md
│   ├── 簡章/               ← 簡章 PDF 原檔
│   └── 證明文件/            ← 申請人給的掃描檔
├── OO大學_永續管理所/
│   ├── 自傳.md → 自傳.pdf
│   ├── 讀書計畫.md → 讀書計畫.pdf
│   ├── form.json → 個人資料表.pdf
│   └── manifest.json → 審查資料總檔.pdf
└── 交付/                   ← 要給申請人看的成品
```

改既有文件前先備份成 `原檔名.bak-YYYYMMDD`。

本文指令裡的 `scripts/`、`examples/` 是這個 skill 資料夾裡的路徑（skill 載入時會給你 base directory，通常是 `~/.claude/skills/shushen-prep/`），執行時補成完整路徑。`out/`、`proofs/` 這類是工作資料夾裡的路徑。**指令一律在工作資料夾裡執行**，產出才不會寫進 skill 資料夾。

## 1. 收集背景

把 `templates/intake_form.md` 給申請人填，用它取代來回訪談。填表比聊天準：日期、職稱、分數會直接照證明抄，不會靠記憶。

同時請申請人給這些檔案（掃描成 PDF，一份證明一個檔，檔名寫清楚是什麼）：

- 歷年成績單、名次證明（很多系所要班排、系排）
- 語言檢定成績單
- 在職／離職／實習證明、獎狀、證照、志工時數證明
- 他自己寫過的履歷、自傳、讀書計畫（**這是語氣的範本，比你寫的更像他**）
- 要報的每個系所的簡章 PDF（或網址）

有密碼的 PDF 讀不到，請他給沒有密碼的版本。

## 2. 建事實表

用 `templates/fact_sheet.md`。每一列是一個事實，四欄：

| 事實 | 來源／證明 | 可以怎麼寫 | 不能怎麼寫 |
|---|---|---|---|

再加三個區塊：

- **鐵律區**：寫錯就出事的規則。例如「正職才開始做的業務，不能掛在實習底下」「已離職，一律用過去式」「職稱照離職證明寫」。
- **待確認區**：申請人沒講清楚、或口頭說法跟證明對不起來的地方。每條寫清楚要問什麼。
- **變更紀錄**：哪天、誰、改了什麼。申請人後來給新版履歷時，先回填事實表，再改文件。

幾個建表時就要抓的點：

- **證明文件上的寫法優先。** 職稱、起訖日期、學位英文名稱、課名都照證明。申請人的習慣說法不同時，告訴他差在哪，讓他決定（審查委員看得到證明，通常照證明寫最安全）。
- **時序到月份。** 每段經歷寫起訖年月，標出是「在學期間」還是「畢業後」。很多錯誤是把後來才有的經驗寫到前面那段。
- **分清楚「會的」和「想學的」。** 技能、方法、文獻都一樣。

> **事實表含內部評語**（例如「名次普通，不主動提」「這件沒有證明」「這個故事申請人說有風險」）。不要放進申請人看得到的共享資料夾，也不要跟著審查資料上傳。另外備份一份到私人位置，工作資料夾被誤刪時才救得回來。

## 3. 讀簡章

用 `templates/requirements_table.md`，每個系所一塊，記這些：

- 系所全名、組別、**系所代碼**（同一份簡章常有名稱很像的兩個班別，確認申請人要報的是哪一個）
- 資格限制（例如某組要求幾年工作年資）
- 名額、審查與面試比重、面試語言
- **繳交項目逐字抄原文**，標簡章頁碼（PDF 頁序和印刷頁碼常常不一樣，兩個都記）
- 每項的頁數、字數、語言版本（「中文及英文」「中英擇一」）
- 檔案格式、單檔／總檔大小、能不能分多檔、命名規則
- 有沒有「不得有書籤／超連結」「須依某順序檢附」這類規定
- 推薦信：幾封、格式、誰上傳、**推薦人的截止時間**
- 報名、繳費、上傳、推薦信各自的截止時間，**寫到分鐘**（常常不同天）
- 面試日期、地點

簡章寫得模糊時，**採最嚴格的解讀**，並在表上註明你怎麼解讀。例如「自傳（中文及英文，限 1 頁）」就當成中英合計排進 1 頁。

好幾個系所時，同時填 `templates/deadline_tracker.md`：截止日由早到晚排，再把面試日期排一排，看有沒有撞期。撞期要早點告訴申請人，讓他決定取捨。

簡章 PDF 抽不出字、或抽出來是亂碼（用 CID 字型的簡章很常見）時，把頁面轉成圖片再看：

```bash
python3 scripts/pdf_pages.py 簡章.pdf 簡章_png --pages "40-45" --text
```

`--text` 會先試著抽字，抽出空白或亂碼時會提示你改看 PNG，接著用 Read 讀那幾張圖。

## 4. 查系所

- 看系所官網：課程架構、必修、研究領域、授課語言、有沒有規定交換或實習。每一條記下網址。
- **不點名教授**，除非你在系所官網親眼看到他的研究領域，而且申請人知道這位老師在做什麼、口試被問得起。
- 系所的英文正式名稱照簡章或官網，不要自己翻。
- 要寫進文件的政策、法規、產業數字，都要有來源。查不到或有爭議的就不寫，或改成保守說法（「正在收緊」比「完全沒有」安全）。

查到的東西寫成一份短清單（重點＋網址），撰寫時只能用清單上的。

## 5. 撰寫

規則全部在 `references/writing_rules.md`，動筆前讀一遍。最重要的幾條：

- **小標照簡章的字眼。** 簡章寫「自傳（含學習計畫）」，文件裡就要有看得出是學習計畫的段落；寫「含生涯規劃」就要有生涯規劃。
- **申請人自己的草稿優先。** 有他寫的版本，就以那份為底修，不要整份重寫。
- **每所客製。** 經歷段落可以共用，但「為什麼是這個所」「要讀什麼、做什麼研究」每所自己寫，而且要對得上第 4 步查到的系所重點。
- **中文講話式，不要顧問腔**；英文版不是逐句翻譯。數字全留。
- 沒查證的教授不點名，申請人沒讀過的文獻不加。

原稿用 Markdown 寫，`scripts/md2pdf.py` 支援的語法：`#` 文件標題（一次）、`##`／`###` 小標、段落（空行分隔）、`- ` 項目、`1. ` 編號、`**粗體**`、`*斜體*`、`---` 分隔線。`<!-- 註解 -->` 不會出現在 PDF 上，可以用來放字數或待確認備註：

```markdown
<!-- 待確認：社區回收站排班是 2023 還是 2024 開始？ -->
<!-- 字數: 980 -->
```

## 6. 對抗式審查

寫完先不要排版，先審。用 `references/review_checklist.md`，從四個角度各看一遍：

- **事實查核員**：每句話能不能追到事實表和證明
- **系所委員**：看完知不知道這個人為什麼要來、要做什麼、做不做得完
- **口試委員**：會追問什麼？申請人答得出來嗎？
- **規範檢查員**：簡章要的東西有沒有齊、有沒有超頁超字

可以開 subagent 扮這幾個角色（各自獨立看，比一個人看四遍有效）。要他們**預設每份文件都有錯**，回報格式是：檔案、原句、問題、嚴重度、改法。嚴重度分三級：

- **blocker**：捏造或沒有依據、時序矛盾、違反簡章硬規定。不改不能交。
- **major**：說法超過證據、口試一問就倒、跨文件不一致、漏了簡章要的子項目。原則上要改。
- **minor**：文風、贅字、可以更具體。合理就改。

審查意見也會錯。跟事實表衝突的意見不採納，記一筆理由。改完 blocker 和 major 後，再針對改過的地方複查一次。

研究→撰寫→審查→定稿四步各自派 subagent 的 prompt 骨架在 `references/simplified_workflow_for_subagents.md`。

## 7. 排版與檢查

需要 Tectonic（LaTeX 編譯器）。先找：

```bash
command -v tectonic || ls ~/.local/bin/tectonic
```

都沒有就裝（單一執行檔、裝到 `~/.local/bin`、不用管理員權限）：

```bash
bash scripts/install_tectonic.sh
```

第一次編譯會下載 LaTeX 套件，要有網路。下面的範例用 `examples/` 裡虛構申請人的檔案示範，實際使用時換成申請人的原稿；記得在工作資料夾裡執行。

**Markdown → PDF**（自傳、讀書計畫、研究計畫）

```bash
python3 scripts/md2pdf.py examples/study_plan_zh.md out/讀書計畫.pdf --lang zh \
  --header "OO大學 永續管理研究所｜讀書計畫" --name "林小安 Lin Hsiao-An" --max-pages 2

python3 scripts/md2pdf.py examples/study_plan_en.md out/Study_Plan.pdf --lang en \
  --header "OO University, Graduate Institute of Sustainability Management | Study Plan" \
  --name "Lin Hsiao-An"
```

它會印出頁數和字數：中文印「漢字數」和「去空白字元數（含標點）」兩個數字，英文印 words；文件標題和註解都不算。超過 `--max-pages` 時 exit code 是 1，PDF 照樣產出，方便你看超了多少。

限一頁的自傳加 `--compact`（字級、行距、邊界一起收緊）：

```bash
python3 scripts/md2pdf.py examples/autobiography.md out/自傳_一頁.pdf --lang zh --compact --max-pages 1 \
  --header "OO大學 永續管理研究所｜自傳 Autobiography" --name "林小安 Lin Hsiao-An"
```

字型會自動偵測（macOS 用 Times New Roman＋PingFang TC 或 Songti TC，Linux 用 TeX Gyre Termes 或 Noto Serif＋Noto Serif／Sans CJK TC），要換就加 `--latin-font`、`--cjk-font`。半形區間號「–」被 xeCJK 排成全形長槓、直引號、LaTeX 特殊字元，腳本都會自動處理。

超頁時的處理順序：**先刪內容，最後才動版面**。先刪最不相關的段落、合併重複的說法，還是超才用 `--compact`。

**個人資料表／基本資料表**

```bash
python3 scripts/render_form.py examples/form.json out/個人資料表.pdf --max-pages 1
```

JSON 的 rows 有四種：`kv`（欄位：值）、`section`（區塊標題）、`item`（期間、內容、英文內容、證明頁碼）、`text`（有字數上限的長欄位，超過會報錯）。它會印出「依表格出現順序、有證明的項目」的 proof 順序，下一步直接用。

如果系所有指定表格（簡章附件），照附件的欄位和順序填，不要自己加欄位。

**佐證重排**（簡章要求「依個人資料表順序檢附」時）

```bash
python3 scripts/reorder_proofs.py 佐證合輯.pdf out/其他有利審查資料.pdf --order "8,7,6,2,4" --max-mb 10
```

頁碼從 1 開始，可以寫 `3-4` 這種範圍。預設會移除超連結和書籤；要保留就加 `--keep-links`、`--keep-outline`。

**合併成總檔**（簡章規定「限一份 PDF」時）

```bash
python3 scripts/merge_pdfs.py manifest.json
```

`manifest.json` 放在工作資料夾裡，長這樣（另一個完整範例看 `examples/merge_manifest.json`，它示範了只列在目錄、不合併的項目）：

```json
{
  "output": "out/林小安_審查資料總檔.pdf",
  "toc": true,
  "toc_title": "審查資料目錄",
  "bookmarks": true,
  "strip_links": true,
  "max_mb": 15,
  "compress": true,
  "items": [
    {"title": "一、歷年成績單（含名次證明）", "file": "proofs/成績單.pdf"},
    {"title": "二、自傳", "file": "out/自傳.pdf"},
    {"title": "三、讀書計畫", "file": "out/讀書計畫.pdf"},
    {"title": "四、其他有利審查資料", "file": "proofs/佐證.pdf", "pages": "1-3,5"}
  ]
}
```

manifest 裡的相對路徑（`output` 和每個 `file`）以 **manifest 所在的資料夾**為準；PDF 放在別處時加 `--base-dir 資料夾`，要換輸出位置加 `--output 路徑`。例如拿範例 manifest 合併你已經排好的 PDF：`python3 scripts/merge_pdfs.py examples/merge_manifest.json --base-dir out --output out/審查資料總檔.pdf`。`items` 的順序照簡章列的繳交順序。`toc` 會自動產一頁目錄（頁碼是合併後的 PDF 頁序）。簡章禁止書籤就把 `bookmarks` 設 `false`。跑完會回報總頁數、MB、連結數、書籤數；超過 `max_mb` 時 exit 1，`compress: true` 會先把內嵌圖片降到寬 2000px、JPEG 品質 80 再試一次。

**看排版結果**——頁數對了不代表版面對了，每份 PDF 都要轉圖看一次：

```bash
python3 scripts/pdf_pages.py out/自傳.pdf out/自傳_png
python3 scripts/pdf_pages.py proofs/證書.pdf out/證書_png --white-bg
```

用 Read 讀 PNG，檢查：有沒有孤行、表格有沒有被切開、頁首對不對、中文有沒有變方塊、標點有沒有怪掉。macOS 的 `sips` 轉出來的 PNG 背景是透明的，Read 看起來正常，但有些看圖程式會顯示成黑底；要把圖給別人看時加 `--white-bg`（需要 Pillow）。

**報名系統的純文字欄位**（簡歷、自傳摘要等直接貼進網頁的欄位）

```bash
python3 scripts/check_text.py examples/form_field.txt --limit 300 --count nospace --encoding cp950
```

它會用四種算法算字數（全部字元、去空白、漢字、英文 words；`--limit` 比的是 `--count` 指定的那種，預設最保守的全部字元），檢查能不能用 cp950（Big5）存，並列出危險字元（特殊破折號、emoji、零寬字元、NBSP、tab、Word 帶來的 `\r`）和建議的替代字。很多報名系統還是 Big5，貼進去會變問號。加 `--fix 修正版.txt` 會另存一份自動修正版，原檔不動。簡章沒說怎麼算字數時，用預設的 `chars` 最保險。

每支腳本都有 `--help`。

## 8. 上傳前檢查

逐條走 `references/upload_checklist.md`。最容易漏的：

- 做一張「上傳欄位 → 檔案」對應表，每個欄位對一個檔，順序照系統畫面。
- 文字欄全部跑過 `check_text.py`。
- 副檔名小寫 `.pdf`、單檔與總檔都在大小上限內、檔名照簡章規定。
- 測試上傳用明顯的測試檔名，不要用正式檔名，免得最後送出的是測試版。
- 簡章禁止書籤／超連結時，確認腳本回報的連結數、書籤數都是 0。
- 佐證順序跟個人資料表一致；個人資料表上列了的項目都有證明。
- 推薦人的截止時間、面試撞期，再提醒一次。
- 上傳和送出通常要申請人本人登入操作。送出前請他把每個 PDF 從頭看過一遍。

## 9. 交付

回覆保持簡短，檔案放在工作資料夾的 `交付/`，回覆裡列：

1. **檔案清單**：每個系所、每份文件的路徑、頁數、字數、限制、是否通過。
2. **要問申請人**：待確認區裡還沒解決的事，一條一個問題，寫成他看得懂、能直接回答的句子。
3. **要補件**：還缺的證明、成績單、語言檢定、推薦信，標上哪個系所要、截止時間。
4. **口試要準備**：文件裡寫了、但沒有證明的說法；文件裡提到的文獻、方法、專有名詞；第 6 步口試委員列出的追問題。申請人要能自己講出來。

## 多系所的節奏

- **先做共用的，再逐所寫。** 事實表、要求對照表、截止日與撞期表三份先做完，再照截止日由早到晚一所一所寫。
- **共用段落，但每所客製。** 經歷段落可以用同一套句子（反正事實一樣），動機、為什麼是這個所、讀書或研究計畫每所重寫。
- **跨所一致性。** 同一件事在每份文件裡說法要一致：日期、職稱、數字、名次寫法。同時報不同領域時，不要在 A 所寫「所以我決定不再走 B 這條路」，因為 B 所的文件正說著相反的話，口試被問到就很難圓。
- **事實改了，全部一起改。** 申請人更正一個事實時，先改事實表，再搜尋所有原稿裡的舊說法，一份一份改，重新排版。只改一份比不改還糟。
- **每所都跑一次審查。** 不要因為上一所審過就跳過，客製的段落最容易出錯。

## 檔案

| 路徑 | 用途 |
|---|---|
| `scripts/md2pdf.py` | Markdown → PDF（中／英），回報頁數字數、超頁 exit 1 |
| `scripts/render_form.py` | JSON → 個人資料表 PDF，印出佐證順序 |
| `scripts/reorder_proofs.py` | 依頁碼重排佐證合輯，預設移除連結與書籤 |
| `scripts/merge_pdfs.py` | 依 manifest 合併、目錄頁、書籤、移除連結、大小檢查與壓縮 |
| `scripts/pdf_pages.py` | PDF 頁面轉 PNG，給目視檢查與抽不出字的簡章 |
| `scripts/check_text.py` | 報名系統文字欄：字數、編碼、危險字元 |
| `scripts/install_tectonic.sh` | 安裝 Tectonic 到 `~/.local/bin` |
| `scripts/_common.py` | 上面幾支腳本共用的函式（找 tectonic、偵測字型等），不用直接執行 |
| `templates/intake_form.md` | 給申請人填的背景表 |
| `templates/fact_sheet.md` | 事實表範本 |
| `templates/requirements_table.md` | 簡章要求對照表範本 |
| `templates/deadline_tracker.md` | 截止日與撞期表 |
| `references/writing_rules.md` | 撰寫規則與中文文風前後對照 |
| `references/review_checklist.md` | 四個審查角度的檢查題、嚴重度、常見問題 |
| `references/upload_checklist.md` | 上傳前檢查與排版坑 |
| `references/simplified_workflow_for_subagents.md` | 研究→撰寫→審查→定稿的派工骨架 |
| `examples/` | 虛構申請人「林小安」的範例原稿、表單與 manifest |
