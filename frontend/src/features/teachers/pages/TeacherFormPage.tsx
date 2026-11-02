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
import { useSaveTeacher, useSchoolOptions, useTeacher } from '../hooks'
import { teacherSchema, type TeacherFormValues } from '../schemas'

type ProfessorLer = components['schemas']['ProfessorLer']
type ProfessorCriar = components['schemas']['ProfessorCriar']
type EscolaLer = components['schemas']['EscolaLer']

const FORM_FIELDS = ['nome', 'email', 'escola_id'] as const
type FormField = (typeof FORM_FIELDS)[number]

const EMAIL_CONFLICT = 'E-mail já cadastrado'

function isFormField(field: string): field is FormField {
  return (FORM_FIELDS as readonly string[]).includes(field)
}

function toPayload(values: TeacherFormValues): ProfessorCriar {
  return {
    nome: values.nome,
    email: values.email.toLowerCase(),
    escola_id: values.escola_id === '' ? null : Number(values.escola_id),
  }
}

type TeacherFormProps = { professor?: ProfessorLer; schools: EscolaLer[] }

function TeacherForm({ professor, schools }: TeacherFormProps) {
  const navigate = useNavigate()
  const { role, user } = useAuth()
  const save = useSaveTeacher(professor?.id)
  const lockedSchoolId = role === 'diretor' ? (user?.escola_id ?? null) : null
  const lockedSchool = schools.find((school) => school.id === lockedSchoolId)
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<TeacherFormValues>({
    resolver: zodResolver(teacherSchema),
    defaultValues: {
      nome: professor?.nome ?? '',
      email: professor?.email ?? '',
      escola_id: String(lockedSchoolId ?? professor?.escola_id ?? ''),
    },
  })

  function applyServerError(e: unknown) {
    if (!(e instanceof ApiError)) {
      notifyError(e)
      return
    }
    if (e.status === 409) {
      setError('email', { message: EMAIL_CONFLICT })
      return
    }
    const fieldEntries = Object.entries(e.fieldErrors)
    for (const [field, message] of fieldEntries) {
      if (isFormField(field)) setError(field, { message })
    }
    if (fieldEntries.length > 0) return
    notifyError(e)
  }

  async function onSubmit(values: TeacherFormValues) {
    try {
      await save.mutateAsync(toPayload(values))
      notifySuccess('Professor salvo')
      navigate('/teachers')
    } catch (e) {
      applyServerError(e)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={professor ? 'Editar professor' : 'Novo professor'}
        description="Dados do professor e escola de lotação"
      />
      <Panel dense className="max-w-[720px] p-6 lg:p-6">
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid gap-x-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <FloatingField label="Nome" error={errors.nome?.message} {...register('nome')} />
          </div>
          <div className="sm:col-span-2">
            <FloatingField
              label="E-mail"
              type="email"
              inputMode="email"
              autoComplete="off"
              error={errors.email?.message}
              {...register('email')}
            />
          </div>
          <div className="sm:col-span-2">
            {lockedSchoolId === null ? (
              <Field label="Escola" error={errors.escola_id?.message}>
                <select {...register('escola_id')}>
                  <option value="">Sem escola</option>
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
          <div className="flex justify-end gap-2 pt-6 sm:col-span-2">
            <Button variant="ghost" asChild>
              <Link to="/teachers">Cancelar</Link>
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

function EditTeacherForm({ teacherId, schools }: { teacherId: number; schools: EscolaLer[] }) {
  const query = useTeacher(teacherId)

  if (query.isPending) return <PageState status="loading" />
  if (query.isError) {
    return <PageState status="error" error={query.error} onRetry={() => void query.refetch()} />
  }

  return <TeacherForm professor={query.data} schools={schools} />
}

export function TeacherFormPage() {
  const { id } = useParams()
  const schools = useSchoolOptions()

  if (schools.isPending) return <PageState status="loading" />
  if (schools.isError) {
    return <PageState status="error" error={schools.error} onRetry={() => void schools.refetch()} />
  }

  if (id === undefined) return <TeacherForm schools={schools.data} />

  return <EditTeacherForm teacherId={Number(id)} schools={schools.data} />
}
