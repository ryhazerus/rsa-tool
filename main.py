#!/usr/bin/env python3
"""EMX Validator — validate IBM RSA 7.5.2 .emx UML model files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from emx.registry import Registry
from emx.resolver import Resolver
from emx.reporter import print_text, print_json, print_summary
from emx.validators.base import Severity
from emx.validators.ids import IdValidator
from emx.validators.references import ReferenceValidator
from emx.validators.structure import StructureValidator
from emx.validators.cardinality import CardinalityValidator

ALL_VALIDATORS = [
    IdValidator(),
    ReferenceValidator(),
    StructureValidator(),
    CardinalityValidator(),
]

_SEVERITY_ORDER = [Severity.INFO, Severity.WARN, Severity.ERROR]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate IBM RSA .emx UML model files for structural issues.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py ./my-rsa-project
  python main.py model.emx interfaces.emx
  python main.py ./project --format json --severity warn
  python main.py ./project --exit-code
""",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        metavar="FILE_OR_DIR",
        help=".emx file(s) or director(y/ies) to validate",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        default=False,
        help="Do not recurse into subdirectories (default: recursive)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--severity",
        choices=["info", "warn", "error"],
        default="info",
        help="Minimum severity to report (default: info)",
    )
    parser.add_argument(
        "--rules",
        metavar="RULE,...",
        help="Comma-separated list of rules to enable exclusively",
    )
    parser.add_argument(
        "--exclude-rules",
        metavar="RULE,...",
        help="Comma-separated list of rules to suppress",
    )
    parser.add_argument(
        "--exit-code",
        action="store_true",
        default=False,
        help="Exit with code 1 if any errors are found (useful for CI)",
    )

    args = parser.parse_args(argv)

    registry = Registry()
    base_dirs: list[Path] = []

    for raw in args.paths:
        p = Path(raw).resolve()
        if p.is_dir():
            base_dirs.append(p)
            registry.load_directory(p, recursive=not args.no_recursive)
        elif p.is_file():
            registry.load_file(p)
        else:
            print(f"ERROR: path not found: {p}", file=sys.stderr)
            return 2

    if not registry.files:
        print("No .emx files found.", file=sys.stderr)
        return 2

    resolver = Resolver(registry)

    # Collect issues
    issues = []
    for validator in ALL_VALIDATORS:
        issues.extend(validator.validate(registry, resolver))

    # Filter by severity
    min_sev = Severity(args.severity.upper())
    min_idx = _SEVERITY_ORDER.index(min_sev)
    issues = [i for i in issues if _SEVERITY_ORDER.index(i.severity) >= min_idx]

    # Filter by rule include/exclude lists
    if args.rules:
        allowed = {r.strip() for r in args.rules.split(",")}
        issues = [i for i in issues if i.rule in allowed]
    if args.exclude_rules:
        excluded = {r.strip() for r in args.exclude_rules.split(",")}
        issues = [i for i in issues if i.rule not in excluded]

    # Sort: errors first, then by file and line
    issues.sort(key=lambda i: (
        -_SEVERITY_ORDER.index(i.severity),
        str(i.file_path),
        i.line,
    ))

    base_dir = base_dirs[0] if len(base_dirs) == 1 else None

    if args.format == "json":
        print_json(issues)
    else:
        n_files = len(registry.files)
        print(f"Validated {n_files} file(s).\n")
        print_text(issues, base_dir=base_dir)
        print_summary(issues)

    if args.exit_code:
        has_errors = any(i.severity == Severity.ERROR for i in issues)
        return 1 if has_errors else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
