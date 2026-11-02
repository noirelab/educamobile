import { Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { canWrite } from '@/shared/auth/permissions'
import { useAuth } from '@/shared/auth/useAuth'
import { Button } from '@/shared/ui/button'
import { DataTable } from '@/shared/ui/DataTable'
import { PageHeader } from '@/shared/ui/PageHeader'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import { Pager } from '@/shared/ui/Pager'
import { usePager } from '@/shared/ui/usePager'
import { usePoles } from '../hooks'

export function PoleListPage() {
  const pager = usePager()
  const { role } = useAuth()
  const query = usePoles(pager)
  const canEdit = role !== null && canWrite(role, 'poles')

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Polos"
        description="Polos de atendimento do transporte escolar"
        actions={
          canEdit && (
            <Button asChild>
              <Link to="/poles/new">
                <Plus aria-hidden="true" />
                Novo polo
              </Link>
            </Button>
          )
        }
      />
      <Panel dense className="p-0 lg:p-0">
        {query.isPending && <PageState status="loading" />}
        {query.isError && (
          <PageState status="error" error={query.error} onRetry={() => void query.refetch()} />
        )}
        {query.isSuccess && query.data.length === 0 && (
          <PageState status="empty" emptyText="Nenhum polo cadastrado" />
        )}
        {query.isSuccess && query.data.length > 0 && (
          <DataTable
            embedded
            columns={[
              { key: 'nome', header: 'Nome', cell: (pole) => pole.nome },
              { key: 'area', header: 'Área', cell: (pole) => (pole.area ? 'Sim' : 'Não') },
            ]}
            rows={query.data}
            rowHref={(pole) => `/poles/${pole.id}`}
          />
        )}
        {query.isSuccess && <Pager pager={pager} rows={query.data} />}
      </Panel>
    </div>
  )
}
