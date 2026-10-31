#!/usr/bin/env python3
"""把 Markdown 排成 A4 PDF（Markdown → LaTeX → tectonic），並印出頁數與字數。

用法：
  python3 md2pdf.py INPUT.md OUTPUT.pdf --lang zh|en [--header "頁首文字"] [--name "姓名"]
                    [--compact] [--max-pages N] [--latin-font F] [--cjk-font F] [--keep-build]

例：
  python3 md2pdf.py 讀書計畫.md 讀書計畫.pdf --lang zh \\
      --header "OO大學 永續管理研究所｜讀書計畫" --name "林小安"
  python3 md2pdf.py 自傳.md 自傳.pdf --lang zh --compact --max-pages 1

支援的 Markdown：
  # 文件標題（第一個 # 當標題，置中；姓名顯示在標題下）
  ## 小標、### 次小標
  段落（空行分段；行尾兩個空白或反斜線 = 段內換行）
  - 項目符號、1. 編號清單（縮排 2 格以上 = 第二層）
  **粗體**、*斜體*、--- 分隔線
  <!-- 註解 -->：不會出現在 PDF，也不算字數

自動處理：
  - 「–」（區間號，例如 2024–2026）用英文字型排成半形，不會被 xeCJK 排成全形長槓
  - 直引號 " ' 轉成彎引號；英文裡的彎引號、撇號用英文字型（I’m 不會變成全形）
  - LaTeX 特殊字元（& % $ # _ { } ~ ^ \\）自動跳脫

字數（不含文件標題與註解）：中文看「漢字」與「去空白字元」，英文看 words。
中間檔：預設放暫存資料夾、成功後刪除；加 --keep-build 會留在輸出檔旁的 _build/。
離開代碼：0 = 成功；1 = 超過 --max-pages（PDF 仍會產出，方便檢查）；2 = 檔案不存在、編譯失敗等錯誤。
"""

from __future__ import annotations

import os
import re
import sys

sys.dont_write_bytecode = True  # 不在 scripts/ 留 __pycache__
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

HR_RE = re.compile(r"(?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,}")
HEAD_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LIST_RE = re.compile(r"^(\s*)([-*+]|\d{1,3}[.)])\s+(.*)$")


# ---------------------------------------------------------------------------
# Markdown 解析
# ---------------------------------------------------------------------------

def _join_lines(raws: list[str]) -> str:
    """把同一段的多行接起來；行尾兩個空白或反斜線視為段內換行。"""
    out = ""
    for k, raw in enumerate(raws):
        t = raw.strip()
        hard = raw.endswith("  ") or t.endswith("\\")
        if t.endswith("\\"):
            t = t[:-1].rstrip()
        if out and not out.endswith(C._HARD_BREAK) and t:
            # 中文接中文不加空白（否則 CJKspace=true 會把換行變成空格）
            if not (C.is_cjk(out[-1]) and C.is_cjk(t[0])):
                out += " "
        out += t
        if hard and k < len(raws) - 1:
            out += C._HARD_BREAK
    return out


def parse(md: str):
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    title = None
    blocks: list[tuple] = []
    para: list[str] = []
    items: list[list] = []  # [level, kind, [raw lines]]

    def flush_para():
        if para:
            blocks.append(("p", _join_lines(para)))
            para.clear()

    def flush_list():
        if items:
            blocks.append(("list", [(lv, kind, _join_lines(lines)) for lv, kind, lines in items]))
            items.clear()

    for raw in md.splitlines():
        s = raw.strip()
        if not s:
            flush_para()
            flush_list()
            continue
        m = HEAD_RE.match(s)
        if m and not raw.startswith("    "):
            flush_para()
            flush_list()
            level, text = len(m.group(1)), m.group(2)
            if level == 1 and title is None:
                title = text
            elif level <= 2:
                blocks.append(("h2", text))
            else:
                blocks.append(("h3", text))
            continue
        if HR_RE.fullmatch(s):
            flush_para()
            flush_list()
            blocks.append(("hr",))
            continue
        m = LIST_RE.match(raw)
        if m:
            flush_para()
            indent = len(m.group(1).expandtabs(4))
            kind = "ol" if m.group(2)[0].isdigit() else "ul"
            items.append([1 if indent >= 2 else 0, kind, [m.group(3)]])
            continue
        if items:  # 清單項目的續行
            items[-1][2].append(raw)
            continue
        para.append(raw)
    flush_para()
    flush_list()
    return title, blocks


