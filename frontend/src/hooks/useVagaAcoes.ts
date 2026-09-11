import { useState } from 'react'
import { useLiberarVaga, useOcuparVaga } from '@/hooks/useVagas'
import { useCancelarReserva, useCriarReserva } from '@/hooks/useReservas'
import { useMeuCadastro } from '@/hooks/useCliente'
import { mensagemDeErro } from '@/lib/utils'
import type { Vaga } from '@/api/types'

export const PRAZOS_RESERVA = [
  { minutos: 15, label: '15 min' },
  { minutos: 30, label: '30 min' },
  { minutos: 60, label: '1h' },
]

export type Acao = 'inicial' | 'escolhendo' | 'prazo'

/**
 * Lógica de ações de uma vaga (ocupar/liberar/reservar/cancelar), compartilhada entre a
 * visão em card (gesto de deslizar) e a visão em lista (botões) — cada uma decide só como
 * renderizar, o estado e as chamadas de API vivem aqui.
 */
export function useVagaAcoes(vaga: Vaga) {
  const [erro, setErro] = useState<string | null>(null)
  const [acao, setAcao] = useState<Acao>('inicial')
  const [veiculoEscolhidoId, setVeiculoEscolhidoId] = useState<number | null>(null)
  const { data: cadastro } = useMeuCadastro()
  const ocupar = useOcuparVaga()
  const liberar = useLiberarVaga()
  const criarReserva = useCriarReserva()
  const cancelarReserva = useCancelarReserva()

  const veiculos = cadastro?.veiculos ?? []
  const veiculoAtivo = veiculos.find((v) => v.id === veiculoEscolhidoId) ?? veiculos[0]

  // A reserva é minha? Só assim faz sentido oferecer "confirmar chegada" direto —
  // reserva de outra pessoa continua só como informação (ocupar fisicamente ainda é
  // possível, mas passa pela escolha normal, não por um atalho "é sua vaga").
  const reservaEhMinha = !!(vaga.reserva_ativa && cadastro && vaga.reserva_ativa.telefone === cadastro.telefone)

  // Ação rápida (swipe ou clique direto) só faz sentido pra quem já tem cadastro + veículo —
  // sem isso não dá pra preencher nome/placa sozinho, e o formulário completo (EntradaModal)
  // continua sendo o caminho (ex.: registrando a entrada de um visitante sem conta).
  const podeAgir = (vaga.status === 'livre' || vaga.status === 'reservada') && !!cadastro && veiculos.length > 0

  function resetar() {
    setAcao('inicial')
    setVeiculoEscolhidoId(null)
  }

  async function handleConfirmarOcupar() {
    if (!cadastro || !veiculoAtivo) return
    setErro(null)
    if (!veiculoAtivo.placa) {
      setErro('Esse veículo não tem placa cadastrada — adicione uma em Meu Cadastro para poder ocupar a vaga.')
      return
    }
    try {
      await ocupar.mutateAsync({
        vaga_id: vaga.id,
        nome: cadastro.nome,
        placa: veiculoAtivo.placa,
        veiculo: veiculoAtivo.veiculo,
        tipo_cliente: cadastro.tipo_cliente,
      })
    } catch (err) {
      setErro(mensagemDeErro(err, 'Não foi possível ocupar a vaga. Tente novamente.'))
      throw err
    } finally {
      resetar()
    }
  }

  async function handleConfirmarLiberar() {
    setErro(null)
    try {
      await liberar.mutateAsync(vaga.id)
    } catch (err) {
      setErro(mensagemDeErro(err, 'Não foi possível liberar a vaga. Tente novamente.'))
      throw err
    }
  }

  async function handleCancelarReserva() {
    if (!vaga.reserva_ativa) return
    setErro(null)
    try {
      await cancelarReserva.mutateAsync({ reservaId: vaga.reserva_ativa.id, vagaId: vaga.id })
    } catch (err) {
      setErro(mensagemDeErro(err, 'Não foi possível cancelar a reserva. Tente novamente.'))
    }
  }

  async function handleReservarPrazo(minutos: number) {
    if (!cadastro || !veiculoAtivo) return
    setErro(null)
    const inicio = new Date()
    const fim = new Date(inicio.getTime() + minutos * 60_000)
    try {
      await criarReserva.mutateAsync({
        vaga_id: vaga.id,
        nome: cadastro.nome,
        telefone: cadastro.telefone,
        email: cadastro.email ?? undefined,
        placa: veiculoAtivo.placa ?? undefined,
        inicio: inicio.toISOString(),
        fim: fim.toISOString(),
      })
    } catch (err) {
      setErro(mensagemDeErro(err, 'Não foi possível reservar a vaga. Tente novamente.'))
    } finally {
      resetar()
    }
  }

  return {
    erro,
    acao,
    setAcao,
    veiculoEscolhidoId,
    setVeiculoEscolhidoId,
    cadastro,
    veiculos,
    veiculoAtivo,
    reservaEhMinha,
    podeAgir,
    ocupar,
    liberar,
    criarReserva,
    cancelarReserva,
    resetar,
    handleConfirmarOcupar,
    handleConfirmarLiberar,
    handleCancelarReserva,
    handleReservarPrazo,
  }
}
