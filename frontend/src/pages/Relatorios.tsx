import { useState } from 'react'
import { baixarArquivo } from '@/api/download'
import { Layout } from '@/components/Layout'
import { StatTile } from '@/components/StatTile'
import { HistoricoChart } from '@/components/charts/HistoricoChart'
import { StatusVagasChart } from '@/components/charts/StatusVagasChart'
import { Button } from '@/components/ui/button'
import { useHistorico, useRelatorioDiario } from '@/hooks/useRelatorios'

export default function Relatorios() {
  const { data: relatorio, isLoading } = useRelatorioDiario()
  const { data: historico } = useHistorico(7)
  const [baixando, setBaixando] = useState<'csv' | 'pdf' | null>(null)

  async function handleBaixarCsv() {
    setBaixando('csv')
    try {
      await baixarArquivo('/relatorios/movimentacoes/csv', 'movimentacoes.csv', { dias: 7 })
    } finally {
      setBaixando(null)
    }
  }

  async function handleBaixarPdf() {
    setBaixando('pdf')
    try {
      await baixarArquivo('/relatorios/diario/pdf', 'relatorio-diario.pdf')
    } finally {
      setBaixando(null)
    }
  }

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">Relatórios</h2>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={baixando !== null} onClick={handleBaixarCsv}>
              {baixando === 'csv' ? 'Baixando…' : 'Exportar CSV'}
            </Button>
            <Button variant="outline" size="sm" disabled={baixando !== null} onClick={handleBaixarPdf}>
              {baixando === 'pdf' ? 'Baixando…' : 'Exportar PDF'}
            </Button>
          </div>
        </div>

        {isLoading && <p className="text-sm text-muted-foreground">Carregando…</p>}

        {relatorio && (
          <>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatTile label="Total de vagas" value={relatorio.total_vagas} />
              <StatTile label="Entradas hoje" value={relatorio.entradas_hoje} />
              <StatTile label="Saídas hoje" value={relatorio.saidas_hoje} />
              <StatTile
                label="Tempo médio"
                value={
                  relatorio.tempo_medio_permanencia_min != null
                    ? `${relatorio.tempo_medio_permanencia_min} min`
                    : '—'
                }
              />
            </div>

            <div className="rounded-lg border border-white/10 bg-card/40 backdrop-blur-xl shadow-glass p-4">
              <h3 className="mb-2 text-sm font-medium text-muted-foreground">Status das vagas</h3>
              <StatusVagasChart relatorio={relatorio} />
            </div>
          </>
        )}

        {historico && (
          <div className="rounded-lg border border-white/10 bg-card/40 backdrop-blur-xl shadow-glass p-4">
            <h3 className="mb-2 text-sm font-medium text-muted-foreground">Entradas e saídas — últimos 7 dias</h3>
            <HistoricoChart dados={historico} />
          </div>
        )}
      </div>
    </Layout>
  )
}
