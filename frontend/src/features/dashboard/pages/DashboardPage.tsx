import { Link } from 'react-router-dom'
import { useAuth } from '@/shared/auth/useAuth'
import { PageHeader } from '@/shared/ui/PageHeader'
import { Panel } from '@/shared/ui/Panel'

// Painel provisório: os indicadores de viagem e alerta entram nas próximas etapas.
export function DashboardPage() {
  const { user } = useAuth()

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Painel" description={`Olá, ${user?.nome ?? ''}`} />
      <Panel title="Transporte escolar seguro">
        <p className="max-w-[60ch] text-body text-ink-muted">
          Cadastre escolas, paradas, rotas e estudantes. O acompanhamento das viagens em tempo real e os alertas
          aparecem aqui conforme forem liberados.
        </p>
        <div className="flex flex-wrap gap-4 pt-4 text-body">
          <Link className="text-accent underline" to="/students">
            Estudantes
          </Link>
          <Link className="text-accent underline" to="/stops">
            Paradas
          </Link>
          <Link className="text-accent underline" to="/routes">
            Rotas
          </Link>
        </div>
      </Panel>
    </div>
  )
}
