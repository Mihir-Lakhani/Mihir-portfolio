# Portfolio RAG Setup

## What runs where

The portfolio assistant has two selectable retrieval adapters:

- `local_hybrid` is the default. It searches only enabled entries in `knowledge/sources.json` with local BM25 plus Ollama `nomic-embed-text` cosine similarity. Gemini routes the question and writes the final answer from selected evidence.
- `gemini_file_search` preserves the existing Google File Search store as an alternative. It is never rebuilt, altered, or deleted by the local-index command.

Both adapters use the same approval registry, source-hash checks, citation gate, privacy blocklist, Gemini final-reply conversation chain, diagnostic format, and browser API.

```text
Visitor -> Flask -> local private-request check
                    -> Gemini router (temporary continuation node, then deleted)
                    -> local hybrid index OR Gemini File Search
                    -> Gemini final answer writer (stored for this page)
                    -> evidence and citation validation
                    -> browser answer, trusted links, optional approved flowchart
```

The local index reads no legacy or unregistered Markdown. In particular, `knowledge/public/projects.md` is not eligible unless it is explicitly registered and enabled in `knowledge/sources.json`.

## Local-first setup

Install the repository dependencies, Ollama, and the local embedding model. Ollama must remain running while Flask serves the assistant.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
ollama pull nomic-embed-text
```

Store Gemini credentials once in the ignored project `.env` file. The app loads it automatically on every Flask start, so restarting from a new terminal does not lose the assistant configuration. The API key never belongs in browser code, committed files, or local diagnostics.

```powershell
Copy-Item .env.example .env -ErrorAction SilentlyContinue
notepad .env
```

Set the following values in that file, then save it. Process-level variables remain supported and take precedence when needed.

```dotenv
GEMINI_API_KEY=your-gemini-api-key
RAG_RETRIEVAL_MODE=local_hybrid
RAG_OLLAMA_EMBEDDING_MODEL=nomic-embed-text
```

Build the index whenever an enabled approved source changes. The build splits Markdown by headings, creates stable overlapping chunks, extracts only source-authored Mermaid blocks, embeds chunks locally, and writes the index below ignored `instance/rag_local_index/`.

```powershell
.\.venv\Scripts\python.exe scripts\build_local_rag_index.py
.\.venv\Scripts\python.exe scripts\build_local_rag_index.py --check
.\.venv\Scripts\python.exe -m flask --app app run --host 127.0.0.1 --port 8102 --no-reload
```

Flask refuses to serve local retrieval when the index is missing, malformed, built with another embedding model, references an unapproved source, has mismatched vector files, or no longer matches the current source hashes. Rebuild it rather than bypassing those checks.

## Gemini File Search alternative

The prior Gemini File Search store remains untouched, but it will no longer pass the exact registry check after approved sources change. Do not update, delete, or reuse it for the expanded portfolio. Create a separate dedicated store if you need to switch adapters:

```powershell
.\.venv\Scripts\python.exe scripts\ingest_knowledge.py --create-file-search-store --name "mihir-portfolio-public-knowledge-current"
```

The command prints the new store ID after it has created the store and ingested every enabled approved source. Verify the completed upload, place that ID only in the server environment file, then select the alternative adapter:

```powershell
$env:RAG_RETRIEVAL_MODE = "gemini_file_search"
$env:RAG_GEMINI_FILE_SEARCH_STORE_ID = "fileSearchStores/your-existing-store"
.\.venv\Scripts\python.exe -m flask --app app run --host 127.0.0.1 --port 8102 --no-reload
```

Do not use `scripts/ingest_knowledge.py` unless you intentionally want to create a new clean File Search store. The local build command never calls it, and the existing store remains unchanged.

## Container deployment

The production deployment remains Docker-based and provider-neutral. [deployment/README.md](deployment/README.md) documents the one-VM stack, private Ollama network, Gunicorn, Nginx, HTTPS bootstrap, health checks, AWS cost guardrails, and later VM-provider migration path. Set `PUBLIC_ORIGIN` only in the server environment file; never hard-code or assume the final public hostname in the repository.

## Conversation and evidence rules

For each browser page, the client holds one opaque random UUID. Flask maps it in process memory to only the latest stored Gemini **final reply** interaction ID. A page reload uses a new UUID. On page exit, the app requests provider-side deletion; TTL cleanup is a fallback. Browser storage and diagnostics never contain a transcript, API key, raw question, answer, prompt, or model reasoning.

The router sees the prior final reply only to resolve references such as “Which services?” Gemini requires a continuing request to be stored, so the router's continuation node is deleted immediately after it returns its JSON plan. It is never used as the saved browser-session pointer or as evidence. A grounded final answer contains selected approved evidence and must attach every claim to verified local chunk IDs or validated File Search document evidence. Gemini cannot select unregistered files, invent a citation, expose internal metadata, or render visitor-provided Mermaid.

Architecture and flowchart answers can return one or more Mermaid blocks only when they were extracted verbatim from approved cited sources. Explicit diagram wording is resolved deterministically against those approved records, so the answer writer cannot suppress, invent, or alter the requested diagram. The browser renders each block with a pinned Mermaid client and `securityLevel: 'strict'`.

Ordinary portfolio questions keep the concise one-to-three-claim response path. Explicit wording such as “tell me everything,” “deep dive,” or “detailed breakdown” selects a separate structured response profile with broad, source-ordered evidence coverage and titled sections. If Gemini's detailed JSON cannot be safely parsed despite approved evidence being available, the assistant falls back to a source-authored, citation-validated section outline rather than refusing the request. This opt-in rule prevents routine replies from becoming unexpectedly long.

## Important environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY` | none | Required server-only Gemini key for routing and answer writing. |
| `RAG_RETRIEVAL_MODE` | `local_hybrid` | `local_hybrid` or `gemini_file_search`. |
| `RAG_LOCAL_INDEX_DIR` | `instance/rag_local_index` | Ignored local index directory. |
| `RAG_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Private Ollama endpoint. |
| `RAG_OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model used to build and query the index. |
| `RAG_LOCAL_TOP_K` | `6` | Maximum selected local evidence chunks. |
| `RAG_GEMINI_FILE_SEARCH_STORE_ID` | none | Required only for `gemini_file_search`. |
| `RAG_GEMINI_MODEL` | `gemini-3.5-flash-lite` | Gemini router and answer writer. |
| `RAG_MAX_QUESTION_CHARACTERS` | `2000` | Server-side input bound. |
| `RAG_STATEFUL_CONVERSATIONS` | `true` | Keeps the per-page final-response interaction chain. |
| `RAG_CONVERSATION_SESSION_TTL_SECONDS` | `1200` | Process-memory interaction-ID lifetime. |
| `RAG_ENV` | `development` | Use `production` when publicly hosting. |
| `RAG_ENABLE_RATE_LIMITS` | unset | Optional override. When unset, development is uncapped and production enables limits. |
| `RAG_RATE_LIMIT_PER_MINUTE` | `12` | Production default per visitor IP. |
| `RAG_GLOBAL_RATE_LIMIT_PER_MINUTE` | `60` | Production default across this Flask process. |
| `RAG_LOCAL_DIAGNOSTICS_PATH` | unset | Optional ignored development trace file. |

