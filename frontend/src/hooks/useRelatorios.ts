import { useQuery } from '@tanstack/react-query'
import { obterHistorico, obterRelatorioDiario } from '@/api/relatorios'

export function useRelatorioDiario() {
  return useQuery({ queryKey: ['relatorio-diario'], queryFn: obterRelatorioDiario })
}

export function useHistorico(dias: number) {
  return useQuery({ queryKey: ['relatorio-historico', dias], queryFn: () => obterHistorico(dias) })
}
