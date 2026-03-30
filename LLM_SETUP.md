# LLM setup (Groq or OpenAI)

The compliance agent uses an LLM only to **explain** violations using retrieved regulations. It does not make compliance decisions.

## Groq (recommended for speed)

1. **Create a `.env` file** in the project root (same folder as `compliance_agent.py`):
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env`** and set your Groq API key:
   ```
   GROQ_API_KEY=gsk_your_actual_key_here
   ```
   **Do not commit `.env`** — it is in `.gitignore`.

3. **Optional:** Use a different Groq model (default is `llama-3.1-8b-instant`):
   ```
   GROQ_MODEL=llama-3.1-70b-versatile
   ```

## OpenAI (alternative)

If you prefer OpenAI, set in `.env`:
```
OPENAI_API_KEY=sk-your_openai_key_here
```
Optional: `OPENAI_MODEL=gpt-4o-mini` (default).

**Precedence:** If both are set, the agent uses **Groq** first.

## Using the LLM

- **Notebook 05:** Run all cells. The first cell loads `.env` and sets `USE_LLM=True` when a key is present. You should see RAG-grounded explanations in the output.
- **CLI:** Export the key or use `.env`, then:
  ```bash
  export COMPLIANCE_USE_LLM=1
  python compliance_agent.py path/to/report.txt
  ```
- **From Python:** Ensure `GROQ_API_KEY` or `OPENAI_API_KEY` is in the environment (or in `.env`), then call `run(report_text, use_llm=True)`.
