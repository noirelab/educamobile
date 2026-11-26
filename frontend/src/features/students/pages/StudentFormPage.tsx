import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useAllSchools } from '@/features/schools/hooks'
import { ApiError } from '@/shared/api/errors'
import type { components } from '@/shared/api/schema'
import { Button } from '@/shared/ui/button'
import { Field } from '@/shared/ui/Field'
import { FloatingField } from '@/shared/ui/FloatingField'
import { PageHeader } from '@/shared/ui/PageHeader'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import { notifyError, notifySuccess } from '@/shared/ui/toast'
import { useSaveStudent, useStopOptions, useStudent } from '../hooks'
import { studentSchema, TURNO_LABEL, TURNOS, type StudentFormValues } from '../schemas'

type EstudanteLer = components['schemas']['EstudanteLer']
type EstudanteCriar = components['schemas']['EstudanteCriar']

const FORM_FIELDS = ['nome', 'data_nascimento', 'escola_id', 'turno', 'parada_id', 'observacoes_cuidado'] as const
type FormField = (typeof FORM_FIELDS)[number]

function isFormField(field: string): field is FormField {
  return (FORM_FIELDS as readonly string[]).includes(field)
}

function toPayload(values: StudentFormValues): EstudanteCriar {
  const observacoes = values.observacoes_cuidado.trim()
  return {
    nome: values.nome.trim(),
    data_nascimento: values.data_nascimento,
    escola_id: Number(values.escola_id),
    turno: values.turno,
    parada_id: values.parada_id === '' ? null : Number(values.parada_id),
    observacoes_cuidado: observacoes === '' ? null : observacoes,
  }
}

function StudentForm({ student }: { student?: EstudanteLer }) {
  const navigate = useNavigate()
  const schools = useAllSchools()
  const stops = useStopOptions(true)
  const save = useSaveStudent(student?.id)
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<StudentFormValues>({
    resolver: zodResolver(studentSchema),
    defaultValues: {
      nome: student?.nome ?? '',
      data_nascimento: student?.data_nascimento ?? '',
      escola_id: student ? String(student.escola_id) : '',
      turno: student?.turno ?? 'manha',
      parada_id: String(student?.parada_id ?? ''),
      observacoes_cuidado: student?.observacoes_cuidado ?? '',
    },
  })

  if (schools.isPending || stops.isPending) return <PageState status="loading" />
  if (schools.isError) {
    return <PageState status="error" error={schools.error} onRetry={() => void schools.refetch()} />
  }

  function applyServerError(e: unknown) {
    if (!(e instanceof ApiError)) {
      notifyError(e)
      return
    }
    const fieldEntries = Object.entries(e.fieldErrors)
    for (const [field, message] of fieldEntries) {
      if (isFormField(field)) setError(field, { message })
    }
    if (fieldEntries.length > 0) return
    notifyError(e)
  }

  async function onSubmit(values: StudentFormValues) {
    try {
      const saved = await save.mutateAsync(toPayload(values))
      notifySuccess('Estudante salvo')
      navigate(`/students/${saved.id}`)
    } catch (e) {
      applyServerError(e)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={student ? 'Editar estudante' : 'Novo estudante'}
        description="Só o necessário para o transporte: sem endereço da casa"
      />
      <Panel dense className="max-w-[720px] p-6 lg:p-6">
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid gap-x-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <FloatingField label="Nome" error={errors.nome?.message} {...register('nome')} />
          </div>
          <Field label="Data de nascimento" error={errors.data_nascimento?.message}>
            <input type="date" {...register('data_nascimento')} />
          </Field>
          <Field label="Turno" error={errors.turno?.message}>
            <select {...register('turno')}>
              {TURNOS.map((turno) => (
                <option key={turno} value={turno}>
                  {TURNO_LABEL[turno]}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Escola" error={errors.escola_id?.message}>
            <select {...register('escola_id')}>
              <option value="">Selecione a escola</option>
              {(schools.data ?? []).map((escola) => (
                <option key={escola.id} value={String(escola.id)}>
                  {escola.nome}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Parada" error={errors.parada_id?.message}>
            <select {...register('parada_id')}>
              <option value="">Sem parada</option>
              {(stops.data ?? []).map((parada) => (
                <option key={parada.id} value={String(parada.id)}>
                  {parada.nome}
                </option>
              ))}
            </select>
          </Field>
          <div className="sm:col-span-2">
            <FloatingField
              label="Observações de cuidado (alergia, necessidade especial)"
              error={errors.observacoes_cuidado?.message}
              {...register('observacoes_cuidado')}
            />
          </div>
          <div className="flex justify-end gap-2 pt-6 sm:col-span-2">
            <Button variant="ghost" asChild>
              <Link to={student ? `/students/${student.id}` : '/students'}>Cancelar</Link>
            </Button>
            <Button type="submit" disabled={save.isPending}>
              Salvar
            </Button>
          </div>
        </form>
      </Panel>
    </div>
  )
}

function EditStudentForm({ studentId }: { studentId: number }) {
  const query = useStudent(studentId)

  if (query.isPending) return <PageState status="loading" />
  if (query.isError) {
    return <PageState status="error" error={query.error} onRetry={() => void query.refetch()} />
  }

  return <StudentForm student={query.data} />
}

export function StudentFormPage() {
  const { id } = useParams()
  if (id === undefined) return <StudentForm />
  return <EditStudentForm studentId={Number(id)} />
}
