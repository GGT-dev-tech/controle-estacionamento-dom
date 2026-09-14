import { useAuth0 } from '@auth0/auth0-react'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { dispararSessaoExpirada } from '@/auth/sessaoExpirada'

function wsUrl(path: string): string {
  const apiUrl = new URL(import.meta.env.VITE_API_URL)
  apiUrl.protocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:'
  apiUrl.pathname = path
  return apiUrl.toString()
}

/** Assina atualizações em tempo real de vagas via WebSocket e invalida o cache do React Query. */
export function useVagasSocket() {
  const { getAccessTokenSilently, isAuthenticated } = useAuth0()
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!isAuthenticated) return

    let socket: WebSocket | null = null
    let cancelled = false

    async function conectar() {
      let token: string
      try {
        token = await getAccessTokenSilently()
      } catch (error) {
        // Mesmo caso do axios (api/client.ts): sessão expirada depois de muito tempo em
        // background. Sem isso, o socket simplesmente não conectava e nada avisava o
        // usuário — a lista de vagas parava de atualizar em tempo real, em silêncio.
        dispararSessaoExpirada()
        return
      }
      if (cancelled) return

      socket = new WebSocket(wsUrl('/ws/vagas') + `?token=${encodeURIComponent(token)}`)
      socket.onmessage = () => {
        queryClient.invalidateQueries({ queryKey: ['vagas'] })
      }
    }

    conectar()

    return () => {
      cancelled = true
      socket?.close()
    }
  }, [isAuthenticated, getAccessTokenSilently, queryClient])
}
