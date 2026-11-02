import { Polygon, Popup } from 'react-leaflet'
import { multiPolygonToLatLngs } from '@/shared/map/geo'
import type { FrequenciaAgregada, Polo } from '../api'
import { rateColor } from '@/shared/lib/heat'
import { popupLabel } from '../heat'

type PoleLayerProps = {
  poles: Polo[]
  rows: FrequenciaAgregada[]
}

export function PoleLayer({ poles, rows }: PoleLayerProps) {
  const rowsById = new Map(rows.map((row) => [row.grupo_id, row]))

  return (
    <>
      {poles.map((pole) => {
        if (!pole.area) return null
        const row = rowsById.get(pole.id)
        return (
          <Polygon
            key={pole.id}
            positions={multiPolygonToLatLngs(pole.area)}
            pathOptions={{ fillColor: rateColor(row?.taxa_infrequencia ?? 0), fillOpacity: 0.45 }}
          >
            <Popup>{popupLabel(pole.nome, row)}</Popup>
          </Polygon>
        )
      })}
    </>
  )
}
