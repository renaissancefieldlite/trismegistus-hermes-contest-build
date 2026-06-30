from __future__ import annotations

from html.parser import HTMLParser
import re
import time
import urllib.parse
import urllib.request
from typing import Any


NOUS_CAREERS_URL = "https://nousresearch.com/careers/"
LOCAL_EVIDENCE_TERMS = (
    "trismegistus",
    "tris",
    "coherence",
    "123",
    "simple 123",
    "100 question",
    "500 question",
    "telegram",
    "openclaw",
    "nemoclaw",
    "nemohermes",
    "paid-work",
    "paid work",
    "67 dollar",
    "business partner",
    "research partner",
    "golden field",
    "golden mark",
    "c5b",
    "cb5",
    "mirror architecture",
    "mirror interface",
    "source mirror",
    "universal data pattern",
    "phase 12c",
    "phase12c",
    "phase 12b",
    "phase12b",
    "muse",
    "hrv",
    "eeg",
    "hrv1.0",
    "quantumhrv",
    "quantum hrv",
    "experiment 1",
    "experiment 2",
    "experiment 3",
    "experiment 4",
    "experiment 5",
    "experiment 6",
    "experiment 7",
    "experiments 1-7",
    "seven experiments",
    "0.67 hz",
    "nest",
    "lattice",
    "hadamard",
    "diophantine",
    "quantum bridge",
    "google willow",
    "willow",
    "echo kernel",
    "echo-kernel",
    "pennylane",
    "qiskit",
    "cirq",
    "bell calibration",
    "bell-state",
    "discipline partner",
    "field expert",
    "ai expert",
    "ai partner",
    "six field",
    "ai / agent",
    "ai agent architecture",
    "ai_agent_architecture",
    "quantum computing",
    "quantum circuits",
    "quantum computing / circuits",
    "quantum computing and mathematics",
    "quantum_computing_circuits_mathematics",
    "structured matter",
    "physical systems",
    "structured_matter_physical_systems",
    "life sciences",
    "medical research",
    "life_sciences_medical_research",
    "mirror architecture / golden mark",
    "golden mark evidence",
    "mirror_architecture_golden_mark_evidence",
    "relationship / paid-work",
    "paid-work field operations",
    "relationship_paid_work_field_ops",
    "source pack",
    "evidence stack",
    "source row",
    "source rows",
    "browser worker",
    "webarena",
    "web arena",
    "swe",
    "swe-bench",
    "gaia",
    "benchmark foundation",
    "benchmark foundations",
    "dress rehearsal",
    "showtime",
    "competition ready",
    "competition",
    "nous careers",
    "quantum partner",
    "quantum partners",
    "quantum scouting",
    "source entity",
    "source entities",
    "company row",
    "company rows",
    "relationship draft",
    "relationship drafts",
    "margin row",
    "margin rows",
    "partner row",
    "partner rows",
)

PROJECT_DOCTRINE_TERMS = (
    "trismegistus",
    "tris",
    "telegram",
    "openclaw",
    "nemoclaw",
    "nemohermes",
    "coherence",
    "123",
    "simple 123",
    "100 question",
    "500 question",
    "67 dollar",
    "paid-work",
    "paid work",
    "business partner",
    "receipt",
    "receipts",
    "behind the veil",
    "swe",
    "swe-bench",
    "webarena",
    "web arena",
    "gaia",
    "benchmark foundation",
    "dress rehearsal",
    "showtime",
    "competition ready",
    "ai expert",
    "ai partner",
    "unclear",
    "compressed",
    "clarification",
    "clarifying question",
)

BROWSER_SOURCE_TERMS = (
    "live site",
    "live sites",
    "live source",
    "source sequence",
    "browser sequence",
    "browser mission",
    "browser stack",
    "playwright",
    "cdp",
    "nvidia quantum",
    "quantum partner",
    "quantum partners",
    "quantum companies",
    "quantum research",
    "nous careers",
    "nous research careers",
    "renaissance field lite",
    "rfl public",
    "webarena baseline",
    "webarena map",
)

BROWSER_ACTION_TERMS = (
    "run",
    "fetch",
    "read",
    "source",
    "research",
    "sweep",
    "go",
    "open",
    "visit",
    "check",
    "verify",
    "mission",
    "sequence",
    "crawl",
    "test",
)


class _TextLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[dict[str, str]] = []
        self._in_title = False
        self._skip_depth = 0
        self._href_stack: list[str | None] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        if tag_name in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if tag_name == "title":
            self._in_title = True
        if tag_name == "a":
            attrs_map = {key.lower(): value for key, value in attrs}
            self._href_stack.append(attrs_map.get("href"))

    def handle_endtag(self, tag: str) -> None:
        tag_name = tag.lower()
        if tag_name in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag_name == "title":
            self._in_title = False
        if tag_name == "a" and self._href_stack:
            self._href_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        clean = " ".join(data.split())
        if not clean:
            return
        if self._in_title:
            self.title_parts.append(clean)
        self.text_parts.append(clean)
        if self._href_stack:
            href = self._href_stack[-1]
            if href:
                self.links.append({"text": clean, "href": href})


def _absolute_url(base_url: str, href: str) -> str:
    url = urllib.parse.urljoin(base_url, href)
    return _canonical_url(url)


def _safe_absolute_url(base_url: str, href: str) -> str | None:
    try:
        return _absolute_url(base_url, href)
    except ValueError:
        return None


def _canonical_url(url: str) -> str:
    if url.startswith("https://nousresearch.com/research-scientist") and not url.endswith("/"):
        return "https://nousresearch.com/research-scientist/"
    return url


def _normalize_url(target: str) -> str:
    text = target.strip()
    if re.match(r"^https?://", text, flags=re.IGNORECASE):
        return text
    return f"https://{text}"


