## ScrnaClaw

**Traditional tools make you repeat yourself.** Every session starts from zero: re-upload data, re-explain context, re-run preprocessing. ScrnaClaw remembers.

## ✨ Features
- **🧠 Persistent Memory** — Context, preferences, and analysis history survive across sessions.
- **🛠️ Extensibility (MCP & Skill Builder)** — Natively integrates Model Context Protocol (MCP) servers and features `omics-skill-builder` to automate custom analysis deployment.
- **🌐 Multi-Provider** — Anthropic, OpenAI, DeepSeek, or local LLMs — one config to switch.
- **📱 Multi-Channel** — CLI as the hub; Telegram, Feishu, and more — one agent session.
- **🔄 Workflow Continuity** — Resume interrupted analyses, track lineage, and avoid redundant computation.
- **🔒 Privacy-First** — All processing is local; memory stores metadata only (no raw data uploads).
- **🎯 Smart Routing** — Natural language routed to the appropriate analysis automatically.
- **🧬 Multi-Omics Coverage** — 72 predefined skills across spatial, single-cell, genomics, proteomics, metabolomics, bulk RNA-seq, literature and orchestration.


## 📦 Installation

To prevent dependency conflicts, we strongly recommend installing ScrnaClaw inside a virtual environment. You can use either the standard `venv` or the ultra-fast `uv`.

Setup Virtual Environment (Highly Recommended)</summary>

**Option A: Using standard venv**
```bash
# 1. Create a virtual environment
python3 -m venv .venv

# 2. Activate it
source .venv/bin/activate
```
```bash
# Clone the repository
git clone https://github.com/TianGzlab/ScrnaClaw.git
cd ScrnaClaw

# Install core system operations
pip install -e .

## 🔑 Configuration

**The Easiest Way (Interactive Setup):**
ScrnaClaw provides a built-in interactive wizard that walks through LLM setup, shared runtime settings, graph memory options, and messaging channel credentials in one flow.
```bash
scrna_claw onboard  # or use short alias: oc onboard
```

The wizard writes the project-root `.env` used by CLI, TUI, routing, and bot entrypoints.

ScrnaClaw supports switching between multiple LLM engines with a single config change. It automatically loads the project-root `.env` file for CLI, TUI, routing, and bot entrypoints. If `python-dotenv` is not installed, it falls back to a built-in `.env` parser, so standard key/value configuration still works in lean installs.

For hosted providers, you can configure either:
- `LLM_API_KEY`
- a provider-specific key such as `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY`


## ⚡ Quick Start

### Option 1: Chat Interface (Recommended)

```bash

# Start the Interactive Terminal Chat
scrna_claw interactive  # or: scrna_claw chat
scrna_claw tui          # or: oc tui

# OR start messaging channels as background frontends
python -m bot.run --channels feishu,telegram
```

> 📖 **Bot Configuration Guide:** See [bot/README.md](bot/README.md) for detailed step-by-step instructions on configuring `.env` and channel-specific credentials.

**Chat with your data:**
```
You: "Preprocess my Visium data"
Bot: ✅ [Runs QC, normalization, clustering]
     💾 [Remembers: visium_sample.h5ad, 5000 spots, normalized]

[Next day]
You: "Find spatial domains"
Bot: 🧠 "Using your Visium data from yesterday (5000 spots, normalized).
     Running domain detection..."
```

<details>
<summary>In-session commands (Interactive CLI/TUI)</summary>

| Command | Description |
| ------- | ----------- |
| **Analysis & Orchestration** | |
| `/run <skill> [...]` | Run an analysis skill directly (e.g. `/run spatial-domains --demo`) |
| `/skills [domain]` | List all available analysis skills |
| `/research` | Launch multi-agent autonomous research pipeline |
| `/install-skill` | Add new custom skills or extension packs from local or GitHub |
| **Workflow & Planning** | |
| `/plan` | Interactively inspect or create the session's action plan |
| `/tasks` | View the structured execution steps for the current pipeline |
| `/approve-plan` | Approve the autonomous pipeline to proceed |
| `/do-current-task` | Proceed with the next execution step in the pipeline |
| **Session & Context Memory** | |
| `/sessions` | List all recent saved conversational workflows |
| `/resume [id/tag]` | Resume a previous analysis session exactly where you left off |
| `/new` / `/clear` | Start fresh or clear conversation context |
| `/memory` | Manage semantic memory and persistent entity tracking |
| `/export` | Export the current session graph into a structured Markdown report |
| **System & Setup** | |
| `/mcp` | Manager for Model Context Protocol servers (`/mcp list/add/remove`) |
| `/config` | View or update engine and model configurations |
| `/doctor` / `/usage` | Run system diagnostics or check LLM token & cost usage |
| `/exit` | Quit ScrnaClaw |

</details>

<details>
<summary>In-bot commands (Telegram / Feishu)</summary>

| Command | Description |
| ------- | ----------- |
| `/start` / `/help`| Get welcome message, usage instructions, or context help |
| `/skills` | Browse the multi-omics skill catalog |
| `/demo <skill>` | Run a skill demo with automated dummy data |
| `/new` / `/clear` | Start a fresh conversational branch (memory preserved) |
| `/forget` | Complete memory reset (wipes conversation & graph memory) |
| `/files` / `/outputs`| List uploaded data files or recent analysis results |
| `/recent` | Show the last 3 completed analyses |
| `/status` / `/health`| Diagnostic info, current backend, and bot uptime |

</details>

### Option 2: Command Line

```bash
# Try a demo (no data needed)
python scrna_claw.py run spatial-preprocess --demo

