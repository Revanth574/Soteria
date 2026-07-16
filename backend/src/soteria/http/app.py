from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Protocol

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from soteria.email import EmailConfig, EmailSender, LoggingEmailSender, create_email_sender
from soteria.ephemeral import (
    EphemeralConfig,
    EphemeralStore,
    NotFoundError,
    RateLimitExceededError,
    SignupFreeFlow,
    UploadValidationError,
)
from soteria.extraction import ClaudeExtractor, ClaudeExtractorConfig, ExtractionConfig
from soteria.web import (
    render_anonymous_results,
    render_failure_page,
    render_full_results,
    render_not_found_page,
    render_processing_page,
    render_rate_limited_page,
    render_signup_gate,
    render_upload_page,
    render_upload_too_large_page,
)

_TOKEN_RE = re.compile(r"^[a-fA-F0-9]{32}$")
_MULTIPART_OVERHEAD_ALLOWANCE_BYTES = 16 * 1024
_STATIC_DIR = Path(__file__).resolve().parents[1] / "web" / "static"
_LOGGER = logging.getLogger(__name__)
_THEME_COOKIE = "soteria_theme"


class BackgroundTaskQueue(Protocol):
    def add_task(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Schedule a background function."""


class _FastApiBackgroundQueue:
    def __init__(self, background_tasks: BackgroundTasks) -> None:
        self.background_tasks = background_tasks

    def add_task(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        self.background_tasks.add_task(func, *args, **kwargs)


def create_app(
    *,
    flow: SignupFreeFlow,
    config: EphemeralConfig,
    trust_proxy_headers: bool = False,
    background_queue_factory: Callable[[BackgroundTasks], BackgroundTaskQueue] | None = None,
    email_sender: EmailSender | None = None,
    public_base_url: str = "http://localhost:8000",
) -> FastAPI:
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
    sender = email_sender or LoggingEmailSender()
    base_url = public_base_url.rstrip("/")

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; "
            "style-src 'self'; "
            "font-src 'self'; "
            "img-src 'self' data:; "
            "form-action 'self'; "
            "base-uri 'none'; "
            "frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.get("/", response_class=HTMLResponse)
    async def upload_page() -> HTMLResponse:
        return HTMLResponse(render_upload_page(config))

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/upload")
    async def upload(
        request: Request,
        background_tasks: BackgroundTasks,
    ) -> Response:
        content_length = _content_length(request)
        if (
            content_length is not None
            and content_length > config.max_upload_bytes + _MULTIPART_OVERHEAD_ALLOWANCE_BYTES
        ):
            return HTMLResponse(render_upload_too_large_page(), status_code=413)

        form = await request.form()
        upload_file = form.get("policy_pdf")
        if upload_file is None or not hasattr(upload_file, "read"):
            return HTMLResponse(render_not_found_page(), status_code=400)

        pdf_bytes = await upload_file.read()
        filename = getattr(upload_file, "filename", None) or "policy.pdf"
        try:
            response = flow.submit_anonymous_upload(
                pdf_bytes=pdf_bytes,
                filename=filename,
                ip_address=_client_ip(request, trust_proxy_headers=trust_proxy_headers),
                analyze_inline=False,
            )
        except RateLimitExceededError:
            return HTMLResponse(render_rate_limited_page(), status_code=429)
        except UploadValidationError as exc:
            status_code = 413 if "size" in str(exc).lower() else 400
            page = render_upload_too_large_page() if status_code == 413 else render_not_found_page()
            return HTMLResponse(page, status_code=status_code)

        queue_factory = background_queue_factory or _FastApiBackgroundQueue
        queue_factory(background_tasks).add_task(_complete_analysis_safely, flow, response.session_token)
        return RedirectResponse(f"/a/{response.session_token}", status_code=303)

    @app.get("/a/{session_token}", response_class=HTMLResponse)
    async def anonymous_results(session_token: str, request: Request) -> HTMLResponse:
        record = _record_or_none(flow, session_token)
        if record is None:
            return HTMLResponse(render_not_found_page(), status_code=404)
        if record.status == "processing":
            return HTMLResponse(render_processing_page(session_token=session_token))
        if record.status == "failed":
            return HTMLResponse(render_failure_page(session_token=session_token))
        theme = request.cookies.get(_THEME_COOKIE, "light")
        return HTMLResponse(
            render_anonymous_results(
                json.loads(record.analysis_json),
                session_token=session_token,
                theme=theme,
                current_path=request.url.path,
            )
        )

    @app.post("/signup/request", response_class=HTMLResponse)
    async def signup_request(request: Request) -> HTMLResponse:
        form = await request.form()
        email = str(form.get("email") or "")
        session_token = str(form.get("session_token") or "")
        if _record_or_none(flow, session_token) is None:
            return HTMLResponse(render_not_found_page(), status_code=404)
        token = flow.issue_signup_token(email=email, session_token=session_token)
        magic_link_url = _build_magic_link_url(public_base_url=base_url, token=token.token)
        sender.send_magic_link(to_email=email, magic_link_url=magic_link_url)
        return HTMLResponse(
            render_signup_gate(
                email=email,
                signup_token=token.token,
                session_token=session_token,
            )
        )

    @app.get("/signup/confirm/{token}")
    async def signup_confirm(token: str) -> Response:
        try:
            attachment = flow.consume_signup_token(token)
        except NotFoundError:
            return HTMLResponse(render_not_found_page(), status_code=404)
        return RedirectResponse(f"/a/{attachment.session_token}/full", status_code=303)

    @app.post("/theme")
    async def set_theme(request: Request) -> Response:
        form = await request.form()
        theme = str(form.get("theme") or "light")
        if theme not in {"light", "dark"}:
            theme = "light"
        next_path = str(form.get("next") or "/")
        if not next_path.startswith("/") or next_path.startswith("//"):
            next_path = "/"
        response = RedirectResponse(next_path, status_code=303)
        response.set_cookie(
            _THEME_COOKIE,
            theme,
            max_age=365 * 24 * 60 * 60,
            path="/",
            secure=base_url.startswith("https://"),
            httponly=True,
            samesite="lax",
        )
        return response

    @app.get("/a/{session_token}/full", response_class=HTMLResponse)
    async def full_results(session_token: str, request: Request) -> HTMLResponse:
        record = _record_or_none(flow, session_token)
        if record is None or record.account_id is None:
            return HTMLResponse(render_not_found_page(), status_code=404)
        if record.status == "processing":
            return HTMLResponse(render_processing_page(session_token=session_token))
        if record.status == "failed":
            return HTMLResponse(render_failure_page(session_token=session_token))
        theme = request.cookies.get(_THEME_COOKIE, "light")
        return HTMLResponse(
            render_full_results(
                json.loads(record.analysis_json),
                theme=theme,
                current_path=request.url.path,
                raw_analysis_json=record.analysis_json,
            )
        )

    return app


def create_app_from_env() -> FastAPI:
    config = EphemeralConfig.from_env()
    extraction_config = ExtractionConfig.from_env()
    email_config = EmailConfig.from_env()
    if extraction_config.combined_prompt_path is not None:
        extractor_config = ClaudeExtractorConfig.from_combined_file(
            extraction_config,
            combined_prompt_path=extraction_config.combined_prompt_path,
        )
    else:
        system_prompt_path = Path(os.environ.get("SOTERIA_SYSTEM_PROMPT_PATH", "prompts/system.md"))
        extractor_config = ClaudeExtractorConfig.from_extraction_config(
            extraction_config,
            system_prompt_path=system_prompt_path,
        )
    extractor = ClaudeExtractor(
        config=extractor_config,
    )
    flow = SignupFreeFlow(
        store=EphemeralStore(config),
        extractor=extractor,
        config=config,
    )
    return create_app(
        flow=flow,
        config=config,
        trust_proxy_headers=_truthy(os.environ.get("TRUST_PROXY_HEADERS", "false")),
        email_sender=create_email_sender(email_config),
        public_base_url=email_config.public_base_url,
    )


def _complete_analysis_safely(flow: SignupFreeFlow, session_token: str) -> None:
    try:
        flow.complete_analysis(session_token=session_token)
    except Exception as exc:
        try:
            flow.store.mark_analysis_failed(
                session_token=session_token,
                failure_message="Analysis failed before a valid result was produced.",
            )
        except Exception:
            _LOGGER.exception(
                "Background analysis failed and failed to mark session failed; "
                "session_token=%s",
                session_token,
            )
            _LOGGER.error(
                "Original background analysis exception; session_token=%s",
                session_token,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            return
        _LOGGER.error(
            "Background analysis failed; session_token=%s",
            session_token,
            exc_info=(type(exc), exc, exc.__traceback__),
        )


def _record_or_none(flow: SignupFreeFlow, session_token: str):
    if not _TOKEN_RE.fullmatch(session_token):
        return None
    return flow.store.get_session(session_token, now=datetime.now(UTC))


def _build_magic_link_url(*, public_base_url: str, token: str) -> str:
    return f"{public_base_url.rstrip('/')}/signup/confirm/{token}"


def _client_ip(request: Request, *, trust_proxy_headers: bool) -> str:
    if trust_proxy_headers:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            parts = [part.strip() for part in forwarded_for.split(",") if part.strip()]
            if parts:
                return parts[-1]
    return request.client.host if request.client is not None else "unknown"


def _content_length(request: Request) -> int | None:
    value = request.headers.get("content-length")
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}
