#!/usr/bin/env python3
"""shushen-prep 腳本的共用工具（給其他腳本 import，不是獨立指令）。

內容：
- 中文化的 argparse（--help 與參數錯誤訊息用繁體中文）
- 找 tectonic、偵測字型、編譯 LaTeX（自動偵測的字型找不到時，自動換下一個候選）
- LaTeX 跳脫，以及中英混排時引號、破折號的處理
- 字數計算、頁碼範圍解析、PDF 超連結／書籤的統計與移除、內嵌圖片壓縮

只用 Python 標準庫；pypdf 與 Pillow 在用到時才 import，缺了會給清楚的安裝指令。
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

# ---------------------------------------------------------------------------
# 錯誤處理與套件檢查
# ---------------------------------------------------------------------------

# 輸出接到管線時，stdout 預設整塊緩衝，會跟 stderr 的錯誤訊息順序錯亂；改成逐行輸出
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

EXIT_LIMIT = 1   # 超過頁數、字數、檔案大小等限制
EXIT_ERROR = 2   # 檔案不存在、參數錯誤、編譯失敗等


def die(msg: str, code: int = EXIT_ERROR) -> None:
    print(f"錯誤：{msg}", file=sys.stderr)
    raise SystemExit(code)


def warn(msg: str) -> None:
    print(f"提醒：{msg}", file=sys.stderr)


def require_pypdf():
    try:
        import pypdf  # noqa: F401
    except ImportError:
        die("缺少 pypdf 套件。請先執行：pip3 install pypdf")
    import logging
    import pypdf
    # pypdf 遇到小瑕疵（例如合併時丟掉指向未選頁面的連結）會印英文警告，對使用者沒有幫助
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    return pypdf


def require_pil(purpose: str):
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        die(f"缺少 Pillow 套件（{purpose}需要）。請先執行：pip3 install Pillow")
    from PIL import Image
    return Image


def need_file(path: str, what: str = "輸入檔") -> str:
    if not os.path.isfile(path):
        sep = " " if what[:1].isascii() else ""
        die(f"找不到{sep}{what}：{path}")
    return path


def ensure_parent(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)


# ---------------------------------------------------------------------------
# 中文化 argparse
# ---------------------------------------------------------------------------

class _ZhFormatter(argparse.RawDescriptionHelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        if prefix is None:
            prefix = "用法："
        return super().add_usage(usage, actions, groups, prefix)


_ARG_ERRORS = [
    (r"the following arguments are required: (.*)", r"缺少必要參數：\1"),
    (r"unrecognized arguments: (.*)", r"看不懂的參數：\1"),
    (r"argument (\S+): invalid choice: (.*) \(choose from (.*)\)", r"參數 \1 的值 \2 不在可選範圍（可選：\3）"),
    (r"argument (\S+): invalid int value: (.*)", r"參數 \1 要填整數，收到 \2"),
    (r"argument (\S+): invalid float value: (.*)", r"參數 \1 要填數字，收到 \2"),
    (r"argument (\S+): expected one argument", r"參數 \1 後面要接一個值"),
]


class ZhArgumentParser(argparse.ArgumentParser):
    """--help 與參數錯誤都用繁體中文的 ArgumentParser。"""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("formatter_class", _ZhFormatter)
        kwargs.setdefault("add_help", False)
        super().__init__(*args, **kwargs)
        self._positionals.title = "必要參數"
        self._optionals.title = "選用參數"
        self.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS,
                          help="顯示這份說明後結束")

    def error(self, message):
        for pat, rep in _ARG_ERRORS:
            if re.fullmatch(pat, message):
                message = re.sub(pat, rep, message)
                break
        self.print_usage(sys.stderr)
        print(f"錯誤：{message}（加 --help 看完整說明）", file=sys.stderr)
        raise SystemExit(EXIT_ERROR)


# ---------------------------------------------------------------------------
# tectonic
# ---------------------------------------------------------------------------

def find_tectonic() -> str:
    """依序找：環境變數 TECTONIC → PATH 上的 tectonic → ~/.local/bin/tectonic。"""
    env = os.environ.get("TECTONIC")
    if env and os.path.isfile(env) and os.access(env, os.X_OK):
        return env
    exe = shutil.which("tectonic")
    if exe:
        return exe
    local = os.path.expanduser("~/.local/bin/tectonic")
    if os.path.isfile(local) and os.access(local, os.X_OK):
        return local
    here = os.path.dirname(os.path.abspath(__file__))
    die("找不到 tectonic（LaTeX 編譯器）。請先執行：\n"
        f"    bash {os.path.join(here, 'install_tectonic.sh')}\n"
        "會安裝到 ~/.local/bin/tectonic，本工具會自動找到它。")
    return ""  # 不會執行到


# ---------------------------------------------------------------------------
# 字型
# ---------------------------------------------------------------------------

# tectonic 內建的 TeX Gyre Termes（Times 的開源版），任何平台都能用，當最後備案。
BUNDLED_TERMES = "TeX Gyre Termes（tectonic 內建）"
_TERMES_SPEC = (r"\setmainfont{texgyretermes}[Extension=.otf, UprightFont=*-regular, "
                r"BoldFont=*-bold, ItalicFont=*-italic, BoldItalicFont=*-bolditalic, Ligatures=TeX]")

_MAC_LATIN = ["Times New Roman"]
_MAC_CJK = {
    "sans": ["PingFang TC", "Songti TC", "Heiti TC"],
    "serif": ["Songti TC", "PingFang TC", "Heiti TC"],
}
_LINUX_LATIN = ["TeX Gyre Termes", "Noto Serif", "Liberation Serif", "DejaVu Serif"]
_LINUX_CJK = {
    "sans": ["Noto Serif CJK TC", "Noto Sans CJK TC", "Source Han Serif TC", "Source Han Sans TC",
             "AR PL UMing TW", "Noto Serif CJK SC", "Noto Sans CJK SC"],
    "serif": ["Noto Serif CJK TC", "Noto Sans CJK TC", "Source Han Serif TC", "Source Han Sans TC",
              "AR PL UMing TW", "Noto Serif CJK SC", "Noto Sans CJK SC"],
}


def _fc_families():
    exe = shutil.which("fc-list")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, ":", "family"], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    fams = set()
    for line in out.splitlines():
        for name in line.split(","):
            name = name.strip().replace("\\-", "-")
            if name:
                fams.add(name)
    return fams


class Fonts:
    """字型選擇。使用者有指定就只用指定的；沒指定就照平台給候選清單，編譯時找不到再換下一個。"""

    def __init__(self, latin: str | None = None, cjk: str | None = None, cjk_style: str = "sans"):
        self.user_latin = bool(latin)
        self.user_cjk = bool(cjk)
        is_mac = sys.platform == "darwin"
        fams = None if is_mac else _fc_families()

        if latin and latin.replace(" ", "").lower() in ("texgyretermes", "termes"):
            self.latin = [BUNDLED_TERMES]  # 指定用 tectonic 內建字型，不依賴系統
        elif latin:
            self.latin = [latin]
        elif is_mac:
            self.latin = list(_MAC_LATIN) + [BUNDLED_TERMES]
        else:
            cands = [f for f in _LINUX_LATIN if fams is None or f in fams]
            self.latin = cands + [BUNDLED_TERMES]

        if cjk:
            self.cjk = [cjk]
        elif is_mac:
            self.cjk = list(_MAC_CJK[cjk_style])
        else:
            pool = _LINUX_CJK[cjk_style]
            cands = [f for f in pool if fams is None or f in fams]
            self.cjk = cands or list(pool)

    def drop(self, name: str) -> bool:
        """編譯時發現字型不存在：從候選移除。還有別的候選可試就回傳 True。"""
        if self.latin and self.latin[0] == name and not self.user_latin and len(self.latin) > 1:
            self.latin.pop(0)
            return True
        if self.cjk and self.cjk[0] == name and not self.user_cjk and len(self.cjk) > 1:
            self.cjk.pop(0)
            return True
        return False

    def describe(self, need_cjk: bool) -> str:
        s = self.latin[0]
        if need_cjk:
            s += " ＋ " + self.cjk[0]
        return s

    def preamble(self, need_cjk: bool) -> str:
        lat = self.latin[0]
        lines = [r"\usepackage{fontspec}"]
        if lat == BUNDLED_TERMES:
            lines.append(_TERMES_SPEC)
        else:
            lines.append(_font_cmd(r"\setmainfont", lat, "Ligatures=TeX"))
        if need_cjk:
            lines.append(r"\usepackage{xeCJK}")
            # AutoFakeBold／AutoFakeSlant：有些中文字型（例如 Songti TC）抓不到粗體，中文字型也沒有斜體，
            # 用偽粗體、偽斜體保證 **粗體**、*斜體* 看得出來
            lines.append(_font_cmd(r"\setCJKmainfont", self.cjk[0], "AutoFakeBold=2.5, AutoFakeSlant=0.15"))
            # CJKspace=true：保留中文字之間刻意打的空白（例如「OO大學 永續管理研究所」）
            lines.append(r"\xeCJKsetup{PunctStyle=kaiming, CJKspace=true}")
        return "\n".join(lines)


def _font_cmd(cmd: str, font: str, opts: str) -> str:
    """字型可以是字型名稱，或字型檔路徑（.otf/.ttf/.ttc）。"""
    if font.lower().endswith((".otf", ".ttf", ".ttc")) or os.sep in font:
        path = os.path.abspath(os.path.expanduser(font))
        if not os.path.isfile(path):
            die(f"找不到字型檔：{font}")
        d, f = os.path.split(path)
        return cmd + "{" + f + "}[Path=" + d + "/, " + opts + "]"
    return cmd + "{" + font + "}[" + opts + "]"


def add_font_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--latin-font", metavar="F",
                        help="英文字型（字型名稱或 .otf/.ttf 路徑；寫 texgyretermes 會用 tectonic 內建字型）。"
                             "預設自動偵測：macOS 用 Times New Roman，Linux 用 TeX Gyre Termes 或 Noto Serif")
    parser.add_argument("--cjk-font", metavar="F",
                        help="中文字型（字型名稱或 .otf/.ttf/.ttc 路徑）。預設自動偵測："
                             "macOS 用 PingFang TC 或 Songti TC，Linux 用 Noto Serif/Sans CJK TC")


# ---------------------------------------------------------------------------
# 編譯
# ---------------------------------------------------------------------------

_FONT_MISSING = re.compile(r'The font "([^"]+)" cannot be found')


def _clean_log(text: str, n: int = 25) -> str:
    keep = [ln for ln in text.splitlines()
            if ln.strip() and "accessing absolute path" not in ln]
    return "\n".join(keep[-n:])


def compile_latex(make_tex, out_pdf: str, fonts: Fonts, need_cjk: bool,
                  jobname: str = "doc", keep_build: bool = False) -> str:
    """make_tex(font_preamble) 回傳完整 .tex 原始碼；編譯後複製到 out_pdf。

    中間檔：預設放在暫存資料夾、成功後刪掉；keep_build=True 時放在輸出檔旁的 _build/。
    編譯失敗時保留中間檔並印出位置。
    """
    tectonic = find_tectonic()
    ensure_parent(out_pdf)
    if keep_build:
        work = os.path.join(os.path.dirname(os.path.abspath(out_pdf)), "_build")
        os.makedirs(work, exist_ok=True)
    else:
        work = tempfile.mkdtemp(prefix="shushen-")
    tex_path = os.path.join(work, jobname + ".tex")
    pdf_path = os.path.join(work, jobname + ".pdf")

    while True:
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(make_tex(fonts.preamble(need_cjk)))
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        try:
            r = subprocess.run([tectonic, "--chatter", "minimal", "--keep-logs",
                                "--outdir", work, tex_path],
                               capture_output=True, text=True)
        except OSError as e:
            die(f"無法執行 tectonic：{e}")
        if r.returncode == 0 and os.path.exists(pdf_path):
            break
        log = (r.stderr or "") + "\n" + (r.stdout or "")
        m = _FONT_MISSING.search(log)
        if m and fonts.drop(m.group(1)):
            warn(f"本機找不到字型「{m.group(1)}」，改用「{fonts.describe(need_cjk)}」重試")
            continue
        hint = ""
        if m:
            hint = (f"\n本機找不到字型「{m.group(1)}」。請用 --latin-font / --cjk-font 指定本機有的字型"
                    "（Linux 可先安裝 fonts-noto-cjk）。")
        elif "network" in log.lower() or "download" in log.lower():
            hint = "\n第一次編譯需要網路下載 LaTeX 套件，請確認網路連線。"
        die(f"LaTeX 編譯失敗。中間檔保留在：{work}\n{_clean_log(log)}{hint}")

    shutil.copyfile(pdf_path, out_pdf)
    if not keep_build:
        shutil.rmtree(work, ignore_errors=True)
    return out_pdf


# ---------------------------------------------------------------------------
# 文字：CJK 判斷、引號與破折號、LaTeX 跳脫
# ---------------------------------------------------------------------------

def is_cjk(c: str) -> bool:
    if not c:
        return False
    o = ord(c)
    return (0x2E80 <= o <= 0x9FFF or 0xAC00 <= o <= 0xD7AF or 0xF900 <= o <= 0xFAFF
            or 0xFE30 <= o <= 0xFE4F or 0xFF00 <= o <= 0xFFEF or 0x20000 <= o <= 0x3FFFF)


def has_cjk(text: str) -> bool:
    return any(is_cjk(c) for c in text)


# 決定好「用英文字型排」的標點，先換成私用區佔位字，跳脫完再換回 TeX 連字寫法。
# 例：I’m 的 ’ 若直接交給 xeCJK，會被當成中文標點、用中文字型排成全形；
# 換成 TeX 的 ' 連字，xeCJK 視為英文字元、由英文字型轉成彎引號，寬度就正確。
_PH = {
    "\ue000": "{`}", "\ue001": "{'}", "\ue002": "{``}", "\ue003": "{''}",
    "\ue004": "{--}", "\ue005": "{---}", "\ue006": "...",
}
_LATIN_OF = {"‘": "\ue000", "’": "\ue001", "“": "\ue002", "”": "\ue003"}
_HARD_BREAK = "\u0001"
_SKIP = set(" \t*`" + _HARD_BREAK)
_OPENERS = set("([{<（「『【〔/—–-") | {_HARD_BREAK}
_CLOSERS = set(".,;:!?)]}>。，；：！？）」』】〕")


def _neighbor(s: str, i: int, step: int, skip=_SKIP) -> str:
    j = i + step
    while 0 <= j < len(s):
        if s[j] not in skip:
            return s[j]
        j += step
    return ""


def _latin_alnum(c: str) -> bool:
    return bool(c) and c.isalnum() and ord(c) < 0x2E80


def typographic(s: str) -> str:
    """直引號轉彎引號，並決定每個彎引號／破折號該用英文字型還是中文字型。

    - 英文脈絡的 ‘ ’ “ ” — … 與所有 –（區間號）→ 佔位字（之後轉成 TeX 連字，用英文字型、半形）
    - 中文脈絡的彎引號、——（中文破折號）、……（刪節號）維持原字，由中文字型排成全形
    """
    chars = list(s)
    n = len(chars)
    dq_open = True
    # 1) 直引號 → 彎引號
    for i, c in enumerate(chars):
        if c not in "\"'":
            continue
        prev = chars[i - 1] if i > 0 else ""
        nxt = chars[i + 1] if i + 1 < n else ""
        if c == '"':
            if not prev or prev.isspace() or prev in _OPENERS:
                opening = True
            elif not nxt or nxt.isspace() or nxt in _CLOSERS:
                opening = False
            else:
                opening = dq_open
            dq_open = not opening
            chars[i] = "“" if opening else "”"
        else:
            nxt2 = chars[i + 2] if i + 2 < n else ""
            if _latin_alnum(prev) and _latin_alnum(nxt):
                chars[i] = "’"
            elif nxt.isdigit() and nxt2.isdigit() and ord(nxt) < 128:
                chars[i] = "’"  # 年代縮寫：the ’90s
            elif not prev or prev.isspace() or prev in _OPENERS:
                chars[i] = "‘"
            else:
                chars[i] = "’"
    s = "".join(chars)
    # 2) 決定字型
    out = []
    for i, c in enumerate(s):
        if c in "“‘":
            ref = _neighbor(s, i, +1) or _neighbor(s, i, -1)
            out.append(c if is_cjk(ref) else _LATIN_OF[c])
        elif c in "”’":
            ref = _neighbor(s, i, -1) or _neighbor(s, i, +1)
            out.append(c if is_cjk(ref) else _LATIN_OF[c])
        elif c == "–":
            out.append("\ue004")
        elif c in "—…":
            skip = _SKIP | {c}
            p, q = _neighbor(s, i, -1, skip), _neighbor(s, i, +1, skip)
            if is_cjk(p) or is_cjk(q):
                out.append(c)
            else:
                out.append("\ue005" if c == "—" else "\ue006")
        else:
            out.append(c)
    return "".join(out)


_SPECIAL = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    "`": r"\textasciigrave{}", "\u00a0": "~", _HARD_BREAK: r"\newline{}",
}


def escape(s: str) -> str:
    """LaTeX 跳脫。佔位字（見 typographic）在這裡換成 TeX 連字。"""
    out = []
    for c in s:
        if c in _SPECIAL:
            out.append(_SPECIAL[c])
        elif c in _PH:
            out.append(_PH[c])
        elif c == "-":
            out.append("-{}")  # 避免使用者原文的 -- 被 TeX 連成破折號
        else:
            out.append(c)
    return "".join(out)


def tex(s: str) -> str:
    """純文字 → 可直接放進 LaTeX 的字串（含引號、破折號處理）。"""
    return escape(typographic(s))


# Markdown 行內語法：`code`、**粗體**、*斜體*、[文字](網址)
_INLINE = re.compile(
    r"(`[^`]+`"
    r"|\*\*(?=\S).+?(?<=\S)\*\*"
    r"|(?<![\*\w])\*(?=[^\s*])[^*]+?(?<=\S)\*(?!\*)"
    r"|\[[^\]]+\]\([^)\s]+\))")


def inline_md(s: str) -> str:
    """一段 Markdown 行內文字 → LaTeX。先整段處理引號（才看得到前後文），再拆語法。"""
    s = typographic(s)
    return _inline(s)


def _inline(s: str) -> str:
    out = []
    for part in _INLINE.split(s):
        if not part:
            continue
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append(r"\texttt{" + escape(part[1:-1]) + "}")
        elif part.startswith("**") and part.endswith("**") and len(part) > 4:
            out.append(r"\textbf{" + _inline(part[2:-2]) + "}")
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            out.append(r"\emph{" + _inline(part[1:-1]) + "}")
        elif part.startswith("[") and part.endswith(")") and "](" in part:
            out.append(_inline(part[1:part.index("](")]))
        else:
            out.append(escape(part))
    return "".join(out)


def strip_md(s: str) -> str:
    """去掉 Markdown 標記，留下計算字數用的純文字。"""
    s = re.sub(r"\[([^\]]+)\]\([^)\s]+\)", r"\1", s)
    s = s.replace("**", "")
    s = re.sub(r"(?<![\*\w])\*(?=\S)([^*]+?)(?<=\S)\*", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    return s


# ---------------------------------------------------------------------------
# 字數
# ---------------------------------------------------------------------------

HAN_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿\U00020000-\U0003ffff]")
WORD_RE = re.compile(r"[A-Za-z0-9À-ɏ]+(?:['’\-][A-Za-z0-9À-ɏ]+)*")

COUNT_MODES = {
    "chars": "全部字元（含空白與換行）",
    "nospace": "去空白字元（標點算、空白與換行不算）",
    "cjk": "漢字數（不含標點、英數）",
    "words": "英文單字數",
}


COUNT_SHORT = {"chars": "全部字元", "nospace": "去空白字元", "cjk": "漢字", "words": "英文單字"}


def count_text(text: str, mode: str) -> int:
    if mode == "chars":
        return len(text)
    if mode == "nospace":
        return len(re.sub(r"\s", "", text))
    if mode == "cjk":
        return len(HAN_RE.findall(text))
    if mode == "words":
        return len(WORD_RE.findall(text))
    raise ValueError(mode)


# ---------------------------------------------------------------------------
# 頁碼範圍
# ---------------------------------------------------------------------------

_RANGE_TOKEN = re.compile(r"^[pP]?(\d+)\s*(?:[-–~～]\s*[pP]?(\d*))?$")


def parse_pages(spec, total: int | None = None, what: str = "頁碼") -> list[int]:
    """'1-3,5'、'p8,p7'、'3-'（到最後一頁）、'5-3'（倒序）→ 1 起算的頁碼清單。"""
    if isinstance(spec, int):
        spec = str(spec)
    if what[-1:].isascii():
        what += " "  # 「--order 超出範圍」而不是「--order超出範圍」
    if not isinstance(spec, str) or not spec.strip():
        die(f"{what}是空的")
    pages: list[int] = []
    for tok in re.split(r"[,，、\s]+", spec.strip()):
        if not tok:
            continue
        m = _RANGE_TOKEN.match(tok)
        if not m:
            die(f"{what}「{spec}」看不懂其中的「{tok}」。寫法例如：1-3,5 或 p8,p7,p6")
        a = int(m.group(1))
        if m.group(2) is None:
            b = a
        elif m.group(2) == "":
            if total is None:
                die(f"{what}「{tok}」要寫結束頁")
            b = total
        else:
            b = int(m.group(2))
        step = 1 if b >= a else -1
        pages.extend(range(a, b + step, step))
    if total is not None:
        bad = [p for p in pages if p < 1 or p > total]
        if bad:
            die(f"{what}超出範圍：{bad}（這份 PDF 只有 {total} 頁）")
    return pages


def format_ranges(pages: list[int]) -> str:
    """[8,7,6,2,3,4] → '8,7,6,2-4'（只合併遞增連號）。"""
    out = []
    i = 0
    while i < len(pages):
        j = i
        while j + 1 < len(pages) and pages[j + 1] == pages[j] + 1:
            j += 1
        out.append(str(pages[i]) if i == j else f"{pages[i]}-{pages[j]}")
        i = j + 1
    return ",".join(out)


def page_span(a: int, b: int, lang: str = "zh") -> str:
    if lang == "en":
        return f"p. {a}" if a == b else f"pp. {a}–{b}"
    return f"第 {a} 頁" if a == b else f"第 {a}–{b} 頁"


# ---------------------------------------------------------------------------
# PDF：連結、書籤、壓縮、統計
# ---------------------------------------------------------------------------

def open_pdf(path: str):
    pypdf = require_pypdf()
    need_file(path, "PDF")
    try:
        r = pypdf.PdfReader(path)
    except Exception as e:  # noqa: BLE001
        die(f"讀不了這個 PDF：{path}（{e}）")
    if r.is_encrypted:
        try:
            ok = r.decrypt("")
        except Exception:  # noqa: BLE001
            ok = 0
        if not ok:
            die(f"這個 PDF 有密碼保護：{path}。請先用原本的軟體另存一份沒有密碼的 PDF。")
    return r


def _annots(page) -> list:
    a = page.get("/Annots")
    if a is None:
        return []
    try:
        return list(a.get_object())
    except Exception:  # noqa: BLE001
        return []


def _is_link(annot) -> bool:
    try:
        return annot.get_object().get("/Subtype") == "/Link"
    except Exception:  # noqa: BLE001
        return False


def strip_links(writer) -> int:
    """移除所有超連結註解（/Subtype /Link）。其他註解（表單欄位、註記）保留。回傳移除數。"""
    from pypdf.generic import ArrayObject, NameObject
    removed = 0
    for page in writer.pages:
        annots = _annots(page)
        if not annots:
            continue
        keep = [a for a in annots if not _is_link(a)]
        removed += len(annots) - len(keep)
        if keep:
            page[NameObject("/Annots")] = ArrayObject(keep)
        elif "/Annots" in page:
            del page["/Annots"]
    return removed


def drop_outline(writer) -> None:
    root = getattr(writer, "root_object", None)
    if root is None:
        root = writer._root_object  # 舊版 pypdf
    for key in ("/Outlines", "/PageMode"):
        if key in root:
            del root[key]


def count_outline(outline) -> int:
    n = 0
    for item in outline:
        n += count_outline(item) if isinstance(item, list) else 1
    return n


def pdf_stats(path: str) -> dict:
    r = open_pdf(path)
    links = other = 0
    for p in r.pages:
        for a in _annots(p):
            if _is_link(a):
                links += 1
            else:
                other += 1
    try:
        bookmarks = count_outline(r.outline)
    except Exception:  # noqa: BLE001
        bookmarks = 0
    return {"pages": len(r.pages), "mb": os.path.getsize(path) / 1048576,
            "links": links, "other_annots": other, "bookmarks": bookmarks}


def print_stats(path: str, st: dict, max_mb: float | None = None) -> None:
    lim = f"（上限 {max_mb:g} MB）" if max_mb else ""
    print(f"輸出：{path}")
    print(f"總頁數 {st['pages']}｜大小 {st['mb']:.2f} MB{lim}｜超連結 {st['links']} 個｜書籤 {st['bookmarks']} 個")
    if st["other_annots"]:
        print(f"（另有 {st['other_annots']} 個非連結註解，例如表單欄位或註記，沒有移除）")


def shrink_pdf(writer, max_width: int = 2000, quality: int = 80) -> int:
    """把內嵌圖片縮到最寬 max_width 像素、轉成 JPEG（quality），回傳處理的圖片數。

    黑白（1-bit）圖片與遮罩不動；透明背景會貼成白底。
    """
    Image = require_pil("壓縮 PDF 內的圖片")
    from io import BytesIO
    seen = set()
    done = 0
    for page in writer.pages:
        try:
            images = list(page.images)
        except Exception:  # noqa: BLE001
            continue
        for img in images:
            ref = getattr(img, "indirect_reference", None)
            if ref is None or ref.idnum in seen:
                continue
            seen.add(ref.idnum)
            try:
                obj = ref.get_object()
                if obj.get("/ImageMask"):
                    continue
                raw = getattr(obj, "_data", None) or b""
                pil = img.image
            except Exception:  # noqa: BLE001
                continue
            if pil.mode == "1":
                continue
            if pil.mode in ("RGBA", "LA", "PA", "P"):
                pil = pil.convert("RGBA")
                bg = Image.new("RGB", pil.size, (255, 255, 255))
                bg.paste(pil, mask=pil.split()[-1])
                pil = bg
            elif pil.mode not in ("RGB", "L"):
                pil = pil.convert("RGB")
            resized = False
            if pil.width > max_width:
                h = max(1, round(pil.height * max_width / pil.width))
                pil = pil.resize((max_width, h), Image.LANCZOS)
                resized = True
            buf = BytesIO()
            pil.save(buf, "JPEG", quality=quality, optimize=True)
            if not resized and raw and buf.tell() >= len(raw) * 0.9:
                continue  # 沒有比較小，就不換
            try:
                img.replace(pil, quality=quality)
                done += 1
            except Exception:  # noqa: BLE001
                continue
    try:
        writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    except Exception:  # noqa: BLE001
        pass
    return done


def write_pdf(writer, path: str) -> None:
    ensure_parent(path)
    with open(path, "wb") as f:
        writer.write(f)
