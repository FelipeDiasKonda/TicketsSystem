from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_serializer

from app.models.ticket import TicketCategory, TicketPriority, TicketStatus


class TicketSort(StrEnum):
    CREATED_DESC = "created_desc"
    CREATED_ASC = "created_asc"
    PRIORITY_DESC = "priority_desc"
    PRIORITY_ASC = "priority_asc"


class TicketListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    status: TicketStatus | None = None
    category: TicketCategory | None = None
    priority: TicketPriority | None = None
    sort: TicketSort = TicketSort.CREATED_DESC


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
