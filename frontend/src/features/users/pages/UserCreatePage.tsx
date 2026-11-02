import { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { CheckCircle2, Eye, EyeOff, Info } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { ApiError } from '@/shared/api/errors'
import type { components } from '@/shared/api/schema'
import { cn } from '@/shared/lib/utils'
import { Button } from '@/shared/ui/button'
import { Field } from '@/shared/ui/Field'
import { FloatingField } from '@/shared/ui/FloatingField'
import { PageHeader } from '@/shared/ui/PageHeader'
import { PageState } from '@/shared/ui/PageState'
import { PasswordStrength } from '@/shared/ui/PasswordStrength'
import { Panel } from '@/shared/ui/Panel'
import { notifyError } from '@/shared/ui/toast'
import { PERFIL_LABEL } from '../labels'
import { useCreateUser, useSchoolOptions } from '../hooks'
import { userCreateSchema, type UserCreateValues } from '../schemas'

type UsuarioLer = components['schemas']['UsuarioLer']
type UsuarioCriar = components['schemas']['UsuarioCriar']
type EscolaLer = components['schemas']['EscolaLer']
type Perfil = components['schemas']['Perfil']

const FORM_FIELDS = ['nome', 'email', 'perfil', 'escola_id', 'senha'] as const
type FormField = (typeof FORM_FIELDS)[number]

const EMAIL_CONFLICT = 'E-mail já cadastrado'

const PERFIS = Object.keys(PERFIL_LABEL) as Perfil[]

function isFormField(field: string): field is FormField {
  return (FORM_FIELDS as readonly string[]).includes(field)
}

function toPayload(values: UserCreateValues): UsuarioCriar {
  const isDiretor = values.perfil === 'diretor'
  return {
    nome: values.nome,
    email: values.email.toLowerCase(),
    perfil: values.perfil as Perfil,
    escola_id: isDiretor ? Number(values.escola_id) : null,
    senha: values.senha,
  }
}

type UserFormProps = {
  schools: EscolaLer[]
  onCreated: (user: UsuarioLer) => void
}

function UserForm({ schools, onCreated }: UserFormProps) {
  const create = useCreateUser()
  const [showPassword, setShowPassword] = useState(false)
  const {
    register,
    handleSubmit,
    watch,
    setError,
    formState: { errors },
  } = useForm<UserCreateValues>({
    resolver: zodResolver(userCreateSchema),
    defaultValues: {
      nome: '',
      email: '',
      perfil: '',
      escola_id: '',
      senha: '',
      confirmar_senha: '',
    },
  })
  const perfil = watch('perfil')
  const senha = watch('senha')
  const isDiretor = perfil === 'diretor'

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

  async function onSubmit(values: UserCreateValues) {
    try {
      onCreated(await create.mutateAsync(toPayload(values)))
    } catch (e) {
      applyServerError(e)
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid gap-x-4 sm:grid-cols-2">
      <div className="sm:col-span-2">
        <FloatingField label="Nome" autoComplete="off" error={errors.nome?.message} {...register('nome')} />
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
      <Field label="Perfil" error={errors.perfil?.message}>
        <select {...register('perfil')}>
          <option value="">Selecione o perfil</option>
          {PERFIS.map((value) => (
            <option key={value} value={value}>
              {PERFIL_LABEL[value]}
            </option>
          ))}
        </select>
      </Field>
      <div
        className={cn(
          'grid transition-[grid-template-rows,opacity] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]',
          isDiretor ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0',
        )}
      >
        <div className="min-h-0 overflow-hidden">
          <Field label="Escola" error={errors.escola_id?.message}>
            <select disabled={!isDiretor} {...register('escola_id')}>
              <option value="">Selecione a escola</option>
              {schools.map((school) => (
                <option key={school.id} value={String(school.id)}>
                  {school.nome}
                </option>
              ))}
            </select>
          </Field>
        </div>
      </div>
      <div>
        <FloatingField
          label="Senha"
          type={showPassword ? 'text' : 'password'}
          autoComplete="new-password"
          error={errors.senha?.message}
          trailing={
            <button
              type="button"
              aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
              onClick={() => setShowPassword((value) => !value)}
              className="focus-ring flex h-11 w-11 items-center justify-center rounded-[12px] text-ink-muted transition-colors duration-150 hover:text-ink"
            >
              {showPassword ? <EyeOff size={18} strokeWidth={1.75} aria-hidden="true" /> : <Eye size={18} strokeWidth={1.75} aria-hidden="true" />}
            </button>
          }
          {...register('senha')}
        />
        <PasswordStrength value={senha} />
      </div>
      <div>
        <FloatingField
          label="Confirmar senha"
          type="password"
          autoComplete="new-password"
          error={errors.confirmar_senha?.message}
          {...register('confirmar_senha')}
        />
      </div>
      <div className="flex justify-end gap-2 pt-6 sm:col-span-2">
        <Button variant="ghost" asChild>
          <Link to="/">Cancelar</Link>
        </Button>
        <Button type="submit" disabled={create.isPending}>
          Criar usuário
        </Button>
      </div>
    </form>
  )
}

type CreatedSummaryProps = {
  user: UsuarioLer
  schoolName: string | null
  onReset: () => void
}

function CreatedSummary({ user, schoolName, onReset }: CreatedSummaryProps) {
  return (
    <div className="page-enter">
      <Panel dense className="max-w-[720px] p-6">
        <div className="flex flex-col items-center gap-3 pb-6 text-center">
          <CheckCircle2 size={40} strokeWidth={1.75} aria-hidden="true" className="text-success" />
          <h2 className="text-section font-semibold text-ink">Usuário criado</h2>
        </div>
        <dl className="grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-label font-medium text-ink-muted">Nome</dt>
            <dd className="text-body text-ink">{user.nome}</dd>
          </div>
          <div>
            <dt className="text-label font-medium text-ink-muted">E-mail</dt>
            <dd className="text-body text-ink">{user.email}</dd>
          </div>
          <div>
            <dt className="text-label font-medium text-ink-muted">Perfil</dt>
            <dd className="text-body text-ink">{PERFIL_LABEL[user.perfil]}</dd>
          </div>
          {user.perfil === 'diretor' && (
            <div>
              <dt className="text-label font-medium text-ink-muted">Escola</dt>
              <dd className="text-body text-ink">{schoolName ?? 'Escola não encontrada'}</dd>
            </div>
          )}
        </dl>
        <div className="flex justify-end pt-6">
          <Button variant="secondary" onClick={onReset}>
            Criar outro
          </Button>
        </div>
      </Panel>
    </div>
  )
}

export function UserCreatePage() {
  const schools = useSchoolOptions()
  const [created, setCreated] = useState<UsuarioLer | null>(null)

  if (schools.isPending) return <PageState status="loading" />
  if (schools.isError) {
    return <PageState status="error" error={schools.error} onRetry={() => void schools.refetch()} />
  }

  const schoolName = created ? (schools.data.find((school) => school.id === created.escola_id)?.nome ?? null) : null

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Usuários" description="Criar acesso para a equipe" />
      <div className="flex max-w-[720px] items-start gap-3 rounded-[14px] bg-accent-soft px-4 py-3 text-body text-accent">
        <Info size={18} strokeWidth={1.75} aria-hidden="true" className="mt-0.5 shrink-0" />
        <p>A listagem e a edição de usuários ainda não estão disponíveis na API</p>
      </div>
      {created ? (
        <CreatedSummary user={created} schoolName={schoolName} onReset={() => setCreated(null)} />
      ) : (
        <Panel dense className="max-w-[720px] p-6 lg:p-6">
          <UserForm schools={schools.data} onCreated={setCreated} />
        </Panel>
      )}
    </div>
  )
}
