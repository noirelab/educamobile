import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import { useState } from 'react'
import { errorMessage } from '@/shared/api/errors'
import { Button } from '@/shared/ui/button'
import { Field } from '@/shared/ui/Field'
import { PageState } from '@/shared/ui/PageState'
import { usePager } from '@/shared/ui/usePager'
import { notifySuccess } from '@/shared/ui/toast'
import { useAttachStudent, useDetachStudent, useStopStudents, useStudentsPage } from '../hooks'

type StopStudentsProps = { stopId: number; canWrite: boolean }

export function StopStudents({ stopId, canWrite }: StopStudentsProps) {
  const students = useStopStudents(stopId)
  const pager = usePager(20)
  const candidates = useStudentsPage({ limit: pager.limit, offset: pager.offset }, canWrite)
  const attach = useAttachStudent(stopId)
  const detach = useDetachStudent(stopId)
  const [selected, setSelected] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)

  const associatedIds = new Set((students.data ?? []).map((student) => student.id))
  const options = (candidates.data ?? []).filter((student) => !associatedIds.has(student.id))

  async function handleAttach() {
    if (selected === '') return
    setActionError(null)
    try {
      await attach.mutateAsync(Number(selected))
      setSelected('')
      notifySuccess('Estudante associado')
    } catch (error) {
      setActionError(errorMessage(error))
    }
  }

  async function handleDetach(studentId: number) {
    setActionError(null)
    try {
      await detach.mutateAsync(studentId)
      notifySuccess('Estudante removido')
    } catch (error) {
      setActionError(errorMessage(error))
    }
  }

  return (
    <div className="flex flex-col gap-5">
      {students.isPending && <PageState status="loading" />}
      {students.isError && (
        <PageState status="error" error={students.error} onRetry={() => void students.refetch()} />
      )}
      {students.isSuccess && students.data.length === 0 && (
        <PageState status="empty" emptyText="Nenhum estudante associado" />
      )}
      {students.isSuccess && students.data.length > 0 && (
        <ul role="list" aria-label="Estudantes da parada" className="divide-y divide-line">
          {students.data.map((student) => (
            <li key={student.id} className="flex items-center justify-between gap-3 py-3">
              <span className="text-body font-medium text-ink">{student.nome}</span>
              {canWrite && (
                <Button variant="ghost" size="sm" onClick={() => void handleDetach(student.id)}>
                  <X aria-hidden="true" />
                  Remover
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {canWrite && (
        <div className="flex flex-col gap-3 border-t border-line pt-5">
          <div className="flex flex-col gap-3 md:flex-row md:items-end">
            <div className="relative min-w-0 flex-1">
              <Field label="Estudante">
                <select value={selected} onChange={(event) => setSelected(event.target.value)}>
                  <option value="">Selecione um estudante</option>
                  {options.map((student) => (
                    <option key={student.id} value={String(student.id)}>
                      {student.nome}
                    </option>
                  ))}
                </select>
              </Field>
              <div className="absolute right-0 top-0 flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  aria-label="Anterior"
                  onClick={pager.prev}
                  disabled={!pager.hasPrev}
                >
                  <ChevronLeft aria-hidden="true" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  aria-label="Próxima"
                  onClick={pager.next}
                  disabled={!pager.hasNext(candidates.data ?? [])}
                >
                  <ChevronRight aria-hidden="true" />
                </Button>
              </div>
            </div>
            <Button onClick={() => void handleAttach()} disabled={selected === '' || attach.isPending}>
              Associar
            </Button>
          </div>
          {actionError && (
            <p role="alert" className="text-caption text-danger">
              {actionError}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
