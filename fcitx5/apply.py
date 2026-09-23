#!/usr/bin/env python3
"""Paint the fcitx5 classic UI from the active Omarchy theme.

Reads ~/.local/state/omarchy/current/theme/colors.toml (the palette Omarchy
just applied) and writes a rounded theme under
~/.local/share/fcitx5/themes/omarchy. Safe to run after every theme switch:
light and dark both come from that palette, so either Cassette Futurism
checkout can own the hook.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

THEME_DIR = Path.home() / ".local/share/fcitx5/themes/omarchy"
CLASSICUI = Path.home() / ".config/fcitx5/conf/classicui.conf"
COLORS = Path.home() / ".local/state/omarchy/current/theme/colors.toml"
THEME_NAME = Path.home() / ".local/state/omarchy/current/theme.name"

# Popped Omarchy windows use rounding 8. The 9-slice margin must stay
# outside that radius so the corners are not stretched.
RADIUS = 8
SLICE = 12
PANEL = 40

CLASSICUI_KEYS = {
    "Font": '"Noto Sans CJK SC 12"',
    "MenuFont": '"Noto Sans CJK SC 12"',
    "Theme": "omarchy",
    "DarkTheme": "omarchy",
    "UseDarkTheme": "False",
    "UseAccentColor": "False",
}


def load_colors(path: Path) -> dict[str, str]:
    colors: dict[str, str] = {}
    # Hex values themselves start with "#", so comments are only a leading "#".
    assign = re.compile(
        r'^([A-Za-z0-9_]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|(\S+))\s*(?:#.*)?$'
    )
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = assign.match(line)
        if not match:
            continue
        key = match.group(1)
        value = next(group for group in match.groups()[1:] if group is not None)
        if key == "mode":
            colors["mode"] = value
        elif re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
            colors[key] = value.lower()
    return colors


def need(colors: dict[str, str], key: str, fallback: str) -> str:
    return colors.get(key, fallback)


def svg_panel(fill: str, stroke: str) -> str:
    inset = 1
    size = PANEL - inset * 2
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{PANEL}" height="{PANEL}">
  <rect x="{inset}" y="{inset}" width="{size}" height="{size}" rx="{RADIUS}" ry="{RADIUS}" fill="{fill}" stroke="{stroke}" stroke-width="1.25"/>
</svg>
"""


