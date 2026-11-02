import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError } from '@/shared/api/errors'
import type { components } from '@/shared/api/schema'
import { useAuth } from '@/shared/auth/useAuth'
import { Button } from '@/shared/ui/button'
import { Field } from '@/shared/ui/Field'
import { FloatingField } from '@/shared/ui/FloatingField'
import { PageHeader } from '@/shared/ui/PageHeader'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import { notifyError, notifySuccess } from '@/shared/ui/toast'
import { TURNO_LABEL, TURNO_OPTIONS } from '../labels'
import { useClass, useSaveClass, useSchoolOptions } from '../hooks'
import { classSchema, type ClassFormValues } from '../schemas'

type TurmaLer = components['schemas']['TurmaLer']
type TurmaCriar = components['schemas']['TurmaCriar']
type EscolaLer = components['schemas']['EscolaLer']

const FORM_FIELDS = ['escola_id', 'nome', 'serie', 'turno', 'ano_letivo'] as const
type FormField = (typeof FORM_FIELDS)[number]

function isFormField(field: string): field is FormField {
  return (FORM_FIELDS as readonly string[]).includes(field)
}

function toPayload(values: ClassFormValues): TurmaCriar {
  return {
    escola_id: Number(values.escola_id),
    nome: values.nome,
    serie: values.serie,
    turno: values.turno,
    ano_letivo: Number(values.ano_letivo),
  }
}

type ClassFormProps = { turma?: TurmaLer; schools: EscolaLer[] }

function ClassForm({ turma, schools }: ClassFormProps) {
  const navigate = useNavigate()
  const { role, user } = useAuth()
  const save = useSaveClass(turma?.id)
  const lockedSchoolId = role === 'diretor' ? (user?.escola_id ?? null) : null
  const lockedSchool = schools.find((school) => school.id === lockedSchoolId)
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<ClassFormValues>({
    resolver: zodResolver(classSchema),
    defaultValues: {
      escola_id: String(lockedSchoolId ?? turma?.escola_id ?? ''),
      nome: turma?.nome ?? '',
      serie: turma?.serie ?? '',
      turno: turma?.turno ?? 'manha',
      ano_letivo: String(turma?.ano_letivo ?? new Date().getFullYear()),
    },
  })

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

  async function onSubmit(values: ClassFormValues) {
    try {
      const saved = await save.mutateAsync(toPayload(values))
      notifySuccess('Turma salva')
      navigate(`/classes/${saved.id}`)
    } catch (e) {
      applyServerError(e)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={turma ? 'Editar turma' : 'Nova turma'}
        description="Dados da turma e escola à qual pertence"
      />
      <Panel dense className="max-w-[720px] p-6 lg:p-6">
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid gap-x-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            {lockedSchoolId === null ? (
              <Field label="Escola" error={errors.escola_id?.message}>
                <select {...register('escola_id')}>
                  <option value="">Selecione a escola</option>
                  {schools.map((school) => (
                    <option key={school.id} value={String(school.id)}>
                      {school.nome}
                    </option>
                  ))}
                </select>
              </Field>
            ) : (
              <Field label="Escola">
                <select disabled value={String(lockedSchoolId)} onChange={() => undefined}>
                  <option value={String(lockedSchoolId)}>{lockedSchool?.nome ?? 'Minha escola'}</option>
                </select>
              </Field>
            )}
          </div>
          <div className="sm:col-span-2">
            <FloatingField label="Nome" error={errors.nome?.message} {...register('nome')} />
          </div>
          <FloatingField label="Série" error={errors.serie?.message} {...register('serie')} />
          <Field label="Turno" error={errors.turno?.message}>
            <select {...register('turno')}>
              {TURNO_OPTIONS.map((turno) => (
                <option key={turno} value={turno}>
                  {TURNO_LABEL[turno]}
                </option>
              ))}
            </select>
          </Field>
          <FloatingField
            label="Ano letivo"
            type="number"
            inputMode="numeric"
            error={errors.ano_letivo?.message}
            {...register('ano_letivo')}
          />
          <div className="flex justify-end gap-2 pt-6 sm:col-span-2">
            <Button variant="ghost" asChild>
              <Link to={turma ? `/classes/${turma.id}` : '/classes'}>Cancelar</Link>
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

function EditClassForm({ classId, schools }: { classId: number; schools: EscolaLer[] }) {
  const query = useClass(classId)

  if (query.isPending) return <PageState status="loading" />
  if (query.isError) {
    return <PageState status="error" error={query.error} onRetry={() => void query.refetch()} />
  }

  return <ClassForm turma={query.data} schools={schools} />
}

export function ClassFormPage() {
  const { id } = useParams()
  const schools = useSchoolOptions()

  if (schools.isPending) return <PageState status="loading" />
  if (schools.isError) {
    return <PageState status="error" error={schools.error} onRetry={() => void schools.refetch()} />
  }

  if (id === undefined) return <ClassForm schools={schools.data} />

  return <EditClassForm classId={Number(id)} schools={schools.data} />
}
