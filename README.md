# Free Model Aggregator

A lightweight **Free Model Aggregator** that discovers, normalizes, stores, and exposes currently available free AI model endpoints from multiple providers.

## Architecture

```
                    GitHub Repository
                           │
             ┌─────────────┴─────────────┐
             │                           │
             ▼                           ▼
       GitHub Actions               Cloudflare Pages
             │                           │
             ▼                           ▼
       Python data/                  web/
             │                           │
             │                           ├── UI
             │                           └── Pages Functions
             │                              │
             └──────────────┐               │
                           ▼               │
                     Cloudflare KV ◄──────────┘
```

- **Data Runtime**: Python data pipeline (offline scheduled job, GitHub Actions daily 02:00) → normalize → validate → deduplicate → Cloudflare KV
- **Web Runtime**: Cloudflare Pages application reads the catalog from KV and provides the online user experience

## Components

- **NVIDIA provider**: Parses build.nvidia.com model catalog (RSC/Flight payloads)
- **AMD provider**: Parses AMD Radeon AI Platform API
- **Hugging Face provider**: Discovers models via router.huggingface.co and HF Hub metadata

## MVP Features

- Daily automated model discovery
- Provider-specific model/endpoint metadata
- Unified model catalog (same model, different provider endpoints)
- Web UI for browsing/selecting models
- LiteLLM configuration generation
- Short-lived generated configuration URLs (~5 min TTL)
- Agent-friendly prompts for importing configurations

## Project Structure

```
free-model-aggregator/
├── data/
│   ├── providers/
│   │   ├── nvidia.py
│   │   ├── amd.py
│   │   └── huggingface.py
│   ├── models/
│   │   ├── schema.py
│   │   ├── normalize.py
│   │   └── deduplicate.py
│   ├── storage/
│   │   └── cloudflare_kv.py
│   ├── tests/
│   ├── main.py
│   └── pyproject.toml
├── web/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── functions/
│   │       ├── api/
│   │       ├── generated/
│   ├── package.json
├── shared/
│   └── schema/
│       └── model.schema.json
├── .github/
│   └── workflows/
│       └── fetch-models.yml
└── README.md
```

## License

See AGENTS.md for license and implementation guidelines.