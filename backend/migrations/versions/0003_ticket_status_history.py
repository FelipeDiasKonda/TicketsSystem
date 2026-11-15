"""Track ticket status changes and snapshot existing ticket state."""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def status_enum(name):
    return sa.Enum(
        "open",
        "in_progress",
        "resolved",
        "closed",
        name=name,
        native_enum=False,
        create_constraint=True,
    )


def upgrade():
    history = op.create_table(
        "ticket_status_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ticket_id",
            sa.Integer(),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("previous_status", status_enum("history_previous_status"), nullable=True),
        sa.Column("new_status", status_enum("history_new_status"), nullable=False),
        sa.Column(
            "changed_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.Column(
            "event",
            sa.Enum(
                "created",
                "transition",
                "snapshot",
                name="history_event",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_ticket_history_ticket_time", "ticket_status_history", ["ticket_id", "changed_at", "id"]
    )
    tickets = sa.table("tickets", sa.column("id", sa.Integer()), sa.column("status", sa.String()))
    op.execute(
        history.insert().from_select(
            ["ticket_id", "previous_status", "new_status", "changed_by_id", "changed_at", "event"],
            sa.select(
                tickets.c.id,
                sa.null(),
                tickets.c.status,
                sa.null(),
                sa.literal(datetime.now(UTC).replace(tzinfo=None)),
                sa.literal("snapshot"),
            ),
        )
    )


def downgrade():
    op.drop_table("ticket_status_history")
