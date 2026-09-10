import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { HistoricoDia } from '@/api/relatorios'
import { CHART_INK, SERIES_COLORS } from '@/lib/chartColors'

export function HistoricoChart({ dados }: { dados: HistoricoDia[] }) {
  const formatado = dados.map((d) => ({
    ...d,
    diaLabel: new Date(`${d.data}T00:00:00`).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }),
  }))

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={formatado} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
        <CartesianGrid stroke={CHART_INK.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="diaLabel" tickLine={false} axisLine={false} tick={{ fill: CHART_INK.muted, fontSize: 12 }} />
        <YAxis
          allowDecimals={false}
          tickLine={false}
          axisLine={false}
          tick={{ fill: CHART_INK.muted, fontSize: 12 }}
        />
        <Tooltip
          contentStyle={{ background: CHART_INK.surface, border: `1px solid ${CHART_INK.grid}`, borderRadius: 8 }}
          labelStyle={{ color: CHART_INK.primary }}
        />
        <Legend wrapperStyle={{ fontSize: 12, color: CHART_INK.secondary }} />
        <Line
          type="monotone"
          dataKey="entradas"
          name="Entradas"
          stroke={SERIES_COLORS.entradas}
          strokeWidth={2}
          dot={{ r: 4 }}
        />
        <Line
          type="monotone"
          dataKey="saidas"
          name="Saídas"
          stroke={SERIES_COLORS.saidas}
          strokeWidth={2}
          dot={{ r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
