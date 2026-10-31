#!/usr/bin/env python3
"""依指定頁序重排一份佐證合輯（例如「其他有利審查資料」），預設移除超連結與書籤。

用法：
  python3 reorder_proofs.py BUNDLE.pdf OUTPUT.pdf --order "8,7,6,2,4" [--keep-links] [--keep-outline]
                            [--max-mb N] [--compress]

--order 寫法：1 起算的原始頁碼，逗號分隔，照你要的新順序排。
  - 可寫範圍：3-4（遞增）、5-3（倒序）、6-（第 6 頁到最後一頁）
  - 可直接貼 render_form.py 印出的順序，或 p8,p7,p6 這種寫法
  - 沒寫到的頁不會放進輸出檔（會列出來提醒你）；同一頁寫兩次會出現兩次（會提醒）

為什麼預設移除超連結與書籤：很多簡章規定上傳的 PDF 不得有超連結或書籤，
而且重排後原本的書籤與頁內連結會指到錯的頁。

離開代碼：0 = 成功；1 = 超過 --max-mb；2 = 檔案不存在、頁碼寫錯等錯誤。
"""

from __future__ import annotations

import os
import sys
from collections import Counter

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402


def copy_outline(reader, writer, order: list[int]) -> int:
    """把原本的書籤（攤平成一層）對應到新頁碼；指到沒被選用頁面的書籤略過。"""
    first_pos = {}
    for new_idx, old in enumerate(order):
        first_pos.setdefault(old - 1, new_idx)
    n = 0

    def walk(items):
        nonlocal n
        for it in items:
            if isinstance(it, list):
                walk(it)
                continue
            try:
                old = reader.get_destination_page_number(it)
            except Exception:  # noqa: BLE001
                continue
            if old in first_pos:
                writer.add_outline_item(str(it.title), first_pos[old])
                n += 1

    try:
        walk(reader.outline)
    except Exception:  # noqa: BLE001
        pass
    return n


def main() -> int:
    p = C.ZhArgumentParser(prog="reorder_proofs.py", description=__doc__)
    p.add_argument("bundle", metavar="BUNDLE.pdf", help="原本的佐證合輯 PDF")
    p.add_argument("output", metavar="OUTPUT.pdf", help="重排後的輸出 PDF")
    p.add_argument("--order", required=True, metavar="頁序", help='（必填）新頁序，例如 "8,7,6,2,4" 或 "p3,p1,5-6"')
    p.add_argument("--keep-links", action="store_true", help="保留超連結（預設移除）")
    p.add_argument("--keep-outline", action="store_true", help="保留書籤並對應到新頁碼（預設移除）")
    p.add_argument("--max-mb", type=float, metavar="N", help="檔案大小上限（MB）；超過時離開代碼為 1")
    p.add_argument("--compress", action="store_true",
                   help="超過 --max-mb 時，把內嵌圖片縮到寬 2000px、JPEG 品質 80 再試（需要 Pillow）")
    args = p.parse_args()

    if os.path.abspath(args.bundle) == os.path.abspath(args.output):
        C.die("輸出檔不能跟原本的合輯同一個（會覆蓋掉原檔）")
    pypdf = C.require_pypdf()
    r = C.open_pdf(args.bundle)
    total = len(r.pages)
    order = C.parse_pages(args.order, total, "--order")

    dup = sorted(pg for pg, k in Counter(order).items() if k > 1)
    if dup:
        C.warn(f"這些頁出現不只一次：{dup}（會重複放進輸出檔）")
    unused = [pg for pg in range(1, total + 1) if pg not in set(order)]

    w = pypdf.PdfWriter()
    for pg in order:
        w.add_page(r.pages[pg - 1])
    C.drop_outline(w)
    n_marks = copy_outline(r, w, order) if args.keep_outline else 0
    removed = 0 if args.keep_links else C.strip_links(w)
    C.write_pdf(w, args.output)

    st = C.pdf_stats(args.output)
    if args.max_mb and st["mb"] > args.max_mb and args.compress:
        before = st["mb"]
        n_img = C.shrink_pdf(w)
        C.write_pdf(w, args.output)
        st = C.pdf_stats(args.output)
        print(f"超過 {args.max_mb:g} MB，已壓縮 {n_img} 張圖片：{before:.2f} MB → {st['mb']:.2f} MB")

    C.print_stats(args.output, st, args.max_mb)
    print(f"新順序（原始頁碼）：{C.format_ranges(order)}")
    if not args.keep_links:
        print(f"（已移除 {removed} 個超連結）")
    if args.keep_outline:
        print(f"（保留 {n_marks} 個書籤，已對應到新頁碼）")
    if args.keep_links and st["links"]:
        C.warn("保留的超連結裡，若有指向 PDF 內其他頁的連結，重排後可能會指錯頁")
    if unused:
        print(f"注意：原檔有 {len(unused)} 頁沒放進輸出檔：{C.format_ranges(unused)}")

    if args.max_mb and st["mb"] > args.max_mb:
        hint = "" if args.compress else "可以加 --compress 再試，"
        print(f"超過大小上限：{st['mb']:.2f} MB > {args.max_mb:g} MB。{hint}或把掃描檔改用較低解析度重掃。",
              file=sys.stderr)
        return C.EXIT_LIMIT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
