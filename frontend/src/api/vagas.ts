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
