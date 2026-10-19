#!/usr/bin/env python3
"""Print a Markdown summary of a Session Test JUnit report (for $GITHUB_STEP_SUMMARY).

    python3 session/summarize.py artifacts/junit.xml "Session Test: stock, fedora 43, x86_64"
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness.util import junit_summary  # noqa: E402

if __name__ == "__main__":
    report = Path(sys.argv[1])
    title = sys.argv[2] if len(sys.argv) > 2 else "Session Test"
    if not report.exists():
        print(f"### {title}\n\nNo JUnit report at `{report}`: the image build or the run failed before pytest.\n")
        sys.exit(0)
    print(junit_summary(report.read_text(), title))
