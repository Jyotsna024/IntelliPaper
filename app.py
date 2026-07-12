"""
IntelliPaper — Backend with Gemini File API
Gemini reads the PDF directly — no PyMuPDF extraction needed.
Works for ANY PDF: old, encrypted, RFC docs, research papers, textbooks.

pip install flask flask-cors google-generativeai spacy pymupdf pdfminer.six
python -m spacy download en_core_web_sm
python app.py → http://127.0.0.1:5000
"""

import os, re, time, uuid, logging
from pathlib import Path
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename

# ── GEMINI API KEY ─────────────────────────────────────────────────────────────
GEMINI_API_KEY = " "
# Free key: https://aistudio.google.com/app/apikey
# ──────────────────────────────────────────────────────────────────────────────

# ── Gemini ─────────────────────────────────────────────────────────────────────
try:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    gemini        = genai.GenerativeModel("gemini-1.5-flash")
    GEMINI_OK     = True
    print("✅ Gemini connected")
except Exception as e:
    GEMINI_OK = False
    print(f"❌ Gemini failed: {e}")

# ── PyMuPDF (optional fallback for text extraction) ────────────────────────────
try:
    import fitz
    FITZ_OK = True
except ImportError:
    FITZ_OK = False

# ── pdfminer (optional fallback) ───────────────────────────────────────────────
try:
    from pdfminer.high_level import extract_text as pdfminer_extract
    PDFMINER_OK = True
except ImportError:
    PDFMINER_OK = False

# ── spaCy (for contributions, architecture, exam Q&A) ─────────────────────────
try:
    import spacy
    SPACY_OK = True
except ImportError:
    SPACY_OK = False

# ── Setup ──────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("intellipaper")

app = Flask(__name__)
CORS(app)
UPLOAD = Path("uploads")
UPLOAD.mkdir(exist_ok=True)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

_nlp = None
def get_nlp():
    global _nlp
    if _nlp is None and SPACY_OK:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


# ══════════════════════════════════════════════════════════════════════════════
#  PDF TEXT EXTRACTION — tries multiple methods
# ══════════════════════════════════════════════════════════════════════════════

def extract_text_pymupdf(path):
    if not FITZ_OK:
        return ""
    try:
        doc   = fitz.open(path)
        pages = [page.get_text("text") for page in doc]
        doc.close()
        return "\n".join(pages)
    except:
        return ""

def extract_text_pdfminer(path):
    if not PDFMINER_OK:
        return ""
    try:
        return pdfminer_extract(path) or ""
    except:
        return ""

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'[^\x20-\x7E\n\t]', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove lines that are just page markers like "[Page 3] RFC 3261"
    lines = []
    for line in text.split('\n'):
        stripped = line.strip()
        # Skip page number lines and RFC header/footer lines
        if re.match(r'^\[Page\s*\d+\]', stripped):
            continue
        if re.match(r'^\s*\d{1,4}\s*$', stripped):
            continue
        if len(stripped) < 3:
            continue
        lines.append(line)
    return '\n'.join(lines).strip()

def extract_best_text(path):
    """Try all text extraction methods, return the best result."""
    results = {
        "pymupdf":  clean_text(extract_text_pymupdf(path)),
        "pdfminer": clean_text(extract_text_pdfminer(path)),
    }
    best = max(results, key=lambda k: len(results[k]))
    text = results[best]
    log.info(f"Text extraction — pymupdf:{len(results['pymupdf'])} pdfminer:{len(results['pdfminer'])} → using:{best}")
    return text


# ══════════════════════════════════════════════════════════════════════════════
#  GEMINI FILE API — send PDF directly to Gemini
#  This bypasses all text extraction problems completely.
#  Gemini reads the PDF itself like a human would.
# ══════════════════════════════════════════════════════════════════════════════

