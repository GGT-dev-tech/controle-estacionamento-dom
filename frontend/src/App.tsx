import { useEffect } from 'react'
import { Route, Routes, Navigate } from 'react-router-dom'
import { useAuth0 } from '@auth0/auth0-react'
import { useApiToken } from '@/auth/useApiToken'
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

export default function App() {
  const { isLoading, isAuthenticated } = useAuth0()
  useApiToken()

  useEffect(() => {
    if (!isAuthenticated) return
    return iniciarSincronizacaoAutomatica()
  }, [isAuthenticated])

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        Carregando…
      </div>
    )
  }

  const rotas = (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/relatorios" element={<RelatoriosPage />} />
      <Route path="/admin" element={<AdminPage />} />
      <Route path="/meu-cadastro" element={<MeuCadastro />} />
      <Route path="/*" element={<Home />} />
    </Routes>
  )

  // O gate de primeiro acesso só faz sentido pra quem já autenticou — evita uma
  // chamada a /clientes/me (que sempre 401 sem token) na tela de login.
  if (!isAuthenticated) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }

  return <RequireCadastro>{rotas}</RequireCadastro>
}
