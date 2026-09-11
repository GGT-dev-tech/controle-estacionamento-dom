import { useAuth0 } from '@auth0/auth0-react'

export default function Login() {
  const { loginWithRedirect, isLoading, error } = useAuth0()

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm rounded-xl border border-white/10 bg-card/40 p-8 text-center shadow-glass backdrop-blur-xl">
        <h1 className="text-xl font-semibold text-foreground">Estacionamento Dom</h1>
        {error && (
          <p className="mt-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error.message || 'Não foi possível entrar. Acesso não autorizado.'}
          </p>
        )}
        <button
          onClick={() => loginWithRedirect({ authorizationParams: { connection: 'google-oauth2' } })}
          disabled={isLoading}
          className="mt-6 w-full rounded-lg bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground shadow-glow-primary transition hover:opacity-90 disabled:opacity-50"
        >
          Entrar com Google
        </button>
      </div>
    </div>
  )
}
