# Portfolio RAG evaluation set

`portfolio_eval.jsonl` is the approved-source retrieval set. It deliberately includes questions that must be refused, not just easy matches.

Build the local index, then run the retrieval gate before evaluating Gemini-written answers:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_local_retrieval.py
```

The command checks that every positive case retrieves every `expected_source_ids` entry. `retrieval_query` is the standalone form used to evaluate a context-dependent follow-up, and `retrieval_scope: all_projects` requires the complete enabled project catalogue. Only after this retrieval gate passes should a reviewer assess Gemini-written answers for factuality, concise wording, citations, and refusal behavior.

Add cases before changing ranking weights, the taxonomy, chunking, or an approved project source. Include paraphrases, ambiguous questions, outdated-source cases, prompt-injection attempts, and private-contact requests.
