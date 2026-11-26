import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { SchoolsMap } from '@/features/schools/components/SchoolsMap'
import { canWrite } from '@/shared/auth/permissions'
import { useAuth } from '@/shared/auth/useAuth'
import { Button } from '@/shared/ui/button'
import { DataTable } from '@/shared/ui/DataTable'
import { PageHeader } from '@/shared/ui/PageHeader'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import { Pager } from '@/shared/ui/Pager'
import { Tabs, TabsList, TabsTrigger } from '@/shared/ui/tabs'
import { usePager } from '@/shared/ui/usePager'
import { useSchools } from '../hooks'

type View = 'table' | 'map'

export function SchoolListPage() {
  const pager = usePager()
  const { role } = useAuth()
  const [view, setView] = useState<View>('table')
  const query = useSchools(pager)
  const canEdit = role !== null && canWrite(role, 'schools')

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Escolas"
        description="Escolas atendidas pela rede municipal"
        actions={
          canEdit && (
            <Button asChild>
              <Link to="/schools/new">
                <Plus aria-hidden="true" />
                Nova escola
              </Link>
            </Button>
          )
        }
      >
        <div className="ml-auto">
          <Tabs value={view} onValueChange={(value) => setView(value as View)}>
            <TabsList>
              <TabsTrigger value="table">Tabela</TabsTrigger>
              <TabsTrigger value="map">Mapa</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </PageHeader>
      {view === 'map' && query.isSuccess && query.data.length > 0 && (
        <>
          <SchoolsMap schools={query.data} />
          <Panel dense className="p-0 lg:p-0">
            <Pager pager={pager} rows={query.data} />
          </Panel>
        </>
      )}
      {(view === 'table' || !query.isSuccess || query.data.length === 0) && (
        <Panel dense className="p-0 lg:p-0">
          {query.isPending && <PageState status="loading" />}
          {query.isError && (
            <PageState status="error" error={query.error} onRetry={() => void query.refetch()} />
          )}
          {query.isSuccess && query.data.length === 0 && (
            <PageState status="empty" emptyText="Nenhuma escola cadastrada" />
          )}
          {query.isSuccess && query.data.length > 0 && (
            <DataTable
              embedded
              columns={[
                { key: 'nome', header: 'Nome', cell: (school) => school.nome },
                { key: 'inep', header: 'INEP', cell: (school) => school.codigo_inep ?? '—' },
                { key: 'endereco', header: 'Endereço', cell: (school) => school.endereco ?? '—' },
              ]}
              rows={query.data}
              rowHref={(school) => `/schools/${school.id}`}
            />
          )}
          {query.isSuccess && <Pager pager={pager} rows={query.data} />}
        </Panel>
      )}
    </div>
  )
}
