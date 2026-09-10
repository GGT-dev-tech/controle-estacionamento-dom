import { apiClient } from './client'

/** Baixa um arquivo autenticado (o link `<a href>` puro não carrega o JWT). */
export async function baixarArquivo(url: string, nomeArquivo: string, params?: Record<string, unknown>): Promise<void> {
  const response = await apiClient.get(url, { responseType: 'blob', params })
  const blobUrl = window.URL.createObjectURL(response.data as Blob)
  const link = document.createElement('a')
  link.href = blobUrl
  link.download = nomeArquivo
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(blobUrl)
}
