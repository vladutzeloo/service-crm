"""Knowledge-domain models — ROADMAP 0.6.0.

Two halves:

1. **Checklists.** :class:`ChecklistTemplate` is the editable recipe;
   :class:`ChecklistRun` is the immutable snapshot taken at the moment
   a technician begins the run. Editing the template afterwards never
   mutates historical runs — the run carries its own copy of every
   item in the ``snapshot`` JSON column, and each
   :class:`ChecklistRunItem` records ``template_item_id`` as plain
   ``ULID`` (not a FK) so dropping a template-item leaves the run
   intact. Tested with a property test in ``tests/knowledge/``.

2. **Procedures.** :class:`ProcedureDocument` stores Markdown body
   text; tags via the M2M ``procedure_document_tag``. Postgres
   gets a GIN expression-index on ``title + body`` for the search
   route; SQLite falls back to ``LIKE``.

Both halves participate in the :class:`Auditable` mixin so create /
update / delete events land in ``audit_event`` automatically.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from ..shared import ulid
from ..shared.audit import Auditable

# The M2M is declared at module level so both ``ProcedureDocument`` and
# ``ProcedureTag`` can reference it through ``secondary=`` below.
procedure_document_tag = Table(
    "procedure_document_tag",
    db.metadata,
    Column(
        "procedure_document_id",
        ulid.ULID(length=16),
        ForeignKey("procedure_document.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "procedure_tag_id",
        ulid.ULID(length=16),
        ForeignKey("procedure_tag.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class ChecklistTemplate(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """Editable recipe of items a technician runs through."""

    __tablename__ = "checklist_template"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    __table_args__ = (UniqueConstraint("name", name="uq_checklist_template_name"),)

    items: Mapped[list[ChecklistTemplateItem]] = relationship(
        "ChecklistTemplateItem",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="ChecklistTemplateItem.position",
    )

    def __repr__(self) -> str:
        return f"<ChecklistTemplate {self.name!r}>"


class ChecklistTemplateItem(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """One step inside a :class:`ChecklistTemplate`."""

    __tablename__ = "checklist_template_item"

    KINDS: frozenset[str] = frozenset({"bool", "text", "number", "choice"})

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    template_id: Mapped[bytes] = mapped_column(
        ulid.ULID,
        ForeignKey("checklist_template.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="bool")
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    choice_options: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    template: Mapped[ChecklistTemplate] = relationship("ChecklistTemplate", back_populates="items")

    __table_args__ = (
        UniqueConstraint("template_id", "key", name="uq_checklist_template_item_key"),
    )

    def __repr__(self) -> str:
        return f"<ChecklistTemplateItem {self.key!r} kind={self.kind}>"


class ChecklistRun(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """Frozen snapshot of a template at run-create time.

    ``snapshot`` carries the entire template (name + items) as JSON;
    each :class:`ChecklistRunItem` then carries its own answer.
    Mutating the source template never touches an existing run.
    """

    __tablename__ = "checklist_run"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    template_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("checklist_template.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    intervention_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("service_intervention.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    completed_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=True)

    template: Mapped[ChecklistTemplate | None] = relationship(
        "ChecklistTemplate",
    )
    intervention: Mapped[Any] = relationship(
        "ServiceIntervention",
        back_populates="checklist_runs",
    )
    items: Mapped[list[ChecklistRunItem]] = relationship(
        "ChecklistRunItem",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="ChecklistRunItem.position",
    )

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None

    @property
    def title(self) -> str:
        if isinstance(self.snapshot, dict):
            name = self.snapshot.get("name")
            if isinstance(name, str) and name:
                return name
        return "(checklist)"

    def __repr__(self) -> str:
        return f"<ChecklistRun id={self.id.hex()[:8]} completed={self.is_completed}>"


class ChecklistRunItem(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """One answered step inside a :class:`ChecklistRun`.

    ``template_item_id`` is stored as plain ULID — *not* a FK — so a
    template-item that's deleted after the run was created doesn't
    cascade or NULL this row out.
    """

    __tablename__ = "checklist_run_item"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    run_id: Mapped[bytes] = mapped_column(
        ulid.ULID,
        ForeignKey("checklist_run.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_item_id: Mapped[bytes] = mapped_column(ulid.ULID, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="bool")
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    answer: Mapped[Any] = mapped_column(JSON, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    run: Mapped[ChecklistRun] = relationship("ChecklistRun", back_populates="items")

    @property
    def is_answered(self) -> bool:
        return self.answer is not None

    def __repr__(self) -> str:
        return f"<ChecklistRunItem {self.key!r}>"


class ProcedureTag(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """Tag used to group :class:`ProcedureDocument` rows.

    The ``code`` column is stable English (``"spindle"``, ``"axis"``,
    ``"controller"``); ``name`` is the editable display label.
    """

    __tablename__ = "procedure_tag"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    __table_args__ = (UniqueConstraint("code", name="uq_procedure_tag_code"),)

    documents: Mapped[list[ProcedureDocument]] = relationship(
        "ProcedureDocument",
        secondary=procedure_document_tag,
        back_populates="tags",
    )

    def __repr__(self) -> str:
        return f"<ProcedureTag {self.code!r}>"


class ProcedureDocument(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """Searchable Markdown document.

    Body is plain Markdown; the renderer in :mod:`.markdown` produces
    HTML-escaped, sanitised output for templates. Body length is
    capped at 64 KB; that's enough for a long maintenance procedure
    and small enough that the audit ``before/after`` JSON stays
    manageable.
    """

    __tablename__ = "procedure_document"

    BODY_MAX_BYTES = 64 * 1024

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(String(400), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    tags: Mapped[list[ProcedureTag]] = relationship(
        "ProcedureTag",
        secondary=procedure_document_tag,
        back_populates="documents",
        order_by="ProcedureTag.name",
    )

    def __repr__(self) -> str:
        return f"<ProcedureDocument {self.title!r}>"


__all__ = [
    "ChecklistRun",
    "ChecklistRunItem",
    "ChecklistTemplate",
    "ChecklistTemplateItem",
    "ProcedureDocument",
    "ProcedureTag",
    "procedure_document_tag",
]
