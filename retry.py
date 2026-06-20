"""
retry.py  —  Decorator ذكي لإعادة المحاولة مع Exponential Backoff
=================================================================
يوفر decorator عام قابل للتهيئة لإعادة محاولة الدوال
عند حدوث أخطاء محددة، مع تسجيل كل محاولة.

الاستخدام:
    from retry import retry

    @retry(max_attempts=3, base_delay=5.0, exceptions=(ConnectionError,))
    def fetch_data():
        ...
"""

from __future__ import annotations

import time
import functools
from typing import Type, Callable, Any

from logger import get_logger

_log = get_logger("retry")


def retry(
    max_attempts: int = 3,
    base_delay: float = 5.0,
    multiplier: float = 2.0,
    max_delay: float = 60.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> Callable:
    """
    Decorator لإعادة محاولة دالة مع exponential backoff.

    Args:
        max_attempts: أقصى عدد محاولات.
        base_delay:   فترة الانتظار الأولية (ثانية).
        multiplier:   مُضاعِف فترة الانتظار بين المحاولات.
        max_delay:    الحد الأقصى لفترة الانتظار (ثانية).
        exceptions:   أنواع الاستثناءات التي تُعاد المحاولة عندها.
        on_retry:     callback اختياري يُستدعى قبل كل إعادة محاولة.
                      يستقبل (رقم_المحاولة, الاستثناء, فترة_الانتظار).

    Returns:
        الدالة المُغلَّفة بمنطق إعادة المحاولة.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc

                    if attempt == max_attempts:
                        _log.error(
                            "[%s] فشل بعد %d محاولات: %s",
                            func.__name__, max_attempts, exc,
                        )
                        raise

                    delay = min(
                        base_delay * (multiplier ** (attempt - 1)),
                        max_delay,
                    )
                    _log.warning(
                        "[%s] المحاولة %d/%d فشلت: %s — إعادة خلال %.1f ثانية",
                        func.__name__, attempt, max_attempts, exc, delay,
                    )

                    if on_retry:
                        on_retry(attempt, exc, delay)

                    time.sleep(delay)

            # لا يُصل إلى هنا لكن يُرضي مدقق الأنواع
            raise last_exception  # type: ignore[misc]

        return wrapper
    return decorator
