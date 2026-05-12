"""Tests for the shared idempotency helper."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from service_crm.shared import idempotency
from service_crm.shared.idempotency import IdempotencyKey, record, sweep
from tests.factories import UserFactory


@pytest.mark.integration
def test_record_new_pair(db_session: Session) -> None:
    user = UserFactory()
    db_session.flush()
    assert record(db_session, user_id=user.id, token="abc", route="/t") is True
    rows = db_session.query(IdempotencyKey).filter(IdempotencyKey.user_id == user.id).all()
    assert len(rows) == 1


@pytest.mark.integration
def test_record_duplicate_pair(db_session: Session) -> None:
    user = UserFactory()
    db_session.flush()
    record(db_session, user_id=user.id, token="abc")
    assert record(db_session, user_id=user.id, token="abc") is False


@pytest.mark.integration
def test_record_empty_token_passes_through(db_session: Session) -> None:
    user = UserFactory()
    db_session.flush()
    assert record(db_session, user_id=user.id, token="") is True
    assert record(db_session, user_id=user.id, token="   ") is True


@pytest.mark.integration
def test_record_oversized_token_passes_through(db_session: Session) -> None:
    user = UserFactory()
    db_session.flush()
    assert record(db_session, user_id=user.id, token="x" * 65) is True


@pytest.mark.integration
def test_sweep_removes_expired(db_session: Session) -> None:
    user = UserFactory()
    db_session.flush()
    past = datetime.now().astimezone() - timedelta(days=1)
    db_session.add(
        IdempotencyKey(
            user_id=user.id,
            token="expired-token",
            created_at=past,
            expires_at=past,
        )
    )
    db_session.flush()
    removed = sweep(db_session)
    assert removed >= 1
    remaining = (
        db_session.query(IdempotencyKey).filter(IdempotencyKey.token == "expired-token").count()
    )
    assert remaining == 0


@pytest.mark.integration
def test_window_constant_is_24h() -> None:
    assert timedelta(hours=24) == idempotency.WINDOW
