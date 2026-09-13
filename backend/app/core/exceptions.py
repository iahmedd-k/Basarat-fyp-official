from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code: int = 500
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None):
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class BadRequestError(AppError):
    status_code = 400
    detail = "Bad request"


class UnauthorizedError(AppError):
    status_code = 401
    detail = "Not authenticated"


class ForbiddenError(AppError):
    status_code = 403
    detail = "Not enough permissions"


class NotFoundError(AppError):
    status_code = 404
    detail = "Resource not found"


class ConflictError(AppError):
    status_code = 409
    detail = "Resource already exists"


class ValidationFailedError(AppError):
    status_code = 422
    detail = "Validation failed"


class ServiceUnavailableError(AppError):
    status_code = 503
    detail = "Service unavailable"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )