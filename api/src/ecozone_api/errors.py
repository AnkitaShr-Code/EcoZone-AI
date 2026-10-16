"""One error shape for every route: contract `ErrorBody` (ENGINEERING_RULES.md §6, api/RULES.md)."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ecozone_contract import ErrorBody, ErrorCode, ErrorDetail
from ecozone_engine import (
    EngineInputError,
    InvalidChangeError,
    NotImplementedYetError,
    QuantityOutOfRangeError,
    UnknownParcelError,
    UnknownSiteError,
)

log = logging.getLogger(__name__)


class ApiError(Exception):
    """An expected failure with a contract error code; the message is shown to the planner."""

    def __init__(self, code: ErrorCode, message: str, status: int) -> None:
        super().__init__(message)
        self.code: ErrorCode = code
        self.message = message
        self.status = status


_ENGINE_CODES: list[tuple[type[EngineInputError], ErrorCode, int]] = [
    (UnknownSiteError, "SITE_NOT_FOUND", 404),
    (UnknownParcelError, "PARCEL_NOT_FOUND", 404),
    (QuantityOutOfRangeError, "QUANTITY_OUT_OF_RANGE", 422),
    (InvalidChangeError, "INVALID_CHANGE", 422),
]


def error_response(code: ErrorCode, message: str, status: int) -> JSONResponse:
    body = ErrorBody(error=ErrorDetail(code=code, message=message))
    return JSONResponse(body.model_dump(mode="json"), status_code=status)


def engine_error(error: EngineInputError) -> ApiError:
    for kind, code, status in _ENGINE_CODES:
        if isinstance(error, kind):
            return ApiError(code, str(error), status)
    return ApiError("INVALID_CHANGE", str(error), 422)


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    def _api(_: Request, exc: ApiError) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return error_response(exc.code, exc.message, exc.status)

    @app.exception_handler(EngineInputError)
    def _engine(_: Request, exc: EngineInputError) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        api = engine_error(exc)
        return error_response(api.code, api.message, api.status)

    @app.exception_handler(NotImplementedYetError)
    def _stub(_: Request, exc: NotImplementedYetError) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return error_response("NOT_IMPLEMENTED", str(exc), 501)

    @app.exception_handler(RequestValidationError)
    def _invalid(_: Request, exc: RequestValidationError) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
        message = f"The request is not valid: {where or 'body'}: {first.get('msg', 'invalid value')}."
        return error_response("INVALID_REQUEST", message, 422)

    @app.exception_handler(Exception)
    def _internal(_: Request, exc: Exception) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        log.exception("Unhandled error", exc_info=exc)
        return error_response("INTERNAL", "Something went wrong on the server. Try again; if it repeats, tell us.", 500)
