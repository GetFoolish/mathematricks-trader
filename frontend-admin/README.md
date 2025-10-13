# Mathematricks Trader - Admin Frontend

Modern React-based admin dashboard for the Mathematricks Trading System.

## Tech Stack

- **Vite** - Fast build tool and dev server
- **React 18** - UI framework
- **TypeScript** - Type safety
- **TailwindCSS** - Utility-first CSS framework
- **React Router** - Client-side routing
- **React Query** - Data fetching and caching
- **Recharts** - Charts and visualizations
- **Axios** - HTTP client
- **Lucide React** - Icon library

## Features

### 5 Core Pages

1. **Login** - JWT authentication (mock for MVP)
2. **Dashboard** - Portfolio metrics, P&L, margin usage, open positions
3. **Allocations** - View/approve portfolio allocations, correlation heatmap, history
4. **Activity** - Trading signals, orders, executions, Cerebro decisions
5. **Strategies** - Full CRUD for strategy management

### Key Functionality

- Real-time data updates (5-30 second polling)
- Protected routes with JWT authentication
- Responsive design (mobile-friendly)
- Dark theme optimized for trading
- Correlation matrix heatmap visualization
- Approve/reject allocation workflow
- Strategy CRUD operations with status toggles

## Getting Started

### Prerequisites

- Node.js >= 18
- npm >= 9

### Installation

```bash
# Install dependencies
npm install
```

### Development

```bash
# Start dev server (http://localhost:5173)
npm run dev
```

### Build for Production

```bash
# Create production build
npm run build

# Preview production build
npm run preview
```

## Environment Variables

Create a `.env` file in the `frontend-admin/` directory:

```env
VITE_API_BASE_URL=http://localhost:8002
VITE_CEREBRO_BASE_URL=http://localhost:8001
```

## Project Structure

```
frontend-admin/
├── src/
│   ├── components/          # Reusable UI components
│   │   ├── Layout.tsx       # Main layout with sidebar nav
│   │   └── ProtectedRoute.tsx
│   ├── contexts/            # React contexts
│   │   └── AuthContext.tsx  # Authentication state
│   ├── pages/               # Page components
│   │   ├── Login.tsx
│   │   ├── Dashboard.tsx
│   │   ├── Allocations.tsx
│   │   ├── Activity.tsx
│   │   └── Strategies.tsx
│   ├── services/            # API client
│   │   └── api.ts
│   ├── types/               # TypeScript types
│   │   └── index.ts
│   ├── App.tsx              # Main app with routing
│   ├── main.tsx             # Entry point
│   └── index.css            # Tailwind CSS
├── public/
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── tsconfig.json
```

## Authentication

For MVP, uses mock authentication:
- **Username**: `admin`
- **Password**: `admin`

JWT token stored in `localStorage`.

## API Integration

Connects to:
- **AccountDataService** (port 8002) - Portfolio, allocations, strategies
- **CerebroService** (port 8001) - Reload allocations, health checks

All endpoints use JWT bearer token authentication (except mock login).

## Development Notes

- React Query handles caching and refetching
- Auto-refetch intervals:
  - Account state: 5 seconds
  - Allocations: 30 seconds
  - Other data: on mount only
- Protected routes redirect to `/login` if not authenticated
- Mock data used in Activity page (replace with real APIs later)

## Deployment

For production:

1. Build static assets: `npm run build`
2. Deploy `dist/` folder to Cloud Storage + CDN
3. Configure production API URLs in `.env.production`
4. Set up proper authentication backend

## Roadmap

- [ ] Real authentication API integration
- [ ] WebSocket for real-time updates
- [ ] Advanced charting (equity curves, drawdowns)
- [ ] Export data to CSV/Excel
- [ ] Mobile app (React Native)
- [ ] Dark/light theme toggle
