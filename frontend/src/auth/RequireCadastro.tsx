import type { ReactNode } from 'react'
import axios from 'axios'
import { useMeuCadastro } from '@/hooks/useCliente'
import { useOnboardingPulado } from '@/stores/useOnboardingPulado'
import Onboarding from '@/pages/Onboarding'

/**
 * Gate de "primeiro acesso": se o usuário autenticado ainda não tem um cadastro
 * (GET /clientes/me -> 404), mostra o onboarding em vez do app. Tem opção de pular,
 * que persiste localmente até o cadastro ser concluído — mas volta a ser exigido na
 * hora se a pessoa tentar ocupar/reservar uma vaga sem cadastro (VagaCard/VagaListItem
 * chamam definirPulado(false), que reabre esta tela imediatamente).
 */
export function RequireCadastro({ children }: { children: ReactNode }) {
  const { isLoading, isError, error } = useMeuCadastro()
  const { pulado, definirPulado } = useOnboardingPulado()

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        Carregando…
      </div>
    )
  }

  const semCadastro = isError && axios.isAxiosError(error) && error.response?.status === 404

  if (semCadastro && !pulado) {
    return <Onboarding onPular={() => definirPulado(true)} />
  }

  return <>{children}</>
}
