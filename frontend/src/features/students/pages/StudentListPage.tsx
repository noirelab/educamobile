import { Plus } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useStopName } from '@/features/stops/hooks'
import type { components } from '@/shared/api/schema'
import { canWrite } from '@/shared/auth/permissions'
import { useAuth } from '@/shared/auth/useAuth'
import { formatDate } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { DataTable } from '@/shared/ui/DataTable'
import { PageHeader } from '@/shared/ui/PageHeader'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import { Pager } from '@/shared/ui/Pager'
import { usePager } from '@/shared/ui/usePager'
import { useStudents } from '../hooks'

type EstudanteLer = components['schemas']['EstudanteLer']

function StopNameCell({ id }: { id: number | null }): ReactNode {
  return useStopName(id)
}

export function StudentListPage() {
  const pager = usePager()
  const { role } = useAuth()
  const query = useStudents(pager)
  const isDiretor = role === 'diretor'
  const canCreate = role !== null && canWrite(role, 'students')

  const columns = [
    { key: 'nome', header: 'Nome', cell: (aluno: EstudanteLer) => aluno.nome },
    { key: 'nascimento', header: 'Nascimento', cell: (aluno: EstudanteLer) => formatDate(aluno.data_nascimento) },
    { key: 'responsavel', header: 'Responsável', cell: (aluno: EstudanteLer) => aluno.nome_responsavel ?? '—' },
    { key: 'parada', header: 'Parada', cell: (aluno: EstudanteLer) => <StopNameCell id={aluno.parada_id} /> },
  ]

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Estudantes"
        description={isDiretor ? 'Estudantes da sua escola' : 'Estudantes da rede'}
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
      />
      <Panel dense className="p-0 lg:p-0">
        {query.isPending && <PageState status="loading" />}
        {query.isError && (
          <PageState status="error" error={query.error} onRetry={() => void query.refetch()} />
        )}
        {query.isSuccess && query.data.length === 0 && (
          <PageState status="empty" emptyText="Nenhum estudante cadastrado" />
        )}
        {query.isSuccess && query.data.length > 0 && (
          <DataTable
            embedded
            columns={columns}
            rows={query.data}
            rowHref={(aluno) => `/students/${aluno.id}`}
          />
        )}
        {query.isSuccess && <Pager pager={pager} rows={query.data} />}
      </Panel>
    </div>
  )
}
