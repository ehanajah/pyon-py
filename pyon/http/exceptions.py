class HTTPError(Exception):
    pass

class HTTPStatusError(HTTPError):
    def __init__(self, message: str, status_code: int, url: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        