def svg_highlight(fill: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28">
  <rect width="28" height="28" rx="6" ry="6" fill="{fill}"/>
</svg>
"""


def svg_chevron(color: str, direction: str) -> str:
    path = (
        "M10.2 2.6 4.8 8l5.4 5.4-1.3 1.3L2.2 8l6.7-6.7z"
        if direction == "prev"
        else "M5.8 2.6 11.2 8 5.8 13.4l1.3 1.3L13.8 8 7.1 1.3z"
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
  <path fill="{color}" d="{path}"/>
</svg>
"""


def svg_arrow(color: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="8" height="12" viewBox="0 0 8 12">
  <path fill="{color}" d="M1.2 0.8 6.4 6 1.2 11.2 0 10l4-4-4-4z"/>
</svg>
"""


def svg_radio(color: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
  <circle cx="8" cy="8" r="3.2" fill="{color}"/>
</svg>
"""


def theme_conf(name: str, bg: str, fg: str, accent: str, selection: str, muted: str, comment: str) -> str:
    return f"""[Metadata]
Name={name}
Version=1
Author=Omarchy
Description=Generated from the active Omarchy theme
ScaleWithDPI=True

[InputPanel]
Font="Noto Sans CJK SC 12"
NormalColor={fg}
HighlightColor={accent}
HighlightBackgroundColor={selection}
HighlightCandidateColor={accent}
CandidateLabelColor={muted}
HighlightCandidateLabelColor={accent}
CandidateCommentColor={comment}
HighlightCandidateCommentColor={fg}
LabelTextSizeFactor=90
CommentTextSizeFactor=78
PageButtonAlignment=Last Candidate

[InputPanel/TextMargin]
Left=10
Right=10
Top=5
Bottom=5

[InputPanel/ContentMargin]
Left=8
Right=8
Top=6
Bottom=6

[InputPanel/Background]
Image=panel.svg

[InputPanel/Background/Margin]
Left={SLICE}
Right={SLICE}
Top={SLICE}
Bottom={SLICE}

[InputPanel/Highlight]
Image=highlight.svg

[InputPanel/Highlight/Margin]
Left=8
Right=8
Top=8
Bottom=8

[InputPanel/PrevPage]
Image=prev.svg

[InputPanel/PrevPage/ClickMargin]
Left=6
Right=4
Top=4
Bottom=4

[InputPanel/NextPage]
Image=next.svg

[InputPanel/NextPage/ClickMargin]
Left=4
Right=6
Top=4
Bottom=4

[Menu]
Font="Noto Sans CJK SC 12"
NormalColor={fg}
HighlightCandidateColor={accent}
Spacing=2

[Menu/TextMargin]
Left=10
Right=12
Top=6
Bottom=6

[Menu/ContentMargin]
Left=6
Right=6
Top=6
Bottom=6

[Menu/Background]
Image=panel.svg

[Menu/Background/Margin]
Left={SLICE}
Right={SLICE}
Top={SLICE}
Bottom={SLICE}

[Menu/Highlight]
Image=highlight.svg

[Menu/Highlight/Margin]
Left=8
Right=8
Top=6
Bottom=6

[Menu/Separator]
Color={comment}

[Menu/CheckBox]
Image=radio.svg

[Menu/SubMenu]
Image=arrow.svg
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def upsert_classicui(path: Path) -> None:
    """Point classicui at this skin without dropping unrelated keys."""
    if path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = [
            "# fcitx5 classic UI, painted from the active Omarchy palette.",
            "Vertical Candidate List=False",
        ]
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            out.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in CLASSICUI_KEYS:
            if key not in seen:
                out.append(f"{key}={CLASSICUI_KEYS[key]}")
                seen.add(key)
            continue
        out.append(line)
    for key, value in CLASSICUI_KEYS.items():
        if key not in seen:
            out.append(f"{key}={value}")
    write(path, "\n".join(out).rstrip() + "\n")


def reload_fcitx() -> None:
    try:
        subprocess.run(
            [
                "busctl",
                "--user",
                "call",
                "org.fcitx.Fcitx5",
                "/controller",
                "org.fcitx.Fcitx.Controller1",
                "ReloadAddonConfig",
                "s",
                "classicui",
            ],
            check=False,
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def palette_path() -> Path:
    override = os.environ.get("OMARCHY_FCITX_COLORS", "")
    if override:
        return Path(override)
    if COLORS.is_file():
        return COLORS
    sibling = Path(__file__).resolve().parent.parent / "colors.toml"
    if sibling.is_file():
        return sibling
    return COLORS


def main() -> int:
    path = palette_path()
    if not path.is_file():
        print(f"fcitx5 theme: no palette at {path}", file=sys.stderr)
        return 1
    colors = load_colors(path)
    bg = need(colors, "background", "#ffffff")
    fg = need(colors, "foreground", "#000000")
    accent = need(colors, "accent", need(colors, "orange", fg))
    selection = need(colors, "selection", need(colors, "lighter_background", bg))
    muted = need(colors, "muted", need(colors, "dark_foreground", fg))
    comment = need(colors, "dark_foreground", muted)
    if THEME_NAME.is_file() and path == COLORS:
        slug = THEME_NAME.read_text(encoding="utf-8").strip()
        name = re.sub(
            r"(^|-)([a-z])",
            lambda match: (" " if match.group(1) else "") + match.group(2).upper(),
            slug,
        ) or "Omarchy"
    else:
        name = "Omarchy"

    THEME_DIR.mkdir(parents=True, exist_ok=True)
    write(THEME_DIR / "panel.svg", svg_panel(bg, accent))
    write(THEME_DIR / "highlight.svg", svg_highlight(selection))
    write(THEME_DIR / "prev.svg", svg_chevron(muted, "prev"))
    write(THEME_DIR / "next.svg", svg_chevron(muted, "next"))
    write(THEME_DIR / "arrow.svg", svg_arrow(muted))
    write(THEME_DIR / "radio.svg", svg_radio(accent))
    write(THEME_DIR / "theme.conf", theme_conf(name, bg, fg, accent, selection, muted, comment))
    upsert_classicui(CLASSICUI)
    reload_fcitx()
    print(f"fcitx5 theme -> {name} ({bg} / {accent})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
