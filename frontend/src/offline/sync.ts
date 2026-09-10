import { apiClient } from '@/api/client'
import { queryClient } from '@/lib/queryClient'
import { db, type TipoOperacao } from './db'

interface ResultadoOperacaoServidor {
  id: number
  sucesso: boolean
  mensagem?: string | null
}

export async function enfileirarOperacao(op: {
  tipo: TipoOperacao
  vagaId: string
  payload: Record<string, unknown>
}): Promise<number> {
  return db.operacoes.add({
    ...op,
    timestamp: new Date().toISOString(),
    tentativas: 0,
    sincronizado: false,
  })
}

let sincronizando = false

/** Envia a fila de operações pendentes ao backend em lote. Uma falha em um item não afeta os demais. */
export async function sincronizarPendentes(): Promise<void> {
  if (sincronizando) return
  sincronizando = true

  try {
    const pendentes = await db.operacoes.toArray()
    if (pendentes.length === 0) return

    const operacoes = pendentes.map((op) => ({ id: op.id!, tipo: op.tipo, payload: op.payload }))

    const { data } = await apiClient.post<{ resultados: ResultadoOperacaoServidor[] }>('/movimentacoes/sync', {
      operacoes,
    })

    for (const resultado of data.resultados) {
      if (resultado.sucesso) {
        await db.operacoes.delete(resultado.id)
      } else {
        const op = pendentes.find((p) => p.id === resultado.id)
        if (op?.id != null) {
          await db.operacoes.update(op.id, {
            tentativas: op.tentativas + 1,
            erro: resultado.mensagem ?? 'Falha ao sincronizar.',
          })
        }
      }
    }

    queryClient.invalidateQueries({ queryKey: ['vagas'] })
    queryClient.invalidateQueries({ queryKey: ['reservas'] })
  } catch {
    // Ainda offline ou erro de rede — a próxima tentativa ocorre no evento 'online' ou manualmente.
  } finally {
    sincronizando = false
  }
}

/** Registra o listener de reconexão e tenta uma sincronização inicial. Retorna a função de limpeza. */
export function iniciarSincronizacaoAutomatica(): () => void {
  const handler = () => void sincronizarPendentes()
  window.addEventListener('online', handler)
  if (navigator.onLine) void sincronizarPendentes()
  return () => window.removeEventListener('online', handler)
}
