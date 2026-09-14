import { useAuth0 } from '@auth0/auth0-react'
import { useEffect } from 'react'
import { useSessaoExpiradaStore } from '@/auth/sessaoExpirada'

const ATRASO_ANTES_DO_REDIRECT_MS = 1200

/**
 * Chamar uma vez perto da raiz do app (ao lado de useApiToken). Observa o estado
 * global marcado por dispararSessaoExpirada() e manda pro login de novo, preservando a
 * rota atual via appState.returnTo (Auth0ProviderWithHistory já sabe navegar de volta
 * pra ela). O atraso é só pra dar tempo do toast aparecer antes do redirect.
 */
export function useTratarSessaoExpirada() {
  const { loginWithRedirect } = useAuth0()
  const expirada = useSessaoExpiradaStore((s) => s.expirada)
  const returnTo = useSessaoExpiradaStore((s) => s.returnTo)

  useEffect(() => {
    if (!expirada) return
    const timer = setTimeout(() => {
      loginWithRedirect({ appState: { returnTo } })
    }, ATRASO_ANTES_DO_REDIRECT_MS)
    return () => clearTimeout(timer)
  }, [expirada, returnTo, loginWithRedirect])
}
