import { apiClient } from './client'

export interface DominioAutorizado {
  dominio: string
  ativo: boolean
  criado_em: string
}

export interface AdminEmailEntry {
  email: string
  criado_em: string
}

export interface AuditLogEntry {
  id: number
  usuario_id: string
  acao: string
  recurso: string
  recurso_id: string | null
  ip: string | null
  timestamp: string
  detalhes: string | null
}

export async function listarDominios(): Promise<DominioAutorizado[]> {
  const { data } = await apiClient.get<DominioAutorizado[]>('/admin/dominios')
  return data
}

export async function adicionarDominio(dominio: string): Promise<DominioAutorizado> {
  const { data } = await apiClient.post<DominioAutorizado>('/admin/dominios', { dominio })
  return data
}

export async function removerDominio(dominio: string): Promise<void> {
  await apiClient.delete(`/admin/dominios/${encodeURIComponent(dominio)}`)
}

export async function listarAdmins(): Promise<AdminEmailEntry[]> {
  const { data } = await apiClient.get<AdminEmailEntry[]>('/admin/admins')
  return data
}

export async function adicionarAdmin(email: string): Promise<AdminEmailEntry> {
  const { data } = await apiClient.post<AdminEmailEntry>('/admin/admins', { email })
  return data
}

export async function removerAdmin(email: string): Promise<void> {
  await apiClient.delete(`/admin/admins/${encodeURIComponent(email)}`)
}

export async function listarAuditLogs(limite: number): Promise<AuditLogEntry[]> {
  const { data } = await apiClient.get<AuditLogEntry[]>('/admin/audit-logs', { params: { limite } })
  return data
}
