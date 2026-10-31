#!/usr/bin/env python3
"""把 JSON 定義的「個人資料表／基本資料表」排成 PDF（中英雙語表格、欄寬自動換行），
檢查頁數與字數上限，並印出佐證頁序，可直接餵給 reorder_proofs.py。

用法：
  python3 render_form.py FORM.json OUTPUT.pdf [--max-pages 1] [--latin-font F] [--cjk-font F] [--keep-build]

FORM.json 格式：
  {
    "title": "OO大學 永續管理研究所 個人資料表",     （必填）
    "subtitle": "Personal Information Form",          （選填）
    "proof_column": "佐證頁",   （選填）表格多一欄，顯示每個項目的證明在「重排後的佐證檔」第幾頁
    "proof_page_offset": 0,     （選填）佐證檔若接在其他文件後面，頁碼要加多少
    "label_width": "3.2cm",     （選填）左欄寬度
    "font_size": 10,            （選填）10、11 或 12
    "note": "…",                （選填）表格下方的小字說明，字串或字串清單
    "rows": [ … ]               （必填）
  }

rows 的四種類型：
  {"type": "kv", "label": "姓名 Name", "value": "林小安 Lin Hsiao-An"}
      一般欄位。value 可以是字串清單（每項一行）。可加 "label_en" 在欄名下方加小字英文。
  {"type": "section", "title": "學歷 Education"}
      分段標題列（底色）。
  {"type": "item", "period": "2023.09–2027.06", "text": "OO大學 XX學系",
   "text_en": "B.A. in XX, OO University", "proof": "p3"}
      經歷、獎項等。text_en 選填（排在第二行、字小一號）；proof 選填。
  {"type": "text", "label": "自我介紹", "value": "…", "limit": 300, "count": "nospace"}
      長文字欄。limit 選填（字數上限，超過就報錯）；count 選填：nospace（預設）／chars／cjk／words。

proof 寫法："p3"、"p3-4"、"p3,p5"、"3" 都可以；"無證明"、"無"、"none" 表示沒有證明；
其他文字（例如 "成績單"）會照印在佐證欄，但不列入頁序。
印出的佐證頁序＝依表格由上到下、有證明的項目所對應的原始頁碼（重複的只算一次）。

離開代碼：0 = 成功；1 = 超過頁數或字數上限（PDF 仍會產出，方便檢查）；
          2 = 檔案不存在、JSON 格式錯誤、編譯失敗等。
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

NO_PROOF = {"", "無證明", "無", "none", "n/a", "na", "-", "—", "–"}
PAGE_REF = re.compile(r"^[pP]?\d+(\s*[-–~]\s*[pP]?\d+)?(\s*[,，、]\s*[pP]?\d+(\s*[-–~]\s*[pP]?\d+)?)*$")
REQUIRED = {"kv": ("label", "value"), "section": ("title",), "item": ("text",), "text": ("label", "value")}


def as_text(v) -> str:
    if isinstance(v, list):
        return "\n".join(str(x) for x in v)
    return "" if v is None else str(v)


def md(v) -> str:
    """表格內文字：換行→段內換行，其餘照 Markdown 行內規則（可用 **粗體**）。"""
    s = as_text(v).replace("\r\n", "\n").strip()
    return C.inline_md(s.replace("\n", C._HARD_BREAK))


def parse_proof(v):
    s = as_text(v).strip()
    if s.lower() in NO_PROOF:
        return ("none", None) if s else (None, None)
    if PAGE_REF.match(s):
        return ("pages", C.parse_pages(s, None, f"proof「{s}」"))
    return ("label", s)


def fmt_new_pages(news: list[int]) -> str:
    if len(news) == 1:
        return str(news[0])
    if news == list(range(news[0], news[0] + len(news))):
        return f"{news[0]}–{news[-1]}"
    return ",".join(str(x) for x in news)


def load_form(path: str) -> dict:
    C.need_file(path, "表單 JSON")
    try:
        with open(path, encoding="utf-8-sig") as f:
            d = json.load(f)
    except json.JSONDecodeError as e:
        C.die(f"不是合法的 JSON：{path}（第 {e.lineno} 行第 {e.colno} 欄：{e.msg}）")
    if not isinstance(d, dict) or not isinstance(d.get("title"), str):
        C.die("表單 JSON 要有 title（表單標題）")
    rows = d.get("rows")
    if not isinstance(rows, list) or not rows:
        C.die("表單 JSON 要有 rows（表格列清單）")
    for i, r in enumerate(rows, 1):
        t = r.get("type") if isinstance(r, dict) else None
        if t not in REQUIRED:
            C.die(f"rows 第 {i} 列的 type 要是 kv、section、item 或 text（收到：{t!r}）")
        miss = [k for k in REQUIRED[t] if k not in r]
        if miss:
            C.die(f"rows 第 {i} 列（{t}）缺少欄位：{', '.join(miss)}")
        if t == "text" and r.get("count", "nospace") not in C.COUNT_MODES:
            C.die(f"rows 第 {i} 列的 count 只能是：{', '.join(C.COUNT_MODES)}")
        if t == "text" and "limit" in r and not isinstance(r["limit"], int):
            C.die(f"rows 第 {i} 列的 limit 要填整數")
    if d.get("font_size", 10) not in (10, 11, 12):
        C.die("font_size 只能是 10、11 或 12")
    return d


def main() -> int:
    p = C.ZhArgumentParser(prog="render_form.py", description=__doc__)
    p.add_argument("form", metavar="FORM.json", help="表單內容（JSON）")
    p.add_argument("output", metavar="OUTPUT.pdf", help="輸出 PDF")
    p.add_argument("--max-pages", type=int, default=1, metavar="N",
                   help="頁數上限（預設 1；填 0 表示不檢查）")
    C.add_font_args(p)
    p.add_argument("--keep-build", action="store_true", help="把 .tex 與編譯紀錄留在輸出檔旁的 _build/")
    args = p.parse_args()

    d = load_form(args.form)
    has_pc = bool(d.get("proof_column"))
    offset = int(d.get("proof_page_offset", 0) or 0)
    lw = d.get("label_width", "3.2cm")
    if not re.fullmatch(r"\d+(\.\d+)?(cm|mm|em|pt|in)", str(lw)):
        C.die(f"label_width 寫法不對：{lw!r}（例如 \"3.2cm\"）")
    ncol = 3 if has_pc else 2
    blank = " & " if has_pc else ""

    # 佐證頁序
    order: list[int] = []
    pos: dict[int, int] = {}
    mapping = []  # (說明, 原始頁, 新頁)
    limit_errors = []
    lines = []
    for i, r in enumerate(d["rows"], 1):
        t = r["type"]
        if t == "section":
            title = md(r["title"])
            if r.get("title_en"):
                title += r"\quad{\small " + md(r["title_en"]) + "}"
            if has_pc:
                lines.append(r"\multicolumn{2}{|l|}{\cellcolor{hd}\textbf{" + title + r"}} & "
                             r"\cellcolor{hd}{\footnotesize\textbf{" + C.tex(d["proof_column"]) + r"}} \\ \hline")
            else:
                lines.append(r"\multicolumn{2}{|l|}{\cellcolor{hd}\textbf{" + title + r"}} \\ \hline")
        elif t == "kv":
            label = r"\textbf{" + md(r["label"]) + "}"
            if r.get("label_en"):
                label += r"\newline{\footnotesize " + md(r["label_en"]) + "}"
            lines.append(f"{label} & {md(r['value'])}{blank} \\\\ \\hline")
        elif t == "text":
            label = r"\textbf{" + md(r["label"]) + "}"
            if r.get("label_en"):
                label += r"\newline{\footnotesize " + md(r["label_en"]) + "}"
            mode = r.get("count", "nospace")
            n = C.count_text(as_text(r["value"]), mode)
            if "limit" in r:
                ok = n <= r["limit"]
                print(f"{as_text(r['label'])}：{n} / {r['limit']}（{C.COUNT_SHORT[mode]}）{'OK' if ok else '超過！'}")
                if not ok:
                    limit_errors.append(f"rows 第 {i} 列「{as_text(r['label'])}」超過字數上限：{n} > {r['limit']}")
            lines.append(f"{label} & {md(r['value'])}{blank} \\\\ \\hline")
        else:  # item
            cell = md(r["text"])
            if r.get("text_en"):
                cell += r"\newline{\small " + md(r["text_en"]) + "}"
            kind, val = parse_proof(r.get("proof"))
            proof_cell = ""
            if kind == "pages":
                news = []
                for pg in val:
                    if pg not in pos:
                        order.append(pg)
                        pos[pg] = len(order)
                    news.append(pos[pg] + offset)
                proof_cell = fmt_new_pages(news)
                mapping.append((as_text(r["text"]), C.format_ranges(val), proof_cell))
            elif kind == "label":
                proof_cell = val
            elif kind == "none":
                proof_cell = "—"
            row = f"{md(r.get('period', ''))} & {cell}"
            if has_pc:
                row += r" & {\small " + C.tex(proof_cell) + "}"
            lines.append(row + r" \\ \hline")

    notes = d.get("note") or []
    if isinstance(notes, str):
        notes = [notes]
    note_tex = "\n".join(r"{\footnotesize " + md(x) + r"\par}" for x in notes)
    colspec = "|L{" + lw + "}|Y|" + ("P{1.4cm}|" if has_pc else "")
    title = C.tex(d["title"])
    subtitle = (r"\vspace{0.15em}{\bfseries " + C.tex(d["subtitle"]) + r"\par}") if d.get("subtitle") else ""
    body = "\n".join(lines)
    fs = d.get("font_size", 10)

    def make_tex(pre: str) -> str:
        return rf"""%!TEX program = xelatex
