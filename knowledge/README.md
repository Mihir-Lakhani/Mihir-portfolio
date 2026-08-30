# Approved public knowledge base

This folder is the only content that the portfolio assistant may ingest.

The raw portfolio HTML and raw resume are deliberately **not** ingestion inputs. They can contain contact details, stale copy, or unfinished project links. Instead, the Markdown files in `public/` are curated summaries of information that is approved for a public assistant.

## Adding or changing a source

1. Edit or add a document under `public/`.
2. Add a matching entry to `sources.json` with a stable `id`, a human-readable title, and its canonical public URL.
3. Mark a source `public: true` and `enabled: true` only after reviewing it for contact details, private data, and unsupported claims.
4. Run `python scripts/ingest_knowledge.py --dry-run` to review the files that would be uploaded.
5. Run the ingestion command only after `GEMINI_API_KEY` and either an existing `RAG_GEMINI_FILE_SEARCH_STORE_ID` or the `--create-file-search-store` option are configured/selected.

The assistant accepts only sources in this manifest, and its runtime additionally filters Gemini File Search to `visibility=public`. Project case studies are intentionally separate sources so each answer can cite the actual project rather than a generic project collection.
