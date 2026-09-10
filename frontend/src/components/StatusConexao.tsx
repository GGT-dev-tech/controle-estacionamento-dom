import { useLiveQuery } from 'dexie-react-hooks'
import { useEffect, useState } from 'react'
import { db } from '@/offline/db'
import { sincronizarPendentes } from '@/offline/sync'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function StatusConexao() {
  const [online, setOnline] = useState(navigator.onLine)
  const pendentes = useLiveQuery(() => db.operacoes.toArray(), [], [])

  useEffect(() => {
    const marcarOnline = () => setOnline(true)
    const marcarOffline = () => setOnline(false)
    window.addEventListener('online', marcarOnline)
    window.addEventListener('offline', marcarOffline)
    return () => {
      window.removeEventListener('online', marcarOnline)
      window.removeEventListener('offline', marcarOffline)
    }
  }, [])

  const totalPendentes = pendentes?.length ?? 0
  const comErro = pendentes?.filter((p) => p.erro).length ?? 0

  if (online && totalPendentes === 0) {
    return (
      <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <span className="h-2 w-2 rounded-full bg-vaga-livre" />
        Online
      </span>
    )
  }

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className={cn('flex items-center gap-1.5', online ? 'text-muted-foreground' : 'text-destructive')}>
        <span className={cn('h-2 w-2 rounded-full', online ? 'bg-vaga-livre' : 'bg-destructive')} />
        {online ? 'Online' : 'Offline'}
      </span>

      {totalPendentes > 0 && (
        <span className="rounded-full bg-secondary px-2 py-0.5 text-secondary-foreground">
          {totalPendentes} pendente{totalPendentes > 1 ? 's' : ''}
          {comErro > 0 && ` · ${comErro} com erro`}
        </span>
      )}

      {online && totalPendentes > 0 && (
        <Button size="sm" variant="ghost" onClick={() => sincronizarPendentes()}>
          Sincronizar agora
        </Button>
      )}
    </div>
  )
}
