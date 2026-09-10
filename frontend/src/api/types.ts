export type StatusVaga = 'livre' | 'ocupada' | 'reservada' | 'manutencao'

export type TipoCliente = 'mensalista' | 'rotativo' | 'visitante' | 'prestador'

export interface Ocupante {
  id: number
  vaga_id: string
  nome: string
  placa: string
  veiculo: string
  tipo_cliente: TipoCliente
  observacoes: string | null
  hora_entrada: string
  operador_id: string
}

export interface Reserva {
  id: number
  vaga_id: string
  nome: string
  telefone: string | null
  email: string | null
  placa: string | null
  inicio: string
  fim: string
  status: string
  canal: string
  criado_em: string
}

export interface Vaga {
  id: string
  numero: string
  andar: string
  posicao: string | null
  tipo: string
  status: StatusVaga
  ativo: boolean
  criado_em: string
  ocupante: Ocupante | null
  reserva_ativa: Reserva | null
}

export interface Movimentacao {
  id: number
  vaga_id: string
  tipo: 'entrada' | 'saida'
  placa: string
  motorista: string
  veiculo: string
  timestamp: string
  operador_id: string
  tempo_permanencia_min: number | null
  sincronizado: boolean
}

export interface EntradaPayload {
  vaga_id: string
  nome: string
  placa: string
  veiculo: string
  tipo_cliente: TipoCliente
  observacoes?: string
}

export interface ReservaPayload {
  vaga_id: string
  nome: string
  telefone?: string
  email?: string
  placa?: string
  inicio: string
  fim: string
}
