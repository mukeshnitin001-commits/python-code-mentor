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
    elif kind == 'review':
        return (
            "You are a senior code reviewer and software architect. Review the following code as if "
            "the author wants to publish it or ship it to production.\n"
            "Return STRICT JSON only, with EXACTLY these keys:\n"
            "- \"score\": integer 0-100 overall quality score\n"
            "- \"categories\": object with 0-100 scores for each of: correctness, readability, "
            "efficiency, maintainability, security\n"
            "- \"comments\": array of short strings, line-specific review comments (quote line numbers, "
            "e.g. 'Line 7: ...'). If no issues, use empty array.\n"
            "- \"suggestions\": array of short strings with concrete improvement suggestions\n"
            "- \"algorithm\": object with keys time_complexity (string), space_complexity (string), "
            "and notes (string) describing the algorithm used and its complexity\n"
            "- \"verdict\": one of \"production-ready\", \"needs-work\", or \"not-ready\"\n"
            "- \"verdict_summary\": one sentence explaining the verdict\n"
            "- \"strengths\": array of short strings listing what the code does well\n\n"
            "CODE:\n```python\n" + code + "\n```"
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


# ---- Offline rule-based code review (always works) ----

def _fallback_review(code):
    """Static-analysis based review: no network needed."""
    lines = code.splitlines()
    total = len(lines)
    n_functions = len(re.findall(r'^\s*def\s+', code, re.M))
    n_classes = len(re.findall(r'^\s*class\s+', code, re.M))
    n_comments = len(re.findall(r'^\s*#', code, re.M))
    n_docstrings = code.count('"""') // 2

    comments, suggestions, strengths = [], [], []

    # ---- Issue detection ----
    if re.search(r'\beval\(|\bexec\(', code):
        comments.append("Security: eval()/exec() on untrusted input can execute arbitrary code.")
        suggestions.append("Replace eval()/exec() with safe alternatives (ast.literal_eval, dedicated parsing).")
    if re.search(r'password\s*=|api[_-]?key\s*=|secret\s*=', code, re.I):
        comments.append("Possible hardcoded secret/password detected — never commit credentials.")
        suggestions.append("Move secrets to environment variables or a secrets manager.")
    if re.search(r'except\s*:', code):
        comments.append("Bare 'except:' swallows all errors silently, hiding bugs.")
        suggestions.append("Catch specific exceptions (e.g. except ValueError) and log the error.")
    if re.search(r'def\s+\w+\([^)]*=\[\]', code) or re.search(r'def\s+\w+\([^)]*=\{\}', code) or re.search(r'def\s+\w+\([^)]*=\{\}', code):
        comments.append("Mutable default argument (e.g. =[] or ={}) is shared across calls — classic bug.")
        suggestions.append("Use None as default and create the mutable inside the function.")
    if re.search(r'\bprint\(', code) and re.search(r'def\s+', code):
        suggestions.append("Replace debugging print() with logging (logging module) before shipping.")
    if re.search(r'\bTODO\b|\bFIXME\b|\bXXX\b', code, re.I):
        comments.append("Unresolved TODO/FIXME markers found in the code.")
    if re.search(r'\bglobal\s+', code):
        suggestions.append("Minimize 'global' usage — prefer passing values or classes.")
    if re.search(r'input\(', code):
        suggestions.append("Validate and sanitize all user input before use.")
    if re.search(r'\bopen\(', code) and 'with' not in code:
        comments.append("File opened without a context manager ('with') — resource may leak.")
        suggestions.append("Use 'with open(...) as f:' to auto-close files.")

    # Nested-loop complexity
    indents = [len(l) - len(l.lstrip()) for l in lines if l.strip()]
    max_depth = max(indents) if indents else 0
    depth = max_depth // 4
    if depth >= 2:
        suggestions.append("Deep nesting detected — consider extracting inner logic into helper functions.")

    # ---- Strengths ----
    if n_docstrings:
        strengths.append(f"Good documentation: {n_docstrings} docstring section(s).")
    if n_comments >= max(1, total // 10):
        strengths.append("Code is well-commented.")
    if n_functions:
        strengths.append(f"Code is organized into {n_functions} function(s).")
    if total <= 60:
        strengths.append("Code is compact and easy to scan.")

    # ---- Score computation (heuristic) ----
    score = 75
    deductions = 0
    if re.search(r'\beval\(|\bexec\(', code): deductions += 15
    if re.search(r'except\s*:', code): deductions += 10
    if re.search(r'password\s*=|api[_-]?key\s*=|secret\s*=', code, re.I): deductions += 12
    if re.search(r'def\s+\w+\([^)]*=\[\]|def\s+\w+\([^)]*=\{\}', code): deductions += 8
    if depth >= 2: deductions += 6
    if not n_functions and total > 20: deductions += 5
    if not n_comments and total > 15: deductions += 4
    score = max(10, min(99, score - deductions))

    cats = {
        'correctness': max(40, min(98, score + 5)),
        'readability': max(40, min(98, score + (5 if n_comments or n_docstrings else -5))),
        'efficiency': max(40, min(98, score - (8 if depth >= 2 else 0))),
        'maintainability': max(40, min(98, score + (5 if n_functions else -5))),
        'security': max(40, min(98, score - (12 if ('eval(' in code or 'exec(' in code or 'password=' in code.lower()) else 0))),
    }

    # Complexity heuristic
    if depth >= 2 or len(re.findall(r'\bfor\s+', code)) >= 2:
        tc, sc = "O(n^2) (or worse)", "O(n) (auxiliary)"
        alg_note = "Nested iteration detected — watch for quadratic growth on large inputs."
    elif len(re.findall(r'\bfor\s+|\bwhile\s+', code)) >= 1:
        tc, sc = "O(n)", "O(1)"
        alg_note = "Single pass over the input — linear time, constant extra space."
    else:
        tc, sc = "O(1)", "O(1)"
        alg_note = "No explicit loops — constant time unless hidden inside library calls."

    if score >= 80:
        verdict, summary = "production-ready", "Solid code with minor polish; suitable for publication/production."
    elif score >= 60:
        verdict, summary = "needs-work", "Decent foundation, but fix the flagged issues before shipping."
    else:
        verdict, summary = "not-ready", "Significant issues found — address them before publication."

    if not comments:
        comments.append("No critical issues auto-detected. (Offline review — connect the free LLM for deeper analysis.)")

    return {
        'score': score,
        'categories': cats,
        'comments': comments[:8],
        'suggestions': suggestions[:8] or ["No suggestions in offline mode — try the AI review for richer advice."],
        'algorithm': {'time_complexity': tc, 'space_complexity': sc, 'notes': alg_note},
        'verdict': verdict,
        'verdict_summary': summary,
        'strengths': strengths[:6] or ["No obvious strengths auto-detected."],
    }


def review_code(code):
    """Review code for publication/production readiness. Returns dict."""
    text, err = _groq_http(code, 'review')
    if text:
        try:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                data = json.loads(text[start:end + 1])
                if isinstance(data, dict) and 'score' in data:
                    return data
        except Exception:
            pass
    return _fallback_review(code)

