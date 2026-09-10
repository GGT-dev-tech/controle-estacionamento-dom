import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { useVagas } from '@/hooks/useVagas'
import { useCriarReserva } from '@/hooks/useReservas'

export function ReservaForm() {
  const { data: vagas } = useVagas('')
  const vagasLivres = vagas?.filter((v) => v.status === 'livre') ?? []
  const criarReserva = useCriarReserva()
  const [erro, setErro] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErro(null)
    const form = new FormData(event.currentTarget)
    const inicio = String(form.get('inicio'))
    const fim = String(form.get('fim'))

    try {
      await criarReserva.mutateAsync({
        vaga_id: String(form.get('vaga_id')),
        nome: String(form.get('nome')),
        telefone: String(form.get('telefone') || '') || undefined,
        inicio: new Date(inicio).toISOString(),
        fim: new Date(fim).toISOString(),
      })
      event.currentTarget.reset()
    } catch {
      setErro('Não foi possível criar a reserva. Verifique os dados e tente novamente.')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 rounded-lg border border-border bg-card p-4">
      <h2 className="text-sm font-semibold">Nova reserva</h2>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor="vaga_id">Vaga</Label>
          <Select id="vaga_id" name="vaga_id" required defaultValue="">
            <option value="" disabled>
              Selecione uma vaga livre
            </option>
            {vagasLivres.map((vaga) => (
              <option key={vaga.id} value={vaga.id}>
                {vaga.id}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="nome">Nome</Label>
          <Input id="nome" name="nome" required />
        </div>
        <div className="space-y-1">
          <Label htmlFor="telefone">Telefone (opcional)</Label>
          <Input id="telefone" name="telefone" placeholder="11999998888" />
        </div>
        <div />
        <div className="space-y-1">
          <Label htmlFor="inicio">Início</Label>
          <Input id="inicio" name="inicio" type="datetime-local" required />
        </div>
        <div className="space-y-1">
          <Label htmlFor="fim">Fim</Label>
          <Input id="fim" name="fim" type="datetime-local" required />
        </div>
      </div>

      {erro && <p className="text-sm text-destructive">{erro}</p>}

      <Button type="submit" disabled={criarReserva.isPending}>
        {criarReserva.isPending ? 'Reservando…' : 'Criar reserva'}
      </Button>
    </form>
  )
}
