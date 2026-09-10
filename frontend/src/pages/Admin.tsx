import { useState, type FormEvent } from 'react'
import { Layout } from '@/components/Layout'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  useAdicionarAdmin,
  useAdicionarDominio,
  useAdmins,
  useAuditLogs,
  useDominios,
  useRemoverAdmin,
  useRemoverDominio,
} from '@/hooks/useAdmin'

function DominiosSection() {
  const { data: dominios } = useDominios()
  const adicionar = useAdicionarDominio()
  const remover = useRemoverDominio()
  const [erro, setErro] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErro(null)
    const form = new FormData(event.currentTarget)
    try {
      await adicionar.mutateAsync(String(form.get('dominio')))
      event.currentTarget.reset()
    } catch {
      setErro('Não foi possível adicionar o domínio.')
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h3 className="mb-3 text-sm font-semibold">Domínios autorizados</h3>
      <form onSubmit={handleSubmit} className="mb-3 flex gap-2">
        <Input name="dominio" placeholder="empresa.com" required className="flex-1" />
        <Button type="submit" size="sm" disabled={adicionar.isPending}>
          Adicionar
        </Button>
      </form>
      {erro && <p className="mb-2 text-sm text-destructive">{erro}</p>}
      <ul className="space-y-1">
        {dominios?.map((d) => (
          <li
            key={d.dominio}
            className="flex items-center justify-between rounded-md bg-secondary px-3 py-1.5 text-sm"
          >
            {d.dominio}
            <button
              onClick={() => remover.mutate(d.dominio)}
              disabled={remover.isPending}
              className="text-xs text-muted-foreground hover:text-destructive"
            >
              Remover
            </button>
          </li>
        ))}
        {dominios?.length === 0 && <p className="text-sm text-muted-foreground">Nenhum domínio cadastrado.</p>}
      </ul>
    </div>
  )
}

function AdminsSection() {
  const { data: admins } = useAdmins()
  const adicionar = useAdicionarAdmin()
  const remover = useRemoverAdmin()
  const [erro, setErro] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErro(null)
    const form = new FormData(event.currentTarget)
    try {
      await adicionar.mutateAsync(String(form.get('email')))
      event.currentTarget.reset()
    } catch {
      setErro('Não foi possível adicionar o e-mail.')
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h3 className="mb-3 text-sm font-semibold">E-mails com papel de admin</h3>
      <form onSubmit={handleSubmit} className="mb-3 flex gap-2">
        <Input name="email" type="email" placeholder="pessoa@empresa.com" required className="flex-1" />
        <Button type="submit" size="sm" disabled={adicionar.isPending}>
          Adicionar
        </Button>
      </form>
      {erro && <p className="mb-2 text-sm text-destructive">{erro}</p>}
      <ul className="space-y-1">
        {admins?.map((a) => (
          <li key={a.email} className="flex items-center justify-between rounded-md bg-secondary px-3 py-1.5 text-sm">
            {a.email}
            <button
              onClick={() => remover.mutate(a.email)}
              disabled={remover.isPending}
              className="text-xs text-muted-foreground hover:text-destructive"
            >
              Remover
            </button>
          </li>
        ))}
        {admins?.length === 0 && <p className="text-sm text-muted-foreground">Nenhum admin extra cadastrado.</p>}
      </ul>
    </div>
  )
}

function AuditLogSection() {
  const { data: logs, isLoading } = useAuditLogs()

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h3 className="mb-3 text-sm font-semibold">Log de auditoria</h3>
      {isLoading && <p className="text-sm text-muted-foreground">Carregando…</p>}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="text-xs text-muted-foreground">
              <th className="pb-2 pr-3">Quando</th>
              <th className="pb-2 pr-3">Usuário</th>
              <th className="pb-2 pr-3">Ação</th>
              <th className="pb-2 pr-3">Recurso</th>
              <th className="pb-2">IP</th>
            </tr>
          </thead>
          <tbody>
            {logs?.map((log) => (
              <tr key={log.id} className="border-t border-border">
                <td className="py-1.5 pr-3 tabular-nums">{new Date(log.timestamp).toLocaleString('pt-BR')}</td>
                <td className="py-1.5 pr-3">{log.usuario_id}</td>
                <td className="py-1.5 pr-3">{log.acao}</td>
                <td className="py-1.5 pr-3">
                  {log.recurso}
                  {log.recurso_id ? `/${log.recurso_id}` : ''}
                </td>
                <td className="py-1.5">{log.ip ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {logs?.length === 0 && <p className="py-2 text-sm text-muted-foreground">Nenhum registro ainda.</p>}
      </div>
    </div>
  )
}

export default function Admin() {
  return (
    <Layout>
      <div className="space-y-6">
        <h2 className="text-sm font-semibold">Administração</h2>
        <div className="grid gap-6 lg:grid-cols-2">
          <DominiosSection />
          <AdminsSection />
        </div>
        <AuditLogSection />
      </div>
    </Layout>
  )
}
