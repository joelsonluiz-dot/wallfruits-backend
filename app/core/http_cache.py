from fastapi import Response

from app.core.config import settings


def detail_cache_control(private: bool) -> str:
    if private:
        return "private, max-age=0, must-revalidate"

    return (
        f"public, max-age={settings.HTTP_PUBLIC_CACHE_MAX_AGE_SECONDS}, "
        f"stale-while-revalidate={settings.HTTP_PUBLIC_CACHE_STALE_WHILE_REVALIDATE_SECONDS}"
    )


def set_detail_cache_headers(response: Response, *, private: bool) -> None:
    response.headers["Cache-Control"] = detail_cache_control(private)
    response.headers["Vary"] = "Accept-Encoding, Authorization, Cookie"
