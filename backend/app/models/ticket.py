from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.auth import User, utc_now


class TicketCategory(StrEnum):
    IT = "it"
    FACILITIES = "facilities"
    HR = "hr"


class TicketPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


def enum_column(enum_type, name):
    return Enum(
        enum_type,
        values_callable=lambda values: [item.value for item in values],
        native_enum=False,
        create_constraint=True,
        name=name,
    )


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_created_at_id", "created_at", "id"),
        Index("ix_tickets_requester_created_id", "requester_id", "created_at", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[TicketCategory] = mapped_column(enum_column(TicketCategory, "ticket_category"))
    priority: Mapped[TicketPriority] = mapped_column(enum_column(TicketPriority, "ticket_priority"))
    status: Mapped[TicketStatus] = mapped_column(
        enum_column(TicketStatus, "ticket_status"),
        default=TicketStatus.OPEN,
    )
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    requester: Mapped[User] = relationship(foreign_keys=[requester_id])
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    assignment_version: Mapped[int] = mapped_column(default=0, server_default="0")
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id])


class HistoryEvent(StrEnum):
    CREATED = "created"
    TRANSITION = "transition"
    SNAPSHOT = "snapshot"


class TicketStatusHistory(Base):
    __tablename__ = "ticket_status_history"
    __table_args__ = (Index("ix_ticket_history_ticket_time", "ticket_id", "changed_at", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"))
    previous_status: Mapped[TicketStatus | None] = mapped_column(
        enum_column(TicketStatus, "history_previous_status"),
        nullable=True,
    )
    new_status: Mapped[TicketStatus] = mapped_column(
        enum_column(TicketStatus, "history_new_status")
    )
    changed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    event: Mapped[HistoryEvent] = mapped_column(enum_column(HistoryEvent, "history_event"))


class TicketComment(Base):
    __tablename__ = "ticket_comments"
    __table_args__ = (Index("ix_ticket_comments_ticket_time", "ticket_id", "created_at", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    author: Mapped[User] = relationship()


class TicketAssignmentHistory(Base):
    __tablename__ = "ticket_assignment_history"
    __table_args__ = (Index("ix_ticket_assignment_ticket_time", "ticket_id", "changed_at", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"))
    previous_assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    new_assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    changed_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
