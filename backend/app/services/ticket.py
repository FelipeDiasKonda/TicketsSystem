from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.auth import User, UserRole
from app.models.ticket import Ticket, TicketStatus
from app.schemas.ticket import TicketCreate, TicketPage


def create_ticket(db: Session, user: User, data: TicketCreate) -> Ticket:
    ticket = Ticket(**data.model_dump(), requester_id=user.id, status=TicketStatus.OPEN)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def list_tickets(db: Session, user: User, page: int, page_size: int) -> TicketPage:
    scope = [] if user.role == UserRole.SUPPORT else [Ticket.requester_id == user.id]
    total = db.scalar(select(func.count()).select_from(Ticket).where(*scope))
    tickets = db.scalars(
        select(Ticket)
        .options(joinedload(Ticket.requester))
        .where(*scope)
        .order_by(Ticket.created_at.desc(), Ticket.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return TicketPage(items=tickets, total=total, page=page, page_size=page_size)
