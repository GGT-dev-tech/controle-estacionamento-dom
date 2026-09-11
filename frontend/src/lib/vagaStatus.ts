import type { Vaga } from '@/api/types'

export const STATUS_LABEL: Record<Vaga['status'], string> = {
  livre: 'Livre',
  ocupada: 'Ocupada',
  reservada: 'Reservada',
  manutencao: 'Manutenção',
}

export const STATUS_RING: Record<Vaga['status'], string> = {
  livre: 'ring-1 ring-vaga-livre/30',
  ocupada: 'ring-1 ring-vaga-ocupada/30',
  reservada: 'ring-1 ring-vaga-reservada/30',
  manutencao: '',
}

export const STATUS_DOT: Record<Vaga['status'], string> = {
  livre: 'bg-vaga-livre shadow-glow-livre',
  ocupada: 'bg-vaga-ocupada shadow-glow-ocupada',
  reservada: 'bg-vaga-reservada shadow-glow-reservada',
  manutencao: 'bg-vaga-manutencao',
}
