#!/usr/bin/env python3
"""依清單把多個 PDF 合併成一份審查資料總檔：可自動產生目錄頁、加書籤、移除超連結、檢查並壓縮檔案大小。

用法：
  python3 merge_pdfs.py MANIFEST.json [--output OUT.pdf] [--base-dir DIR] [--latin-font F] [--cjk-font F]

MANIFEST.json 欄位（相對路徑預設以 manifest 所在資料夾為準，可用 --base-dir 改）：
  output       輸出 PDF 路徑（必填；或用 --output 覆寫）
  items        依序合併的項目（必填），每項：
                 title  標題（目錄與書籤用，必填）
                 file   PDF 路徑；省略時只在目錄列出，不合併（例如「推薦函由推薦人另行上傳」）
                 pages  只取部分頁，例如 "1-3,5"（1 起算；"3-" 表示第 3 頁到最後一頁）
                 note   目錄裡的小字備註（選填）
  toc          true＝在最前面自動產生目錄頁；頁碼＝合併後 PDF 的頁序，目錄超過一頁會自動重算
  toc_title    目錄頁標題（預設「目錄」）
  toc_intro    目錄上方的說明（字串或字串清單，例如考生姓名、報考系所；可用 **粗體**）
  toc_lang     "zh"（預設）或 "en"：目錄欄名與頁碼寫法
  bookmarks    true＝每個項目加一個書籤（有目錄頁時也會加「目錄」書籤）
  strip_links  true＝移除所有超連結（很多簡章規定上傳檔不得有超連結）
  max_mb       檔案大小上限（MB）；最後仍超過時離開代碼為 1
  compress     true＝超過 max_mb 時，把內嵌圖片縮到寬 2000px、轉 JPEG 品質 80 再試一次
  metadata     {"title": "...", "author": "..."}：PDF 文件屬性（選填；沒填作者就不寫）
  以底線開頭的欄位（例如 "_說明"）會被忽略，可以當註解用。

完成後回報：總頁數、MB、超連結數、書籤數，以及每個項目在總檔裡的頁碼。
離開代碼：0 = 成功；1 = 超過 max_mb；2 = 檔案不存在、manifest 格式錯誤、編譯失敗等。
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

KNOWN = {"output", "items", "toc", "toc_title", "toc_intro", "toc_lang", "bookmarks",
         "strip_links", "max_mb", "compress", "metadata"}
ITEM_KNOWN = {"title", "file", "pages", "note"}

LABELS = {
    "zh": {"item": "項目", "pages": "頁碼", "count": "頁數", "unit": "{n} 頁", "toc": "目錄",
           "foot": "頁碼為本 PDF 檔的頁序（即 PDF 閱讀器顯示的頁碼）。", "none": "—"},
    "en": {"item": "Item", "pages": "Pages", "count": "Count", "unit": "{n}", "toc": "Contents",
           "foot": "Page numbers refer to the page order of this PDF file.", "none": "—"},
}


def load_manifest(path: str) -> dict:
    C.need_file(path, "manifest")
    try:
        with open(path, encoding="utf-8-sig") as f:
            m = json.load(f)
    except json.JSONDecodeError as e:
        C.die(f"manifest 不是合法的 JSON：{path}（第 {e.lineno} 行第 {e.colno} 欄：{e.msg}）")
    if not isinstance(m, dict):
        C.die("manifest 最外層要是 {…} 物件")
    unknown = [k for k in m if k not in KNOWN and not k.startswith("_")]
    if unknown:
        C.warn(f"manifest 有看不懂的欄位，已忽略：{', '.join(unknown)}")
    items = m.get("items")
    if not isinstance(items, list) or not items:
        C.die("manifest 缺少 items（要合併的項目清單）")
    for i, it in enumerate(items, 1):
        if not isinstance(it, dict) or not isinstance(it.get("title"), str) or not it["title"].strip():
            C.die(f"items 第 {i} 項缺少 title")
        bad = [k for k in it if k not in ITEM_KNOWN and not k.startswith("_")]
        if bad:
            C.warn(f"items 第 {i} 項有看不懂的欄位，已忽略：{', '.join(bad)}")
        if it.get("file") is None and "pages" in it:
            C.die(f"items 第 {i} 項（{it['title']}）有 pages 但沒有 file")
    if m.get("toc_lang", "zh") not in LABELS:
        C.die("toc_lang 只能是 \"zh\" 或 \"en\"")
    mx = m.get("max_mb")
    if mx is not None and (not isinstance(mx, (int, float)) or mx <= 0):
        C.die("max_mb 要填正數，例如 15")
    return m


def toc_tex(pre: str, title: str, intro: list[str], rows: list[tuple], lang: str) -> str:
    L = LABELS[lang]
    body = []
    for t, note, span, count in rows:
        cell = C.inline_md(t)
        if note:
            cell += r"\newline{\small\color{gray6} " + C.inline_md(note) + "}"
        body.append(f"{cell} & {C.tex(span)} & {C.tex(count)} \\\\")
    intro_tex = "\n".join(C.inline_md(x) + r"\par" for x in intro)
    return rf"""%!TEX program = xelatex
