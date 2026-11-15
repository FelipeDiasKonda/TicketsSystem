from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.dependencies import CurrentUser, Database, require_csrf
from app.schemas.ticket import TicketCreate, TicketListQuery, TicketPage, TicketResponse
from app.services.ticket import create_ticket, list_tickets

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
