"""API error format: {"error": {"code", "message", "hint"}}. Messages never contain absolute paths."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

try:
    from . import config
except ImportError:
    from SYSTEM.core import config


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, hint: str = ""):
        super().__init__(message)
        self.status, self.code, self.message, self.hint = status, code, message, hint


def clean(text: str) -> str:
    """Strip the repository root so no absolute path (of this or any other project) reaches the client."""
    root = str(config.PROJECT_ROOT)
    for variant in (root + "\\", root.replace("\\", "/") + "/", root, root.replace("\\", "/")):
        text = text.replace(variant, "")
    return text


def body(code: str, message: str, hint: str = "") -> dict:
    return {"error": {"code": code, "message": clean(message), "hint": clean(hint)}}


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, e: ApiError):
        return JSONResponse(body(e.code, e.message, e.hint), status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError):
        fields = ", ".join(".".join(str(p) for p in x["loc"] if p != "body") or "body" for x in e.errors()[:5])
        return JSONResponse(body("invalid_request", f"invalid or missing field(s): {fields}",
                                 "see /docs for the request format"), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, e: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(e.status_code, "http_error")
        return JSONResponse(body(code, str(e.detail)), status_code=e.status_code)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, e: Exception):
        return JSONResponse(body("internal_error", "unexpected server error", "see projects/<id>/log.txt"), status_code=500)
