import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { canWrite } from '@/shared/auth/permissions'
import { useAuth } from '@/shared/auth/useAuth'
import { Button } from '@/shared/ui/button'
import { DataTable } from '@/shared/ui/DataTable'
import { Field } from '@/shared/ui/Field'
import { PageHeader } from '@/shared/ui/PageHeader'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import { Pager } from '@/shared/ui/Pager'
import { usePager } from '@/shared/ui/usePager'
import type { components } from '@/shared/api/schema'
import { TURNO_LABEL } from '../labels'
import { useClasses, useSchoolOptions } from '../hooks'

type TurmaLer = components['schemas']['TurmaLer']

export function ClassListPage() {
  const pager = usePager()
  const { role, user } = useAuth()
  const isDiretor = role === 'diretor'
  const [schoolFilter, setSchoolFilter] = useState<number | undefined>(undefined)
  const escolaId = isDiretor ? (user?.escola_id ?? undefined) : schoolFilter
  const query = useClasses(pager, escolaId)
  const schools = useSchoolOptions()
  const canEdit = role !== null && canWrite(role, 'classes')
  const schoolNames = new Map((schools.data ?? []).map((school) => [school.id, school.nome]))

  function handleSchoolChange(value: string) {
    setSchoolFilter(value === '' ? undefined : Number(value))
    pager.reset()
  }

  const columns = [
    { key: 'nome', header: 'Nome', cell: (turma: TurmaLer) => turma.nome },
    { key: 'serie', header: 'Série', cell: (turma: TurmaLer) => turma.serie },
    { key: 'turno', header: 'Turno', cell: (turma: TurmaLer) => TURNO_LABEL[turma.turno] },
    { key: 'ano', header: 'Ano letivo', cell: (turma: TurmaLer) => turma.ano_letivo },
    ...(isDiretor
      ? []
      : [
          {
            key: 'escola',
            header: 'Escola',
            cell: (turma: TurmaLer) => schoolNames.get(turma.escola_id) ?? '—',
          },
        ]),
  ]

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Turmas"
        description={isDiretor ? 'Turmas da sua escola' : 'Turmas da rede municipal'}
        actions={
          canEdit && (
            <Button asChild>
              <Link to="/classes/new">
                <Plus aria-hidden="true" />
                Nova turma
              </Link>
            </Button>
          )
        }
      >
        {!isDiretor && (
          <div className="w-full sm:w-72">
            <Field label="Escola">
              <select
                id="class-school-filter"
                value={schoolFilter === undefined ? '' : String(schoolFilter)}
                onChange={(e) => handleSchoolChange(e.target.value)}
              >
                <option value="">Todas as escolas</option>
                {(schools.data ?? []).map((school) => (
                  <option key={school.id} value={String(school.id)}>
                    {school.nome}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        )}
      </PageHeader>
      <Panel dense className="p-0 lg:p-0">
        {query.isPending && <PageState status="loading" />}
        {query.isError && (
          <PageState status="error" error={query.error} onRetry={() => void query.refetch()} />
        )}
        {query.isSuccess && query.data.length === 0 && (
          <PageState status="empty" emptyText="Nenhuma turma cadastrada" />
        )}
        {query.isSuccess && query.data.length > 0 && (
          <DataTable
            embedded
            columns={columns}
            rows={query.data}
            rowHref={(turma) => `/classes/${turma.id}`}
          />
        )}
        {query.isSuccess && <Pager pager={pager} rows={query.data} />}
      </Panel>
    </div>
  )
}
