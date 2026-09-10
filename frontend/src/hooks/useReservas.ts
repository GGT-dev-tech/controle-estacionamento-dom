import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { cancelarReserva, criarReserva, listarReservas } from '@/api/reservas'
import type { ReservaPayload } from '@/api/types'

export function useReservas() {
  return useQuery({
    queryKey: ['reservas'],
    queryFn: listarReservas,
  })
}

export function useCriarReserva() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ReservaPayload) => criarReserva(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reservas'] })
      queryClient.invalidateQueries({ queryKey: ['vagas'] })
    },
  })
}

export function useCancelarReserva() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (reservaId: number) => cancelarReserva(reservaId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reservas'] })
      queryClient.invalidateQueries({ queryKey: ['vagas'] })
    },
  })
}
