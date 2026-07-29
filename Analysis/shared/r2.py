"""Resolve licensed data locally or from explicitly configured object storage.

Usage:
    from shared.r2 import ensure_data_file
    path = ensure_data_file("processed/revB4AudStata.feather")
"""
import os

_ARCHIVAL_RECOVERY_FLAG = "R2_ARCHIVAL_RECOVERY"
_R2_ENDPOINT = os.environ.get("R2_ENDPOINT")
_R2_BUCKET = os.environ.get("R2_BUCKET")
_R2_DATA_PREFIX = os.environ.get(
    "R2_DATA_PREFIX", "Analysis/Data"
).strip("/")


def _get_r2_credentials():
    """Return externally supplied object-storage credentials."""
    if os.environ.get(_ARCHIVAL_RECOVERY_FLAG) != "1":
        raise RuntimeError(
            "Required data are missing. Place independently licensed files "
            "under Analysis/Data/ or explicitly configure remote recovery."
        )
    key = os.environ.get("R2_ACCESS_KEY_ID")
    secret = os.environ.get("R2_SECRET_ACCESS_KEY")
    if key and secret:
        return key, secret

    try:
        from google.colab import userdata
        key = userdata.get("R2_ACCESS_KEY_ID")
        secret = userdata.get("R2_SECRET_ACCESS_KEY")
        if key and secret:
            return key, secret
    except (ImportError, Exception):
        pass

    raise RuntimeError(
        "Remote recovery credentials are not configured. Place independently "
        "licensed input files under Analysis/Data/."
    )


def _get_s3_client():
    """Create a cached S3-compatible object-storage client."""
    global _s3_client
    try:
        return _s3_client
    except NameError:
        pass
    import boto3
    access_key, secret_key = _get_r2_credentials()
    if not _R2_ENDPOINT or not _R2_BUCKET:
        raise RuntimeError(
            "Remote recovery configuration is incomplete. R2_ENDPOINT and "
            "R2_BUCKET must be supplied externally."
        )
    _s3_client = boto3.client(
        "s3",
        endpoint_url=_R2_ENDPOINT,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
    )
    return _s3_client


def ensure_data_file(subpath):
    """Return a local data-file path.

    Independently licensed data should be placed under Analysis/Data/. Remote
    recovery is attempted only after explicit external configuration.

    Args:
        subpath: Path relative to Analysis/Data/, e.g.
                 "processed/revB4AudStata.feather" or
                 "raw/audit_analytics/audit_audit_comp_feed34_revised_audit_opinions.csv"

    Returns:
        Absolute local file path.
    """
    from shared.paths import data_dir

    local_path = os.path.join(data_dir, subpath)
    if os.path.exists(local_path):
        return local_path

    r2_key = f"{_R2_DATA_PREFIX}/{subpath}"
    size_mb = _download(r2_key, local_path)
    print(f"  Recovered {subpath} ({size_mb:.1f} MB) from object storage")
    return local_path


def _download(r2_key, local_path):
    """Download one configured object and return its size in MB."""
    s3 = _get_s3_client()

    # Get size for progress reporting
    head = s3.head_object(Bucket=_R2_BUCKET, Key=r2_key)
    size_mb = head["ContentLength"] / (1024 * 1024)

    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    print(f"  Downloading {r2_key} ({size_mb:.1f} MB)...")
    s3.download_file(_R2_BUCKET, r2_key, local_path)
    return size_mb
