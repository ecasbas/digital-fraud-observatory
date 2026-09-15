#!/usr/bin/env python3
"""Curate recent Desenmascara fraud reports into observatory cases.

Runs every 16 hours from the backend's Celery Beat (task
``update_digital_fraud_observatory``) and by hand. It is conservative on
purpose, because a case here republishes an accusation in a public repository:

* It reads the verdict a visitor is served — the same projection the MCP tools
  use, where a human correction outranks the pipeline — never the raw column.
* It skips well-known domains, domains with a verdict dispute on file, and
  verdicts that rest on a regulator notice (a licence question, not fraud).
* It showcases our own work: only verdicts our AI reasoned over the corpus
  (then human review, then heuristics). Third-party listings such as
  PhishDestroy are not curated (owner's rule, 2026-09-15).
* It follows retractions: a case it added is withdrawn once the published
  verdict stops being FRAUDULENT or the operator disputes it. Hand-written
  cases are never touched.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "content" / "cases.json"
STATE_PATH = ROOT / ".curator-state.json"
CAPTURES = ROOT / "assets" / "captures"
BACKEND_ROOT = Path(os.getenv("DESENMASCARA_BACKEND_ROOT", "/home/deploy/desenmascarame-backend"))
SCREEN_DIR = BACKEND_ROOT / "media" / "screens"

#: Tranco reputation rank at or above which a domain is too well known to be
#: republished here, whatever the verdict (same bar as `audit_major_domains`).
PROTECTED_RANK = 100_000

#: What decided the verdict -> how the case attributes it. A basis missing from
#: this map is skipped: regulator notices say "not authorised", which is a
#: licence question; reputation/trust-seal/prior paths never yield FRAUDULENT;
#: an unknown basis cannot be attributed honestly.
ATTRIBUTION = {
    "phishdestroy_destroylist": "attributed PhishDestroy DestroyList match",
    "google_safe_browsing": "attributed Google Safe Browsing match",
    "cloudflare_phishing": "attributed Cloudflare phishing warning",
    "manual_review": "human review",
    "ai_reasoning": "AI-assisted analysis",
    "heuristics": "heuristic analysis",
}

#: Verdict bases new cases may come from, in order of preference.
CURATED_BASES = ("ai_reasoning", "manual_review", "heuristics")

CATEGORY_RULES = [
    ("Investment", "High-return promise", ["invest", "trading", "broker", "forex", "cfd", "profit", "capital", "wealth"], "Retail investors", "Is this firm authorised to take your money?", "Before investing, verify the firm in the relevant regulator register and treat guaranteed or effortless returns as a warning sign.", "Big returns. No verifiable firm behind them."),
    ("Crypto", "Crypto wallet or exchange lure", ["crypto", "bitcoin", "btc", "wallet", "token", "airdrop", "defi", "nft", "exchange"], "Crypto users and retail investors", "Who controls the wallet you are asked to connect?", "Do not connect a wallet, send crypto or trust a token claim until you verify it through independent official channels.", "A crypto platform. A source says fraudulent."),
    ("Banking", "Financial-service facade", ["bank", "login", "account", "card", "payment", "transfer", "transact"], "Bank customers and payment users", "Is this a bank any regulator has heard of?", "Use your bank's official app, domain or support channel before entering credentials or payment details, and check any new bank in the regulator's register.", "A bank website. No bank you can verify."),
    ("Shopping", "Deceptive storefront", ["shop", "store", "discount", "sale", "cart", "checkout", "shipping"], "Online shoppers", "Who operates this shop?", "Check who operates a shop before trusting its sale. A discount alone proves neither fraud nor legitimacy.", "A bargain storefront. A source says fraudulent."),
    ("Jobs", "Advance-fee request", ["job", "task", "salary", "commission", "withdraw", "earn"], "Job seekers and online task workers", "A displayed balance is not proof of withdrawable earnings", "A number on a dashboard does not prove that withdrawable earnings exist. Do not send money to release supposed wages.", "Easy earnings. Pay first to withdraw."),
    ("Transport", "Manufactured credibility", ["logistics", "cargo", "parcel", "shipment", "delivery", "freight"], "Customers, shippers and business counterparties", "Does this carrier exist outside its website?", "A transport website does not establish that a carrier exists. Verify the company identity before entrusting it with money or goods.", "A carrier website. An identity still to verify."),
]
GENERIC_CATEGORY = ("Website fraud", "Manufactured credibility", [], "People asked to trust a new website", "Who is behind this website?", "Treat a polished website as a claim, not proof. Verify the operator, source and payment path through independent records.", "A polished website. A source says fraudulent.")
ALLOW_GENERIC = (os.getenv("OBSERVATORY_ALLOW_GENERIC") or "").lower() in {"1", "true", "yes", "on"}


# --------------------------------------------------------------------------
# Pure helpers (no Django), covered by scripts/test_curate_from_desenmascara.py
# --------------------------------------------------------------------------

def host_of(domain: str) -> str:
    return re.sub(r"^https?://", "", (domain or "").strip().lower()).strip("/")


def slug_of(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", re.sub(r"^www\.", "", value.lower()))
    return value.strip("-")[:70] or "fraudulent-website"


def rejection_reason(projection: dict, rank: int | None, disputed: bool, check_basis: bool = True) -> str | None:
    """Why a report may not become (or stay) a case; None when it may.

    ``check_basis=False`` for cases already published: which engine decided is
    a curation preference, not a retraction.
    """
    if projection.get("status") != "complete" or projection.get("verdict") != "FRAUDULENT":
        return f"published verdict is {projection.get('verdict') or projection.get('status')}"
    if rank is not None and rank <= PROTECTED_RANK:
        return f"well-known domain (Tranco #{rank})"
    if disputed:
        return "verdict disputed by the operator"
    if check_basis and projection.get("assessed_by") not in CURATED_BASES:
        return f"basis not attributable here ({projection.get('assessed_by')})"
    return None


def observations_from(projection: dict, domain: str) -> list[str]:
    """Negative findings from the report, minus 'impersonation' of the site's own name."""
    sld = re.sub(r"[^a-z0-9]", "", host_of(domain).split(".")[-2] if "." in domain else domain)
    out = []
    for item in projection.get("evidence") or []:
        label = (item.get("label") or "").strip()
        if not label or item.get("positive"):
            continue
        brand = re.search(r"Possible (.+?) impersonation", label, re.I)
        if brand and re.sub(r"[^a-z0-9]", "", brand.group(1).lower()) in sld:
            continue  # a site cannot impersonate its own name
        out.append(f"The source report records: {label[0].lower() + label[1:]}.")
    return out[:3]


