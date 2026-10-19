"""add roles, invitations, and ingredient images

Revision ID: 7c4a1f3e9b20
Revises: 409698d56b7b
Create Date: 2026-10-19 17:52:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "7c4a1f3e9b20"
down_revision = "409698d56b7b"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("role", sa.String(length=20), nullable=False, server_default="admin")
        )

    with op.batch_alter_table("ingredients") as batch_op:
        batch_op.add_column(sa.Column("image_filename", sa.String(length=100), nullable=True))

    op.create_table(
        "user_invitations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    with op.batch_alter_table("user_invitations") as batch_op:
        batch_op.create_index("ix_user_invitations_workspace_id", ["workspace_id"])


def downgrade():
    with op.batch_alter_table("user_invitations") as batch_op:
        batch_op.drop_index("ix_user_invitations_workspace_id")
    op.drop_table("user_invitations")
    with op.batch_alter_table("ingredients") as batch_op:
        batch_op.drop_column("image_filename")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("role")
