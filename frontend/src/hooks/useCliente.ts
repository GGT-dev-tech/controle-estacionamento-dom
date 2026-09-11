import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  adicionarVeiculo,
  atualizarMeuCadastro,
  criarMeuCadastro,
  obterMeuCadastro,
  removerVeiculo,
  type MeuCadastroPayload,
} from '@/api/clientes'

/** 404 é esperado (sinal de "primeiro acesso") — por isso sem retry automático. */
export function useMeuCadastro() {
  return useQuery({
    queryKey: ['meu-cadastro'],
    queryFn: obterMeuCadastro,
    retry: false,
  })
}

export function useCriarMeuCadastro() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: criarMeuCadastro,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['meu-cadastro'] }),
  })
}

export function useAtualizarMeuCadastro() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: Partial<MeuCadastroPayload>) => atualizarMeuCadastro(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['meu-cadastro'] }),
  })
}

export function useAdicionarVeiculo() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: adicionarVeiculo,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['meu-cadastro'] }),
  })
}

export function useRemoverVeiculo() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: removerVeiculo,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['meu-cadastro'] }),
  })
}
