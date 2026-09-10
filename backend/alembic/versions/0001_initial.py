"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vagas",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("numero", sa.String(10), nullable=False),
        sa.Column("andar", sa.String(5), nullable=False),
        sa.Column("posicao", sa.String(50), nullable=True),
        sa.Column("tipo", sa.String(20), nullable=False, server_default="normal"),
        sa.Column(
            "status",
            sa.Enum("livre", "ocupada", "reservada", "manutencao", name="status_vaga"),
            nullable=False,
            server_default="livre",
        ),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "ocupantes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vaga_id", sa.String(20), sa.ForeignKey("vagas.id"), nullable=False),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("placa", sa.String(10), nullable=False),
        sa.Column("veiculo", sa.String(100), nullable=False),
        sa.Column(
            "tipo_cliente",
            sa.Enum("mensalista", "rotativo", "visitante", "prestador", name="tipo_cliente"),
            nullable=False,
        ),
        sa.Column("hora_entrada", sa.DateTime(), nullable=False),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("operador_id", sa.String(200), nullable=False),
    )

    op.create_table(
        "reservas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vaga_id", sa.String(20), sa.ForeignKey("vagas.id"), nullable=False),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("telefone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(100), nullable=True),
        sa.Column("placa", sa.String(10), nullable=True),
        sa.Column("inicio", sa.DateTime(), nullable=False),
        sa.Column("fim", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ativa"),
        sa.Column("canal", sa.String(20), nullable=False, server_default="webapp"),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "movimentacoes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vaga_id", sa.String(20), sa.ForeignKey("vagas.id"), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("placa", sa.String(10), nullable=False),
        sa.Column("motorista", sa.String(100), nullable=False),
        sa.Column("veiculo", sa.String(100), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("operador_id", sa.String(200), nullable=False),
        sa.Column("tempo_permanencia_min", sa.Integer(), nullable=True),
        sa.Column("sincronizado", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("usuario_id", sa.String(200), nullable=False),
        sa.Column("acao", sa.String(100), nullable=False),
        sa.Column("recurso", sa.String(50), nullable=False),
        sa.Column("recurso_id", sa.String(50), nullable=True),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("detalhes", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("movimentacoes")
    op.drop_table("reservas")
    op.drop_table("ocupantes")
    op.drop_table("vagas")
    sa.Enum(name="tipo_cliente").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="status_vaga").drop(op.get_bind(), checkfirst=True)
