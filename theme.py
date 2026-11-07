"""Reads the design tokens from Theme.qml so Python widgets use the same values as QML.

Theme.qml stays the single source of truth for colors, font and sizes. Only simple
`readonly property color|string|int name: value` lines are understood.
"""
import re
from pathlib import Path

_PROPERTY = re.compile(r'readonly\s+property\s+(color|string|int)\s+(\w+)\s*:\s*("([^"]*)"|-?\d+)')


def load_theme(path):
    """Returns {"chrome": "#1b1b1b", "fontSize": 14, ...} (colors and strings as str, ints as int)."""
    tokens = {}
    for kind, name, raw, text in _PROPERTY.findall(Path(path).read_text(encoding="utf-8")):
        tokens[name] = int(raw) if kind == "int" else text
    return tokens
