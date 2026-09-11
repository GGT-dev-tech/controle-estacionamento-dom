"""cadastro unificado: email/auth0_sub em clientes + tabela veiculos

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clientes", sa.Column("email", sa.String(100), nullable=True))
    op.add_column("clientes", sa.Column("auth0_sub", sa.String(200), nullable=True))
    op.create_index("ix_clientes_auth0_sub", "clientes", ["auth0_sub"], unique=True)

    op.create_table(
        "veiculos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes.id"), nullable=False),
        sa.Column("placa", sa.String(10), nullable=False),
        sa.Column("veiculo", sa.String(100), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_veiculos_placa", "veiculos", ["placa"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_veiculos_placa", table_name="veiculos")
    op.drop_table("veiculos")
    op.drop_index("ix_clientes_auth0_sub", table_name="clientes")
    op.drop_column("clientes", "auth0_sub")
    op.drop_column("clientes", "email")
