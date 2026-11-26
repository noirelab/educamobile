import { Plus } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useStopName } from '@/features/stops/hooks'
import type { components } from '@/shared/api/schema'
import { canWrite } from '@/shared/auth/permissions'
import { useAuth } from '@/shared/auth/useAuth'
import { formatDate } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { DataTable } from '@/shared/ui/DataTable'
import { FloatingField } from '@/shared/ui/FloatingField'
import { PageHeader } from '@/shared/ui/PageHeader'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import { Pager } from '@/shared/ui/Pager'
import { usePager } from '@/shared/ui/usePager'
import { useStudents } from '../hooks'
import { TURNO_LABEL } from '../schemas'

type EstudanteLer = components['schemas']['EstudanteLer']

function StopNameCell({ id }: { id: number | null }): ReactNode {
  return useStopName(id)
}

export function StudentListPage() {
  const pager = usePager()
  const { role } = useAuth()
  const [busca, setBusca] = useState('')
  const query = useStudents(pager, busca.trim())
  const canCreate = role !== null && canWrite(role, 'students')
  const rows = query.data?.itens ?? []

  const columns = [
    { key: 'nome', header: 'Nome', cell: (aluno: EstudanteLer) => aluno.nome },
    { key: 'nascimento', header: 'Nascimento', cell: (aluno: EstudanteLer) => formatDate(aluno.data_nascimento) },
    { key: 'turno', header: 'Turno', cell: (aluno: EstudanteLer) => TURNO_LABEL[aluno.turno] },
    { key: 'parada', header: 'Parada', cell: (aluno: EstudanteLer) => <StopNameCell id={aluno.parada_id} /> },
  ]

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Estudantes"
        description={query.data ? `${query.data.total} no total` : 'Estudantes atendidos pelo transporte'}
        actions={
          canCreate && (
            <Button asChild>
              <Link to="/students/new">
                <Plus aria-hidden="true" />
                Novo estudante
              </Link>
            </Button>
          )
        }
      >
        <div className="w-full sm:w-72">
          <FloatingField
            label="Buscar por nome"
            value={busca}
            onChange={(e) => {
              setBusca(e.target.value)
              pager.reset()
            }}
          />
        </div>
      </PageHeader>
      <Panel dense className="p-0 lg:p-0">
        {query.isPending && <PageState status="loading" />}
        {query.isError && (
          <PageState status="error" error={query.error} onRetry={() => void query.refetch()} />
        )}
        {query.isSuccess && rows.length === 0 && (
          <PageState status="empty" emptyText="Nenhum estudante encontrado" />
        )}
        {query.isSuccess && rows.length > 0 && (
          <DataTable embedded columns={columns} rows={rows} rowHref={(aluno) => `/students/${aluno.id}`} />
        )}
        {query.isSuccess && <Pager pager={pager} rows={rows} />}
      </Panel>
    </div>
  )
}
