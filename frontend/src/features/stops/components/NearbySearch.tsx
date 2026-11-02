import { Search } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { formatMeters } from '@/shared/lib/format'
import type { LatLng } from '@/shared/map/geo'
import { Button } from '@/shared/ui/button'
import { FloatingField } from '@/shared/ui/FloatingField'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import { useNearbyStops } from '../hooks'
import { parseNearbyForm, type NearbyErrors } from '../schemas'

export type NearbyFilter = { center: LatLng; raio_m: number }

type NearbySearchProps = {
  prefill: LatLng | null
  onSearch: (filter: NearbyFilter) => void
}

export function NearbySearch({ prefill, onSearch }: NearbySearchProps) {
  const [latitude, setLatitude] = useState('')
  const [longitude, setLongitude] = useState('')
  const [raio, setRaio] = useState('1000')
  const [errors, setErrors] = useState<NearbyErrors>({})
  const search = useNearbyStops()

  useEffect(() => {
    if (!prefill) return
    setLatitude(String(prefill.latitude))
    setLongitude(String(prefill.longitude))
  }, [prefill])

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const parsed = parseNearbyForm({ latitude, longitude, raio })
    setErrors(parsed.errors ?? {})
    if (parsed.values === null) return
    const { values } = parsed
    onSearch({ center: { latitude: values.latitude, longitude: values.longitude }, raio_m: values.raio_m })
    search.mutate(values)
  }

  return (
    <Panel title="Buscar próximas">
      <form onSubmit={handleSubmit} noValidate className="flex flex-col">
        <div className="grid grid-cols-1 gap-x-4 sm:grid-cols-2">
          <FloatingField
            label="Latitude"
            type="number"
            step="any"
            value={latitude}
            error={errors.latitude}
            onChange={(event) => setLatitude(event.target.value)}
          />
          <FloatingField
            label="Longitude"
            type="number"
            step="any"
            value={longitude}
            error={errors.longitude}
            onChange={(event) => setLongitude(event.target.value)}
          />
        </div>
        <FloatingField
          label="Raio (m)"
          type="number"
          step="any"
          value={raio}
          error={errors.raio_m}
          onChange={(event) => setRaio(event.target.value)}
        />
        <div>
          <Button type="submit" disabled={search.isPending}>
            <Search aria-hidden="true" />
            Buscar próximas
          </Button>
        </div>
      </form>
      {search.isError && (
        <PageState status="error" error={search.error} onRetry={() => search.reset()} />
      )}
      {search.isSuccess && search.data.length === 0 && (
        <PageState status="empty" emptyText="Nenhuma parada neste raio" />
      )}
      {search.isSuccess && search.data.length > 0 && (
        <ul role="list" aria-label="Paradas próximas" className="mt-4 divide-y divide-line">
          {search.data.map((stop) => (
            <li key={stop.id} className="py-2.5 text-body text-ink">
              {`${stop.nome} — ${formatMeters(stop.distancia_m)}`}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
