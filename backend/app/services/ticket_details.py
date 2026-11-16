from sqlalchemy import func, literal, select, union_all, update
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AssignmentConflictError, InvalidAssigneeError, TicketNotFoundError
from app.core.observability import logged_operation
from app.models.auth import User, UserRole
from app.models.ticket import Ticket, TicketAssignmentHistory, TicketComment, TicketStatusHistory
from app.schemas.ticket_details import (
    AssignmentUpdate,
    CommentCreate,
    CommentPage,
    HistoryItem,
    HistoryPage,
    PageQuery,
)


@logged_operation
def get_ticket(db: Session, actor: User, ticket_id: int) -> Ticket:
    scope = [] if actor.role == UserRole.SUPPORT else [Ticket.requester_id == actor.id]
    ticket = db.scalar(
        select(Ticket)
        .where(Ticket.id == ticket_id, *scope)
        .options(joinedload(Ticket.requester), joinedload(Ticket.assignee))
        .execution_options(populate_existing=True)
    )
    if ticket is None:
        raise TicketNotFoundError
    return ticket


@logged_operation
def list_support_members(db: Session) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .where(User.role == UserRole.SUPPORT, User.is_active.is_(True))
            .order_by(User.name, User.id)
        )
    )


@logged_operation
def assign_ticket(db: Session, actor: User, ticket_id: int, data: AssignmentUpdate) -> Ticket:
    ticket = get_ticket(db, actor, ticket_id)
    if ticket.assignment_version != data.expected_assignment_version:
        raise AssignmentConflictError
    if data.assignee_id is not None:
        assignee = db.scalar(
            select(User).where(
                User.id == data.assignee_id, User.role == UserRole.SUPPORT, User.is_active.is_(True)
            )
        )
        if assignee is None:
            raise InvalidAssigneeError
    previous = ticket.assignee_id
    # Even a no-op uses compare-and-swap so stale requests cannot silently succeed.
    try:
        result = db.execute(
            update(Ticket)
            .where(
                Ticket.id == ticket_id,
                Ticket.assignment_version == data.expected_assignment_version,
            )
            .values(assignee_id=data.assignee_id, assignment_version=Ticket.assignment_version + 1)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise AssignmentConflictError
        if previous != data.assignee_id:
            db.add(
                TicketAssignmentHistory(
                    ticket_id=ticket_id,
                    previous_assignee_id=previous,
                    new_assignee_id=data.assignee_id,
                    changed_by_id=actor.id,
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return get_ticket(db, actor, ticket_id)


@logged_operation
def add_comment(db: Session, actor: User, ticket_id: int, data: CommentCreate) -> TicketComment:
    get_ticket(db, actor, ticket_id)
    comment = TicketComment(ticket_id=ticket_id, author_id=actor.id, body=data.body)
    try:
        db.add(comment)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(comment)
    return comment


@logged_operation
def list_comments(db: Session, actor: User, ticket_id: int, query: PageQuery) -> CommentPage:
    get_ticket(db, actor, ticket_id)
    scope = TicketComment.ticket_id == ticket_id
    total = db.scalar(select(func.count()).select_from(TicketComment).where(scope))
    items = db.scalars(
        select(TicketComment)
        .where(scope)
        .options(joinedload(TicketComment.author))
        .order_by(TicketComment.created_at.desc(), TicketComment.id.desc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    ).all()
    return CommentPage(items=items, total=total, **query.model_dump())


@logged_operation
def list_history(db: Session, actor: User, ticket_id: int, query: PageQuery) -> HistoryPage:
    ticket = get_ticket(db, actor, ticket_id)
    # Page the combined timeline in SQL rather than loading entire histories in memory.
    timeline = union_all(
        select(
            TicketStatusHistory.id.label("id"),
            literal("status").label("kind"),
            TicketStatusHistory.changed_at.label("time"),
        ).where(TicketStatusHistory.ticket_id == ticket_id),
        select(
            TicketAssignmentHistory.id, literal("assignment"), TicketAssignmentHistory.changed_at
        ).where(TicketAssignmentHistory.ticket_id == ticket_id),
    ).subquery()
    # Snapshot migrations did not store creation events; expose the known creation separately.
    has_creation = db.scalar(
        select(TicketStatusHistory.id)
        .where(TicketStatusHistory.ticket_id == ticket_id, TicketStatusHistory.event == "created")
        .limit(1)
    )
    if has_creation is None:
        timeline = union_all(
            select(timeline),
            select(
                literal(0).label("id"),
                literal("creation").label("kind"),
                literal(ticket.created_at).label("time"),
            ),
        ).subquery()
    total = db.scalar(select(func.count()).select_from(timeline))
    rows = (
        db.execute(
            select(timeline)
            .order_by(timeline.c.time.desc(), timeline.c.kind.desc(), timeline.c.id.desc())
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
        .mappings()
        .all()
    )

    statuses = {
        entry.id: entry
        for entry in db.scalars(
            select(TicketStatusHistory).where(
                TicketStatusHistory.id.in_([row["id"] for row in rows if row["kind"] == "status"])
            )
        )
    }
    assignments = {
        entry.id: entry
        for entry in db.scalars(
            select(TicketAssignmentHistory).where(
                TicketAssignmentHistory.id.in_(
                    [row["id"] for row in rows if row["kind"] == "assignment"]
                )
            )
        )
    }
    user_ids = {ticket.requester_id}
    user_ids.update(entry.changed_by_id for entry in statuses.values())
    for entry in assignments.values():
        user_ids.update((entry.changed_by_id, entry.previous_assignee_id, entry.new_assignee_id))
    people = {
        user.id: user
        for user in db.scalars(
            select(User).where(
                User.id.in_([user_id for user_id in user_ids if user_id is not None])
            )
        )
    }

    def person(user_id):
        user = people.get(user_id)
        return {"id": user.id, "name": user.name} if user else None

    items = []
    for row in rows:
        if row["kind"] == "creation":
            items.append(
                HistoryItem(
                    id="creation",
                    event="created",
                    actor=person(ticket.requester_id),
                    changed_at=ticket.created_at,
                    new_status="open",
                )
            )
        elif row["kind"] == "status":
            entry = statuses[row["id"]]
            items.append(
                HistoryItem(
                    id=f"status-{entry.id}",
                    event=entry.event,
                    actor=person(entry.changed_by_id),
                    changed_at=entry.changed_at,
                    previous_status=entry.previous_status,
                    new_status=entry.new_status,
                )
            )
        else:
            entry = assignments[row["id"]]
            items.append(
                HistoryItem(
                    id=f"assignment-{entry.id}",
                    event="assignment",
                    actor=person(entry.changed_by_id),
                    changed_at=entry.changed_at,
                    previous_assignee=person(entry.previous_assignee_id),
                    new_assignee=person(entry.new_assignee_id),
                )
            )
    return HistoryPage(items=items, total=total, **query.model_dump())
