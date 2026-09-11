import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select } from '@/components/ui/select'
import { EntradaModal } from '@/components/EntradaModal'
import { SwipeToConfirm } from '@/components/SwipeToConfirm'
import { useIsAdmin } from '@/auth/useIsAdmin'
import { PRAZOS_RESERVA, useVagaAcoes } from '@/hooks/useVagaAcoes'
import { STATUS_DOT, STATUS_LABEL, STATUS_RING } from '@/lib/vagaStatus'
import { useOnboardingPulado } from '@/stores/useOnboardingPulado'
import type { Vaga } from '@/api/types'
import { cn } from '@/lib/utils'

export function VagaCard({ vaga }: { vaga: Vaga }) {
  const [modalAberto, setModalAberto] = useState(false)
  const isAdmin = useIsAdmin()
  const { definirPulado } = useOnboardingPulado()
  const {
    erro,
    acao,
    setAcao,
    setVeiculoEscolhidoId,
    cadastro,
    veiculos,
    veiculoAtivo,
    reservaEhMinha,
    podeAgir,
    ocupar,
    criarReserva,
    cancelarReserva,
    resetar,
    handleConfirmarOcupar,
    handleConfirmarLiberar,
    handleCancelarReserva,
    handleReservarPrazo,
  } = useVagaAcoes(vaga)

  return (
    <div
      className={cn(
        'flex flex-col gap-3 rounded-lg border border-white/10 bg-card/40 backdrop-blur-xl shadow-glass p-4 text-card-foreground transition-shadow',
        STATUS_RING[vaga.status],
        !vaga.ativo && 'opacity-50',
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-1.5">
            <span
              className={cn(
                'h-2 w-2 shrink-0 rounded-full',
                STATUS_DOT[vaga.status],
                vaga.status !== 'manutencao' && 'animate-pulse',
              )}
            />
            <p className="font-mono text-lg font-semibold tabular-nums">{vaga.id}</p>
            <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] font-medium text-secondary-foreground">
              {vaga.andar}
            </span>
          </div>
          {vaga.posicao && <p className="text-xs text-muted-foreground">{vaga.posicao}</p>}
        </div>
        <Badge variant={vaga.status}>{STATUS_LABEL[vaga.status]}</Badge>
      </div>

      {vaga.ocupante && (
        <div className="text-sm">
          <p className="font-medium">{vaga.ocupante.nome}</p>
          <p className="text-muted-foreground">
            {vaga.ocupante.veiculo} • <span className="font-mono tabular-nums">{vaga.ocupante.placa}</span>
          </p>
        </div>
      )}

      {vaga.reserva_ativa && !vaga.ocupante && (
        <div className="text-sm">
          <p className="font-medium">
            {reservaEhMinha ? 'Reservada por você' : `Reservada para ${vaga.reserva_ativa.nome}`}
          </p>
          <p className="text-muted-foreground">
            até{' '}
            <span className="font-mono tabular-nums">
              {new Date(vaga.reserva_ativa.fim).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
            </span>
          </p>
        </div>
      )}

      {erro && <p className="text-xs text-destructive">{erro}</p>}

      <div className="mt-auto space-y-2 pt-1">
        {vaga.status === 'ocupada' ? (
          <SwipeToConfirm
            label="Deslize para liberar"
            confirmingLabel="Liberando…"
            onConfirm={handleConfirmarLiberar}
          />
        ) : vaga.status === 'manutencao' ? (
          <p className="text-center text-xs text-muted-foreground">Indisponível</p>
        ) : podeAgir ? (
          <>
            {veiculos.length > 1 && acao !== 'inicial' && (
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

            {acao === 'inicial' && reservaEhMinha && (
              <>
                <SwipeToConfirm
                  label="Deslize para confirmar chegada"
                  confirmingLabel="Confirmando…"
                  onConfirm={handleConfirmarOcupar}
                />
                <button
                  type="button"
                  onClick={handleCancelarReserva}
                  disabled={cancelarReserva.isPending}
                  className="w-full text-center text-xs text-muted-foreground hover:text-destructive"
                >
                  {cancelarReserva.isPending ? 'Cancelando…' : 'Cancelar reserva'}
                </button>
              </>
            )}
            {acao === 'inicial' && !reservaEhMinha && (
              <SwipeToConfirm label="Deslize para continuar" onConfirm={() => setAcao('escolhendo')} />
            )}

            {acao === 'escolhendo' && (
              <div className="space-y-2">
                <div className="flex gap-2">
                  <Button size="sm" className="flex-1" disabled={ocupar.isPending} onClick={handleConfirmarOcupar}>
                    {ocupar.isPending ? 'Ocupando…' : 'Ocupar agora'}
                  </Button>
                  {vaga.status === 'livre' && (
                    <Button variant="outline" size="sm" className="flex-1" onClick={() => setAcao('prazo')}>
                      Reservar
                    </Button>
                  )}
                </div>
                <button
                  type="button"
                  onClick={resetar}
                  className="w-full text-center text-xs text-muted-foreground hover:text-foreground"
                >
                  Cancelar
                </button>
              </div>
            )}

            {acao === 'prazo' && (
              <div className="space-y-2">
                <p className="text-center text-xs text-muted-foreground">Reservar por quanto tempo?</p>
                <div className="flex gap-2">
                  {PRAZOS_RESERVA.map((p) => (
                    <Button
                      key={p.minutos}
                      variant="outline"
                      size="sm"
                      className="flex-1"
                      disabled={criarReserva.isPending}
                      onClick={() => handleReservarPrazo(p.minutos)}
                    >
                      {p.label}
                    </Button>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => setAcao('escolhendo')}
                  className="w-full text-center text-xs text-muted-foreground hover:text-foreground"
                >
                  Voltar
                </button>
              </div>
            )}

            {acao === 'inicial' && (
              <button
                type="button"
                onClick={() => setModalAberto(true)}
                className="w-full text-center text-xs text-muted-foreground hover:text-foreground"
              >
                Registrar para outra pessoa
              </button>
            )}
          </>
        ) : isAdmin ? (
          <Button size="sm" className="w-full" onClick={() => setModalAberto(true)}>
            Ocupar vaga
          </Button>
        ) : !cadastro ? (
          <Button size="sm" className="w-full" onClick={() => definirPulado(false)}>
            Completar cadastro para continuar
          </Button>
        ) : (
          <div className="space-y-1 text-center">
            <p className="text-xs text-muted-foreground">Adicione um veículo no seu cadastro para continuar.</p>
            <Link to="/meu-cadastro" className="text-xs text-primary underline">
              Ir para Meu Cadastro
            </Link>
          </div>
        )}
      </div>

      <EntradaModal vagaId={vaga.id} open={modalAberto} onOpenChange={setModalAberto} />
    </div>
  )
}
