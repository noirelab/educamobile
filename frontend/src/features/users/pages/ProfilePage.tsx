import { PageHeader } from '@/shared/ui/PageHeader'
import { PageState } from '@/shared/ui/PageState'
import { Panel } from '@/shared/ui/Panel'
import { PERFIL_LABEL } from '../labels'
import { useMe, useSchool } from '../hooks'

export function ProfilePage() {
  const me = useMe()
  const escolaId = me.data?.perfil === 'diretor' ? (me.data.escola_id ?? null) : null
  const school = useSchool(escolaId)

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
          {user.perfil === 'diretor' && (
            <div>
              <dt className="text-label font-medium text-ink-muted">Escola</dt>
              <dd className="text-body text-ink">
                {school.isPending ? 'Carregando escola…' : school.isError ? 'Escola não encontrada' : school.data.nome}
              </dd>
            </div>
          )}
        </dl>
        <p className="mt-6 text-caption text-ink-muted">A troca de senha ainda não está disponível</p>
      </Panel>
    </div>
  )
}
