# TRIDENT documentation

Start with [ARCHITECTURE.md](ARCHITECTURE.md) for the big picture, then follow the path for your role.

## Reading paths

| You are | Read |
|---|---|
| New to the project | [ARCHITECTURE.md](ARCHITECTURE.md), then [GETTING_STARTED.md](GETTING_STARTED.md) |
| Operating the console, piloting a ROV or wearing a band | [USER_GUIDE.md](USER_GUIDE.md) |
| Deploying or running a server | [DEPLOYMENT.md](DEPLOYMENT.md), [GETTING_STARTED.md](GETTING_STARTED.md) (configuration) |
| Working on the API, frontend or integrations | [PLATFORM_DESIGN.md](PLATFORM_DESIGN.md), [../src/backend/README.md](../src/backend/README.md), [../src/frontend/web/README.md](../src/frontend/web/README.md) |
| Working on models | [WEARABLE_ML_ARCHITECTURE.md](WEARABLE_ML_ARCHITECTURE.md), [TRAINING_GUIDE.md](TRAINING_GUIDE.md), [WEATHER_MODEL.md](WEATHER_MODEL.md), [reports/](reports/) |
| Working on hardware | [../src/firmware/README.md](../src/firmware/README.md), [../src/cv/README.md](../src/cv/README.md) |
| Planning the next version | [RESILIENCE_AND_FUTURE_WORK.md](RESILIENCE_AND_FUTURE_WORK.md) |
| Writing a report, paper or patent | [TRIDENT_MASTER_CONTEXT.md](TRIDENT_MASTER_CONTEXT.md) |

## All documents

| Document | Contents |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Components, data flows, design principles, repository layout, technology |
| [GETTING_STARTED.md](GETTING_STARTED.md) | Install, run, live demo, tests, real hardware, configuration, troubleshooting |
| [USER_GUIDE.md](USER_GUIDE.md) | Public SOS, dispatch, alerts, wearables, ROV missions, weather and analytics, admin, the band |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Production checklist, Docker Compose + PostgreSQL + TLS, backups, monitoring, scaling limits |
| [PLATFORM_DESIGN.md](PLATFORM_DESIGN.md) | Design principles (consistency/availability, transactions, idempotency, scheduling, auth) and the full REST/WebSocket contract |
| [WEARABLE_ML_ARCHITECTURE.md](WEARABLE_ML_ARCHITECTURE.md) | Wearable ML design record: frame contract, data, features, heads, tournament, fusion, decisions |
| [TRAINING_GUIDE.md](TRAINING_GUIDE.md) | Rebuilding the wearable, weather and vision models |
| [WEATHER_MODEL.md](WEATHER_MODEL.md) | Weather forecaster: data, candidates, backtests, hazards, limitations |
| [RESILIENCE_AND_FUTURE_WORK.md](RESILIENCE_AND_FUTURE_WORK.md) | Part I: degraded conditions and fallbacks. Part II: future-work roadmap |
| [WEARABLE_ML_SUBPROJECT_CONTEXT.md](WEARABLE_ML_SUBPROJECT_CONTEXT.md) | Project context, dataset inventory with download links, full iteration log |
| [TRIDENT_MASTER_CONTEXT.md](TRIDENT_MASTER_CONTEXT.md) | Single reference for write-ups: canonical results, inventive points, patent drafting kit (Form 2, claims, IDF), IEEE/Springer/VIT report blueprints, full fact sheets and format rules with sources |

### Generated reports (`reports/`)

These are written by the pipeline; don't edit them by hand.

| Report | Written by |
|---|---|
| [WEARABLE_DATA_REPORT.md](reports/WEARABLE_DATA_REPORT.md) | `python -m src.ml.wearable.pipeline report` |
| [MODEL_TOURNAMENT_RESULTS.md](reports/MODEL_TOURNAMENT_RESULTS.md) | `pipeline tournament` |
| [WEARABLE_FINAL_MODELS.md](reports/WEARABLE_FINAL_MODELS.md) | `pipeline final` (links to every model card) |
| [WEARABLE_FUSION_REPLAY.md](reports/WEARABLE_FUSION_REPLAY.md) | `pipeline replay` |
| [WEARABLE_RHYTHM_PPG_AF_TEST.md](reports/WEARABLE_RHYTHM_PPG_AF_TEST.md) | `python -m src.ml.wearable.serving.external_rhythm` |

Model cards sit next to the models in `models/wearable/<head>/<version>/card.md` and
`models/weather/<version>/card.md`.

### Personal (`career/`)

Career notes for the project owner (resume bullets and interview preparation). They are not part of
the technical documentation.
