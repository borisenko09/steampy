from __future__ import annotations

import logging
import time

import requests

from steampy.exceptions import SteamRequestError, SteamResponseError


logger = logging.getLogger(__name__)


class SteamSession(requests.Session):
    """Requests session with bounded retries for safe Steam API reads."""

    RETRYABLE_METHODS = {'GET', 'HEAD', 'OPTIONS'}
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(self, timeout: float = 30, max_retries: int = 3) -> None:
        super().__init__()
        self.timeout = timeout
        self.max_retries = max_retries

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        method = method.upper()
        timeout = kwargs.pop('timeout', self.timeout)
        retryable = method in self.RETRYABLE_METHODS
        attempts = self.max_retries if retryable else 1
        last_error = None

        for attempt in range(attempts):
            try:
                response = super().request(method, url, timeout=timeout, **kwargs)
            except requests.RequestException as error:
                last_error = error
                if not retryable or attempt == attempts - 1:
                    raise SteamRequestError(
                        f'Steam request failed: {error}', method=method, url=url,
                    ) from error
            else:
                if response.status_code not in self.RETRYABLE_STATUS_CODES or attempt == attempts - 1:
                    if response.status_code >= 500:
                        raise SteamResponseError('Steam returned a server error.', response, method)
                    return response
                last_error = response

            delay = self._retry_delay(last_error, attempt)
            logger.warning('Retrying Steam %s request to %s in %.1fs.', method, url, delay)
            time.sleep(delay)

        raise SteamRequestError('Steam request failed after retries.', method=method, url=url)

    @staticmethod
    def _retry_delay(response_or_error, attempt: int) -> float:
        retry_after = getattr(response_or_error, 'headers', {}).get('Retry-After')
        if retry_after and retry_after.isdigit():
            return min(float(retry_after), 60)
        return min(2**attempt, 30)