def choose_category(projection: dict, domain: str) -> tuple:
    fraud_type = re.search(r"Fraud type:\s*([^.]+)", projection.get("explanation") or "")
    labels = " ".join(i.get("label") or "" for i in projection.get("evidence") or [])
    for haystack in (fraud_type.group(1) if fraud_type else "", f"{domain} {labels}"):
        for rule in CATEGORY_RULES:
            if any(keyword in haystack.lower() for keyword in rule[2]):
                return rule
    return GENERIC_CATEGORY


def build_case(projection: dict, case_id: str, slug: str, image: str, image_source: str) -> dict:
    domain = projection["domain"]
    category, technique, _kw, audience, counterclaim, lesson, title = choose_category(projection, domain)
    basis = ATTRIBUTION[projection["assessed_by"]]
    observations = observations_from(projection, domain) or ["The source report records the domain as fraudulent."]
    third_party = basis.startswith("attributed")
    score = int(round(float(projection["risk_score"])))
    first_sentence = ""
    if projection.get("explanation_language") == "en" and projection.get("explanation"):
        first_sentence = re.split(r"(?<=[.!?])\s", projection["explanation"].strip(), maxsplit=1)[0]
    source_summary = (
        f"Desenmascara publishes a Fraudulent assessment of {score}/100 for {domain}, based on {basis}."
        + (f" Its analysis says: “{first_sentence}”" if first_sentence and not third_party else "")
        + (" The verdict is the third-party listing's, reported with attribution, not an independent finding." if third_party else "")
        + " Follow the report for the full rationale, evidence and any later correction."
    )
    return {
        "id": case_id, "slug": slug, "title": title, "short_title": f"The {category.lower()} website",
        "category": category, "technique": technique, "kind": "capture", "subject": domain,
        "summary": f"{domain} was captured while Desenmascara assessed it as fraudulent ({basis}).",
        "lesson": lesson, "image": image, "image_source": image_source,
        "image_alt": f"Archived capture of {domain}, a website assessed as fraudulent.",
        "claim": "An operating online service", "counterclaim": counterclaim,
        "observations": observations, "source_summary": source_summary,
        "limits": "This case was added automatically from a dated, attributed source assessment; it is not an independent investigation by this project. The capture does not prove customer losses, operator identity or AI generation. Signals such as a young domain or shared hosting do not prove fraud on their own. If the source withdraws the verdict, this case is withdrawn too.",
        "analysis_date": (projection.get("assessed_at") or "")[:10] or datetime.now(timezone.utc).date().isoformat(),
        "checked_at": datetime.now(timezone.utc).date().isoformat(),
        "assessment": f"Fraudulent · {score}/100",
        "assessment_source": f"desenmascara.me · {basis}",
        "sources": [{"name": "desenmascara.me", "short": "Desenmascara", "role": f"Public report and archived capture; verdict basis: {basis}", "url": projection["report_url"]}],
        "audience": audience,
    }


