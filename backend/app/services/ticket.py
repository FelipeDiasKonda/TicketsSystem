from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session, joinedload

from app.models.auth import User, UserRole
from app.models.ticket import (
    HistoryEvent,
    Ticket,
    TicketPriority,
    TicketStatus,
    TicketStatusHistory,
)
from app.schemas.ticket import (
    TicketCreate,
    TicketListQuery,
    TicketPage,
    TicketSort,
    TicketStatusUpdate,
)

NEXT_STATUS = {
    TicketStatus.OPEN: TicketStatus.IN_PROGRESS,
    TicketStatus.IN_PROGRESS: TicketStatus.RESOLVED,
    TicketStatus.RESOLVED: TicketStatus.CLOSED,
}


class TicketNotFoundError(Exception):
    pass


class StatusConflictError(Exception):
    pass


def record_ticket_creation(db: Session, ticket: Ticket) -> None:
    db.flush()
    db.add(
        TicketStatusHistory(
            ticket_id=ticket.id,
            previous_status=None,
            new_status=ticket.status,
            changed_by_id=ticket.requester_id,
            changed_at=ticket.created_at,
            event=HistoryEvent.CREATED,
        )
    )


def create_ticket(db: Session, user: User, data: TicketCreate) -> Ticket:
    ticket = Ticket(**data.model_dump(), requester_id=user.id, status=TicketStatus.OPEN)
    db.add(ticket)
    record_ticket_creation(db, ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def update_ticket_status(
    db: Session, ticket_id: int, actor: User, data: TicketStatusUpdate
) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise TicketNotFoundError
    if ticket.status != data.expected_status:
        raise StatusConflictError("Ticket status has changed. Refresh and try again.")
    if NEXT_STATUS.get(data.expected_status) != data.status:
        raise StatusConflictError("Only the next workflow status is allowed.")
    try:
        changed = db.execute(
            update(Ticket)
            .where(Ticket.id == ticket_id, Ticket.status == data.expected_status)
            .values(status=data.status)
            .execution_options(synchronize_session=False)
        )
        if changed.rowcount != 1:
            db.rollback()
            raise StatusConflictError("Ticket status has changed. Refresh and try again.")
        db.add(
            TicketStatusHistory(
                ticket_id=ticket_id,
                previous_status=data.expected_status,
                new_status=data.status,
                changed_by_id=actor.id,
                event=HistoryEvent.TRANSITION,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
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
