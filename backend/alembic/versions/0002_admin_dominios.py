"""domínios autorizados e e-mails admin

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dominios_autorizados",
        sa.Column("dominio", sa.String(255), primary_key=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "admin_emails",
        sa.Column("email", sa.String(255), primary_key=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("admin_emails")
    op.drop_table("dominios_autorizados")
