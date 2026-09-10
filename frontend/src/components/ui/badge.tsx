import { cva, type VariantProps } from 'class-variance-authority'
import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

const badgeVariants = cva('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium', {
  variants: {
    variant: {
      livre: 'bg-vaga-livre/15 text-vaga-livre',
      ocupada: 'bg-vaga-ocupada/15 text-vaga-ocupada',
      reservada: 'bg-vaga-reservada/15 text-vaga-reservada',
      manutencao: 'bg-vaga-manutencao/15 text-vaga-manutencao',
      neutro: 'bg-secondary text-secondary-foreground',
    },
  },
  defaultVariants: {
    variant: 'neutro',
  },
})

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}
