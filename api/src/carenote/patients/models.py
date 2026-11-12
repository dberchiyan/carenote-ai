"""Patients (synthetic)."""

import datetime as dt

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from carenote.db import Base, UuidPk


class Patient(UuidPk, Base):
    __tablename__ = "patients"

    mrn: Mapped[str] = mapped_column(String(32), unique=True)
    given_name: Mapped[str] = mapped_column(String(64))
    family_name: Mapped[str] = mapped_column(String(64))
    birth_date: Mapped[dt.date] = mapped_column(Date)
    sex: Mapped[str] = mapped_column(String(16))
    ward: Mapped[str] = mapped_column(String(32), index=True)
    room: Mapped[str] = mapped_column(String(16))

    @property
    def full_name(self) -> str:
        return f"{self.given_name} {self.family_name}"
