import axios from 'axios'
import { type ClassValue, clsx } from 'clsx'
import type { ChangeEvent } from 'react'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Lê a mensagem de erro real da API (campo `detail`, padrão do FastAPI) em vez de um
 * palpite fixo — assim o usuário vê exatamente por que falhou (ex.: "placa já
 * cadastrada" vs. qualquer outro motivo), sem a mesma mensagem genérica pra tudo.
 */
export function mensagemDeErro(erro: unknown, fallback: string): string {
  if (axios.isAxiosError(erro) && typeof erro.response?.data?.detail === 'string') {
    return erro.response.data.detail
  }
  return fallback
}

/**
 * Força o valor de um input pra maiúsculas enquanto digita (ex.: placa) — o `uppercase`
 * do Tailwind só muda a aparência, não o valor real enviado no submit; teclados de
 * celular também não capitalizam sozinhos, então sem isso dava pra digitar em minúscula
 * e enviar assim, dependendo só da normalização do backend pra não gerar duplicidade.
 */
export function forcarMaiusculas(event: ChangeEvent<HTMLInputElement>) {
  event.target.value = event.target.value.toUpperCase()
}
