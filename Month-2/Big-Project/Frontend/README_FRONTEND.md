# AeroDelay AI — Phase 3 Frontend

## Quick Start

```bash
# 1. Install dependencies
npm install

# 2. Start development server
npx next dev

# 3. Open http://localhost:3000 in your browser
```

## Project Structure

```
aero-frontend/
├── package.json          # Dependencies & scripts
├── tailwind.config.js    # Aviation color palette
├── tsconfig.json        # TypeScript config
├── app/
│   ├── layout.tsx       # Root layout
│   ├── page.tsx         # Home screen
│   ├── tracking/        # Live flight tracking
│   ├── prediction/      # Delay-risk prediction
│   ├── analytics/       # Route performance analytics
│   └── models/          # Model information
├── components/          # UI components
│   ├── navigation.tsx   # Bottom/Top Nav
│   └── ui.tsx           # GlassPanel, Card, Badge, etc.
├── hooks/               # use-reduced-motion.ts
└── node_modules/        # Installed dependencies
```

## Screens

| Route | Description |
|-------|-------------|
| `/` | Home & flight search |
| `/tracking` | Live flight tracking with path visualization |
| `/prediction` | Delay-risk prediction with model scores |
| `/analytics` | Route performance analytics |
| `/models` | Model information and methodology |

## Design

- **Colors**: Deep navy (#0f172a) / electric cyan (#3b82f6)
- **Typography**: Outfit display / Inter body
- **Panels**: Glassmorphism with backdrop-blur
- **Mobile**: Bottom navigation, responsive grids

## Important

- All data is demo/placeholder until backend connected
- Streamlit app (`app.py`) remains untouched and functional
- No API keys in frontend environment variables
- Reduced-motion preferences respected