\documentclass[11pt, a4paper]{{article}}
{pre}
\usepackage[top=2.5cm, bottom=2.3cm, left=2.5cm, right=2.5cm]{{geometry}}
\usepackage{{array, booktabs, xltabular, xcolor, setspace}}
\definecolor{{gray6}}{{RGB}}{{95, 95, 95}}
\pagestyle{{empty}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{0.3em}}
\setstretch{{1.2}}
\begin{{document}}
{{\centering{{\Large\bfseries {C.tex(title)}}}\par}}
\vspace{{1.2em}}
{intro_tex}
\vspace{{0.8em}}
\begin{{xltabular}}{{\textwidth}}{{@{{}}>{{\raggedright\arraybackslash}}X r r@{{}}}}
\toprule
\textbf{{{L['item']}}} & \textbf{{{L['pages']}}} & \textbf{{{L['count']}}} \\
\midrule
\endhead
{chr(10).join(body)}
\bottomrule
\end{{xltabular}}
\vspace{{0.4em}}
{{\small\color{{gray6}} {C.tex(L['foot'])}}}
\end{{document}}
"""


def main() -> int:
    p = C.ZhArgumentParser(prog="merge_pdfs.py", description=__doc__)
    p.add_argument("manifest", metavar="MANIFEST.json", help="合併清單（JSON）")
    p.add_argument("--output", "-o", metavar="OUT.pdf", help="輸出路徑（覆寫 manifest 的 output）")
    p.add_argument("--base-dir", metavar="DIR", help="manifest 內相對路徑的基準資料夾（預設：manifest 所在資料夾）")
    C.add_font_args(p)
    args = p.parse_args()

    m = load_manifest(args.manifest)
    base = os.path.abspath(args.base_dir or os.path.dirname(os.path.abspath(args.manifest)))
    if args.base_dir and not os.path.isdir(base):
        C.die(f"找不到 --base-dir 資料夾：{args.base_dir}")

    def resolve(x: str) -> str:
        x = os.path.expanduser(x)
        return x if os.path.isabs(x) else os.path.join(base, x)

    out_rel = args.output or m.get("output")
    if not out_rel:
        C.die("沒有指定輸出檔：請在 manifest 寫 output，或加 --output")
    out = os.path.abspath(args.output) if args.output else resolve(out_rel)

    lang = m.get("toc_lang", "zh")
    L = LABELS[lang]
    use_toc = bool(m.get("toc"))
    toc_title = m.get("toc_title") or L["toc"]
    intro = m.get("toc_intro") or []
    if isinstance(intro, str):
        intro = [intro]

    # 1) 讀每個項目的頁數
    plan = []  # (title, note, path or None, [pages])
    for i, it in enumerate(m["items"], 1):
        f = it.get("file")
        if not f:
            plan.append((it["title"], it.get("note"), None, []))
            continue
        path = resolve(f)
        if os.path.abspath(path) == os.path.abspath(out):
            C.die(f"items 第 {i} 項的檔案跟輸出檔是同一個：{path}")
        r = C.open_pdf(path)
        pages = (C.parse_pages(it["pages"], len(r.pages), f"items 第 {i} 項（{it['title']}）的 pages")
                 if it.get("pages") not in (None, "") else list(range(1, len(r.pages) + 1)))
        plan.append((it["title"], it.get("note"), path, pages))
    if not any(x[2] for x in plan):
        C.die("items 裡沒有任何一項有 file，沒有東西可以合併")

    def layout(toc_pages: int):
        rows, spans = [], []
        cur = toc_pages
        for title, note, path, pages in plan:
            if path is None:
                rows.append((title, note, L["none"], L["none"]))
                spans.append(None)
                continue
            a, b = cur + 1, cur + len(pages)
            rows.append((title, note, C.page_span(a, b, lang), L["unit"].format(n=len(pages))))
            spans.append((a, b))
            cur = b
        return rows, spans

    pypdf = C.require_pypdf()
    tmpdir = tempfile.mkdtemp(prefix="shushen-merge-")
    toc_pdf = os.path.join(tmpdir, "toc.pdf")
    toc_pages = 0
    if use_toc:
        need_cjk = C.has_cjk(toc_title + "".join(intro) + "".join(x[0] + (x[1] or "") for x in plan)) or lang == "zh"
        fonts = C.Fonts(args.latin_font, args.cjk_font, cjk_style="sans")
        toc_pages = 1
        for _ in range(4):
            rows, _spans = layout(toc_pages)
            C.compile_latex(lambda pre: toc_tex(pre, toc_title, intro, rows, lang),
                            toc_pdf, fonts, need_cjk, jobname="toc")
            n = len(pypdf.PdfReader(toc_pdf).pages)
            if n == toc_pages:
                break
            toc_pages = n
    rows, spans = layout(toc_pages)

    # 2) 合併
    w = pypdf.PdfWriter()
    if use_toc:
        w.append(toc_pdf, import_outline=False)
    for title, note, path, pages in plan:
        if path:
            w.append(path, pages=[x - 1 for x in pages], import_outline=False)

    C.drop_outline(w)
    if m.get("bookmarks"):
        if use_toc:
            w.add_outline_item(toc_title, 0)
        for (title, _n, _path, _p), sp in zip(plan, spans):
            if sp:
                w.add_outline_item(title, sp[0] - 1)
        w.page_mode = "/UseOutlines"  # 打開 PDF 時直接顯示書籤欄
    removed = C.strip_links(w) if m.get("strip_links") else 0

    meta = m.get("metadata") or {}
    info = {"/Title": str(meta.get("title") or os.path.splitext(os.path.basename(out))[0])}
    if meta.get("author"):
        info["/Author"] = str(meta["author"])
    w.add_metadata(info)
    C.write_pdf(w, out)

    # 3) 大小檢查與壓縮
    max_mb = m.get("max_mb")
    st = C.pdf_stats(out)
    if max_mb and st["mb"] > max_mb and m.get("compress"):
        before = st["mb"]
        n_img = C.shrink_pdf(w)
        C.write_pdf(w, out)
        st = C.pdf_stats(out)
        print(f"超過 {max_mb:g} MB，已壓縮 {n_img} 張圖片：{before:.2f} MB → {st['mb']:.2f} MB")

    C.print_stats(out, st, max_mb)
    if m.get("strip_links"):
        print(f"（已移除 {removed} 個超連結）")
    print("各項目位置：")
    if use_toc:
        print(f"  {toc_title}：{C.page_span(1, toc_pages, lang)}")
    for (title, note, path, pages), sp in zip(plan, spans):
        if sp:
            print(f"  {title}：{C.page_span(sp[0], sp[1], lang)}（{len(pages)} 頁）")
        else:
            print(f"  {title}：不在本檔" + (f"（{note}）" if note else ""))

    try:
        os.remove(toc_pdf)
        os.rmdir(tmpdir)
    except OSError:
        pass

    if max_mb and st["mb"] > max_mb:
        hint = "" if m.get("compress") else "可以在 manifest 加 \"compress\": true 再試，"
        print(f"超過大小上限：{st['mb']:.2f} MB > {max_mb:g} MB。{hint}或把掃描檔改用較低解析度重掃。",
              file=sys.stderr)
        return C.EXIT_LIMIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
