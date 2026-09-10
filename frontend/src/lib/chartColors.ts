/**
 * Paleta validada (dataviz skill) — a app hoje só renderiza em dark mode (index.html fixa
 * `class="dark"`, sem toggle ainda), então usamos apenas os steps de dark aqui.
 */
export const STATUS_COLORS = {
  livre: '#0ca30c', // good
  reservada: '#fab219', // warning
  ocupada: '#d03b3b', // critical
  manutencao: '#898781', // neutro (fora da paleta de status — não é um estado de alerta)
} as const

export const SERIES_COLORS = {
  entradas: '#3987e5', // categórico slot 1 (azul, dark)
  saidas: '#d95926', // categórico slot 2 (laranja, dark)
} as const

export const CHART_INK = {
  primary: '#ffffff',
  secondary: '#c3c2b7',
  muted: '#898781',
  grid: '#2c2c2a',
  surface: '#1a1a19',
} as const
