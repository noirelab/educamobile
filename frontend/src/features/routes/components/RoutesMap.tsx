import L from 'leaflet'
import { Fragment } from 'react'
import { Marker, Polyline, Popup } from 'react-leaflet'
import type { components } from '@/shared/api/schema'
import { BaseMap } from '@/shared/map/BaseMap'
import { FitBounds } from '@/shared/map/FitBounds'
import { geoJsonLineToLatLngs, toLeaflet, type LatLng } from '@/shared/map/geo'
import { formatMeters } from '@/shared/lib/format'
import { routeColor } from '../sequence'
import './routes.css'

type ParadaLer = components['schemas']['ParadaLer']
type RotaLer = components['schemas']['RotaLer']

const POLYLINE_OPTIONS = { weight: 5, opacity: 0.85 }

function numberedIcon(order: number, color: string) {
  return L.divIcon({
    className: '',
    iconSize: [22, 22],
    iconAnchor: [11, 11],
    html: `<span class="route-stop-marker" style="--stop-color:${color}">${order}</span>`,
  })
}

const freeStopIcon = L.divIcon({
  className: '',
  iconSize: [12, 12],
  iconAnchor: [6, 6],
  html: '<span class="route-stop-marker-free"></span>',
})

function routeCenter(routes: RotaLer[]): LatLng | undefined {
  return routes.find((route) => route.paradas.length > 0)?.paradas[0]?.localizacao
}

function RoutePopup({ route }: { route: RotaLer }) {
  return (
    <Popup>
      {route.nome} · {formatMeters(route.distancia_m)}
    </Popup>
  )
}

export function RoutesMap({ routes }: { routes: RotaLer[] }) {
  return (
    <BaseMap center={routeCenter(routes)} className="h-[560px]">
      <FitBounds points={routes.flatMap((route) => route.paradas.map((stop) => stop.localizacao))} />
      {routes.map((route) => {
        const color = routeColor(route.id)
        return (
          <Fragment key={route.id}>
            {route.trajeto && (
              <Polyline
                positions={geoJsonLineToLatLngs(route.trajeto)}
                pathOptions={{ color, ...POLYLINE_OPTIONS }}
              >
                <RoutePopup route={route} />
              </Polyline>
            )}
            {route.paradas.map((stop, index) => (
              <Marker
                key={`${route.id}-${stop.id}`}
                position={toLeaflet(stop.localizacao)}
                icon={numberedIcon(index + 1, color)}
                title={stop.nome}
              >
                <RoutePopup route={route} />
              </Marker>
            ))}
          </Fragment>
        )
      })}
    </BaseMap>
  )
}

type EditorMapProps = {
  stops: ParadaLer[]
  sequence: number[]
  trajeto: RotaLer['trajeto']
  routeId: number
  canEdit: boolean
  onAdd: (stopId: number) => void
}

function stopsById(stops: ParadaLer[]) {
  return new Map(stops.map((stop) => [stop.id, stop]))
}

export function RouteEditorMap({ stops, sequence, trajeto, routeId, canEdit, onAdd }: EditorMapProps) {
  const color = routeColor(routeId)
  const byId = stopsById(stops)
  const inRoute = new Set(sequence)
  const ordered = sequence.map((id) => byId.get(id)).filter((stop): stop is ParadaLer => stop !== undefined)
  const free = stops.filter((stop) => !inRoute.has(stop.id))

  return (
    <BaseMap center={(ordered[0] ?? stops[0])?.localizacao} className="h-[560px]">
      <FitBounds points={stops.map((stop) => stop.localizacao)} />
      {trajeto && (
        <Polyline positions={geoJsonLineToLatLngs(trajeto)} pathOptions={{ color, ...POLYLINE_OPTIONS }} />
      )}
      {free.map((stop) => (
        <Marker
          key={`free-${stop.id}`}
          position={toLeaflet(stop.localizacao)}
          icon={freeStopIcon}
          title={stop.nome}
          eventHandlers={canEdit ? { click: () => onAdd(stop.id) } : undefined}
        />
      ))}
      {ordered.map((stop, index) => (
        <Marker
          key={`route-${stop.id}`}
          position={toLeaflet(stop.localizacao)}
          icon={numberedIcon(index + 1, color)}
          title={stop.nome}
        />
      ))}
    </BaseMap>
  )
}
