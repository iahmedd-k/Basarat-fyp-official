from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code: int = 500
    detail: str = "Internal server error"
    code: str = "INTERNAL_ERROR"

    def __init__(self, detail: str | None = None, code: str | None = None):
        if detail is not None:
            self.detail = detail
        if code is not None:
            self.code = code
        super().__init__(self.detail)


class BadRequestError(AppError):
    status_code = 400
    detail = "Bad request"
    code = "BAD_REQUEST"


class UnauthorizedError(AppError):
    status_code = 401
    detail = "Not authenticated"
    code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    status_code = 403
    detail = "Not enough permissions"
    code = "FORBIDDEN"


class NotFoundError(AppError):
    status_code = 404
    detail = "Resource not found"
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    detail = "Resource already exists"
    code = "CONFLICT"


class ValidationFailedError(AppError):
    status_code = 422
    detail = "Validation failed"
    code = "VALIDATION_FAILED"


class ServiceUnavailableError(AppError):
    status_code = 503
    detail = "Service unavailable"
    code = "SERVICE_UNAVAILABLE"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.code,
                    "message": exc.detail,
                },
            },
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                },
            },
        )