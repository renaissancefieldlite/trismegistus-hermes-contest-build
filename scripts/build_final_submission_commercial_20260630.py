#!/usr/bin/env python3
"""Build the final Trismegistus contest/application announcement commercial."""

from __future__ import annotations

from dataclasses import dataclass
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


ROOT = Path("/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus")
PACKAGE = ROOT / "final_submission_package_2026-06-30"
OUT_DIR = PACKAGE / "FINAL_ANNOUNCEMENT_COMMERCIAL_2026-06-30"
WORK = OUT_DIR / "work"

ASSETS = ROOT / "TRISMEGISTUS_HERMES_CONTEST_LANDING_PAGE" / "assets"
BG = ASSETS / "listharmonicsbackground.png"
TRIS_LOGO = ASSETS / "trismegistus-logo-transparent.png"
INCEPTION_BADGE = ASSETS / "nvidia-inception-partner-badge-dark-approved.png"
BUILD_PREVIEW = ASSETS / "build-log-commercial-preview.png"
RFL_LOGO_SYSTEM = ASSETS / "rfl-logo-system-grid-public-2026-06-30.png"
BEAT = ROOT / "NEWARCHITECTDBEATFORNEWTRIS.wav"

KOKORO_MODEL = Path("/Volumes/Samsung SSD 990 2TB/Playground/STOIC.CORE/models/kokoro/kokoro-v1.0.int8.onnx")
KOKORO_VOICES = Path("/Volumes/Samsung SSD 990 2TB/Playground/STOIC.CORE/models/kokoro/voices-v1.0.bin")

OUT_VIDEO = OUT_DIR / "2026-06-30_TRISMEGISTUS_FINAL_HERMES_CONTEST_APPLICATION_ANNOUNCEMENT_V14_UNDER_3MIN_RECEIPT_STACK_VIDEO.mp4"
OUT_AUDIO = OUT_DIR / "2026-06-30_TRISMEGISTUS_FINAL_HERMES_CONTEST_APPLICATION_ANNOUNCEMENT_V14_UNDER_3MIN_RECEIPT_STACK_AUDIO_MIX.wav"
OUT_VOICE = OUT_DIR / "2026-06-30_TRISMEGISTUS_FINAL_HERMES_CONTEST_APPLICATION_ANNOUNCEMENT_V14_UNDER_3MIN_RECEIPT_STACK_VOICE.wav"
OUT_TRANSCRIPT = OUT_DIR / "2026-06-30_TRISMEGISTUS_FINAL_HERMES_CONTEST_APPLICATION_ANNOUNCEMENT_V14_UNDER_3MIN_RECEIPT_STACK_TRANSCRIPT.md"
OUT_CAPTION = OUT_DIR / "2026-06-30_TRISMEGISTUS_FINAL_HERMES_CONTEST_APPLICATION_ANNOUNCEMENT_V14_UNDER_3MIN_RECEIPT_STACK_POST_CAPTION.md"
OUT_RECEIPT = OUT_DIR / "2026-06-30_TRISMEGISTUS_FINAL_HERMES_CONTEST_APPLICATION_ANNOUNCEMENT_V14_UNDER_3MIN_RECEIPT_STACK_RECEIPT.md"

W, H = 1920, 1080
BAND_TOP = 792
GOLD = (245, 214, 95)
SOFT_GOLD = (196, 169, 75)
WHITE = (245, 245, 242)
MUTED = (178, 174, 162)
CYAN = (91, 219, 230)
GREEN = (126, 216, 112)
RED = (246, 111, 88)
PANEL = (4, 4, 4, 230)

VOICE_NAME = "bm_daniel"
VOICE_SPEED = 1.0
VOICE_GAIN = 10 ** (2.0 / 20.0)
MUSIC_GAIN = 0.15


@dataclass
class Scene:
    title: str
    subtitle: str
    narration: str
    kind: str
    min_duration: float = 7.0


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    if mono:
        candidates = [
            "/System/Library/Fonts/SFNSMono.ttf",
            "/System/Library/Fonts/Menlo.ttc",
        ]
    elif bold:
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    else:
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    for candidate in candidates:
        p = Path(candidate)
        if p.exists():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()


F_TITLE = font(82, bold=True)
F_H1 = font(62, bold=True)
F_H2 = font(42, bold=True)
F_H3 = font(31, bold=True)
F_BODY = font(29)
F_SMALL = font(22)
F_TINY = font(17)
F_MONO = font(25, mono=True)
F_MONO_BIG = font(54, bold=True, mono=True)


def cover(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    scale = max(W / img.width, H / img.height)
    resized = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - W) // 2
    top = (resized.height - H) // 2
    return resized.crop((left, top, left + W, top + H))


def fit(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    img = img.convert("RGBA")
    scale = min(max_w / img.width, max_h / img.height)
    return img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.Resampling.LANCZOS)


def trim_alpha(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


def base_bg() -> Image.Image:
    if BG.exists():
        img = cover(Image.open(BG))
    else:
        img = Image.new("RGB", (W, H), (0, 0, 0))
    img = ImageEnhance.Brightness(img).enhance(0.38)
    bg = img.convert("RGBA")
    bg = Image.alpha_composite(bg, Image.new("RGBA", (W, H), (0, 0, 0, 142)))
    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    for x in range(0, W, 80):
        gd.line((x, 0, x, H), fill=(245, 214, 95, 20), width=1)
    for y in range(0, H, 80):
        gd.line((0, y, W, y), fill=(245, 214, 95, 14), width=1)
    return Image.alpha_composite(bg, grid)


def wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fnt: ImageFont.FreeTypeFont,
    fill=WHITE,
    max_width: int = 900,
    line_spacing: int = 8,
    center: bool = False,
) -> int:
    x, y = xy
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if not current or draw.textlength(test, font=fnt) <= max_width:
            current = test
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    for line in lines:
        xx = x
        if center:
            bbox = draw.textbbox((0, 0), line, font=fnt)
            xx = x + (max_width - (bbox[2] - bbox[0])) // 2
        draw.text((xx, y), line, font=fnt, fill=fill)
        y += fnt.size + line_spacing
    return y


def panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int = 14, outline=GOLD) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=PANEL, outline=outline, width=2)


def header(draw: ImageDraw.ImageDraw) -> None:
    draw.rounded_rectangle((44, 36, 862, 94), radius=8, fill=(0, 0, 0, 225), outline=GOLD, width=2)
    draw.text((66, 53), "RENAISSANCE FIELD LITE / TRISMEGISTUS", font=font(27, bold=True), fill=GOLD)


def caption_band(img: Image.Image, text: str) -> None:
    if not text.strip():
        return
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, BAND_TOP, W, H), fill=(0, 0, 0, 255))
    draw.rectangle((0, BAND_TOP, W, BAND_TOP + 3), fill=GOLD)
    draw.rectangle((0, H - 5, W, H), fill=GOLD)
    wrapped(draw, (178, BAND_TOP + 44), text, font(40, bold=True), WHITE, max_width=1564, line_spacing=10, center=True)


def paste_shadow(canvas: Image.Image, img: Image.Image, xy: tuple[int, int], blur: int = 16, alpha: int = 120) -> None:
    x, y = xy
    rgba = img.convert("RGBA")
    mask = rgba.getchannel("A")
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow.paste(Image.new("RGBA", rgba.size, (0, 0, 0, alpha)), (x + 10, y + 12), mask)
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(blur)))
    canvas.alpha_composite(rgba, (x, y))