\documentclass[{fs}pt, a4paper]{{article}}
{pre}
\usepackage[top=1.2cm, bottom=1.2cm, left=1.5cm, right=1.5cm]{{geometry}}
\usepackage{{array, xltabular, colortbl, xcolor, setspace}}
\definecolor{{hd}}{{RGB}}{{226, 233, 241}}
\pagestyle{{empty}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\LTpre}}{{0pt}}
\setlength{{\LTpost}}{{0.4em}}
\renewcommand{{\arraystretch}}{{1.15}}
\setstretch{{1.05}}
\newcolumntype{{L}}[1]{{>{{\raggedright\arraybackslash}}p{{#1}}}}
\newcolumntype{{P}}[1]{{>{{\centering\arraybackslash}}p{{#1}}}}
\newcolumntype{{Y}}{{>{{\raggedright\arraybackslash}}X}}
\begin{{document}}
{{\centering{{\large\bfseries {title}\par}}{subtitle}\par}}
\vspace{{0.6em}}
\begin{{xltabular}}{{\textwidth}}{{{colspec}}}
\hline
{body}
\end{{xltabular}}
{note_tex}
\end{{document}}
"""

    raw_json = json.dumps(d, ensure_ascii=False)
    need_cjk = C.has_cjk(raw_json)
    fonts = C.Fonts(args.latin_font, args.cjk_font, cjk_style="serif")
    jobname = re.sub(r"[^\w\-]+", "_", os.path.splitext(os.path.basename(args.output))[0]) or "form"
    C.compile_latex(make_tex, args.output, fonts, need_cjk, jobname=jobname, keep_build=args.keep_build)

    pypdf = C.require_pypdf()
    pages = len(pypdf.PdfReader(args.output).pages)
    print(f"已產出：{args.output}")
    over = args.max_pages > 0 and pages > args.max_pages
    if args.max_pages > 0:
        print(f"頁數：{pages}（上限 {args.max_pages}，{'超過！' if over else 'OK'}）")
    else:
        print(f"頁數：{pages}")
    print(f"字型：{fonts.describe(need_cjk)}")

    if order:
        o = C.format_ranges(order)
        print(f"\n佐證頁序（依表格由上到下、有證明的項目；重複頁只算一次）：{o}")
        print(f'  → python3 reorder_proofs.py 佐證合輯.pdf 佐證_重排.pdf --order "{o}"')
        print("對照（原始頁 → 重排後頁）：")
        for text, old, new in mapping:
            short = text if len(text) <= 28 else text[:27] + "…"
            print(f"  {short}：p{old} → {new}")
        if offset:
            print(f"（重排後頁碼已加上 proof_page_offset = {offset}）")

    for e in limit_errors:
        print(f"錯誤：{e}", file=sys.stderr)
    if over:
        print(f"超過頁數上限：{pages} > {args.max_pages}。可以縮短文字、把 font_size 改小或縮窄 label_width。",
              file=sys.stderr)
    return C.EXIT_LIMIT if (over or limit_errors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
