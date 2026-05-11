"""Service layer for the clients blueprint.

All DB access lives here. Routes call these functions and stay thin.
Cross-dialect search: Postgres uses an inline to_tsvector expression
(the GIN index in the migration makes it fast); SQLite uses LIKE with
lower() (adequate for dev/test data volumes).
"""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..extensions import db
from .models import Client, Contact, Location, ServiceContract

# ── Helpers ──────────────────────────────────────────────────────────────────


def _dialect() -> str:
    return db.engine.dialect.name


def _client_search_filter(session: Session, q: str) -> Any:
    """Return a WHERE expression that searches clients and their contacts."""
    q = q.strip()
    if not q:
        return None

    if _dialect() == "postgresql":
        from sqlalchemy import literal_column

        tsq = func.plainto_tsquery(literal_column("'simple'"), q)

        def _vec(col1: Any, col2: Any, col3: Any = None) -> Any:
            text = func.coalesce(col1, "") + " " + func.coalesce(col2, "")
            if col3 is not None:
                text = text + " " + func.coalesce(col3, "")
            return func.to_tsvector(literal_column("'simple'"), text)

        client_match = _vec(Client.name, Client.email, Client.phone).op("@@")(tsq)
        contact_ids = session.query(Contact.client_id).filter(
            _vec(Contact.name, Contact.email).op("@@")(tsq)
        )
        return or_(client_match, Client.id.in_(contact_ids))

    # SQLite / fallback — LIKE with lower()
    pattern = f"%{q.lower()}%"
    contact_ids = session.query(Contact.client_id).filter(
        or_(
            func.lower(Contact.name).like(pattern),
            func.lower(Contact.email).like(pattern),
        )
    )
    return or_(
        func.lower(Client.name).like(pattern),
        func.lower(Client.email).like(pattern),
        func.lower(Client.phone).like(pattern),
        Client.id.in_(contact_ids),
    )


# ── Clients ───────────────────────────────────────────────────────────────────


def list_clients(
    session: Session,
    *,
    q: str = "",
    active_only: bool = True,
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[Client], int]:
    """Return (page_items, total_matching_count)."""
    base = session.query(Client)
    if active_only:
        base = base.filter(Client.is_active.is_(True))
    flt = _client_search_filter(session, q)
    if flt is not None:
        base = base.filter(flt)
    total: int = base.count()
    items: list[Client] = (
        base.order_by(Client.name).offset((page - 1) * per_page).limit(per_page).all()
    )
    return items, total


def get_client(session: Session, client_id: bytes) -> Client | None:
    return session.get(Client, client_id)


def require_client(session: Session, client_hex: str) -> Client:
    """Decode hex id and return the client; raises ValueError if missing."""
    try:
        cid = bytes.fromhex(client_hex)
    except ValueError as exc:
        raise ValueError("invalid client id") from exc
    client = session.get(Client, cid)
    if client is None:
        raise ValueError("client not found")
    return client


def create_client(
    session: Session,
    *,
    name: str,
    email: str = "",
    phone: str = "",
    notes: str = "",
) -> Client:
    client = Client(
        name=name.strip(),
        email=email.strip(),
        phone=phone.strip(),
        notes=notes.strip(),
    )
    session.add(client)
    session.flush()
    return client


def update_client(
    session: Session,
    client: Client,
    *,
    name: str,
    email: str = "",
    phone: str = "",
    notes: str = "",
) -> Client:
    client.name = name.strip()
    client.email = email.strip()
    client.phone = phone.strip()
    client.notes = notes.strip()
    session.flush()
    return client


def deactivate_client(session: Session, client: Client) -> None:
    client.is_active = False
    session.flush()


def reactivate_client(session: Session, client: Client) -> None:
    client.is_active = True
    session.flush()


# ── Contacts ──────────────────────────────────────────────────────────────────


def require_contact(session: Session, contact_hex: str, client: Client) -> Contact:
    try:
        cid = bytes.fromhex(contact_hex)
    except ValueError as exc:
        raise ValueError("invalid contact id") from exc
    contact = session.get(Contact, cid)
    if contact is None or contact.client_id != client.id:
        raise ValueError("contact not found")
    return contact


def create_contact(
    session: Session,
    *,
    client_id: bytes,
    name: str,
    role: str = "",
    email: str = "",
    phone: str = "",
    is_primary: bool = False,
) -> Contact:
    contact = Contact(
        client_id=client_id,
        name=name.strip(),
        role=role.strip(),
        email=email.strip(),
        phone=phone.strip(),
        is_primary=is_primary,
    )
    session.add(contact)
    session.flush()
    return contact


