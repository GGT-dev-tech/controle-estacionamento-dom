import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { RelatorioDiario } from '@/api/relatorios'
import { CHART_INK, STATUS_COLORS } from '@/lib/chartColors'

export function StatusVagasChart({ relatorio }: { relatorio: RelatorioDiario }) {
  const dados = [
    { status: 'Livres', valor: relatorio.livres, cor: STATUS_COLORS.livre },
    { status: 'Reservadas', valor: relatorio.reservadas, cor: STATUS_COLORS.reservada },
    { status: 'Ocupadas', valor: relatorio.ocupadas, cor: STATUS_COLORS.ocupada },
    { status: 'Manutenção', valor: relatorio.manutencao, cor: STATUS_COLORS.manutencao },
  ]

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={dados} layout="vertical" margin={{ top: 4, right: 32, bottom: 4, left: 8 }}>
        <XAxis type="number" hide allowDecimals={false} />
        <YAxis
          type="category"
          dataKey="status"
          width={90}
          tickLine={false}
          axisLine={false}
          tick={{ fill: CHART_INK.secondary, fontSize: 12 }}
        />
        <Tooltip
          cursor={{ fill: 'rgba(255,255,255,0.04)' }}
          contentStyle={{ background: CHART_INK.surface, border: `1px solid ${CHART_INK.grid}`, borderRadius: 8 }}
          labelStyle={{ color: CHART_INK.primary }}
          itemStyle={{ color: CHART_INK.secondary }}
        />
        <Bar
          dataKey="valor"
          radius={[0, 4, 4, 0]}
          barSize={22}
          label={{ position: 'right', fill: CHART_INK.primary, fontSize: 12 }}
        >
          {dados.map((entrada) => (
            <Cell key={entrada.status} fill={entrada.cor} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
