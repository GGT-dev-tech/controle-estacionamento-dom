import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select } from '@/components/ui/select'
import { EntradaModal } from '@/components/EntradaModal'
import { SwipeToConfirm } from '@/components/SwipeToConfirm'
import { useLiberarVaga, useOcuparVaga } from '@/hooks/useVagas'
import { useMeuCadastro } from '@/hooks/useCliente'
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
  const [erro, setErro] = useState<string | null>(null)
  const [veiculoEscolhidoId, setVeiculoEscolhidoId] = useState<number | null>(null)
  const { data: cadastro } = useMeuCadastro()
  const ocupar = useOcuparVaga()
  const liberar = useLiberarVaga()

  const veiculos = cadastro?.veiculos ?? []
  const veiculoAtivo = veiculos.find((v) => v.id === veiculoEscolhidoId) ?? veiculos[0]

  // Ocupar/liberar por swipe só faz sentido pra quem já tem cadastro + veículo — sem
  // isso, não tem como preencher nome/placa sozinho, e o formulário completo continua
  // sendo o caminho (ex.: registrando a entrada de um visitante sem conta).
  const podeUsarSwipeParaOcupar =
    (vaga.status === 'livre' || vaga.status === 'reservada') && !!cadastro && veiculos.length > 0

  async function handleConfirmarOcupar() {
    if (!cadastro || !veiculoAtivo) return
    setErro(null)
    try {
      await ocupar.mutateAsync({
        vaga_id: vaga.id,
        nome: cadastro.nome,
        placa: veiculoAtivo.placa,
        veiculo: veiculoAtivo.veiculo,
        tipo_cliente: cadastro.tipo_cliente,
      })
    } catch (err) {
      setErro('Não foi possível ocupar a vaga. Tente novamente.')
      throw err
    }
  }

  async function handleConfirmarLiberar() {
    setErro(null)
    try {
      await liberar.mutateAsync(vaga.id)
    } catch (err) {
      setErro('Não foi possível liberar a vaga. Tente novamente.')
      throw err
    }
  }

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

      {erro && <p className="text-xs text-destructive">{erro}</p>}

      <div className="mt-auto space-y-2 pt-1">
        {vaga.status === 'ocupada' ? (
          cadastro ? (
            <SwipeToConfirm
              label="Deslize para liberar"
              confirmingLabel="Liberando…"
              onConfirm={handleConfirmarLiberar}
            />
          ) : (
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              disabled={liberar.isPending}
              onClick={() => liberar.mutate(vaga.id)}
            >
              {liberar.isPending ? 'Liberando…' : 'Liberar vaga'}
            </Button>
          )
        ) : vaga.status === 'manutencao' ? (
          <p className="text-center text-xs text-muted-foreground">Indisponível</p>
        ) : podeUsarSwipeParaOcupar ? (
          <>
            {veiculos.length > 1 && (
              <Select
                value={veiculoAtivo?.id}
                onChange={(event) => setVeiculoEscolhidoId(Number(event.target.value))}
              >
                {veiculos.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.placa} — {v.veiculo}
                  </option>
                ))}
              </Select>
            )}
            <SwipeToConfirm
              label={`Deslize para ocupar${veiculoAtivo ? ` (${veiculoAtivo.placa})` : ''}`}
              confirmingLabel="Ocupando…"
              onConfirm={handleConfirmarOcupar}
            />
            <button
              type="button"
              onClick={() => setModalAberto(true)}
              className="w-full text-center text-xs text-muted-foreground hover:text-foreground"
            >
              Registrar para outra pessoa
            </button>
          </>
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