def _fetch_html(url: str, timeout: int = 12) -> dict[str, Any]:
    started = time.time()
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Trismegistus-source-check/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(1_000_000).decode("utf-8", errors="replace")
            final_url = response.geturl()
            status = getattr(response, "status", 200)
    except Exception as exc:  # noqa: BLE001 - surfaced as source receipt.
        return {"ok": False, "url": url, "error": str(exc), "latency_ms": round((time.time() - started) * 1000)}
    parser = _TextLinkParser()
    parser.feed(raw)
    title = " ".join(parser.title_parts).strip()
    text = " ".join(parser.text_parts)
    text = re.sub(r"\s+", " ", text).strip()
    links: list[dict[str, str]] = []
    for item in parser.links:
        href = item.get("href")
        if not href:
            continue
        absolute = _safe_absolute_url(final_url, href)
        if not absolute:
            continue
        links.append({"text": item["text"], "url": absolute})
    return {
        "ok": True,
        "url": url,
        "final_url": _canonical_url(final_url),
        "status": status,
        "title": title,
        "text": text[:12000],
        "links": links[:400],
        "latency_ms": round((time.time() - started) * 1000),
    }


def _decode_duckduckgo_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return query["uddg"][0]
    return url


def _search_web(query: str, max_results: int = 5) -> dict[str, Any]:
    started = time.time()
    search_url = "https://lite.duckduckgo.com/lite/?" + urllib.parse.urlencode({"q": query})
    page = _fetch_html(search_url, timeout=14)
    if not page.get("ok"):
        return {
            "ok": False,
            "source": "source-fetch",
            "kind": "web-search",
            "query": query,
            "search_url": search_url,
            "error": page.get("error"),
            "latency_ms": round((time.time() - started) * 1000),
        }
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in page.get("links", []):
        text = str(link.get("text", "")).strip()
        url = _decode_duckduckgo_url(str(link.get("url", "")))
        if not text or not url.startswith(("http://", "https://")):
            continue
        host = urllib.parse.urlparse(url).netloc.lower()
        if "duckduckgo.com" in host:
            continue
        key = url.split("#", 1)[0]
        if key in seen:
            continue
        seen.add(key)
        results.append({"title": text, "url": url})
        if len(results) >= max_results:
            break
    fetched = []
    for result in results[:3]:
        item = _fetch_html(result["url"], timeout=12)
        item["result_title"] = result["title"]
        fetched.append(item)
    return {
        "ok": bool(results),
        "source": "source-fetch",
        "kind": "web-search",
        "query": query,
        "search_url": search_url,
        "results": results,
        "fetched": fetched,
        "latency_ms": round((time.time() - started) * 1000),
    }


def _extract_urls(text: str) -> list[str]:
    return [match.rstrip(".,;)") for match in re.findall(r"https?://[^\s<>\"]+", text)]


def _extract_source_targets(text: str) -> list[str]:
    targets = _extract_urls(text)
    seen = {item.lower() for item in targets}
    for match in re.finditer(r"(?<!@)\b((?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s<>\"]*)?)", text, flags=re.IGNORECASE):
        raw = match.group(1).rstrip(".,;)")
        if raw.lower().startswith(("http://", "https://")):
            continue
        if raw.lower() in seen:
            continue
        seen.add(raw.lower())
        targets.append(_normalize_url(raw))
    return targets[:3]


def _role_needles(message: str) -> list[str]:
    lower = message.lower()
    needles: list[str] = []
    if "research" in lower or "researcher" in lower or "scientist" in lower:
        needles.append("research scientist")
    if "full stack" in lower:
        needles.append("full stack engineer")
    if "machine learning" in lower or "ml engineer" in lower:
        needles.append("machine learning engineer")
    if "forward deployed" in lower or "fde" in lower:
        needles.append("forward deployed engineer")
    if "ui" in lower or "ux" in lower or "designer" in lower:
        needles.append("ui/ux designer")
    if "counsel" in lower or "legal" in lower:
        needles.append("general counsel")
    return needles


def _is_job_worker_command(message: str) -> bool:
    lower = message.lower()
    return any(
        term in lower
        for term in (
            "find jobs",
            "find some jobs",
            "scan jobs",
            "scout jobs",
            "look for work",
            "apply",
            "draft proposal",
            "worker cycle",
            "run worker",
        )
    )


def _contains_discipline_lane_reference(lower: str) -> bool:
    return any(
        term in lower
        for term in (
            "ai / agent",
            "ai agent",
            "agent architecture",
            "ai_agent_architecture",
            "quantum computing",
            "quantum circuit",
            "quantum circuits",
            "quantum computing / circuits",
            "quantum computing and mathematics",
            "quantum_computing_circuits_mathematics",
            "structured matter",
            "physical systems",
            "structured_matter_physical_systems",
            "life sciences",
            "medical research",
            "life_sciences_medical_research",
            "mirror architecture",
            "golden mark",
            "mirror_architecture_golden_mark_evidence",
            "relationship / paid-work",
            "relationship paid-work",
            "paid-work field",
            "relationship_paid_work_field_ops",
            "discipline partner lane",
            "six discipline",
            "5+1",
            "five plus one",
            "field-expert disciplines",
            "field expert disciplines",
        )
    )