def gemini_read_pdf_and_summarize(pdf_path):
    """
    Upload PDF directly to Gemini File API.
    Gemini reads the actual PDF — works even if text extraction fails.
    Returns: { summary, eli5, contributions, architecture, exam_qa }
    """
    if not GEMINI_OK:
        return None

    try:
        log.info("Uploading PDF to Gemini File API...")
        uploaded_file = genai.upload_file(
            path=pdf_path,
            mime_type="application/pdf",
            display_name="document.pdf"
        )
        log.info(f"PDF uploaded: {uploaded_file.name}")

        # Ask Gemini to read the PDF and return ALL sections at once
        prompt = """Read this PDF document carefully and provide ALL of the following.
Use EXACTLY these section markers so I can parse your response:

===SUMMARY===
Write a clear 3-paragraph summary:
Paragraph 1: What is this document about? What problem or topic does it cover?
Paragraph 2: What are the main methods, rules, protocols, or approaches described?
Paragraph 3: What are the key conclusions or takeaways?
(Plain English. 3-5 sentences each paragraph. Be specific about the actual content.)

===SIMPLE===
Explain this to a smart high school student using a real-world analogy.
Write 3-4 short conversational paragraphs. Use simple words, no jargon.
Include: what problem it solves, why it matters, one surprising fact.

===CONTRIBUTIONS===
List the 5 most important points, contributions, or specifications from this document.
Write each as one clear sentence. Number them 1-5.

===ARCHITECTURE===
Describe the main process, protocol flow, or system architecture in 5 steps.
Format each step as: STEP_LABEL | one sentence description
(Use actual content from the document, not generic steps)

===EXAMQA===
Write 5 exam questions with answers based on this document.
Format: Q: question text | A: answer text
(One per line, use actual content)

Now read the PDF and respond with all sections:"""

        log.info("Asking Gemini to analyze the PDF...")
        response = gemini.generate_content([uploaded_file, prompt])
        raw      = response.text.strip()
        log.info(f"Gemini response: {len(raw)} chars")

        # Clean up the uploaded file
        try:
            genai.delete_file(uploaded_file.name)
        except:
            pass

        return parse_gemini_response(raw)

    except Exception as e:
        log.error(f"Gemini File API error: {e}")
        return None


