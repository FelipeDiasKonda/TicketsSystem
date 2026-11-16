from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from app.api.dependencies import CurrentUser, Database, require_csrf, require_support
from app.models.auth import User
from app.schemas.ticket import TicketRequester
from app.schemas.ticket_details import (
    AssignmentUpdate,
    CommentCreate,
    CommentPage,
    CommentResponse,
    HistoryPage,
    PageQuery,
    TicketDetails,
)
from app.services import ticket_details as service


def private_response(response: Response):
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/tickets", dependencies=[Depends(private_response)])
TicketId = Annotated[int, Path(ge=1)]
SupportUser = Annotated[User, Depends(require_support)]
Pagination = Annotated[PageQuery, Query()]


@router.get("/support-members", response_model=list[TicketRequester])
def support_members(user: SupportUser, db: Database):
    return service.list_support_members(db)


@router.get("/{ticket_id}", response_model=TicketDetails)
def details(ticket_id: TicketId, user: CurrentUser, db: Database):
    return service.get_ticket(db, user, ticket_id)


@router.patch(
    "/{ticket_id}/assignee", response_model=TicketDetails, dependencies=[Depends(require_csrf)]
)
def assignment(ticket_id: TicketId, data: AssignmentUpdate, user: SupportUser, db: Database):
    return service.assign_ticket(db, user, ticket_id, data)


@router.get("/{ticket_id}/comments", response_model=CommentPage)
def comments(ticket_id: TicketId, user: CurrentUser, db: Database, query: Pagination):
    return service.list_comments(db, user, ticket_id, query)


@router.post(
    "/{ticket_id}/comments",
    response_model=CommentResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def comment(ticket_id: TicketId, data: CommentCreate, user: CurrentUser, db: Database):
    return service.add_comment(db, user, ticket_id, data)


@router.get("/{ticket_id}/history", response_model=HistoryPage)
def history(ticket_id: TicketId, user: CurrentUser, db: Database, query: Pagination):
    return service.list_history(db, user, ticket_id, query)
