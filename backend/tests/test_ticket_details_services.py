"""Database/service integration checks that also run without local network sockets."""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy.exc import OperationalError
from test_ticket_details import details_domain as domain_fixture

from app.api.dependencies import require_support
from app.api.routes.endpoints.ticket_details import ticket_action
from app.main import create_app
from app.models import TicketAssignmentHistory, TicketStatusHistory
from app.schemas.ticket import TicketStatusUpdate
from app.schemas.ticket_details import (
    AssignmentUpdate,
    CommentCreate,
    CommentResponse,
    PageQuery,
    TicketDetails,
)
from app.services import ticket_details as service
from app.services.ticket import TicketNotFoundError, update_ticket_status

details_domain = domain_fixture


def test_service_details_permissions_and_members(details_domain):
    db, users, ticket_id = details_domain
    for actor in (users[0], users[2]):
        ticket = service.get_ticket(db, actor, ticket_id)
        data = TicketDetails.model_validate(ticket).model_dump(mode="json")
        assert data["requester"] == {"id": users[0].id, "name": "employee"}
        assert data["description"] == "The full issue description."
        assert data["assignee"] is None and data["created_at"].endswith("Z")
    assert {user.id for user in service.list_support_members(db)} == {users[2].id, users[3].id}
    for operation in (service.get_ticket,):
        with pytest.raises(TicketNotFoundError):
            operation(db, users[1], ticket_id)
    with pytest.raises(HTTPException) as denied:
        require_support(users[0])
    assert denied.value.status_code == 403


def test_service_assignment_conflicts_and_combined_timeline(details_domain):
    db, users, ticket_id = details_domain
    actor = users[2]
    for version, target in enumerate((users[2].id, users[3].id, None)):
        ticket = service.assign_ticket(
            db,
            actor,
            ticket_id,
            AssignmentUpdate(
                assignee_id=target,
                expected_assignment_version=version,
            ),
        )
        assert ticket.assignee_id == target and ticket.assignment_version == version + 1
    with pytest.raises(service.AssignmentConflictError):
        service.assign_ticket(
            db,
            actor,
            ticket_id,
            AssignmentUpdate(
                assignee_id=actor.id,
                expected_assignment_version=0,
            ),
        )
    update_ticket_status(
        db, ticket_id, actor, TicketStatusUpdate(expected_status="open", status="in_progress")
    )
    history = service.list_history(db, users[0], ticket_id, PageQuery())
    assert history.total == 5
    assert [item.event for item in history.items] == [
        "transition",
        "assignment",
        "assignment",
        "assignment",
        "created",
    ]
    assert history.items[1].new_assignee is None
    assert history.items[1].previous_assignee.id == users[3].id
    assert history.items[0].actor.id == actor.id
    pages = [
        service.list_history(db, actor, ticket_id, PageQuery(page=page, page_size=2))
        for page in (1, 2, 3)
    ]
    assert [len(page.items) for page in pages] == [2, 2, 1]
    assert len({item.id for page in pages for item in page.items}) == 5


@pytest.mark.parametrize("index", [0, 1, 4, None])
def test_service_invalid_assignees(details_domain, index):
    db, users, ticket_id = details_domain
    with pytest.raises(service.InvalidAssigneeError):
        service.assign_ticket(
            db,
            users[2],
            ticket_id,
            AssignmentUpdate(
                assignee_id=users[index].id if index is not None else 999,
                expected_assignment_version=0,
            ),
        )


def test_service_comments_closed_ticket_and_pagination(details_domain):
    db, users, ticket_id = details_domain
    for previous, target in (
        ("open", "in_progress"),
        ("in_progress", "resolved"),
        ("resolved", "closed"),
    ):
        update_ticket_status(
            db,
            ticket_id,
            users[2],
            TicketStatusUpdate(
                expected_status=previous,
                status=target,
            ),
        )
    for index in range(23):
        actor = users[0] if index % 2 == 0 else users[2]
        comment = service.add_comment(
            db, actor, ticket_id, CommentCreate(body=f"  Comment {index}  ")
        )
        data = CommentResponse.model_validate(comment).model_dump(mode="json")
        assert data["body"] == f"Comment {index}" and data["author"]["id"] == actor.id
        assert data["created_at"].endswith("Z")
    first = service.list_comments(db, users[0], ticket_id, PageQuery())
    second = service.list_comments(db, users[2], ticket_id, PageQuery(page=2))
    assert first.total == second.total == 23
    assert len(first.items) == 20 and len(second.items) == 3
    assert first.items[0].body == "Comment 22"
    assert not ({item.id for item in first.items} & {item.id for item in second.items})
    for operation in (
        lambda: service.list_comments(db, users[1], ticket_id, PageQuery()),
        lambda: service.list_history(db, users[1], ticket_id, PageQuery()),
        lambda: service.add_comment(db, users[1], ticket_id, CommentCreate(body="foreign")),
    ):
        with pytest.raises(TicketNotFoundError):
            operation()


@pytest.mark.parametrize(
    "payload",
    [{"body": ""}, {"body": "  "}, {"body": "x" * 5001}, {"body": "ok", "author_id": 100}],
)
def test_service_comment_contract_validation(payload):
    with pytest.raises(ValidationError):
        CommentCreate(**payload)


def test_service_legacy_snapshot_and_creation(details_domain):
    db, users, ticket_id = details_domain
    entry = db.scalar(select(TicketStatusHistory))
    entry.event = "snapshot"
    entry.changed_by_id = None
    db.commit()
    history = service.list_history(db, users[0], ticket_id, PageQuery())
    assert history.total == 2 and {item.event for item in history.items} == {"created", "snapshot"}
    assert next(item for item in history.items if item.event == "snapshot").actor is None
    assert next(item for item in history.items if item.event == "created").actor.id == users[0].id


def test_service_audit_failure_rolls_back_assignment(details_domain):
    db, users, ticket_id = details_domain
    engine = db.get_bind()

    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO ticket_assignment_history"):
            raise OperationalError("audit", {}, Exception("simulated failure"))

    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(OperationalError):
            service.assign_ticket(
                db,
                users[2],
                ticket_id,
                AssignmentUpdate(
                    assignee_id=users[2].id,
                    expected_assignment_version=0,
                ),
            )
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    ticket = service.get_ticket(db, users[2], ticket_id)
    assert ticket.assignee_id is None and ticket.assignment_version == 0
    assert db.scalar(select(func.count()).select_from(TicketAssignmentHistory)) == 0


def test_service_error_translation_and_openapi_contract(details_domain):
    db, users, ticket_id = details_domain
    for action, status in (
        (lambda: service.get_ticket(db, users[0], 999), 404),
        (
            lambda: service.assign_ticket(
                db,
                users[2],
                ticket_id,
                AssignmentUpdate(
                    assignee_id=users[0].id,
                    expected_assignment_version=0,
                ),
            ),
            422,
        ),
        (
            lambda: service.assign_ticket(
                db,
                users[2],
                ticket_id,
                AssignmentUpdate(
                    assignee_id=None,
                    expected_assignment_version=99,
                ),
            ),
            409,
        ),
    ):
        with pytest.raises(HTTPException) as error:
            ticket_action(action)
        assert error.value.status_code == status
    paths = create_app().openapi()["paths"]
    assert "get" in paths["/api/tickets/{ticket_id}"]
    assert {"get", "post"} <= paths["/api/tickets/{ticket_id}/comments"].keys()
    assert "patch" in paths["/api/tickets/{ticket_id}/assignee"]
