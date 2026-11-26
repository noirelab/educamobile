import type { ReactNode } from 'react'
import { createBrowserRouter, Outlet, type RouteObject } from 'react-router-dom'
import { LoginPage } from '@/features/auth/pages/LoginPage'
import { DashboardPage } from '@/features/dashboard/pages/DashboardPage'
import { AuthProvider } from '@/shared/auth/AuthProvider'
import { RequireAccess } from '@/shared/auth/RequireAccess'
import { RequireAuth } from '@/shared/auth/RequireAuth'
import type { Resource } from '@/shared/auth/permissions'
import { StudentDetailPage } from '@/features/students/pages/StudentDetailPage'
import { StudentFormPage } from '@/features/students/pages/StudentFormPage'
import { StudentListPage } from '@/features/students/pages/StudentListPage'
import { ProfilePage } from '@/features/users/pages/ProfilePage'
import { UserCreatePage } from '@/features/users/pages/UserCreatePage'
import { SchoolDetailPage } from '@/features/schools/pages/SchoolDetailPage'
import { SchoolFormPage } from '@/features/schools/pages/SchoolFormPage'
import { SchoolListPage } from '@/features/schools/pages/SchoolListPage'
import { StopDetailPage } from '@/features/stops/pages/StopDetailPage'
import { StopsPage } from '@/features/stops/pages/StopsPage'
import { RouteEditorPage } from '@/features/routes/pages/RouteEditorPage'
import { RoutesPage } from '@/features/routes/pages/RoutesPage'
import { AppShell } from './layout/AppShell'
import { ErrorBoundaryPage } from './pages/ErrorBoundaryPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { UiShowcasePage } from './pages/UiShowcasePage'

type FeatureRoute = {
  path: string
  resource: Resource
  level: 'read' | 'write'
  element: ReactNode
}

export const featureRoutes: FeatureRoute[] = [
  { path: '/', resource: 'dashboard', level: 'read', element: <DashboardPage /> },
  { path: '/schools', resource: 'schools', level: 'read', element: <SchoolListPage /> },
  { path: '/schools/new', resource: 'schools', level: 'write', element: <SchoolFormPage /> },
  { path: '/schools/:id', resource: 'schools', level: 'read', element: <SchoolDetailPage /> },
  { path: '/schools/:id/edit', resource: 'schools', level: 'write', element: <SchoolFormPage /> },
  { path: '/students', resource: 'students', level: 'read', element: <StudentListPage /> },
  { path: '/students/new', resource: 'students', level: 'write', element: <StudentFormPage /> },
  { path: '/students/:id', resource: 'students', level: 'read', element: <StudentDetailPage /> },
  { path: '/students/:id/edit', resource: 'students', level: 'write', element: <StudentFormPage /> },
  { path: '/stops', resource: 'stops', level: 'read', element: <StopsPage /> },
  { path: '/stops/:id', resource: 'stops', level: 'read', element: <StopDetailPage /> },
  { path: '/routes', resource: 'routes', level: 'read', element: <RoutesPage /> },
  { path: '/routes/:id', resource: 'routes', level: 'read', element: <RouteEditorPage /> },
  { path: '/users', resource: 'users', level: 'write', element: <UserCreatePage /> },
]

function toRouteObject(route: FeatureRoute): RouteObject {
  return {
    path: route.path,
    element: (
      <RequireAccess resource={route.resource} level={route.level}>
        {route.element}
      </RequireAccess>
    ),
  }
}

export const routes: RouteObject[] = [
  {
    element: (
      <AuthProvider>
        <Outlet />
      </AuthProvider>
    ),
    errorElement: <ErrorBoundaryPage />,
    children: [
      { path: '/login', element: <LoginPage /> },
      ...(import.meta.env.DEV ? [{ path: '/dev/ui', element: <UiShowcasePage /> }] : []),
      {
        element: (
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        ),
        children: [
          ...featureRoutes.map(toRouteObject),
          { path: '/profile', element: <ProfilePage /> },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
]

export function createAppRouter() {
  return createBrowserRouter(routes)
}
