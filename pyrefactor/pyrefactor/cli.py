import argparse
import os
import sys
from typing import List, Optional

from .analyzer import Analyzer
from .models import SmellResult, RefactoringChange, RefactoringProposal, RefactorReport, SmellType
from .report import ReportGenerator


def main():
    parser = argparse.ArgumentParser(
        description="PyRefactor - Python code smell detection and automated refactoring tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pyrefactor check myfile.py
  pyrefactor check ./src/
  pyrefactor check ./src/ --config .pyrefactor.yaml
  pyrefactor refactor ./src/ --auto --backup
  pyrefactor refactor ./src/ --preview
        """,
    )

    parser.add_argument(
        "--version", action="version", version="pyrefactor 0.1.0"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    check_parser = subparsers.add_parser("check", help="Check for code smells")
    check_parser.add_argument(
        "path", help="File or directory to check for code smells"
    )
    check_parser.add_argument(
        "--config", "-c", help="Path to configuration file (YAML)", default=None
    )
    check_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text",
        help="Output format (default: text)"
    )
    check_parser.add_argument(
        "--output", "-o", help="Output report to file", default=None
    )
    check_parser.add_argument(
        "--no-vcs", action="store_true", help="Disable VCS integration (check all files)"
    )
    check_parser.add_argument(
        "--rule", "-r", action="append", help="Run only specific rules", default=None
    )

    refactor_parser = subparsers.add_parser(
        "refactor", help="Check for code smells and apply refactoring"
    )
    refactor_parser.add_argument(
        "path", help="File or directory to refactor"
    )
    refactor_parser.add_argument(
        "--config", "-c", help="Path to configuration file (YAML)", default=None
    )
    refactor_parser.add_argument(
        "--auto", action="store_true",
        help="Apply refactoring automatically without confirmation"
    )
    refactor_parser.add_argument(
        "--preview", action="store_true",
        help="Preview refactoring changes without applying"
    )
    refactor_parser.add_argument(
        "--backup", action="store_true",
        help="Create backup files before refactoring (.bak)"
    )
    refactor_parser.add_argument(
        "--format", "-f", choices=["text", "json"], default="text",
        help="Output format (default: text)"
    )
    refactor_parser.add_argument(
        "--output", "-o", help="Output report to file", default=None
    )
    refactor_parser.add_argument(
        "--no-vcs", action="store_true", help="Disable VCS integration"
    )
    refactor_parser.add_argument(
        "--rule", "-r", action="append", help="Run only specific rules", default=None
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "check":
        run_check(args)
    elif args.command == "refactor":
        run_refactor(args)


def _should_skip_untracked(file_path: str, skip_untracked: bool) -> bool:
    if not skip_untracked:
        return False
    from .vcs import get_untracked_files, is_git_repository

    parent_dir = os.path.dirname(os.path.abspath(file_path))
    if not is_git_repository(parent_dir):
        return False
    untracked = get_untracked_files(parent_dir)
    norm_path = os.path.normpath(os.path.abspath(file_path))
    return norm_path in untracked


def run_check(args):
    analyzer = Analyzer(args.config)
    skip_untracked = analyzer.config.get("vcs", {}).get("skip_untracked", True)
    if args.no_vcs:
        skip_untracked = False
        analyzer.config["vcs"]["skip_untracked"] = False

    if args.rule:
        for rule_name in analyzer.config["rules"]:
            analyzer.config["rules"][rule_name]["enabled"] = False
        for rule_name in args.rule:
            if rule_name in analyzer.config["rules"]:
                analyzer.config["rules"][rule_name]["enabled"] = True
        analyzer._init_detectors()

    path = os.path.abspath(args.path)

    if os.path.isfile(path):
        if skip_untracked and _should_skip_untracked(path, skip_untracked):
            print(f"Skipping untracked file: {path}")
            print(f"Use --no-vcs to check all files.")
            sys.exit(0)
        smells = analyzer.analyze_file(path)
    elif os.path.isdir(path):
        smells = analyzer.analyze_directory(path)
    else:
        print(f"Error: Path not found: {path}", file=sys.stderr)
        sys.exit(1)

    report = RefactorReport()
    files_set = set()
    for smell in smells:
        report.add_smell(smell)
        files_set.add(smell.location.file_path)
    report.files_processed = len(files_set) if os.path.isdir(path) else 1
    report.files_with_smells = len(files_set)

    generator = ReportGenerator(report)

    if args.format == "json":
        output = generator.generate_json(smells, {})
    else:
        output = generator.generate_text(smells, {})

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to {args.output}")
    else:
        print(output)

    if report.total_smells > 0:
        sys.exit(1)


def run_refactor(args):
    analyzer = Analyzer(args.config)
    skip_untracked = analyzer.config.get("vcs", {}).get("skip_untracked", True)
    if args.no_vcs:
        skip_untracked = False
        analyzer.config["vcs"]["skip_untracked"] = False

    if args.rule:
        for rule_name in analyzer.config["rules"]:
            analyzer.config["rules"][rule_name]["enabled"] = False
        for rule_name in args.rule:
            if rule_name in analyzer.config["rules"]:
                analyzer.config["rules"][rule_name]["enabled"] = True
        analyzer._init_detectors()

    path = os.path.abspath(args.path)

    if os.path.isfile(path):
        if skip_untracked and _should_skip_untracked(path, skip_untracked):
            print(f"Skipping untracked file: {path}")
            print(f"Use --no-vcs to check all files.")
            sys.exit(0)
        smells = analyzer.analyze_file(path)
    elif os.path.isdir(path):
        smells = analyzer.analyze_directory(path)
    else:
        print(f"Error: Path not found: {path}", file=sys.stderr)
        sys.exit(1)

    report = RefactorReport()
    files_set = set()
    for smell in smells:
        report.add_smell(smell)
        files_set.add(smell.location.file_path)
    report.files_processed = len(files_set) if os.path.isdir(path) else 1
    report.files_with_smells = len(files_set)

    refactoring_changes = {}

    auto_refactorable = [s for s in smells if s.can_auto_refactor]
    for smell in auto_refactorable:
        change = analyzer.create_refactoring(smell, smell.location.file_path)
        if change:
            file_path = smell.location.file_path
            if file_path not in refactoring_changes:
                refactoring_changes[file_path] = []
            refactoring_changes[file_path].append((change, smell))

    if args.preview:
        _show_preview(refactoring_changes)
    elif args.auto:
        _apply_refactoring(refactoring_changes, args.backup, report)
    else:
        if refactoring_changes:
            _show_preview(refactoring_changes)
            response = input("\nApply these changes? [y/N]: ").strip().lower()
            if response == "y":
                _apply_refactoring(refactoring_changes, args.backup, report)
            else:
                print("Refactoring cancelled.")
        else:
            print("No auto-refactorable smells found.")

    generator = ReportGenerator(report)
    if args.format == "json":
        output = generator.generate_json(smells, refactoring_changes)
    else:
        output = generator.generate_text(smells, refactoring_changes)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to {args.output}")
    else:
        print(output)


def _show_preview(refactoring_changes):
    print("\n" + "=" * 70)
    print("  REFACTORING PREVIEW")
    print("=" * 70)

    if not refactoring_changes:
        print("\nNo refactoring changes to preview.")
        return

    for file_path, changes in refactoring_changes.items():
        with open(file_path, "r", encoding="utf-8") as f:
            original_content = f.read()
        proposal = RefactoringProposal(
            file_path=file_path,
            original_content=original_content,
            changes=[c for c, _ in changes],
        )
        print(f"\n{'=' * 70}")
        print(f"  File: {file_path}")
        for change, smell in changes:
            print(f"  Action: {change.description}")
            print(f"  Smell:  {smell.smell_type.value} ({smell.message})")
        print(f"{'=' * 70}")
        print(proposal.get_diff())

    print("\n" + "=" * 70)


def _apply_refactoring(refactoring_changes, backup, report):
    for file_path, changes in refactoring_changes.items():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                original_content = f.read()

            if backup:
                backup_path = file_path + ".bak"
                with open(backup_path, "w", encoding="utf-8") as f:
                    f.write(original_content)
                print(f"Backup saved to {backup_path}")

            proposal = RefactoringProposal(
                file_path=file_path,
                original_content=original_content,
                changes=[c for c, _ in changes],
            )

            new_content = proposal.get_full_new_content()
            diff_text = proposal.get_diff()

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            for change, smell in changes:
                report.add_refactoring(file_path, change, smell, diff_text)

            print(f"Refactored: {file_path}")

        except (IOError, OSError) as e:
            report.errors.append(f"Failed to refactor {file_path}: {e}")
            print(f"Error refactoring {file_path}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()