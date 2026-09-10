import { useAuth0 } from '@auth0/auth0-react'
import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { StatusConexao } from '@/components/StatusConexao'
import { cn } from '@/lib/utils'

const NAV_LINKS = [
  { to: '/', label: 'Vagas' },
  { to: '/reservas', label: 'Reservas' },
]

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth0()

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-y-2 px-4 py-4">
          <div>
            <h1 className="text-lg font-semibold">Estacionamento Dom</h1>
            <p className="text-xs text-muted-foreground">Olá, {user?.name ?? user?.email}</p>
          </div>
          <nav className="flex flex-wrap items-center gap-3">
            <StatusConexao />
            {NAV_LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end
                className={({ isActive }) =>
                  cn(
                    'rounded-md px-3 py-1.5 text-sm font-medium',
                    isActive ? 'bg-secondary text-foreground' : 'text-muted-foreground hover:text-foreground',
                  )
                }
              >
                {link.label}
              </NavLink>
            ))}
            <button
              onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
              className="ml-2 rounded-md border border-border px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground"
            >
              Sair
            </button>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
    </div>
  )
}
