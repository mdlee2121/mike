#!/usr/bin/env bash
# Build dist/mfn-label-run.zip: SKILL.md plus the mfn code, for upload as a Cowork skill.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m unittest discover -s tests -t . >/dev/null
rm -rf dist/mfn-label-run && mkdir -p dist/mfn-label-run
cp skills/mfn-label-run/SKILL.md dist/mfn-label-run/
cp -r mfn dist/mfn-label-run/
find dist/mfn-label-run -name __pycache__ -prune -exec rm -rf {} +
(cd dist && rm -f mfn-label-run.zip && python3 -m zipfile -c mfn-label-run.zip mfn-label-run)
echo "dist/mfn-label-run.zip"
