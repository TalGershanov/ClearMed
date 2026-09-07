from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class UserCreate(BaseModel):
	email: EmailStr
	name: str
	password: str

	@field_validator("name")
	@classmethod
	def name_not_blank(cls, value: str) -> str:
		value = value.strip()
		if not value:
			raise ValueError("Name must not be empty")
		return value

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
	# None only for accounts created before this field existed -- see
	# webapp/users/models.py::User.name.
	name: Optional[str] = None
	created_at: datetime