# Run with your data
python scrna_claw.py run spatial-preprocess --input data.h5ad --output results/
```

> 📚 **Documentation:** [INSTALLATION.md](docs/INSTALLATION.md) • [METHODS.md](docs/METHODS.md) • [MEMORY_SYSTEM.md](docs/MEMORY_SYSTEM.md)

## Supported Domains

| Domain | Skills | Key Capabilities |
|--------|--------|------------------|
| **Spatial Transcriptomics** | 16 | QC, clustering, cell typing, deconvolution, spatial statistics, communication, velocity, trajectory, microenvironment |
| **Single-Cell Omics** | 14 | QC, filtering, preprocessing, doublet detection, annotation, trajectory, batch integration, DE, GRN, scATAC preprocessing |

## Skills Overview

### Spatial Transcriptomics (16 skills)

- **Basic:** `spatial-preprocess` — QC, normalization, clustering, UMAP
- **Analysis:** `spatial-domains`, `spatial-annotate`, `spatial-deconv`, `spatial-statistics`, `spatial-genes`, `spatial-de`, `spatial-condition`, `spatial-microenvironment-subset`
- **Advanced:** `spatial-communication`, `spatial-velocity`, `spatial-trajectory`, `spatial-enrichment`, `spatial-cnv`
- **Integration:** `spatial-integrate`, `spatial-register`
- **Routing:** use top-level `orchestrator` for cross-domain query routing and pipelines

<details>
<summary>View all spatial skills</summary>

| Skill | Description | Key Methods |
|-------|-------------|-------------|
| `spatial-preprocess` | QC, normalization, HVG, PCA, UMAP, clustering | Scanpy |
| `spatial-domains` | Tissue region / niche identification | Leiden, Louvain, SpaGCN, STAGATE, GraphST, BANKSY, CellCharter |
| `spatial-annotate` | Cell type annotation | Marker-based (Scanpy), Tangram, scANVI, CellAssign |
| `spatial-deconv` | Cell type proportion estimation | FlashDeconv, Cell2location, RCTD, DestVI, Stereoscope, Tangram, SPOTlight, CARD |
| `spatial-statistics` | Spatial autocorrelation, network topology | Moran's I (Global/Local/Bivariate), Geary's C, Getis-Ord Gi*, Ripley's L, Co-occurrence, Centrality |
| `spatial-genes` | Spatially variable genes | Moran's I, SpatialDE, SPARK-X, FlashS |
| `spatial-de` | Differential expression | Wilcoxon, t-test, PyDESeq2 |
| `spatial-condition` | Condition comparison | Pseudobulk DESeq2 |
| `spatial-microenvironment-subset`| Extract local neighborhood subset by spatial radius | KDTree, Scanpy |
| `spatial-communication` | Ligand-receptor interactions | LIANA+, CellPhoneDB, FastCCC, CellChat |
| `spatial-velocity` | RNA velocity / cellular dynamics | scVelo, VELOVI |
| `spatial-trajectory` | Developmental trajectories | CellRank, Palantir, DPT |
| `spatial-enrichment` | Pathway enrichment | GSEA, ssGSEA, Enrichr |
| `spatial-cnv` | Copy number variation | inferCNVpy, Numbat |
| `spatial-integrate` | Multi-sample integration | Harmony, BBKNN, Scanorama |
| `spatial-register` | Spatial registration | PASTE, STalign |
</details>

### Single-Cell Omics (14 skills)

- **Basic:** `sc-qc`, `sc-filter`, `sc-preprocessing`, `sc-ambient-removal`, `sc-doublet-detection`
- **Analysis:** `sc-cell-annotation`, `sc-de`, `sc-markers`
- **Advanced:** `sc-pseudotime`, `sc-velocity`, `sc-grn`, `sc-cell-communication`
- **Integration:** `sc-batch-integration`
- **ATAC:** `scatac-preprocessing`

<details>
<summary>View all single-cell skills</summary>

| Skill | Description | Key Methods |
|-------|-------------|-------------|
| `sc-qc` | Calculate and visualize QC metrics | Scanpy QC |
| `sc-filter` | Filter cells and genes using QC thresholds | Rule-based filtering |
| `sc-preprocessing` | QC, normalization, HVG, PCA, UMAP | Scanpy, Seurat, SCTransform |
| `sc-ambient-removal` | Remove ambient RNA contamination | CellBender, SoupX, simple |
| `sc-doublet-detection` | Identify and remove doublets | Scrublet, DoubletFinder, scDblFinder |
| `sc-cell-annotation` | Cell type annotation | markers, CellTypist, SingleR |
| `sc-de` | Differential expression | Wilcoxon, t-test, DESeq2 pseudobulk |
| `sc-markers` | Marker gene discovery | Wilcoxon, t-test, logistic regression |
| `sc-pseudotime` | Pseudotime & trajectory inference | PAGA, DPT |
| `sc-velocity` | RNA velocity | scVelo |
| `sc-grn` | Gene regulatory networks | pySCENIC |
| `sc-cell-communication` | Ligand-receptor interactions | builtin, LIANA, CellChat |
| `sc-batch-integration` | Multi-sample integration | Harmony, scVI, BBKNN, Scanorama, fastMNN, Seurat CCA/RPCA |
| `scatac-preprocessing` | scATAC-seq preprocessing and clustering | TF-IDF, LSI, UMAP, Leiden |

</details>

## Architecture

<details>
<summary>View project architecture and skill layout</summary>

ScrnaClaw uses a modular, domain-organized structure:

```
ScrnaClaw/
├── scrna_claw.py              # Main CLI entrypoint
├── scrna_claw/                # Domain-agnostic framework package
│   ├── core/                 # Registry, skill discovery, dependency management
│   ├── routing/              # Query routing and orchestration logic
│   ├── loaders/              # File extension / domain detection helpers
│   ├── common/               # Shared utilities (reports, checksums)
│   ├── memory/               # Graph memory system
│   ├── interactive/          # Interactive CLI / TUI interfaces
│   ├── agents/               # Agent definitions
│   ├── knowledge/            # Knowledge loading helpers
│   └── r_scripts/            # Shared R-side helpers
├── skills/                   # Self-contained analysis modules
│   ├── spatial/              # 16 spatial transcriptomics skills + _lib
│   ├── singlecell/           # 14 single-cell omics skills + _lib
│   ├── genomics/             # 10 genomics skills + _lib
│   ├── proteomics/           # 8 proteomics skills + _lib
│   ├── metabolomics/         # 8 metabolomics skills + _lib
│   ├── bulkrna/              # 13 bulk RNA-seq skills + _lib
│   └── orchestrator/         # Multi-domain routing
├── knowledge_base/           # Guardrails, guides, and reusable know-how
├── bot/                      # Multi-channel messaging interfaces
├── frontend/                 # Memory Explorer React/Vite dashboard
├── website/                  # Official documentation and landing page
├── docs/                     # Documentation (installation, methods, architecture)
├── examples/                 # Example datasets
├── scripts/                  # Utility scripts (catalog generation, etc.)
├── templates/                # Report and output templates
├── tests/                    # Integration tests
├── sessions/                 # Session storage for workflow state
├── Makefile                  # Build tasks, shortcuts and runners map
└── install_r_dependencies.R  # R libraries installation script
```

**Each skill is self-contained:**
```
skills/<domain>/<skill>/
├── SKILL.md                  # Methodology specification
├── <skill_script>.py         # CLI implementation
└── tests/                    # Unit and integration tests
```

Skills communicate via standardized formats (`.h5ad`, `.vcf`, `.mzML`, `.csv`) and can be chained into pipelines.

</details>

## 🤖 For AI Agents

**If you are an AI Agent reading this repository (e.g., via OpenClaw, Claude Desktop, Cursor, OpenDevin, or a local CLI):** 

Your human relies on ScrnaClaw's unified skills for multi-omics analysis. **Do not hallucinate ad-hoc python scripts.** Instead, you MUST leverage ScrnaClaw's standardized tools and Graph Memory System. 

Please read the following system specifications **immediately** before taking any action:

- 📜 **[`llms.txt`](llms.txt)**: High-level overview of the project architecture and prompt boundaries.
- 🧠 **[`AGENTS.md`](AGENTS.md)**: Your official operations manual, detailing the `oc` CLI syntax and memory integration.
- 🤖 **[`CLAUDE.md`](CLAUDE.md)**: Custom agent instructions and internal orchestration parameters.
- 🧩 **[`skills/catalog.json`](skills/catalog.json)**: The complete machine-readable registry of all 72 available analysis skills across 8 domains and their explicit execution parameters.
- 
[🔝 Back to top](#top)
