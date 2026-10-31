# shushen-prep 書審準備

一個 [Claude Code](https://claude.com/claude-code) skill，幫你準備台灣研究所甄試（推甄）的書面審查資料：讀簡章、整理要求和截止日、寫讀書計畫和自傳、排版成 PDF、合併佐證、上傳前檢查。

它的核心規則只有一條：**申請人寫什麼就是什麼，一個字都不捏造。** 每一句話都要追得到申請人的事實表和證明文件，因為口試委員會拿著書審問問題。

## 為什麼

書審最常出事的地方不是文筆，是事實：

- 正職才做過的事，被寫成實習就做過
- 草案寫成「已協助三個社區」
- 職稱跟離職證明不一樣
- 引用了申請人沒讀過的文獻，口試一問就倒
- 同時報五所，改了一份忘了其他四份

再來是規範：超頁、超字、檔案太大、「不得有書籤或超連結」、「依個人資料表順序檢附」、報名系統文字欄貼上去變問號。

這個 skill 把這些坑整理成流程、範本和腳本，讓 Claude 一所一所幫你做，並在每一步檢查。

## 會幫你做的

- **建事實表**：申請人填背景表，整理成唯一的事實來源，標出鐵律（不能寫錯的事）和待確認事項。
- **讀簡章**：逐字整理每個系所的繳交項目、頁數字數、格式大小、截止時間（到分鐘），並檢查面試撞期。簡章抽不出字時轉成圖片看。
- **查系所**：從官網整理課程和研究重點，每條附網址。沒查證的教授不點名。
- **撰寫**：自傳、讀書計畫、研究計畫、個人資料表。中文用講話的方式寫，不要顧問腔；英文版不是逐句翻譯。
- **對抗式審查**：從事實查核員、系所委員、口試委員、規範檢查員四個角度挑錯，分 blocker／major／minor。
- **排版與檢查**：Markdown 轉中英文 PDF、限一頁的緊排版、個人資料表、佐證重排、合併總檔（目錄頁、書籤、移除超連結、大小檢查與壓縮）、報名系統文字欄的字數與編碼檢查。
- **交付**：列出要問申請人的事、要補的件、口試要準備的說法。

## 不會做的

- **不代寫捏造。** 沒有的經歷、獎項、分數、合作對象不會出現在文件裡。缺的會列出來給你。
- **不保證錄取。** 它只確保文件真實、合規、講得出口。
- **不取代簡章。** 每年簡章都會變，一律以學校最新公告為準。範本裡的系所和規定都是虛構的示範。
- **不替申請人上傳或送出。** 上傳和送出由申請人本人操作。
- **申請人對內容的真實性負責。** 每份文件送出前，都要申請人本人看過、確認。

## 安裝

```bash
git clone https://github.com/qwe2457629-max/shushen-prep.git ~/.claude/skills/shushen-prep
```

需求：

- `python3`，加上 `pypdf` 和 `Pillow`：

  ```bash
  pip3 install pypdf Pillow
  ```

  （`Pillow` 只有壓縮圖片和貼白底時用到，沒裝的話相關功能會告訴你要裝。）

- [Tectonic](https://tectonic-typesetting.github.io/)（LaTeX 編譯器）。沒有的話：

  ```bash
  bash ~/.claude/skills/shushen-prep/scripts/install_tectonic.sh
  ```

  單一執行檔，裝到 `~/.local/bin`，不用管理員權限。第一次編譯會下載 LaTeX 套件，要有網路。

- 中文字型：macOS 內建的就夠（PingFang TC 或 Songti TC）。Linux 請裝 Noto Serif CJK TC 或 Noto Sans CJK TC。

- PDF 轉圖片（`pdf_pages.py`）：macOS 用內建的 `sips`；Linux 要有 `pdftoppm`（通常在 `poppler-utils` 套件裡）。

不需要 pandoc、LibreOffice 或 Word。

## 快速開始

在 Claude Code 裡直接講，skill 會自動觸發（或輸入 `/shushen-prep`）：

```
你：我要幫學弟準備推甄，報 OO大學永續管理所和 △△大學環境政策所，
    簡章 PDF 在 ~/Downloads/簡章/。他以前寫過一份自傳，也在那裡。

Claude：好。先開一個工作資料夾，申請人的資料不會放進 skill 資料夾。
        1. 請他填 templates/intake_form.md 這張背景表，並給我成績單、
           名次證明、語言檢定和各種證明的掃描檔。
        2. 我先讀兩份簡章，整理要求對照表和截止日表。
           △△大學的簡章第 12–14 頁抽不出字，我轉成圖片看。
        ……
        兩所的面試都在 11/08，一北一南，要請他決定取捨。

（幾輪之後）

Claude：OO大學的四份文件都過了審查和規範檢查：
        - 自傳.pdf：中英同頁，1 頁（限 1 頁）✓
        - 讀書計畫.pdf：7 頁（限 10 頁）✓
        - 個人資料表.pdf：1 頁 ✓
        - 其他有助審查資料.pdf：6 頁、2.3 MB、連結 0、書籤 0 ✓
        要問他：志工是 2022 還是 2023 開始？（證明和履歷不一致）
        要補件：推薦人還沒定（推薦人 10/09 17:00 前要自己上傳）
        口試要準備：報名表欄位從 14 個減到 6 個那件事沒有書面證明，
                    要能講清楚怎麼做的。
```

## 檔案結構

```
shushen-prep/
├── SKILL.md                     # Claude 照著做的流程
├── scripts/
│   ├── md2pdf.py                # Markdown → 中英文 PDF，回報頁數字數
│   ├── render_form.py           # JSON → 個人資料表 PDF，印出佐證順序
│   ├── reorder_proofs.py        # 依頁碼重排佐證，移除連結與書籤
│   ├── merge_pdfs.py            # 合併總檔：目錄頁、書籤、大小檢查與壓縮
│   ├── pdf_pages.py             # PDF 頁面轉 PNG，目視檢查用
│   ├── check_text.py            # 報名系統文字欄：字數、Big5 編碼、危險字元
│   ├── install_tectonic.sh      # 安裝 LaTeX 編譯器
│   └── _common.py               # 共用函式，不直接執行
├── templates/
│   ├── intake_form.md           # 給申請人填的背景表
│   ├── fact_sheet.md            # 事實表
│   ├── requirements_table.md    # 簡章要求對照表
│   └── deadline_tracker.md      # 截止日與撞期表
├── references/
│   ├── writing_rules.md         # 撰寫規則、中文文風前後對照
│   ├── review_checklist.md      # 四個審查角度、嚴重度、常見問題
│   ├── upload_checklist.md      # 上傳前檢查、排版的坑
│   └── simplified_workflow_for_subagents.md  # 派 subagent 的 prompt 骨架
└── examples/                    # 虛構申請人「林小安」的範例
```

## 不用 Claude，單獨用腳本

每支腳本都有 `--help`。在你自己的工作資料夾裡執行，`scripts/` 換成 skill 的完整路徑（例如 `~/.claude/skills/shushen-prep/scripts/`）：

```bash
python3 ~/.claude/skills/shushen-prep/scripts/md2pdf.py 自傳.md 自傳.pdf --lang zh --max-pages 2
python3 ~/.claude/skills/shushen-prep/scripts/check_text.py 簡歷.txt --limit 300 --count nospace
python3 ~/.claude/skills/shushen-prep/scripts/merge_pdfs.py manifest.json
```

`manifest.json` 的格式看 `examples/merge_manifest.json` 或 `merge_pdfs.py --help`；裡面的相對路徑以 manifest 所在資料夾為準。

## 隱私

申請人的資料（事實表、證明文件、成績單）請放在 skill 資料夾以外的工作資料夾。`.gitignore` 已排除 PDF、`private/`、`applicants/`，但不要依賴它。事實表含內部評語，不要分享給申請人或上傳。

## English

**shushen-prep** is a Claude Code skill for preparing written application packages (書審) for Taiwanese graduate-school admissions by recommendation and review (推甄). It reads admission brochures, builds a per-program requirements and deadline table, drafts study plans and autobiographies in Chinese and English from a verified fact sheet, runs an adversarial review (fact-checker, faculty reader, interviewer, compliance checker), typesets PDFs with Tectonic, merges and reorders supporting documents (table of contents, bookmarks, hyperlink removal, size limits), and checks plain-text form fields for Big5 compatibility. It never invents experience: every sentence must trace to the applicant's fact sheet and proof documents, and the applicant has the final say. It does not guarantee admission and does not replace the official brochure.

## 授權

MIT