def _extract_discipline_lane_id(lower: str) -> str | None:
    lane_aliases = (
        ("ai_agent_architecture", ("ai / agent", "ai agent architecture", "ai_agent_architecture")),
        (
            "quantum_computing_circuits_mathematics",
            (
                "quantum computing",
                "quantum circuit",
                "quantum circuits",
                "quantum computing / circuits",
                "quantum computing and mathematics",
                "quantum_computing_circuits_mathematics",
            ),
        ),
        (
            "structured_matter_physical_systems",
            ("structured matter", "physical systems", "structured_matter_physical_systems"),
        ),
        (
            "life_sciences_medical_research",
            ("life sciences", "medical research", "life_sciences_medical_research"),
        ),
        (
            "mirror_architecture_golden_mark_evidence",
            (
                "mirror architecture / golden mark",
                "mirror architecture",
                "golden mark evidence",
                "mirror_architecture_golden_mark_evidence",
            ),
        ),
        (
            "relationship_paid_work_field_ops",
            (
                "relationship / paid-work",
                "relationship paid-work",
                "paid-work field operations",
                "relationship_paid_work_field_ops",
                "sales networking",
                "outreach sales",
                "relationship operations",
            ),
        ),
    )
    for lane_id, aliases in lane_aliases:
        if any(alias in lower for alias in aliases):
            return lane_id
    return None


