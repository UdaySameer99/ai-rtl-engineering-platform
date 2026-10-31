# AI RTL Engineering Platform

A browser-based RTL assistant with cloud-hosted AI analysis and cloud-hosted Icarus Verilog compilation/simulation.

## What it does

- Prompt-to-Verilog/SystemVerilog generation
- AI review for potential RTL bugs and coding issues
- AI-assisted code correction
- Testbench generation
- Server-side compilation with Icarus Verilog
- Server-side simulation with `vvp`
- Combined compile and simulation output

## Important limitations

1. The application does not run a local LLM or compiler on the user's laptop. The browser is only the user interface; AI calls and HDL compilation happen on the deployed server.
2. Gemini API access requires your own API key. Google may provide a free tier, but quotas, model availability, and eligibility can change. Free usage is not unlimited or guaranteed.
3. AI review is advisory, not formal verification. A successful compile does not prove functional correctness, timing closure, synthesizability on every FPGA/ASIC tool, or hardware safety.
4. Icarus Verilog supports common Verilog/SystemVerilog simulation features but is not a replacement for Vivado, Questa, VCS, or formal verification.
5. The free hosting plan may sleep when idle and can have resource/time limits. The first request after inactivity may be slow.

## Deploy online (recommended: Render + GitHub)

You need a GitHub account, a Render account, and a Gemini API key.

### 1. Get a Gemini API key
- Visit https://aistudio.google.com/app/apikey
- Create an API key.
- Keep it private. Do not paste it into frontend code or commit it to GitHub.

### 2. Upload this project to GitHub
- Extract the ZIP.
- Create a new GitHub repository.
- Upload all extracted files and folders to the repository root.

### 3. Deploy to Render
- Visit https://render.com/
- Sign in and choose **New → Blueprint**.
- Connect your GitHub repository.
- Render detects `render.yaml`.
- When prompted, enter `GEMINI_API_KEY` as the secret value.
- Deploy. The first Docker build can take several minutes.

### 4. Open the deployed URL
Render provides a URL similar to `https://your-service-name.onrender.com`.
Open it in any modern browser. No local software installation is needed.

### 5. Check service health
Open `https://YOUR-RENDER-URL/api/health`.
Expected fields:
- `status: online`
- `ai_configured: true`
- `compiler_available: true`
- `simulator_available: true`

If any field is false, inspect Render deployment logs and environment variables.

## How to use

1. **Generate RTL:** enter a specification such as "4-bit synchronous up counter, active-low asynchronous reset".
2. Copy the generated RTL into the RTL editor.
3. Use **Review RTL** to request an engineering review.
4. Use **Fix RTL** to generate a corrected version.
5. Generate or paste a testbench.
6. Click **Compile & Simulate**.
7. Read compiler diagnostics and simulation output separately.

## API endpoints

- `GET /api/health`
- `POST /api/ai` JSON: `{ "mode": "generate|review|fix|testbench", "prompt": "...", "code": "...", "testbench": "..." }`
- `POST /api/simulate` JSON: `{ "code": "...", "testbench": "...", "top": "optional_top_module" }`

## Local development (optional only)
This is only for developers. The end user does not need to run it locally.

```bash
python -m venv .venv
# activate the environment
pip install -r requirements.txt
# install Icarus Verilog separately
export GEMINI_API_KEY="your-key"
python app.py
```

## Security notes
- The Gemini key is read only from the server environment.
- Simulation runs in a temporary directory with a time limit and a 1 MB request limit.
- For a public production deployment, add authentication, per-user quotas, stricter rate limiting, request logging policy, and stronger sandbox isolation before allowing untrusted users.
