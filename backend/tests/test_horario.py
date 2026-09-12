"""horario_br: conversão de datetime naive-UTC (como tudo é salvo no banco) para o
horário de Brasília usado em mensagens (WhatsApp, e-mail) voltadas ao usuário final."""

from datetime import datetime

from app.services.horario import horario_br


def test_horario_br_converte_utc_para_brt_3_horas_atras():
    # 18:00 UTC == 15:00 em Brasília (UTC-3, sem horário de verão).
    utc = datetime(2026, 1, 15, 18, 0, 0)
    br = horario_br(utc)
    assert (br.hour, br.minute) == (15, 0)


def test_horario_br_formata_com_strftime_direto():
    utc = datetime(2026, 3, 10, 2, 30, 0)  # 02:30 UTC == 23:30 do dia anterior em BRT
    assert f"{horario_br(utc):%d/%m %H:%M}" == "09/03 23:30"


def test_horario_br_aceita_datetime_ja_com_tzinfo():
    from datetime import timezone

    aware = datetime(2026, 1, 15, 18, 0, 0, tzinfo=timezone.utc)
    br = horario_br(aware)
    assert (br.hour, br.minute) == (15, 0)
