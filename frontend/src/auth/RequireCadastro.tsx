import { useState, type ReactNode } from 'react'
import axios from 'axios'
import { useMeuCadastro } from '@/hooks/useCliente'
import Onboarding from '@/pages/Onboarding'

const CHAVE_PULADO = 'dom-onboarding-pulado'

function foiPulado(): boolean {
  try {
    return localStorage.getItem(CHAVE_PULADO) === '1'
  } catch {
    return false
  }
}

function marcarOnboardingPulado(): void {
  try {
    localStorage.setItem(CHAVE_PULADO, '1')
  } catch {
    // localStorage indisponível (modo privado etc.) — sem persistência, o onboarding
    // reaparece na próxima sessão; sem problema, não bloqueia o uso agora.
  }
}

/**
 * Gate de "primeiro acesso": se o usuário autenticado ainda não tem um cadastro
 * (GET /clientes/me -> 404), mostra o onboarding em vez do app. Tem opção de pular,
 * que persiste localmente até o cadastro ser concluído.
 */
export function RequireCadastro({ children }: { children: ReactNode }) {
  const { isLoading, isError, error } = useMeuCadastro()
  const [pulado, setPulado] = useState(foiPulado)

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        Carregando…
      </div>
    )
  }

  const semCadastro = isError && axios.isAxiosError(error) && error.response?.status === 404

  if (semCadastro && !pulado) {
    return (
      <Onboarding
        onPular={() => {
          marcarOnboardingPulado()
          setPulado(true)
        }}
      />
    )
  }

  return <>{children}</>
}
