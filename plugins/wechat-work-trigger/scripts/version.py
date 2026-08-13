#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = ROOT / "pyproject.toml"
MANIFEST_PATH = ROOT / "manifest.yaml"
SEMVER_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SUPPORTED_MANIFEST_VERSIONS = {"0.0.1", "0.0.2"}


def parse_version(value: str) -> tuple[int, int, int]:
    match = SEMVER_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError(f"invalid version {value!r}; expected MAJOR.MINOR.PATCH")
    return tuple(int(part) for part in match.groups())


def read_versions() -> tuple[dict[str, str], str]:
    with PYPROJECT_PATH.open("rb") as file:
        project_version = tomllib.load(file)["project"]["version"]

    manifest = MANIFEST_PATH.read_text(encoding="utf-8")
    top_level_match = re.search(r"(?m)^version:\s*([^\s#]+)\s*$", manifest)
    meta_match = re.search(
        r"(?m)^meta:\s*$\n(?:(?:^[ \t]+.*\n)*?)?^[ \t]+version:\s*([^\s#]+)\s*$",
        manifest,
    )
    if top_level_match is None or meta_match is None:
        raise ValueError("manifest.yaml must contain top-level and meta versions")

    return (
        {
            "pyproject.toml": project_version,
            "manifest.yaml": top_level_match.group(1),
        },
        meta_match.group(1),
    )


def check_versions() -> str:
    versions, manifest_version = read_versions()
    for value in versions.values():
        parse_version(value)
    if manifest_version not in SUPPORTED_MANIFEST_VERSIONS:
        raise ValueError(f"unsupported manifest schema version {manifest_version!r}")
    if len(set(versions.values())) != 1:
        details = ", ".join(f"{source}={version}" for source, version in versions.items())
        raise ValueError(f"version mismatch: {details}")
    return next(iter(versions.values()))


def set_version(version: str) -> None:
    requested = parse_version(version)
    current = check_versions()
    if requested <= parse_version(current):
        raise ValueError(f"new version {version} must be greater than current version {current}")

    pyproject = PYPROJECT_PATH.read_text(encoding="utf-8")
    pyproject, replacements = re.subn(
        r'(?m)^(version\s*=\s*)"[^"\n]+"\s*$',
        rf'\g<1>"{version}"',
        pyproject,
        count=1,
    )
    if replacements != 1:
        raise ValueError("could not update project.version in pyproject.toml")

    manifest = MANIFEST_PATH.read_text(encoding="utf-8")
    manifest, top_level_replacements = re.subn(
        r"(?m)^version:\s*[^\s#]+\s*$",
        f"version: {version}",
        manifest,
        count=1,
    )
    if top_level_replacements != 1:
        raise ValueError("could not update version in manifest.yaml")

    PYPROJECT_PATH.write_text(pyproject, encoding="utf-8")
    MANIFEST_PATH.write_text(manifest, encoding="utf-8")
    if check_versions() != version:
        raise ValueError("version update did not pass consistency validation")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check or update plugin versions.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="Check that all plugin versions match.")
    set_parser = subparsers.add_parser("set", help="Set a new plugin version.")
    set_parser.add_argument("version", help="New version in MAJOR.MINOR.PATCH format.")
    args = parser.parse_args()

    try:
        if args.command == "set":
            set_version(args.version)
        version = check_versions()
    except (KeyError, OSError, TypeError, ValueError, tomllib.TOMLDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
