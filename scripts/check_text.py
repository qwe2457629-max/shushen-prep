#!/usr/bin/env python3
"""檢查要貼進報名系統「純文字欄位」的文字：字數、能不能用 Big5／CP950 編碼、有沒有危險字元。

用法：
  python3 check_text.py FILE.txt [--limit N] [--count chars|nospace|cjk|words]
                        [--encoding big5|cp950|utf-8] [--fix OUT.txt]

字數（四種都會印出，--limit 用 --count 指定的那一種比，預設 chars）：
  chars    全部字元（含空白與換行；多數網頁欄位的算法，最保守）
  nospace  去空白字元（標點算，空白與換行不算）
  cjk      漢字數（不含標點、英數）
  words    英文單字數
  檔案結尾的換行不算；Windows/Word 的 \\r\\n 先當成一個換行再算。

編碼：台灣很多報名系統還是 Big5／CP950，存不了的字會變成「?」或整欄被拒。預設檢查 cp950。

會列出的危險字元（彎引號 “ ” ‘ ’ 能正常編碼，不列）：
  [錯誤] 無法用指定編碼存的字（emoji、簡體字、罕用字、é 等）
  [錯誤] 看不見的字元：零寬空白、BOM、軟連字號、方向控制字元
  [錯誤] 特殊空白：NBSP（不換行空白）、窄空白等
  [錯誤] 控制字元、私用區（造字）字元
  [提醒] 特殊破折號 – —：能編碼，但不同系統的 Big5 對照表不一樣，可能被換成別的符號
  [提醒] Tab、Word 帶來的 \\r：有些系統會吃掉 Tab，或把一個換行算成兩個字
--fix OUT.txt：另存一份自動修正版（\\r、Tab、特殊空白、看不見的字元、少見的連字號），
  原檔不動。emoji、無法編碼的字與 – — 需要你自己決定怎麼改。

離開代碼：0 = 沒問題（只有[提醒]也算 0）；1 = 超過字數上限或有[錯誤]；2 = 檔案不存在等錯誤。
"""

from __future__ import annotations

import os
import sys
import unicodedata

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

ERR, WARN = "錯誤", "提醒"

INVISIBLE = {
    0x200B: "零寬空白", 0x200C: "零寬非連接符", 0x200D: "零寬連接符", 0x2060: "字詞連接符",
    0xFEFF: "BOM／零寬不換行空白", 0x00AD: "軟連字號", 0x200E: "左至右標記", 0x200F: "右至左標記",
    0x202A: "方向控制字元", 0x202B: "方向控制字元", 0x202C: "方向控制字元", 0x202D: "方向控制字元",
    0x202E: "方向控制字元", 0x2066: "方向控制字元", 0x2067: "方向控制字元", 0x2068: "方向控制字元",
    0x2069: "方向控制字元", 0x180E: "蒙古文母音分隔符", 0x2028: "行分隔符", 0x2029: "段落分隔符",
}
SPACES = {
    0x00A0: "不換行空白 NBSP", 0x2002: "en 空白", 0x2003: "em 空白", 0x2004: "1/3 em 空白",
    0x2005: "1/4 em 空白", 0x2006: "1/6 em 空白", 0x2007: "數字空白", 0x2008: "標點空白",
    0x2009: "細空白", 0x200A: "極細空白", 0x202F: "窄不換行空白", 0x205F: "數學空白", 0x1680: "歐甘空白",
}
RISKY_DASH = {0x2013: "區間號 en dash", 0x2014: "破折號 em dash"}
OTHER_DASH = {
    0x2010: "連字號 hyphen", 0x2011: "不換行連字號", 0x2012: "數字破折號", 0x2015: "水平線（常被當破折號）",
    0x2212: "減號", 0xFE58: "小型破折號", 0xFE63: "小型連字號", 0x2E3A: "雙倍破折號", 0x2E3B: "三倍破折號",
}
SUGGEST = {
    "–": "改成「-」；表示區間可改用「～」或「至」",
    "—": "英文改成「-」；中文破折號可改寫成逗號或括號",
    "・": "改成「·」", "〜": "改成「～」或「~」", "™": "改成「(TM)」或刪除",
    "©": "改成「(C)」或刪除", "®": "改成「(R)」或刪除", "℃": "改成「°C」",
    "―": "改成「—」或「-」",
}
FIX = {"\t": " ", "‐": "-", "‑": "-", "‒": "-", "−": "-",
       "﹘": "-", "﹣": "-", "―": "—", "・": "·"}


