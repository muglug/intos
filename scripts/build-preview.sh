#!/usr/bin/env bash

# Rebuilds preview.png from the bundled fonts. Requires ImageMagick (`magick`).
# Usage: ./scripts/build-preview.sh [output-path]

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "$script_dir/.." && pwd)"
font_dir="$repo_dir/fonts"
output_path="${1:-$repo_dir/preview.png}"
magick_bin="${MAGICK:-magick}"

if ! command -v "$magick_bin" >/dev/null 2>&1; then
  echo "ImageMagick is required (expected the 'magick' command)." >&2
  exit 1
fi

text_regular="$font_dir/Intos-Regular.ttf"
display_regular="$font_dir/IntosDisplay-Regular.ttf"
display_bold="$font_dir/IntosDisplay-Bold.ttf"

for font_path in "$text_regular" "$display_regular" "$display_bold"; do
  if [[ ! -f "$font_path" ]]; then
    echo "Missing font: $font_path" >&2
    exit 1
  fi
done

preview_tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/intos-preview.XXXXXX")"
trap 'rm -rf -- "$preview_tmp_dir"' EXIT

printf '%s\n%s\n' \
  'A computer is a device that can be instructed to carry out arbitrary sequences of arithmetic or logical operations automatically. The ability of computers to follow generalized sets of operations, called programs, enables them to perform an extremely wide range of tasks.' \
  'Such computers are used as control systems for a very wide variety of industrial and consumer devices. This includes simple special purpose devices like microwave ovens and remote controls, factory devices such as industrial robots and computer assisted design, but also in general purpose devices like personal computers and mobile devices such as smartphones. The Internet is run on computers and it connects millions of other computers.' \
  > "$preview_tmp_dir/en.txt"

printf '%s\n' \
  "Tanken om programstyrede regnemaskiner har rødder tilbage til det industrielle gennembrud i England omkring 1800. Den fremgår f.eks. af Jacquards mønstervæv og Charles Babbages udviklingsarbejde. Hulkortmaskinerne var også programmerbare. Herman Hollerith/IBM's maskiner blev programmeret med koblingstavler, mens Powers benyttede connectionboxe. I slutningen af 1920'erne dukkede de første naturvidenskabelige hulkortanvendelser op. De spillede ikke den store mængdemæssige rolle, men var vigtige for den fortsatte tekniske udvikling. Der var tale om analytisk statistik og udarbejdelse af astronomiske tabeller." \
  > "$preview_tmp_dir/da.txt"

printf '%s\n' \
  'Charles Babbage und Ada Lovelace gelten durch die von Babbage 1837 entworfene Rechenmaschine Analytical Engine als Vordenker des modernen universell programmierbaren Computers. Konrad Zuse (Z3, 1941 und Z4, 1945), John Presper Eckert und John William Mauchly (ENIAC, 1946) bauten die ersten funktionstüchtigen Geräte dieser Art. Bei der Klassifizierung eines Geräts als universell programmierbarer Computer spielt die Turing-Vollständigkeit eine wesentliche Rolle. Sie ist benannt nach dem englischen Mathematiker Alan Turing, der 1936 das logische Modell der Turingmaschine eingeführt hatte. Die frühen Computer wurden auch (Groß-)Rechner genannt; ihre Ein- und Ausgabe der Daten war zunächst auf Zahlen beschränkt.' \
  > "$preview_tmp_dir/de.txt"

printf '%s\n' \
  'Počítač je v informatice zařízení a výpočetní technika, která zpracovává data pomocí předem vytvořeného programu. Současný počítač je elektronický a skládá se z hardwaru, který představuje fyzické části počítače (mikroprocesor, klávesnice, monitor atd.) a ze softwaru (operační systém a programy). Počítač je zpravidla ovládán uživatelem, který poskytuje počítači data ke zpracování prostřednictvím jeho vstupních zařízení a počítač výsledky prezentuje pomocí výstupních zařízení. V současnosti jsou počítače využívány téměř ve všech oborech lidské činnosti.' \
  > "$preview_tmp_dir/cs.txt"

render_body() {
  local language="$1"
  local width="$2"

  "$magick_bin" \
    -background none \
    -fill '#111111' \
    -font "$text_regular" \
    -pointsize 34 \
    -size "${width}x" \
    -interline-spacing 0 \
    "caption:@$preview_tmp_dir/$language.txt" \
    "$preview_tmp_dir/body-$language.png"
}

render_label() {
  local language="$1"
  local label="$2"

  "$magick_bin" \
    -background none \
    -fill '#a5a5a5' \
    -font "$text_regular" \
    -pointsize 24 \
    "label:$label" \
    -trim +repage \
    "$preview_tmp_dir/label-$language.png"
}

render_body en 638
render_body da 638
render_body de 634
render_body cs 638

render_label en 'ENGLISH'
render_label da 'DANSK (DANISH)'
render_label de 'DEUTSCH (GERMAN)'
render_label cs 'ČESKÝ (CZECH)'

"$magick_bin" \
  -size 2048x2478 xc:white \
  -fill none \
  -stroke '#d5d5d5' \
  -strokewidth 2 \
  -draw 'line 0,730 638,730 line 707,730 1345,730 line 1414,730 2048,730 line 0,1715 638,1715 line 707,1715 2048,1715' \
  -stroke none \
  -fill '#000000' \
  -font "$display_regular" \
  -pointsize 120 \
  -draw 'text 0,100 "ABCDEFGHIJKLMN" text 0,219 "OPQRSTUVWXYZ.," text 0,336 "abcdefghijklmnopq" text 0,451 "rstuvwxyz () & ?! @" text 0,573 "1234567890 ⌘/→"' \
  -font "$display_bold" \
  -draw 'text 1055,100 "ABCDEFGHIJKLMN" text 1055,219 "OPQRSTUVWXYZ.," text 1055,336 "abcdefghijklmnopq" text 1055,451 "rstuvwxyz () & ?! @" text 1055,573 "1234567890 ⌘/→"' \
  -pointsize 106 \
  -draw 'text 707,1860 "The user interface in the" text 707,1964 "industrial design field of" text 707,2068 "human-computer interaction" text 707,2172 "is the space where" text 707,2276 "interactions between" text 707,2380 "humans and machines occur."' \
  "$preview_tmp_dir/base.png"

"$magick_bin" \
  "$preview_tmp_dir/base.png" \
  "$preview_tmp_dir/label-en.png" -geometry +1+743 -composite \
  "$preview_tmp_dir/label-da.png" -geometry +707+741 -composite \
  "$preview_tmp_dir/label-de.png" -geometry +1414+741 -composite \
  "$preview_tmp_dir/label-cs.png" -geometry +1+1720 -composite \
  "$preview_tmp_dir/body-en.png" -geometry +0+806 -composite \
  "$preview_tmp_dir/body-da.png" -geometry +707+806 -composite \
  "$preview_tmp_dir/body-de.png" -geometry +1414+806 -composite \
  "$preview_tmp_dir/body-cs.png" -geometry +0+1787 -composite \
  -strip \
  -define png:compression-level=9 \
  "$preview_tmp_dir/preview.png"

cp "$preview_tmp_dir/preview.png" "$output_path"
echo "Wrote $output_path"
