# Setup: the writing help (S-087)

"Help me write this" on the applicant form needs an LLM. Without it (`ASSIST_ENABLED=false`, the default) the button is
hidden and everything else works. If it is on but the model does not answer, the applicant gets a short error and the
form and the check keep working.

## Claude Opus 5.5 (default)
Put `ANTHROPIC_API_KEY` in `.env`. `make dev` sets `ASSIST_ENABLED=true`. The draft's purpose, question and definitions and
the rules' findings go to Anthropic; applicant names and patient data do not. A draft costs about 1 to 3 cents.

## Self-hosted Qwen (option)
Set `ASSIST_PROVIDER=ollama`. The model is `qwen3.8:27b` (Q4, 17 GB) in Ollama on the event's Exoscale instance (RTX A5000,
23 GB). Ollama listens only on the instance's `127.0.0.1:11434`, so no extra port is open, and the app reaches it through
an SSH tunnel. The instance's IP and SSH key are in the event guide, not in git.
```bash
ssh -N -i <key-file> -L 127.0.0.1:11435:127.0.0.1:11434 ubuntu@<instance-ip>
curl -s 127.0.0.1:11435/api/tags   # lists qwen3.8:27b
```
Ollama starts by itself after an instance restart. The first answer then takes about 90 s while the model loads, and a warm
answer takes 2 to 10 s.

Other settings: `ASSIST_MODEL`, `ASSIST_URL` (default `http://127.0.0.1:11435`), `ASSIST_TIMEOUT` (default 120 s).
