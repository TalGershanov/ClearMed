from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class UserCreate(BaseModel):
	email: EmailStr
	password: str

	@field_validator("password")
	@classmethod
	def password_min_length(cls, value: str) -> str:
		if len(value) < 8:
			raise ValueError("Password must be at least 8 characters long")
		return value


class UserLogin(BaseModel):
	email: EmailStr
	password: str


class UserOut(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: int
	email: str
	created_at: datetime
