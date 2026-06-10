"""
Tests for all /auth/* endpoints.

Cognito is mocked via unittest.mock — no real AWS calls are made.
Each test verifies that the router correctly maps Cognito responses and
exceptions to the expected HTTP status codes and response shapes.
"""
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Cognito mock factory
# ---------------------------------------------------------------------------


def _make_cognito(
    sign_up_effect=None,
    confirm_sign_up_effect=None,
    initiate_auth_effect=None,
    initiate_auth_result=None,
    forgot_password_effect=None,
    confirm_forgot_password_effect=None,
):
    class _Exc:
        class UsernameExistsException(Exception):
            pass

        class InvalidPasswordException(Exception):
            pass

        class InvalidParameterException(Exception):
            pass

        class CodeMismatchException(Exception):
            pass

        class ExpiredCodeException(Exception):
            pass

        class UserNotFoundException(Exception):
            pass

        class NotAuthorizedException(Exception):
            pass

        class UserNotConfirmedException(Exception):
            pass

    mock = MagicMock()
    mock.exceptions = _Exc

    mock.sign_up.return_value = {"UserConfirmed": False}
    mock.confirm_sign_up.return_value = {}
    mock.forgot_password.return_value = {}
    mock.confirm_forgot_password.return_value = {}
    mock.initiate_auth.return_value = initiate_auth_result or {
        "AuthenticationResult": {
            "AccessToken": "fake-access-token",
            "IdToken": "fake-id-token",
            "RefreshToken": "fake-refresh-token",
            "ExpiresIn": 3600,
        }
    }

    if sign_up_effect is not None:
        mock.sign_up.side_effect = sign_up_effect
    if confirm_sign_up_effect is not None:
        mock.confirm_sign_up.side_effect = confirm_sign_up_effect
    if initiate_auth_effect is not None:
        mock.initiate_auth.side_effect = initiate_auth_effect
    if forgot_password_effect is not None:
        mock.forgot_password.side_effect = forgot_password_effect
    if confirm_forgot_password_effect is not None:
        mock.confirm_forgot_password.side_effect = confirm_forgot_password_effect

    return mock


_REGISTER_BODY = {"username": "newuser", "email": "new@example.com", "password": "Secure123!"}
_LOGIN_BODY = {"username_or_email": "newuser", "password": "Secure123!"}
_CFP_BODY = {"email": "user@example.com", "code": "123456", "new_password": "NewPass123!"}


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------


async def test_register_success_returns_message(client: AsyncClient):
    cognito = _make_cognito()
    with patch("app.routers.auth._cognito", return_value=cognito):
        r = await client.post("/auth/register", json=_REGISTER_BODY)
    assert r.status_code == 200
    assert r.json()["message"] == "Verification email sent"


async def test_register_duplicate_username_returns_409(client: AsyncClient):
    cognito = _make_cognito()
    cognito.sign_up.side_effect = cognito.exceptions.UsernameExistsException()
    with patch("app.routers.auth._cognito", return_value=cognito):
        r = await client.post("/auth/register", json=_REGISTER_BODY)
    assert r.status_code == 409
    assert "already exists" in r.json()["detail"]


async def test_register_weak_password_returns_400(client: AsyncClient):
    cognito = _make_cognito()
    cognito.sign_up.side_effect = cognito.exceptions.InvalidPasswordException("too short")
    with patch("app.routers.auth._cognito", return_value=cognito):
        r = await client.post("/auth/register", json=_REGISTER_BODY)
    assert r.status_code == 400


async def test_register_invalid_parameter_returns_400(client: AsyncClient):
    cognito = _make_cognito()
    cognito.sign_up.side_effect = cognito.exceptions.InvalidParameterException("bad param")
    with patch("app.routers.auth._cognito", return_value=cognito):
        r = await client.post("/auth/register", json=_REGISTER_BODY)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /auth/confirm
# ---------------------------------------------------------------------------


async def test_confirm_success_returns_message(client: AsyncClient):
    cognito = _make_cognito()
    with patch("app.routers.auth._cognito", return_value=cognito):
        r = await client.post("/auth/confirm", json={"email": "new@example.com", "code": "123456"})
    assert r.status_code == 200
    assert r.json()["message"] == "Email confirmed"


async def test_confirm_code_mismatch_returns_400(client: AsyncClient):
    cognito = _make_cognito()
    cognito.confirm_sign_up.side_effect = cognito.exceptions.CodeMismatchException()
    with patch("app.routers.auth._cognito", return_value=cognito):
        r = await client.post("/auth/confirm", json={"email": "new@example.com", "code": "000000"})
    assert r.status_code == 400
    assert "Invalid" in r.json()["detail"]


async def test_confirm_expired_code_returns_400(client: AsyncClient):
    cognito = _make_cognito()
    cognito.confirm_sign_up.side_effect = cognito.exceptions.ExpiredCodeException()
    with patch("app.routers.auth._cognito", return_value=cognito):
        r = await client.post("/auth/confirm", json={"email": "new@example.com", "code": "111111"})
    assert r.status_code == 400
    assert "expired" in r.json()["detail"].lower()


