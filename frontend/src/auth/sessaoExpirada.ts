import { create } from 'zustand'

interface SessaoExpiradaState {
  expirada: boolean
  returnTo: string
  marcarExpirada: (returnTo: string) => void
}

export const useSessaoExpiradaStore = create<SessaoExpiradaState>((set) => ({
  expirada: false,
  returnTo: '/',
  marcarExpirada: (returnTo) => set({ expirada: true, returnTo }),
}))

let jaDisparado = false

/**
 * Chamado de qualquer lugar (interceptor do axios, WebSocket) quando a sessão do Auth0
 * expirou — comum depois de muitas horas com a aba/PWA em background, quando o refresh
 * token silencioso falha. Antes disso, a falha ficava muda: a requisição simplesmente
 * não tinha Authorization (axios) ou o socket não conectava, e a tela parecia travada.
 *
 * `jaDisparado` evita disparar o redirecionamento mais de uma vez quando várias
 * requisições falham ao mesmo tempo (comum: várias queries do React Query expiram
 * juntas) — sem isso, cada uma chamaria loginWithRedirect por conta própria.
 */
export function dispararSessaoExpirada() {
  if (jaDisparado) return
  jaDisparado = true
  const returnTo = `${window.location.pathname}${window.location.search}`
  useSessaoExpiradaStore.getState().marcarExpirada(returnTo)
}
