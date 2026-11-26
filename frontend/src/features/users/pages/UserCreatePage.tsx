import { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { CheckCircle2, Eye, EyeOff, Info } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { ApiError } from '@/shared/api/errors'
import type { components } from '@/shared/api/schema'
import { Button } from '@/shared/ui/button'
import { Field } from '@/shared/ui/Field'
import { FloatingField } from '@/shared/ui/FloatingField'
import { PageHeader } from '@/shared/ui/PageHeader'
import { PasswordStrength } from '@/shared/ui/PasswordStrength'
import { Panel } from '@/shared/ui/Panel'
import { notifyError } from '@/shared/ui/toast'
import { useAuth } from '@/shared/auth/useAuth'
import { PERFIL_LABEL, PERFIS_CRIAVEIS, PERFIS_CRIAVEIS_PELO_GESTOR } from '../labels'
import { useCreateUser } from '../hooks'
import { userCreateSchema, type UserCreateValues } from '../schemas'

type UsuarioLer = components['schemas']['UsuarioLer']
type UsuarioCriar = components['schemas']['UsuarioCriar']
type Perfil = components['schemas']['Perfil']

const FORM_FIELDS = ['nome', 'email', 'perfil', 'senha'] as const
type FormField = (typeof FORM_FIELDS)[number]

const EMAIL_CONFLICT = 'E-mail já cadastrado'

function isFormField(field: string): field is FormField {
  return (FORM_FIELDS as readonly string[]).includes(field)
}

function toPayload(values: UserCreateValues): UsuarioCriar {
  return {
    nome: values.nome,
    email: values.email.toLowerCase(),
    perfil: values.perfil as Perfil,
    senha: values.senha,
  }
}

type UserFormProps = { onCreated: (user: UsuarioLer) => void }

function UserForm({ onCreated }: UserFormProps) {
  const create = useCreateUser()
  const { role } = useAuth()
  const perfis = role === 'admin' ? PERFIS_CRIAVEIS : PERFIS_CRIAVEIS_PELO_GESTOR
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
      senha: '',
      confirmar_senha: '',
    },
  })
  const senha = watch('senha')

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
          {perfis.map((value) => (
            <option key={value} value={value}>
              {PERFIL_LABEL[value]}
            </option>
          ))}
        </select>
      </Field>
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

type CreatedSummaryProps = { user: UsuarioLer; onReset: () => void }

function CreatedSummary({ user, onReset }: CreatedSummaryProps) {
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
  const [created, setCreated] = useState<UsuarioLer | null>(null)

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Usuários" description="Criar acesso para a equipe" />
      <div className="flex max-w-[720px] items-start gap-3 rounded-[14px] bg-accent-soft px-4 py-3 text-body text-accent">
        <Info size={18} strokeWidth={1.75} aria-hidden="true" className="mt-0.5 shrink-0" />
        {/* Reformulado: o responsável aceita o convite em POST /auth/convites/aceitar, com o
            código no corpo ({ codigo, ... }), não mais na URL. Perfis novos: gestor, motorista,
            monitor (opcional na viagem) e responsável. */}
        <p>Responsáveis não são cadastrados aqui: eles entram por convite, vinculados ao estudante</p>
      </div>
      {created ? (
        <CreatedSummary user={created} onReset={() => setCreated(null)} />
      ) : (
        <Panel dense className="max-w-[720px] p-6 lg:p-6">
          <UserForm onCreated={setCreated} />
        </Panel>
      )}
    </div>
  )
}
