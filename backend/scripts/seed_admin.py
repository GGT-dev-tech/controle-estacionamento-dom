"""Cadastra o primeiro domínio autorizado e/ou e-mail admin.

Necessário uma única vez após o primeiro deploy: sem isso, ninguém consegue logar
(o domínio não está autorizado) nem administrar o painel /admin (chicken-and-egg).
A partir daí, novos domínios/admins podem ser geridos pelo próprio painel.

Uso:
    python -m scripts.seed_admin --dominio dompagamentos.com --admin gustavo.tavares@dompagamentos.com
"""

import argparse
import asyncio

from app.database import SessionLocal
from app.models.admin_email import AdminEmail
from app.models.dominio_autorizado import DominioAutorizado


async def seed(dominio: str | None, admin_email: str | None) -> None:
    async with SessionLocal() as db:
        if dominio:
            dominio = dominio.strip().lower()
            if not await db.get(DominioAutorizado, dominio):
                db.add(DominioAutorizado(dominio=dominio))
                print(f"Domínio '{dominio}' cadastrado.")
            else:
                print(f"Domínio '{dominio}' já existia.")

        if admin_email:
            admin_email = admin_email.strip().lower()
            if not await db.get(AdminEmail, admin_email):
                db.add(AdminEmail(email=admin_email))
                print(f"Admin '{admin_email}' cadastrado.")
            else:
                print(f"Admin '{admin_email}' já existia.")

        await db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dominio", help="Domínio de e-mail a autorizar (ex.: dompagamentos.com)")
    parser.add_argument("--admin", dest="admin_email", help="E-mail que deve ter papel de admin")
    args = parser.parse_args()

    if not args.dominio and not args.admin_email:
        parser.error("informe --dominio e/ou --admin")

    asyncio.run(seed(args.dominio, args.admin_email))


if __name__ == "__main__":
    main()
