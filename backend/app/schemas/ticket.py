from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_serializer

from app.models.ticket import TicketCategory, TicketPriority, TicketStatus


class TicketCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=150)]
    description: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=10, max_length=5000),
    ]
    category: TicketCategory
    priority: TicketPriority


class TicketRequester(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class TicketSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: TicketCategory
    priority: TicketPriority
    status: TicketStatus
    requester: TicketRequester
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        # MySQL DATETIME is stored as naive UTC; API timestamps carry the UTC offset.
        return value.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")


class TicketResponse(TicketSummary):
    description: str


class TicketPage(BaseModel):
    items: list[TicketSummary]
    total: int
    page: int
    page_size: int
