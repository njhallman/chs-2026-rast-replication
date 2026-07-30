#!/usr/bin/env python3
"""Verify the canonical software environment for the exact replication."""

from __future__ import annotations

import argparse
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "environment.lock.json"
PIN_RE = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s;]+)$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def exact_python_requirements(path: Path) -> dict[str, tuple[str, str]]:
    requirements: dict[str, tuple[str, str]] = {}
    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = PIN_RE.fullmatch(line)
        if not match:
            raise ValueError(
                f"{path}:{line_number} is not an exact name==version pin: {line}"
            )
        name, version = match.groups()
        requirements[normalized_name(name)] = (name, version)
    return requirements


def sw_vers(field: str) -> str:
    return subprocess.check_output(
        ["sw_vers", f"-{field}"], text=True
    ).strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify Python, system, Stata, and add-on package locks."
    )
    parser.add_argument(
        "--python-only",
        action="store_true",
        help="Verify Python and its packages without requiring the canonical OS or Stata.",
    )
    args = parser.parse_args()

    lock = json.loads(LOCK_PATH.read_text())
    failures: list[str] = []

    python_lock = lock["python"]
    actual_python = platform.python_version()
    if actual_python != python_lock["version"]:
        failures.append(
            f"Python version: expected {python_lock['version']}, found {actual_python}"
        )
    if platform.python_implementation() != python_lock["implementation"]:
        failures.append(
            "Python implementation: expected "
            f"{python_lock['implementation']}, found {platform.python_implementation()}"
        )

    requirements_path = ROOT / python_lock["requirements_file"]
    hash_lock_path = ROOT / python_lock["hash_lock_file"]
    for path, expected in (
        (requirements_path, python_lock["requirements_sha256"]),
        (hash_lock_path, python_lock["hash_lock_sha256"]),
    ):
        if not path.is_file():
            failures.append(f"Missing lock input: {path.relative_to(ROOT)}")
        elif sha256(path) != expected:
            failures.append(f"Lock checksum mismatch: {path.relative_to(ROOT)}")

    requirements = exact_python_requirements(requirements_path)
    installed = {
        normalized_name(distribution.metadata["Name"]): distribution.version
        for distribution in metadata.distributions()
        if distribution.metadata["Name"]
    }
    for normalized, (display_name, expected_version) in requirements.items():
        actual_version = installed.get(normalized)
        if actual_version is None:
            failures.append(f"Missing Python package: {display_name}=={expected_version}")
        elif actual_version != expected_version:
            failures.append(
                f"Python package {display_name}: expected {expected_version}, "
                f"found {actual_version}"
            )

    actual_pip = installed.get("pip")
    if actual_pip != python_lock["pip_version"]:
        failures.append(
            f"pip version: expected {python_lock['pip_version']}, found {actual_pip}"
        )

    allowed = set(requirements) | {"pip"}
    unexpected = sorted(set(installed) - allowed)
    if unexpected:
        failures.append(
            "Unexpected Python packages in environment: " + ", ".join(unexpected)
        )

    if not args.python_only:
        system_lock = lock["system"]
        if platform.system() != "Darwin":
            failures.append(f"OS: expected macOS, found {platform.system()}")
        else:
            actual_version = sw_vers("productVersion")
            actual_build = sw_vers("buildVersion")
            if actual_version != system_lock["version"]:
                failures.append(
                    f"macOS version: expected {system_lock['version']}, "
                    f"found {actual_version}"
                )
            if actual_build != system_lock["build"]:
                failures.append(
                    f"macOS build: expected {system_lock['build']}, found {actual_build}"
                )
        if platform.machine() != system_lock["machine"]:
            failures.append(
                f"machine: expected {system_lock['machine']}, found {platform.machine()}"
            )

        stata_lock = lock["stata"]
        for label in ("binary", "library"):
            artifact = stata_lock[label]
            path = Path(artifact["path"])
            if not path.is_file():
                failures.append(f"Missing Stata {label}: {path}")
            elif sha256(path) != artifact["sha256"]:
                failures.append(f"Stata {label} checksum mismatch: {path}")

        ado_root = Path(stata_lock["ado_root"]).expanduser()
        for package in stata_lock["packages"]:
            path = ado_root / package["file"]
            if not path.is_file():
                failures.append(
                    f"Missing Stata package {package['name']}=={package['version']}: {path}"
                )
            elif sha256(path) != package["sha256"]:
                failures.append(
                    f"Stata package checksum mismatch: "
                    f"{package['name']}=={package['version']}"
                )

    if failures:
        print("Environment verification FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    scope = "Python" if args.python_only else "canonical Python, macOS, and Stata"
    print(f"Environment verification passed ({scope}).")
    print(
        f"Python {python_lock['version']}; "
        f"{len(requirements)} hash-locked packages."
    )
    if not args.python_only:
        stata_lock = lock["stata"]
        print(
            f"{stata_lock['product']} {stata_lock['version']} "
            f"(revision {stata_lock['revision']}); "
            f"{len(stata_lock['packages'])} checksummed add-ons."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
