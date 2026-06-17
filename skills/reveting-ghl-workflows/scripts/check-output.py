#!/usr/bin/env python3
"""
check-output.py — Reveting GHL Workflows Output Validator

Validates that a generated deliverable document contains all required sections
and keywords for a complete Reveting GHL Workflows implementation spec.

Usage:
    python3 check-output.py <path_to_markdown_file>

Exit codes:
    0 — All checks passed
    1 — One or more checks failed
    2 — File not found or unreadable
"""

import sys
import os

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Keywords that MUST appear somewhere in the deliverable
REQUIRED_KEYWORDS = [
    "pipeline",
    "workflow",
    "guest",
    "automation",
    "sequence",
    "trigger",
]

# Minimum character count for a meaningful document
MIN_CHAR_COUNT = 200


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(filepath: str) -> dict:
    """Run all checks and return a result dict."""
    results = {
        "file_exists": False,
        "min_length": False,
        "keywords_found": [],
        "keywords_missing": [],
        "passed": False,
    }

    # Read file
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"[FAIL] File not found: {filepath}")
        return results
    except IOError as exc:
        print(f"[FAIL] Cannot read file: {exc}")
        return results

    results["file_exists"] = True

    # Length check
    char_count = len(content)
    if char_count >= MIN_CHAR_COUNT:
        results["min_length"] = True
        print(f"[PASS] Document length: {char_count} chars (min {MIN_CHAR_COUNT})")
    else:
        print(f"[FAIL] Document length: {char_count} chars (min {MIN_CHAR_COUNT})")

    # Keyword checks
    content_lower = content.lower()
    for kw in REQUIRED_KEYWORDS:
        if kw.lower() in content_lower:
            results["keywords_found"].append(kw)
            print(f"[PASS] Keyword found: '{kw}'")
        else:
            results["keywords_missing"].append(kw)
            print(f"[FAIL] Keyword missing: '{kw}'")

    # Overall pass / fail
    all_keywords_ok = len(results["keywords_missing"]) == 0
    results["passed"] = results["min_length"] and all_keywords_ok

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {os.path.basename(__file__)} <path_to_markdown_file>")
        print()
        print("Validates that a Reveting GHL Workflows deliverable contains all")
        print("required sections and keywords.")
        sys.exit(1)

    filepath = sys.argv[1]
    print(f"Validating: {filepath}")
    print("-" * 60)

    results = validate(filepath)

    print("-" * 60)
    if results["file_exists"] and results["passed"]:
        print("RESULT: PASS — All checks passed ✓")
        sys.exit(0)
    elif not results["file_exists"]:
        print("RESULT: FAIL — File could not be read")
        sys.exit(2)
    else:
        print("RESULT: FAIL — One or more checks failed ✗")
        if results["keywords_missing"]:
            print(f"  Missing keywords: {', '.join(results['keywords_missing'])}")
        if not results["min_length"]:
            print(f"  Document is shorter than {MIN_CHAR_COUNT} characters")
        sys.exit(1)


if __name__ == "__main__":
    main()
