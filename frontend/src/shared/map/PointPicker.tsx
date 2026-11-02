import { useEffect, useState } from 'react'
import { Marker, useMapEvents } from 'react-leaflet'
import { Button } from '@/shared/ui/button'
import { FloatingField } from '@/shared/ui/FloatingField'
import { BaseMap } from './BaseMap'
import { DEFAULT_CENTER, toLeaflet, type LatLng } from './geo'

type PointPickerProps = {
  value: LatLng | null
  onChange: (point: LatLng | null) => void
  required?: boolean
}

function parseCoordinate(raw: string, min: number, max: number): number | null {
  if (raw.trim() === '') return null
  const parsed = Number(raw.replace(',', '.'))
  if (!Number.isFinite(parsed) || parsed < min || parsed > max) return null
  return parsed
}

function ClickHandler({ onPick }: { onPick: (point: LatLng) => void }) {
  useMapEvents({
    click(event) {
      onPick({ latitude: event.latlng.lat, longitude: event.latlng.lng })
    },
  })
  return null
}

export function PointPicker({ value, onChange, required = false }: PointPickerProps) {
  const latitude = value?.latitude
  const longitude = value?.longitude
  const [latText, setLatText] = useState(latitude === undefined ? '' : String(latitude))
  const [lngText, setLngText] = useState(longitude === undefined ? '' : String(longitude))

  useEffect(() => {
    setLatText(latitude === undefined ? '' : String(latitude))
    setLngText(longitude === undefined ? '' : String(longitude))
  }, [latitude, longitude])

  const latInvalid = latText.trim() !== '' && parseCoordinate(latText, -90, 90) === null
  const lngInvalid = lngText.trim() !== '' && parseCoordinate(lngText, -180, 180) === null

  function commit(nextLat: string, nextLng: string) {
    const lat = parseCoordinate(nextLat, -90, 90)
    const lng = parseCoordinate(nextLng, -180, 180)
    if (lat !== null && lng !== null) onChange({ latitude: lat, longitude: lng })
  }

  function pick(point: LatLng) {
    setLatText(String(point.latitude))
    setLngText(String(point.longitude))
    onChange(point)
  }

  const center = value ?? DEFAULT_CENTER

  return (
    <div className="flex flex-col gap-2">
      <BaseMap center={center} className="h-[280px]">
        <ClickHandler onPick={pick} />
        {value && <Marker position={toLeaflet(value)} />}
      </BaseMap>
      <div className="grid grid-cols-1 gap-x-4 sm:grid-cols-2">
        <FloatingField
          label="Latitude"
          type="number"
          step="any"
          value={latText}
          error={latInvalid ? 'Latitude entre -90 e 90' : undefined}
          onChange={(e) => {
            setLatText(e.target.value)
            commit(e.target.value, lngText)
          }}
        />
        <FloatingField
          label="Longitude"
          type="number"
          step="any"
          value={lngText}
          error={lngInvalid ? 'Longitude entre -180 e 180' : undefined}
          onChange={(e) => {
            setLngText(e.target.value)
            commit(latText, e.target.value)
          }}
        />
      </div>
      {!required && (
        <div>
          <Button type="button" variant="outline" size="sm" onClick={() => onChange(null)}>
            Limpar
          </Button>
        </div>
      )}
    </div>
  )
}
