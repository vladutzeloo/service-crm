"""Client-domain models: Client, Contact, Location, ServiceContract.

Soft-delete via ``is_active`` on Client and ServiceContract — history
(tickets, interventions) remains queryable after deactivation. Hard
delete is reserved for the GDPR forget endpoint (v0.9.0).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from ..shared import ulid
from ..shared.audit import Auditable


class Client(db.Model, Auditable):  # type: ignore[name-defined,misc]
    __tablename__ = "client"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    contacts: Mapped[list[Contact]] = relationship(
        "Contact", back_populates="client", cascade="all, delete-orphan"
    )
    locations: Mapped[list[Location]] = relationship(
        "Location", back_populates="client", cascade="all, delete-orphan"
    )
    contracts: Mapped[list[ServiceContract]] = relationship(
        "ServiceContract", back_populates="client", cascade="all, delete-orphan"
    )
    equipment: Mapped[list["Equipment"]] = relationship(  # type: ignore[name-defined]
        "Equipment", back_populates="client", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Client {self.name!r}>"


class Contact(db.Model, Auditable):  # type: ignore[name-defined,misc]
    __tablename__ = "contact"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    client_id: Mapped[bytes] = mapped_column(
        ulid.ULID, ForeignKey("client.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    client: Mapped[Client] = relationship("Client", back_populates="contacts")

    def __repr__(self) -> str:
        return f"<Contact {self.name!r}>"


class Location(db.Model, Auditable):  # type: ignore[name-defined,misc]
    __tablename__ = "location"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    client_id: Mapped[bytes] = mapped_column(
        ulid.ULID, ForeignKey("client.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False, default="")
    city: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    country: Mapped[str] = mapped_column(String(80), nullable=False, default="")

    client: Mapped[Client] = relationship("Client", back_populates="locations")
    equipment: Mapped[list["Equipment"]] = relationship("Equipment", back_populates="location")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<Location {self.label!r}>"


class ServiceContract(db.Model, Auditable):  # type: ignore[name-defined,misc]
    __tablename__ = "service_contract"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    client_id: Mapped[bytes] = mapped_column(
        ulid.ULID, ForeignKey("client.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    reference: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    client: Mapped[Client] = relationship("Client", back_populates="contracts")

    __table_args__ = (
        CheckConstraint(
            "ends_on IS NULL OR ends_on > starts_on",
            name="ck_service_contract_dates",
        ),
    )

    def __repr__(self) -> str:
        return f"<ServiceContract {self.title!r}>"
