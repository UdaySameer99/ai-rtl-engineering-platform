import os, re, subprocess, tempfile, time
from pathlib import Path
from flask import Flask, request, jsonify, render_template
import requests

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

# OpenRouter is preferred when configured. Gemini remains available as a fallback.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
MAX_EXEC_SECONDS = int(os.getenv("SIM_TIMEOUT", "12"))

SYSTEM_PROMPT = """You are a senior RTL design and verification engineer.
Work with synthesizable Verilog/SystemVerilog unless the user explicitly asks otherwise.
Be precise. Never claim a design is correct without evidence.
When reviewing code, distinguish syntax/compile errors, simulation failures, coding-style concerns,
and potential functional/design bugs. Explain uncertainty and assumptions.
When asked to generate RTL, return complete code and a useful self-checking testbench when requested.
Do not use markdown fences around code in structured JSON fields."""


def call_openrouter(prompt, temperature=0.2):
    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": 8192,
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://ai-rtl-engineering-platform.onrender.com",
        "X-Title": "AI RTL Engineering Platform",
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=90)
        if r.status_code >= 400:
            try:
                detail = r.json().get("error", {}).get("message", r.text)
            except Exception:
                detail = r.text
            return None, f"OpenRouter API error ({r.status_code}): {detail}"
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "\n".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        if not isinstance(content, str) or not content.strip():
            return None, "OpenRouter returned an empty response. Try again or select another model."
        return content, None
    except requests.RequestException as e:
        return None, f"Could not reach OpenRouter: {e}"
    except (KeyError, IndexError, TypeError, ValueError):
        return None, "OpenRouter returned an unexpected response."


def call_gemini(prompt, temperature=0.2):
    if not GEMINI_API_KEY:
        return None, "GEMINI_API_KEY is not configured."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": 8192},
    }
    try:
        r = requests.post(url, json=payload, timeout=60)
        if r.status_code >= 400:
            try:
                detail = r.json().get("error", {}).get("message", r.text)
            except Exception:
                detail = r.text
            return None, f"Gemini API error ({r.status_code}): {detail}"
        data = r.json()
        text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        return text, None
    except requests.RequestException as e:
        return None, f"Could not reach Gemini: {e}"
    except (KeyError, IndexError, TypeError, ValueError):
        return None, "Gemini returned an unexpected response."


def call_ai(prompt, temperature=0.2):
    # Use OpenRouter as the primary provider whenever its key is present.
    if OPENROUTER_API_KEY:
        result, err = call_openrouter(prompt, temperature)
        if not err:
            return result, None
        # Only fall back to Gemini when it is configured. Include both errors if it fails.
        if GEMINI_API_KEY:
            fallback_result, fallback_err = call_gemini(prompt, temperature)
            if not fallback_err:
                return fallback_result, None
            return None, f"Primary provider failed: {err} | Gemini fallback failed: {fallback_err}"
        return None, err
    if GEMINI_API_KEY:
        return call_gemini(prompt, temperature)
    return None, "No AI provider is configured. Add OPENROUTER_API_KEY or GEMINI_API_KEY in Render Environment."


def strip_fences(s):
    s = (s or "").strip()
    s = re.sub(r"^```(?:verilog|systemverilog|sv|v|text)?\s*", "", s, flags=re.I)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return jsonify({
        "status": "online",
        "ai_configured": bool(OPENROUTER_API_KEY or GEMINI_API_KEY),
        "ai_provider": "OpenRouter" if OPENROUTER_API_KEY else ("Gemini" if GEMINI_API_KEY else "none"),
        "compiler_available": bool(__import__("shutil").which("iverilog")),
        "simulator_available": bool(__import__("shutil").which("vvp")),
    })


