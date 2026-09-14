import axios from 'axios'
import { dispararSessaoExpirada } from '@/auth/sessaoExpirada'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
})

type TokenGetter = () => Promise<string>
let getToken: TokenGetter | null = null

export function setTokenGetter(fn: TokenGetter) {
  getToken = fn
}

apiClient.interceptors.request.use(async (config) => {
  if (getToken) {
    try {
      const token = await getToken()
      config.headers.Authorization = `Bearer ${token}`
    } catch (error) {
      // getAccessTokenSilently rejeita (login_required, missing_refresh_token, etc.)
      // quando a sessão expirou — comum depois de muitas horas com a aba/PWA em
      // background. Sem isso, a requisição seguia sem Authorization e falhava em
      // silêncio (401 seco), deixando a tela parecendo travada.
      dispararSessaoExpirada()
      throw error
    }
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      dispararSessaoExpirada()
    }
    return Promise.reject(error)
  },
)
