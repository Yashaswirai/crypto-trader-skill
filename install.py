#!/usr/bin/env python3
"""
Installer for the Crypto Trader Skill Suite.
Installs all 11 skills into Claude Code, Claude Desktop, or an agent skills directory.

Usage:
    python3 install.py                  # Installs globally to ~/.claude/skills/
    python3 install.py --local          # Installs locally to ./.claude/skills/
    python3 install.py --agents         # Installs locally to ./.agents/skills/
    python3 install.py --target /path   # Installs to custom directory
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

SKILLS = [
    "crypto-scanner",
    "crypto-news",
    "crypto-entry",
    "crypto-exit",
    "crypto-timemachine",
    "crypto-budget",
    "crypto-risk",
    "crypto-broker",
    "crypto-alerts",
    "crypto-analyst",
    "crypto-whale",
]


def resolve_source_dir() -> Path:
    return Path(__file__).resolve().parent


def copy_skill(source_dir: Path, target_base: Path, skill_name: str) -> None:
    src = source_dir / skill_name
    dest = target_base / skill_name

    if not src.exists():
        raise FileNotFoundError(f"Source skill folder not found: {src}")

    if dest.exists():
        shutil.rmtree(dest)

    shutil.copytree(
        src,
        dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
    )


def install_skills(target_dir: Path) -> int:
    source_dir = resolve_source_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"Installing 11 Crypto Trader skills into: {target_dir}")

    installed_count = 0
    for skill in SKILLS:
        copy_skill(source_dir, target_dir, skill)
        print(f"  + {skill}")
        installed_count += 1

    print(f"\nSuccessfully installed {installed_count}/{len(SKILLS)} skills.")
    print("Skills are ready to use via Claude, Claude Code, or compatible AI agents.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install the 11 Crypto Trader skills."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--global",
        dest="is_global",
        action="store_true",
        help="Install globally to ~/.claude/skills/ (default)",
    )
    group.add_argument(
        "--local",
        action="store_true",
        help="Install locally to .claude/skills/ in the current directory",
    )
    group.add_argument(
        "--agents",
        action="store_true",
        help="Install locally to .agents/skills/ in the current directory",
    )
    group.add_argument(
        "--target",
        type=str,
        help="Install to a specific custom target directory",
    )

    args = parser.parse_args()

    if args.target:
        target_path = Path(args.target).resolve()
    elif args.local:
        target_path = Path.cwd() / ".claude" / "skills"
    elif args.agents:
        target_path = Path.cwd() / ".agents" / "skills"
    else:
        # Default: user home .claude/skills
        target_path = Path.home() / ".claude" / "skills"

    return install_skills(target_path)


if __name__ == "__main__":
    sys.exit(main())
