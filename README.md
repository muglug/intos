# Intos

A small typeface family designed to be metric-compatible with Microsoft's Aptos family.

Based on [Inter](https://github.com/rsms/inter) and [Gelasio](https://github.com/SorkinType/Gelasio), with a series of manual and programmatic alterations.

![Intos type specimen](preview.png)

Text set in Aptos keeps its line breaks and pagination when it is rendered with Intos.

- `Intos.glyphs` — **Intos** (sans), derived from [Inter](https://github.com/rsms/inter).
  Four masters — Regular, Bold, Italic, Bold Italic — in final font coordinates, TrueType
  outlines, with Aptos's kerning and the `ccmp`/`locl` features and mark anchors.
- `IntosDisplay.glyphs` — **Intos Display**, the four Intos masters with the
  Aptos → Aptos Display change replayed on them programmatically
- `IntosSerif.glyphs` — **Intos Serif**, derived from [Gelasio](https://github.com/SorkinType/Gelasio):
  Gelasio's full glyph set (Latin, Cyrillic, small caps, figure styles) re-proportioned to
  Aptos Serif, with Gelasio's serifs squashed to Aptos Serif's depth and lengthened to its
  overhang, Aptos Serif's metrics and kerning.
- `fonts/` — the built TTFs (Intos, Intos Display and Intos Serif).

Edit in Glyphs 4 and export into `fonts/`.

Licensed under the SIL Open Font License 1.1 — see `LICENSE.txt`.
