"""clientes cadastrados (bot WhatsApp)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "clientes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("telefone", sa.String(20), nullable=False),
        sa.Column(
            "tipo_cliente",
            # create_type=False: o tipo "tipo_cliente" já foi criado pela migration 0001
            # (tabela ocupantes) — recriá-lo aqui quebraria no PostgreSQL.
            sa.Enum("mensalista", "rotativo", "visitante", "prestador", name="tipo_cliente", create_type=False),
            nullable=False,
        ),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_clientes_telefone", "clientes", ["telefone"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_clientes_telefone", table_name="clientes")
    op.drop_table("clientes")
