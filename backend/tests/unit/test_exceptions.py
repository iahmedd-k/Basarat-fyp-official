"""Unit tests for custom exceptions."""

import pytest

from app.core.exceptions import (
    AppError,
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
    ValidationFailedError,
)


class TestAppError:
    def test_default_message(self):
        err = AppError()
        assert str(err) == "Internal server error"
        assert err.status_code == 500

    def test_custom_message(self):
        err = AppError("custom error")
        assert str(err) == "custom error"

    def test_is_exception(self):
        assert issubclass(AppError, Exception)


class TestSpecificErrors:
    @pytest.mark.parametrize(
        "error_class,status_code,default_detail",
        [
            (BadRequestError, 400, "Bad request"),
            (UnauthorizedError, 401, "Not authenticated"),
            (ForbiddenError, 403, "Not enough permissions"),
            (NotFoundError, 404, "Resource not found"),
            (ConflictError, 409, "Resource already exists"),
            (ValidationFailedError, 422, "Validation failed"),
            (ServiceUnavailableError, 503, "Service unavailable"),
        ],
    )
    def test_error_status_code(self, error_class, status_code, default_detail):
        err = error_class()
        assert err.status_code == status_code
        assert str(err) == default_detail

    def test_custom_detail_override(self):
        err = NotFoundError("Stock not found")
        assert str(err) == "Stock not found"
        assert err.status_code == 404

    def test_all_inherit_from_app_error(self):
        for cls in [
            BadRequestError, UnauthorizedError, ForbiddenError,
            NotFoundError, ConflictError, ValidationFailedError,
            ServiceUnavailableError,
        ]:
            assert issubclass(cls, AppError)
