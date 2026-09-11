import { useState } from 'react'
import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select } from '@/components/ui/select'
import { EntradaModal } from '@/components/EntradaModal'
import { useIsAdmin } from '@/auth/useIsAdmin'
import { PRAZOS_RESERVA, useVagaAcoes } from '@/hooks/useVagaAcoes'
import { STATUS_DOT, STATUS_LABEL, STATUS_RING } from '@/lib/vagaStatus'
import { useOnboardingPulado } from '@/stores/useOnboardingPulado'
import type { Vaga } from '@/api/types'
import { cn } from '@/lib/utils'

/**
 * Mesma lógica de ações do VagaCard (useVagaAcoes), em layout compacto de linha. No lugar
 * do gesto de deslizar do card, um toque no "❯" expande um painel de botões — mais rápido
 * de escanear numa lista longa do que um grid de cards.
 */
export function VagaListItem({ vaga }: { vaga: Vaga }) {
  const [modalAberto, setModalAberto] = useState(false)
  const [expandido, setExpandido] = useState(false)
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
    liberar,
    criarReserva,
    cancelarReserva,
    resetar,
    handleConfirmarOcupar,
    handleConfirmarLiberar,
    handleCancelarReserva,
    handleReservarPrazo,
  } = useVagaAcoes(vaga)

  const podeExpandir = vaga.status !== 'manutencao'

  function handleToqueNaLinha() {
    if (!podeExpandir) return
    if (!expandido && acao === 'inicial' && podeAgir && !reservaEhMinha) {
      setAcao('escolhendo')
    }
    setExpandido((v) => !v)
  }

  function fecharPainel() {
    setExpandido(false)
    resetar()
  }

  const resumo = vaga.ocupante
    ? `${vaga.ocupante.nome} • ${vaga.ocupante.placa}`
    : vaga.reserva_ativa
      ? `${reservaEhMinha ? 'Reservada por você' : `Reservada para ${vaga.reserva_ativa.nome}`} até ${new Date(
          vaga.reserva_ativa.fim,
        ).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`
      : (vaga.posicao ?? 'Livre')

  return (
    <div
      className={cn(
        'rounded-lg border border-white/10 bg-card/40 backdrop-blur-xl shadow-glass transition-shadow',
        STATUS_RING[vaga.status],
        !vaga.ativo && 'opacity-50',
      )}
    >
      <button type="button" onClick={handleToqueNaLinha} className="flex w-full items-center gap-3 p-3 text-left">
        <span
          className={cn(
            'h-2 w-2 shrink-0 rounded-full',
            STATUS_DOT[vaga.status],
            vaga.status !== 'manutencao' && 'animate-pulse',
          )}
        />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="font-mono text-sm font-semibold">{vaga.id}</span>
            <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] font-medium text-secondary-foreground">
              {vaga.andar}
            </span>
          </div>
          <p className="truncate font-mono text-xs tabular-nums text-muted-foreground">{resumo}</p>
        </div>
        <Badge variant={vaga.status}>{STATUS_LABEL[vaga.status]}</Badge>
        {podeExpandir && (
          <ChevronRight
            className={cn('h-4 w-4 shrink-0 text-muted-foreground transition-transform', expandido && 'rotate-90')}
          />
        )}
      </button>

      {expandido && (
        <div className="space-y-2 border-t border-white/10 px-3 pb-3 pt-3">
          {erro && <p className="text-xs text-destructive">{erro}</p>}

          {vaga.status === 'ocupada' ? (
            cadastro ? (
              <Button size="sm" className="w-full" disabled={liberar.isPending} onClick={handleConfirmarLiberar}>
                {liberar.isPending ? 'Liberando…' : 'Liberar vaga'}
              </Button>
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
          ) : podeAgir ? (
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

              {reservaEhMinha ? (
                <div className="space-y-2">
                  <Button size="sm" className="w-full" disabled={ocupar.isPending} onClick={handleConfirmarOcupar}>
                    {ocupar.isPending ? 'Confirmando…' : 'Confirmar chegada'}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full"
                    disabled={cancelarReserva.isPending}
                    onClick={handleCancelarReserva}
                  >
                    {cancelarReserva.isPending ? 'Cancelando…' : 'Cancelar reserva'}
                  </Button>
                </div>
              ) : acao === 'prazo' ? (
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
              ) : (
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
              )}

              <button
                type="button"
                onClick={() => setModalAberto(true)}
                className="w-full text-center text-xs text-muted-foreground hover:text-foreground"
              >
                Registrar para outra pessoa
              </button>
            </>
          ) : vaga.status !== 'livre' ? null : isAdmin ? (
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

          <button
            type="button"
            onClick={fecharPainel}
            className="w-full text-center text-xs text-muted-foreground hover:text-foreground"
          >
            Fechar
          </button>
        </div>
      )}

      <EntradaModal vagaId={vaga.id} open={modalAberto} onOpenChange={setModalAberto} />
    </div>
  )
}