def is_emoji(o: int) -> bool:
    return 0x1F000 <= o <= 0x1FAFF or o in (0xFE0F, 0xFE0E, 0x20E3) or 0x1F3FB <= o <= 0x1F3FF


def classify(c: str, enc: str):
    """回傳 (等級, 說明, 建議) 或 None。"""
    o = ord(c)
    if c == "\r":
        return WARN, "Word／Windows 的 \\r", "改成一般換行（--fix 會處理）；有些系統會把 \\r\\n 算成 2 個字"
    if c == "\t":
        return WARN, "Tab", "改成空白（--fix 會處理）；網頁欄位常會吃掉 Tab"
    if o in INVISIBLE:
        return ERR, f"看不見的字元：{INVISIBLE[o]}", "刪除（--fix 會處理）"
    if o in SPACES:
        return ERR, f"特殊空白：{SPACES[o]}", "改成一般空白（--fix 會處理）"
    if is_emoji(o):
        return ERR, "emoji", "刪除，或改用文字描述"
    if 0xE000 <= o <= 0xF8FF or o >= 0xF0000:
        return ERR, "私用區字元（造字）", "換成標準字，或改寫"
    cat = unicodedata.category(c)
    if cat == "Cc" and c != "\n":
        return ERR, "控制字元", "刪除"
    encodable = True
    if enc != "utf-8":
        try:
            c.encode(enc)
        except UnicodeEncodeError:
            encodable = False
    if o in RISKY_DASH:
        if encodable:
            return WARN, f"特殊破折號：{RISKY_DASH[o]}（能編碼，但各系統的對照表不一樣，可能變成別的符號）", SUGGEST[c]
        return ERR, f"特殊破折號：{RISKY_DASH[o]}，無法用 {enc} 編碼", SUGGEST[c]
    if o in OTHER_DASH:
        return (ERR if not encodable else WARN), f"特殊破折號：{OTHER_DASH[o]}", SUGGEST.get(c, "改成「-」（--fix 會處理）")
    if not encodable:
        if c in SUGGEST:
            tip = SUGGEST[c]
        else:
            base = unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode()
            if base and base != c:
                tip = f"改成「{base}」"
            elif C.HAN_RE.match(c):
                tip = "可能是簡體字或罕用字：換成繁體常用字，或改寫"
            else:
                tip = "換成常見符號，或刪除"
        return ERR, f"無法用 {enc} 編碼", tip
    return None


def apply_fix(text: str) -> tuple[str, int]:
    n = 0
    out = []
    t = text.replace("\r\n", "\n")
    n += text.count("\r")
    t = t.replace("\r", "\n")
    for c in t:
        o = ord(c)
        if c in FIX:
            out.append(FIX[c])
            n += 1
        elif o in INVISIBLE:
            n += 1
        elif o in SPACES:
            out.append(" ")
            n += 1
        else:
            out.append(c)
    return "".join(out), n


