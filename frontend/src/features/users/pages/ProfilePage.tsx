import { zodResolver } from '@hookform/resolvers/zod'
import { LogOut } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '@/shared/api/errors'
import { clearToken } from '@/shared/auth/session'
import { useAuth } from '@/shared/auth/useAuth'
import { Button } from '@/shared/ui/button'
import { FloatingField } from '@/shared/ui/FloatingField'
import { PageHeader } from '@/shared/ui/PageHeader'
import { PageState } from '@/shared/ui/PageState'
import { Panel } from '@/shared/ui/Panel'
import { notifyError, notifySuccess } from '@/shared/ui/toast'
import { useChangePassword, useMe } from '../hooks'
import { PERFIL_LABEL } from '../labels'
import { passwordChangeSchema, type PasswordChangeValues } from '../schemas'

function PasswordForm() {
  const navigate = useNavigate()
  const change = useChangePassword()
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors },
  } = useForm<PasswordChangeValues>({
    resolver: zodResolver(passwordChangeSchema),
    defaultValues: { senha_atual: '', senha_nova: '', confirmar: '' },
  })

  async function onSubmit(values: PasswordChangeValues) {
    try {
      await change.mutateAsync({ senha_atual: values.senha_atual, senha_nova: values.senha_nova })
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        setError('senha_atual', { message: 'Senha atual incorreta' })
      } else if (e instanceof ApiError && e.status === 429) {
        notifyError(e)
      } else {
        notifyError(e)
      }
      return
    }
    // O backend encerra todas as sessões ao trocar a senha, inclusive esta.
    reset()
    clearToken()
    notifySuccess('Senha alterada. Entre novamente')
    navigate('/login')
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid max-w-[420px] gap-x-4">
      <FloatingField
        label="Senha atual"
        type="password"
        autoComplete="current-password"
        error={errors.senha_atual?.message}
        {...register('senha_atual')}
      />
      <FloatingField
        label="Senha nova"
        type="password"
        autoComplete="new-password"
        error={errors.senha_nova?.message}
        {...register('senha_nova')}
      />
      <FloatingField
        label="Confirmar senha nova"
        type="password"
        autoComplete="new-password"
        error={errors.confirmar?.message}
        {...register('confirmar')}
      />
      <div className="flex justify-end pt-4">
        <Button type="submit" disabled={change.isPending}>
          Trocar senha
        </Button>
      </div>
    </form>
  )
}

export function ProfilePage() {
  const me = useMe()
  const { logout, logoutAll } = useAuth()

  if (me.isPending) return <PageState status="loading" />
  if (me.isError) {
    return <PageState status="error" error={me.error} onRetry={() => void me.refetch()} />
  }

  const user = me.data
  const initial = user.nome.trim().charAt(0).toUpperCase()

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={user.nome} description={PERFIL_LABEL[user.perfil]} />
      <Panel className="max-w-[720px]">
        <div className="flex items-center gap-4 pb-6">
          <span
            aria-hidden="true"
            className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-accent-soft text-title font-semibold text-accent"
          >
            {initial}
          </span>
        </div>
        <dl className="grid gap-4 border-t border-line pt-6 sm:grid-cols-2">
          <div>
            <dt className="text-label font-medium text-ink-muted">E-mail</dt>
            <dd className="break-all text-body text-ink">{user.email}</dd>
          </div>
          <div>
            <dt className="text-label font-medium text-ink-muted">Perfil</dt>
            <dd className="text-body text-ink">{PERFIL_LABEL[user.perfil]}</dd>
          </div>
        </dl>
      </Panel>
      <Panel className="max-w-[720px]" title="Trocar senha">
        <PasswordForm />
      </Panel>
      <Panel className="max-w-[720px]" title="Sessões">
        <p className="pb-4 text-body text-ink-muted">
          Se perdeu um celular ou usou um computador de outra pessoa, encerre todas as sessões.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => logout()}>
            <LogOut aria-hidden="true" />
            Sair deste aparelho
          </Button>
          <Button variant="danger-outline" onClick={() => logoutAll()}>
            <LogOut aria-hidden="true" />
            Sair de todos os aparelhos
          </Button>
        </div>
      </Panel>
    </div>
  )
}
