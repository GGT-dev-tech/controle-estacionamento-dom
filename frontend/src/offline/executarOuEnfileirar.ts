import axios from 'axios'
import { enfileirarOperacao } from './sync'
import type { TipoOperacao } from './db'

export interface Enfileirada {
  enfileirada: true
}

export function isEnfileirada<T>(resultado: T | Enfileirada): resultado is Enfileirada {
  return typeof resultado === 'object' && resultado !== null && 'enfileirada' in resultado
}

/**
 * Executa a chamada à API; se estiver offline ou a chamada falhar por falta de rede,
 * grava a operação na fila local (Dexie) para sincronização posterior.
 */
export async function executarOuEnfileirar<T>(
  chamada: () => Promise<T>,
  operacao: { tipo: TipoOperacao; vagaId: string; payload: Record<string, unknown> },
): Promise<T | Enfileirada> {
  if (!navigator.onLine) {
    await enfileirarOperacao(operacao)
    return { enfileirada: true }
  }

  try {
    return await chamada()
  } catch (error) {
    if (axios.isAxiosError(error) && !error.response) {
      await enfileirarOperacao(operacao)
      return { enfileirada: true }
    }
    throw error
  }
}
