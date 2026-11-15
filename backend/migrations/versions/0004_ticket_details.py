"""Ticket assignment, comments and assignment audit trail."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tickets") as batch:
        batch.add_column(sa.Column("assignee_id", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("assignment_version", sa.Integer(), nullable=False, server_default="0")
        )
        batch.create_foreign_key(
            "fk_tickets_assignee", "users", ["assignee_id"], ["id"], ondelete="RESTRICT"
        )
    op.create_table(
        "ticket_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ticket_id",
            sa.Integer(),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_ticket_comments_ticket_time", "ticket_comments", ["ticket_id", "created_at", "id"]
    )
    op.create_table(
        "ticket_assignment_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ticket_id",
            sa.Integer(),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "previous_assignee_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "new_assignee_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "changed_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_ticket_assignment_ticket_time",
        "ticket_assignment_history",
        ["ticket_id", "changed_at", "id"],
    )


def downgrade():
    op.drop_table("ticket_assignment_history")
    op.drop_table("ticket_comments")
    with op.batch_alter_table("tickets") as batch:
        batch.drop_constraint("fk_tickets_assignee", type_="foreignkey")
        batch.drop_column("assignee_id")
        batch.drop_column("assignment_version")
