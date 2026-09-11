import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type VisualizacaoVagas = 'cards' | 'lista'

interface VisualizacaoState {
  visualizacao: VisualizacaoVagas
  definirVisualizacao: (v: VisualizacaoVagas) => void
}

/** Preferência de visualização (cards ou lista) — por dispositivo/navegador, via localStorage. */
export const useVisualizacaoVagas = create<VisualizacaoState>()(
  persist(
    (set) => ({
      visualizacao: 'cards',
      definirVisualizacao: (v) => set({ visualizacao: v }),
    }),
    { name: 'dom-visualizacao-vagas' },
  ),
)
