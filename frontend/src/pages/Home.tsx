import { useAuth0 } from '@auth0/auth0-react'

export default function Home() {
  const { user, logout } = useAuth0()

  return (
    <div className="min-h-screen bg-background px-4 py-6 text-foreground">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Estacionamento Dom</h1>
          <p className="text-sm text-muted-foreground">Olá, {user?.name ?? user?.email}</p>
        </div>
        <button
          onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
          className="rounded-md border border-border px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          Sair
        </button>
      </header>

      <p className="text-sm text-muted-foreground">
        Dashboard de andares e vagas em construção — Fase 2.
      </p>
    </div>
  )
}
