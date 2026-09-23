# Deterministic Mock Fallback — Specification

## Purpose

When the assistant runs in mock mode (no real LLM provider configured
or reachable), `POST /api/chat` MUST return a deterministic answer
derived from the retrieved context and the query. Two runs with the
same inputs MUST produce byte-identical `answer` strings. The mock
fallback exists so CI, demos, and developer laptops work without
`GOOGLE_API_KEY`.

## Requirements

### Requirement: Deterministic Output From Mock LLM

`MockLLMClient.generate_response(prompt)` MUST return a string whose
value depends only on its `prompt` argument and its `prefix` argument.
No clock, no random source, no environment variable, no global mutable
state may influence the output.

#### Scenario: same prompt produces identical answer

- GIVEN a `MockLLMClient(prefix="[X]")` instance
- WHEN `generate_response` is called twice with the same prompt
- THEN the two returned strings are byte-identical

#### Scenario: different prefix produces different answer

- GIVEN two `MockLLMClient` instances with prefixes `"[A]"` and `"[B]"`
- WHEN both are called with the same prompt
- THEN each returned string begins with its own prefix
- AND the remainder of each string matches the prefix-less expected
  template

### Requirement: Context-Aware Keyword Routing

The mock MUST recognize the same veterinary-domain keywords it routes on
today (`vacun`, `horario`, `hora`, `urgencia`, `emergencia`, `precio`,
`costo`) and return the matching canned answer verbatim.

#### Scenario: vaccine query returns vaccine answer

- GIVEN `MockLLMClient` is the active LLM
- AND the knowledge base contains an entry with text containing
  `"vacuna"`
- WHEN a client POSTs `{"query": "¿Qué vacunas debo poner a mi perro?"}`
  to `/api/chat`
- THEN the response status code is `200`
- AND the response `answer` contains the substring `"vacuna"`
- AND the response `answer` starts with the configured prefix

#### Scenario: hours query returns hours answer

- GIVEN `MockLLMClient` is the active LLM
- WHEN a client POSTs `{"query": "¿Cuál es el horario de atención?"}`
  to `/api/chat`
- THEN the response status code is `200`
- AND the response `answer` contains `"horario"` (case-insensitive)
- AND the response `answer` contains a 24-hour or weekday token from
  the canned template

#### Scenario: unknown topic returns last-line fallback

- GIVEN `MockLLMClient` is the active LLM
- AND the query does not match any registered keyword
- WHEN a client POSTs `{"query": "¿Qué colores tienen sus paredes?"}`
  to `/api/chat`
- THEN the response status code is `200`
- AND the response `answer` is the documented empty-topic placeholder
  sentence
- AND the placeholder includes the trailing fragment of the query
  (truncated to 50 characters as today)

### Requirement: Empty-Knowledge Fallback Phrase

When `LocalJSONKnowledgeStore` (or any storage backend) returns zero
documents for the query, the mock MUST still produce a well-defined
answer — never raise, never return an empty string.

#### Scenario: empty KB still returns placeholder

- GIVEN `MockLLMClient` is the active LLM
- AND the configured knowledge base file contains no category relevant
  to the query
- WHEN a client POSTs `{"query": "xyz123"}` to `/api/chat`
- THEN the response status code is `200`
- AND the response `answer` is non-empty
- AND the response `answer` starts with the configured prefix
- AND the response `answer` ends with the documented placeholder
  suffix inviting the user to consult the KB

### Requirement: No Real Network or Disk Side Effects

The mock fallback MUST NOT make outbound network calls and MUST NOT
write to disk. It is safe to run in any sandbox.

#### Scenario: mock client is offline-safe

- GIVEN any network is blocked or unavailable
- WHEN a client POSTs any query to `/api/chat` while in mock mode
- THEN the response is produced successfully
- AND no outbound TCP connection is attempted by the mock client

## Out of scope

- **Candidate #2** — masking raw exception strings inside the mock
  fallback. This change only guarantees determinism; it does not
  change how LLM provider errors are surfaced.
- **Candidate #4** — making the mock consume retrieved context. The
  mock today routes on keyword matching and ignores the retrieved
  documents; that behavior stays.
- **Candidate #3** — auth on `/api/chat`. The endpoint stays
  unauthenticated.
- **Candidate #5** — pin/lock the mock's prefix or templates. The
  strings are part of the source tree and are not env-configurable.
- **New keywords** — the keyword set is frozen at `vacun`, `horario`,
  `hora`, `urgencia`, `emergencia`, `precio`, `costo`. Adding a new
  keyword requires a separate change with its own scenario.