def next_id(cases: list[dict], high_water: int) -> str:
    ids = [int(m.group(1)) for c in cases if (m := re.fullmatch(r"SA-(\d{3})", str(c.get("id", ""))))]
    return f"SA-{max(ids + [high_water]) + 1:03d}"


# --------------------------------------------------------------------------
# Django-backed lookups
# --------------------------------------------------------------------------

def _setup_django() -> None:
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
    import django
    django.setup()


def _row_for(domain: str):
    from django.db.models import Q
    from core.models import AnalyzedDomain
    d = host_of(domain)
    q = Q(domain__iexact=d) | Q(domain__iexact=f"https://{d}") | Q(domain__iexact=f"http://{d}")
    return AnalyzedDomain.objects.filter(q).order_by("-date").first()


def _assess(row, since_dispute: datetime | None = None, check_basis: bool = True) -> tuple[dict, str | None]:
    from core.models import VerdictDispute
    from core.report_projection import build_report_projection
    from core.top_sites import get_reputation_rank
    projection = build_report_projection(row, lang="en")
    domain = projection.get("domain") or host_of(row.domain)
    disputes = VerdictDispute.objects.filter(domain__iexact=domain)
    if since_dispute:
        disputes = disputes.filter(created_at__gte=since_dispute)
    return projection, rejection_reason(projection, get_reputation_rank(domain), disputes.exists(), check_basis)


def _candidates(since: datetime, limit: int):
    from django.db.models import Q
    from core.models import AnalyzedDomain
    rows = (AnalyzedDomain.objects
            .filter(Q(veredict="FRAUDULENT") | Q(manual_verdict="FRAUDULENT"), date__gte=since,
                    public_id__isnull=False, assessed_by__in=CURATED_BASES)
            .exclude(screenshot_url__isnull=True).exclude(screenshot_url="")
            .order_by("-ai_score", "-date")[: limit * 20])
    return sorted(rows, key=lambda row: CURATED_BASES.index(row.assessed_by))


