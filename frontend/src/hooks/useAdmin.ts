import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  adicionarAdmin,
  adicionarClienteAdmin,
  adicionarDominio,
  listarAdmins,
  listarAuditLogs,
  listarClientesAdmin,
  listarDominios,
  removerAdmin,
  removerClienteAdmin,
  removerDominio,
} from '@/api/admin'

export function useDominios() {
  return useQuery({ queryKey: ['admin-dominios'], queryFn: listarDominios })
}

export function useAdicionarDominio() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: adicionarDominio,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-dominios'] }),
  })
}

export function useRemoverDominio() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: removerDominio,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-dominios'] }),
  })
}

export function useAdmins() {
  return useQuery({ queryKey: ['admin-admins'], queryFn: listarAdmins })
}

export function useAdicionarAdmin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: adicionarAdmin,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-admins'] }),
  })
}

export function useRemoverAdmin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: removerAdmin,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-admins'] }),
  })
}

export function useAuditLogs() {
  return useQuery({ queryKey: ['admin-audit-logs'], queryFn: () => listarAuditLogs(100) })
}

export function useClientesAdmin() {
  return useQuery({ queryKey: ['admin-clientes'], queryFn: listarClientesAdmin })
}

export function useAdicionarClienteAdmin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: adicionarClienteAdmin,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-clientes'] }),
  })
}

export function useRemoverClienteAdmin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: removerClienteAdmin,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-clientes'] }),
  })
}
