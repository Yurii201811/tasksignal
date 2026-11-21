from secrets import compare_digest


def secret_text_matches(supplied: str | None, configured: str | None) -> bool:
    """Compare text secrets without raising on non-ASCII header values."""
    if not supplied or not configured:
        return False
    return compare_digest(supplied.encode("utf-8"), configured.encode("utf-8"))
