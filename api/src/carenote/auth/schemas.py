import uuid

from pydantic import BaseModel, ConfigDict, Field

from carenote.auth.models import Role


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    display_name: str
    role: Role
    ward: str | None


class DemoLoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
