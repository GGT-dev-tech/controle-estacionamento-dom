import { useAuth0 } from '@auth0/auth0-react'

const ROLE_CLAIM = 'https://estacionamento.dom/role'

export function useIsAdmin(): boolean {
  const { user } = useAuth0()
  return user?.[ROLE_CLAIM] === 'admin'
}
