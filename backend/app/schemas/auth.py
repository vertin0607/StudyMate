"""注册、登录和当前用户的请求结构。客户端不能提交 user_id。"""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    username: str
    password: str
    email: str | None = None
    nickname: str | None = None

    @field_validator("username")
    @classmethod
    def clean_username(cls, value: str) -> str:
        text = value.strip()
        if not text or len(text) > 50 or any(character.isspace() for character in text):
            raise ValueError("需要 1 到 50 个字符，且不能包含空白")
        return text

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip().lower()
        if not text:
            return None
        if len(text) > 255 or _EMAIL.fullmatch(text) is None:
            raise ValueError("格式不正确")
        return text

    @field_validator("nickname")
    @classmethod
    def clean_nickname(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            return None
        if len(text) > 50:
            raise ValueError("不能超过 50 个字符")
        return text

    @field_validator("password")
    @classmethod
    def clean_password(cls, value: str) -> str:
        if not 8 <= len(value) <= 128:
            raise ValueError("需要 8 到 128 位")
        if not any(character.isalpha() for character in value) or not any(character.isdigit() for character in value):
            raise ValueError("需要同时包含字母和数字")
        return value

    @model_validator(mode="after")
    def password_differs_from_username(self) -> "RegisterRequest":
        if self.password.casefold() == self.username.casefold():
            raise ValueError("密码不能与用户名相同")
        return self


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def clean_username(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("不能为空")
        return text


class UserPublic(BaseModel):
    """返回给浏览器的用户资料。不含密码哈希和会话令牌。"""

    id: int
    username: str
    email: str | None
    nickname: str
    avatar: str | None
    is_active: bool
    created_at: str
    updated_at: str
