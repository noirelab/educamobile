import type { ReactNode } from 'react'
import { Bell, CalendarCheck, GraduationCap, Pencil, Plus, Trash2, Users } from 'lucide-react'
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog'
import { DataTable } from '@/shared/ui/DataTable'
import { Field } from '@/shared/ui/Field'
import { FloatingField } from '@/shared/ui/FloatingField'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { KpiCard } from '@/shared/ui/KpiCard'
import { Pager } from '@/shared/ui/Pager'
import { PageHeader } from '@/shared/ui/PageHeader'
import { PageState } from '@/shared/ui/PageState'
import { PasswordStrength } from '@/shared/ui/PasswordStrength'
import { Panel } from '@/shared/ui/Panel'
import { Reveal } from '@/shared/ui/Reveal'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/shared/ui/tabs'
import { notifySuccess } from '@/shared/ui/toast'
import { usePager } from '@/shared/ui/usePager'

const rows = [
  { id: 1, nome: 'EMEF Professora Ana', polo: 'Polo Centro', infreq: 'Ativa' },
  { id: 2, nome: 'EMEI Bela Vista', polo: 'Polo Norte', infreq: 'Transferida' },
  { id: 3, nome: 'EMEF João Pessoa', polo: 'Polo Sul', infreq: 'Ativa' },
  { id: 4, nome: 'EMEB Rio Claro', polo: 'Polo Leste', infreq: 'Encerrada' },
]

const columns = [
  { key: 'nome', header: 'Escola', cell: (row: (typeof rows)[number]) => row.nome },
  { key: 'polo', header: 'Polo', cell: (row: (typeof rows)[number]) => row.polo },
  {
    key: 'status',
    header: 'Situação',
    cell: (row: (typeof rows)[number]) => (
      <Badge variant={row.infreq === 'Ativa' ? 'success' : row.infreq === 'Transferida' ? 'warning' : 'muted'}>
        {row.infreq}
      </Badge>
    ),
  },
]

const passwords = ['', 'abcdefghij', 'abcdefghiJ', 'abcdefgHI1', 'abcdefgHI1!']

function ShowcaseSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-section font-semibold text-ink">{title}</h2>
      {children}
    </section>
  )
}

