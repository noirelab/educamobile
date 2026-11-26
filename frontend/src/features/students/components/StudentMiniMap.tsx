import L from 'leaflet'
import { Marker } from 'react-leaflet'
import { BaseMap } from '@/shared/map/BaseMap'
import { toLeaflet, type LatLng } from '@/shared/map/geo'

const stopIcon = L.divIcon({ className: 'stop-marker', iconSize: [14, 14], iconAnchor: [7, 7] })

// Só a parada: a casa da criança não é cadastrada nem exibida.
export function StudentMiniMap({ stop }: { stop: LatLng }) {
  return (
    <BaseMap center={stop} zoom={15} className="h-[220px]">
      <Marker position={toLeaflet(stop)} icon={stopIcon} title="Parada" />
    </BaseMap>
  )
}
