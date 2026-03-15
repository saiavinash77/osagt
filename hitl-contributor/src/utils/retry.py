"""
Retry utilities with exponential backoff.
Use the @retry decorator on any function that calls external APIs.
"""

import logging
import time
import functools
from typing import Callable, Tuple, Type, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable)


def retry(
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    max_attempts: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    reraise: bool = True,
) -> Callable[[F], F]:
    """
    Decorator factory for retrying a function on specified exceptions.

    Args:
        exceptions:     Exception types to catch and retry on.
        max_attempts:   Total attempts (including first try).
        base_delay:     Seconds to wait before first retry.
        max_delay:      Maximum wait between retries.
        backoff_factor: Multiplier applied to delay each retry.
        reraise:        If True, raise the last exception after exhausting retries.

    Example:
        @retry(exceptions=(requests.Timeout, RateLimitError), max_attempts=4)
        def call_api():
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            last_exc: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {exc}"
                        )
                        break
                    wait = min(delay, max_delay)
                    logger.warning(
                        f"{func.__name__} attempt {attempt}/{max_attempts} failed "
                        f"({type(exc).__name__}: {exc}). Retrying in {wait:.1f}s…"
                    )
                    time.sleep(wait)
                    delay *= backoff_factor

            if reraise and last_exc:
                raise last_exc
            return None

        return wrapper  # type: ignore
    return decorator


def retry_on_rate_limit(func: F) -> F:
    """Shorthand decorator tuned for GitHub / OpenRouter rate limits."""
    from github import GithubException
    import openai

    return retry(
        exceptions=(GithubException, openai.RateLimitError, ConnectionError),
        max_attempts=4,
        base_delay=5.0,
        max_delay=60.0,
    )(func)
