import { useState, type FormEvent } from 'react'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { useOcuparVaga } from '@/hooks/useVagas'
import type { TipoCliente } from '@/api/types'

const TIPOS_CLIENTE: { value: TipoCliente; label: string }[] = [
  { value: 'mensalista', label: 'Mensalista' },
  { value: 'rotativo', label: 'Rotativo' },
  { value: 'visitante', label: 'Visitante' },
  { value: 'prestador', label: 'Prestador de serviço' },
]

export function EntradaModal({
  vagaId,
  open,
  onOpenChange,
}: {
  vagaId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const ocupar = useOcuparVaga()
  const [erro, setErro] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErro(null)
    const form = new FormData(event.currentTarget)

    try {
      await ocupar.mutateAsync({
        vaga_id: vagaId,
        nome: String(form.get('nome')),
        placa: String(form.get('placa')),
        veiculo: String(form.get('veiculo')),
        tipo_cliente: form.get('tipo_cliente') as TipoCliente,
        observacoes: String(form.get('observacoes') || '') || undefined,
      })
      onOpenChange(false)
    } catch {
      setErro('Não foi possível ocupar a vaga. Tente novamente.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={`Ocupar vaga ${vagaId}`}>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="nome">Nome do motorista</Label>
            <Input id="nome" name="nome" required />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="placa">Placa</Label>
              <Input id="placa" name="placa" required maxLength={10} className="uppercase" />
            </div>
            <div className="space-y-1">
              <Label htmlFor="tipo_cliente">Tipo</Label>
              <Select id="tipo_cliente" name="tipo_cliente" required defaultValue="visitante">
                {TIPOS_CLIENTE.map((tipo) => (
                  <option key={tipo.value} value={tipo.value}>
                    {tipo.label}
                  </option>
                ))}
              </Select>
            </div>
          </div>
          <div className="space-y-1">
            <Label htmlFor="veiculo">Veículo</Label>
            <Input id="veiculo" name="veiculo" placeholder="Fiat Argo 1.0 6V Flex" required />
          </div>
          <div className="space-y-1">
            <Label htmlFor="observacoes">Observações</Label>
            <Input id="observacoes" name="observacoes" placeholder="Vaga de trás, parede…" />
          </div>

          {erro && <p className="text-sm text-destructive">{erro}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={ocupar.isPending}>
              {ocupar.isPending ? 'Ocupando…' : 'Confirmar entrada'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
