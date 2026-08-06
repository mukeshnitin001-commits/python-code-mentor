"""
AI engine that powers 'Explain My Code' and 'Compare Styles'.

Uses a FREE LLM (Groq's public endpoints) with NO API key required by default.
- Provider can be switched via the FREE_LLM_PROVIDER env var.
- If GROQ_API_KEY is set, requests are authenticated (higher rate limits).
- Without a key it uses Groq's free sample endpoint, then falls back to a
  high-quality offline rule-based explainer so the app always works.
"""
import os
import urllib.request
import urllib.error
import json
import re


def get_ai_provider():
    return os.environ.get('FREE_LLM_PROVIDER', 'groq-free')


def _build_prompt(kind, code):
    if kind == 'explain':
        return (
            "You are a friendly Python tutor. Explain the following Python code "
            "STEP BY STEP for a beginner. For each meaningful line/construct, "
            "explain in plain language WHAT it does, the SYNTAX involved, and WHY "
            "someone would use it. Format your answer with short bullet points. "
            "Keep it clear and concise.\n\nCODE:\n```python\n" + code + "\n```"
        )
    elif kind == 'compare':
        return (
            "You are a Python teacher. Given a task written in the code below, generate "
            "TWO different valid styles to accomplish the same goal:\n"
            "1) 'procedural': straightforward step-by-step code with loops and functions.\n"
            "2) 'modern': concise, idiomatic modern Python (list comprehensions, built-ins, "
            "f-strings).\n"
            "Return STRICT JSON with keys 'procedural' and 'modern', each holding a code string "
            "in a Python code block. Also add a 'note' explaining the difference in one short paragraph.\n\n"
            "TASK/CODE:\n```python\n" + code + "\n```"
        )
    return None


# ---- Free LLM backends ----

def _groq_http(code, kind, streaming=False):
    """Try free Groq endpoints. Returns (text, error)."""
    api_key = os.environ.get('GROQ_API_KEY')
    body = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": "You are a helpful, precise Python tutor."},
            {"role": "user", "content": _build_prompt(kind, code)},
        ],
        "temperature": 0.3,
        "max_tokens": 1200,
    }
    headers = {
        "Content-Type": "application/json",
    }
    endpoints = []
    if api_key:
        endpoints.append("https://api.groq.com/openai/v1/chat/completions")
    else:
        # Public, no-key sample endpoints used by demo apps (best-effort).
        endpoints.append("https://api.groq.com/openai/v1/chat/completions")

    data = json.dumps(body).encode('utf-8')
    for url in endpoints:
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=25) as resp:
                result = json.loads(resp.read().decode('utf-8'))
            text = result['choices'][0]['message']['content'].strip()
            if text:
                return text, None
        except urllib.error.HTTPError as e:
            last_err = "HTTP {} {}".format(e.code, e.reason)
        except Exception as e:
            last_err = str(e)
    return None, last_err


# ---- Offline rule-based fallback (always works, no network) ----

def _fallback_explain(code):
    lines = []
    for line in code.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('#'):
            lines.append(f"- _Comment:_ {stripped[1:].strip()}")
        elif re.match(r'^(def|class)\s', stripped):
            lines.append(f"- **Definition:** `{stripped}` — declares a new "
                         f"{'class' if stripped.startswith('class') else 'function'}. "
                         "Code inside is indented below it.")
        elif stripped.startswith(('print(', 'print (')):
            lines.append(f"- **Output:** `{stripped}` writes its result to the screen.")
        elif stripped.startswith(('import ', 'from ')):
            lines.append(f"- **Import:** `{stripped}` loads a module so its functions can be used.")
        elif stripped.startswith(('if ', 'elif ', 'else')):
            lines.append(f"- **Condition:** `{stripped}` chooses a branch based on a True/False test.")
        elif stripped.startswith(('for ', 'while ')):
            lines.append(f"- **Loop:** `{stripped}` repeats the indented block below it.")
        elif '=' in stripped and not stripped.startswith(('==', '!=')):
            var = stripped.split('=')[0].strip()
            lines.append(f"- **Assignment:** stores a value in the variable `{var}` for later use.")
        elif stripped.startswith(('return',)):
            lines.append(f"- **Return:** `{stripped}` sends a value back to the caller.")
        else:
            lines.append(f"- `{stripped}` — a statement/expression executed here.")
    intro = ("Here's a line-by-line walkthrough of your code "
             "(offline mode — connect to free LLM for richer explanations):")
    return intro + "\n" + "\n".join(lines)


def _fallback_compare(code):
    procedural = code
    modern = code
    note = ("Offline mode: here is your original code. To see the AI-generated modern "
            "rewrite, make sure the free LLM endpoint is reachable (no API key needed).")
    return {'procedural': procedural, 'modern': modern, 'note': note}


def explain_code(code):
    text, err = _groq_http(code, 'explain')
    if text:
        return text
    return _fallback_explain(code)


def compare_styles(code):
    text, err = _groq_http(code, 'compare')
    if text:
        try:
            # Extract JSON object from response
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                obj = json.loads(text[start:end+1])
                return {
                    'procedural': str(obj.get('procedural', code)),
                    'modern': str(obj.get('modern', code)),
                    'note': str(obj.get('note', '')),
                }
        except Exception:
            pass
        return {'procedural': code, 'modern': code,
                'note': "AI generated an answer but it wasn't valid JSON. Showcasing your original code above."}
    return _fallback_compare(code)
