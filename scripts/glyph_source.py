"""Small serialization helpers for targeted edits to native Glyphs sources.

These helpers do not load/save or normalize whole packages. Keep calculations at
full precision, then use encode_nodes only for the contours being edited.
"""

from decimal import Decimal, ROUND_HALF_UP
import re


def format_coordinate(value):
    """Serialize a computed coordinate at Glyphs' observed 0.001-unit precision."""
    # Preserve the binary coordinate before rounding: native saves round the
    # exact 1327.3125 upward but 895.0785 (stored just below the tie) downward.
    number = Decimal.from_float(float(value))
    if not number.is_finite():
        raise ValueError(f"Non-finite glyph coordinate: {value!r}")
    rounded = number.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    result = format(rounded, "f").rstrip("0").rstrip(".")
    return "0" if result == "-0" else result


def encode_nodes(nodes):
    """Encode (x, y, node_type, smooth) tuples as a native nodes-list body."""
    types = {"offcurve": "o", "qcurve": "q", "curve": "c", "line": "l"}
    result = []
    for x, y, node_type, smooth in nodes:
        kind = types[node_type]
        if smooth:
            kind += "s"
        result.append(f"({format_coordinate(x)},{format_coordinate(y)},{kind})")
    return ",\n".join(result)


def strip_last_change(text):
    """Omit Glyphs' discarded edit timestamp from an intentionally edited file."""
    return re.sub(r'^lastChange = [^\n]*;\n', '', text, flags=re.MULTILINE)
