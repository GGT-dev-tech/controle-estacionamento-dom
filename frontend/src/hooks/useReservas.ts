import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { cancelarReserva, criarReserva, listarReservas } from '@/api/reservas'
import type { ReservaPayload, Vaga } from '@/api/types'
import { patchVagaNoCacheOffline } from '@/offline/db'
import { executarOuEnfileirar, isEnfileirada } from '@/offline/executarOuEnfileirar'

export function useReservas() {
  return useQuery({
    queryKey: ['reservas'],
    queryFn: listarReservas,
  })
}

async function aplicarPatchOtimista(queryClient: QueryClient, vagaId: string, patch: Partial<Vaga>) {
  queryClient.setQueriesData<Vaga[]>({ queryKey: ['vagas'] }, (old) =>
    old?.map((v) => (v.id === vagaId ? { ...v, ...patch } : v)),
  )
  await patchVagaNoCacheOffline(vagaId, patch)
}

export function useCriarReserva() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ReservaPayload) =>
      executarOuEnfileirar(() => criarReserva(payload), {
        tipo: 'reserva',
        vagaId: payload.vaga_id,
        payload: { ...payload },
      }),
    onSuccess: async (resultado, payload) => {
      queryClient.invalidateQueries({ queryKey: ['reservas'] })
      if (isEnfileirada(resultado)) {
        await aplicarPatchOtimista(queryClient, payload.vaga_id, {
          status: 'reservada',
          reserva_ativa: {
            id: -1,
            vaga_id: payload.vaga_id,
            nome: payload.nome,
            telefone: payload.telefone ?? null,
            email: payload.email ?? null,
            placa: payload.placa ?? null,
            inicio: payload.inicio,
            fim: payload.fim,
            status: 'ativa',
            canal: 'webapp',
            criado_em: new Date().toISOString(),
          },
        })
      } else {
        queryClient.invalidateQueries({ queryKey: ['vagas'] })
      }
    },
  })
}

export function useCancelarReserva() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ reservaId, vagaId }: { reservaId: number; vagaId: string }) =>
      executarOuEnfileirar(() => cancelarReserva(reservaId), {
        tipo: 'cancelamento',
        vagaId,
        payload: { reserva_id: reservaId },
      }),
    onSuccess: async (resultado, { vagaId }) => {
      queryClient.invalidateQueries({ queryKey: ['reservas'] })
      if (isEnfileirada(resultado)) {
        await aplicarPatchOtimista(queryClient, vagaId, { status: 'livre', reserva_ativa: null })
      } else {
        queryClient.invalidateQueries({ queryKey: ['vagas'] })
      }
    },
  })
}
