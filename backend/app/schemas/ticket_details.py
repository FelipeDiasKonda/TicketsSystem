from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_serializer

from app.models.ticket import TicketStatus
from app.schemas.ticket import TicketRequester, TicketResponse


class PageQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class TicketDetails(TicketResponse):
    assignee: TicketRequester | None
    assignment_version: int


class AssignmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignee_id: int | None = Field(ge=1)
    expected_assignment_version: int = Field(ge=0)


class CommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    body: str
    author: TicketRequester
    created_at: datetime

    @field_serializer("created_at")
    def timestamp(self, value: datetime) -> str:
        return value.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")


class CommentPage(BaseModel):
    items: list[CommentResponse]
    total: int
    page: int
    page_size: int


class HistoryItem(BaseModel):
    id: str
    event: Literal["created", "transition", "snapshot", "assignment"]
    actor: TicketRequester | None
    changed_at: datetime
    previous_status: TicketStatus | None = None
    new_status: TicketStatus | None = None
    previous_assignee: TicketRequester | None = None
    new_assignee: TicketRequester | None = None

    @field_serializer("changed_at")
    def timestamp(self, value: datetime) -> str:
        return value.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")


class HistoryPage(BaseModel):
    items: list[HistoryItem]
    total: int
    page: int
    page_size: int
