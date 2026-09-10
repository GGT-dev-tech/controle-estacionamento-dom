import { Layout } from '@/components/Layout'
import { VagaCard } from '@/components/VagaCard'
import { cn } from '@/lib/utils'
import { ANDARES, useUiStore } from '@/stores/useUiStore'
import { useVagas } from '@/hooks/useVagas'
import { useVagasSocket } from '@/hooks/useVagasSocket'

export default function Home() {
  const { andarSelecionado, selecionarAndar } = useUiStore()
  const { data: vagas, isLoading, isError } = useVagas(andarSelecionado)
  useVagasSocket()

  return (
    <Layout>
      <div className="mb-5 flex gap-2">
        {ANDARES.map((andar) => (
          <button
            key={andar.id}
            onClick={() => selecionarAndar(andar.id)}
            className={cn(
              'rounded-md px-4 py-2 text-sm font-medium transition-colors',
              andarSelecionado === andar.id
                ? 'bg-primary text-primary-foreground'
                : 'bg-secondary text-secondary-foreground hover:opacity-80',
            )}
          >
            {andar.label}
          </button>
        ))}
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Carregando vagas…</p>}
      {isError && <p className="text-sm text-destructive">Erro ao carregar vagas. Tente novamente.</p>}

      {vagas && vagas.length === 0 && (
        <p className="text-sm text-muted-foreground">Nenhuma vaga cadastrada para este andar.</p>
      )}

      {vagas && vagas.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {vagas.map((vaga) => (
            <VagaCard key={vaga.id} vaga={vaga} />
          ))}
        </div>
      )}
    </Layout>
  )
}
