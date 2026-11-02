import L from 'leaflet'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
import type { ReactNode } from 'react'
import { MapContainer, TileLayer } from 'react-leaflet'
import { cn } from '@/shared/lib/utils'
import { DEFAULT_CENTER, DEFAULT_ZOOM, toLeaflet, type LatLng } from './geo'
import './map.css'

delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
})

type BaseMapProps = {
  center?: LatLng
  zoom?: number
  className?: string
  children?: ReactNode
}

export function BaseMap({ center = DEFAULT_CENTER, zoom = DEFAULT_ZOOM, className, children }: BaseMapProps) {
  return (
    <MapContainer
      center={toLeaflet(center)}
      zoom={zoom}
      className={cn('relative h-80 w-full overflow-hidden rounded-[18px]', className)}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution="&copy; OpenStreetMap contributors"
      />
      {children}
    </MapContainer>
  )
}
