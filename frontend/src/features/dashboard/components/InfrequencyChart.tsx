import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { formatPercent } from '@/shared/lib/format'
import { rateColor } from '@/shared/lib/heat'
import { Panel } from '@/shared/ui/Panel'
import { Skeleton } from '@/shared/ui/Skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/shared/ui/tabs'
import type { Group } from '../api'
import { useAggregate, type Period } from '../hooks'
import { groupLabel } from '../summary'

const GROUP_LABEL: Record<Group, string> = { polo: 'Polo', escola: 'Escola', turma: 'Turma' }

const AXIS_TICK = { fontSize: 12, fill: '#2c3b50', fontFamily: 'Inter, system-ui, sans-serif' }

const TOOLTIP_STYLE = {
  background: 'rgba(255, 255, 255, 0.62)',
  backdropFilter: 'blur(18px) saturate(160%)',
  WebkitBackdropFilter: 'blur(18px) saturate(160%)',
  border: '1px solid rgba(15, 30, 51, 0.10)',
  borderRadius: 14,
  boxShadow: '0 12px 32px rgba(15, 30, 51, 0.12)',
  color: '#0f1e33',
  fontSize: 13,
}

type InfrequencyChartProps = {
  period: Period
  groups: Group[]
}

export function InfrequencyChart({ period, groups }: InfrequencyChartProps) {
  const [group, setGroup] = useState<Group>(groups[0])
  const query = useAggregate(group, period)
  const data = (query.data ?? []).map((row) => ({
    name: groupLabel(row, group),
    taxa: row.taxa_infrequencia,
    fill: rateColor(row.taxa_infrequencia),
  }))

  return (
    <Panel
      title={`Infrequência por ${GROUP_LABEL[group].toLowerCase()}`}
      actions={
        groups.length > 1 && (
          <Tabs value={group} onValueChange={(value) => setGroup(value as Group)}>
            <TabsList>
              {groups.map((item) => (
                <TabsTrigger key={item} value={item}>
                  {GROUP_LABEL[item]}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        )
      }
    >
      {query.isPending ? (
        <Skeleton className="h-[280px] w-full rounded-[14px]" />
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="rgba(15, 30, 51, 0.10)" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="name" tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: 'rgba(15, 30, 51, 0.10)' }} />
            <YAxis
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value: number) => formatPercent(value)}
              width={70}
            />
            <Tooltip
              cursor={{ fill: 'rgba(15, 118, 110, 0.06)' }}
              contentStyle={TOOLTIP_STYLE}
              labelStyle={{ color: '#0f1e33', fontWeight: 600 }}
              itemStyle={{ color: '#2c3b50' }}
              formatter={(value: number) => formatPercent(value)}
            />
            <Bar dataKey="taxa" name="Infrequência" radius={[6, 6, 0, 0]} maxBarSize={72} isAnimationActive={false}>
              {data.map((item, index) => (
                <Cell key={index} fill={item.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </Panel>
  )
}
