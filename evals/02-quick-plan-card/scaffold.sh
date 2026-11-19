#!/usr/bin/env bash
# Copies the repo's synthetic `messy` home into the workspace as ./audit-home and records
# a checksum of every file, so graders can confirm report mode changed nothing.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fixture="$here/../../tests/fixtures/messy/home"
cd "${1:-$PWD}"
cp -R "$fixture" audit-home
(cd audit-home && find . -type f -print0 | sort -z | xargs -0 shasum -a 256) > .audit-home.sha256
