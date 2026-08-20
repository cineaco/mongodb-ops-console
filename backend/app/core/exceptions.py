from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    detail = str(exc.orig) if exc.orig else "Integrity constraint violated"
    return JSONResponse(
        status_code=409,
        content={"type": "https://httpstatuses.io/409", "title": "Conflict", "status": 409, "detail": detail},
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"type": "https://httpstatuses.io/500", "title": "Internal Server Error", "status": 500, "detail": "An unexpected error occurred."},
    )
