import { Route, Routes } from 'react-router-dom'
import { useAuth0 } from '@auth0/auth0-react'
import { useApiToken } from '@/auth/useApiToken'
import { withProtection } from '@/auth/ProtectedRoute'
import Login from '@/pages/Login'
import Home from '@/pages/Home'

const ProtectedHome = withProtection(Home)

export default function App() {
  const { isLoading } = useAuth0()
  useApiToken()

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
      <Route path="/*" element={<ProtectedHome />} />
    </Routes>
  )
}
