from datetime import datetime, timedelta

from sqlalchemy import select


async def _criar_vaga(client, vaga_id):
    resp = await client.post("/vagas", json={"id": vaga_id, "numero": vaga_id.split("-")[1], "andar": "G2"})
    assert resp.status_code == 201


async def test_ciclo_do_scheduler_expira_e_lembra_reservas_num_unico_passo(
    client_as_admin, db_session, monkeypatch
):
    """Exercita o loop in-process (scheduler._executar_ciclo) que substitui os Cron Jobs
    externos do Railway — mesma lógica de expirar_reservas_vencidas/
    lembrar_reservas_proximas_do_vencimento, só chamada direto em vez de via HTTP+cron secret."""
    from app.models.reserva import Reserva
    from app.models.vaga import StatusVaga, Vaga
    from app.services import notificacoes, scheduler

    # scheduler.SessionLocal aponta pro banco real por padrão — redireciona pro sqlite
    # in-memory do db_session (mesmo padrão de app.dependency_overrides[get_db], mas pro
    # módulo que abre sessão direto, sem passar por uma rota).
    monkeypatch.setattr(scheduler, "SessionLocal", db_session)

    enviados = []

    async def _fake_enviar(telefone, texto):
        enviados.append((telefone, texto))
        return True

    async def _fake_definir_estado(telefone, estado):
        return None

    monkeypatch.setattr(notificacoes, "enviar_mensagem", _fake_enviar)
    monkeypatch.setattr(notificacoes, "definir_estado", _fake_definir_estado)

    await _criar_vaga(client_as_admin, "G2-90")
    await _criar_vaga(client_as_admin, "G2-91")

    async with db_session() as session:
        vaga_vencida = await session.get(Vaga, "G2-90")
        vaga_vencida.status = StatusVaga.reservada
        vaga_proxima = await session.get(Vaga, "G2-91")
        vaga_proxima.status = StatusVaga.reservada
        session.add(
            Reserva(
                vaga_id="G2-90",
                nome="Cliente Vencido",
                telefone="11911112222",
                inicio=datetime.utcnow() - timedelta(hours=3),
                fim=datetime.utcnow() - timedelta(hours=1),
                status="ativa",
                canal="webapp",
                criado_em=datetime.utcnow() - timedelta(hours=3),
            )
        )
        session.add(
            Reserva(
                vaga_id="G2-91",
                nome="Cliente Próximo",
                telefone="11933334444",
                inicio=datetime.utcnow() - timedelta(minutes=50),
                fim=datetime.utcnow() + timedelta(minutes=5),
                status="ativa",
                canal="webapp",
                criado_em=datetime.utcnow() - timedelta(minutes=50),
            )
        )
        await session.commit()

    await scheduler._executar_ciclo()

    vaga_vencida_depois = (await client_as_admin.get("/vagas/G2-90")).json()
    assert vaga_vencida_depois["status"] == "livre"

    async with db_session() as session:
        proxima = (
            await session.execute(select(Reserva).where(Reserva.vaga_id == "G2-91"))
        ).scalar_one()
        assert proxima.lembrete_enviado is True

    telefones_avisados = {telefone for telefone, _ in enviados}
    assert "11911112222" in telefones_avisados  # expiração
    assert "11933334444" in telefones_avisados  # lembrete
