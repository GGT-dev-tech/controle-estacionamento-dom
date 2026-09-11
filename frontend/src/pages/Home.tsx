import { Layout } from '@/components/Layout'
import { VagaCard } from '@/components/VagaCard'
import { useVagas } from '@/hooks/useVagas'
import { useVagasSocket } from '@/hooks/useVagasSocket'

export default function Home() {
  const { data: vagas, isLoading, isError } = useVagas('')
  useVagasSocket()

  return (
    <Layout>
      {isLoading && <p className="text-sm text-muted-foreground">Carregando vagas…</p>}
      {isError && <p className="text-sm text-destructive">Erro ao carregar vagas. Tente novamente.</p>}

      {vagas && vagas.length === 0 && (
        <p className="text-sm text-muted-foreground">Nenhuma vaga cadastrada.</p>
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
