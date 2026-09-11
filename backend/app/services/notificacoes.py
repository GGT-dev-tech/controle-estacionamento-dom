from app.models.reserva import Reserva
from app.services.email import enviar_cancelamento_reserva, enviar_confirmacao_reserva
from app.services.whatsapp import enviar_mensagem
from app.services.whatsapp_estado import definir_estado


def _reserva_para_dict(reserva: Reserva) -> dict:
    return {
        "nome": reserva.nome,
        "vaga_id": reserva.vaga_id,
        "inicio": reserva.inicio,
        "fim": reserva.fim,
        "placa": reserva.placa,
        "email": reserva.email,
    }


async def notificar_reserva_criada(reserva: Reserva) -> None:
    """Notifica o cliente sobre a reserva. Pulado para o canal 'whatsapp', que já confirma inline."""
    if reserva.canal != "webapp":
        return
    if reserva.email:
        await enviar_confirmacao_reserva(_reserva_para_dict(reserva))
    if reserva.telefone:
        await enviar_mensagem(
            reserva.telefone, f"✅ Reserva confirmada — vaga {reserva.vaga_id}, até {reserva.fim:%d/%m %H:%M}."
        )


async def notificar_reserva_cancelada(reserva: Reserva) -> None:
    if reserva.canal != "webapp":
        return
    if reserva.email:
        await enviar_cancelamento_reserva(_reserva_para_dict(reserva))
    if reserva.telefone:
        await enviar_mensagem(reserva.telefone, f"❌ Reserva da vaga {reserva.vaga_id} foi cancelada.")


async def notificar_reserva_sobreposta(reserva: Reserva) -> None:
    """A reserva foi cancelada porque a vaga foi ocupada fisicamente por um veículo diferente
    do que reservou (prioridade para quem chegou no local). Sempre notifica, independente do
    canal de origem — é justamente o cliente que perdeu a vaga que precisa saber."""
    mensagem = (
        f"⚠️ Sua reserva da vaga {reserva.vaga_id} foi cancelada, pois ela foi ocupada "
        "presencialmente por prioridade. Por favor, faça uma nova reserva para outra vaga."
    )
    if reserva.telefone:
        await enviar_mensagem(reserva.telefone, mensagem)
    if reserva.email:
        await enviar_cancelamento_reserva(_reserva_para_dict(reserva))


async def notificar_reserva_proxima_do_vencimento(reserva: Reserva) -> None:
    """O prazo da reserva está próximo (services.sync.lembrar_reservas_proximas_do_vencimento)
    e ninguém ocupou a vaga ainda — pergunta via WhatsApp se a pessoa ainda vem. Uma resposta
    afirmativa estende o prazo (services/whatsapp.py); sem resposta, a expiração automática
    (notificar_reserva_expirada) segue seu curso normalmente. Sem telefone, não há o que fazer."""
    if not reserva.telefone:
        return
    await enviar_mensagem(
        reserva.telefone,
        f"⏰ Sua reserva da vaga {reserva.vaga_id} vence às {reserva.fim:%H:%M}. Ainda vem? "
        "Responda *sim* para garantir mais um tempo. Sem resposta, a vaga é liberada normalmente "
        "no vencimento.",
    )
    await definir_estado(reserva.telefone, {"step": "confirmando_reserva", "reserva_id": reserva.id})


async def notificar_reserva_expirada(reserva: Reserva) -> None:
    """Reserva venceu sem que ninguém ocupasse a vaga — sempre notifica, independente do canal de origem."""
    if reserva.telefone:
        await enviar_mensagem(
            reserva.telefone, f"⌛ Sua reserva da vaga {reserva.vaga_id} expirou e a vaga foi liberada."
        )
    if reserva.email:
        await enviar_cancelamento_reserva(_reserva_para_dict(reserva))
