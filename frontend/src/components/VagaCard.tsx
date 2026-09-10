import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { EntradaModal } from '@/components/EntradaModal'
import { useLiberarVaga } from '@/hooks/useVagas'
import type { Vaga } from '@/api/types'
import { cn } from '@/lib/utils'

const STATUS_LABEL: Record<Vaga['status'], string> = {
  livre: 'Livre',
  ocupada: 'Ocupada',
  reservada: 'Reservada',
  manutencao: 'Manutenção',
}

export function VagaCard({ vaga }: { vaga: Vaga }) {
  const [modalAberto, setModalAberto] = useState(false)
  const liberar = useLiberarVaga()

  return (
    <div
      className={cn(
        'flex flex-col gap-3 rounded-lg border border-border bg-card p-4 text-card-foreground',
        !vaga.ativo && 'opacity-50',
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-lg font-semibold">{vaga.id}</p>
          {vaga.posicao && <p className="text-xs text-muted-foreground">{vaga.posicao}</p>}
        </div>
        <Badge variant={vaga.status}>{STATUS_LABEL[vaga.status]}</Badge>
      </div>

      {vaga.ocupante && (
        <div className="text-sm">
          <p className="font-medium">{vaga.ocupante.nome}</p>
          <p className="text-muted-foreground">
            {vaga.ocupante.veiculo} • {vaga.ocupante.placa}
          </p>
        </div>
      )}

      {vaga.reserva_ativa && !vaga.ocupante && (
        <div className="text-sm">
          <p className="font-medium">Reservada para {vaga.reserva_ativa.nome}</p>
          <p className="text-muted-foreground">
            {new Date(vaga.reserva_ativa.inicio).toLocaleString('pt-BR')}
          </p>
        </div>
      )}

      <div className="mt-auto pt-1">
        {vaga.status === 'ocupada' ? (
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            disabled={liberar.isPending}
            onClick={() => liberar.mutate(vaga.id)}
          >
            {liberar.isPending ? 'Liberando…' : 'Liberar vaga'}
          </Button>
        ) : vaga.status === 'manutencao' ? (
          <p className="text-center text-xs text-muted-foreground">Indisponível</p>
        ) : (
          <Button size="sm" className="w-full" onClick={() => setModalAberto(true)}>
            Ocupar vaga
          </Button>
        )}
      </div>

      <EntradaModal vagaId={vaga.id} open={modalAberto} onOpenChange={setModalAberto} />
    </div>
  )
}
