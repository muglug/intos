# Intos

Fonts that are metric-compatible with Microsoft's Aptos family: text set in Aptos keeps its
line breaks and pagination when it is rendered with Intos. Only numbers are taken from Aptos
(advance widths, sidebearings, vertical metrics, kerning values); the outlines are derived from
open-source typefaces.

- `Intos.glyphs` — **Intos** (sans), derived from [Inter](https://github.com/rsms/inter).
  Four masters — Regular, Bold, Italic, Bold Italic — in final font coordinates, TrueType
  outlines, with Aptos's kerning and the `ccmp`/`locl` features and mark anchors.
- `IntosDisplay.glyphs` — **Intos Display**, the four Intos masters with the
  Aptos → Aptos Display change replayed on them: Aptos and Aptos Display are point-compatible,
  and per glyph the display cut is a horizontal remapping of the outline (stems keep their
  weight, counters and sidebearings tighten; along the slant for the italics); the same map is
  applied to each Intos glyph, with Aptos Display's advances and kerning. Generated from
  `Intos.glyphs`, not hand-edited.
- `IntosSerif.glyphs` — **Intos Serif**, derived from [Gelasio](https://github.com/SorkinType/Gelasio):
  Gelasio's full glyph set (Latin, Cyrillic, small caps, figure styles) re-proportioned to
  Aptos Serif, with Gelasio's serifs squashed to Aptos Serif's depth and lengthened to its
  overhang, Aptos Serif's metrics and kerning. The same four masters.
- `fonts/` — the built TTFs (Intos, Intos Display and Intos Serif, four styles each).

Edit in Glyphs 4 and export into `fonts/`. The shipped TTFs additionally carry a legacy `kern`
table with the same values as their GPOS kerning (Word for Mac reads only that table); a plain
Glyphs export writes GPOS kerning alone.

Licensed under the SIL Open Font License 1.1 — see `LICENSE.txt`.
