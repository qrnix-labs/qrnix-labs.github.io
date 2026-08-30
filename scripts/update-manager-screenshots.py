#!/usr/bin/env python3
"""Regenerate the QRNix Manager screenshots used on the manager page.

Runs the real qrnix-manager binary (--demo) in a PTY, drives it to the
Monitor, Firmware module, flash review, and active flash journey screens,
captures each frame from the terminal stream, and renders it to a PNG
framed as a terminal window (traffic-light dots, caption, site palette —
assets/manager/*.png).

Usage:
    python3 scripts/update-manager-screenshots.py [--binary PATH] [--out DIR]

Binary resolution (first match):
    --binary PATH
    the newest Linux archive under downloads/qrnix-manager/
    `qrnix-manager` on PATH

Requirements: python3 with Pillow, script(1), and the DejaVu Sans Mono
font. Re-run whenever a new manager release changes the UI, then commit
the regenerated PNGs alongside the release.

Notes:
    - The demo scripts a "second unit" episode (issue #42, C7): the first
      two flash confirmations are refused, the third flashes.
    - The write phase is too fast to capture, so the journey screenshot
      shows the Verifying stage (the post-flash verification wait).
    - "qrnix-demo" (the demo device name) is normalized to "QRNix" in the
      rendered text so the screenshots read like real hardware.
"""

import argparse
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent

# --- palette (site colors) -------------------------------------------------
BG = (7, 20, 33)            # navy-deep #071421
DIM = (125, 146, 168)       # slate     #7d92a8
BRIGHT = (245, 248, 252)    # off-white #f5f8fc
GREEN = (32, 217, 154)      # green     #20d99a
AMBER = (232, 182, 76)      # amber
CYAN = (101, 191, 232)      # #65bfe8
BLUE = (90, 155, 220)       # right-channel series
SEL_BG = (29, 59, 87)       # #1d3b57 selected row / reversed cells
DEFAULT = (215, 224, 232)   # body text

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
SCALE = 2

SESSION = [
    ("● CONNECTED", GREEN), ("QRNix", BRIGHT), ("serial", DIM),
    ("SERIAL", DIM), ("INSTALLED", DIM), ("VERIFIED", GREEN),
    ("LIVE", GREEN), ("last line", DIM),
]
BORDERS = "│┌└┐┘─"
HALF_BLOCKS = "▀▄█▌▐"

# --- binary resolution ------------------------------------------------------

def resolve_binary(args):
    if args.binary:
        p = Path(args.binary).resolve()
        if not p.exists():
            sys.exit(f"error: --binary {args.binary} does not exist")
        return p
    archives = sorted((REPO / "downloads" / "qrnix-manager").glob("*linux*.tar.gz"))
    if archives:
        print(f"extracting {archives[-1].name}…")
        tmp = Path(tempfile.mkdtemp(prefix="qrnix-mgr-"))
        with tarfile.open(archives[-1]) as tf:
            tf.extractall(tmp)
        return next(tmp.rglob("qrnix-manager"))
    found = shutil.which("qrnix-manager")
    if found:
        return Path(found)
    sys.exit("error: no qrnix-manager binary found (pass --binary, or run from the site repo)")

# --- capture ----------------------------------------------------------------

