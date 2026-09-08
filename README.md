# Intos

A small typeface family designed to be metric-compatible with Microsoft's Aptos family.

Based on [Inter](https://github.com/rsms/inter) and [Gelasio](https://github.com/SorkinType/Gelasio), with a series of manual and programmatic alterations.

![Intos type specimen](preview.png)

Text set in Aptos keeps its line breaks and pagination when it is rendered with Intos.

- `Intos.glyphspackage` — **Intos** (sans), derived from [Inter](https://github.com/rsms/inter).
  Regular, Bold, Italic, Bold Italic, and Semibold / Semibold Italic review masters, in final font coordinates, TrueType
  outlines, with Aptos's kerning and the `ccmp`/`locl` features and mark anchors.
- `IntosDisplay.glyphspackage` — **Intos Display**, the four Intos masters with the
  Aptos → Aptos Display change replayed on them programmatically
- `IntosNarrow.glyphspackage` — **Intos Narrow**, likewise with the Aptos → Aptos Narrow change
  (narrower advances and counters, raised x-height, Aptos Narrow's metrics and kerning)
- `IntosSerif.glyphspackage` — **Intos Serif**, derived from [Gelasio](https://github.com/SorkinType/Gelasio):
  Gelasio's full glyph set (Latin, Cyrillic, small caps, figure styles) re-proportioned to
  Aptos Serif, with Gelasio's serifs squashed to Aptos Serif's depth and lengthened to its
  overhang, Aptos Serif's metrics and kerning.
- `fonts/` — the built TTFs (Intos, Intos Display, Intos Narrow and Intos Serif).

Each source is a native Glyphs package. Open the `.glyphspackage` in Glyphs 4
as usual; in Finder, choose **Show Package Contents** to browse its files.

- `glyphs/g.glyph` contains all masters of lowercase **g**; each glyph has its own file.
- `glyphs/G_.glyph` contains uppercase **G** (underscores distinguish uppercase filenames).
- `fontinfo.plist` contains shared metrics, kerning, features, and export settings.
- `order.plist` preserves glyph order; `UIState.plist` stores editor tabs separately.

Edit these packages, then rebuild without opening Glyphs:

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

The upright **Semibold** is a weight-600 review master. It starts with Inter 4.1
Semibold, with the Inter Regular → Intos Regular outline transformations
reconstructed from corresponding contours and replayed on Inter Semibold.
This carries across the lowercase height, proportions, and symbol placement.
Aptos supplies advance widths, vertical metric tables, and kerning for shared
characters; its ink bounds are not used to fit outlines. The glyphs listed in
`design/semibold-custom-glyphs.json` use a two-thirds blend of the edited Intos
Regular and Bold outlines, without any subsequent outline scaling. Where a
Regular construction cannot be mapped reliably,
the generator reuses a related base-glyph map or interpolates the Intos drawings;
`build/semibold/provenance.json` records the method and reconstruction error for
each glyph. Regeneration preserves existing custom Semibold drawings.

The **Semibold Italic** review master blends the Italic and Bold Italic masters
at two thirds (`scripts/create-semibold-italic.py`), keeping the Italic's node
structure: every Italic segment becomes one segment whose ends meet their
counterparts on the Bold Italic (nearest points walked monotonically around the
contour, so differing node structures do not matter) and whose handle is fitted
to the blended curve; straight segments stay straight and implied on-curve
points stay implied. Replaying Inter's semibold through a recovered deformation,
as for the upright, scattered hundreds of nodes over the italics and extrapolated
badly, so it is not used here. Blends that fail a plausibility check (points far
from both masters, or a bounding box or area outside theirs) retry with the Bold
Italic's structure, then the arc-length interpolation; the few remaining glyphs
keep the Italic outline and are listed for review. Aptos SemiBold Italic supplies
advances, vertical metrics and kerning. The i/j family then has its dots centred
on Aptos SemiBold Italic's, like the other italics, and the g family takes the
upright Semibold g sheared 9.5° with the upper storey sheared back 2° about its
centre, its accents from the blend. `build/semibold-italic/provenance.json`
records the method per glyph.

The ordinary font build exports `fonts/Intos-Semibold.ttf` and
`fonts/Intos-SemiboldItalic.ttf` from these editable masters. The creation
scripts record the workflow and require the original Inter and Aptos files;
they refuse to overwrite an existing master unless explicitly asked to
regenerate the review master. The optional creation
and comparison tools use `scripts/review-requirements.txt` (Python 3.12+).

Licensed under the SIL Open Font License 1.1 — see `LICENSE.txt`.
