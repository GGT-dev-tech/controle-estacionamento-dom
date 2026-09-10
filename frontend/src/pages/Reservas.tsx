import { Layout } from '@/components/Layout'
import { ReservaForm } from '@/components/ReservaForm'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useCancelarReserva, useReservas } from '@/hooks/useReservas'

const STATUS_VARIANT: Record<string, 'livre' | 'reservada' | 'neutro'> = {
  ativa: 'reservada',
  concluida: 'livre',
  cancelada: 'neutro',
}

export default function Reservas() {
  const { data: reservas, isLoading } = useReservas()
  const cancelar = useCancelarReserva()

  return (
    <Layout>
      <div className="space-y-6">
        <ReservaForm />

        <div>
          <h2 className="mb-3 text-sm font-semibold">Reservas</h2>
          {isLoading && <p className="text-sm text-muted-foreground">Carregando…</p>}

          <div className="space-y-2">
            {reservas?.map((reserva) => (
              <div
                key={reserva.id}
                className="flex items-center justify-between rounded-lg border border-border bg-card p-3"
              >
                <div>
                  <p className="text-sm font-medium">
                    {reserva.vaga_id} — {reserva.nome}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(reserva.inicio).toLocaleString('pt-BR')} até{' '}
                    {new Date(reserva.fim).toLocaleString('pt-BR')}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <Badge variant={STATUS_VARIANT[reserva.status] ?? 'neutro'}>{reserva.status}</Badge>
                  {reserva.status === 'ativa' && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={cancelar.isPending}
                      onClick={() => cancelar.mutate(reserva.id)}
                    >
                      Cancelar
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Layout>
  )
}