def render_list(items, compact: bool) -> str:
    sp = "itemsep=0.05em, topsep=0.15em, parsep=0pt" if compact else "itemsep=0.15em, topsep=0.25em, parsep=0pt"
    out: list[str] = []
    stack: list[tuple[int, str]] = []

    def open_env(level, kind):
        depth = len(stack)
        if kind == "ul":
            label = r"\textbullet" if depth == 0 else r"$\circ$"
            out.append(r"\begin{itemize}[label=" + label + ", leftmargin=1.5em, " + sp + "]")
        else:
            label = r"\arabic*." if depth == 0 else r"\alph*)"
            out.append(r"\begin{enumerate}[label=" + label + ", leftmargin=1.9em, " + sp + "]")
        stack.append((level, kind))

    def close_env():
        _, kind = stack.pop()
        out.append(r"\end{itemize}" if kind == "ul" else r"\end{enumerate}")

    for level, kind, text in items:
        while stack and stack[-1][0] > level:
            close_env()
        if stack and stack[-1][0] == level and stack[-1][1] != kind:
            close_env()
        if not stack or stack[-1][0] < level:
            open_env(level, kind)
        out.append(r"  \item " + C.inline_md(text))
    while stack:
        close_env()
    return "\n".join(out)


def render_body(blocks, compact: bool) -> str:
    out = []
    for b in blocks:
        kind = b[0]
        if kind == "p":
            out.append(C.inline_md(b[1]))
        elif kind == "h2":
            out.append(r"\section*{" + C.inline_md(b[1]) + "}")
        elif kind == "h3":
            out.append(r"\subsection*{" + C.inline_md(b[1]) + "}")
        elif kind == "hr":
            out.append(r"\noindent\rule{\linewidth}{0.4pt}")
        elif kind == "list":
            out.append(render_list(b[1], compact))
    return "\n\n".join(out)


# ---------------------------------------------------------------------------
# 字數
# ---------------------------------------------------------------------------

def count_words(md: str) -> dict:
    text = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    lines = []
    title_skipped = False
    for ln in text.splitlines():
        s = ln.strip()
        if not title_skipped and re.match(r"^#\s", s):
            title_skipped = True
            continue
        if HR_RE.fullmatch(s or "x"):
            continue
        s = re.sub(r"^#{1,6}\s+", "", s)
        s = re.sub(r"^([-*+]|\d{1,3}[.)])\s+", "", s)
        lines.append(C.strip_md(s))
    t = "\n".join(lines)
    return {m: C.count_text(t, m) for m in ("cjk", "nospace", "words")}


# ---------------------------------------------------------------------------
# LaTeX 版型
# ---------------------------------------------------------------------------

def build_tex(font_pre: str, title, body: str, args) -> str:
    zh = args.lang == "zh"
    if args.compact:
        cls = "11pt"
        size = r"\fontsize{10.5}{13}\selectfont"
        geo = "top=1.5cm, bottom=1.5cm, left=1.9cm, right=1.9cm, headheight=14pt, headsep=0.4cm, footskip=0.75cm"
        stretch = "1.12" if zh else "1.05"
        parskip = "0.35em"
        sec = (r"\titlespacing*{\section}{0pt}{0.55em}{0.25em}" "\n"
               r"\titlespacing*{\subsection}{0pt}{0.4em}{0.1em}")
        title_size, after_title = r"\large", "0.1em"
    else:
        cls = "12pt" if zh else "11pt"
        size = ""
        geo = "top=2.3cm, bottom=2.3cm, left=2.5cm, right=2.5cm, headheight=14pt"
        stretch = "1.3" if zh else "1.15"
        parskip = "0.55em" if zh else "0.5em"
        sec = ((r"\titlespacing*{\section}{0pt}{1.0em}{0.45em}" if zh
                else r"\titlespacing*{\section}{0pt}{0.9em}{0.4em}") + "\n"
               r"\titlespacing*{\subsection}{0pt}{0.7em}{0.2em}")
        title_size, after_title = r"\Large" if not zh else r"\large", "0.5em"

    header, name = args.header or "", args.name or ""
    if header or name:
        head = (r"\fancyhead[L]{\footnotesize\color{gray6} " + C.tex(header) + "}\n"
                r"\fancyhead[R]{\footnotesize\color{gray6} " + C.tex(name) + "}\n"
                r"\renewcommand{\headrulewidth}{0.3pt}")
    else:
        head = r"\renewcommand{\headrulewidth}{0pt}"

    title_block = ""
    if title or name:
        parts = []
        if title:
            parts.append("{" + title_size + r"\bfseries\color{deep} " + C.inline_md(title) + r"\par}")
        if name:
            parts.append(r"\vspace{0.15em}{\footnotesize\color{gray6} " + C.tex(name) + r"\par}")
        title_block = "{\\centering\n" + "\n".join(parts) + "\n\\par}\n\\vspace{" + after_title + "}\n"

    return rf"""%!TEX program = xelatex
\documentclass[{cls}, a4paper]{{article}}
{font_pre}
\usepackage[{geo}]{{geometry}}
\usepackage{{setspace}}
\usepackage{{titlesec}}
\usepackage{{fancyhdr}}
\usepackage{{enumitem}}
\usepackage{{xcolor}}
\definecolor{{deep}}{{RGB}}{{25, 55, 95}}
\definecolor{{gray6}}{{RGB}}{{95, 95, 95}}
\titleformat{{\section}}{{\normalsize\bfseries\color{{deep}}}}{{}}{{0em}}{{}}[{{\parskip=0pt\vspace{{0.1em}}\titlerule[0.5pt]}}]
\titleformat{{\subsection}}{{\normalsize\bfseries}}{{}}{{0em}}{{}}
{sec}
\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{{parskip}}}
\setlength{{\emergencystretch}}{{2em}}
\frenchspacing
\setstretch{{{stretch}}}
\raggedbottom
\pagestyle{{fancy}}
\fancyhf{{}}
{head}
\fancyfoot[C]{{\footnotesize\thepage}}
\begin{{document}}
{size}
{title_block}{body}
\end{{document}}
"""


