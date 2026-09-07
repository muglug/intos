#!/usr/bin/env python3
"""Compile static instances in a staging directory, validate, then publish TTFs."""
import argparse
import copy
import hashlib
import logging
from pathlib import Path
import tempfile
import unicodedata

from fontmake.font_project import FontProject
from fontTools.ttLib import TTFont
from glyphsLib import GSFont

ROOT = Path(__file__).resolve().parent.parent
FAMILIES = ('Intos', 'IntosDisplay', 'IntosNarrow', 'IntosSerif')


def prepare_source(font):
    """Match Glyphs' upright fallback and enclosing-mark advance behavior."""
    italic_axis = next(i for i, axis in enumerate(font.axes) if axis.axisTag == 'ital')
    for glyph in font.glyphs:
        for master in font.masters:
            layer = glyph.layers[master.id]
            upright = next((m for m in font.masters if m.axes[italic_axis] == 0
                            and all(m.axes[i] == master.axes[i] for i in range(len(font.axes))
                                    if i != italic_axis)), font.masters[0])
            default = glyph.layers[upright.id]
            # Glyphs exports the upright master for empty alternate layers (a.1
            # and its accented forms). fontmake otherwise emits blank glyphs.
            if not layer.shapes and default.shapes:
                replacement = copy.deepcopy(default, {id(glyph): glyph})
                replacement.layerId = master.id
                replacement.associatedMasterId = master.id
                glyph.layers[master.id] = replacement
        # glyphsLib zeros Mn marks but currently leaves enclosing (Me) marks wide.
        if any(unicodedata.category(chr(int(u, 16))) == 'Me' for u in glyph.unicodes):
            for layer in glyph.layers:
                layer.width = 0


def validate(path, expected_name):
    with TTFont(path, checkChecksums=2) as font:
        for tag in font.keys():
            font[tag]  # Force full table decoding before replacing any outputs.
        required = {'glyf', 'cmap', 'hmtx', 'GSUB', 'GPOS', 'GDEF', 'fpgm', 'prep'}
        if not required.issubset(font.keys()):
            raise ValueError(f'{path.name}: missing tables {required - set(font.keys())}')
        if font['name'].getDebugName(6) != expected_name:
            raise ValueError(f'{path.name}: unexpected PostScript name')
        if not set(range(32, 127)).issubset(font.getBestCmap()):
            raise ValueError(f'{path.name}: missing printable ASCII characters')
        if font['head'].unitsPerEm != 2048:
            raise ValueError(f'{path.name}: unexpected em size')
        return len(font.getBestCmap())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--family', choices=FAMILIES, action='append',
                        help='Build only this family; repeat to select several.')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'fonts')
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    sources = [ROOT / f'{family}.glyphs' for family in dict.fromkeys(args.family or FAMILIES)]
    hashes = {p: hashlib.sha256(p.read_bytes()).digest() for p in sources}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # Stage on the same filesystem so each final replacement is atomic.
    with tempfile.TemporaryDirectory(prefix='.font-build-', dir=args.output_dir) as temp:
        staging = Path(temp)
        outputs = []
        for source in sources:
            print(f'Building {source.stem}…', flush=True)
            font = GSFont(str(source))
            instances = [i for i in font.instances if i.active]
            masters = {m.id for m in font.masters}
            for instance in instances:
                weights = {k: v for k, v in instance.instanceInterpolations.items() if v}
                if len(weights) != 1 or next(iter(weights)) not in masters or next(iter(weights.values())) != 1:
                    raise ValueError(f'{source.name}: {instance.name} must select exactly one master')
            prepare_source(font)
            prepared = staging / source.name
            font.save(str(prepared))
            # Instances apply export parameters, including Serif's Remove Glyphs.
            # Keep the imported quadratic contours; boolean overlap removal fails
            # on these sources. ufo2ft also handles extended GPOS lookups itself.
            FontProject().run_from_glyphs(
                str(prepared), output=('ttf',), output_dir=str(staging),
                interpolate=True, remove_overlaps=False, autohint=True,
                use_production_names=True,
            )
            for instance in instances:
                name = instance.customParameters['postscriptFontName']
                if not name:
                    raise ValueError(f'{source.name}: missing PostScript name')
                path = staging / f'{name}.ttf'
                count = validate(path, name)
                outputs.append(path)
                print(f'  {path.name}: {count} characters, validated', flush=True)
        if any(hashlib.sha256(p.read_bytes()).digest() != digest for p, digest in hashes.items()):
            raise RuntimeError('A source changed during the build. Run again to export the latest edits.')
        for path in outputs:
            path.replace(args.output_dir / path.name)
    print(f'Built {len(outputs)} TTFs in {args.output_dir.resolve()}', flush=True)


if __name__ == '__main__':
    main()
