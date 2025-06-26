# ── lambda_function.py ─────────────────────────────────────────────────────
import json, os, re, base64, logging, mimetypes
import boto3
from botocore.exceptions import ClientError
import requests

# ── AWS & env config ──────────────────────────────────────────────────────
REGION        = os.environ.get("AWS_REGION", "us-east-1")
SENDER_EMAIL  = os.environ.get("SENDER_EMAIL")          # verified in SES
RAPID_KEY     = os.environ.get("RAPID_API_KEY")         # RapidAPI key
RAPID_HOST    = "jsearch.p.rapidapi.com"
# NEW ➜ label that will appear in the subject line so the recipient sees the
# provider clearly (defaults to "AWS SNS", change via ENV if desired)
PROVIDER_LABEL = os.environ.get("EMAIL_PROVIDER_LABEL", "AWS SNS")

textract = boto3.client("textract", region_name=REGION)
ses      = boto3.client("ses",      region_name=REGION)

# ── logging ───────────────────────────────────────────────────────────────
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ── resume‑scoring helpers ────────────────────────────────────────────────
SECTION_HEADS = {
    "education": re.compile(r"\beducation\b", re.I),
    "experience": re.compile(r"\bexperience\b|\bemployment\b|\bwork history\b", re.I),
    "projects": re.compile(r"\bproject[s]?\b|\bresearch\b", re.I),
    "certifications": re.compile(r"\bcertification[s]?\b|\blicense[s]?\b", re.I),
    "skills": re.compile(r"\bskills?\b", re.I)
}

ACTION_VERBS = [
    "designed", "developed", "implemented", "led", "created", "optimized",
    "automated", "deployed", "analysed", "improved", "built", "managed"
]

DEGREE_RX = re.compile(r"\b(bachelor|master|phd|b\.?tech|m\.?tech)\b", re.I)

SKILL_DICT = {                 # pts per skill
    "python": 4, "java": 4, "c++": 4, "javascript": 4,
    "aws": 5, "docker": 4, "kubernetes": 5, "git": 2,
    "sql": 2, "nosql": 2, "rest": 2, "react": 3, "node": 3,
    "machine learning": 5, "data science": 5, "cloud": 4
}

def score_resume(text: str) -> dict:
    lo = text.lower()
    words = len(lo.split())
    score, tips = 0, []
    found_skills = set()

    # 1️⃣ Section check
    for sec, rx in SECTION_HEADS.items():
        if rx.search(lo):
            score += 3
        else:
            tips.append(f"Add a clear **{sec.title()}** section.")

    # 2️⃣ Education
    if DEGREE_RX.search(lo):
        score += 8
    else:
        tips.append("State your degree (e.g., *B.Tech in CSE, 2024*).")

    # 3️⃣ Experience span (years)
    years = sorted(set(int(y) for y in re.findall(r"(20\d{2}|19\d{2})", text)))
    if len(years) >= 2:
        span = max(years) - min(years)
        score += min(span * 2, 14)
        if span < 2:
            tips.append("Show multi‑year experience or internships to strengthen credibility.")
    else:
        tips.append("Add start/end years for each role to highlight tenure.")

    # 4️⃣ Bullets & numbers
    bullets = [ln for ln in text.splitlines() if re.match(r"^\s*[-•*]", ln)]
    if len(bullets) >= 6:
        score += 6
    else:
        tips.append("Use ≥ 6 bullet points for readability and ATS parsing.")

    if len(re.findall(r"\b\d+(\.\d+)?[%$KkMm+]?\b", lo)) >= 4:
        score += 6
    else:
        tips.append("Quantify achievements (e.g., *reduced latency by 40%*).")

    # 5️⃣ Action verbs
    verbs = sum(1 for v in ACTION_VERBS if v in lo)
    score += min(verbs, 6)
    if verbs < 3:
        tips.append("Start bullets with strong verbs (Implemented, Optimized, Led…).")

    # 6️⃣ Skills
    for sk, pts in SKILL_DICT.items():
        if re.search(rf"\b{re.escape(sk)}\b", lo):
            score += pts
            found_skills.add(sk)
    if len(found_skills) < 5:
        tips.append("Add modern skills like Docker, AWS Lambda, React, etc.")

    # 7️⃣ Length penalty/bonus
    if words < 250:
        score -= 8
        tips.append("Aim for 300‑500 words (≈ one full page).")
    elif words > 800:
        score -= 5
        tips.append("Condense to ≤ 2 pages for recruiter‑friendly length.")

    return {
        "score": max(0, min(int(score), 100)),
        "tips": sorted(set(tips))[:8],
        "skills": sorted(found_skills)
    }

# ── RapidAPI JSearch helper ────────────────────────────────────────────────

