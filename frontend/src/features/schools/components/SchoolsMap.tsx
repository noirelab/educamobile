import { Marker } from 'react-leaflet'
import type { components } from '@/shared/api/schema'
import { BaseMap } from '@/shared/map/BaseMap'
import { toLeaflet } from '@/shared/map/geo'
import { Panel } from '@/shared/ui/Panel'

type EscolaLer = components['schemas']['EscolaLer']

type SchoolsMapProps = { schools: EscolaLer[] }

export function SchoolsMap({ schools }: SchoolsMapProps) {
  return (
    <Panel className="p-2.5 lg:p-2.5">
      <BaseMap center={schools[0]?.localizacao} className="h-[560px]">
        {schools.map((school) => (
          <Marker key={school.id} position={toLeaflet(school.localizacao)} title={school.nome} />
        ))}
      </BaseMap>
    </Panel>
  )
}
