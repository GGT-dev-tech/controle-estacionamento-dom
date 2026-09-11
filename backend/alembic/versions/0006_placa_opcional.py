"""placa do veiculo passa a ser opcional

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("veiculos", "placa", existing_type=sa.String(length=10), nullable=True)


def downgrade() -> None:
    op.alter_column("veiculos", "placa", existing_type=sa.String(length=10), nullable=False)
