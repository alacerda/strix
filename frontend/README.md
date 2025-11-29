# Strix Frontend

Frontend Next.js para a interface web do Strix.

## Desenvolvimento

### Pré-requisitos

- Node.js 18+ 
- npm ou yarn

### Instalação

```bash
npm install
```

### Executar em modo desenvolvimento

```bash
npm run dev
```

O frontend estará disponível em `http://localhost:3000`.

### Build para produção

```bash
npm run build
```

O build será gerado em `.next/`. O backend Python servirá automaticamente o build quando disponível.

## Estrutura

- `src/app/` - Páginas Next.js (App Router)
- `src/components/` - Componentes React
- `src/hooks/` - Hooks customizados
- `src/lib/` - Utilitários (API client, WebSocket)
- `src/types/` - Definições TypeScript

## Integração com Backend

O frontend se conecta ao backend Python FastAPI via:
- REST API em `/api/*`
- WebSocket em `/ws`

As requisições são redirecionadas via `next.config.js` para o backend em `http://127.0.0.1:8080`.