def update_contact(
    session: Session,
    contact: Contact,
    *,
    name: str,
    role: str = "",
    email: str = "",
    phone: str = "",
    is_primary: bool = False,
) -> Contact:
    contact.name = name.strip()
    contact.role = role.strip()
    contact.email = email.strip()
    contact.phone = phone.strip()
    contact.is_primary = is_primary
    session.flush()
    return contact


def delete_contact(session: Session, contact: Contact) -> None:
    session.delete(contact)
    session.flush()


# ── Locations ─────────────────────────────────────────────────────────────────


def require_location(session: Session, location_hex: str, client: Client) -> Location:
    try:
        lid = bytes.fromhex(location_hex)
    except ValueError as exc:
        raise ValueError("invalid location id") from exc
    location = session.get(Location, lid)
    if location is None or location.client_id != client.id:
        raise ValueError("location not found")
    return location


def create_location(
    session: Session,
    *,
    client_id: bytes,
    label: str,
    address: str = "",
    city: str = "",
    country: str = "",
) -> Location:
    location = Location(
        client_id=client_id,
        label=label.strip(),
        address=address.strip(),
        city=city.strip(),
        country=country.strip(),
    )
    session.add(location)
    session.flush()
    return location


def update_location(
    session: Session,
    location: Location,
    *,
    label: str,
    address: str = "",
    city: str = "",
    country: str = "",
) -> Location:
    location.label = label.strip()
    location.address = address.strip()
    location.city = city.strip()
    location.country = country.strip()
    session.flush()
    return location


def delete_location(session: Session, location: Location) -> None:
    session.delete(location)
    session.flush()


# ── Contracts ─────────────────────────────────────────────────────────────────


def require_contract(session: Session, contract_hex: str, client: Client) -> ServiceContract:
    try:
        cid = bytes.fromhex(contract_hex)
    except ValueError as exc:
        raise ValueError("invalid contract id") from exc
    contract = session.get(ServiceContract, cid)
    if contract is None or contract.client_id != client.id:
        raise ValueError("contract not found")
    return contract


def create_contract(
    session: Session,
    *,
    client_id: bytes,
    title: str,
    reference: str = "",
    starts_on: date,
    ends_on: date | None = None,
    notes: str = "",
) -> ServiceContract:
    if ends_on is not None and ends_on <= starts_on:
        raise ValueError("ends_on must be after starts_on")
    contract = ServiceContract(
        client_id=client_id,
        title=title.strip(),
        reference=reference.strip(),
        starts_on=starts_on,
        ends_on=ends_on,
        notes=notes.strip(),
    )
    session.add(contract)
    session.flush()
    return contract


def update_contract(
    session: Session,
    contract: ServiceContract,
    *,
    title: str,
    reference: str = "",
    starts_on: date,
    ends_on: date | None = None,
    notes: str = "",
) -> ServiceContract:
    if ends_on is not None and ends_on <= starts_on:
        raise ValueError("ends_on must be after starts_on")
    contract.title = title.strip()
    contract.reference = reference.strip()
    contract.starts_on = starts_on
    contract.ends_on = ends_on
    contract.notes = notes.strip()
    session.flush()
    return contract


def delete_contract(session: Session, contract: ServiceContract) -> None:
    session.delete(contract)
    session.flush()


# ── CSV import ────────────────────────────────────────────────────────────────

_REQUIRED_COLS = {"name"}
_ALLOWED_COLS = {"name", "email", "phone", "notes"}


def import_clients_csv(session: Session, text: str) -> tuple[int, list[str]]:
    """Parse CSV and insert clients. Returns (imported_count, error_messages)."""
    reader = csv.DictReader(io.StringIO(text.strip()))
    if reader.fieldnames is None:
        return 0, ["CSV file is empty or missing a header row."]
    header = {f.strip().lower() for f in reader.fieldnames}
    if not (header >= _REQUIRED_COLS):
        missing = sorted(_REQUIRED_COLS - header)
        return 0, [f"Missing required columns: {', '.join(missing)}"]

    imported = 0
    errors: list[str] = []
    for row_num, raw_row in enumerate(reader, start=2):
        row = {k.strip().lower(): v for k, v in raw_row.items() if k}
        name = row.get("name", "").strip()
        if not name:
            errors.append(f"Row {row_num}: name is required.")
            continue
        create_client(
            session,
            name=name,
            email=row.get("email", "").strip(),
            phone=row.get("phone", "").strip(),
            notes=row.get("notes", "").strip(),
        )
        imported += 1

    return imported, errors
