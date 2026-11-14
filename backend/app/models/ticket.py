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
    requester: Mapped[User] = relationship()
