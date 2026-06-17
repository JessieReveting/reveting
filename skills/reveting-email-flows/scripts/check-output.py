#!/usr/bin/env python3
"""
check-output.py — Reveting Email Flows Validator

Validates that email flow output files contain required terms and meet
minimum content thresholds.

Usage:
    python3 check-output.py <file_path>
    python3 check-output.py <file_path> [--verbose]
"""

import sys
import os
import argparse

# Required terms that must appear in valid email flow output
REQUIRED_TERMS = [
    "sequence",
    "guest",
    "confirmation",
    "replay",
    "subject",
    "nurture",
]

# Minimum character count for valid output
MIN_CHAR_COUNT = 200


def validate_file(file_path: str, verbose: bool = False) -> dict:
    """
    Validate a single file against required terms and minimum length.

    Args:
        file_path: Path to the file to validate.
        verbose: If True, print detailed results.

    Returns:
        dict with keys: file, valid, char_count, terms_found, terms_missing
    """
    result = {
        "file": file_path,
        "valid": True,
        "char_count": 0,
        "terms_found": [],
        "terms_missing": [],
    }

    # Check file exists
    if not os.path.isfile(file_path):
        result["valid"] = False
        result["error"] = f"File not found: {file_path}"
        if verbose:
            print(f"[FAIL] {file_path} — file not found")
        return result

    # Read file content
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        result["valid"] = False
        result["error"] = f"Read error: {e}"
        if verbose:
            print(f"[FAIL] {file_path} — {e}")
        return result

    result["char_count"] = len(content)

    # Check minimum character count
    if result["char_count"] < MIN_CHAR_COUNT:
        result["valid"] = False
        if verbose:
            print(
                f"[FAIL] {file_path} — {result['char_count']} chars "
                f"(minimum {MIN_CHAR_COUNT})"
            )

    # Check required terms (case-insensitive)
    content_lower = content.lower()
    for term in REQUIRED_TERMS:
        if term.lower() in content_lower:
            result["terms_found"].append(term)
        else:
            result["terms_missing"].append(term)
            result["valid"] = False

    # Verbose output
        if verbose:
        status = "PASS" if result["valid"] else "FAIL"
        print(f"[{status}] {file_path}")
        print(f"  Characters: {result['char_count']} (min: {MIN_CHAR_COUNT})")
        print(f"  Terms found:    {', '.join(result['terms_found']) or 'none'}")
        print(
            f"  Terms missing:  {', '.join(result['terms_missing']) or 'none'}"
        )

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Validate reveting email flow output files."
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="One or more file paths to validate.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed validation results.",
    )

    args = parser.parse_args()

    all_valid = True
    results = []

    for file_path in args.files:
        result = validate_file(file_path, verbose=args.verbose)
        results.append(result)
        if not result["valid"]:
            all_valid = False

    # Summary
    if not args.verbose:
        for result in results:
            status = "PASS" if result["valid"] else "FAIL"
            print(f"[{status}] {result['file']}")

    passed = sum(1 for r in results if r["valid"])
    failed = sum(1 for r in results if not r["valid"])
    print(f"\n{passed}/{len(results)} passed, {failed} failed")

    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()