def parse_gemini_response(raw):
    """Parse the structured Gemini response into separate sections."""

    def extract_section(text, marker):
        pattern = rf'==={marker}===(.*?)(?====\w+===|$)'
        match   = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""

    summary_raw = extract_section(raw, "SUMMARY")
    simple_raw  = extract_section(raw, "SIMPLE")
    contrib_raw = extract_section(raw, "CONTRIBUTIONS")
    arch_raw    = extract_section(raw, "ARCHITECTURE")
    qa_raw      = extract_section(raw, "EXAMQA")

    # Parse summary into paragraphs
    summary_paras = [p.strip() for p in re.split(r'\n\n+', summary_raw) if p.strip()]
    if len(summary_paras) < 2:
        summary_paras = [p.strip() for p in summary_raw.split('\n') if len(p.strip()) > 40]
    summary_paras = summary_paras[:3]

    # Parse simple explanation into paragraphs
    simple_paras = [p.strip() for p in re.split(r'\n\n+', simple_raw) if p.strip()]
    if len(simple_paras) < 2:
        simple_paras = [p.strip() for p in simple_raw.split('\n') if len(p.strip()) > 30]
    simple_paras = simple_paras[:4]

    # Parse contributions — numbered list
    contributions = []
    for line in contrib_raw.split('\n'):
        line = re.sub(r'^\d+[\.\)]\s*', '', line.strip())
        if len(line) > 20:
            contributions.append(line)
    contributions = contributions[:6]

    # Parse architecture — "LABEL | detail" format
    architecture = []
    for line in arch_raw.split('\n'):
        line = line.strip()
        if '|' in line:
            parts = line.split('|', 1)
            label  = re.sub(r'^(step\s*\d+[\.\):]*\s*)', '', parts[0], flags=re.IGNORECASE).strip()
            detail = parts[1].strip() if len(parts) > 1 else ""
            if label:
                architecture.append({"label": label[:60], "detail": detail})
        elif len(line) > 20 and not line.startswith('#'):
            line_clean = re.sub(r'^(step\s*\d+[\.\):]*\s*)', '', line, flags=re.IGNORECASE).strip()
            if line_clean:
                architecture.append({"label": line_clean[:60], "detail": ""})
    if len(architecture) < 3:
        architecture = [
            {"label": "Input",        "detail": "Document or data is provided"},
            {"label": "Processing",   "detail": "Main logic is applied"},
            {"label": "Output",       "detail": "Results are generated"},
        ]
    architecture = architecture[:7]

    # Parse exam Q&A — "Q: ... | A: ..." format
    exam_qa = []
    for line in qa_raw.split('\n'):
        line = line.strip()
        if line.lower().startswith('q:') and '|' in line:
            parts = line.split('|', 1)
            q = re.sub(r'^q:\s*', '', parts[0], flags=re.IGNORECASE).strip()
            a = re.sub(r'^a:\s*', '', parts[1], flags=re.IGNORECASE).strip()
            if q and a:
                exam_qa.append({"q": q, "a": a})
    # fallback if pipe format not used
    if len(exam_qa) < 3:
        exam_qa = []
        lines   = [l.strip() for l in qa_raw.split('\n') if l.strip()]
        i = 0
        while i < len(lines) - 1:
            q_line = lines[i]
            a_line = lines[i+1] if i+1 < len(lines) else ""
            if re.match(r'^[Qq][\d\.\):]', q_line):
                q = re.sub(r'^[Qq][\d\.\):]*\s*', '', q_line).strip()
                a = re.sub(r'^[Aa][\d\.\):]*\s*', '', a_line).strip()
                if q:
                    exam_qa.append({"q": q, "a": a or "See document for details."})
                i += 2
            else:
                i += 1
    exam_qa = exam_qa[:5]

    return {
        "summary":       summary_paras,
        "eli5":          simple_paras,
        "contributions": contributions,
        "architecture":  architecture,
        "exam_qa":       exam_qa,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  TEXT-BASED ANALYSIS (used when text extraction works, or as fallback)
# ══════════════════════════════════════════════════════════════════════════════

def gemini_call(prompt):
    if not GEMINI_OK:
        return None
    try:
        return gemini.generate_content(prompt).text.strip()
    except Exception as e:
        log.error(f"Gemini error: {e}")
        return None

def make_summary_from_text(text):
    snippet = text[:6000]
    prompt  = f"""Read this document and write a clear summary in EXACTLY 3 paragraphs.
Paragraph 1: What is this document about?
Paragraph 2: What are the main methods, rules, or approaches?
Paragraph 3: Key conclusions or takeaways.
Plain English, 3-5 sentences each, no bullet points.

Document:
{snippet}

3 paragraphs:"""
    result = gemini_call(prompt)
    if not result:
        return make_summary_fallback(text)
    paras = [p.strip() for p in re.split(r'\n\n+', result) if p.strip()]
    return paras[:3] if paras else make_summary_fallback(text)

def make_eli5_from_text(text):
    snippet = text[:4000]
    prompt  = f"""Explain this document to a smart high school student.
Use a real-world analogy, simple words, no jargon.
3-4 short conversational paragraphs.

Document:
{snippet}

Explain:"""
    result = gemini_call(prompt)
    if not result:
        return make_eli5_fallback(text)
    paras = [p.strip() for p in re.split(r'\n\n+', result) if p.strip()]
    return paras[:4] if paras else make_eli5_fallback(text)

def ask_gemini_text(question, text):
    snippet = text[:6000]
    prompt  = f"""Answer based ONLY on this document.
Question: {question}
2-4 sentence answer. If not in document say "Not mentioned, but based on context: ..."

Document:
{snippet}

Answer:"""
    result = gemini_call(prompt)
    return result if result else ask_fallback(question, text)


# ══════════════════════════════════════════════════════════════════════════════
#  spaCy FEATURES
# ══════════════════════════════════════════════════════════════════════════════

def get_sentences(text):
    nlp = get_nlp()
    if nlp:
        doc = nlp(text[:100000])
        return [s.text.strip() for s in doc.sents if len(s.text.strip()) > 20]
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 20]

def get_word_scores(text):
    nlp  = get_nlp()
    freq = {}
    if nlp:
        doc = nlp(text[:80000])
        for tok in doc:
            if not tok.is_stop and not tok.is_punct and len(tok.text) > 2:
                w        = tok.lemma_.lower()
                freq[w]  = freq.get(w, 0) + 1
    else:
        stop = {"the","a","an","is","it","in","on","of","to","and","or","but","for",
                "with","this","that","are","was","were","be","been","has","have"}
        for w in re.findall(r"[a-z]{3,}", text.lower()):
            if w not in stop:
                freq[w] = freq.get(w, 0) + 1
    mx = max(freq.values(), default=1)
    return {w: c/mx for w, c in freq.items()}

def score_sentences(sents, ws):
    scored = []
    for s in sents:
        words = re.findall(r"[a-z]{3,}", s.lower())
        sc    = sum(ws.get(w, 0) for w in words) / max(len(words), 1)
        scored.append((sc, s))
    return sorted(scored, reverse=True)

