import { useEffect } from 'react'
import { Route, Routes } from 'react-router-dom'
import { useAuth0 } from '@auth0/auth0-react'
import { useApiToken } from '@/auth/useApiToken'
import { withProtection } from '@/auth/ProtectedRoute'
import { RequireAdmin } from '@/auth/RequireAdmin'
import { RequireCadastro } from '@/auth/RequireCadastro'
import { iniciarSincronizacaoAutomatica } from '@/offline/sync'
import Login from '@/pages/Login'
import Home from '@/pages/Home'
import Relatorios from '@/pages/Relatorios'
import Admin from '@/pages/Admin'
import MeuCadastro from '@/pages/MeuCadastro'

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
const ProtectedRelatorios = withProtection(RelatoriosPage)
const ProtectedAdmin = withProtection(AdminPage)
const ProtectedMeuCadastro = withProtection(MeuCadastro)

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

  const rotas = (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/relatorios" element={<ProtectedRelatorios />} />
      <Route path="/admin" element={<ProtectedAdmin />} />
      <Route path="/meu-cadastro" element={<ProtectedMeuCadastro />} />
      <Route path="/*" element={<ProtectedHome />} />
    </Routes>
  )

  // O gate de primeiro acesso só faz sentido pra quem já autenticou — evita uma
  // chamada a /clientes/me (que sempre 401 sem token) na tela de login.
  if (!isAuthenticated) return rotas

  return <RequireCadastro>{rotas}</RequireCadastro>
}
