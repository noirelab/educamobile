import { useMemo } from 'react'
import { CircleMarker, Popup } from 'react-leaflet'
import { rateColor } from '@/shared/lib/heat'
import { toLeaflet } from '@/shared/map/geo'
import type { Escola, FrequenciaAgregada } from '../api'
import { heatPoints, popupLabel } from '../heat'
import { HeatLayer } from './HeatLayer'

type InfrequencyHeatmapProps = {
  schools: Escola[]
  rows: FrequenciaAgregada[]
}

export function InfrequencyHeatmap({ schools, rows }: InfrequencyHeatmapProps) {
  const { points } = useMemo(() => heatPoints(schools, rows), [schools, rows])
  const rowsById = useMemo(() => new Map(rows.map((row) => [row.grupo_id, row])), [rows])
  const located = schools.filter((school) => school.localizacao != null && rowsById.has(school.id))

  return (
    <>
      <HeatLayer points={points} />
      {located.map((school) => (
        <CircleMarker
          key={school.id}
          center={toLeaflet(school.localizacao)}
          radius={7}
          pathOptions={{
            color: '#ffffff',
            weight: 2,
            opacity: 1,
            fillColor: rateColor(rowsById.get(school.id)?.taxa_infrequencia ?? 0),
            fillOpacity: 1,
          }}
        >
          <Popup>{popupLabel(school.nome, rowsById.get(school.id))}</Popup>
        </CircleMarker>
      ))}
    </>
  )
}
