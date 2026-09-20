from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code: int = 500
    detail: str = "Internal server error"
    code: str = "INTERNAL_ERROR"
    field: str | None = None

    def __init__(self, detail: str | None = None, code: str | None = None, field: str | None = None, **kwargs):
        if detail is not None:
            self.detail = detail
        if code is not None:
            self.code = code
        if field is not None:
            self.field = field
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


class CommunityError(AppError):
    """Error rendered in the Community module's own JSON contract shape.

    Response body: ``{"error": <CODE>, "message": <detail>, ...}`` with
    optional ``field`` and custom extras (e.g. ``retryAfterSeconds``).
    """

    status_code = 400
    detail = "Community request failed"
    code = "COMMUNITY_ERROR"
    field: str | None = None
    extras: dict | None = None

    def __init__(
        self,
        status_code: int | None = None,
        code: str | None = None,
        detail: str | None = None,
        field: str | None = None,
        extras: dict | None = None,
    ):
        super().__init__(detail if detail is not None else self.detail, code)
        if status_code is not None:
            self.status_code = status_code
        if field is not None:
            self.field = field
        self.extras = extras or {}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(CommunityError)
    async def handle_community_error(request: Request, exc: CommunityError) -> JSONResponse:
        body: dict = {
            "error": exc.code,
            "message": exc.detail,
        }
        if exc.field is not None:
            body["field"] = exc.field
        body.update(exc.extras)
        return JSONResponse(
            status_code=exc.status_code,
            content=body,
        )
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