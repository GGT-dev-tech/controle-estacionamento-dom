import { apiClient } from './client'
import type { Reserva, ReservaPayload } from './types'

export async function listarReservas(): Promise<Reserva[]> {
  const { data } = await apiClient.get<Reserva[]>('/reservas')
  return data
}

export async function criarReserva(payload: ReservaPayload): Promise<Reserva> {
  const { data } = await apiClient.post<Reserva>('/reservas', payload)
  return data
}

export async function cancelarReserva(reservaId: number): Promise<Reserva> {
  const { data } = await apiClient.post<Reserva>(`/reservas/${reservaId}/cancelar`)
  return data
}
