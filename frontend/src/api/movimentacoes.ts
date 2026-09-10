import { apiClient } from './client'
import type { EntradaPayload, Movimentacao } from './types'

export async function registrarEntrada(payload: EntradaPayload): Promise<Movimentacao> {
  const { data } = await apiClient.post<Movimentacao>('/movimentacoes/entrada', payload)
  return data
}

export async function registrarSaida(vagaId: string): Promise<Movimentacao> {
  const { data } = await apiClient.post<Movimentacao>('/movimentacoes/saida', { vaga_id: vagaId })
  return data
}

export async function listarMovimentacoes(vagaId?: string): Promise<Movimentacao[]> {
  const { data } = await apiClient.get<Movimentacao[]>('/movimentacoes', {
    params: vagaId ? { vaga_id: vagaId } : undefined,
  })
  return data
}