def _capture_source(row) -> Path | None:
    name = Path(urlparse(row.screenshot_url or "").path).name
    path = SCREEN_DIR / name if name else None
    return path if path and path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} else None


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _auto_git(message: str) -> None:
    if (os.getenv("OBSERVATORY_AUTO_GIT") or "").lower() not in {"1", "true", "yes", "on"}:
        return
    # dist/ is gitignored: the Pages workflow builds it.
    subprocess.run(["git", "add", "-A", "content/cases.json", "assets/captures"], cwd=ROOT, check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode != 0:
        subprocess.run(["git", "commit", "-m", message], cwd=ROOT, check=True)
    if (os.getenv("OBSERVATORY_AUTO_PUSH") or "").lower() in {"1", "true", "yes", "on"}:
        # Push whenever we are ahead, so a failed push is retried on the next run.
        subprocess.run(["git", "pull", "--rebase", "--autostash", "origin", "main"], cwd=ROOT, check=True)
        subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=int(os.getenv("OBSERVATORY_LOOKBACK_HOURS", "96")))
    parser.add_argument("--max-new", type=int, default=int(os.getenv("OBSERVATORY_MAX_NEW", "2")))
    parser.add_argument("--min-score", type=float, default=float(os.getenv("OBSERVATORY_MIN_SCORE", "75")))
    parser.add_argument("--build", action="store_true", help="Rebuild and check the static site after changes.")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change; write nothing.")
    args = parser.parse_args()
    _setup_django()

    state = _load(STATE_PATH, {})
    cases = _load(CASES_PATH, [])
    curated = set(state.get("curated_ids", []))
    now = datetime.now(timezone.utc)

    # 1. Follow retractions for the cases this curator added.
    withdrawals = []
    for case in [c for c in cases if c["id"] in curated]:
        row = _row_for(case["subject"])
        added = datetime.fromisoformat(case["checked_at"]).replace(tzinfo=timezone.utc)
        reason = "report no longer found" if row is None else _assess(row, since_dispute=added, check_basis=False)[1]
        if reason:
            withdrawals.append({"id": case["id"], "subject": case["subject"], "reason": reason, "at": now.isoformat()})

    # 2. Add new cases, one per fraud category per run.
    # Always the full window: already-published domains are deduplicated below,
    # and a candidate skipped for a category clash gets another chance next run.
    since = now - timedelta(hours=args.hours)
    withdrawn_ids = {w["id"] for w in withdrawals}
    kept = [c for c in cases if c["id"] not in withdrawn_ids]
    known = {c["subject"].lower() for c in cases} | {w["subject"] for w in state.get("withdrawn", [])}
    used_categories: set[str] = set()
    additions, skipped = [], []
    high_water = int(state.get("id_high_water", 0))
    for row in _candidates(since, args.max_new):
        if len(additions) >= args.max_new:
            break
        domain = host_of(row.domain)
        if domain in known:
            continue
        projection, reason = _assess(row)
        category = choose_category(projection, domain)[0]
        if not reason and (projection.get("risk_score") or 0) < args.min_score:
            reason = f"score {projection.get('risk_score')} below {args.min_score:g}"
        if not reason and category in used_categories:
            reason = f"already adding a {category} case this run"
        if not reason and category == GENERIC_CATEGORY[0] and not ALLOW_GENERIC:
            reason = "no specific fraud category"
        capture = _capture_source(row)
        if not reason and not capture:
            reason = "no local capture"
        if reason:
            skipped.append({"domain": domain, "reason": reason})
            continue
        pending = kept + [c for c, _ in additions]
        case_id = next_id(pending, high_water)
        slug = slug_of(domain)
        if slug in {c["slug"] for c in pending}:
            slug = f"{slug}-{case_id.lower()}"
        image = f"{slug}{capture.suffix.lower()}"
        additions.append((build_case(projection, case_id, slug, image, row.screenshot_url), capture))
        known.add(domain)
        used_categories.add(category)

    if args.dry_run:
        print(json.dumps({"since": since.isoformat(), "withdraw": withdrawals, "would_add": [c for c, _ in additions], "skipped": skipped}, indent=2, ensure_ascii=False))
        return 0

    for w in withdrawals:
        case = next(c for c in cases if c["id"] == w["id"])
        (CAPTURES / case["image"]).unlink(missing_ok=True)
    for case, capture in additions:
        CAPTURES.mkdir(parents=True, exist_ok=True)
        shutil.copy2(capture, CAPTURES / case["image"])
    new_cases = kept + [c for c, _ in additions]
    if withdrawals or additions:
        CASES_PATH.write_text(json.dumps(new_cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    all_ids = [int(c["id"][3:]) for c in cases + new_cases if re.fullmatch(r"SA-\d{3}", c["id"])]
    state.update({
        "last_checked_at": now.isoformat(),
        "curated_ids": sorted((curated - withdrawn_ids) | {c["id"] for c, _ in additions}),
        "id_high_water": max(all_ids + [high_water]),
        "withdrawn": state.get("withdrawn", []) + withdrawals,
        "last_run": {"added": [c["id"] for c, _ in additions], "withdrawn": sorted(withdrawn_ids)},
    })
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if (withdrawals or additions) and args.build:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "build.py")], cwd=ROOT, check=True)
        subprocess.run([sys.executable, str(ROOT / "scripts" / "check.py")], cwd=ROOT, check=True)
    parts = [f"add {', '.join(c['id'] for c, _ in additions)}" if additions else "", f"withdraw {', '.join(sorted(withdrawn_ids))}" if withdrawals else ""]
    _auto_git("content: curator " + "; ".join(p for p in parts if p))

    print(f"observatory-curator: added={len(additions)} withdrawn={len(withdrawals)} since={since.isoformat()}")
    for case, _ in additions:
        print(f"  + {case['id']} {case['subject']} ({case['category']}, {case['assessment_source']})")
    for w in withdrawals:
        print(f"  - {w['id']} {w['subject']}: {w['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
