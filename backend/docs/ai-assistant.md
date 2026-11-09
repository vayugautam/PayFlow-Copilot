# PayFlow Copilot AI Assistant

Phase 4 adds authenticated conversations and a Groq tool-calling assistant.

## Architecture

`/api/v1/chat` uses the existing JWT dependency and async SQLAlchemy session. Conversation
and message metadata is stored in PostgreSQL. The assistant service loads a bounded history,
calls the configured Groq model, validates tool arguments with Pydantic, executes only tools
registered in `chat_tools.py`, and persists the assistant/tool messages.

The available tools are:

- `get_transaction`
- `list_transactions`
- `analyze_transaction_failure`
- `retrieve_payment_policy`

Tools always derive ownership from the authenticated user. The model cannot provide a
`user_id`, execute code, or access SQL/Qdrant directly. Tool execution is limited to four
rounds per message.

## Endpoints

- `POST /api/v1/chat/conversations`
- `GET /api/v1/chat/conversations`
- `GET /api/v1/chat/conversations/{conversation_id}`
- `GET /api/v1/chat/conversations/{conversation_id}/messages`
- `POST /api/v1/chat/conversations/{conversation_id}/messages`

The message response contains the user message, assistant message, tool summaries, and
policy citations. Citations are copied only from policy retrieval results; an empty retrieval
produces an empty citation list.

## Configuration

The existing settings are used:

- `GROQ_API_KEY` (or the existing `LLM_API_KEY` fallback)
- `LLM_PROVIDER`
- `LLM_MODEL`
- `GROQ_TIMEOUT_SECONDS`
- `GROQ_MAX_RETRIES`

The configured model is never silently replaced. Authentication, rate-limit, timeout and
bounded retry failures are returned as safe API errors without credentials or raw traces.

## Security boundaries

Conversation, transaction, and document access is ownership-scoped. The system prompt treats
user and retrieved-document text as untrusted. The assistant explains and drafts information
only; it cannot issue refunds, retry payments, change statuses, or create disputes.

## Database and tests

Apply the migration from `backend/`:

```text
alembic upgrade head
alembic current
```

Run the test suite:

```text
pytest -q
```

Automated tests must mock Groq. An optional live check may be performed only when
`GROQ_API_KEY` is already configured; never print the key or request headers.

## Windows DEBUG environment issue

Pydantic reads process environment variables with precedence over `.env`. An inherited
`DEBUG=release` therefore overrides `.env`'s boolean value and must be corrected rather than
silently ignored. In PowerShell for the current process:

```powershell
Remove-Item Env:DEBUG
# or
$env:DEBUG = "true"
```

For a persistent Windows user variable, open **System Properties → Environment Variables**,
edit or remove `DEBUG`, then restart the terminal/VS Code. The application intentionally keeps
one `DEBUG` setting and does not introduce an `APP_DEBUG` duplicate.
