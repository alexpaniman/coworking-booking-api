from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return naive UTC datetimes for the existing database columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