def fetch_jobs(skills, location="India"):
    if not RAPID_KEY:
        logger.warning("RAPID_API_KEY not set – skipping job search")
        return []

    hdrs = {"X-RapidAPI-Key": RAPID_KEY, "X-RapidAPI-Host": RAPID_HOST}
    jobs = []
    for sk in skills[:3]:
        url = f"https://{RAPID_HOST}/search?query={sk}%20internship%20{location}&page=1&num_pages=1"
        try:
            data = requests.get(url, headers=hdrs, timeout=6).json()
            for j in data.get("data", [])[:2]:
                jobs.append({
                    "title":   j.get("job_title") or "Untitled",
                    "company": j.get("employer_name") or "Unknown",
                    "place":   ", ".join(filter(None, [j.get("job_city"), j.get("job_country")])),
                    "link":    j.get("job_apply_link") or "#"
                })
        except Exception as e:
            logger.warning("JSearch call failed: %s", e)
    return jobs

# ── SES helper ─────────────────────────────────────────────────────────────

def send_email(to_addr, subject, html):
    try:
        resp = ses.send_email(
            Source=SENDER_EMAIL,
            Destination={"ToAddresses": [to_addr]},
            Message={"Subject": {"Data": subject},
                     "Body":    {"Html": {"Data": html}}}
        )
        logger.info("SES accepted: %s", json.dumps(resp))
    except ClientError as e:
        logger.error("SES send_email failed: %s", e.response["Error"]["Message"])

# ── safe extraction ────────────────────────────────────────────────────────

def extract_text(blob: bytes, mime: str | None) -> str:
    logger.info("MIME: %s", mime)
    if mime in ("application/pdf", "image/jpeg", "image/png", "image/tiff"):
        try:
            out = textract.detect_document_text(Document={"Bytes": blob})
            return " ".join(b["Text"] for b in out["Blocks"] if b["BlockType"] == "WORD")
        except textract.exceptions.UnsupportedDocumentException:
            logger.warning("Textract unsupported; decoding bytes.")
        except Exception:
            logger.exception("Textract error; decoding bytes.")
    return blob.decode("utf-8", errors="ignore")


def get_bytes_and_mime(evt):
    if "resume_content_base64" in evt:
        return base64.b64decode(evt["resume_content_base64"]), evt.get("resume_file_type")
    if evt.get("headers", {}).get("content-type", "").startswith("application/json"):
        body = json.loads(evt["body"])
        return base64.b64decode(body["resume_content_base64"]), body.get("resume_file_type")
    b64 = evt.get("body", "")
    blob = base64.b64decode(b64) if evt.get("isBase64Encoded") else b64.encode()
    return blob, evt.get("headers", {}).get("content-type")

# ── Lambda handler ────────────────────────────────────────────────────────

def lambda_handler(event, context):
    logger.info("Event (truncated): %s", json.dumps(event)[:400])
    try:
        blob, mime = get_bytes_and_mime(event)
        mime = mime or mimetypes.guess_type("resume.pdf")[0]

        text   = extract_text(blob, mime)
        result = score_resume(text)
        jobs   = fetch_jobs(result["skills"])

        to_addr = event.get("email") or event.get("recipient_email") or SENDER_EMAIL

        job_html = (
            "".join(f"<li><b>{j['title']}</b> – {j['company']} ({j['place']}) "
                    f"<a href='{j['link']}'>Apply</a></li>" for j in jobs)
            or "<li>No matching jobs right now – try adding more in-demand skills.</li>"
        )

        html = f"""
        <h2>Résumé Score: {result['score']}/100</h2>
        <h3>Personalised Suggestions</h3>
        <ul>{"".join(f"<li>{t}</li>" for t in result['tips'])}</ul>
        <h3>Skills Detected</h3>
        <p>{", ".join(result['skills']) or "—"}</p>
        <h3>Real-Time Jobs & Internships</h3>
        <ul>{job_html}</ul>"""

        # NEW ➜ Professional subject line showing provider
        subject = f"Résumé Analysis – {result['score']}/100 | Sent via {PROVIDER_LABEL}"
        send_email(to_addr, subject, html)

        # 🔍 EXTRA LOGGING FOR CLOUDWATCH
        logger.info("Score: %d", result["score"])
        logger.info("Tips: %s", result["tips"])
        logger.info("Skills: %s", result["skills"])
        logger.info("Jobs found: %d", len(jobs))
        logger.info("Job details: %s", jobs)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({**result, "jobs_found": len(jobs)})
        }

    except Exception as e:
        logger.exception("Unhandled error")
        return {"statusCode": 500,
                "body": json.dumps({"error": str(e)})}

