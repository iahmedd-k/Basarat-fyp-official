from types import SimpleNamespace

import pytest

from app.services import email_service


@pytest.fixture(autouse=True)
def _mock_email_service():
    yield


class _FakeResponse:
    status_code = 202
    text = ""


class _FakeAsyncClient:
    payloads = []

    def __init__(self, **kwargs):
        self.options = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def post(self, url, **kwargs):
        self.payloads.append((url, self.options, kwargs))
        return _FakeResponse()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "expected_subject", "expected_content"),
    [
        (
            "send_verification_code",
            "Verify your Basarat account",
            "Verify your email address",
        ),
        (
            "send_email_change_code",
            "Confirm your new Basarat email",
            "Confirm your new email address",
        ),
        (
            "send_password_reset_code",
            "Your Basarat password reset code",
            "Reset your password",
        ),
        (
            "send_password_changed_alert",
            "Security alert: Your Basarat password was changed",
            "Your password was changed",
        ),
    ],
)
async def test_transactional_emails_include_branded_html_and_plain_text(
    monkeypatch, method_name, expected_subject, expected_content
):
    _FakeAsyncClient.payloads = []
    monkeypatch.setattr(email_service.httpx, "AsyncClient", _FakeAsyncClient)
    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: SimpleNamespace(
            SENDGRID_API_KEY="test-api-key",
            SENDGRID_FROM_EMAIL="no-reply@example.com",
            EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES=10,
            PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=15,
        ),
    )

    service = email_service.EmailService()
    if method_name == "send_password_changed_alert":
        result = await getattr(service, method_name)("investor@example.com")
    else:
        result = await getattr(service, method_name)("investor@example.com", "123456")

    assert result == {"status": "sent"}
    assert len(_FakeAsyncClient.payloads) == 1
    url, options, request = _FakeAsyncClient.payloads[0]
    assert url == email_service.SENDGRID_API_URL
    assert options["timeout"] == 3.0
    assert request["headers"]["Authorization"] == "Bearer test-api-key"

    payload = request["json"]
    assert payload["personalizations"][0]["to"] == [
        {"email": "investor@example.com"}
    ]
    assert payload["subject"] == expected_subject
    assert [item["type"] for item in payload["content"]] == [
        "text/plain",
        "text/html",
    ]
    plain_text, html_content = [item["value"] for item in payload["content"]]
    assert "Basarat" in plain_text
    assert "Basarat" in html_content
    assert expected_content in plain_text
    assert expected_content in html_content
    if method_name != "send_password_changed_alert":
        assert "123456" in plain_text
        assert "123456" in html_content


@pytest.mark.asyncio
async def test_verification_code_is_escaped_in_html(monkeypatch):
    _FakeAsyncClient.payloads = []
    monkeypatch.setattr(email_service.httpx, "AsyncClient", _FakeAsyncClient)
    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: SimpleNamespace(
            SENDGRID_API_KEY="test-api-key",
            SENDGRID_FROM_EMAIL="no-reply@example.com",
            EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES=10,
        ),
    )

    result = await email_service.EmailService().send_verification_code(
        "investor@example.com", "<123456>"
    )

    assert result == {"status": "sent"}
    html_content = _FakeAsyncClient.payloads[0][2]["json"]["content"][1]["value"]
    assert "&lt;123456&gt;" in html_content
    assert "<123456>" not in html_content
