from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response

from app.api.dependencies import CurrentUser, Database, require_csrf, require_support
from app.models.auth import User
from app.schemas.ticket import (
    TicketCreate,
    TicketListQuery,
    TicketPage,
    TicketResponse,
    TicketStatusUpdate,
)
from app.services.ticket import (
    StatusConflictError,
    TicketNotFoundError,
    create_ticket,
    list_tickets,
    update_ticket_status,
)

router = APIRouter(prefix="/tickets")


@router.post(
    "", response_model=TicketResponse, status_code=201, dependencies=[Depends(require_csrf)]
)
def create(data: TicketCreate, user: CurrentUser, db: Database, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return create_ticket(db, user, data)


@router.get("", response_model=TicketPage)
def list_all(
    user: CurrentUser,
    db: Database,
    response: Response,
    query: Annotated[TicketListQuery, Query()],
):
    response.headers["Cache-Control"] = "no-store"
    return list_tickets(db, user, query)


@router.patch(
    "/{ticket_id}/status", response_model=TicketResponse, dependencies=[Depends(require_csrf)]
)
def change_status(
    ticket_id: Annotated[int, Path(ge=1)],
    data: TicketStatusUpdate,
    user: Annotated[User, Depends(require_support)],
    db: Database,
    response: Response,
):
    try:
        ticket = update_ticket_status(db, ticket_id, user, data)
    except TicketNotFoundError:
        raise HTTPException(status_code=404, detail="Ticket not found.") from None
    except StatusConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    response.headers["Cache-Control"] = "no-store"
    return ticket
