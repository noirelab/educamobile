import { Polyline } from 'react-leaflet'
import { BaseMap } from '@/shared/map/BaseMap'
import { geoJsonLineToLatLngs } from '@/shared/map/geo'
import type { Rota } from '../api'

type RoutesMiniMapProps = {
  routes: Rota[]
}

export function RoutesMiniMap({ routes }: RoutesMiniMapProps) {
  return (
    <BaseMap className="h-[420px]">
      {routes.map((route) =>
        route.trajeto ? (
          <Polyline key={route.id} positions={geoJsonLineToLatLngs(route.trajeto)} pathOptions={{ color: '#0f766e' }} />
        ) : null,
      )}
    </BaseMap>
  )
}