# ---------------------------------------------------------------------------

def main() -> int:
    p = C.ZhArgumentParser(prog="md2pdf.py", description=__doc__)
    p.add_argument("input", metavar="INPUT.md", help="Markdown 原稿")
    p.add_argument("output", metavar="OUTPUT.pdf", help="輸出 PDF 路徑（資料夾不存在會自動建立）")
    p.add_argument("--lang", required=True, choices=["zh", "en"],
                   help="（必填）主要語言：zh 用 12pt、行距較寬；en 用 11pt。只影響版面與字數報告，中英混排都可以")
    p.add_argument("--header", metavar="文字", help="頁首左側文字，例如「OO大學 永續管理研究所｜讀書計畫」")
    p.add_argument("--name", metavar="姓名", help="姓名：顯示在標題下方與頁首右側")
    p.add_argument("--compact", action="store_true", help="單頁緊排版（自傳限一頁時用）：字小一點、邊界與行距收緊")
    p.add_argument("--max-pages", type=int, metavar="N", help="頁數上限；超過時離開代碼為 1")
    C.add_font_args(p)
    p.add_argument("--keep-build", action="store_true", help="把 .tex 與編譯紀錄留在輸出檔旁的 _build/（除錯用）")
    args = p.parse_args()

    C.need_file(args.input, "Markdown 檔")
    with open(args.input, encoding="utf-8-sig") as f:
        md = f.read()
    if not md.strip():
        C.die(f"Markdown 是空的：{args.input}")
    if os.path.abspath(args.output) == os.path.abspath(args.input):
        C.die("輸出檔不能跟輸入檔同一個")

    title, blocks = parse(md)
    if not title:
        C.warn("沒有找到「# 標題」，PDF 會沒有文件標題")
    body = render_body(blocks, args.compact)
    need_cjk = C.has_cjk(md) or C.has_cjk(args.header or "") or C.has_cjk(args.name or "")
    fonts = C.Fonts(args.latin_font, args.cjk_font, cjk_style="sans")
    jobname = re.sub(r"[^\w\-]+", "_", os.path.splitext(os.path.basename(args.output))[0]) or "doc"

    C.compile_latex(lambda pre: build_tex(pre, title, body, args), args.output, fonts,
                    need_cjk, jobname=jobname, keep_build=args.keep_build)

    pypdf = C.require_pypdf()
    pages = len(pypdf.PdfReader(args.output).pages)
    cnt = count_words(md)

    print(f"已產出：{args.output}")
    over = args.max_pages is not None and pages > args.max_pages
    if args.max_pages is not None:
        print(f"頁數：{pages}（上限 {args.max_pages}，{'超過！' if over else 'OK'}）")
    else:
        print(f"頁數：{pages}")
    if args.lang == "zh":
        line = f"漢字 {cnt['cjk']:,}｜去空白字元 {cnt['nospace']:,}"
        if cnt["words"]:
            line += f"｜英文 {cnt['words']:,} words"
    else:
        line = f"{cnt['words']:,} words"
        if cnt["cjk"]:
            line += f"（另有漢字 {cnt['cjk']:,} 個）"
    print(f"字數（不含文件標題與註解）：{line}")
    print(f"字型：{fonts.describe(need_cjk)}")
    if args.keep_build:
        print(f"中間檔：{os.path.join(os.path.dirname(os.path.abspath(args.output)), '_build')}")
    if over:
        print(f"超過頁數上限：{pages} > {args.max_pages}。可以刪減內容，或加 --compact。", file=sys.stderr)
        return C.EXIT_LIMIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
