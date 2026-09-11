import { apiClient } from './client'
import type { Vaga } from './types'

export async function listarVagas(andar?: string): Promise<Vaga[]> {
  const { data } = await apiClient.get<Vaga[]>('/vagas', { params: andar ? { andar } : undefined })
  return data
}

export async function obterVaga(vagaId: string): Promise<Vaga> {
  const { data } = await apiClient.get<Vaga>(`/vagas/${vagaId}`)
  return data
}

export async function criarVaga(payload: { id: string; numero: string; andar: string; posicao: string; tipo: 'padrao' | 'presa' }): Promise<Vaga> {
  const { data } = await apiClient.post<Vaga>('/vagas', payload)
  return data
}

export async function excluirVaga(vagaId: string): Promise<void> {
  await apiClient.delete(`/vagas/${vagaId}`)
}

export async function atualizarVaga({ id, payload }: { id: string; payload: Partial<{ numero: string; andar: string; posicao: string; tipo: 'padrao' | 'presa' }> }): Promise<Vaga> {
  const { data } = await apiClient.patch<Vaga>(`/vagas/${id}`, payload)
  return data
}
