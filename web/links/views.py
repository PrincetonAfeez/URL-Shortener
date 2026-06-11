"""Views for the links app. """

from __future__ import annotations

import json
import secrets
import time
from datetime import datetime, timezone

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from sniplink.api import error_envelope, link_to_dict, status_for_exception
from sniplink.api.validation import (
    parse_api_max_clicks,
    parse_api_metadata,
    parse_api_redirect_status,
)
from sniplink.config import load_config
from sniplink.core import SniplinkService
from sniplink.core.factory import build_sniplink_service
from sniplink.exceptions import AuthError, CodeNotFound, LinkGone, SniplinkError
from sniplink.observability import log_redirect_decision
from sniplink.raw_http.request_parser import path_too_long

from links.storage_adapter import DjangoStorage

_CONFIG = load_config()


def get_service(request: HttpRequest | None = None) -> SniplinkService:
    """Build a SniplinkService from cached Django settings."""

    base_url = getattr(settings, "SNIPLINK_BASE_URL", "http://localhost:8000")
    if request is not None:
        base_url = request.build_absolute_uri("/").rstrip("/")
    return build_sniplink_service(
        DjangoStorage(),
        _CONFIG,
        base_url=base_url,
    )


def redirect_link(request: HttpRequest, code: str) -> HttpResponse:
    if request.method not in {"GET", "HEAD"}:
        return HttpResponseNotAllowed(["GET", "HEAD"])
    reserved = getattr(settings, "SNIPLINK_RESERVED_CODES", ())
    if code.lower() in {p.lower() for p in reserved}:
        return render(request, "links/404.html", {"code": code}, status=404)
    max_path = getattr(settings, "SNIPLINK_MAX_REQUEST_PATH_BYTES", 2048)
    if path_too_long(f"/{code}", max_path_length=max_path):
        return HttpResponse(
            "414 URI Too Long: request target is too long\n",
            status=414,
            content_type="text/plain; charset=utf-8",
        )
    service = get_service(request)
    try:
        started = time.perf_counter()
        decision = service.resolve(
            code,
            record_click=request.method == "GET",
            referrer=request.headers.get("referer"),
            user_agent=request.headers.get("user-agent"),
        )
        lookup_ms = (time.perf_counter() - started) * 1000.0
    except CodeNotFound:
        log_redirect_decision(
            "django",
            short_code=code,
            status_code=404,
            destination_url=None,
            lookup_ms=0.0,
            result="not_found",
        )
        return render(request, "links/404.html", {"code": code}, status=404)
    except LinkGone:
        log_redirect_decision(
            "django",
            short_code=code,
            status_code=410,
            destination_url=None,
            lookup_ms=0.0,
            result="gone",
        )
        return render(request, "links/410.html", {"code": code}, status=410)

    log_redirect_decision(
        "django",
        short_code=code,
        status_code=decision.status_code,
        destination_url=decision.destination_url,
        lookup_ms=lookup_ms,
        result="found",
    )
    response = HttpResponse(b"", status=decision.status_code)
    response["Location"] = decision.destination_url
    response["Cache-Control"] = "no-store"
    response["Content-Length"] = "0"
    return response


def dashboard(request: HttpRequest) -> HttpResponse:
    """Dashboard view — POST creates a link, GET renders the page."""

    if request.method not in {"GET", "POST"}:
        return HttpResponseNotAllowed(["GET", "POST"])

    service = get_service(request)
    error: Exception | None = None
    created = None

    if request.method == "POST":
        try:
            redirect_status = _parse_int_field(
                request.POST.get("redirect_status"),
                default=service.default_redirect_status,
                field="redirect_status",
            )
            max_clicks = _parse_optional_int_field(
                request.POST.get("max_clicks"), field="max_clicks"
            )
            expires_at = _parse_optional_datetime(request.POST.get("expires_at"))
            created = service.create_link(
                request.POST.get("url", ""),
                alias=request.POST.get("alias") or None,
                code_strategy=request.POST.get("strategy", "base62"),
                redirect_status=redirect_status,
                expires_at=expires_at,
                max_clicks=max_clicks,
            )
        except Exception as exc:  # noqa: BLE001 - render form feedback.
            error = exc
        if _is_htmx(request):
            if error:
                return render(
                    request,
                    "links/partials/form_error.html",
                    {"error": error},
                    status=200,
                )
            return render(
                request,
                "links/partials/create_success.html",
                {
                    "link": created,
                    "short_url": _short_url(request, created.short_code),
                    "total": len(service.list_links()),
                },
                status=201,
            )
        if not error:
            return redirect("links:dashboard")

    links = service.list_links()
    default_redirect = getattr(settings, "SNIPLINK_DEFAULT_REDIRECT_STATUS", 302)
    return render(
        request,
        "links/dashboard.html",
        {
            "links": links,
            "error": error,
            "default_redirect_status": default_redirect,
            "short_urls": {link.short_code: _short_url(request, link.short_code) for link in links},
        },
    )