def drive(binary, keys, freeze=None):
    """Run the demo in a PTY (120x34), feeding `keys` [(delay_s, bytes)].

    With `freeze`, SIGSTOP the app at that offset after the last key and
    SIGKILL it two seconds later — used where the app would otherwise keep
    redrawing or hang (the review overlay, the flash journey).
    """
    ts = Path(tempfile.mkdtemp(prefix="qrnix-mgr-")) / "frame.ts"
    cmd = ["script", "-q", "-e", "-c",
           f"stty rows 34 cols 120; {binary} --demo", str(ts)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    name = binary.name
    try:
        for delay, data in keys:
            time.sleep(delay)
            proc.stdin.write(data)
            proc.stdin.flush()
        if freeze is not None:
            time.sleep(freeze)
            subprocess.run(["pkill", "-STOP", "-x", name], check=False)
            time.sleep(2)
            subprocess.run(["pkill", "-KILL", "-x", name], check=False)
        proc.stdin.close()
        proc.wait(timeout=60)
    finally:
        if proc.poll() is None:
            proc.kill()
        subprocess.run(["pkill", "-KILL", "-x", name], check=False)
    return ts

# --- terminal emulation -----------------------------------------------------

def parse_frame(ts):
    """Parse a script(1) typescript into (rows, bold, rev) cell grids."""
    data = open(ts, "rb").read().decode("utf-8", "replace")
    data = re.sub(r"Script started on .*?\n", "", data, count=1, flags=re.S)
    data = re.sub(r"Script done on .*?\n", "", data, count=1, flags=re.S)
    ROWS, COLS = 40, 120
    rows = [[" "] * COLS for _ in range(ROWS)]
    bold = [[False] * COLS for _ in range(ROWS)]
    rev = [[False] * COLS for _ in range(ROWS)]
    row = col = 0
    is_bold = is_rev = False
    i, n = 0, len(data)
    while i < n:
        c = data[i]
        if c == "\x1b":
            m = re.match(r"\x1b\[(\??)([0-9;]*)([A-Za-z])", data[i:])
            if not m:
                i += 1
                continue
            i += m.end()
            _, params, final = m.group(1), m.group(2), m.group(3)
            ps = [int(x) if x else 0 for x in params.split(";")] if params else []
            if final in "Hf":
                row = (ps[0] if ps and ps[0] else 1) - 1
                col = (ps[1] if len(ps) > 1 and ps[1] else 1) - 1
            elif final == "J":
                if ps and ps[0] == 2:
                    rows = [[" "] * COLS for _ in range(ROWS)]
                    bold = [[False] * COLS for _ in range(ROWS)]
                    rev = [[False] * COLS for _ in range(ROWS)]
                else:
                    for r in range(row, ROWS):
                        rows[r][col:] = [" "] * (COLS - col)
                        bold[r][col:] = [False] * (COLS - col)
                        rev[r][col:] = [False] * (COLS - col)
            elif final == "K":
                if not ps or ps[0] == 0:
                    rows[row][col:] = [" "] * (COLS - col)
                    bold[row][col:] = [False] * (COLS - col)
                    rev[row][col:] = [False] * (COLS - col)
            elif final == "m":
                if not ps or ps == [0] or ps == [0, 0]:
                    is_bold = is_rev = False
                for p in ps:
                    if p == 1:
                        is_bold = True
                    elif p == 22:
                        is_bold = False
                    elif p == 7:
                        is_rev = True
                    elif p == 27:
                        is_rev = False
            elif final in "ABCD":
                if final == "A": row = max(0, row - (ps[0] or 1))
                elif final == "B": row = min(ROWS - 1, row + (ps[0] or 1))
                elif final == "C": col = min(COLS - 1, col + (ps[0] or 1))
                elif final == "D": col = max(0, col - (ps[0] or 1))
            continue
        if c == "\r":
            col = 0
        elif c == "\n":
            row += 1
        elif ord(c) >= 32 and row < ROWS and col < COLS:
            rows[row][col] = c
            bold[row][col] = is_bold
            rev[row][col] = is_rev
            col += 1
        i += 1
    return rows, bold, rev

def normalize(rows):
    """Text-level fixes so the screenshots read like real hardware."""
    for y in range(len(rows)):
        line = "".join(rows[y])
        line = line.replace("qrnix-demo", "QRNix" + " " * 5)        # same width
        line = line.replace("qrnix-manager-demo", "qrnix-manager")
        line = line.replace("…Killed", "…").replace("Killed", "")
        for x in range(len(line)):
            rows[y][x] = line[x]
    return rows

# --- per-screen coloring ----------------------------------------------------

def screen_rules(kind):
    """Row index -> (base color, [(needle, color), ...])."""
    def r(base, needles=()):
        return (base, list(needles))

    if kind == "monitor":
        return {
            0: r(DIM, [("QRNix Manager", BRIGHT)]),
            1: r(DIM, [("Monitor", GREEN)]),
            4: r(DEFAULT, SESSION),
            5: r(AMBER, [("[d] dismiss", DIM), ("[p] pause", DIM)]),
            8: r(DEFAULT, [("MODE", DIM), ("SOURCE", DIM), ("CLIP", DIM),
                           ("TONE KILLER", AMBER), ("POST PROCESSING", AMBER)]),
            10: r(DEFAULT, [("RED", DIM), ("SM", DIM), ("WH", DIM), ("AG", DIM)]),
            12: r(DEFAULT, [("INPUT", DIM), ("LEVEL", DIM), ("OUTPUT", DIM)]),
            14: r(DEFAULT, [("INPUT", DIM), ("LEFT", DIM), ("RIGHT", DIM),
                            ("AUTO", DIM), ("60 s · 1 Hz", DIM)]),
            18: r(DEFAULT, [("LEVEL", DIM), ("LEFT", DIM), ("RIGHT", DIM),
                            ("AUTO", DIM), ("60 s · 1 Hz", DIM)]),
            22: r(DEFAULT, [("OUTPUT", DIM), ("LEFT", DIM), ("RIGHT", DIM),
                            ("AUTO", DIM), ("60 s · 1 Hz", DIM)]),
            29: r(DEFAULT, [("SNR", DIM), ("AVG", DIM), ("MIN", DIM), ("MAX", DIM),
                            ("BANDS", DIM), ("AGG", DIM), ("BYP", DIM),
                            ("GAIN", DIM), ("MIX", DIM)]),
            31: r(DEFAULT, [("HEALTH", DIM), ("BLOCKS", DIM), ("LEFT", DIM),
                            ("RIGHT", DIM), ("BAD", DIM), ("UNPARSED", DIM)]),
            33: r(DEFAULT, [("up", DIM), ("fw", DIM), ("app", DIM),
                            ("update available: v0.4.0", AMBER),
                            ("update available: v0.4.2 (u)", AMBER)]),
        }

    base = {
        0: r(DIM, [("QRNix Manager", BRIGHT)]),
        1: r(DIM, [("Firmware", GREEN)]),
        4: r(DEFAULT, SESSION),
        6: r(DEFAULT, [("QRNix Firmware", BRIGHT), ("[r] refresh", DIM),
                       ("[d] download", DIM), ("[f] review flash", DIM),
                       ("[Tab] next module", DIM),
                       ("[f] Review flash v0.4.0", GREEN)]),
        8: r(DEFAULT, [("published", DIM), ("cursor — browsing only", DIM), ("·", DIM)]),
        11: r(DEFAULT, [("SHA-256 VERIFIED", GREEN), ("v0.4.0", BRIGHT)]),
        13: r(DEFAULT, [("[f] Review flash", DIM)]),
        15: r(DEFAULT, [("VERSION", DIM), ("PUBLISHED", DIM), ("ARTIFACT", DIM)]),
    }
    if kind == "firmware":
        base[13] = r(DEFAULT, [("[d] download and verify", BRIGHT),
                               ("— no artifact prepared", DIM)])
    elif kind == "journey":
        base[14] = r(DEFAULT, [("1 SELECTED", GREEN), ("2 VERIFIED", GREEN),
                               ("3 REVIEW", GREEN), ("4 FLASH", GREEN),
                               ("5 VERIFY", BRIGHT)])
        base[16] = r(DEFAULT, [("stage  Verifying", BRIGHT), ("·  target  ", DIM),
                               ("v0.4.0", GREEN)])
        base[17] = r(BRIGHT)
        base[18] = r(DEFAULT, [("device  last confirmed ", DIM),
                               ("SERIAL 00000000001E19A4", BRIGHT),
                               ("VERIFIED", GREEN), ("·  from running firmware", DIM)])
    elif kind == "review":
        # rows 13+ sit behind the overlay: dimmed, box content brightened
        for y in range(14, 23):
            base[y] = r(DIM, [("SHA-256 VERIFIED", GREEN), ("VERIFIED", GREEN),
                              ("v0.4.0", BRIGHT), ("00000000001E19A4", BRIGHT),
                              ("0.3.13", BRIGHT), ("[Enter] Start flash", BRIGHT),
                              ("[Esc] Back", BRIGHT), ("Flash review", CYAN)])
    return base

# --- rendering --------------------------------------------------------------

def render(rows, bold, rev, rules, out_path, selected_rows=(), caption=""):
    """Draw the frame to PNG with the per-row rules, framed as a terminal
    window (title bar with traffic-light dots and a caption)."""
    last = 0
    for y in range(len(rows)):
        if any(c != " " for c in rows[y]):
            last = y
    rows = rows[:last + 1]

    font = ImageFont.truetype(FONT, int(15 * SCALE))
    cell_w = int(round(font.getlength("M")))
    ascent, descent = font.getmetrics()
    line_h = int((ascent + descent) * 1.22)

    # --- window chrome ------------------------------------------------------
    BORDER = 3 * SCALE
    RADIUS = 16 * SCALE
    TITLEBAR_H = 31 * SCALE
    PAD_X = 20 * SCALE
    PAD_TOP = 14 * SCALE
    PAD_BOTTOM = 22 * SCALE
    TITLEBAR_BG = (10, 26, 47)          # navy #0a1a2f
    DIVIDER = (40, 80, 108)             # #28506c
    DOT_COLORS = ((224, 96, 79), (226, 176, 74), (63, 201, 143))
    DOT_D = 11 * SCALE
    DOT_GAP = 7 * SCALE
    DOT_TOP = (TITLEBAR_H - DOT_D) // 2

    screen_w = cell_w * 120
    screen_h = line_h * len(rows)
    w = screen_w + 2 * (PAD_X + BORDER)
    h = BORDER + TITLEBAR_H + PAD_TOP + screen_h + PAD_BOTTOM
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)
    # The title bar first (rounded top corners), the border outline last so
    # no fill ever covers the corner arcs or the side rails.
    draw.rounded_rectangle([0, 0, w - 1, BORDER + TITLEBAR_H], radius=RADIUS,
                           fill=TITLEBAR_BG)
    draw.rounded_rectangle([0, 0, w - 1, h - 1], radius=RADIUS,
                           outline=DIVIDER, width=BORDER)
    draw.rectangle([0, BORDER + TITLEBAR_H, w - 1, BORDER + TITLEBAR_H],
                   fill=DIVIDER)

    # Transparent rounded corners: the window's dark silhouette must be
    # rounded, not just its border line — otherwise the opaque corner
    # pixels read as black squares against the page background. The alpha
    # mask is built at 4x and downscaled for a smooth (anti-aliased) edge.
    AA = 2
    mask = Image.new("L", (w * AA, h * AA), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, w * AA - 1, h * AA - 1],
                         radius=RADIUS * AA, fill=255)
    mask = mask.resize((w, h), Image.LANCZOS)
    img.putalpha(mask)
    x = BORDER + 14 * SCALE
    for color in DOT_COLORS:
        draw.ellipse([x, BORDER + DOT_TOP, x + DOT_D, BORDER + DOT_TOP + DOT_D],
                     fill=color)
        x += DOT_D + DOT_GAP
    if caption:
        cap_font = ImageFont.truetype(FONT, 12 * SCALE)
        draw.text((x + 8 * SCALE, BORDER + TITLEBAR_H // 2), caption,
                  font=cap_font, fill=DIM, anchor="lm")

    ox = BORDER + PAD_X
    oy = BORDER + TITLEBAR_H + PAD_TOP

    # the flash-review overlay's column range (review screen)
    box = None
    for y in range(len(rows)):
        text = "".join(rows[y])
        if "┌ Flash review" in text:
            box = (text.index("┌ Flash review"), text.index("┌ Flash review") + 70)
            break

    for y in range(len(rows)):
        text = "".join(rows[y])
        base, needles = rules.get(y, (DEFAULT, []))
        colors = [base] * len(text)
        pos = 0
        for needle, color in needles:
            idx = text.find(needle, pos)
            if idx == -1:
                continue
            for j in range(idx, idx + len(needle)):
                colors[j] = color
            pos = idx + len(needle)

        in_box = box is not None and y >= 13 and box[0] <= 0
        selected = y in selected_rows

        if selected:
            draw.rectangle([ox, oy + y * line_h, ox + screen_w, oy + (y + 1) * line_h], fill=SEL_BG)

        for x in range(len(text)):
            ch = text[x]
            region = box is not None and y >= 13 and box[0] <= x <= box[1]
            color = colors[x]
            if region and ch in BORDERS:
                color = BRIGHT
            if ch in BORDERS and not region:
                color = DIM
            if 0x2800 <= ord(ch) <= 0x28FF:
                color = CYAN
            elif ch in HALF_BLOCKS:
                color = BLUE
            if rev[y][x]:
                draw.rectangle([ox + x * cell_w, oy + y * line_h,
                                ox + (x + 1) * cell_w, oy + (y + 1) * line_h], fill=SEL_BG)
                color = CYAN
            if selected:
                color = DEFAULT
            if ch == " ":
                continue
            draw.text((ox + x * cell_w, oy + y * line_h), ch, font=font, fill=color)

    img.save(out_path)
    return img.size

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--binary", help="path to the qrnix-manager binary")
    ap.add_argument("--suffix", default="",
                    help="filename suffix for cache-busting (e.g. --suffix v3 "
                         "writes monitor-v3.png); bump it whenever the visuals "
                         "change so deployed pages never serve stale shots")
    ap.add_argument("--out", default=str(REPO / "assets" / "manager"),
                    help="output directory (default: assets/manager)")
    args = ap.parse_args()
    binary = resolve_binary(args)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    screens = [
        ("monitor", [(8, b""), (2, b"q")], None, (), "qrnix-manager — Monitor module"),
        ("firmware", [(8, b""), (2, b"\t"), (3, b"q")], None, (16,), "qrnix-manager — Firmware module"),
        ("review", [(8, b""), (2, b"\t"), (2, b"d"), (4, b"f")], 2.2, (), "qrnix-manager — Flash review overlay"),
        ("journey", [(8, b""), (2, b"\t"), (2, b"d"), (4, b"f"), (1.5, b"\r"),
                     (2, b"f"), (1.5, b"\r"), (2, b"f"), (1.5, b"\r")], 2.2, (22,), "qrnix-manager — UPDATE JOURNEY during a flash"),
    ]
    for name, keys, freeze, selected, caption in screens:
        print(f"capturing {name}…")
        ts = drive(binary, keys, freeze=freeze)
        rows, bold, rev = parse_frame(ts)
        rows = normalize(rows)
        suffix = f"-{args.suffix}" if args.suffix else ""
        path = out / f"{name}{suffix}.png"
        size = render(rows, bold, rev, screen_rules(name), path,
                      selected_rows=selected, caption=caption)
        print(f"  {path.name}: {size[0]}x{size[1]}")
    print("done — commit the PNGs with the release")

if __name__ == "__main__":
    main()
