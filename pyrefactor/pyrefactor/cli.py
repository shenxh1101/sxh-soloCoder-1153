import argparse
import os
import sys
from typing import List, Optional

from .analyzer import Analyzer
from .models import SmellResult, RefactoringChange, RefactoringProposal, RefactorReport, SmellType
from .report import ReportGenerator, filter_smells
from .config import find_config_file, generate_init_config


def main():
    parser = argparse.ArgumentParser(
        description="PyRefactor - Python code smell detection and automated refactoring tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pyrefactor init
  pyrefactor check myfile.py
  pyrefactor check ./src/
  pyrefactor check ./src/ --severity warning --auto-refactorable-only
  pyrefactor check ./src/ --config .pyrefactor.yaml
  pyrefactor refactor ./src/ --auto --backup
  pyrefactor refactor ./src/ --preview
  pyrefactor refactor ./src/ --patch-only --patch-output changes.patch
        """,
    )

    parser.add_argument(
        "--version", action="version", version="pyrefactor 0.1.0"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    init_parser = subparsers.add_parser("init", help="Generate a default configuration file")
    init_parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to create the config file in (default: current directory)",
    )

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
    check_parser.add_argument(
        "--severity", "-s",
        choices=["error", "warning", "info"],
        default=None,
        help="Minimum severity level to report (error > warning > info)",
    )
    check_parser.add_argument(
        "--auto-refactorable-only", action="store_true",
        help="Only report smells that can be automatically refactored",
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
    refactor_parser.add_argument(
        "--severity", "-s",
        choices=["error", "warning", "info"],
        default=None,
        help="Minimum severity level to report (error > warning > info)",
    )
    refactor_parser.add_argument(
        "--auto-refactorable-only", action="store_true",
        help="Only report smells that can be automatically refactored",
    )
    refactor_parser.add_argument(
        "--patch-only", action="store_true",
        help="Generate patch file only, do not modify source files",
    )
    refactor_parser.add_argument(
        "--patch-output", default=None,
        help="Path to save the patch file (default: pyrefactor.patch)",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "init":
        run_init(args)
    elif args.command == "check":
        run_check(args)
    elif args.command == "refactor":
        run_refactor(args)


def run_init(args):
    target = args.directory
    try:
        config_path = generate_init_config(target)
        print(f"Configuration file created: {config_path}")
        print(f"")
        print(f"You can now run 'pyrefactor check' or 'pyrefactor refactor'")
        print(f"and it will automatically use this configuration file.")
    except (IOError, OSError) as e:
        print(f"Error: Failed to create config file: {e}", file=sys.stderr)
        sys.exit(1)


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

    smells = filter_smells(
        smells,
        min_severity=args.severity,
        auto_refactorable_only=args.auto_refactorable_only,
    )

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

    smells_before_filter = smells
    smells = filter_smells(
        smells,
        min_severity=args.severity,
        auto_refactorable_only=args.auto_refactorable_only,
    )

    report = RefactorReport()
    files_set = set()
    for smell in smells:
        report.add_smell(smell)
        files_set.add(smell.location.file_path)
    report.files_processed = len(files_set) if os.path.isdir(path) else 1
    report.files_with_smells = len(files_set)

    refactoring_changes = {}
    skipped_unsafe = 0

    auto_refactorable = [s for s in smells if s.can_auto_refactor]
    for smell in auto_refactorable:
        if not smell.is_safe_to_refactor:
            skipped_unsafe += 1
            continue
        change = analyzer.create_refactoring(smell, smell.location.file_path)
        if change:
            file_path = smell.location.file_path
            if file_path not in refactoring_changes:
                refactoring_changes[file_path] = []
            refactoring_changes[file_path].append((change, smell))

    report.skipped_unsafe = skipped_unsafe

    if args.patch_only:
        patch_output = args.patch_output or "pyrefactor.patch"
        generator = ReportGenerator(report)
        patch_text = generator.generate_patch(refactoring_changes)
        with open(patch_output, "w", encoding="utf-8") as f:
            f.write(patch_text)
        print(f"Patch file saved to {patch_output}")
        print(f"No source files were modified.")
    elif args.preview:
        _show_preview(refactoring_changes, skipped_unsafe)
    elif args.auto:
        _apply_refactoring(refactoring_changes, args.backup, report, args.patch_output)
    else:
        if refactoring_changes:
            _show_preview(refactoring_changes, skipped_unsafe)
            response = input("\nApply these changes? [y/N]: ").strip().lower()
            if response == "y":
                _apply_refactoring(refactoring_changes, args.backup, report, args.patch_output)
            else:
                print("Refactoring cancelled.")
        else:
            if skipped_unsafe > 0:
                print(f"No auto-refactorable smells found ({skipped_unsafe} unsafe refactorings were skipped).")
            else:
                print("No auto-refactorable smells found.")

    if not args.patch_only:
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


def _show_preview(refactoring_changes, skipped_unsafe=0):
    print("\n" + "=" * 70)
    print("  REFACTORING PREVIEW")
    print("=" * 70)

    if skipped_unsafe > 0:
        print(f"\n  [{skipped_unsafe} unsafe refactoring(s) were automatically skipped.]")

    if not refactoring_changes:
        print("\nNo safe refactoring changes to preview.")
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
            if not change.is_safe:
                print(f"  *** UNSAFE — will be skipped in auto mode ***")
                for w in change.safety_warnings:
                    print(f"  ! {w}")
        print(f"{'=' * 70}")
        print(proposal.get_diff())

    print("\n" + "=" * 70)


def _apply_refactoring(refactoring_changes, backup, report, patch_output=None):
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

    if patch_output and refactoring_changes:
        generator = ReportGenerator(report)
        patch_text = generator.generate_patch(refactoring_changes)
        with open(patch_output, "w", encoding="utf-8") as f:
            f.write(patch_text)
        print(f"Patch file saved to {patch_output}")


if __name__ == "__main__":
    main()