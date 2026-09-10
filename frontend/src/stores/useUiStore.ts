import { create } from 'zustand'

export const ANDARES = [
  { id: 'S2', label: 'S2 — Subsolo 2' },
  { id: 'G2', label: 'G2 — Garagem 2' },
] as const

interface UiState {
  andarSelecionado: string
  selecionarAndar: (andar: string) => void
}

export const useUiStore = create<UiState>((set) => ({
  andarSelecionado: ANDARES[0].id,
  selecionarAndar: (andar) => set({ andarSelecionado: andar }),
}))
