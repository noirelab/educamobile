import L from 'leaflet'
import { useMemo } from 'react'
import { Marker } from 'react-leaflet'
import { BaseMap } from '@/shared/map/BaseMap'
import { FitBounds } from '@/shared/map/FitBounds'
import { DEFAULT_CENTER, toLeaflet, type LatLng } from '@/shared/map/geo'

const stopIcon = L.divIcon({ className: 'stop-marker', iconSize: [14, 14], iconAnchor: [7, 7] })

type StudentMiniMapProps = { residence: LatLng | null; stop: LatLng | null }

export function StudentMiniMap({ residence, stop }: StudentMiniMapProps) {
  const points = useMemo(
    () => [residence, stop].filter((point): point is LatLng => point !== null),
    [residence, stop],
  )
  const center = points[0] ?? DEFAULT_CENTER

  return (
    <BaseMap center={center} zoom={14} className="h-[220px]">
      <FitBounds points={points} padding={32} maxZoom={15} />
      {residence && <Marker position={toLeaflet(residence)} title="Residência" />}
      {stop && <Marker position={toLeaflet(stop)} icon={stopIcon} title="Parada" />}
    </BaseMap>
  )
}
