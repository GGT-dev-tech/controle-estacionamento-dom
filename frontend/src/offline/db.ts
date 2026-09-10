import Dexie, { type Table } from 'dexie'
import type { Vaga } from '@/api/types'

export type TipoOperacao = 'entrada' | 'saida' | 'reserva' | 'cancelamento'

export interface OperacaoPendente {
  id?: number
  tipo: TipoOperacao
  vagaId: string
  payload: Record<string, unknown>
  timestamp: string
  tentativas: number
  sincronizado: boolean
  erro?: string
}

export interface VagasCacheEntry {
  andar: string
  vagas: Vaga[]
  atualizadoEm: string
}

export class EstacionamentoDB extends Dexie {
  operacoes!: Table<OperacaoPendente, number>
  vagasCache!: Table<VagasCacheEntry, string>

  constructor() {
    super('EstacionamentoDOM')
    this.version(1).stores({
      operacoes: '++id, sincronizado, vagaId',
      vagasCache: 'andar',
    })
  }
}

export const db = new EstacionamentoDB()

/**
 * Aplica um patch otimista a uma vaga em todas as entradas de cache (por andar).
 * Mantém o cache offline consistente com operações ainda não sincronizadas,
 * para que uma vaga ocupada/reservada offline continue aparecendo assim após um reload.
 */
export async function patchVagaNoCacheOffline(vagaId: string, patch: Partial<Vaga>): Promise<void> {
  const entradas = await db.vagasCache.toArray()
  for (const entrada of entradas) {
    const indice = entrada.vagas.findIndex((v) => v.id === vagaId)
    if (indice === -1) continue
    const vagas = [...entrada.vagas]
    vagas[indice] = { ...vagas[indice], ...patch }
    await db.vagasCache.put({ ...entrada, vagas })
  }
}