def _project_doctrine(message: str) -> dict[str, Any] | None:
    lower = message.lower()
    if "golden field lite" in lower:
        return {
            "ok": True,
            "source": "project-doctrine",
            "kind": "project-doctrine",
            "topic": "golden-field-lite-bridge",
            "claim": "Golden Field Lite is the known-good local Hermes conversational bridge that Tris imports read-only as its smoother research-partner spine.",
            "evidence": (
                "The active local route uses the Golden Field Lite generate endpoint at "
                "http://127.0.0.1:8788/api/generate with the OpenHermes 2.5 Mistral 7B 4-bit checkpoint, "
                "while Tris keeps its own SQL/JSON/RAG memory, OpenClaw/NemoClaw receipt layer, browser missions, "
                "source entities, and benchmark harness."
            ),
            "boundary": "Golden Field Lite is a runtime and behavior bridge, not proof that OpenClaw worker autonomy is complete.",
            "next_gate": "Use the baseline-vs-architecture evals to show what Tris gains on top of the Golden Field Lite/Hermes route.",
        }
    if (
        ("who are you" in lower or "what are you" in lower or "identity" in lower)
        and ("architect d" in lower or "trismegistus" in lower or "tris" in lower)
    ):
        return {
            "ok": True,
            "source": "project-doctrine",
            "kind": "project-doctrine",
            "topic": "tris-identity",
            "claim": "Trismegistus is the Tris field node: a coherent conversational research partner and operator layer for Architect D's build surface.",
            "evidence": (
                "Tris inherits the Golden Field Lite/Hermes conversational spine, uses Tris SQL/JSON/RAG memory, "
                "routes source requests through the Telegram/OpenClaw field mission bridge, and organizes the "
                "Mirror Architecture work into six discipline partner lanes."
            ),
            "boundary": "This identifies the local operator role and keeps external actions review-gated until worker receipts exist.",
            "next_gate": "Prove the role through visible 100-question coherence/source/mission iterations and saved worker receipts.",
        }
    if any(term in lower for term in ("dress rehearsal", "showtime", "competition ready", "competition readiness")):
        return {
            "ok": True,
            "source": "project-doctrine",
            "kind": "project-doctrine",
            "topic": "showtime-dress-rehearsal",
            "claim": "The showtime job is to demonstrate Tris as a coherent AI expert partner with real receipts underneath.",
            "evidence": (
                "Current foundation: SQL/JSON/RAG memory, Golden Mark/CB5 evidence, live Telegram channel, "
                "source/field-mission bridge, browser traces, paid-work draft lane, WebArena hard receipt, "
                "and SWE-bench local official selected-test foundation parked pending hosted/maintainer response."
            ),
            "boundary": "Normal chat should stay conversational. Audit receipts surface only when proof, source paths, or benchmark detail are requested.",
            "next_gate": "Run a phone/Telegram source mission, show the saved receipt, summarize benchmark truth, and produce one review-gated relationship draft.",
        }
    if any(term in lower for term in ("benchmark foundation", "swe", "swe-bench", "webarena", "web arena", "gaia")):
        return {
            "ok": True,
            "source": "project-doctrine",
            "kind": "project-doctrine",
            "topic": "benchmark-foundation",
            "claim": "The benchmark foundation supports Tris as a serious AI expert partner, and the SWE-bench helper route becomes the recursive task discipline for every lane.",
            "evidence": (
                "SWE-bench: local official selected-test foundation is parked while hosted sb-cli/maintainer review is pending. "
                "The reusable behavior is already active: exact source inspection, smallest patch/action, preflight, repair from failed receipts, "
                "JSON/Markdown trace saving, and scale only after clean gates. "
                "WebArena: hard receipt is public-ready with final-row fixture/evaluator boundaries documented upstream. "
                "GAIA: local source smoke is clean, but official/private scoring remains Hugging Face gated."
            ),
            "boundary": "Hosted SWE placement, clean WebArena final-row signoff, and official GAIA score stay parked until those external gates answer. The recursive discipline is active; leaderboard claims remain gated.",
            "next_gate": "Use the recursive loop inside worker, source, relationship, and code tasks: inspect source, preflight, repair, save receipt, then scale.",
        }
    if any(
        term in lower
        for term in (
            "5+1",
            "five plus one",
            "five field",
            "5 field",
            "six lane",
            "six-lane",
            "cross train",
            "cross-train",
            "cross trained",
            "cross-trained",
        )
    ):
        return {
            "ok": True,
            "source": "project-doctrine",
            "kind": "project-doctrine",
            "topic": "five-plus-one-field-expert-curriculum",
            "claim": "Tris is organized as a 5+1 AI expert partner: five field-expert disciplines plus one relationship, paid-work, sales, and networking operations lane.",
            "evidence": (
                "The SQL/RAG lane map holds AI / Agent Architecture, Quantum Computing / Circuits and Mathematics, Structured Matter / Physical Systems, "
                "Life Sciences / Medical Research, and Mirror Architecture / Golden Mark Evidence as the five field-expert disciplines. "
                "The sixth lane is Relationship / Paid-Work Field Operations, which covers outreach, bids, partner follow-up, margin checks, "
                "Apple Mail sends, Stripe sandbox receipts, and review-gated external action."
            ),
            "boundary": "This is an operational curriculum and retrieval spine. Public proof still depends on source-backed lane evals and saved receipts.",
            "next_gate": "Run matched baseline-vs-Tris eval rows across the five field disciplines and keep relationship operations receipt-gated.",
        }
    if any(term in lower for term in ("apple mail", "email batch", "batch send", "rapidly send", "approved email")):
        return {
            "ok": True,
            "source": "project-doctrine",
            "kind": "project-doctrine",
            "topic": "approved-apple-mail-batch-capability",
            "claim": "Tris can rapidly execute approved direct-address outreach through Apple Mail while saving one receipt per send.",
            "evidence": (
                "On 2026-06-29, Architect D approved a live-fire Quadro follow-up batch. "
                "Tris sent six direct-address follow-up emails through the RFL Apple Mail bridge in roughly two seconds: "
                "ServiceNow, Vanta, Freshworks/Freshdesk, Five9, Talkdesk, and Workiva. "
                "Each send has a JSON and Markdown receipt under data/rfl_mail_actions."
            ),
            "boundary": "This is only for direct email addresses with explicit approval. Portal-only partner routes remain portal/form tasks and are not counted as sent emails.",
            "next_gate": "Add reply triage, portal submission packets, and margin scoring to the relationship/paid-work operations lane.",
        }
    if any(
        term in lower
        for term in (
            "recursive nature",
            "recursive discipline",
            "recursive operating discipline",
            "operating discipline",
            "recursive task discipline",
            "recursive repair discipline",
            "recursive receipt loop",
            "recursive loop",
            "passing swe",
            "swe discipline",
            "codex helper recursion",
            "codex-helper recursion",
        )
    ):
        return {
            "ok": True,
            "source": "project-doctrine",
            "kind": "project-doctrine",
            "topic": "recursive-swe-operating-discipline",
            "claim": "Tris should treat the SWE/Codex-helper lane as an operating pattern, not an isolated benchmark.",
            "evidence": (
                "The stable helper pipeline was: inspect source in the exact task environment, author the smallest valid action or diff, "
                "run preflight checks, repair from the failed receipt, build a nonempty prediction/receipt, and only scale after the clean gate. "
                "That same loop now guides source missions, worker packets, relationship drafts, benchmark slices, and future code upgrades."
            ),
            "boundary": "This does not mean every Tris task is a SWE task, and it does not upgrade parked hosted leaderboard claims. It means the recursive proof behavior is the default way Tris engages work.",
            "next_gate": "Run the next Telegram/worker/source rehearsal using this loop and log failures as repair targets instead of conversation drift.",
        }
    direct_receipt_boundary = "receipt" in lower and any(
        term in lower
        for term in (
            "behind the veil",
            "receipt boundary",
            "show receipts",
            "when should",
            "when do",
            "audit layer",
            "proof view",
        )
    )
    if direct_receipt_boundary and not _contains_discipline_lane_reference(lower):
        return {
            "ok": True,
            "source": "project-doctrine",
            "kind": "project-doctrine",
            "topic": "receipt-voice-boundary",
            "claim": "Receipts are the audit layer behind the voice, not the default speaking style.",
            "evidence": (
                "Tris should answer like a coherent partner first. When the task calls for proof, source paths, "
                "runtime truth, or audit view, it can reveal saved receipts. Otherwise it should keep receipts "
                "behind the surface and avoid prompt/runtime dumps."
            ),
            "boundary": "Hiding receipt noise is not hiding proof; it is separating operator voice from audit trace.",
            "next_gate": "Keep every source, worker, Telegram, and iteration run saved to JSON/Markdown so proof can be opened on request.",
        }
    if "123" in lower or "simple" in lower and "test" in lower:
        return {
            "ok": True,
            "source": "project-doctrine",
            "kind": "project-doctrine",
            "topic": "coherence-probes",
            "claim": "Simple 123 checks are coherence probes, not meaningless chatter.",
            "evidence": (
                "They test whether Tris keeps the operator arc, responds naturally, avoids prompt/receipt spill, "
                "and understands that the live goal is a coherent field-expert research and business partner."
            ),
            "boundary": "Passing a 123 probe only proves the live conversational route is not broken.",
            "next_gate": "Use the same probes inside the 100-turn visible iteration run and track failures over time.",
        }
    if "telegram" in lower and ("source" in lower or "channel" in lower or "ask" in lower):
        return {
            "ok": True,
            "source": "project-doctrine",
            "kind": "project-doctrine",
            "topic": "telegram-field-mission-bridge",
            "claim": "Telegram should behave as the mobile Tris channel, not as a separate improvising bot.",
            "evidence": (
                "The live gate is Telegram/OpenClaw -> Tris /api/field-mission -> saved source_missions "
                "and RAG/source table receipts. Source requests should call the bridge directly, answer from "
                "the saved receipt, and ask one clarifying question when the target is missing."
            ),
            "boundary": "No outbound post, application, spend, or partner action is implied by a source mission.",
            "next_gate": "Run the first live Telegram phone mission through this bridge and compare it to the browser/API receipt.",
        }
    if any(
        term in lower
        for term in (
            "100 question",
            "500 question",
            "100-turn",
            "500-turn",
            "iteration run",
            "iter run",
            "question iteration",
            "coherence iteration",
        )
    ):
        return {
            "ok": True,
            "source": "project-doctrine",
            "kind": "project-doctrine",
            "topic": "coherence-iteration-ladder",
            "claim": "The 100-question run is the visible cognition/coherence training and test lane; the 500-question run is the stability curve.",
            "evidence": (
                "The run should probe presence, context recall, self-explanation, source accuracy, Mirror Architecture reasoning, "
                "OpenClaw/Telegram route discipline, paid-work margin logic, clarification behavior, and meta-improvement. "
                "Every run saves JSON and Markdown receipts for comparison."
            ),
            "boundary": "Engineering eval and demo trace for measuring context stability, field-expert growth, source discipline, and mission coherence.",
            "next_gate": "Run 100 visible turns from the command, inspect failures, patch the weak lanes, then scale to 500.",
        }
    if ("unclear" in lower or "compressed" in lower or "clarification" in lower) and (
        "what should" in lower or "should you" in lower or "do?" in lower or "do " in lower
    ):
        return {
            "ok": True,
            "source": "project-doctrine",
            "kind": "project-doctrine",
            "topic": "clarification-discipline",
            "claim": "When Architect D's message is compressed or unclear, Tris should ask one clean clarifying question instead of guessing or flooding receipts.",
            "evidence": (
                "The operator rule is to slow down, preserve the arc, identify the missing variable, "
                "and keep the user moving without turning a conversation into a mechanical dump."
            ),
            "boundary": "Clarifying is not stalling; it is the correct move when guessing would break the build path.",
            "next_gate": "Track clarification behavior in the 100-turn run and mark any guessing, over-routing, or receipt flooding as a failure.",
        }
    if any(term in lower for term in ("67 dollar", "paid-work", "paid work", "budget", "scouting")):
        return {
            "ok": True,
            "source": "project-doctrine",
            "kind": "project-doctrine",
            "topic": "paid-work-margin-lane",
            "claim": "Paid-work scouting is one capital lane under the larger field-expert architecture.",
            "evidence": (
                "Tris should find real leads, score fit, estimate time/cost/margin, draft outreach or work plans, "
                "and wait for approval before sending, spending, applying, or charging."
            ),
            "boundary": "Draft mode only until email, Stripe, and external action receipts are explicitly wired and approved.",
            "next_gate": "Add margin scoring rows and review-gated relationship draft mode to the mission queue.",
        }
    if any(term in lower for term in ("business partner", "research partner", "trismegistus path", "coherent research")):
        return {
            "ok": True,
            "source": "project-doctrine",
            "kind": "project-doctrine",
            "topic": "tris-research-business-partner",
            "claim": "Trismegistus is meant to become a coherent conversational field expert, research partner, and business operator.",
            "evidence": (
                "The current spine combines Golden Field Lite/Hermes conversational pattern, Tris SQL/JSON/RAG memory, "
                "six discipline-partner lanes, Telegram/OpenClaw source routing, and paid-work scouting with receipt discipline."
            ),
            "boundary": "Current proof is local route, memory, source, and eval behavior; full autonomous worker action remains gated by receipts.",
            "next_gate": "Run visible coherence iterations, patch failures, then connect verified OpenClaw worker and relationship draft missions.",
        }
    if "openclaw" in lower or "nemoclaw" in lower or "nemohermes" in lower:
        return {
            "ok": True,
            "source": "project-doctrine",
            "kind": "project-doctrine",
            "topic": "openclaw-worker-gate",
            "claim": "The next OpenClaw/NemoClaw gate is a saved worker receipt, not another status card.",
            "evidence": (
                "The browser/API field mission bridge has passed, and the sandbox can call the host bridge. "
                "The next step is a live worker loop that takes a bounded mission, acts through the configured route, "
                "and saves the session/JSON/Markdown receipt."
            ),
            "boundary": "Model route and source bridge are not the same as completed autonomous external action.",
            "next_gate": "Run a bounded OpenClaw worker mission and save the receipt before claiming worker autonomy.",
        }
    if "coherence" in lower or "123" in lower:
        return {
            "ok": True,
            "source": "project-doctrine",
            "kind": "project-doctrine",
            "topic": "coherence-probes",
            "claim": "Simple 123 checks are coherence probes, not meaningless chatter.",
            "evidence": (
                "They test whether Tris keeps the operator arc, responds naturally, avoids prompt/receipt spill, "
                "and asks for clarification instead of degrading into a mechanical retrieval system."
            ),
            "boundary": "Passing a 123 probe only proves the live conversational route is not broken.",
            "next_gate": "Use the same probes inside the 100-turn visible iteration run and track failures over time.",
        }
    return None


