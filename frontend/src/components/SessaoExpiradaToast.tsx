import { useSessaoExpiradaStore } from '@/auth/sessaoExpirada'

/** Feedback mínimo pra quando dispararSessaoExpirada() é chamado — sem isso, o
 * redirect pro login (com ~1.2s de atraso) acontece sem nenhum aviso, parecendo
 * que o app travou por um instante antes de "sumir" pra tela de login. */
export function SessaoExpiradaToast() {
  const expirada = useSessaoExpiradaStore((s) => s.expirada)
  if (!expirada) return null

  return (
    <div className="fixed inset-x-0 top-4 z-50 flex justify-center px-4">
      <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-card/90 px-4 py-3 text-sm text-foreground shadow-glass backdrop-blur-xl">
        <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-destructive" />
        Sua sessão expirou. Redirecionando para o login…
      </div>
    </div>
  )
}
