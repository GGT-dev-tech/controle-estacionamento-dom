import { apiClient } from './client'

export interface RelatorioDiario {
  data: string
  total_vagas: number
  livres: number
  ocupadas: number
  reservadas: number
  manutencao: number
  entradas_hoje: number
  saidas_hoje: number
  tempo_medio_permanencia_min: number | null
}

export interface HistoricoDia {
  data: string
  entradas: number
  saidas: number
  tempo_medio_permanencia_min: number | null
}

export async function obterRelatorioDiario(): Promise<RelatorioDiario> {
  const { data } = await apiClient.get<RelatorioDiario>('/relatorios/diario')
  return data
}

export async function obterHistorico(dias: number): Promise<HistoricoDia[]> {
  const { data } = await apiClient.get<HistoricoDia[]>('/relatorios/historico', { params: { dias } })
  return data
}
