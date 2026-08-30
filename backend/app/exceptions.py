from typing import Any


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: Any | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


class ChatError(AppError):
    def __init__(self, message: str, details: Any | None = None) -> None:
        super().__init__(status_code=400, code="CHAT_ERROR", message=message, details=details)


class ExternalServiceError(AppError):
    def __init__(self, service: str, message: str, details: Any | None = None) -> None:
        super().__init__(status_code=503, code="EXTERNAL_SERVICE_ERROR", message=message, details=details)
