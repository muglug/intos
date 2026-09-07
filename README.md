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
- `IntosNarrow.glyphs` — **Intos Narrow**, likewise with the Aptos → Aptos Narrow change
  (narrower advances and counters, raised x-height, Aptos Narrow's metrics and kerning)
- `IntosSerif.glyphs` — **Intos Serif**, derived from [Gelasio](https://github.com/SorkinType/Gelasio):
  Gelasio's full glyph set (Latin, Cyrillic, small caps, figure styles) re-proportioned to
  Aptos Serif, with Gelasio's serifs squashed to Aptos Serif's depth and lengthened to its
  overhang, Aptos Serif's metrics and kerning.
- `fonts/` — the built TTFs (Intos, Intos Display, Intos Narrow and Intos Serif).

Edit the sources in Glyphs 4, then rebuild without opening Glyphs:

```sh
./scripts/build-fonts.sh
./scripts/build-preview.sh
```

The first font build requires Python 3.10+ and an internet connection to install
the pinned fontmake toolchain into `build/venv`. Later builds work offline.
No Glyphs installation is required. To build selected families or use another
output folder:

```sh
./scripts/build-fonts.sh --family IntosDisplay --family IntosNarrow
./scripts/build-fonts.sh --output-dir build/fonts
```

The build exports all active static instances, applies their export parameters,
adds TrueType autohinting, and validates the staged fonts before replacing the
outputs. Sources are never rewritten. Quadratic contours retain their overlaps;
empty italic alternate layers use the matching upright master's outlines, matching Glyphs.
The compiler and autohinter differ from Glyphs, so binary files and small-size
rasterization may differ from native exports.

Licensed under the SIL Open Font License 1.1 — see `LICENSE.txt`.
