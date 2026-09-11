import asyncio
import json
import logging

from fastapi import WebSocket
from redis import RedisError

from app.services.redis_cache import get_redis

logger = logging.getLogger(__name__)

VAGAS_CHANNEL = "vagas:atualizacoes"


class ConnectionManager:
    """Fan-out local (só entre conexões WebSocket abertas NESTE processo). Com o backend
    rodando com múltiplos workers (gunicorn), cada processo tem sua própria instância —
    por isso notificar_vaga_atualizada não chama isso diretamente, publica no Redis
    (escutar_atualizacoes_de_vaga é quem repassa pra cá)."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, message: dict) -> None:
        stale: list[WebSocket] = []
        for connection in self._connections:
            try:
                await connection.send_json(message)
            except Exception:
                stale.append(connection)
        for connection in stale:
            self.disconnect(connection)


manager = ConnectionManager()


async def notificar_vaga_atualizada(vaga_id: str, status: str) -> None:
    """Publica no Redis em vez de broadcastar só localmente: com múltiplos workers
    (gunicorn), cada processo mantém sua própria lista de conexões WebSocket em memória —
    sem isso, só clientes conectados ao MESMO worker que processou a mudança eram
    avisados; os demais (a maioria, espalhados pelos outros workers) ficavam vendo o
    status antigo indefinidamente, mesmo a vaga já tendo mudado de dono.
    """
    mensagem = {"type": "vaga_atualizada", "vaga_id": vaga_id, "status": status}
    try:
        await get_redis().publish(VAGAS_CHANNEL, json.dumps(mensagem))
    except RedisError:
        logger.warning(
            "Redis indisponível ao publicar atualização de vaga — clientes conectados a "
            "outros workers não serão avisados agora; broadcastando só localmente."
        )
        await manager.broadcast(mensagem)


async def escutar_atualizacoes_de_vaga() -> None:
    """Roda em cada worker (disparado no lifespan do FastAPI): assina o canal do Redis e
    repassa cada mensagem publicada por QUALQUER worker pros clientes WebSocket conectados
    neste processo — é isso que fecha o loop entre os workers."""
    while True:
        try:
            pubsub = get_redis().pubsub()
            await pubsub.subscribe(VAGAS_CHANNEL)
            async for mensagem in pubsub.listen():
                if mensagem["type"] != "message":
                    continue
                try:
                    dados = json.loads(mensagem["data"])
                except (TypeError, ValueError):
                    logger.warning("Mensagem inválida no canal %s: %r", VAGAS_CHANNEL, mensagem["data"])
                    continue
                await manager.broadcast(dados)
        except Exception:
            logger.exception("Erro escutando atualizações de vaga via Redis — tentando de novo em 5s.")
            await asyncio.sleep(5)
