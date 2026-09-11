/**
 * Paleta de syntax highlighting (VS Code Dark) — os mesmos tons usados nos indicadores de
 * status das vagas (index.css: --vaga-livre/ocupada/reservada), pra o Relatórios ler como
 * parte do mesmo sistema visual em vez de uma paleta de gráfico genérica à parte.
 */
export const STATUS_COLORS = {
  livre: '#4ec9b0', // teal — mesmo tom de --vaga-livre
  reservada: '#dcdcaa', // amarelo suave — mesmo tom de --vaga-reservada
  ocupada: '#ce9178', // terracota — mesmo tom de --vaga-ocupada
  manutencao: '#737373', // neutro (fora da paleta de status — não é um estado de alerta)
} as const

export const SERIES_COLORS = {
  entradas: '#569cd6', // azul (functions/keywords)
  saidas: '#ce9178', // terracota (strings)
} as const

export const CHART_INK = {
  primary: '#d4d4d4',
  secondary: '#999999',
  muted: '#737373',
  grid: '#404040',
  surface: '#121212',
} as const
