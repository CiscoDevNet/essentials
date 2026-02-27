```
/
├── apps/                         # Deployable applications (any language)
│   ├── web-dashboard-ts/         # TypeScript web app
│   ├── api-service-py/           # Python web app/API
│   ├── bot-service-js/           # JavaScript bot application
│   └── docs-site/                # Documentation site
├── packages/                     # Shared libraries and tools
│   ├── javascript/               # Your existing @cisco packages
│   │   ├── analytics/
│   │   ├── bot-commands/
│   │   ├── bot-factory/
│   │   ├── bot-middleware/
│   │   ├── cards/
│   │   ├── core/
│   │   ├── google/
│   │   ├── releases/
│   │   └── salesforce/
│   ├── typescript/               # Shared TypeScript libraries
│   │   ├── ui/                   # Shared UI components
│   │   ├── types/                # Shared type definitions
│   │   └── utils/                # TypeScript utilities
│   └── python/                   # Shared Python libraries
│       ├── shared/               # Shared Python utilities
│       ├── database/             # Database utilities
│       └── auth/                 # Authentication utilities
├── tools/                        # Development tools and configs
│   ├── eslint-config/
│   ├── typescript-config/
│   ├── python-config/            # Python linting, formatting configs
│   └── build-scripts/
```