def make_summary_fallback(text):
    sents   = get_sentences(text)
    ws      = get_word_scores(text)
    top     = [s for _, s in score_sentences(sents, ws)[:12]]
    ordered = [s for s in sents if s in top][:12]
    n       = max(len(ordered)//3, 1)
    return [p for p in [" ".join(ordered[:n]), " ".join(ordered[n:2*n]), " ".join(ordered[2*n:])] if p.strip()]

def make_eli5_fallback(text):
    sents  = get_sentences(text)
    ws     = get_word_scores(text)
    simple = [(sc, s) for sc, s in score_sentences(sents, ws) if 40 < len(s) < 180][:3]
    topic  = ", ".join(list(ws.keys())[:3])
    return [f"This document is about: {topic}.", simple[0][1] if simple else "", "It describes an approach that improves on existing methods."]

def ask_fallback(question, text):
    sents   = get_sentences(text)
    ws      = get_word_scores(text)
    q_words = set(re.findall(r"[a-z]{3,}", question.lower()))
    best, best_score = "", 0
    for sc, sent in score_sentences(sents, ws):
        overlap  = len(q_words & set(re.findall(r"[a-z]{3,}", sent.lower())))
        combined = sc + overlap * 0.4
        if combined > best_score and 30 < len(sent) < 400:
            best_score = combined
            best       = sent
    return best or "No relevant answer found."

def make_contributions_from_text(text):
    sents   = get_sentences(text)
    ws      = get_word_scores(text)
    signals = re.compile(
        r"we propose|we present|novel|new approach|outperform|our method|"
        r"contribut|demonstrate|defines|specifies|establishes|introduces|"
        r"key|important|significant|must|shall|required",
        re.IGNORECASE
    )
    found  = [s.strip() for s in sents if signals.search(s) and 30 < len(s) < 300]
    unique = []
    for s in found:
        if not any(s[:40] in u for u in unique):
            unique.append(s)
    if len(unique) < 4:
        for _, s in score_sentences(sents, ws):
            if s not in unique:
                unique.append(s)
            if len(unique) >= 5:
                break
    return unique[:6]

def make_architecture_from_text(text):
    sents        = get_sentences(text)
    ws           = get_word_scores(text)
    method_words = re.compile(
        r"input|output|layer|module|encoder|decoder|pipeline|architecture|"
        r"network|model|block|process|step|stage|protocol|request|response|"
        r"header|message|packet|field|session|register|invite|transaction",
        re.IGNORECASE
    )
    method_sents = [s for s in sents if method_words.search(s) and 20 < len(s) < 250]
    top          = [s for _, s in score_sentences(method_sents, ws)[:6]]
    nodes        = []
    nlp          = get_nlp()
    for sent in top:
        if nlp:
            doc    = nlp(sent[:200])
            chunks = [c.text.strip() for c in doc.noun_chunks if len(c.text.strip()) > 3]
            label  = chunks[0][:55] if chunks else sent[:55]
        else:
            label = sent[:55]
        nodes.append({"label": label, "detail": sent.strip()})
    if len(nodes) < 3:
        nodes = [
            {"label": "Input",        "detail": "Document or data is provided"},
            {"label": "Processing",   "detail": "Main logic is applied"},
            {"label": "Output",       "detail": "Results are generated"},
        ]
    return nodes[:7]

def make_exam_qa_from_text(text):
    sents     = get_sentences(text)
    ws        = get_word_scores(text)
    questions = [
        ("What is the main topic or purpose of this document?",
         r"purpose|problem|goal|objective|aim|about|describ|defin"),
        ("What is the main method, protocol, or approach described?",
         r"propos|method|approach|protocol|mechanism|framework|system"),
        ("What are the key components or elements involved?",
         r"component|element|field|section|part|module|type|format"),
        ("What are the key rules, results, or specifications?",
         r"result|rule|must|shall|should|require|specif|standard"),
        ("What are the limitations or future considerations?",
         r"limit|constrain|future|further|extend|improve|note|exception"),
    ]
    qa_list = []
    for question, keywords in questions:
        pattern = re.compile(keywords, re.IGNORECASE)
        matches = [(sc, s) for sc, s in score_sentences(sents, ws)
                   if pattern.search(s) and 30 < len(s) < 350]
        answer  = matches[0][1] if matches else "Not explicitly mentioned in this document."
        qa_list.append({"q": question, "a": answer})
    return qa_list

def get_stats(text):
    words     = text.split()
    sentences = [s for s in re.split(r'[.!?]+', text) if s.strip()]
    syllables = sum(max(1, len(re.findall(r'[aeiou]+', w.lower()))) for w in words)
    avg_sent  = len(words) / max(len(sentences), 1)
    avg_syl   = syllables  / max(len(words), 1)
    score     = max(0, min(100, 206.835 - 1.015*avg_sent - 84.6*avg_syl))
    if score >= 70:   level = "Easy"
    elif score >= 50: level = "Moderate"
    elif score >= 30: level = "Difficult"
    else:             level = "Very Technical"
    return {"word_count": len(words), "sentence_count": len(sentences),
            "level": level, "read_time_min": max(1, round(len(words)/200))}


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyse", methods=["POST"])
def analyse():
    start       = time.time()
    text        = ""
    pdf_path    = None
    used_file_api = False

    # ── Get input ──
    if "file" in request.files:
        f = request.files["file"]
        if f and f.filename:
            fn       = secure_filename(f.filename)
            pdf_path = str(UPLOAD / f"{uuid.uuid4()}_{fn}")
            f.save(pdf_path)
            ext      = fn.rsplit(".", 1)[-1].lower()

            if ext == "pdf":
                # Step 1: Try to extract text normally
                text = clean_text(extract_best_text(pdf_path))
                log.info(f"Text extracted: {len(text)} chars")

                # Step 2: If text extraction got good content, use it
                # Step 3: If text is garbage or too short, use Gemini File API
                is_garbage = (
                    len(text) < 200 or
                    len(re.findall(r'[a-zA-Z]{3,}', text)) < 50 or
                    text.count('[Page') > 5  # page markers = bad extraction
                )

                if is_garbage and GEMINI_OK:
                    log.info("Text extraction poor — using Gemini File API to read PDF directly")
                    gemini_result = gemini_read_pdf_and_summarize(pdf_path)
                    if gemini_result:
                        used_file_api = True
                        stats         = get_stats(text) if len(text) > 100 else {
                            "word_count": 0, "sentence_count": 0,
                            "level": "Unknown", "read_time_min": 0
                        }
                        Path(pdf_path).unlink(missing_ok=True)
                        gemini_result["stats"]      = stats
                        gemini_result["elapsed_ms"] = round((time.time()-start)*1000)
                        return jsonify(gemini_result)
            else:
                text = open(pdf_path, encoding="utf-8", errors="ignore").read()

            Path(pdf_path).unlink(missing_ok=True)

    else:
        data = request.get_json() or {}
        text = data.get("text", "").strip()

    text = clean_text(text)

    if len(text) < 100:
        return jsonify({"error": "Could not extract text. Try pasting the text directly."}), 400

    log.info(f"Analysing {len(text)} chars via text pipeline...")

    result = {
        "stats":         get_stats(text),
        "summary":       make_summary_from_text(text),
        "eli5":          make_eli5_from_text(text),
        "contributions": make_contributions_from_text(text),
        "architecture":  make_architecture_from_text(text),
        "exam_qa":       make_exam_qa_from_text(text),
        "elapsed_ms":    round((time.time()-start)*1000),
    }
    return jsonify(result)


@app.route("/api/ask", methods=["POST"])
def ask():
    data     = request.get_json() or {}
    text     = data.get("text",     "").strip()
    question = data.get("question", "").strip()
    if not text or not question:
        return jsonify({"error": "Send both text and question."}), 400
    return jsonify({"question": question, "answer": ask_gemini_text(question, text)})


if __name__ == "__main__":
    print("\n" + "="*50)
    print("  IntelliPaper — Robust PDF Reader")
    print("  Open → http://127.0.0.1:5000")
    print(f"  Gemini:   {'✅' if GEMINI_OK    else '❌ Add API key above'}")
    print(f"  PyMuPDF:  {'✅' if FITZ_OK      else '❌ pip install pymupdf'}")
    print(f"  pdfminer: {'✅' if PDFMINER_OK  else '❌ pip install pdfminer.six'}")
    print(f"  spaCy:    {'✅' if SPACY_OK     else '❌ pip install spacy'}")
    print("="*50 + "\n")
    app.run(debug=False, host="127.0.0.1", port=5000)
