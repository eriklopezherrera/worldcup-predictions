import asyncio

import boto3
import botocore.exceptions
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.schemas.auth import (
    ConfirmForgotPasswordRequest,
    ConfirmRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _cognito():
    return boto3.client("cognito-idp", region_name=settings.cognito_region)


def _client_id() -> str:
    return settings.cognito_client_id


@router.post("/register", response_model=MessageResponse)
async def register(body: RegisterRequest):
    client = _cognito()
    try:
        await asyncio.to_thread(
            client.sign_up,
            ClientId=_client_id(),
            Username=body.username,
            Password=body.password,
            UserAttributes=[{"Name": "email", "Value": body.email}],
        )
    except client.exceptions.UsernameExistsException:
        raise HTTPException(status_code=409, detail="Username already exists")
    except client.exceptions.InvalidPasswordException as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except client.exceptions.InvalidParameterException as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except botocore.exceptions.ClientError as exc:
        raise HTTPException(status_code=400, detail=exc.response["Error"]["Message"])
    return MessageResponse(message="Verification email sent")


@router.post("/confirm", response_model=MessageResponse)
async def confirm(body: ConfirmRequest):
    client = _cognito()
    try:
        await asyncio.to_thread(
            client.confirm_sign_up,
            ClientId=_client_id(),
            Username=body.email,
            ConfirmationCode=body.code,
        )
    except client.exceptions.CodeMismatchException:
        raise HTTPException(status_code=400, detail="Invalid confirmation code")
    except client.exceptions.ExpiredCodeException:
        raise HTTPException(status_code=400, detail="Confirmation code has expired")
    except client.exceptions.UserNotFoundException:
        raise HTTPException(status_code=404, detail="User not found")
    except botocore.exceptions.ClientError as exc:
        raise HTTPException(status_code=400, detail=exc.response["Error"]["Message"])
    return MessageResponse(message="Email confirmed")


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    client = _cognito()
    try:
        response = await asyncio.to_thread(
            client.initiate_auth,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": body.username_or_email,
                "PASSWORD": body.password,
            },
            ClientId=_client_id(),
        )
    except client.exceptions.NotAuthorizedException:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    except client.exceptions.UserNotConfirmedException:
        raise HTTPException(status_code=403, detail="Email not confirmed")
    except client.exceptions.UserNotFoundException:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    except botocore.exceptions.ClientError as exc:
        raise HTTPException(status_code=400, detail=exc.response["Error"]["Message"])

    auth = response["AuthenticationResult"]
    return TokenResponse(
        access_token=auth["AccessToken"],
        id_token=auth["IdToken"],
        refresh_token=auth["RefreshToken"],
        expires_in=auth["ExpiresIn"],
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest):
    client = _cognito()
    try:
        response = await asyncio.to_thread(
            client.initiate_auth,
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters={"REFRESH_TOKEN": body.refresh_token},
            ClientId=_client_id(),
        )
    except client.exceptions.NotAuthorizedException:
        raise HTTPException(status_code=401, detail="Refresh token is invalid or expired")
    except botocore.exceptions.ClientError as exc:
        raise HTTPException(status_code=400, detail=exc.response["Error"]["Message"])

    auth = response["AuthenticationResult"]
    return TokenResponse(
        access_token=auth["AccessToken"],
        id_token=auth["IdToken"],
        refresh_token=body.refresh_token,  # Cognito does not rotate the refresh token
        expires_in=auth["ExpiresIn"],
    )


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(body: ForgotPasswordRequest):
    client = _cognito()
    try:
        await asyncio.to_thread(
            client.forgot_password,
            ClientId=_client_id(),
            Username=body.email,
        )
    except client.exceptions.UserNotFoundException:
        # Return success regardless to avoid user enumeration
        pass
    except botocore.exceptions.ClientError as exc:
        raise HTTPException(status_code=400, detail=exc.response["Error"]["Message"])
    return MessageResponse(message="If that account exists, a password reset email has been sent")


@router.post("/confirm-forgot-password", response_model=MessageResponse)
async def confirm_forgot_password(body: ConfirmForgotPasswordRequest):
    client = _cognito()
    try:
        await asyncio.to_thread(
            client.confirm_forgot_password,
            ClientId=_client_id(),
            Username=body.email,
            ConfirmationCode=body.code,
            Password=body.new_password,
        )
    except client.exceptions.CodeMismatchException:
        raise HTTPException(status_code=400, detail="Invalid reset code")
    except client.exceptions.ExpiredCodeException:
        raise HTTPException(status_code=400, detail="Reset code has expired")
    except client.exceptions.InvalidPasswordException as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except client.exceptions.UserNotFoundException:
        raise HTTPException(status_code=404, detail="User not found")
    except botocore.exceptions.ClientError as exc:
        raise HTTPException(status_code=400, detail=exc.response["Error"]["Message"])
    return MessageResponse(message="Password reset successful")
