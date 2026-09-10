import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { listarVagas } from '@/api/vagas'
import { registrarEntrada, registrarSaida } from '@/api/movimentacoes'
import type { EntradaPayload, Vaga } from '@/api/types'
import { db, patchVagaNoCacheOffline } from '@/offline/db'
import { executarOuEnfileirar, isEnfileirada } from '@/offline/executarOuEnfileirar'

export function useVagas(andar: string) {
  const chaveCache = andar || 'todas'

  return useQuery({
    queryKey: ['vagas', andar],
    queryFn: async () => {
      try {
        const vagas = await listarVagas(andar)
        await db.vagasCache.put({ andar: chaveCache, vagas, atualizadoEm: new Date().toISOString() })
        return vagas
      } catch (error) {
        const cache = await db.vagasCache.get(chaveCache)
        if (cache) return cache.vagas
        throw error
      }
    },
  })
}

async function aplicarPatchOtimista(queryClient: QueryClient, vagaId: string, patch: Partial<Vaga>) {
  queryClient.setQueriesData<Vaga[]>({ queryKey: ['vagas'] }, (old) =>
    old?.map((v) => (v.id === vagaId ? { ...v, ...patch } : v)),
  )
  await patchVagaNoCacheOffline(vagaId, patch)
}

export function useOcuparVaga() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: EntradaPayload) =>
      executarOuEnfileirar(() => registrarEntrada(payload), {
        tipo: 'entrada',
        vagaId: payload.vaga_id,
        payload: { ...payload },
      }),
    onSuccess: async (resultado, payload) => {
      if (isEnfileirada(resultado)) {
        await aplicarPatchOtimista(queryClient, payload.vaga_id, {
          status: 'ocupada',
          ocupante: {
            id: -1,
            vaga_id: payload.vaga_id,
            nome: payload.nome,
            placa: payload.placa.toUpperCase(),
            veiculo: payload.veiculo,
            tipo_cliente: payload.tipo_cliente,
            observacoes: payload.observacoes ?? null,
            hora_entrada: new Date().toISOString(),
            operador_id: 'offline',
          },
        })
      } else {
        queryClient.invalidateQueries({ queryKey: ['vagas'] })
      }
    },
  })
}

export function useLiberarVaga() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vagaId: string) =>
      executarOuEnfileirar(() => registrarSaida(vagaId), {
        tipo: 'saida',
        vagaId,
        payload: { vaga_id: vagaId },
      }),
    onSuccess: async (resultado, vagaId) => {
      if (isEnfileirada(resultado)) {
        await aplicarPatchOtimista(queryClient, vagaId, { status: 'livre', ocupante: null })
      } else {
        queryClient.invalidateQueries({ queryKey: ['vagas'] })
      }
    },
  })
}
