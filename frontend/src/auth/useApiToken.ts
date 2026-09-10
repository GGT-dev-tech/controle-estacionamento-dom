import { useAuth0 } from '@auth0/auth0-react'
import { useEffect } from 'react'
import { setTokenGetter } from '@/api/client'

/** Conecta o getter de token do Auth0 ao interceptor do Axios. Chamar uma vez perto da raiz do app. */
export function useApiToken() {
  const { getAccessTokenSilently } = useAuth0()

  useEffect(() => {
    setTokenGetter(() => getAccessTokenSilently())
  }, [getAccessTokenSilently])
}
