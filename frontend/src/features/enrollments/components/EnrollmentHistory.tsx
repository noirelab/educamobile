import type { ReactNode } from 'react'
import { useClassName } from '@/features/classes/hooks'
import type { components } from '@/shared/api/schema'
import { formatDate } from '@/shared/lib/format'
import { Badge } from '@/shared/ui/badge'
import { DataTable } from '@/shared/ui/DataTable'
import { PageState } from '@/shared/ui/PageState'
import { ENROLLMENT_STATUS_LABEL, ENROLLMENT_STATUS_VARIANT } from '../labels'
import { useEnrollmentHistory } from '../hooks'
import { CloseEnrollmentDialog } from './CloseEnrollmentDialog'
import { EnrollDialog } from './EnrollDialog'
import { TransferDialog } from './TransferDialog'

type MatriculaLer = components['schemas']['MatriculaLer']

function ClassNameCell({ id }: { id: number }): ReactNode {
  return useClassName(id)
}

function ActiveActions({ matricula }: { matricula: MatriculaLer }): ReactNode {
  if (matricula.status !== 'ativa') return null
  return (
    <div className="flex justify-end gap-2">
      <TransferDialog matricula={matricula} />
      <CloseEnrollmentDialog matricula={matricula} />
    </div>
  )
}

export function EnrollmentHistory({ studentId }: { studentId: number }) {
  const query = useEnrollmentHistory(studentId)

  if (query.isPending) return <PageState status="loading" />
  if (query.isError) {
    return <PageState status="error" error={query.error} onRetry={() => void query.refetch()} />
  }

  const matriculas = query.data
  const hasActive = matriculas.some((matricula) => matricula.status === 'ativa')

  return (
    <div className="flex flex-col gap-4">
      {!hasActive && (
        <div className="flex justify-end">
          <EnrollDialog studentId={studentId} />
        </div>
      )}
      {matriculas.length === 0 ? (
        <PageState status="empty" emptyText="Nenhuma matrícula registrada" />
      ) : (
        <DataTable
          embedded
          rows={matriculas}
          columns={[
            { key: 'turma', header: 'Turma', cell: (m: MatriculaLer) => <ClassNameCell id={m.turma_id} /> },
            { key: 'inicio', header: 'Início', cell: (m: MatriculaLer) => formatDate(m.data_inicio) },
            {
              key: 'fim',
              header: 'Fim',
              cell: (m: MatriculaLer) => (m.data_fim ? formatDate(m.data_fim) : '—'),
            },
            {
              key: 'situacao',
              header: 'Situação',
              cell: (m: MatriculaLer) => (
                <Badge variant={ENROLLMENT_STATUS_VARIANT[m.status]}>{ENROLLMENT_STATUS_LABEL[m.status]}</Badge>
              ),
            },
            { key: 'acoes', header: 'Ações', cell: (m: MatriculaLer) => <ActiveActions matricula={m} /> },
          ]}
        />
      )}
    </div>
  )
}
