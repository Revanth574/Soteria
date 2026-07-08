from __future__ import annotations

from datetime import UTC, datetime
import json

from soteria.ephemeral import EphemeralConfig, SignupFreeFlow
from soteria.web.render import (
    render_anonymous_results,
    render_expired_page,
    render_full_results,
    render_signup_gate,
)


class AnalysisWebController:
    def __init__(self, *, flow: SignupFreeFlow, config: EphemeralConfig) -> None:
        self.flow = flow
        self.config = config

    def submit_upload(self, *, pdf_bytes: bytes, filename: str, ip_address: str) -> str:
        response = self.flow.submit_anonymous_upload(
            pdf_bytes=pdf_bytes,
            filename=filename,
            ip_address=ip_address,
        )
        return render_anonymous_results(
            {
                "summary": response.preview.summary,
                "red_flags": response.preview.red_flags,
            },
            session_token=response.session_token,
        )

    def request_signup(self, *, email: str, session_token: str) -> str:
        token = self.flow.issue_signup_token(email=email, session_token=session_token)
        return render_signup_gate(
            email=email,
            signup_token=token.token,
            session_token=session_token,
        )

    def consume_signup(self, *, signup_token: str) -> str:
        account = self.flow.consume_signup_token(signup_token)
        record = self.flow.store.get_account_session(
            account.account_id,
            account.session_token,
            now=datetime.now(UTC),
        )
        if record is None:
            return render_expired_page()
        return render_full_results(json.loads(record.analysis_json))
