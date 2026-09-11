import asyncio

from app.services import ws_manager


class _FakeWebSocket:
    def __init__(self) -> None:
        self.recebidas: list[dict] = []

    async def accept(self) -> None:
        return None

    async def send_json(self, mensagem: dict) -> None:
        self.recebidas.append(mensagem)


async def test_notificar_vaga_atualizada_publica_no_redis_e_chega_pelo_listener(monkeypatch):
    """Reproduz o bug real: com múltiplos workers (gunicorn), cada processo tem seu
    próprio ConnectionManager em memória — sem publicar/escutar via Redis, um cliente
    conectado a um worker diferente do que processou a mudança nunca via a atualização
    (a vaga continuava aparecendo livre pra ele). Confirma que notificar_vaga_atualizada
    publica no canal e que escutar_atualizacoes_de_vaga entrega pro WebSocket local."""
    import fakeredis.aioredis

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(ws_manager, "get_redis", lambda: fake)

    websocket = _FakeWebSocket()
    await ws_manager.manager.connect(websocket)

    tarefa = asyncio.create_task(ws_manager.escutar_atualizacoes_de_vaga())
    try:
        # Dá tempo do subscribe() do listener rodar antes de publicar — senão a
        # publicação pode acontecer antes de haver alguém ouvindo o canal.
        await asyncio.sleep(0.1)

        await ws_manager.notificar_vaga_atualizada("G2-1", "ocupada")

        for _ in range(50):
            if websocket.recebidas:
                break
            await asyncio.sleep(0.05)

        assert {"type": "vaga_atualizada", "vaga_id": "G2-1", "status": "ocupada"} in websocket.recebidas
    finally:
        tarefa.cancel()
        ws_manager.manager.disconnect(websocket)
