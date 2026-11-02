import L from 'leaflet'
import { Circle, Marker, useMapEvents } from 'react-leaflet'
import type { components } from '@/shared/api/schema'
import { BaseMap } from '@/shared/map/BaseMap'
import { FitBounds } from '@/shared/map/FitBounds'
import { toLeaflet, type LatLng } from '@/shared/map/geo'

type ParadaLer = components['schemas']['ParadaLer']

const stopIcon = L.divIcon({ className: 'stop-marker', iconSize: [14, 14], iconAnchor: [7, 7] })

type NearbyCircle = { center: LatLng; raio_m: number }

type StopsMapProps = {
  stops: ParadaLer[]
  draggable: boolean
  nearby: NearbyCircle | null
  onMapClick: (point: LatLng) => void
  onMove: (stop: ParadaLer, point: LatLng) => void
}

function ClickHandler({ onClick }: { onClick: (point: LatLng) => void }) {
  useMapEvents({
    click: (event) => onClick({ latitude: event.latlng.lat, longitude: event.latlng.lng }),
  })
  return null
}

export function StopsMap({ stops, draggable, nearby, onMapClick, onMove }: StopsMapProps) {
  return (
    <BaseMap center={stops[0]?.localizacao} className="h-[560px]">
      <FitBounds points={stops.map((stop) => stop.localizacao)} />
      <ClickHandler onClick={onMapClick} />
      {stops.map((stop) => (
        <Marker
          key={stop.id}
          position={toLeaflet(stop.localizacao)}
          icon={stopIcon}
          title={stop.nome}
          draggable={draggable}
          eventHandlers={{
            dragend: (event) => {
              const { lat, lng } = event.target.getLatLng()
              onMove(stop, { latitude: lat, longitude: lng })
            },
          }}
        />
      ))}
      {nearby && (
        <Circle
          center={toLeaflet(nearby.center)}
          radius={nearby.raio_m}
          pathOptions={{ color: '#0f766e', dashArray: '6 6', fillOpacity: 0.06 }}
        />
      )}
    </BaseMap>
  )
}

export function StopMiniMap({ stop }: { stop: ParadaLer }) {
  return (
    <BaseMap center={stop.localizacao} zoom={15} className="h-[320px]">
      <Marker position={toLeaflet(stop.localizacao)} icon={stopIcon} title={stop.nome} />
    </BaseMap>
  )
}
