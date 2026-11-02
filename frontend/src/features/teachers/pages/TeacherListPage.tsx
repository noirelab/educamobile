import { Pencil, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { components } from '@/shared/api/schema'
import { canWrite } from '@/shared/auth/permissions'
import { useAuth } from '@/shared/auth/useAuth'
import { Button } from '@/shared/ui/button'
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog'
import { DataTable } from '@/shared/ui/DataTable'
import { Field } from '@/shared/ui/Field'
import { PageHeader } from '@/shared/ui/PageHeader'
import { PageState } from '@/shared/ui/PageState'
import { Pager } from '@/shared/ui/Pager'
import { Panel } from '@/shared/ui/Panel'
import { notifySuccess } from '@/shared/ui/toast'
import { usePager } from '@/shared/ui/usePager'
import { useDeleteTeacher, useSchoolOptions, useTeachers } from '../hooks'

type ProfessorLer = components['schemas']['ProfessorLer']

export function TeacherListPage() {
  const pager = usePager()
  const { role, user } = useAuth()
  const isDiretor = role === 'diretor'
  const [schoolFilter, setSchoolFilter] = useState<number | undefined>(undefined)
  const escolaId = isDiretor ? (user?.escola_id ?? undefined) : schoolFilter
  const query = useTeachers(pager, escolaId)
  const schools = useSchoolOptions()
  const remove = useDeleteTeacher()
  const canEdit = role !== null && canWrite(role, 'teachers')
  const schoolNames = new Map((schools.data ?? []).map((school) => [school.id, school.nome]))

  function handleSchoolChange(value: string) {
    setSchoolFilter(value === '' ? undefined : Number(value))
    pager.reset()
  }

  const columns = [
    {
      key: 'nome',
      header: 'Nome',
      cell: (professor: ProfessorLer) =>
        canEdit ? (
          <Link to={`/teachers/${professor.id}/edit`} className="text-ink">
            {professor.nome}
          </Link>
        ) : (
          professor.nome
        ),
    },
    { key: 'email', header: 'E-mail', cell: (professor: ProfessorLer) => professor.email },
    ...(isDiretor
      ? []
      : [
          {
            key: 'escola',
            header: 'Escola',
            cell: (professor: ProfessorLer) =>
              professor.escola_id === null ? 'Sem escola' : (schoolNames.get(professor.escola_id) ?? '—'),
          },
        ]),
    ...(canEdit
      ? [
          {
            key: 'acoes',
            header: 'Ações',
            cell: (professor: ProfessorLer) => (
              <div className="flex justify-end gap-1">
                <Button variant="ghost" size="icon" asChild>
                  <Link to={`/teachers/${professor.id}/edit`} aria-label={`Editar professor ${professor.nome}`}>
                    <Pencil aria-hidden="true" />
                  </Link>
                </Button>
                <ConfirmDialog
                  trigger={
                    <Button variant="ghost" size="icon" aria-label={`Excluir professor ${professor.nome}`}>
                      <Trash2 aria-hidden="true" />
                    </Button>
                  }
                  title="Excluir professor"
                  description="Esta ação não pode ser desfeita."
                  confirmLabel="Excluir"
                  onConfirm={async () => {
                    await remove.mutateAsync(professor.id)
                    notifySuccess('Professor excluído')
                  }}
                />
              </div>
            ),
          },
        ]
      : []),
  ]

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Professores"
        description={isDiretor ? 'Professores da sua escola' : 'Professores da rede municipal'}
        actions={
          canEdit && (
            <Button asChild>
              <Link to="/teachers/new">
                <Plus aria-hidden="true" />
                Novo professor
              </Link>
            </Button>
          )
        }
      >
        {!isDiretor && (
          <div className="w-full sm:w-72">
            <Field label="Escola">
              <select
                id="teacher-school-filter"
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
          <PageState status="empty" emptyText="Nenhum professor cadastrado" />
        )}
        {query.isSuccess && query.data.length > 0 && <DataTable embedded columns={columns} rows={query.data} />}
        {query.isSuccess && <Pager pager={pager} rows={query.data} />}
      </Panel>
    </div>
  )
}