def disable_link(request: HttpRequest, code: str) -> HttpResponse:
    """Disable via HTMX form POST. CSRF-protected (no @csrf_exempt)."""

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    service = get_service(request)
    try:
        link = service.disable_link(code)
    except CodeNotFound:
        return _htmx_lifecycle_error(request, code, status=404)
    except LinkGone:
        return _htmx_lifecycle_error(request, code, status=410)
    if _is_htmx(request):
        return render(
            request,
            "links/partials/link_row.html",
            {"link": link, "short_url": _short_url(request, link.short_code)},
        )
    return redirect("links:dashboard")


def delete_link(request: HttpRequest, code: str) -> HttpResponse:
    """Soft-delete via HTMX form POST. CSRF-protected (no @csrf_exempt)."""

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    service = get_service(request)
    try:
        service.delete_link(code)
    except CodeNotFound:
        return _htmx_lifecycle_error(request, code, status=404)
    if _is_htmx(request):
        return HttpResponse(status=200)
    return redirect("links:dashboard")


def stats_panel(request: HttpRequest, code: str) -> HttpResponse:
    if request.method not in {"GET", "HEAD"}:
        return HttpResponseNotAllowed(["GET", "HEAD"])
    if not _is_htmx(request):
        auth_response = _require_api_key(request)
        if auth_response is not None:
            return auth_response
    service = get_service(request)
    try:
        service.resolve(code, record_click=False)
        stats = service.stats(code)
    except CodeNotFound:
        return render(request, "links/404.html", {"code": code}, status=404)
    except LinkGone:
        return render(request, "links/410.html", {"code": code}, status=410)
    return render(request, "links/partials/stats.html", {"stats": stats})


