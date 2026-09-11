"""Reenvia a mensagem de onboarding (boas-vindas) por WhatsApp pra clientes já cadastrados.

Útil pra verificar quais números realmente recebem mensagem. Confirmado na prática: os
números cadastrados existem de verdade no WhatsApp (checado via /chat/whatsappNumbers),
mas mandar vários seguidos sem pausa faz alguns falharem com 400 — rate limiting do
WhatsApp/Evolution API pra envios em rajada, não um problema com o número em si (o mesmo
número que falhou em lote enviou normalmente quando tentado sozinho logo em seguida).
Por isso este script espera --intervalo segundos entre cada envio e tenta de novo uma vez
(com uma espera maior) se a primeira tentativa falhar.

O resultado impresso é o que enviar_mensagem() de fato conseguiu fazer: OK = a Evolution
API aceitou o envio; FALHOU = não aceitou mesmo depois da nova tentativa (o motivo aparece
no log de erro logo acima, via logger.exception em app/services/whatsapp.py).

Uso (rodar com `railway ssh --service backend -- ...` ou `railway run --service backend ...`):
    python -m scripts.enviar_onboarding --telefone 48984569143
    python -m scripts.enviar_onboarding --id 6
    python -m scripts.enviar_onboarding --todos                  # só lista, não envia
    python -m scripts.enviar_onboarding --todos --confirmar       # envia de verdade pra todos
    python -m scripts.enviar_onboarding --todos --confirmar --intervalo 5
"""

import argparse
import asyncio
import logging

from sqlalchemy import select

from app.database import SessionLocal
from app.models.cliente import Cliente
from app.services.whatsapp import enviar_mensagem, normalizar_telefone

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

INTERVALO_PADRAO_SEGUNDOS = 3.0
ESPERA_ANTES_DE_TENTAR_DE_NOVO_SEGUNDOS = 5.0


def _mensagem(nome: str) -> str:
    return (
        f"👋 Olá {nome}! Você está cadastrado(a) no sistema do Dom Estacionamento. "
        "Seu número já está autorizado.\n\n"
        "Envie */ajuda* aqui no WhatsApp a qualquer momento para ver os comandos disponíveis."
    )


async def _obter_clientes(db, telefone: str | None, cliente_id: int | None, todos: bool) -> list[Cliente]:
    if todos:
        return list((await db.execute(select(Cliente).where(Cliente.ativo.is_(True)))).scalars().all())
    if cliente_id is not None:
        cliente = await db.get(Cliente, cliente_id)
        return [cliente] if cliente else []
    telefone_norm = normalizar_telefone(telefone or "")
    cliente = (await db.execute(select(Cliente).where(Cliente.telefone == telefone_norm))).scalar_one_or_none()
    return [cliente] if cliente else []


async def _enviar_com_retentativa(cliente: Cliente) -> bool:
    if await enviar_mensagem(cliente.telefone, _mensagem(cliente.nome)):
        return True
    # O mesmo número que falha em lote costuma funcionar sozinho (rate limiting, não o
    # número em si) — uma segunda tentativa, com uma pausa maior, resolve na maioria dos casos.
    await asyncio.sleep(ESPERA_ANTES_DE_TENTAR_DE_NOVO_SEGUNDOS)
    return await enviar_mensagem(cliente.telefone, _mensagem(cliente.nome))


async def executar(
    telefone: str | None, cliente_id: int | None, todos: bool, confirmar: bool, intervalo: float
) -> None:
    async with SessionLocal() as db:
        clientes = await _obter_clientes(db, telefone, cliente_id, todos)

    if not clientes:
        print("Nenhum cliente encontrado com esse critério.")
        return

    if todos and not confirmar:
        print(f"{len(clientes)} cliente(s) ativo(s) — nada foi enviado (modo listagem, sem --confirmar):\n")
        for cliente in clientes:
            print(f"  id={cliente.id} nome={cliente.nome!r} telefone={cliente.telefone}")
        print("\nRode de novo com --confirmar para enviar de verdade pra todos.")
        return

    print(f"Enviando onboarding pra {len(clientes)} cliente(s)...\n")
    for i, cliente in enumerate(clientes):
        if i > 0:
            await asyncio.sleep(intervalo)
        ok = await _enviar_com_retentativa(cliente)
        status = "OK" if ok else "FALHOU"
        print(f"[{status}] id={cliente.id} nome={cliente.nome!r} telefone={cliente.telefone}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--telefone", help="Telefone do cliente (com ou sem DDD/país — ex.: 48984569143)")
    grupo.add_argument("--id", dest="cliente_id", type=int, help="ID do cliente (tabela clientes)")
    grupo.add_argument("--todos", action="store_true", help="Todos os clientes ativos (por padrão só lista)")
    parser.add_argument(
        "--confirmar", action="store_true", help="Envia de verdade quando usado junto de --todos"
    )
    parser.add_argument(
        "--intervalo",
        type=float,
        default=INTERVALO_PADRAO_SEGUNDOS,
        help=f"Segundos de espera entre cada envio (padrão: {INTERVALO_PADRAO_SEGUNDOS})",
    )
    args = parser.parse_args()

    asyncio.run(executar(args.telefone, args.cliente_id, args.todos, args.confirmar, args.intervalo))


if __name__ == "__main__":
    main()
