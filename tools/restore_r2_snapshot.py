#!/usr/bin/env python3
"""Restore and verify a licensed snapshot from configured object storage."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import sys

import boto3


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_KEY = "SHA256SUMS"
ARCHIVAL_RECOVERY_FLAG = "R2_ARCHIVAL_RECOVERY"


def client():
    key = os.environ.get("R2_ACCESS_KEY_ID")
    secret = os.environ.get("R2_SECRET_ACCESS_KEY")
    if not key or not secret:
        raise RuntimeError(
            "Set R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY to valid read-only "
            "credentials supplied outside this repository."
        )
    endpoint = os.environ.get("R2_ENDPOINT")
    if not endpoint:
        raise RuntimeError(
            "Remote recovery configuration is incomplete. R2_ENDPOINT must be "
            "supplied externally."
        )
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        region_name="auto",
    )


def parse_manifest(body: bytes) -> list[tuple[str, Path]]:
    entries = []
    for line in body.decode("utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        if not relative.startswith("Analysis/Data/"):
            raise ValueError(f"Unexpected manifest path: {relative}")
        target = (ROOT / relative).resolve()
        if ROOT not in target.parents:
            raise ValueError(f"Unsafe manifest path: {relative}")
        entries.append((digest, target))
    return entries


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Restore and SHA-256 verify a licensed data snapshot."
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Do not download; verify the existing Analysis/Data tree.",
    )
    args = parser.parse_args()

    if os.environ.get(ARCHIVAL_RECOVERY_FLAG) != "1":
        raise RuntimeError(
            "Remote recovery is disabled. Set R2_ARCHIVAL_RECOVERY=1 only when "
            "you are authorized to access the configured storage."
        )

    bucket = os.environ.get("R2_BUCKET")
    prefix = os.environ.get("R2_DATA_PREFIX", "Analysis/Data").strip("/")
    if not bucket:
        raise RuntimeError(
            "Remote recovery configuration is incomplete. R2_BUCKET must be "
            "supplied externally."
        )
    s3 = client()
    manifest = s3.get_object(Bucket=bucket, Key=MANIFEST_KEY)["Body"].read()
    entries = parse_manifest(manifest)

    failures = []
    for index, (expected, target) in enumerate(entries, start=1):
        relative = target.relative_to(ROOT).as_posix()
        key = f"{prefix}/{target.relative_to(ROOT / 'Analysis' / 'Data').as_posix()}"
        if not target.is_file() and not args.verify_only:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".partial")
            s3.download_file(bucket, key, str(temporary))
            temporary.replace(target)
        if not target.is_file():
            failures.append(f"MISSING {relative}")
        elif sha256(target) != expected:
            failures.append(f"MISMATCH {relative}")
        print(f"[{index}/{len(entries)}] {relative}")

    if failures:
        print("\nSnapshot verification failed:", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"\nVerified {len(entries)} snapshot files against SHA256SUMS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
