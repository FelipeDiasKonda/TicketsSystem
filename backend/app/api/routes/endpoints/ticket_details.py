from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response

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
from app.services.ticket import TicketNotFoundError


def private_response(response: Response):
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/tickets", dependencies=[Depends(private_response)])
TicketId = Annotated[int, Path(ge=1)]
SupportUser = Annotated[User, Depends(require_support)]
Pagination = Annotated[PageQuery, Query()]


def ticket_action(action, *args):
    try:
        return action(*args)
    except TicketNotFoundError:
        raise HTTPException(404, "Ticket not found.") from None
    except service.AssignmentConflictError:
        raise HTTPException(409, "Ticket assignment has changed. Refresh and try again.") from None
    except service.InvalidAssigneeError:
        raise HTTPException(422, "Assignee must be an active support member.") from None


@router.get("/support-members", response_model=list[TicketRequester])
def support_members(user: SupportUser, db: Database):
    return service.list_support_members(db)


@router.get("/{ticket_id}", response_model=TicketDetails)
def details(ticket_id: TicketId, user: CurrentUser, db: Database):
    return ticket_action(service.get_ticket, db, user, ticket_id)


@router.patch(
    "/{ticket_id}/assignee", response_model=TicketDetails, dependencies=[Depends(require_csrf)]
)
def assignment(ticket_id: TicketId, data: AssignmentUpdate, user: SupportUser, db: Database):
    return ticket_action(service.assign_ticket, db, user, ticket_id, data)


@router.get("/{ticket_id}/comments", response_model=CommentPage)
def comments(ticket_id: TicketId, user: CurrentUser, db: Database, query: Pagination):
    return ticket_action(service.list_comments, db, user, ticket_id, query)


@router.post(
    "/{ticket_id}/comments",
    response_model=CommentResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def comment(ticket_id: TicketId, data: CommentCreate, user: CurrentUser, db: Database):
    return ticket_action(service.add_comment, db, user, ticket_id, data)


@router.get("/{ticket_id}/history", response_model=HistoryPage)
def history(ticket_id: TicketId, user: CurrentUser, db: Database, query: Pagination):
    return ticket_action(service.list_history, db, user, ticket_id, query)
