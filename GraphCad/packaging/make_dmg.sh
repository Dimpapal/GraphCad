#!/bin/sh
set -eu
task_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
task_dist="$task_root/dist"
task_stage=$(mktemp -d "${TMPDIR:-/tmp}/graphcad-dmg.XXXXXX")
trap 'rm -rf "$task_stage"' EXIT INT TERM
test -d "$task_dist/GraphCad.app" || { echo 'Build GraphCad.app first with python scripts/build.py'; exit 1; }
/usr/bin/ditto "$task_dist/GraphCad.app" "$task_stage/GraphCad.app"
ln -s /Applications "$task_stage/Applications"
cp "$task_root/docs/LICENSES.md" "$task_stage/Dependency licenses.txt"
/usr/bin/hdiutil create -volname GraphCad -srcfolder "$task_stage" -ov -format UDZO "$task_dist/GraphCad-1.1.0-macOS-$(uname -m).dmg"
