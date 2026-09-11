import { useState, type FormEvent } from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAdicionarVeiculo, useCriarMeuCadastro } from '@/hooks/useCliente'
import { forcarMaiusculas } from '@/lib/utils'

export default function Onboarding({ onPular }: { onPular: () => void }) {
  const { user } = useAuth0()
  const criarCadastro = useCriarMeuCadastro()
  const adicionarVeiculo = useAdicionarVeiculo()
  const [erro, setErro] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErro(null)
    setEnviando(true)
    const form = new FormData(event.currentTarget)
    const placa = String(form.get('placa') || '').trim()
    const veiculo = String(form.get('veiculo') || '').trim()

    try {
      await criarCadastro.mutateAsync({
        nome: user?.name ?? user?.email ?? 'Sem nome',
        telefone: String(form.get('telefone')),
        email: String(form.get('email') || '') || undefined,
      })
      if (placa && veiculo) {
        await adicionarVeiculo.mutateAsync({ placa, veiculo })
      }
    } catch {
      setErro('Não foi possível concluir o cadastro. Confira os dados e tente novamente.')
      setEnviando(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm space-y-4 rounded-lg border border-white/10 bg-card/40 backdrop-blur-xl shadow-glass p-6">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Bem-vindo(a) ao Estacionamento Dom</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Complete seu cadastro para ocupar/reservar vagas e usar o bot do WhatsApp.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="telefone">Telefone (WhatsApp)</Label>
            <Input id="telefone" name="telefone" placeholder="11999998888" required />
          </div>
          <div className="space-y-1">
            <Label htmlFor="email">E-mail</Label>
            <Input id="email" name="email" type="email" defaultValue={user?.email ?? ''} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="placa">Placa (opcional)</Label>
              <Input id="placa" name="placa" className="uppercase" placeholder="ABC1234" onChange={forcarMaiusculas} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="veiculo">Veículo</Label>
              <Input id="veiculo" name="veiculo" placeholder="Fiat Argo" />
            </div>
          </div>

          {erro && <p className="text-sm text-destructive">{erro}</p>}

          <div className="flex flex-col gap-2 pt-2">
            <Button type="submit" disabled={enviando}>
              {enviando ? 'Salvando…' : 'Concluir cadastro'}
            </Button>
            <Button type="button" variant="ghost" onClick={onPular}>
              Pular por enquanto
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