@csrf_exempt
def api_create(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return _json_method_not_allowed(["POST"])
    auth_response = _require_api_key(request)
    if auth_response is not None:
        return auth_response
    if not _within_body_cap(request):
        return _payload_too_large_response()
    try:
        body = request.body
    except RequestDataTooBig:
        return _payload_too_large_response()
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
        expires_at = _parse_optional_datetime(payload.get("expires_at"))
        link = get_service(request).create_link(
            payload.get("url", ""),
            alias=payload.get("alias"),
            code_strategy=payload.get("strategy", "base62"),
            redirect_status=parse_api_redirect_status(payload.get("redirect_status")),
            expires_at=expires_at,
            max_clicks=parse_api_max_clicks(payload.get("max_clicks")),
            metadata=parse_api_metadata(payload.get("metadata")),
        )
        short_url = _short_url(request, link.short_code)
        response = JsonResponse(link_to_dict(link, short_url=short_url), status=201)
        response["Location"] = short_url
        return response
    except Exception as exc:  # noqa: BLE001 - API envelope maps domain errors.
        return JsonResponse(error_envelope(exc), status=status_for_exception(exc))


@csrf_exempt
def api_detail(request: HttpRequest, code: str) -> JsonResponse | HttpResponse:
    auth_response = _require_api_key(request)
    if auth_response is not None:
        return auth_response
    service = get_service(request)
    if request.method == "GET":
        try:
            decision = service.resolve(code, record_click=False)
            return JsonResponse(
                link_to_dict(decision.link, short_url=_short_url(request, code))
            )
        except Exception as exc:  # noqa: BLE001
            return JsonResponse(error_envelope(exc), status=status_for_exception(exc))
    if request.method == "DELETE":
        try:
            service.delete_link(code)
            return HttpResponse(status=204)
        except Exception as exc:  # noqa: BLE001
            return JsonResponse(error_envelope(exc), status=status_for_exception(exc))
    return _json_method_not_allowed(["GET", "DELETE"])


@csrf_exempt
def api_disable(request: HttpRequest, code: str) -> JsonResponse:
    if request.method != "POST":
        return _json_method_not_allowed(["POST"])
    auth_response = _require_api_key(request)
    if auth_response is not None:
        return auth_response
    try:
        link = get_service(request).disable_link(code)
        return JsonResponse(link_to_dict(link, short_url=_short_url(request, code)))
    except Exception as exc:  # noqa: BLE001
        return JsonResponse(error_envelope(exc), status=status_for_exception(exc))


@csrf_exempt
def api_expire(request: HttpRequest, code: str) -> JsonResponse:
    if request.method != "POST":
        return _json_method_not_allowed(["POST"])
    auth_response = _require_api_key(request)
    if auth_response is not None:
        return auth_response
    if not _within_body_cap(request):
        return _payload_too_large_response()
    try:
        body = request.body
    except RequestDataTooBig:
        return _payload_too_large_response()
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
        when = _parse_optional_datetime(payload.get("expires_at"))
        if when is None:
            when = datetime.now(timezone.utc)
        link = get_service(request).expire_link(code, when)
        return JsonResponse(link_to_dict(link, short_url=_short_url(request, code)))
    except Exception as exc:  # noqa: BLE001
        return JsonResponse(error_envelope(exc), status=status_for_exception(exc))


@csrf_exempt
def api_stats(request: HttpRequest, code: str) -> JsonResponse:
    if request.method != "GET":
        return _json_method_not_allowed(["GET"])
    auth_response = _require_api_key(request)
    if auth_response is not None:
        return auth_response
    try:
        service = get_service(request)
        service.resolve(code, record_click=False)
        return JsonResponse(service.stats(code))
    except Exception as exc:  # noqa: BLE001
        return JsonResponse(error_envelope(exc), status=status_for_exception(exc))


def _require_api_key(request: HttpRequest) -> JsonResponse | None:
    """Return a 401 response when ``SNIPLINK_API_KEY`` is set and missing."""

    expected = getattr(settings, "SNIPLINK_API_KEY", None)
    if not expected:
        return None
    supplied = request.headers.get("X-API-Key") or request.headers.get("Authorization", "")
    if supplied.lower().startswith("bearer "):
        supplied = supplied[7:].strip()
    if not secrets.compare_digest(supplied, expected):
        return JsonResponse(
            error_envelope(AuthError("invalid or missing API key")),
            status=401,
        )
    return None


def _htmx_lifecycle_error(
    request: HttpRequest, code: str, *, status: int
) -> HttpResponse:
    template = "links/404.html" if status == 404 else "links/410.html"
    return render(request, template, {"code": code}, status=status)


def _short_url(request: HttpRequest, code: str) -> str:
    return request.build_absolute_uri(reverse("links:redirect", args=[code]))


def _is_htmx(request: HttpRequest) -> bool:
    return request.headers.get("HX-Request") == "true"


def _within_body_cap(request: HttpRequest) -> bool:
    cap = getattr(settings, "SNIPLINK_API_MAX_BODY_BYTES", 65536)
    raw = request.META.get("CONTENT_LENGTH")
    if raw is None or raw == "":
        return True
    try:
        length = int(raw)
    except (TypeError, ValueError):
        return False
    return 0 <= length <= cap


def _payload_too_large_response() -> JsonResponse:
    return JsonResponse(
        {
            "error": {
                "type": "PayloadTooLarge",
                "message": "request body exceeds configured limit",
            }
        },
        status=413,
    )


def _json_method_not_allowed(allowed: list[str]) -> JsonResponse:
    return JsonResponse(
        {"error": {"type": "MethodNotAllowed", "message": "method not allowed"}},
        status=405,
        headers={"Allow": ", ".join(allowed)},
    )


def _parse_optional_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"expires_at: not an ISO 8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_int_field(value: str | None, *, default: int, field: str) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field}: expected an integer, got {value!r}") from exc


def _parse_optional_int_field(value: str | None, *, field: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field}: expected an integer, got {value!r}") from exc
    if parsed < 1:
        raise ValueError(f"{field}: must be at least 1 when set")
    return parsed