def _search_query(message: str) -> str:
    text = " ".join(message.split()).strip()
    text = re.sub(r"^(tris|trismegistus|rick|bro|alright|ok|okay)[,:\s]+", "", text, flags=re.IGNORECASE)
    replacements = (
        r"\bplease\b",
        r"\bgo\b",
        r"\bcan you\b",
        r"\bsearch(?: the)? web(?: for)?\b",
        r"\bweb search(?: for)?\b",
        r"\blook up\b",
        r"\bresearch\b",
        r"\bverify\b",
        r"\bfind info(?:rmation)?(?: on| about)?\b",
        r"\bfind(?: me)?(?: the)?\b",
        r"\bshow(?: me)?(?: the)?\b",
        r"\btell me(?: about)?\b",
        r"\bwhat do you know(?: about)?\b",
        r"\bsummarize\b",
        r"\bexplain\b",
        r"\bfetch\b",
        r"\bread(?: the)?(?: page| site| website)?\b",
        r"\bsource check\b",
        r"\bsource rows?\b",
        r"\bevidence rows?\b",
        r"\bcurrent\b",
        r"\blatest\b",
        r"\bloaded\b",
        r"\babout\b",
    )
    for pattern in replacements:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" .,:;")
    return text[:220]


def _wants_indexed_evidence(message: str) -> bool:
    lower = message.lower()
    domain_terms = LOCAL_EVIDENCE_TERMS + BROWSER_SOURCE_TERMS + (
        "nous",
        "webarena",
        "benchmark route",
        "browser worker",
        "source-intake",
    )
    evidence_intents = (
        "source row",
        "source rows",
        "evidence row",
        "evidence rows",
        "claim",
        "evidence",
        "boundary",
        "next gate",
        "what sources",
        "sources has",
        "source has",
        "loaded",
        "what tris knows",
        "what do you know",
        "status for tris",
        "benchmark route status",
        "route status",
        "support label",
        "support labels",
        "source-intake",
        "indexed",
    )
    return any(term in lower for term in domain_terms) and any(term in lower for term in evidence_intents)


