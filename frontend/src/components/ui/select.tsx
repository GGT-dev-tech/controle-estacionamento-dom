import type { SelectHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        'flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm text-foreground',
        'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:shadow-glow-primary',
        className,
      )}
      {...props}
    />
  )
}
