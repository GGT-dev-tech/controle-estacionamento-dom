import { LayoutGrid, List } from 'lucide-react'
import { Layout } from '@/components/Layout'
import { VagaCard } from '@/components/VagaCard'
import { VagaListItem } from '@/components/VagaListItem'
import { useVagas } from '@/hooks/useVagas'
import { useVagasSocket } from '@/hooks/useVagasSocket'
import { useVisualizacaoVagas } from '@/stores/useVisualizacaoVagas'
import { cn } from '@/lib/utils'

export default function Home() {
  const { data: vagas, isLoading, isError } = useVagas('')
  useVagasSocket()
  const { visualizacao, definirVisualizacao } = useVisualizacaoVagas()

  return (
    <Layout>
      <div className="mb-4 flex justify-end">
        <div className="inline-flex rounded-md border border-white/10 bg-card/40 p-0.5 backdrop-blur-xl">
          <button
            type="button"
            onClick={() => definirVisualizacao('cards')}
            aria-label="Visualização em cards"
            aria-pressed={visualizacao === 'cards'}
            className={cn(
              'rounded p-1.5',
              visualizacao === 'cards'
                ? 'bg-secondary text-foreground'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <LayoutGrid className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => definirVisualizacao('lista')}
            aria-label="Visualização em lista"
            aria-pressed={visualizacao === 'lista'}
            className={cn(
              'rounded p-1.5',
              visualizacao === 'lista'
                ? 'bg-secondary text-foreground'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <List className="h-4 w-4" />
          </button>
        </div>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Carregando vagas…</p>}
      {isError && <p className="text-sm text-destructive">Erro ao carregar vagas. Tente novamente.</p>}

      {vagas && vagas.length === 0 && (
        <p className="text-sm text-muted-foreground">Nenhuma vaga cadastrada.</p>
      )}

      {vagas && vagas.length > 0 && visualizacao === 'cards' && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {vagas.map((vaga) => (
            <VagaCard key={vaga.id} vaga={vaga} />
          ))}
        </div>
      )}

      {vagas && vagas.length > 0 && visualizacao === 'lista' && (
        <div className="space-y-2">
          {vagas.map((vaga) => (
            <VagaListItem key={vaga.id} vaga={vaga} />
          ))}
        </div>
      )}
    </Layout>
  )
}
