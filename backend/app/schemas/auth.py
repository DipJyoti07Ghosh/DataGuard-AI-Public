"""
DataGuard AI — Auth request/response schemas.
"""

from typing import Optional
from pydantic import BaseModel, Field, AliasChoices, ConfigDict


class RegisterRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    full_name: str = Field(
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("full_name", "fullName", "name"),
    )
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=72)


class GoogleLoginRequest(BaseModel):
    credential: str = Field(
        min_length=10,
        validation_alias=AliasChoices("credential", "id_token", "idToken", "token"),
    )


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    has_password: bool
    has_google: bool


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
