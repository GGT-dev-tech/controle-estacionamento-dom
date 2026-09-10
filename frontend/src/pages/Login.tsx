import { useAuth0 } from '@auth0/auth0-react'

export default function Login() {
  const { loginWithRedirect, isLoading } = useAuth0()

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background px-4 text-center">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Estacionamento Dom</h1>
        <p className="mt-1 text-sm text-muted-foreground">Dom Pagamentos — acesso restrito</p>
      </div>
      <button
        onClick={() => loginWithRedirect()}
        disabled={isLoading}
        className="rounded-lg bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:opacity-50"
      >
        Entrar com Google
      </button>
    </div>
  )
}
