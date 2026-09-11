import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface OnboardingState {
  pulado: boolean
  definirPulado: (v: boolean) => void
}

/**
 * "Pular por enquanto" no onboarding — por dispositivo/navegador, via localStorage.
 * Compartilhado (não é state local do RequireCadastro) porque precisa poder ser
 * reativado de qualquer lugar: ao tentar ocupar/reservar sem cadastro, o cadastro
 * volta a ser obrigatório (definirPulado(false) reabre o onboarding na hora).
 */
export const useOnboardingPulado = create<OnboardingState>()(
  persist(
    (set) => ({
      pulado: false,
      definirPulado: (v) => set({ pulado: v }),
    }),
    { name: 'dom-onboarding-pulado-v2' },
  ),
)