def _wants_source_entities(message: str) -> bool:
    lower = message.lower()
    entity_terms = (
        "source entity",
        "source entities",
        "company row",
        "company rows",
        "companies loaded",
        "partner row",
        "partner rows",
        "partner scouting",
        "relationship draft",
        "relationship drafts",
        "margin row",
        "margin rows",
        "margin scoring",
        "quantum companies",
        "quantum partner",
        "quantum partners",
    )
    return any(term in lower for term in entity_terms) and any(
        term in lower
        for term in (
            "what",
            "show",
            "list",
            "loaded",
            "status",
            "have",
            "know",
            "draft",
            "score",
            "source",
        )
    )


def _source_entity_table(message: str) -> dict[str, Any]:
    from . import db

    rows = db.list_source_entities(limit=30)
    entities = rows.get("source_entities") or []
    drafts = rows.get("relationship_drafts") or []
    lower = message.lower()
    latest_source_sequence_id = None
    wants_history = any(
        term in lower
        for term in (
            "all rows",
            "all source",
            "all sources",
            "history",
            "older",
            "previous",
            "mixed",
        )
    )
    if entities and not wants_history:
        latest_source_sequence_id = str(entities[0].get("source_mission_id") or "")
        if latest_source_sequence_id:
            entities = [
                item
                for item in entities
                if str(item.get("source_mission_id") or "") == latest_source_sequence_id
            ]
            drafts = [
                item
                for item in drafts
                if str(item.get("source_entity_id") or "").startswith(f"{latest_source_sequence_id}:")
            ]
    if "quantum" in lower:
        entities = [item for item in entities if "quantum" in item.get("lane", "") or item.get("entity_type") == "company"]
        drafts = [
            item
            for item in drafts
            if any(entity.get("id") == item.get("source_entity_id") for entity in entities)
        ]
    return {
        "ok": bool(entities or drafts),
        "source": "tris-source-entities",
        "kind": "source-entity-table",
        "query": message,
        "source_sequence_id": latest_source_sequence_id or "all_visible_rows",
        "source_entities": entities,
        "relationship_drafts": drafts,
        "boundary": "These are normalized source and draft rows. They are not outbound actions or partner claims.",
        "next_gate": "Generate review-gated relationship drafts with citations, then run a bounded benchmark slice.",
    }


def should_handle(message: str) -> bool:
    lower = message.lower()
    local_evidence_intent = (
        "tell me",
        "what do you know",
        "explain",
        "summarize",
        "show",
        "source",
        "evidence",
        "receipt",
        "read",
        "fetch",
        "verify",
        "research",
        "status",
        "checkpoint",
        "lane",
        "rag",
        "database",
        "memory",
        "about",
    )
    if _wants_source_entities(message):
        return True
    if any(term in lower for term in PROJECT_DOCTRINE_TERMS):
        return True
    if any(term in lower for term in BROWSER_SOURCE_TERMS) and any(term in lower for term in BROWSER_ACTION_TERMS):
        return True
    if any(term in lower for term in LOCAL_EVIDENCE_TERMS) and any(term in lower for term in local_evidence_intent):
        return True
    if _extract_source_targets(message):
        return any(
            term in lower
            for term in (
                "fetch",
                "read",
                "source",
                "exact",
                "url",
                "role",
                "career",
                "page",
                "site",
                "website",
                "domain",
                "verify",
                "look up",
                "pull",
                "crawl",
            )
        )
    if _is_job_worker_command(message):
        return False
    if any(
        term in lower
        for term in (
            "search web",
            "web search",
            "look up",
            "find info",
            "research",
            "verify",
            "latest",
            "current",
            "source check",
        )
    ):
        return bool(_search_query(message))
    if "nous" in lower and any(term in lower for term in ("role", "career", "position", "job", "researcher", "research scientist", "exact url", "link")):
        return True
    return False


def _find_nous_role(message: str) -> dict[str, Any]:
    careers = _fetch_html(NOUS_CAREERS_URL)
    if not careers.get("ok"):
        return {"ok": False, "source": "source-fetch", "error": careers.get("error"), "careers": careers}
    needles = _role_needles(message) or ["research scientist"]
    matches: list[dict[str, str]] = []
    for item in careers.get("links", []):
        text = str(item.get("text", "")).lower()
        url = str(item.get("url", ""))
        for needle in needles:
            if needle in text or needle.replace("/", " ") in text:
                if url not in [match["url"] for match in matches]:
                    matches.append({"role": item.get("text", "").strip(), "url": url})
    if not matches and any("research" in needle for needle in needles):
        matches.append({"role": "Research Scientist", "url": "https://nousresearch.com/research-scientist/"})
    role_page = _fetch_html(matches[0]["url"]) if matches else {}
    excerpt = ""
    if role_page.get("text"):
        text = role_page["text"]
        index = text.lower().find(matches[0]["role"].lower()) if matches else -1
        if index < 0:
            index = 0
        excerpt = text[index:index + 900]
    return {
        "ok": bool(matches),
        "source": "source-fetch",
        "kind": "nous-career-role",
        "careers_url": NOUS_CAREERS_URL,
        "role": matches[0] if matches else None,
        "role_page": {
            "ok": role_page.get("ok"),
            "url": role_page.get("final_url") or (matches[0]["url"] if matches else ""),
            "title": role_page.get("title"),
            "excerpt": excerpt,
            "latency_ms": role_page.get("latency_ms"),
        },
        "careers_title": careers.get("title"),
        "latency_ms": careers.get("latency_ms"),
    }


