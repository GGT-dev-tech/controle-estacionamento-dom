import { apiClient } from './client'

export interface Veiculo {
  id: number
  placa: string
  veiculo: string
  criado_em: string
}

export interface MeuCadastro {
  id: number
  nome: string
  telefone: string
  email: string | null
  tipo_cliente: string
  ativo: boolean
  criado_em: string
  veiculos: Veiculo[]
}

export interface MeuCadastroPayload {
  nome: string
  telefone: string
  email?: string
}

export async function obterMeuCadastro(): Promise<MeuCadastro> {
  const { data } = await apiClient.get<MeuCadastro>('/clientes/me')
  return data
}

export async function criarMeuCadastro(payload: MeuCadastroPayload): Promise<MeuCadastro> {
  const { data } = await apiClient.post<MeuCadastro>('/clientes/me', payload)
  return data
}

export async function atualizarMeuCadastro(payload: Partial<MeuCadastroPayload>): Promise<MeuCadastro> {
  const { data } = await apiClient.patch<MeuCadastro>('/clientes/me', payload)
  return data
}

export async function adicionarVeiculo(payload: { placa: string; veiculo: string }): Promise<Veiculo> {
  const { data } = await apiClient.post<Veiculo>('/clientes/me/veiculos', payload)
  return data
}

export async function removerVeiculo(veiculoId: number): Promise<void> {
  await apiClient.delete(`/clientes/me/veiculos/${veiculoId}`)
}
