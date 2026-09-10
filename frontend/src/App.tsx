import { useEffect } from 'react'
import { Route, Routes } from 'react-router-dom'
import { useAuth0 } from '@auth0/auth0-react'
import { useApiToken } from '@/auth/useApiToken'
import { withProtection } from '@/auth/ProtectedRoute'
import { RequireAdmin } from '@/auth/RequireAdmin'
import { iniciarSincronizacaoAutomatica } from '@/offline/sync'
import Login from '@/pages/Login'
import Home from '@/pages/Home'
import Reservas from '@/pages/Reservas'
import Relatorios from '@/pages/Relatorios'
import Admin from '@/pages/Admin'

function RelatoriosPage() {
  return (
    <RequireAdmin>
      <Relatorios />
    </RequireAdmin>
  )
}

function AdminPage() {
  return (
    <RequireAdmin>
      <Admin />
    </RequireAdmin>
  )
}

const ProtectedHome = withProtection(Home)
const ProtectedReservas = withProtection(Reservas)
const ProtectedRelatorios = withProtection(RelatoriosPage)
const ProtectedAdmin = withProtection(AdminPage)

export default function App() {
  const { isLoading, isAuthenticated } = useAuth0()
  useApiToken()

  useEffect(() => {
    if (!isAuthenticated) return
    return iniciarSincronizacaoAutomatica()
  }, [isAuthenticated])

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-muted-foreground">
        Carregando…
      </div>
    )
  }

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/reservas" element={<ProtectedReservas />} />
      <Route path="/relatorios" element={<ProtectedRelatorios />} />
      <Route path="/admin" element={<ProtectedAdmin />} />
      <Route path="/*" element={<ProtectedHome />} />
    </Routes>
  )
}
