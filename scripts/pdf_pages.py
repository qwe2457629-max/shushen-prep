#!/usr/bin/env python3
"""把 PDF 頁面轉成 PNG，供目視檢查排版（有沒有溢出、中文有沒有變方塊、破折號對不對）；也可以先抽文字。

用法：
  python3 pdf_pages.py INPUT.pdf OUTDIR [--pages "1,3-5"] [--white-bg] [--text] [--dpi 110]
                       [--engine auto|sips|pdftoppm|pymupdf]

轉圖工具（--engine auto 時依序找）：
  macOS 內建的 sips → pdftoppm（Linux 安裝 poppler-utils）→ PyMuPDF（pip3 install pymupdf，選用）
  都沒有就會報錯並告訴你怎麼裝。
--white-bg：把透明背景貼成白底。sips 轉出的 PNG 背景是透明的，有些看圖程式會顯示成黑底。需要 Pillow。
--text：先用 pypdf 抽出文字存成 .txt。抽不出字（掃描檔）或抽出來像亂碼（簡章常用的 CID 字型常見）
  的頁面，會提示你改看圖片，並自動把那幾頁轉成 PNG。
輸出檔名：OUTDIR/<PDF 檔名>-p001.png、OUTDIR/<PDF 檔名>-p001.txt（頁碼 1 起算）。

離開代碼：0 = 成功；2 = 檔案不存在、找不到轉圖工具等錯誤。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

# 常用繁體字（用來判斷抽出來的中文是不是亂碼：正常中文裡這些字的比例不會太低）
COMMON = set(
    "的一是不了在人有我他這個們中來上大為和國地到以說時要就出會可也你對生能而子那得於著下自之年過"
    "發後作裡用道行所然家種事成方多經麼去法學如都同現當沒動面起看定天分還進好小部其些主樣理心她本前"
    "開但因只從想實日者意無力它與長把機十民第公此已工使情明性知全三又關點正業外將兩高間由問很最重並"
    "物手應向頭文體政美相見被利什二等產或新己制身果加西月話合回特代內信表化老給世位次度門任常先海通"
    "教原東聲提立及比員解水名真論處走義各入幾口認條平系氣題活更別打女變四神總何電數安少報才結反受目"
    "太量再感建務做接必場件計管期市直資命山金指許統區保至形社便空決治展科司五基書非則白界達光放強即"
    "像難且權思王象完設式色路記南品住告類求據程北邊張該交規萬取格望覺術領共確傳師觀清今切院讓識候帶"
    "導運步改收根造言聯持組每濟車親極林服快辦議往元士證近失轉令準布始存未遠台單影具字愛流備連調深商"
    "算質團集百需價華城級整府離況請技際約示復究線似官斷精滿支視消越器容照須九增研寫稱企八功包片史委"
    "查易早除農找裝廣顯圖念六引歷首醫局專費號另周較注語僅考落青隨選列紅響雖推勢參希古眾構房半節土投"
    "案維劃致律足態護七興驗責營章音跟志底站嚴例防族供效續施留講型料終答緊黃絕察段依批群項故按河圍江"
    "織害雙境客紀舉父密低友止細願千值仍男錢破網熱助育屬坐限職速刻否剛狀率甚獨球般普校苦創假久錯承印"
    "試股預益陽若微繼送急素藥適初喜衛源食險待述陸習置居勞財環排福納獲模充負停木疑層冷略範句室異激策"
    "演簡判擔退既宗積餘檢差富協角配修擇名生甄審簡章碩班錄取繳附件截止日期申請"
)


def text_quality(text: str) -> str:
    """回傳 'ok'、'empty'（幾乎沒字）或 'garbled'（像亂碼）。"""
    s = re.sub(r"\s", "", text)
    if len(s) < 10:
        return "empty"
    if "(cid:" in text:
        return "garbled"
    bad = sum(1 for c in s if c == "�" or unicodedata.category(c) in ("Co", "Cn", "Cc", "Cs"))
    if bad / len(s) > 0.05:
        return "garbled"
    han = [c for c in s if C.HAN_RE.match(c)]
    if len(han) >= 30:
        if sum(1 for c in han if c in COMMON) / len(han) < 0.12:
            return "garbled"
        if sum(1 for c in han if 0x3400 <= ord(c) <= 0x4DBF) / len(han) > 0.05:
            return "garbled"
    s2 = re.sub(r"([.\-_=·…‧．。])\1{2,}", "", s)  # 目錄頁的點線 ...... 不算
    ascii_ = [c for c in s2 if ord(c) < 128]
    if len(ascii_) >= 50 and len(han) < len(ascii_):
        if sum(1 for c in ascii_ if c.isalnum()) / len(ascii_) < 0.55:
            return "garbled"
    return "ok"


def fix_radicals(text: str) -> tuple[str, int]:
    """CID 字型的 PDF 常把一般漢字抽成長得一樣的「康熙部首」字元（⼠ U+2F20 ≠ 士 U+58EB），
    搜尋、比對都會失敗。這裡把部首字元換回對應的一般漢字。"""
    out, n = [], 0
    for c in text:
        if 0x2E80 <= ord(c) <= 0x2FDF:
            k = unicodedata.normalize("NFKC", c)
            if k != c:
                n += 1
                c = k
        out.append(c)
    return "".join(out), n


def pick_engine(want: str) -> str:
    has = {
        "sips": sys.platform == "darwin" and shutil.which("sips") is not None,
        "pdftoppm": shutil.which("pdftoppm") is not None,
    }
    try:
        import fitz  # noqa: F401
        has["pymupdf"] = True
    except ImportError:
        has["pymupdf"] = False
    if want != "auto":
        if not has.get(want):
            C.die(f"找不到轉圖工具 {want}。" + {
                "sips": "sips 只有 macOS 才有。",
                "pdftoppm": "請安裝 poppler-utils（例如 apt install poppler-utils）。",
                "pymupdf": "請執行：pip3 install pymupdf",
            }[want])
        return want
    for e in ("sips", "pdftoppm", "pymupdf"):
        if has[e]:
            return e
    C.die("找不到把 PDF 轉成圖片的工具。macOS 內建 sips；Linux 請安裝 poppler-utils（提供 pdftoppm）；"
          "或執行 pip3 install pymupdf。")
    return ""


def render(engine: str, reader, src: str, idx: int, dpi: int, out_png: str) -> None:
    """idx：0 起算的頁碼。"""
    if engine == "sips":
        pypdf = C.require_pypdf()
        w = pypdf.PdfWriter()
        page = w.add_page(reader.pages[idx])
        page.scale_by(dpi / 72.0)  # sips 以 72 dpi 點陣化，先放大頁面才清楚
        tmp = tempfile.mkdtemp(prefix="shushen-png-")
        try:
            one = os.path.join(tmp, "page.pdf")
            with open(one, "wb") as f:
                w.write(f)
            r = subprocess.run(["sips", "-s", "format", "png", one, "--out", out_png],
                               capture_output=True, text=True)
            if r.returncode != 0 or not os.path.exists(out_png):
                C.die(f"sips 轉第 {idx + 1} 頁失敗：{(r.stderr or r.stdout).strip()[-500:]}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    elif engine == "pdftoppm":
        prefix = out_png[:-4]
        r = subprocess.run(["pdftoppm", "-png", "-r", str(dpi), "-f", str(idx + 1), "-l", str(idx + 1),
                            "-singlefile", src, prefix], capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(out_png):
            C.die(f"pdftoppm 轉第 {idx + 1} 頁失敗：{(r.stderr or r.stdout).strip()[-500:]}")
    else:
        import fitz
        doc = fitz.open(src)
        doc[idx].get_pixmap(dpi=dpi).save(out_png)
        doc.close()


def has_alpha(path: str) -> bool:
    try:
        from PIL import Image
    except ImportError:
        return False
    with Image.open(path) as im:
        return im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)


def white_bg(path: str) -> None:
    Image = C.require_pil("--white-bg 選項")
    with Image.open(path) as im:
        im.load()
        if im.mode not in ("RGBA", "LA", "P"):
            return
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
    bg.save(path)


def main() -> int:
    p = C.ZhArgumentParser(prog="pdf_pages.py", description=__doc__)
    p.add_argument("pdf", metavar="INPUT.pdf", help="要檢查的 PDF")
    p.add_argument("outdir", metavar="OUTDIR", help="輸出資料夾（不存在會自動建立）")
    p.add_argument("--pages", metavar="頁碼", help='只處理這些頁，例如 "1,3-5"（預設全部）')
    p.add_argument("--white-bg", action="store_true", help="透明背景貼成白底（需要 Pillow）")
    p.add_argument("--text", action="store_true", help="改成抽文字；抽不出或像亂碼的頁才轉圖")
    p.add_argument("--dpi", type=int, default=110, help="解析度（預設 110；要看小字可用 150）")
    p.add_argument("--engine", choices=["auto", "sips", "pdftoppm", "pymupdf"], default="auto",
                   help="轉圖工具（預設 auto）")
    args = p.parse_args()

    if not 30 <= args.dpi <= 600:
        C.die("--dpi 請填 30 到 600 之間")
    if args.white_bg:
        C.require_pil("--white-bg 選項")
    reader = C.open_pdf(args.pdf)
    total = len(reader.pages)
    pages = C.parse_pages(args.pages, total, "--pages") if args.pages else list(range(1, total + 1))
    os.makedirs(args.outdir, exist_ok=True)
    stem = re.sub(r"[^\w\-]+", "_", os.path.splitext(os.path.basename(args.pdf))[0]) or "page"

    to_render = pages
    if args.text:
        to_render = []
        print(f"抽文字：{args.pdf}（共 {total} 頁，處理 {len(pages)} 頁）")
        for pg in pages:
            try:
                txt = reader.pages[pg - 1].extract_text() or ""
            except Exception as e:  # noqa: BLE001
                txt = ""
                C.warn(f"第 {pg} 頁抽字失敗：{e}")
            txt, n_rad = fix_radicals(txt)
            path = os.path.join(args.outdir, f"{stem}-p{pg:03d}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(txt)
            if n_rad:
                print(f"  （第 {pg} 頁有 {n_rad} 個「部首字元」，例如把「士」抽成「⼠」；.txt 裡已換回正常字，"
                      "但直接從 PDF 複製的文字仍要小心）")
            q = text_quality(txt)
            n = len(re.sub(r"\s", "", txt))
            if q == "ok":
                first = next((ln.strip() for ln in txt.splitlines() if ln.strip()), "")
                print(f"  第 {pg} 頁：{n} 字 → {path}｜開頭：{first[:30]}")
            else:
                why = "幾乎抽不出字（可能是掃描圖檔）" if q == "empty" else "抽出來像亂碼（常見於 CID 字型的簡章）"
                print(f"  第 {pg} 頁：{why}，請改看圖片")
                to_render.append(pg)
        if not to_render:
            return 0

    engine = pick_engine(args.engine)
    outs = []
    for pg in to_render:
        out = os.path.join(args.outdir, f"{stem}-p{pg:03d}.png")
        render(engine, reader, args.pdf, pg - 1, args.dpi, out)
        if args.white_bg:
            white_bg(out)
        outs.append(out)
    print(f"轉圖（{engine}，{args.dpi} dpi）：{len(outs)} 張")
    for o in outs:
        print(f"  {o}")
    if not args.white_bg and outs and has_alpha(outs[0]):
        print("（PNG 背景是透明的；如果看起來是黑底，加 --white-bg 重跑）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
