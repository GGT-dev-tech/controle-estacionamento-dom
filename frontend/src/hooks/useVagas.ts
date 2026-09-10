import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listarVagas } from '@/api/vagas'
import { registrarEntrada, registrarSaida } from '@/api/movimentacoes'
import type { EntradaPayload } from '@/api/types'

export function useVagas(andar: string) {
  return useQuery({
    queryKey: ['vagas', andar],
    queryFn: () => listarVagas(andar),
  })
}

export function useOcuparVaga() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: EntradaPayload) => registrarEntrada(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vagas'] })
    },
  })
}

export function useLiberarVaga() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vagaId: string) => registrarSaida(vagaId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vagas'] })
    },
  })
}