Local request limits are intentionally disabled by default in development so evaluation does not compete with provider quota. In production the app enables 12 visitor requests per IP per minute and 60 per Flask process by default. A public multi-worker deployment should add shared rate limiting and bot protection at the reverse proxy or WAF.

## Diagnostics and evaluation

Set a local-only diagnostics path before starting Flask when investigating failures:

```powershell
$env:RAG_LOCAL_DIAGNOSTICS_PATH = "$PWD\instance\rag_provider_failure.json"
```

The rolling trace records retrieval mode, local index version, route mode and scope, selected source and chunk IDs, score bands, diagram decision, durations, and scrubbed provider failure category. It intentionally excludes visitor text, output text, prompts, source passages, API keys, and hidden model reasoning.

Run the checks without a Gemini request:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q rag scripts
.\.venv\Scripts\python.exe scripts\build_local_rag_index.py --check
```

`evals/portfolio_eval.jsonl` covers exact technology lookup, misspellings, project catalogue completeness, architecture and diagram questions, follow-ups, unsupported questions, and private-information refusal. Retrieval success against expected approved sources is the gate before evaluating any Gemini-written answer.

## Public-source hygiene

Only reviewed, enabled `knowledge/sources.json` entries may enter either retrieval adapter. Keep phone numbers, addresses, credentials, private notes, chats, secrets, grade records, and raw exports out of `knowledge/public/`. A disabled registry entry or an unregistered file is not retrieval evidence.

If a source changes, review it, update its registry hash through the normal ingestion/source workflow, and rebuild the local index. A File Search store has its own persistence lifecycle; removing a local registry entry does not delete remote content that was previously uploaded.
