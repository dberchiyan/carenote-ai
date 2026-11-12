"""Demo users and roles."""

import enum

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from carenote.db import Base, UuidPk


class Role(enum.StrEnum):
    NURSE = "nurse"
    CHARGE_NURSE = "charge_nurse"
    AUDITOR = "auditor"


class User(UuidPk, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    role: Mapped[Role] = mapped_column(
        Enum(Role, name="role", values_callable=lambda e: [m.value for m in e])
    )
    # Nurses and charge nurses belong to one ward; auditors have none.
    ward: Mapped[str | None] = mapped_column(String(32))
