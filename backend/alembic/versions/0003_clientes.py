"""clientes cadastrados (bot WhatsApp)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # O tipo "tipo_cliente" já existe no PostgreSQL (criado pela migration 0001 para a
    # tabela ocupantes). sa.Enum(..., create_type=False) genérico NÃO é suficiente para
    # suprimir o CREATE TYPE nesse caminho de op.create_table quando esta migration roda
    # sozinha (banco já em 0002) — só "funcionava" em teste local porque 0001/0002/0003
    # rodavam juntas na mesma conexão. A classe postgresql.ENUM (dialect-specific, só
    # usada aqui na migration — o modelo ORM continua com sa.Enum genérico) respeita
    # create_type de verdade. No MySQL isso não importa: enum é inline por coluna, sem
    # tipo nomeado compartilhado, então o branch abaixo nunca entra em jogo lá.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        tipo_cliente = postgresql.ENUM(
            "mensalista", "rotativo", "visitante", "prestador", name="tipo_cliente", create_type=False
        )
    else:
        tipo_cliente = sa.Enum("mensalista", "rotativo", "visitante", "prestador", name="tipo_cliente")

    op.create_table(
        "clientes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("telefone", sa.String(20), nullable=False),
        sa.Column("tipo_cliente", tipo_cliente, nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_clientes_telefone", "clientes", ["telefone"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_clientes_telefone", table_name="clientes")
    op.drop_table("clientes")