async def test_confirm_user_not_found_returns_404(client: AsyncClient):
    cognito = _make_cognito()
    cognito.confirm_sign_up.side_effect = cognito.exceptions.UserNotFoundException()
    with patch("app.routers.auth._cognito", return_value=cognito):
        r = await client.post("/auth/confirm", json={"email": "ghost@example.com", "code": "222222"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


async def test_login_success_returns_all_token_fields(client: AsyncClient):
    cognito = _make_cognito()
    with patch("app.routers.auth._cognito", return_value=cognito):
        r = await client.post("/auth/login", json=_LOGIN_BODY)
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] == "fake-access-token"
    assert body["id_token"] == "fake-id-token"
    assert body["refresh_token"] == "fake-refresh-token"
    assert body["expires_in"] == 3600


async def test_login_invalid_credentials_returns_401(client: AsyncClient):
    cognito = _make_cognito()
    cognito.initiate_auth.side_effect = cognito.exceptions.NotAuthorizedException()
    with patch("app.routers.auth._cognito", return_value=cognito):
        r = await client.post("/auth/login", json=_LOGIN_BODY)
    assert r.status_code == 401
    assert "Invalid credentials" in r.json()["detail"]


async def test_login_unconfirmed_email_returns_403(client: AsyncClient):
    cognito = _make_cognito()
    cognito.initiate_auth.side_effect = cognito.exceptions.UserNotConfirmedException()
    with patch("app.routers.auth._cognito", return_value=cognito):
        r = await client.post("/auth/login", json=_LOGIN_BODY)
    assert r.status_code == 403
    assert "confirmed" in r.json()["detail"].lower()


async def test_login_unknown_user_returns_401_not_404(client: AsyncClient):
    """Must return 401, not 404, to prevent user enumeration via login."""
    cognito = _make_cognito()
    cognito.initiate_auth.side_effect = cognito.exceptions.UserNotFoundException()
    with patch("app.routers.auth._cognito", return_value=cognito):
        r = await client.post("/auth/login", json=_LOGIN_BODY)
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------


async def test_refresh_success_preserves_refresh_token(client: AsyncClient):
    """Cognito does not rotate the refresh token — the original must be echoed back."""
    cognito = _make_cognito()
    with patch("app.routers.auth._cognito", return_value=cognito):
        r = await client.post("/auth/refresh", json={"refresh_token": "my-refresh-token"})
    assert r.status_code == 200
    body = r.json()
    assert body["refresh_token"] == "my-refresh-token"
    assert "access_token" in body
    assert "id_token" in body
    assert "expires_in" in body


async def test_refresh_expired_token_returns_401(client: AsyncClient):
    cognito = _make_cognito()
    cognito.initiate_auth.side_effect = cognito.exceptions.NotAuthorizedException()
    with patch("app.routers.auth._cognito", return_value=cognito):
        r = await client.post("/auth/refresh", json={"refresh_token": "expired-token"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/forgot-password
# ---------------------------------------------------------------------------


async def test_forgot_password_always_succeeds(client: AsyncClient):
    cognito = _make_cognito()
    with patch("app.routers.auth._cognito", return_value=cognito):
        r = await client.post("/auth/forgot-password", json={"email": "any@example.com"})
    assert r.status_code == 200
    assert "password reset" in r.json()["message"].lower()


async def test_forgot_password_unknown_email_still_returns_200(client: AsyncClient):
    """Must not reveal whether the email exists — user enumeration prevention."""
    cognito = _make_cognito()
    cognito.forgot_password.side_effect = cognito.exceptions.UserNotFoundException()
    with patch("app.routers.auth._cognito", return_value=cognito):
        r = await client.post("/auth/forgot-password", json={"email": "ghost@example.com"})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# POST /auth/confirm-forgot-password
# ---------------------------------------------------------------------------


async def test_confirm_forgot_password_success(client: AsyncClient):
    cognito = _make_cognito()
    with patch("app.routers.auth._cognito", return_value=cognito):
        r = await client.post("/auth/confirm-forgot-password", json=_CFP_BODY)
    assert r.status_code == 200
    assert "Password reset successful" in r.json()["message"]


async def test_confirm_forgot_password_code_mismatch_returns_400(client: AsyncClient):
    cognito = _make_cognito()
    cognito.confirm_forgot_password.side_effect = cognito.exceptions.CodeMismatchException()
    with patch("app.routers.auth._cognito", return_value=cognito):
        r = await client.post("/auth/confirm-forgot-password", json=_CFP_BODY)
    assert r.status_code == 400
    assert "Invalid" in r.json()["detail"]


async def test_confirm_forgot_password_expired_code_returns_400(client: AsyncClient):
    cognito = _make_cognito()
    cognito.confirm_forgot_password.side_effect = cognito.exceptions.ExpiredCodeException()
    with patch("app.routers.auth._cognito", return_value=cognito):
        r = await client.post("/auth/confirm-forgot-password", json=_CFP_BODY)
    assert r.status_code == 400
    assert "expired" in r.json()["detail"].lower()


async def test_confirm_forgot_password_weak_password_returns_400(client: AsyncClient):
    cognito = _make_cognito()
    cognito.confirm_forgot_password.side_effect = cognito.exceptions.InvalidPasswordException("too short")
    with patch("app.routers.auth._cognito", return_value=cognito):
        r = await client.post("/auth/confirm-forgot-password", json=_CFP_BODY)
    assert r.status_code == 400


async def test_confirm_forgot_password_user_not_found_returns_404(client: AsyncClient):
    cognito = _make_cognito()
    cognito.confirm_forgot_password.side_effect = cognito.exceptions.UserNotFoundException()
    with patch("app.routers.auth._cognito", return_value=cognito):
        r = await client.post("/auth/confirm-forgot-password", json=_CFP_BODY)
    assert r.status_code == 404
