from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):

    username: str = Field(
        min_length=3,
        max_length=50,
    )

    email: EmailStr

    password: str = Field(
        min_length=6,
    )

    role: str = "user"


class UserLogin(BaseModel):

    username: str

    password: str


class UserResponse(BaseModel):

    id: int
    username: str
    email: str
    role: str

    class Config:
        from_attributes = True