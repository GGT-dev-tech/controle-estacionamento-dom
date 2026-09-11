import { useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { cn } from '@/lib/utils'

interface SwipeToConfirmProps {
  label: string
  confirmingLabel?: string
  onConfirm: () => void | Promise<void>
  disabled?: boolean
  className?: string
}

const LIMIAR_CONFIRMACAO = 0.7 // arrastar 70% do caminho já confirma, sem precisar chegar no fim
const LARGURA_ALCA = 40

/**
 * "Deslize para confirmar", estilo alarme do iPhone — sem dependência nova, só
 * Pointer Events + transform CSS. Arrastar até o limiar e soltar confirma; soltar
 * antes disso volta pro início.
 */
export function SwipeToConfirm({
  label,
  confirmingLabel = 'Confirmando…',
  onConfirm,
  disabled,
  className,
}: SwipeToConfirmProps) {
  const trilhaRef = useRef<HTMLDivElement>(null)
  const [arrastando, setArrastando] = useState(false)
  const [progresso, setProgresso] = useState(0)
  const [confirmando, setConfirmando] = useState(false)
  const inicioX = useRef(0)

  function larguraUtil(): number {
    const largura = trilhaRef.current?.offsetWidth ?? 0
    return Math.max(largura - LARGURA_ALCA - 8, 1)
  }

  function handlePointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (disabled || confirmando) return
    event.currentTarget.setPointerCapture(event.pointerId)
    inicioX.current = event.clientX
    setArrastando(true)
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    if (!arrastando) return
    const delta = event.clientX - inicioX.current
    setProgresso(Math.min(Math.max(delta / larguraUtil(), 0), 1))
  }

  async function handlePointerUp() {
    if (!arrastando) return
    setArrastando(false)

    if (progresso >= LIMIAR_CONFIRMACAO) {
      setProgresso(1)
      setConfirmando(true)
      try {
        await onConfirm()
      } catch {
        // erro é responsabilidade de quem chama exibir (ex.: mensagem no card) — aqui só
        // garantimos que a alça sempre volta pro início, sem propagar rejeição solta.
      } finally {
        setConfirmando(false)
        setProgresso(0)
      }
    } else {
      setProgresso(0)
    }
  }

  return (
    <div
      ref={trilhaRef}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      className={cn(
        'relative h-12 w-full touch-none select-none overflow-hidden rounded-full bg-secondary',
        (disabled || confirmando) && 'opacity-70',
        className,
      )}
    >
      <div
        className="pointer-events-none absolute inset-y-0 left-0 rounded-full bg-primary/20"
        style={{ width: `${progresso * 100}%` }}
      />
      <span className="pointer-events-none absolute inset-0 flex items-center justify-center px-12 text-center text-sm font-medium text-foreground">
        {confirmando ? confirmingLabel : label}
      </span>
      <div
        className="absolute left-1 top-1 flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground shadow"
        style={{
          transform: `translateX(${progresso * larguraUtil()}px)`,
          transition: arrastando ? 'none' : 'transform 150ms ease-out',
        }}
      >
        →
      </div>
    </div>
  )
}
