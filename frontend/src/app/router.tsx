import type { ReactNode } from 'react'
import { createBrowserRouter, Outlet, type RouteObject } from 'react-router-dom'
import { AttendancePage } from '@/features/attendance/pages/AttendancePage'
import { LoginPage } from '@/features/auth/pages/LoginPage'
import { DashboardPage } from '@/features/dashboard/pages/DashboardPage'
import { AuthProvider } from '@/shared/auth/AuthProvider'
import { RequireAccess } from '@/shared/auth/RequireAccess'
import { RequireAuth } from '@/shared/auth/RequireAuth'
import type { Resource } from '@/shared/auth/permissions'
import { PoleDetailPage } from '@/features/poles/pages/PoleDetailPage'
import { PoleFormPage } from '@/features/poles/pages/PoleFormPage'
import { PoleListPage } from '@/features/poles/pages/PoleListPage'
import { ClassDetailPage } from '@/features/classes/pages/ClassDetailPage'
import { ClassFormPage } from '@/features/classes/pages/ClassFormPage'
import { ClassListPage } from '@/features/classes/pages/ClassListPage'
import { StudentDetailPage } from '@/features/students/pages/StudentDetailPage'
import { StudentFormPage } from '@/features/students/pages/StudentFormPage'
import { StudentListPage } from '@/features/students/pages/StudentListPage'
import { TeacherFormPage } from '@/features/teachers/pages/TeacherFormPage'
import { TeacherListPage } from '@/features/teachers/pages/TeacherListPage'
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
  { path: '/poles', resource: 'poles', level: 'read', element: <PoleListPage /> },
  { path: '/poles/new', resource: 'poles', level: 'write', element: <PoleFormPage /> },
  { path: '/poles/:id', resource: 'poles', level: 'read', element: <PoleDetailPage /> },
  { path: '/poles/:id/edit', resource: 'poles', level: 'write', element: <PoleFormPage /> },
  { path: '/schools', resource: 'schools', level: 'read', element: <SchoolListPage /> },
  { path: '/schools/new', resource: 'schools', level: 'write', element: <SchoolFormPage /> },
  { path: '/schools/:id', resource: 'schools', level: 'read', element: <SchoolDetailPage /> },
  { path: '/schools/:id/edit', resource: 'schools', level: 'write', element: <SchoolFormPage /> },
  { path: '/classes', resource: 'classes', level: 'read', element: <ClassListPage /> },
  { path: '/classes/new', resource: 'classes', level: 'write', element: <ClassFormPage /> },
  { path: '/classes/:id', resource: 'classes', level: 'read', element: <ClassDetailPage /> },
  { path: '/classes/:id/edit', resource: 'classes', level: 'write', element: <ClassFormPage /> },
  { path: '/teachers', resource: 'teachers', level: 'read', element: <TeacherListPage /> },
  { path: '/teachers/new', resource: 'teachers', level: 'write', element: <TeacherFormPage /> },
  { path: '/teachers/:id/edit', resource: 'teachers', level: 'write', element: <TeacherFormPage /> },
  { path: '/students', resource: 'students', level: 'read', element: <StudentListPage /> },
  { path: '/students/new', resource: 'students', level: 'write', element: <StudentFormPage /> },
  { path: '/students/:id', resource: 'students', level: 'read', element: <StudentDetailPage /> },
  { path: '/students/:id/edit', resource: 'students', level: 'write', element: <StudentFormPage /> },
  { path: '/attendance', resource: 'attendance', level: 'read', element: <AttendancePage /> },
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
