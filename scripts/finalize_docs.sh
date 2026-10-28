#!/usr/bin/env bash
# Build every Word deliverable from docs/report/*.yaml, then (macOS + Microsoft Word) update the tables of
# contents / lists of figures and tables and export a PDF next to each .docx.
# Usage: ./scripts/finalize_docs.sh [--no-build] [deliverables/X.docx ...]
set -uo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
BUILD=1
if [[ "${1:-}" == "--no-build" ]]; then BUILD=0; shift; fi
if [[ $BUILD == 1 ]]; then
  "$PY" scripts/collect_results.py
  "$PY" scripts/build_docs.py docs/report/final_report.yaml docs/report/midterm_report.yaml docs/report/d2.yaml \
    docs/report/d3.yaml docs/report/d4.yaml docs/report/d5.yaml docs/report/d6.yaml
fi
if [[ "$(uname)" != "Darwin" ]] || [[ ! -d "/Applications/Microsoft Word.app" ]]; then
  echo "Microsoft Word not found: open each .docx, right-click the tables of contents and choose Update Field."; exit 0
fi
start_word() {
  # A fresh Word that has finished launching (recovery panes, splash) accepts automation reliably.
  osascript -e 'with timeout of 15 seconds' -e 'tell application "Microsoft Word" to quit saving no' -e 'end timeout' >/dev/null 2>&1
  sleep 3; pkill -f "Microsoft Word.app/Contents/MacOS/Microsoft Word" 2>/dev/null; sleep 2
  open -g -a "Microsoft Word"; sleep 25
}
docs=("$@"); [[ ${#docs[@]} -eq 0 ]] && docs=(deliverables/*.docx)
start_word
for docx in "${docs[@]}"; do
  abs="$(cd "$(dirname "$docx")" && pwd)/$(basename "$docx")"; pdf="${abs%.docx}.pdf"
  for attempt in 1 2 3; do
    if perl -e 'alarm 2400; exec @ARGV' osascript scripts/word_finalize.applescript "$abs" "$pdf" >/dev/null 2>&1; then
      echo "finalised $(basename "$docx") -> $(basename "$pdf")"; break
    fi
    echo "Word automation failed for $(basename "$docx") (attempt $attempt); restarting Word"; start_word
  done
done
