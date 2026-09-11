import type { Config } from 'tailwindcss'

export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border) / <alpha-value>)',
        input: 'hsl(var(--input) / <alpha-value>)',
        ring: 'hsl(var(--ring) / <alpha-value>)',
        background: 'hsl(var(--background) / <alpha-value>)',
        foreground: 'hsl(var(--foreground) / <alpha-value>)',
        primary: {
          DEFAULT: 'hsl(var(--primary) / <alpha-value>)',
          foreground: 'hsl(var(--primary-foreground) / <alpha-value>)',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary) / <alpha-value>)',
          foreground: 'hsl(var(--secondary-foreground) / <alpha-value>)',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted) / <alpha-value>)',
          foreground: 'hsl(var(--muted-foreground) / <alpha-value>)',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent) / <alpha-value>)',
          foreground: 'hsl(var(--accent-foreground) / <alpha-value>)',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive) / <alpha-value>)',
          foreground: 'hsl(var(--destructive-foreground) / <alpha-value>)',
        },
        card: {
          DEFAULT: 'hsl(var(--card) / <alpha-value>)',
          foreground: 'hsl(var(--card-foreground) / <alpha-value>)',
        },
        vaga: {
          livre: 'hsl(var(--vaga-livre) / <alpha-value>)',
          ocupada: 'hsl(var(--vaga-ocupada) / <alpha-value>)',
          reservada: 'hsl(var(--vaga-reservada) / <alpha-value>)',
          manutencao: 'hsl(var(--vaga-manutencao) / <alpha-value>)',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      fontFamily: {
        sans: ['"Space Grotesk"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        glass: 'inset 0 1px 1px rgba(255,255,255,0.1)',
        'glow-primary': '0 0 15px hsl(var(--primary) / 0.5)',
        'glow-livre': '0 0 15px hsl(var(--vaga-livre) / 0.5)',
        'glow-ocupada': '0 0 15px hsl(var(--vaga-ocupada) / 0.5)',
        'glow-reservada': '0 0 15px hsl(var(--vaga-reservada) / 0.5)',
        'glow-destructive': '0 0 15px hsl(var(--destructive) / 0.5)',
      },
    },
  },
  plugins: [],
} satisfies Config
