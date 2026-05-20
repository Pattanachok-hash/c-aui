import logging
import time

from supabase import create_client, Client
from config import settings

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

logger = logging.getLogger(__name__)

_TRANSIENT_HINTS = ("ReadError", "WriteError", "ConnectError", "RemoteProtocolError", "Timeout")


def _is_transient(e: Exception) -> bool:
    return any(h in type(e).__name__ for h in _TRANSIENT_HINTS)


def db_execute(query, retries: int = 3, *, idempotent: bool = True):
    """Execute a Supabase query, retrying transient HTTP errors when safe.

    idempotent=False → no retry. Use for INSERT/UPDATE/DELETE where a retry
    on a successful-but-response-lost write would create a duplicate row.
    """
    if not idempotent:
        return query.execute()

    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return query.execute()
        except Exception as e:
            last_exc = e
            if attempt < retries - 1 and _is_transient(e):
                logger.warning(
                    "db_execute retry %d/%d: %s: %s",
                    attempt + 1, retries - 1, type(e).__name__, e,
                )
                time.sleep(0.3 * (attempt + 1))
                continue
            raise
    raise last_exc  # type: ignore[misc]
