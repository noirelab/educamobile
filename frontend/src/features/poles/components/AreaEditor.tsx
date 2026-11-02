import L from 'leaflet'
import '@geoman-io/leaflet-geoman-free'
import '@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css'
import { useEffect, useRef, useState } from 'react'
import { useMap } from 'react-leaflet'
import type { components } from '@/shared/api/schema'
import { latLngsToMultiPolygon, multiPolygonToLatLngs } from '@/shared/map/geo'
import { Button } from '@/shared/ui/button'

type MultiPolygon = components['schemas']['MultiPolygonGeoJSON']

type AreaEditorProps = {
  value: MultiPolygon | null
  onChange: (area: MultiPolygon | null) => void
}

function polygonRings(layer: L.Polygon): [number, number][][] {
  return (layer.getLatLngs() as L.LatLng[][]).map((ring) =>
    ring.map((point) => [point.lat, point.lng] as [number, number]),
  )
}

function collectArea(group: L.FeatureGroup): MultiPolygon | null {
  const polygons = group.getLayers().filter((layer): layer is L.Polygon => layer instanceof L.Polygon)
  if (polygons.length === 0) return null
  return latLngsToMultiPolygon(polygons.map(polygonRings))
}

export function AreaEditor({ value, onChange }: AreaEditorProps) {
  const map = useMap()
  const [group] = useState(() => L.featureGroup())
  const [initialArea] = useState(value)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange
  const controlRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (controlRef.current) L.DomEvent.disableClickPropagation(controlRef.current)
  }, [])

  useEffect(() => {
    const emit = () => onChangeRef.current(collectArea(group))
    const attach = (layer: L.Layer) => {
      group.addLayer(layer)
      layer.on('pm:update', emit)
    }
    if (initialArea) {
      multiPolygonToLatLngs(initialArea).forEach((rings) => attach(L.polygon(rings)))
    }
    group.addTo(map)
    map.pm.addControls({
      position: 'topleft',
      drawPolygon: true,
      editMode: true,
      removalMode: true,
      drawMarker: false,
      drawCircleMarker: false,
      drawPolyline: false,
      drawRectangle: false,
      drawCircle: false,
      drawText: false,
      cutPolygon: false,
      rotateMode: false,
      dragMode: false,
    })
    const handleCreate = (event: { layer: L.Layer }) => {
      attach(event.layer)
      emit()
    }
    const handleRemove = (event: { layer: L.Layer }) => {
      group.removeLayer(event.layer)
      emit()
    }
    map.on('pm:create', handleCreate)
    map.on('pm:remove', handleRemove)
    return () => {
      map.off('pm:create', handleCreate)
      map.off('pm:remove', handleRemove)
      map.pm.removeControls()
      group.clearLayers()
      group.remove()
    }
  }, [map, group, initialArea])

  function clear() {
    group.clearLayers()
    onChangeRef.current(null)
  }

  return (
    <div ref={controlRef} className="absolute bottom-3 left-3 z-[1000]">
      <Button type="button" variant="outline" size="sm" onClick={clear}>
        Limpar área
      </Button>
    </div>
  )
}