@app.post("/api/ai")
def ai():
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "generate")
    prompt = (body.get("prompt") or "").strip()
    code = (body.get("code") or "").strip()
    testbench = (body.get("testbench") or "").strip()
    if not prompt and mode in ("generate", "testbench"):
        return jsonify(error="Enter a design prompt first."), 400
    if mode in ("review", "fix") and not code:
        return jsonify(error="Paste RTL code to continue."), 400
    if mode == "generate":
        task = f"""Create RTL from this specification:
{prompt}
Return exactly these sections:
DESIGN_NOTES:
brief assumptions and design choices
RTL_CODE:
complete Verilog/SystemVerilog source
TESTBENCH:
a self-checking testbench with meaningful checks
Do not claim simulation was run."""
    elif mode == "review":
        task = f"""Review this RTL carefully.
User's focus (if any): {prompt or 'Find functional, structural, reset, timing-semantics, and coding issues.'}
RTL:
{code}
Existing testbench:
{testbench or '(not provided)'}
Return sections:
SUMMARY:
FINDINGS:
For each finding include severity (Critical/High/Medium/Low), location, why it matters, and suggested fix.
CORRECTED_CODE:
Provide a complete corrected version only if a defensible correction is possible; otherwise say what information is missing.
TEST_RECOMMENDATIONS:
Give concrete tests. Clearly distinguish confirmed issues from potential risks."""
    elif mode == "fix":
        task = f"""Fix the following RTL based on the request.
Request: {prompt or 'Correct confirmed bugs while preserving intended behaviour.'}
RTL:
{code}
Testbench:
{testbench or '(not provided)'}
Return sections:
CHANGE_SUMMARY:
CORRECTED_CODE:
TESTBENCH:
ASSUMPTIONS:
Do not silently change the specification."""
    elif mode == "testbench":
        task = f"""Write a robust self-checking Verilog/SystemVerilog testbench for this design specification:
{prompt}
RTL if available:
{code or '(not provided)'}
Return only the complete testbench code followed by a short list of assumptions."""
    else:
        return jsonify(error="Unknown AI operation."), 400
    result, err = call_ai(task, 0.15 if mode == "review" else 0.25)
    if err:
        return jsonify(error=err), 502
    return jsonify(result=result, mode=mode)


@app.post("/api/simulate")
def simulate():
    body = request.get_json(silent=True) or {}
    rtl = (body.get("code") or "").strip()
    tb = (body.get("testbench") or "").strip()
    top = (body.get("top") or "").strip()
    if not rtl:
        return jsonify(error="RTL source is required."), 400
    if not tb:
        return jsonify(error="A testbench is required for simulation. Generate one with the AI assistant or paste your own."), 400
    if len(rtl) + len(tb) > 180000:
        return jsonify(error="Combined source is too large (maximum 180 KB)."), 413
    if not __import__("shutil").which("iverilog") or not __import__("shutil").which("vvp"):
        return jsonify(error="Cloud compiler is not installed on this deployment. Check Dockerfile deployment logs."), 503
    if top and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", top):
        return jsonify(error="Invalid top-module name."), 400
    started = time.time()
    with tempfile.TemporaryDirectory(prefix="rtl_job_") as td:
        td = Path(td)
        (td / "design.v").write_text(rtl, encoding="utf-8")
        (td / "testbench.v").write_text(tb, encoding="utf-8")
        output = td / "simulation.out"
        cmd = ["iverilog", "-g2012", "-Wall", "-o", str(output)]
        if top:
            cmd += ["-s", top]
        cmd += [str(td / "design.v"), str(td / "testbench.v")]
        try:
            comp = subprocess.run(cmd, capture_output=True, text=True, timeout=MAX_EXEC_SECONDS)
            if comp.returncode != 0:
                return jsonify(status="compile_error", compile_output=comp.stdout + comp.stderr,
                               simulation_output="", duration=round(time.time()-started, 2))
            run = subprocess.run(["vvp", str(output)], capture_output=True, text=True, timeout=MAX_EXEC_SECONDS)
            return jsonify(status="passed" if run.returncode == 0 else "simulation_error",
                           compile_output=comp.stdout + comp.stderr,
                           simulation_output=run.stdout + run.stderr,
                           duration=round(time.time()-started, 2), exit_code=run.returncode)
        except subprocess.TimeoutExpired:
            return jsonify(status="timeout", error="Simulation exceeded the cloud execution time limit. Check for an infinite clock/loop or increase SIM_TIMEOUT.", duration=round(time.time()-started, 2)), 408


@app.errorhandler(413)
def too_large(_):
    return jsonify(error="Request too large. Maximum upload size is 1 MB."), 413


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
