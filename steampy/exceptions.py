class SevenDaysHoldException(Exception):
    pass


class TooManyRequests(Exception):
    pass


class ApiException(Exception):
    pass


class SteamRequestError(ApiException):
    def __init__(
        self,
        message: str,
        method: str | None = None,
        url: str | None = None,
        status_code: int | None = None,
        body_preview: str | None = None,
    ) -> None:
        super().__init__(message)
        self.method = method
        self.url = url
        self.status_code = status_code
        self.body_preview = body_preview


class SteamResponseError(SteamRequestError):
    def __init__(self, message: str, response, method: str | None = None) -> None:
        body_preview = response.text[:500].replace('\n', ' ') if response.text else ''
        request = getattr(response, 'request', None)
        response_method = getattr(request, 'method', None)
        super().__init__(message, method or response_method, response.url, response.status_code, body_preview)


class LoginRequired(Exception):
    pass


class InvalidCredentials(Exception):
    pass


class CaptchaRequired(Exception):
    pass


class ConfirmationExpected(Exception):
    pass


class ProxyConnectionError(Exception):
    pass
