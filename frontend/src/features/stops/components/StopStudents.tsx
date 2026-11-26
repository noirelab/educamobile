import { PageState } from '@/shared/ui/PageState'
import { useStopStudents } from '../hooks'

// A associação de estudante à parada passou a ser a inscrição na rota (etapa B).
// Esta lista é só de consulta.
export function StopStudents({ stopId }: { stopId: number }) {
  const students = useStopStudents(stopId)

  return (
    <div className="flex flex-col gap-3">
      {students.isPending && <PageState status="loading" />}
      {students.isError && (
        <PageState status="error" error={students.error} onRetry={() => void students.refetch()} />
      )}
      {students.isSuccess && students.data.length === 0 && (
        <PageState status="empty" emptyText="Nenhum estudante nesta parada" />
      )}
      {students.isSuccess && students.data.length > 0 && (
        <ul role="list" aria-label="Estudantes da parada" className="divide-y divide-line">
          {students.data.map((student) => (
            <li key={student.id} className="py-3 text-body font-medium text-ink">
              {student.nome}
            </li>
          ))}
        </ul>
      )}
      <p className="text-caption text-ink-muted">
        Para mudar onde a criança embarca, ajuste a inscrição dela na rota.
      </p>
    </div>
  )
}