def main() -> int:
    p = C.ZhArgumentParser(prog="check_text.py", description=__doc__)
    p.add_argument("file", metavar="FILE.txt", help="要檢查的文字檔（UTF-8；Big5 檔也讀得到）")
    p.add_argument("--limit", type=int, metavar="N", help="字數上限；超過時離開代碼為 1")
    p.add_argument("--count", choices=list(C.COUNT_MODES), default="chars",
                   help="--limit 用哪一種算法比（預設 chars）")
    p.add_argument("--encoding", choices=["big5", "cp950", "utf-8"], default="cp950",
                   help="報名系統的編碼（預設 cp950；不確定就用預設）")
    p.add_argument("--fix", metavar="OUT.txt", help="另存一份自動修正版（原檔不動）")
    args = p.parse_args()

    C.need_file(args.file, "文字檔")
    with open(args.file, "rb") as f:
        raw = f.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("cp950")
            C.warn("這個檔案不是 UTF-8，已改用 CP950（Big5）讀取")
        except UnicodeDecodeError:
            C.die(f"讀不懂這個檔案的編碼：{args.file}。請另存成 UTF-8 純文字檔。")

    norm = text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    counts = {m: C.count_text(norm, m) for m in C.COUNT_MODES}
    enc_label = args.encoding.upper()

    # 逐字檢查，同一個字元合併成一行
    found: dict[str, dict] = {}

    def record(ch, ln, cl):
        res = classify(ch, args.encoding)
        if res is not None:
            found.setdefault(ch, {"res": res, "where": []})["where"].append((ln, cl))

    line, col = 1, 0
    for i, c in enumerate(text):
        if c == "\n":
            line, col = line + 1, 0
            continue
        if c == "\r":
            record(c, line, 0)  # 0 = 行尾
            if i + 1 >= len(text) or text[i + 1] != "\n":  # 單獨的 \r 也當換行
                line, col = line + 1, 0
            continue
        col += 1
        record(c, line, col)

    print(f"檔案：{args.file}")
    print("字數：" + "｜".join(f"{C.COUNT_SHORT[m]} {counts[m]:,}" for m in C.COUNT_MODES))
    over = False
    if args.limit is not None:
        n = counts[args.count]
        over = n > args.limit
        verdict = f"超過 {n - args.limit} 字！" if over else f"還剩 {args.limit - n} 字"
        print(f"上限：{args.limit}（以{C.COUNT_SHORT[args.count]}計）→ {n}，{verdict}")

    errors = sum(1 for r in found.values() if r["res"][0] == ERR)
    unenc = [c for c, r in found.items() if "無法用" in r["res"][1]]
    if args.encoding == "utf-8":
        print("編碼：UTF-8（任何字都能存；但 emoji 等仍可能被系統擋）")
    else:
        print(f"編碼：{enc_label} → " + ("全部可以編碼" if not unenc else f"有 {len(unenc)} 種字元無法編碼"))

    if found:
        print(f"發現 {len(found)} 種需要注意的字元：")
        for c, r in sorted(found.items(), key=lambda kv: (kv[1]["res"][0] != ERR, kv[1]["where"][0])):
            level, desc, tip = r["res"]
            where = r["where"]
            pos = "、".join(f"第 {ln} 行第 {cl} 字" if cl else f"第 {ln} 行行尾" for ln, cl in where[:3])
            if len(where) > 3:
                pos += f" 等 {len(where)} 處"
            shown = {"\r": "\\r", "\t": "\\t"}.get(c, c if unicodedata.category(c)[0] not in "CZ" else " ")
            print(f"  [{level}] U+{ord(c):04X}「{shown}」{desc}｜{pos}")
            print(f"         → 建議：{tip}")
    else:
        print("沒有發現危險字元。")

    if args.fix:
        if os.path.abspath(args.fix) == os.path.abspath(args.file):
            C.die("--fix 的輸出檔不能跟原檔同一個")
        fixed, n_fix = apply_fix(text)
        C.ensure_parent(args.fix)
        with open(args.fix, "w", encoding="utf-8", newline="\n") as f:
            f.write(fixed)
        print(f"已另存修正版：{args.fix}（自動改了 {n_fix} 處；emoji、無法編碼的字與 – — 請自己改）")

    return C.EXIT_LIMIT if (over or errors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
