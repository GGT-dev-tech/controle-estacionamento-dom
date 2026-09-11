import { useState, type FormEvent } from 'react'
import { Layout } from '@/components/Layout'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  useAdicionarVeiculo,
  useAtualizarMeuCadastro,
  useMeuCadastro,
  useRemoverVeiculo,
} from '@/hooks/useCliente'

function DadosSection() {
  const { data: cadastro } = useMeuCadastro()
  const atualizar = useAtualizarMeuCadastro()
  const [erro, setErro] = useState<string | null>(null)
  const [salvo, setSalvo] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErro(null)
    setSalvo(false)
    const form = new FormData(event.currentTarget)
    try {
      await atualizar.mutateAsync({
        telefone: String(form.get('telefone')),
        email: String(form.get('email') || '') || undefined,
      })
      setSalvo(true)
    } catch {
      setErro('Não foi possível salvar. Confira os dados e tente novamente.')
    }
  }

  if (!cadastro) return null

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h3 className="mb-3 text-sm font-semibold">Meus dados</h3>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="space-y-1">
          <Label htmlFor="telefone">Telefone (WhatsApp)</Label>
          <Input id="telefone" name="telefone" defaultValue={cadastro.telefone} required />
        </div>
        <div className="space-y-1">
          <Label htmlFor="email">E-mail</Label>
          <Input id="email" name="email" type="email" defaultValue={cadastro.email ?? ''} />
        </div>
        {erro && <p className="text-sm text-destructive">{erro}</p>}
        {salvo && <p className="text-sm text-vaga-livre">Salvo com sucesso.</p>}
        <Button type="submit" size="sm" disabled={atualizar.isPending}>
          {atualizar.isPending ? 'Salvando…' : 'Salvar'}
        </Button>
      </form>
    </div>
  )
}

function VeiculosSection() {
  const { data: cadastro } = useMeuCadastro()
  const adicionar = useAdicionarVeiculo()
  const remover = useRemoverVeiculo()
  const [erro, setErro] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErro(null)
    const form = new FormData(event.currentTarget)
    try {
      await adicionar.mutateAsync({
        placa: String(form.get('placa')),
        veiculo: String(form.get('veiculo')),
      })
      event.currentTarget.reset()
    } catch {
      setErro('Não foi possível adicionar o veículo (placa já cadastrada?).')
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h3 className="mb-3 text-sm font-semibold">Meus veículos</h3>
      <form onSubmit={handleSubmit} className="mb-3 flex flex-wrap gap-2">
        <Input name="placa" placeholder="ABC1234" required className="w-28 uppercase" />
        <Input name="veiculo" placeholder="Fiat Argo 1.0" required className="flex-1 min-w-[140px]" />
        <Button type="submit" size="sm" disabled={adicionar.isPending}>
          Adicionar
        </Button>
      </form>
      {erro && <p className="mb-2 text-sm text-destructive">{erro}</p>}
      <ul className="space-y-1">
        {cadastro?.veiculos.map((v) => (
          <li
            key={v.id}
            className="flex items-center justify-between rounded-md bg-secondary px-3 py-1.5 text-sm"
          >
            <span>
              <span className="font-medium">{v.placa}</span> — {v.veiculo}
            </span>
            <button
              onClick={() => remover.mutate(v.id)}
              disabled={remover.isPending}
              className="text-xs text-muted-foreground hover:text-destructive"
            >
              Remover
            </button>
          </li>
        ))}
        {cadastro?.veiculos.length === 0 && (
          <p className="text-sm text-muted-foreground">Nenhum veículo cadastrado ainda.</p>
        )}
      </ul>
    </div>
  )
}

export default function MeuCadastro() {
  return (
    <Layout>
      <div className="space-y-6">
        <h2 className="text-sm font-semibold">Meu cadastro</h2>
        <DadosSection />
        <VeiculosSection />
      </div>
    </Layout>
  )
}