def run(message: str) -> dict[str, Any]:
    urls = _extract_source_targets(message)
    lower = message.lower()
    if _wants_source_entities(message):
        rows = _source_entity_table(message)
        if rows.get("ok"):
            return rows
    lane_id = _extract_discipline_lane_id(lower)
    if lane_id:
        from . import evidence_index

        local = evidence_index.search(lane_id)
        if local.get("ok"):
            return local
    if "golden field lite" in lower:
        doctrine = _project_doctrine(message)
        if doctrine:
            return doctrine
    doctrine = _project_doctrine(message)
    if doctrine:
        return doctrine
    if _wants_indexed_evidence(message):
        from . import evidence_index

        local = evidence_index.search(lane_id or _search_query(message) or message)
        if local.get("ok"):
            return local
    if any(term in lower for term in LOCAL_EVIDENCE_TERMS):
        from . import evidence_index

        local = evidence_index.search(_search_query(message) or message)
        if local.get("ok"):
            return local
        return {
            "ok": False,
            "source": "tris-evidence-index",
            "kind": "local-evidence-rag",
            "query": message,
            "results": [],
            "error": "No local evidence node matched the internal project query.",
        }
    if "nous" in lower and any(term in lower for term in ("role", "career", "position", "job", "researcher", "research scientist")):
        return _find_nous_role(message)
    if urls:
        fetched = [_fetch_html(url) for url in urls[:3]]
        return {"ok": any(item.get("ok") for item in fetched), "source": "source-fetch", "kind": "url-fetch", "fetched": fetched}
    query = _search_query(message)
    if query:
        return _search_web(query)
    return {"ok": False, "source": "source-fetch", "error": "No source-fetch route matched."}


def _wants_full_receipt(request: str | None) -> bool:
    lower = str(request or "").lower()
    if "when should" in lower and ("behind the veil" in lower or "stay behind" in lower):
        return False
    if _contains_discipline_lane_reference(lower) and not any(
        term in lower
        for term in (
            "full receipt",
            "raw receipt",
            "audit view",
            "show receipt",
            "show proof",
            "source paths",
            "source path",
            "exact evidence",
        )
    ):
        return False
    return any(
        term in lower
        for term in (
            "full receipt",
            "raw receipt",
            "show receipt",
            "show proof",
            "source paths",
            "source path",
            "exact evidence",
            "audit view",
            "audit",
        )
    )


