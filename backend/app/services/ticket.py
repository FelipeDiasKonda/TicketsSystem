from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.auth import User, UserRole
from app.models.ticket import Ticket, TicketPriority, TicketStatus
from app.schemas.ticket import TicketCreate, TicketListQuery, TicketPage, TicketSort


def create_ticket(db: Session, user: User, data: TicketCreate) -> Ticket:
    ticket = Ticket(**data.model_dump(), requester_id=user.id, status=TicketStatus.OPEN)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def list_tickets(db: Session, user: User, query: TicketListQuery) -> TicketPage:
    scope = [] if user.role == UserRole.SUPPORT else [Ticket.requester_id == user.id]
    for column, value in (
        (Ticket.status, query.status),
        (Ticket.category, query.category),
        (Ticket.priority, query.priority),
    ):
        if value is not None:
            scope.append(column == value)

    priority_rank = case(
        {
            TicketPriority.LOW.value: 0,
            TicketPriority.MEDIUM.value: 1,
            TicketPriority.HIGH.value: 2,
            TicketPriority.URGENT.value: 3,
        },
        value=Ticket.priority,
    )
    ordering = {
        TicketSort.CREATED_DESC: (Ticket.created_at.desc(), Ticket.id.desc()),
        TicketSort.CREATED_ASC: (Ticket.created_at.asc(), Ticket.id.asc()),
        TicketSort.PRIORITY_DESC: (
            priority_rank.desc(),
            Ticket.created_at.desc(),
            Ticket.id.desc(),
        ),
        TicketSort.PRIORITY_ASC: (priority_rank.asc(), Ticket.created_at.desc(), Ticket.id.desc()),
    }[query.sort]
    total = db.scalar(select(func.count()).select_from(Ticket).where(*scope))
    tickets = db.scalars(
        select(Ticket)
        .options(joinedload(Ticket.requester))
        .where(*scope)
        .order_by(*ordering)
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    ).all()
    return TicketPage(items=tickets, total=total, page=query.page, page_size=query.page_size)
