import axios from 'axios'

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
    const token = await getToken()
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
