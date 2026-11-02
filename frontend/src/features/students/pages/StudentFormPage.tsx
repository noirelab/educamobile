import { zodResolver } from '@hookform/resolvers/zod'
import { useMemo } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useClassesInScope } from '@/features/classes/hooks'
import { ApiError } from '@/shared/api/errors'
import type { components } from '@/shared/api/schema'
import { useAuth } from '@/shared/auth/useAuth'
import { todayLocal } from '@/shared/lib/format'
import { PointPicker } from '@/shared/map/PointPicker'
import { Button } from '@/shared/ui/button'
import { Field } from '@/shared/ui/Field'
import { FloatingField } from '@/shared/ui/FloatingField'
import { PageHeader } from '@/shared/ui/PageHeader'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import { notifyError, notifySuccess } from '@/shared/ui/toast'
import { useSaveStudent, useStopOptions, useStudent } from '../hooks'
import { buildStudentSchema, type StudentFormValues } from '../schemas'

type EstudanteLer = components['schemas']['EstudanteLer']
type EstudanteCadastrar = components['schemas']['EstudanteCadastrar']

const FORM_FIELDS = ['nome', 'data_nascimento', 'nome_responsavel', 'localizacao', 'parada_id', 'turma_id', 'data_inicio'] as const
type FormField = (typeof FORM_FIELDS)[number]

function isFormField(field: string): field is FormField {
  return (FORM_FIELDS as readonly string[]).includes(field)
}

function toPayload(values: StudentFormValues, isAdmin: boolean, isCreate: boolean): EstudanteCadastrar {
  const nomeResponsavel = values.nome_responsavel.trim()
  const base = {
    nome: values.nome.trim(),
    data_nascimento: values.data_nascimento,
    nome_responsavel: nomeResponsavel === '' ? null : nomeResponsavel,
    localizacao: values.localizacao,
    ...(isAdmin ? { parada_id: values.parada_id === '' ? null : Number(values.parada_id) } : {}),
  }
  if (!isCreate || values.turma_id === '') return base
  return {
    ...base,
    matricula: { turma_id: Number(values.turma_id), data_inicio: values.data_inicio },
  }
}

type StudentFormProps = { student?: EstudanteLer }

function StudentForm({ student }: StudentFormProps) {
  const navigate = useNavigate()
  const { role } = useAuth()
  const isAdmin = role === 'admin'
  const isDiretor = role === 'diretor'
  const isCreate = student === undefined
  const classes = useClassesInScope()
  const stops = useStopOptions(isAdmin)
  const save = useSaveStudent(student?.id)
  const schema = useMemo(() => buildStudentSchema({ isCreate, isDiretor }), [isCreate, isDiretor])
  const {
    register,
    handleSubmit,
    setError,
    control,
    formState: { errors },
  } = useForm<StudentFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      nome: student?.nome ?? '',
      data_nascimento: student?.data_nascimento ?? '',
      nome_responsavel: student?.nome_responsavel ?? '',
      localizacao: student?.localizacao ?? null,
      turma_id: '',
      data_inicio: todayLocal(),
      parada_id: String(student?.parada_id ?? ''),
    },
  })

  if (classes.isPending || (isAdmin && stops.isPending)) return <PageState status="loading" />
  if (classes.isError) {
    return <PageState status="error" error={classes.error} onRetry={() => void classes.refetch()} />
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
      const saved = await save.mutateAsync(toPayload(values, isAdmin, isCreate))
      notifySuccess('Estudante salvo')
      navigate(`/students/${saved.id}`)
    } catch (e) {
      applyServerError(e)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={isCreate ? 'Novo estudante' : 'Editar estudante'}
        description="Dados do estudante e da sua matrícula"
      />
      <Panel dense className="max-w-[720px] p-6 lg:p-6">
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-6">
          <section className="grid gap-x-4 sm:grid-cols-2">
            <h2 className="mb-2 text-section font-semibold text-ink sm:col-span-2">Dados do estudante</h2>
            <div className="sm:col-span-2">
              <FloatingField label="Nome" error={errors.nome?.message} {...register('nome')} />
            </div>
            <Field label="Data de nascimento" error={errors.data_nascimento?.message}>
              <input type="date" {...register('data_nascimento')} />
            </Field>
            <FloatingField label="Responsável" error={errors.nome_responsavel?.message} {...register('nome_responsavel')} />
            <div className="flex flex-col gap-2 sm:col-span-2">
              <span className="text-label text-ink-muted">Localização (opcional)</span>
              <Controller
                name="localizacao"
                control={control}
                render={({ field }) => <PointPicker value={field.value} onChange={field.onChange} />}
              />
            </div>
          </section>

          {isCreate && (
            <section className="grid gap-x-4 sm:grid-cols-2">
              <h2 className="mb-2 text-section font-semibold text-ink sm:col-span-2">Matrícula</h2>
              {isAdmin && <p className="mb-2 text-caption text-ink-muted sm:col-span-2">Opcional para administrador</p>}
              <div className="sm:col-span-2">
                <Field label="Turma" error={errors.turma_id?.message}>
                  <select {...register('turma_id')}>
                    <option value="">Selecione a turma</option>
                    {(classes.data ?? []).map((turma) => (
                      <option key={turma.id} value={String(turma.id)}>
                        {turma.nome}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>
              <Field label="Data de início" error={errors.data_inicio?.message}>
                <input type="date" {...register('data_inicio')} />
              </Field>
            </section>
          )}

          {isAdmin && (
            <section className="grid gap-x-4 sm:grid-cols-2">
              <h2 className="mb-2 text-section font-semibold text-ink sm:col-span-2">Transporte</h2>
              <div className="sm:col-span-2">
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
              </div>
            </section>
          )}

          <div className="flex justify-end gap-2 pt-2">
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