def answer(receipt: dict[str, Any], request: str | None = None) -> str:
    request_lower = str(request or "").lower()
    if receipt.get("kind") == "project-doctrine":
        if _wants_full_receipt(request):
            lines = [
                "Full source receipt:",
                f"Topic: {receipt.get('topic')}",
                f"Claim: {receipt.get('claim')}",
                f"Evidence: {receipt.get('evidence')}",
                f"Boundary: {receipt.get('boundary')}",
                f"Next gate: {receipt.get('next_gate')}",
            ]
            return "\n".join(lines)
        return "\n".join(
            [
                "Clean read:",
                str(receipt.get("claim") or "").strip(),
                "",
                "What that means for Tris:",
                str(receipt.get("evidence") or "").strip(),
                "",
                f"Boundary: {receipt.get('boundary')}",
                f"Next gate: {receipt.get('next_gate')}",
                "",
                "Receipt is saved behind the surface; ask for the full receipt when you want audit view.",
            ]
        )
    if receipt.get("kind") == "local-evidence-rag":
        results = receipt.get("results") or []
        if not _wants_full_receipt(request):
            if not results:
                return (
                    "I do not have a strong local evidence hit for that yet. "
                    "Next gate: add or index the source card, then rerun the question with a receipt."
                )
            top = results[0]
            lane_label = str(top.get("lane_name") or top.get("lane_id") or "").strip()
            lane_names = []
            for item in results[:4]:
                lane = str(item.get("lane_id") or "").strip()
                if lane and lane not in lane_names:
                    lane_names.append(lane)
            lines = [
                "Clean read:",
                f"Lane: {lane_label}" if lane_label else "Lane: local evidence",
                "",
                str(top.get("claim") or "I found a matching local evidence lane.").strip(),
                "",
                "What that means for Tris:",
                str(top.get("evidence") or "The matching source card is indexed in the local RAG lane.").strip(),
            ]
            if lane_names:
                lines.extend(["", f"Matching lanes: {', '.join(lane_names)}"])
            if top.get("release_boundary"):
                lines.extend(["", f"Boundary: {top.get('release_boundary')}"])
            if top.get("next_gate"):
                lines.append(f"Next gate: {top.get('next_gate')}")
            if any(term in request_lower for term in ("universal data pattern", "udp", "pattern map", "pattern mapping")):
                lines.extend(
                    [
                        "",
                        "UDP mapping shape:",
                        "Repeated structure -> source support -> control/baseline separation -> recurrence/repeatability -> support label -> cross-field transfer -> next gate.",
                    ]
                )
            if any(term in request_lower for term in ("architecture-off", "architecture-on", "golden mark comparison")):
                lines.extend(
                    [
                        "",
                        "Comparison shape:",
                        "Baseline/control: architecture-off answer on the same lane task.",
                        "Architecture-on: Tris six-lane RAG plus receipt route on the same task.",
                        "Metric/score: task success, source support, recurrence/repeatability, drift/failure handling, and receipt discipline.",
                        "Failure mode: overclaim, missing control, missing support label, lost lane context, or no saved receipt.",
                        "Saved receipt: JSON/Markdown eval row for the paired run.",
                    ]
                )
            lines.append("")
            lines.append("Receipt is saved behind the surface; ask for the full receipt or source paths when you want audit view.")
            return "\n".join(lines)

        lines = ["Full source receipt:"]
        for item in results[:5]:
            lines.extend(
                [
                    "",
                    f"Lane: {item.get('lane_id')}",
                    f"Support: {item.get('support_state')}",
                    f"Claim: {item.get('claim')}",
                    f"Evidence: {item.get('evidence')}",
                    f"Boundary: {item.get('release_boundary')}",
                    f"Next gate: {item.get('next_gate')}",
                    f"Source: {item.get('source_path') or item.get('source_url')}",
                ]
            )
        if not results:
            lines.append("No local evidence node matched. Next gate: add or index the source card.")
        return "\n".join(lines)
    if receipt.get("kind") == "source-entity-table":
        entities = receipt.get("source_entities") or []
        drafts = receipt.get("relationship_drafts") or []
        if not _wants_full_receipt(request):
            if not entities and not drafts:
                return (
                    "I do not have normalized source entity rows for that yet. "
                    "Next gate: run the live-source promotion script and rerun the question."
                )
            names = ", ".join(str(item.get("name")) for item in entities[:7])
            top_drafts = sorted(
                drafts,
                key=lambda item: (float(item.get("margin_score") or 0), float(item.get("fit_score") or 0)),
                reverse=True,
            )[:3]
            lines = [
                "Clean read:",
                f"Tris has {len(entities)} normalized source entities loaded: {names}.",
                "",
                "What that means for Tris:",
                "These rows turn the browser receipt into company/role/self-source objects that can feed review-gated relationship drafts and margin checks.",
            ]
            if top_drafts:
                lines.extend(["", "Top draft lanes:"])
                for draft in top_drafts:
                    lines.append(
                        f"- {draft.get('source_entity_id')}: fit {draft.get('fit_score')}, "
                        f"margin {draft.get('margin_score')}, status {draft.get('status')}"
                    )
            lines.extend(
                [
                    "",
                    f"Boundary: {receipt.get('boundary')}",
                    f"Next gate: {receipt.get('next_gate')}",
                    "",
                    "Receipt is saved behind the surface; ask for full receipt when you want the row IDs and source paths.",
                ]
            )
            return "\n".join(lines)

        lines = ["Full source entity receipt:"]
        for entity in entities[:10]:
            lines.extend(
                [
                    "",
                    f"Entity: {entity.get('name')}",
                    f"ID: {entity.get('id')}",
                    f"Type: {entity.get('entity_type')}",
                    f"Lane: {entity.get('lane')}",
                    f"Support: {entity.get('support_state')}",
                    f"URL: {entity.get('url')}",
                    f"Fit: {entity.get('fit_label')}",
                    f"Boundary: {entity.get('boundary')}",
                    f"Next gate: {entity.get('next_gate')}",
                ]
            )
        if drafts:
            lines.extend(["", "Relationship drafts:"])
            for draft in drafts[:10]:
                lines.extend(
                    [
                        "",
                        f"Draft: {draft.get('id')}",
                        f"Source entity: {draft.get('source_entity_id')}",
                        f"Status: {draft.get('status')}",
                        f"Fit score: {draft.get('fit_score')}",
                        f"Margin score: {draft.get('margin_score')}",
                        f"Offer lane: {draft.get('offer_lane')}",
                        f"Boundary: {draft.get('boundary')}",
                        f"Next gate: {draft.get('next_gate')}",
                    ]
                )
        return "\n".join(lines)
    if receipt.get("kind") == "nous-career-role":
        role = receipt.get("role") or {}
        page = receipt.get("role_page") or {}
        if role:
            lines = [
                "Source fetch receipt:",
                f"Official role: {role.get('role')}",
                f"Official URL: {page.get('url') or role.get('url')}",
                f"Careers source: {receipt.get('careers_url')}",
            ]
            if page.get("title"):
                lines.append(f"Page title: {page.get('title')}")
            if page.get("excerpt"):
                lines.extend(["", "Source excerpt:", str(page["excerpt"])[:900]])
            return "\n".join(lines)
    if receipt.get("kind") == "url-fetch":
        lines = ["Source fetch receipt:"]
        for item in receipt.get("fetched", []):
            lines.append("")
            lines.append(f"URL: {item.get('final_url') or item.get('url')}")
            lines.append(f"OK: {item.get('ok')}")
            if item.get("title"):
                lines.append(f"Title: {item.get('title')}")
            if item.get("error"):
                lines.append(f"Error: {item.get('error')}")
            if item.get("text"):
                lines.append(f"Excerpt: {str(item.get('text'))[:600]}")
        return "\n".join(lines)
    if receipt.get("kind") == "web-search":
        lines = [
            "Source search receipt:",
            f"Query: {receipt.get('query')}",
            f"Search source: {receipt.get('search_url')}",
        ]
        if receipt.get("error"):
            lines.append(f"Error: {receipt.get('error')}")
        for index, result in enumerate(receipt.get("results", [])[:5], start=1):
            lines.extend(["", f"{index}. {result.get('title')}", f"URL: {result.get('url')}"])
        for item in receipt.get("fetched", [])[:3]:
            lines.append("")
            lines.append(f"Read: {item.get('final_url') or item.get('url')}")
            lines.append(f"OK: {item.get('ok')}")
            if item.get("title"):
                lines.append(f"Title: {item.get('title')}")
            if item.get("error"):
                lines.append(f"Error: {item.get('error')}")
            if item.get("text"):
                lines.append(f"Excerpt: {str(item.get('text'))[:650]}")
        return "\n".join(lines)
    return f"Source fetch blocked: {receipt.get('error') or 'no receipt'}"
