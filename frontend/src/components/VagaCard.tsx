import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select } from '@/components/ui/select'
import { EntradaModal } from '@/components/EntradaModal'
import { SwipeToConfirm } from '@/components/SwipeToConfirm'
import { useLiberarVaga, useOcuparVaga } from '@/hooks/useVagas'
import { useCriarReserva } from '@/hooks/useReservas'
import { useMeuCadastro } from '@/hooks/useCliente'
import type { Vaga } from '@/api/types'
import { cn } from '@/lib/utils'

const STATUS_LABEL: Record<Vaga['status'], string> = {
  livre: 'Livre',
  ocupada: 'Ocupada',
  reservada: 'Reservada',
  manutencao: 'Manutenção',
}

const PRAZOS_RESERVA = [
  { minutos: 15, label: '15 min' },
  { minutos: 30, label: '30 min' },
  { minutos: 60, label: '1h' },
]

type Acao = 'inicial' | 'escolhendo' | 'prazo'

export function VagaCard({ vaga }: { vaga: Vaga }) {
  const [modalAberto, setModalAberto] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [acao, setAcao] = useState<Acao>('inicial')
  const [veiculoEscolhidoId, setVeiculoEscolhidoId] = useState<number | null>(null)
  const { data: cadastro } = useMeuCadastro()
  const ocupar = useOcuparVaga()
  const liberar = useLiberarVaga()
  const criarReserva = useCriarReserva()

  const veiculos = cadastro?.veiculos ?? []
  const veiculoAtivo = veiculos.find((v) => v.id === veiculoEscolhidoId) ?? veiculos[0]

  // A reserva é minha? Só assim faz sentido oferecer "confirmar chegada" direto —
  // reserva de outra pessoa continua só como informação (ocupar fisicamente ainda é
  // possível, mas passa pela escolha normal, não por um atalho "é sua vaga").
  const reservaEhMinha = !!(vaga.reserva_ativa && cadastro && vaga.reserva_ativa.telefone === cadastro.telefone)

  // Swipe só faz sentido pra quem já tem cadastro + veículo — sem isso não dá pra
  // preencher nome/placa sozinho, e o formulário completo continua sendo o caminho
  // (ex.: registrando a entrada de um visitante sem conta).
  const podeUsarSwipe =
    (vaga.status === 'livre' || vaga.status === 'reservada') && !!cadastro && veiculos.length > 0

  function resetar() {
    setAcao('inicial')
    setVeiculoEscolhidoId(null)
  }

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
    } finally {
      resetar()
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

  async function handleReservarPrazo(minutos: number) {
    if (!cadastro || !veiculoAtivo) return
    setErro(null)
    const inicio = new Date()
    const fim = new Date(inicio.getTime() + minutos * 60_000)
    try {
      await criarReserva.mutateAsync({
        vaga_id: vaga.id,
        nome: cadastro.nome,
        telefone: cadastro.telefone,
        email: cadastro.email ?? undefined,
        placa: veiculoAtivo.placa,
        inicio: inicio.toISOString(),
        fim: fim.toISOString(),
      })
    } catch {
      setErro('Não foi possível reservar a vaga. Tente novamente.')
    } finally {
      resetar()
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
          <div className="flex items-center gap-1.5">
            <p className="text-lg font-semibold">{vaga.id}</p>
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
            {vaga.ocupante.veiculo} • {vaga.ocupante.placa}
          </p>
        </div>
      )}

      {vaga.reserva_ativa && !vaga.ocupante && (
        <div className="text-sm">
          <p className="font-medium">
            {reservaEhMinha ? 'Reservada por você' : `Reservada para ${vaga.reserva_ativa.nome}`}
          </p>
          <p className="text-muted-foreground">
            até {new Date(vaga.reserva_ativa.fim).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
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
        ) : podeUsarSwipe ? (
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
              <SwipeToConfirm
                label="Deslize para confirmar chegada"
                confirmingLabel="Confirmando…"
                onConfirm={handleConfirmarOcupar}
              />
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
