"""Testa o enviar_mensagem de verdade (não mockado) — todos os outros testes do bot
substituem essa função por um fake que só grava as chamadas, então nenhum deles pegaria
um bug na montagem do número de destino em si (como o "55" duplicado corrigido aqui)."""

import pytest

from app.services import whatsapp


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None


class _FakeAsyncClient:
    chamadas: list[dict] = []
    falhas_restantes = 0  # quantas próximas chamadas devem levantar erro antes de suceder

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *args) -> bool:
        return False

    async def post(self, url, json, headers):
        _FakeAsyncClient.chamadas.append(json)
        if _FakeAsyncClient.falhas_restantes > 0:
            _FakeAsyncClient.falhas_restantes -= 1
            raise RuntimeError("Falha simulada (rate limiting)")
        return _FakeResponse()


@pytest.fixture(autouse=True)
def _fake_http(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "evolution_api_url", "https://evolution.example.com")
    _FakeAsyncClient.chamadas = []
    _FakeAsyncClient.falhas_restantes = 0
    monkeypatch.setattr(whatsapp.httpx, "AsyncClient", _FakeAsyncClient)
    # Sem isso, o teste de retentativa esperaria os 3s reais entre tentativas.
    monkeypatch.setattr(whatsapp.asyncio, "sleep", lambda *_args, **_kwargs: _sem_espera())


async def _sem_espera() -> None:
    return None


async def test_enviar_mensagem_nao_duplica_55_quando_telefone_ja_vem_com_pais():
    # Telefone cru do webhook (remoteJid sem o sufixo) já vem com "55" — bug corrigido:
    # enviar_mensagem prepend outro "55" por cima, gerando "5555..." (número inválido).
    await whatsapp.enviar_mensagem("5511999998888", "oi")
    assert _FakeAsyncClient.chamadas[-1]["number"] == "5511999998888@s.whatsapp.net"


async def test_enviar_mensagem_adiciona_55_quando_telefone_vem_do_cadastro():
    # Telefone como vem do cadastro/reserva (sem código do país).
    await whatsapp.enviar_mensagem("11999998888", "oi")
    assert _FakeAsyncClient.chamadas[-1]["number"] == "5511999998888@s.whatsapp.net"


async def test_enviar_mensagem_normaliza_nono_digito_ausente():
    # remoteJid real capturado em produção: 55 + DDD + 8 dígitos (sem o 9).
    await whatsapp.enviar_mensagem("554791190758", "oi")
    assert _FakeAsyncClient.chamadas[-1]["number"] == "5547991190758@s.whatsapp.net"


async def test_enviar_mensagem_tenta_de_novo_apos_falha_e_da_certo(monkeypatch):
    # Confirmado em produção: o mesmo número que falha (rate limiting em rajada) costuma
    # funcionar numa segunda tentativa logo em seguida.
    _FakeAsyncClient.falhas_restantes = 1
    ok = await whatsapp.enviar_mensagem("11999998888", "oi")
    assert ok is True
    assert len(_FakeAsyncClient.chamadas) == 2


async def test_enviar_mensagem_desiste_apos_2_falhas():
    _FakeAsyncClient.falhas_restantes = 2
    ok = await whatsapp.enviar_mensagem("11999998888", "oi")
    assert ok is False
    assert len(_FakeAsyncClient.chamadas) == 2
