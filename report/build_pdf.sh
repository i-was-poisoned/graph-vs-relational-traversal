#!/usr/bin/env bash
# Build report/report.pdf from report/report.html with Microsoft Edge (headless).
#
# Usage (from Git Bash, anywhere in the project):
#     ./report/build_pdf.sh
#
# Edge runs with its own temporary profile (--user-data-dir), so it doesn't
# clash with a normal Edge window that may already be open.
# Close report.pdf in any viewer first, or the file may be locked.

set -eo pipefail
cd "$(dirname "$0")"

EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
PROFILE="$(cygpath -w /tmp)\\edge-pdf-profile"
HTML="file:///$(cygpath -m "$PWD/report.html")"
PDF="$(cygpath -w "$PWD/report.pdf")"

# Edge prints some internal "[...ERROR:...]" lines (company settings, sync) that
# have nothing to do with the PDF, so they're filtered out.
timeout 90 "$EDGE" --headless --disable-gpu --no-first-run --user-data-dir="$PROFILE" \
    --no-pdf-header-footer --print-to-pdf="$PDF" "$HTML" 2>&1 | grep -v "^\[.*ERROR:" || true

echo "PDF ready: report/report.pdf"