export function UiShowcasePage() {
  const pager = usePager()

  return (
    <div className="mx-auto flex w-full max-w-[1360px] flex-col gap-8 p-4 lg:p-5">
      <PageHeader
        title="Kit de interface"
        description="Componentes e estados do design, somente em desenvolvimento."
        actions={
          <Button>
            <Plus aria-hidden="true" />
            Novo polo
          </Button>
        }
      >
        <Tabs defaultValue="tabela">
          <TabsList>
            <TabsTrigger value="tabela">Tabela</TabsTrigger>
            <TabsTrigger value="mapa">Mapa</TabsTrigger>
          </TabsList>
          <TabsContent value="tabela" />
          <TabsContent value="mapa" />
        </Tabs>
      </PageHeader>

      <Reveal index={0}>
        <ShowcaseSection title="Botões">
          <Panel>
            <div className="flex flex-wrap items-center gap-3">
              <Button>
                <Plus aria-hidden="true" />
                Entrar
              </Button>
              <Button variant="secondary">Cancelar</Button>
              <Button variant="ghost">Anterior</Button>
              <Button variant="destructive">
                <Trash2 aria-hidden="true" />
                Excluir
              </Button>
              <Button variant="danger-outline">
                <Trash2 aria-hidden="true" />
                Excluir polo
              </Button>
              <Button variant="link">Ver rotas</Button>
              <Button disabled>Desabilitado</Button>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <Button size="sm">Pequeno</Button>
              <Button size="sm" variant="secondary">
                Pequeno
              </Button>
              <Button size="icon" aria-label="Editar">
                <Pencil aria-hidden="true" />
              </Button>
              <Button size="icon" variant="ghost" aria-label="Excluir">
                <Trash2 aria-hidden="true" />
              </Button>
              <Button variant="secondary" onClick={() => notifySuccess('Registro salvo com sucesso')}>
                <Bell aria-hidden="true" />
                Mostrar aviso
              </Button>
            </div>
          </Panel>
        </ShowcaseSection>
      </Reveal>

      <Reveal index={1}>
        <ShowcaseSection title="Campos">
          <Panel className="grid gap-x-6 md:grid-cols-2">
            <FloatingField label="Nome" />
            <FloatingField label="E-mail" defaultValue="ana@educa.test" />
            <FloatingField label="Senha" type="password" error="Senha obrigatória" />
            <Field label="Turno">
              <select defaultValue="manha">
                <option value="manha">Manhã</option>
                <option value="tarde">Tarde</option>
              </select>
            </Field>
            <Field label="Data de início" error="Data inválida">
              <input type="date" />
            </Field>
          </Panel>
        </ShowcaseSection>
      </Reveal>

      <Reveal index={2}>
        <ShowcaseSection title="Força da senha">
          <Panel className="flex flex-col gap-5 md:max-w-[480px]">
            {passwords.map((value) => (
              <PasswordStrength key={value || 'empty'} value={value} />
            ))}
          </Panel>
        </ShowcaseSection>
      </Reveal>

      <Reveal index={3}>
        <ShowcaseSection title="Badges e abas">
          <Panel className="flex flex-col gap-5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge>Informação</Badge>
              <Badge variant="success">Ativa</Badge>
              <Badge variant="warning">Transferida</Badge>
              <Badge variant="muted">Encerrada</Badge>
              <Badge variant="destructive">Erro</Badge>
              <Badge variant="outline">Rascunho</Badge>
            </div>
            <Tabs defaultValue="polo">
              <TabsList>
                <TabsTrigger value="polo">Polo</TabsTrigger>
                <TabsTrigger value="escola">Escola</TabsTrigger>
                <TabsTrigger value="turma">Turma</TabsTrigger>
              </TabsList>
            </Tabs>
          </Panel>
        </ShowcaseSection>
      </Reveal>

      <Reveal index={4}>
        <ShowcaseSection title="Indicadores">
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard label="Registros" value="55" icon={Users} />
            <KpiCard label="Infrequência" value="16,4%" icon={CalendarCheck} tone="warning" />
            <KpiCard label="Faltas" value="41%" icon={GraduationCap} tone="danger" />
            <KpiCard label="Carregando" value="--" loading />
          </div>
        </ShowcaseSection>
      </Reveal>

      <Reveal index={5}>
        <ShowcaseSection title="Tabela">
          <DataTable columns={columns} rows={rows} footer={<Pager pager={pager} rows={rows} />} />
        </ShowcaseSection>
      </Reveal>

      <Reveal index={6}>
        <ShowcaseSection title="Estados">
          <div className="grid gap-5 md:grid-cols-3">
            <Panel>
              <PageState status="loading" />
            </Panel>
            <Panel>
              <PageState status="empty" emptyText="Nenhuma escola neste polo" />
            </Panel>
            <Panel>
              <PageState status="error" error={new Error('Não foi possível carregar os dados')} onRetry={() => undefined} />
            </Panel>
          </div>
        </ShowcaseSection>
      </Reveal>

      <Reveal index={7}>
        <ShowcaseSection title="Diálogo de confirmação">
          <Panel>
            <ConfirmDialog
              trigger={
                <Button variant="danger-outline">
                  <Trash2 aria-hidden="true" />
                  Excluir polo
                </Button>
              }
              title="Excluir polo"
              description="Confirma a exclusão deste polo? Esta ação não pode ser desfeita."
              confirmLabel="Excluir"
              onConfirm={async () => undefined}
            />
          </Panel>
        </ShowcaseSection>
      </Reveal>
    </div>
  )
}