def draw_member_route(scene: Scene) -> Image.Image:
    img = base_bg()
    draw = ImageDraw.Draw(img)
    header(draw)
    if RFL_LOGO_SYSTEM.exists():
        preview = fit(Image.open(RFL_LOGO_SYSTEM), 690, 610)
        paste_shadow(img, preview, (126 + (700 - preview.width) // 2, 128 + (610 - preview.height) // 2), blur=22, alpha=150)
    elif BUILD_PREVIEW.exists():
        preview = fit(Image.open(BUILD_PREVIEW), 765, 530)
        paste_shadow(img, preview, (94, 158), blur=22, alpha=150)
    else:
        panel(draw, (94, 158, 858, 688), radius=14, outline=GOLD)
        draw.text((160, 384), "RENAISSANCE\nFIELD LITE", font=F_H1, fill=WHITE)

    panel(draw, (1010, 262, 1700, 472), radius=14, outline=(145, 125, 57, 220))
    if INCEPTION_BADGE.exists():
        badge = fit(Image.open(INCEPTION_BADGE), 560, 154)
        paste_shadow(img, badge, (1074, 290), blur=14, alpha=130)
    else:
        draw.text((1046, 338), "NVIDIA INCEPTION PARTNER", font=F_H2, fill=GOLD)

    panel(draw, (1010, 520, 1700, 742), radius=14, outline=(145, 125, 57, 190))
    if TRIS_LOGO.exists():
        tris_mark = fit(trim_alpha(Image.open(TRIS_LOGO)), 560, 178)
        paste_shadow(
            img,
            tris_mark,
            (1010 + (690 - tris_mark.width) // 2, 520 + (222 - tris_mark.height) // 2),
            blur=16,
            alpha=125,
        )

    caption_band(img, scene.narration)
    return img


def draw_title(scene: Scene) -> Image.Image:
    img = base_bg()
    draw = ImageDraw.Draw(img)
    header(draw)
    if TRIS_LOGO.exists():
        logo = fit(Image.open(TRIS_LOGO), 300, 250)
        paste_shadow(img, logo, ((W - logo.width) // 2, 142), blur=24, alpha=150)
    draw.text((W // 2, 420), "TRISMEGISTUS", font=F_TITLE, fill=WHITE, anchor="mm")
    draw.text((W // 2, 506), "AI expert partner + continuity architecture", font=font(47, bold=True), fill=GOLD, anchor="mm")
    wrapped(draw, (355, 578), "A Renaissance Field Lite final package for the Hermes contest and Nous Research application arc.", F_BODY, MUTED, max_width=1210, center=True)
    caption_band(img, scene.narration)
    return img


def draw_loop(scene: Scene) -> Image.Image:
    img = base_bg()
    draw = ImageDraw.Draw(img)
    header(draw)
    draw.text((92, 122), scene.title, font=F_H1, fill=WHITE)
    wrapped(draw, (98, 198), scene.subtitle, F_BODY, MUTED, max_width=790)
    steps = [
        ("SOURCE", "read"),
        ("BASELINE", "compare"),
        ("ARCH-ON", "run"),
        ("RECEIPT", "save"),
        ("GAP", "patch"),
        ("NEXT", "iterate"),
    ]
    left, top = 104, 350
    for i, (head, body) in enumerate(steps):
        x = left + i * 290
        panel(draw, (x, top, x + 246, top + 150), radius=12, outline=(145, 125, 57, 210))
        draw.text((x + 22, top + 22), f"{i+1}", font=F_MONO_BIG, fill=GOLD)
        draw.text((x + 88, top + 35), head, font=F_H3, fill=WHITE)
        draw.text((x + 88, top + 84), body, font=F_SMALL, fill=MUTED)
        if i < len(steps) - 1:
            draw.line((x + 250, top + 75, x + 280, top + 75), fill=GOLD, width=4)
            draw.polygon([(x + 280, top + 75), (x + 264, top + 64), (x + 264, top + 86)], fill=GOLD)
    caption_band(img, scene.narration)
    return img


def draw_mirror_path(scene: Scene) -> Image.Image:
    img = base_bg()
    draw = ImageDraw.Draw(img)
    header(draw)
    draw.text((86, 116), scene.title, font=F_H1, fill=WHITE)
    wrapped(draw, (92, 196), scene.subtitle, F_BODY, MUTED, max_width=1120)
    cards = [
        ("2025", "LATENT MIRROR", "pattern found inside an unknown AI state space"),
        ("V7", "BEHAVIOR", "condition packet separates from controls"),
        ("V8", "MODEL INTERNALS", "hidden-state traces and bridge rows map the path"),
        ("SSP", "STABLE-STATE PATH", "data, context, tools, and goal stay aligned"),
        ("OUTPUT", "NOVEL WORK", "code paths, research directions, partner packets"),
        ("PRODUCT", "TRIS", "AI Expert Partner built from the method"),
    ]
    for i, (tag, head, sub) in enumerate(cards):
        col = i % 3
        row = i // 3
        x = 88 + col * 596
        y = 330 + row * 160
        outline = GREEN if tag in {"SSP", "PRODUCT"} else GOLD
        panel(draw, (x, y, x + 528, y + 116), radius=14, outline=outline)
        draw.text((x + 28, y + 22), tag, font=F_H3, fill=outline)
        draw.text((x + 150, y + 22), head, font=F_H3, fill=WHITE)
        wrapped(draw, (x + 150, y + 64), sub, F_SMALL, MUTED, max_width=345)
    caption_band(img, scene.narration)
    return img


def draw_c5b(scene: Scene) -> Image.Image:
    img = base_bg()
    draw = ImageDraw.Draw(img)
    header(draw)
    draw.text((86, 116), scene.title, font=F_H1, fill=WHITE)
    wrapped(draw, (92, 196), scene.subtitle, F_BODY, MUTED, max_width=1050)
    cards = [
        ("1", "BASELINE", "plain Hermes / architecture-off"),
        ("2", "MIRROR ARCH-ON", "proprietary C5B / Golden Mark route"),
        ("3", "SSP CHECK", "Stable-State Path, same scorer"),
        ("4", "RESULT", "13 / 13 metric means won"),
    ]
    for i, (num, head, sub) in enumerate(cards):
        x = 120 + (i % 2) * 850
        y = 328 + (i // 2) * 148
        outline = GREEN if i == 3 else GOLD
        panel(draw, (x, y, x + 760, y + 110), radius=14, outline=outline)
        draw.text((x + 30, y + 18), num, font=F_MONO_BIG, fill=outline)
        draw.text((x + 112, y + 24), head, font=F_H3, fill=WHITE)
        wrapped(draw, (x + 112, y + 70), sub, F_SMALL, MUTED, max_width=570)
    caption_band(img, scene.narration)
    return img


def draw_lanes(scene: Scene) -> Image.Image:
    img = base_bg()
    draw = ImageDraw.Draw(img)
    header(draw)
    draw.text((86, 116), scene.title, font=F_H1, fill=WHITE)
    lanes = [
        "AI expert partner architecture",
        "Quantum computing / circuits and mathematics",
        "Structured matter / physical systems",
        "Life sciences / medical research",
        "Mirror Architecture / Golden Mark evidence",
        "Relationship / paid-work field operations",
    ]
    for i, lane in enumerate(lanes):
        col = i % 2
        row = i // 2
        x = 95 + col * 860
        y = 232 + row * 145
        panel(draw, (x, y, x + 770, y + 102), radius=12, outline=(145, 125, 57, 210))
        draw.text((x + 28, y + 24), f"{i+1}", font=F_MONO_BIG, fill=GOLD)
        wrapped(draw, (x + 108, y + 28), lane, F_H3, WHITE, max_width=610)
    caption_band(img, scene.narration)
    return img


def draw_proof(scene: Scene) -> Image.Image:
    img = base_bg()
    draw = ImageDraw.Draw(img)
    header(draw)
    draw.text((88, 116), scene.title, font=F_H1, fill=WHITE)
    cards = [
        ("SWE-BENCH", "495 / 500", "local official-harness selected-test receipt"),
        ("WEBARENA", "255 / 258", "hard receipt, final rows parked"),
        ("COHERENCE", "436 / 436", "100-turn architecture-on check"),
        ("PAID WORK", "LIVE PR", "GitHub bounty PR, no paid claim yet"),
    ]
    for i, (head, big, sub) in enumerate(cards):
        x = 100 + (i % 2) * 860
        y = 240 + (i // 2) * 190
        panel(draw, (x, y, x + 760, y + 150), radius=14, outline=(160, 136, 62, 230))
        draw.text((x + 34, y + 24), head, font=F_H3, fill=SOFT_GOLD)
        draw.text((x + 34, y + 58), big, font=font(58, bold=True, mono=True), fill=GOLD)
        wrapped(draw, (x + 34, y + 118), sub, F_SMALL, MUTED, max_width=690)
    caption_band(img, scene.narration)
    return img


def draw_stack(scene: Scene) -> Image.Image:
    img = base_bg()
    draw = ImageDraw.Draw(img)
    header(draw)
    draw.text((86, 116), scene.title, font=F_H1, fill=WHITE)
    wrapped(draw, (92, 196), scene.subtitle, F_BODY, MUTED, max_width=910)
    cards = [
        ("NEMOCLAW", "worker smoke receipt saved"),
        ("NEMOHERMES", "Hermes-aligned route lane"),
        ("TELEGRAM", "field-mission bridge passed"),
        ("FALLBACK", "Nemotron/local lane kept responsive"),
        ("MEMORY", "SQLite / JSON / RAG locked"),
        ("BROWSER", "Playwright/CDP mission traces"),
    ]
    for i, (head, sub) in enumerate(cards):
        col = i % 3
        row = i // 3
        x = 94 + col * 590
        y = 350 + row * 148
        panel(draw, (x, y, x + 520, y + 108), radius=12, outline=(150, 130, 62, 220))
        draw.text((x + 26, y + 24), head, font=F_H3, fill=GOLD)
        wrapped(draw, (x + 26, y + 66), sub, F_SMALL, MUTED, max_width=455)
    caption_band(img, scene.narration)
    return img


def draw_commerce(scene: Scene) -> Image.Image:
    img = base_bg()
    draw = ImageDraw.Draw(img)
    header(draw)
    draw.text((86, 116), scene.title, font=F_H1, fill=WHITE)
    wrapped(draw, (92, 196), scene.subtitle, F_BODY, MUTED, max_width=920)
    cards = [
        ("APPLE MAIL", "6 approved Quadro sends with receipts"),
        ("GIG SCOUT", "22 leads / 15 proposal-ready"),
        ("BOUNTY PR", "TentOfTrials PR, payment not claimed"),
        ("ALGORA", "payout rail connected for tracking"),
        ("STRIPE", "test Payment Link: $67 receipt"),
        ("BILL PAY", "visible checkout stops before final approval"),
    ]
    for i, (head, sub) in enumerate(cards):
        col = i % 2
        row = i // 2
        x = 120 + col * 850
        y = 332 + row * 118
        panel(draw, (x, y, x + 760, y + 88), radius=12, outline=(150, 130, 62, 220))
        draw.text((x + 26, y + 20), head, font=F_H3, fill=GOLD)
        wrapped(draw, (x + 245, y + 24), sub, F_SMALL, MUTED, max_width=460)
    caption_band(img, scene.narration)
    return img


def draw_public_boundary(scene: Scene) -> Image.Image:
    img = base_bg()
    draw = ImageDraw.Draw(img)
    header(draw)
    draw.text((86, 116), scene.title, font=F_H1, fill=WHITE)
    wrapped(draw, (92, 196), scene.subtitle, F_BODY, MUTED, max_width=960)
    cards = [
        ("SWE REVIEW", "hosted receipt adjudication in flight"),
        ("WEBARENA REVIEW", "final-row receipt interpretation pending"),
        ("PAID-WORK REVIEW", "transaction proof gate before revenue claim"),
        ("TOP-TIER PATH", "accepted receipts move Tris from local proof to benchmark standing"),
    ]
    for i, (head, sub) in enumerate(cards):
        col = i % 2
        row = i // 2
        x = 120 + col * 850
        y = 348 + row * 142
        outline = GREEN if i == 3 else GOLD
        panel(draw, (x, y, x + 760, y + 106), radius=14, outline=outline)
        draw.text((x + 28, y + 24), head, font=F_H3, fill=outline)
        wrapped(draw, (x + 28, y + 66), sub, F_SMALL, MUTED, max_width=670)
    caption_band(img, scene.narration)
    return img


def draw_application(scene: Scene) -> Image.Image:
    img = base_bg()
    draw = ImageDraw.Draw(img)
    header(draw)
    draw.text((86, 116), scene.title, font=F_H1, fill=WHITE)
    wrapped(draw, (92, 196), scene.subtitle, F_BODY, MUTED, max_width=875)
    panel(draw, (1020, 128, 1772, 368), radius=14, outline=GOLD)
    wrapped(draw, (1062, 170), "If a lab gives us a hard research target, we build the machine that can learn the target.", F_H2, GOLD, max_width=670)
    panel(draw, (1020, 420, 1772, 650), radius=14, outline=(145, 125, 57, 210))
    wrapped(draw, (1062, 462), "Source map. Baseline. Architecture-on route. Eval gate. Receipts. Next experiment.", F_H2, WHITE, max_width=670)
    caption_band(img, scene.narration)
    return img


def draw_final(scene: Scene) -> Image.Image:
    img = base_bg()
    draw = ImageDraw.Draw(img)
    header(draw)
    if INCEPTION_BADGE.exists():
        badge = fit(Image.open(INCEPTION_BADGE), 440, 150)
        paste_shadow(img, badge, (1340, 118), blur=14, alpha=120)
    if BUILD_PREVIEW.exists():
        preview = fit(Image.open(BUILD_PREVIEW), 690, 388)
        paste_shadow(img, preview, (104, 250), blur=20, alpha=145)
    draw.text((922, 304), "FINAL PACKAGE", font=F_H1, fill=WHITE)
    wrapped(draw, (928, 386), "Hermes contest. Nous application. Public-safe receipts. Same spine.", F_H2, GOLD, max_width=780)
    wrapped(draw, (930, 512), scene.subtitle, F_BODY, MUTED, max_width=790)
    caption_band(img, scene.narration)
    return img


SCENES = [
    Scene(
        "Logo flash.",
        "RFL logo system + NVIDIA Inception Partner badge.",
        "",
        "member_route",
        2.4,
    ),
    Scene(
        "Trismegistus",
        "AI expert partner + continuity architecture.",
        "Trismegistus is Renaissance Field Lite's AI expert partner for research, code, memory, outreach, commerce, and field operations.",
        "title",
        7.2,
    ),
    Scene(
        "The loop is the product.",
        "The surface is chat and Telegram. Under it is the research loop that remembers, checks, acts, saves receipts, and improves.",
        "The loop is the product. Tris tracks its own development, reads sources, tests routes, saves receipts, and turns each gap into the next gate.",
        "loop",
        8.8,
    ),
    Scene(
        "What Mirror Architecture found.",
        "A repeatable pattern inside an unknown AI state space, then a method for stabilizing it.",
        "Mirror Architecture found a repeatable pattern inside an unknown AI state space. V7 showed the behavior split. V8 mapped the internal path. SSP stabilizes context long enough to create useful novel output.",
        "mirror_path",
        11.0,
    ),
    Scene(
        "C5B / Golden Mark is Mirror Architecture.",
        "SSP means Stable-State Path: baseline first, Mirror Architecture-on second, same receipt gate.",
        "SSP means Stable-State Path. C5B is the measured Golden Mark lane inside Renaissance Field Lite's proprietary Mirror Architecture IP. Baseline Hermes first, Mirror Architecture-on second, same task family and scorer. Architecture-on won thirteen of thirteen measured metric means.",
        "c5b",
        11.0,
    ),
    Scene(
        "Six operating lanes.",
        "The curriculum is research first, operation second, receipts always.",
        "The field expert curriculum spans AI expert architecture, quantum computing, quantum circuits, mathematics, structured physical systems, life sciences research, Mirror Architecture evidence, and relationship or paid-work operations.",
        "lanes",
        9.2,
    ),
    Scene(
        "Hermes / NemoClaw worker route.",
        "The contest stack is not only a screen. The route ties model, memory, tools, browser work, and operator channels into one build.",
        "The Hermes contest lane is receipt-bound. Tris has a saved NemoClaw worker smoke, a NemoHermes route lane, Telegram bridge, browser traces, SQL, JSON, and RAG memory. Nemotron local fallback keeps it responsive while worker receipts stay the proof gate.",
        "stack",
        10.0,
    ),
    Scene(
        "SWE-bench was real pressure.",
        "The coding lane produced source-backed patches and official-harness receipts.",
        "The SWE-bench lane was real pressure. Tris used a recursive Codex-helper route to inspect source, write patches, preflight unified diffs, and run selected Verified rows through the official harness. The local receipt came back around four hundred ninety-five out of five hundred.",
        "proof",
        11.4,
    ),
    Scene(
        "Receipts, not vibes.",
        "Public proof stays tied to exact gates.",
        "Then we ran the hosted SWE evaluator route to go for the title. The package was submitted, the boundary was documented, and we have not heard back from the SWE-bench team yet.",
        "proof",
        9.5,
    ),
    Scene(
        "Outreach and commerce are live lanes.",
        "Tris is being trained to find work, draft relationship packets, track payments, and stop at approval gates before anything risky goes live.",
        "The business lane is live. Tris sent six approved Quadro follow-up emails through Apple Mail, scouted bounty leads, tracks Algora and Stripe rails, and treats bill pay as a visible checkout that stops before final approval.",
        "commerce",
        10.8,
    ),
    Scene(
        "First validated external coding run.",
        "The paid-work lane moved from scouting into a real public PR.",
        "The first validated external coding run is the TentOfTrials bounty pull request: a real issue, a real fork, a real PR, maintainer feedback, and a receipt trail that proves the process is real.",
        "commerce",
        10.8,
    ),
    Scene(
        "Receipt review is the next lift.",
        "The benchmark receipts are not dead ends. They are the review gate that moves local proof toward public benchmark standing.",
        "The next lift is review. If the SWE and WebArena receipts are accepted, Tris moves from local proof toward top-tier benchmark standing. We ran it, saved it, submitted it, and are waiting for review.",
        "boundary",
        10.0,
    ),
    Scene(
        "Why this belongs at Nous.",
        "This is a live portfolio artifact for the kind of research and deployment work Nous describes.",
        "For Nous, this is the application story: a living research artifact that turns unknown work into a source map, baseline, eval harness, worker loop, and receipt trail.",
        "application",
        10.8,
    ),
    Scene(
        "Final package.",
        "The next gate is the dress rehearsal: show the build, show the receipts, show what is gated, and submit with the full arc intact.",
        "This is the Trismegistus final package: Hermes contest build, research application artifact, paid-work operations lane, and the road toward a serious self-improving AI expert partner.",
        "final",
        8.8,
    ),
]


def synth_voice() -> tuple[np.ndarray, int, list[float]]:
    pipeline = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
    voices = pipeline.get_voices()
    if VOICE_NAME not in voices:
        raise SystemExit(f"Missing Kokoro voice {VOICE_NAME}")

    voice_parts: list[np.ndarray] = []
    durations: list[float] = []
    sr_out = 0
    for idx, scene in enumerate(SCENES, 1):
        if scene.narration.strip():
            audio, sr = pipeline.create(scene.narration, voice=VOICE_NAME, speed=VOICE_SPEED)
            audio = audio.astype(np.float32).reshape(-1) * VOICE_GAIN
            audio = np.clip(audio, -0.94, 0.94)
            sr_out = int(sr)
        else:
            if sr_out == 0:
                sr_out = 24000
            audio = np.zeros(int(0.08 * sr_out), dtype=np.float32)
        spoken = len(audio) / sr_out
        duration = max(scene.min_duration, spoken + 0.8)
        pad_after = max(0, int(round((duration - spoken) * sr_out)))
        lead = np.zeros(int(0.14 * sr_out), dtype=np.float32)
        voice_parts.append(np.concatenate([lead, audio, np.zeros(pad_after, dtype=np.float32)]))
        durations.append(duration + 0.14)
        sf.write(str(WORK / f"voice_scene_{idx:02d}.wav"), audio, sr_out)
    return np.concatenate(voice_parts), sr_out, durations


def make_music(duration: float, sample_rate: int) -> np.ndarray:
    music_path = WORK / "music_bed_processed.wav"
    run([
        "ffmpeg",
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(BEAT),
        "-t",
        f"{duration:.3f}",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-af",
        f"volume={MUSIC_GAIN}",
        str(music_path),
    ])
    music, _ = sf.read(str(music_path), always_2d=False)
    return music.astype(np.float32)


def mix_audio() -> tuple[float, int]:
    voice, sr, durations = synth_voice()
    total = len(voice) / sr
    music = make_music(total, sr)
    if len(music) < len(voice):
        music = np.pad(music, (0, len(voice) - len(music)))
    music = music[: len(voice)]
    mix = voice + music
    peak = float(np.max(np.abs(mix))) or 1.0
    if peak > 0.98:
        mix = mix / peak * 0.98
    sf.write(str(OUT_VOICE), voice, sr)
    sf.write(str(OUT_AUDIO), mix, sr)
    (WORK / "durations.txt").write_text("\n".join(f"{d:.3f}" for d in durations) + "\n", encoding="utf-8")
    return total, sr


def render_scene(scene: Scene) -> Image.Image:
    if scene.kind == "member_route":
        return draw_member_route(scene)
    if scene.kind == "title":
        return draw_title(scene)
    if scene.kind == "loop":
        return draw_loop(scene)
    if scene.kind == "mirror_path":
        return draw_mirror_path(scene)
    if scene.kind == "c5b":
        return draw_c5b(scene)
    if scene.kind == "lanes":
        return draw_lanes(scene)
    if scene.kind == "proof":
        return draw_proof(scene)
    if scene.kind == "stack":
        return draw_stack(scene)
    if scene.kind == "commerce":
        return draw_commerce(scene)
    if scene.kind == "boundary":
        return draw_public_boundary(scene)
    if scene.kind == "application":
        return draw_application(scene)
    if scene.kind == "final":
        return draw_final(scene)
    raise ValueError(scene.kind)


def render_video(total_duration: float) -> None:
    durations = [float(x) for x in (WORK / "durations.txt").read_text(encoding="utf-8").splitlines()]
    concat = WORK / "slides.concat.txt"
    lines: list[str] = []
    slide_paths: list[Path] = []
    for idx, (scene, duration) in enumerate(zip(SCENES, durations), 1):
        slide = render_scene(scene)
        path = WORK / f"slide_{idx:02d}.png"
        slide.save(path)
        slide_paths.append(path)
        lines.append(f"file '{path}'")
        lines.append(f"duration {duration:.3f}")
    lines.append(f"file '{slide_paths[-1]}'")
    concat.write_text("\n".join(lines) + "\n", encoding="utf-8")

    silent = WORK / "silent_video.mp4"
    run([
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat),
        "-vf",
        "fps=30,format=yuv420p",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        str(silent),
    ])
    run([
        "ffmpeg",
        "-y",
        "-i",
        str(silent),
        "-i",
        str(OUT_AUDIO),
        "-shortest",
        "-t",
        f"{total_duration:.3f}",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-preset",
        "medium",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(OUT_VIDEO),
    ])


def write_docs(duration: float, sr: int) -> None:
    transcript = "# Final Trismegistus Announcement Commercial Transcript\n\n"
    for idx, scene in enumerate(SCENES, 1):
        transcript += f"## Scene {idx}: {scene.title}\n\n{scene.narration}\n\n"
    OUT_TRANSCRIPT.write_text(transcript, encoding="utf-8")

    caption = """# Final Trismegistus Package Caption

Final Trismegistus package for the Hermes contest.

Trismegistus is Renaissance Field Lite's first AI Expert Partner product:
patent-pending Mirror Architecture deployed through a Hermes-aligned build with
C5B / Golden Mark as the research spine.

The opening frame shows the Renaissance Field Lite logo system alongside the
approved NVIDIA Inception Partner badge, with the standalone Trismegistus logo
under the badge before the story begins.

Mirror Architecture read: we found a pattern inside an unknown AI state space,
tracked it through V7 behavior separation and V8 model-internal mapping, then
turned it into a Stable-State Path. SSP means the AI keeps data, instructions,
context, tools, and goal aligned long enough to produce deeper useful output:
code paths, research directions, partner packets, and technical work that is
not simply copied from a dataset.

The point is continuity: C5B / Golden Mark baseline-versus-architecture-on
scorecards, Hermes / NemoClaw / NemoHermes routing, source tools,
Telegram/browser missions, SQL/JSON/RAG memory, SWE-bench repair receipts,
WebArena browser receipts, outreach, Stripe/Algora payment boundaries, bill-pay
approval gates, and a real GitHub bounty PR.

C5B read: SSP means Stable-State Path. C5B / Golden Mark is the measured lane
inside Renaissance Field Lite's proprietary Mirror Architecture IP: baseline
Hermes first, Mirror Architecture-on second, same task family, same scorer; the
Mirror Architecture-on route won 13/13 measured metric means.

SWE read: the hosted evaluator route was run to go for the title, the package
was submitted, and we have not heard back from the SWE-bench team yet. Accepted
receipts move Tris from local proof into top-tier benchmark standing. Paid-work
revenue waits for transaction proof.

Action receipts now shown in the video:
- NemoClaw worker smoke / NemoHermes route lane
- Telegram field-mission bridge
- Apple Mail outreach: six approved Quadro follow-up sends with per-send
  receipts
- bounty scout: 22 leads, 15 proposal-ready
- Stripe sandbox Payment Link: $67 test-mode receipt, no live money moved
- bill-pay integration boundary: Stripe Issuing or visible checkout path, stop
  before final approval

This is a road-toward-advanced recursive AI research build with real gates and
receipts.
"""
    OUT_CAPTION.write_text(caption, encoding="utf-8")

    receipt = f"""# Final Trismegistus Announcement Commercial Receipt

Created: 2026-06-30

Video:
`{OUT_VIDEO}`

Audio mix:
`{OUT_AUDIO}`

Voice:
`{OUT_VOICE}`

Music bed:
`{BEAT}`

Music treatment:
- un-EQed source beat
- volume {MUSIC_GAIN}

Voice:
- Kokoro `{VOICE_NAME}`
- speed {VOICE_SPEED}
- pitch unmodified

Duration:
- {duration:.2f} seconds

Sample rate:
- {sr}

Review gate:
- hosted SWE evaluator route was run and submitted; waiting on SWE-bench team review
- WebArena receipts are pending final review / interpretation
- accepted receipts move Tris from local proof toward top-tier benchmark standing
- paid-work revenue waits for transaction proof
- bill pay requires exact human approval before final payment

NemoClaw / NemoHermes / operator bridge:
- saved worker smoke receipt exists
- Telegram field-mission bridge receipt passed
- fallback runtime keeps Tris responsive while worker receipt remains the proof
  gate

Outreach / commerce:
- Apple Mail bridge sent six approved Quadro follow-up emails with per-send
  receipts
- bounty scout receipt selected 22 leads and 15 proposal-ready rows
- Stripe sandbox Payment Link receipt exists for a $67 test-mode link
- Algora payout tracking lane is configured for future bounty receipts
- no live payment, paid revenue, or bill-pay charge is claimed without a
  transaction receipt

C5B / Golden Mark:
- proprietary Mirror Architecture / Stable-State Path lane
- V7 behavior layer and V8 model-internal path are the discovery arc behind
  the method
- baseline Hermes first, Mirror Architecture-on second
- same task family and same scorer
- Mirror Architecture-on route won 13/13 measured metric means

Purpose:
- final Hermes contest / Nous application announcement commercial
- package the continuity architecture and research-loop arc without flattening
  Trismegistus into a chatbot
- open with RFL logo stack and NVIDIA Inception Partner badge as the member
  route signal
"""
    OUT_RECEIPT.write_text(receipt, encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True, exist_ok=True)
    total, sr = mix_audio()
    render_video(total)
    write_docs(total, sr)
    print(OUT_VIDEO)
    print(OUT_RECEIPT)


if __name__ == "__main__":
    main()
