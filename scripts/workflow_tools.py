#!/usr/bin/env python3
"""Local, bounded checks for academic-writing-workflow. Python 3.10+, stdlib."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile

VERSION = "0.1.0"
MODES = {"question", "evidence", "design", "argument", "draft", "revise", "submit"}
ACCESS = {"metadata", "abstract", "partial", "full", "unavailable"}
SUPPORT = {"supporting", "contradicting", "mixed", "not_checked"}
KEY = re.compile(r"^[A-Za-z0-9_:.+\-]+$")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    """Atomic replace, used only for explicit output paths or new project records."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".awf-", delete=False) as handle:
            temp = Path(handle.name)
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temp.replace(path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def citation_keys(text):
    """Only explicit bracketed Pandoc keys; never pretends to parse APA prose."""
    text = re.sub(r"(?ms)^\s*(`{3,}|~{3,}).*?^\s*\1\s*$", "", text)
    text = re.sub(r"`+[^`\n]*`+", "", text)
    keys = []
    for match in re.finditer(r"(?<!\\)\[([^\]\n]+)\]", text):
        keys.extend(re.findall(r"(?<![\w@])@([A-Za-z0-9_:.+\-]+)", match.group(1)))
    return keys


def normalize_doi(value):
    value = value.strip()
    value = re.sub(r"(?i)^https?://(?:dx\.)?doi\.org/", "", value)
    return re.sub(r"(?i)^doi:\s*", "", value).casefold()


def new_project(target, title):
    target = Path(target)
    if target.exists():
        raise ValueError("Project target already exists; choose a new directory (no overwrite).")
    # No network, manuscript discovery, or existing project modification.
    template_dir = Path(__file__).resolve().parent.parent / "assets"
    templates = sorted(template_dir.glob("*.md"))
    if len(templates) != 5:
        raise ValueError("Expected five bundled Markdown templates; package may be incomplete.")
    contents = [(p.name, p.read_text(encoding="utf-8")) for p in templates]
    record = {
        "schema_version": 1, "skill_version": VERSION, "title": title,
        "mode": "question", "sources": [], "results": [], "claims": [],
        "decisions": [], "issues": [], "terms": [], "artifacts": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    target.mkdir(parents=True)
    for name, content in contents:
        (target / name).write_text(content, encoding="utf-8")
    write_json(target / "research.json", record)
    return {"operation": "init", "project": str(target.resolve()),
            "files_created": ["research.json"] + [name for name, _ in contents],
            "note": "Empty records are not completed research."}


def check_project(record_path, manuscript=None):
    record_path = Path(record_path).resolve()
    base = record_path.parent
    data = read_json(record_path)
    findings = []

    def add(code, where, detail):
        findings.append({"code": code, "where": where, "detail": detail})

    if not isinstance(data, dict):
        raise ValueError("research.json must contain an object.")
    if type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
        add("SCHEMA_VERSION", "schema_version", "Expected integer 1.")
    if data.get("mode") not in MODES:
        add("INVALID_MODE", "mode", "Unknown or missing mode.")
    tables = {}
    for name in ("sources", "results", "claims", "decisions", "issues", "terms", "artifacts"):
        rows = data.get(name)
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            add("INVALID_TABLE", name, "Expected array of objects; table not checked.")
            rows = []
        tables[name] = rows

    indexed = {}
    for name in ("sources", "results", "claims", "decisions", "issues"):
        index = {}
        for n, row in enumerate(tables[name]):
            identity = row.get("id")
            if not isinstance(identity, str) or not identity.strip():
                add("MISSING_ID", f"{name}[{n}]", "Nonempty string id required.")
                continue
            if identity in index:
                add("DUPLICATE_ID", name, identity)
            index[identity] = row
        indexed[name] = index

    seen = {}
    for n, source in enumerate(tables["sources"]):
        where = f"sources[{n}]"
        for field in ("id", "title", "key"):
            if not isinstance(source.get(field), str) or not source[field].strip():
                add("SOURCE_FIELD", where, f"Missing string {field}.")
        if isinstance(source.get("key"), str) and not KEY.fullmatch(source["key"]):
            add("INVALID_CITATION_KEY", where, "Use ASCII letters/digits/_:.+- without spaces.")
        if source.get("access") not in ACCESS:
            add("ACCESS_UNKNOWN", where, "Record actual reading scope.")
        if source.get("metadata_status") not in {"verified", "mismatch", "not_checked", "unavailable"}:
            add("METADATA_STATUS", where, "Unknown metadata status.")
        if source.get("metadata_status") != "verified":
            add("METADATA_UNRESOLVED", where, str(source.get("metadata_status")))
        if source.get("access") in {"metadata", "unavailable"}:
            add("SOURCE_CONTENT_UNREAD", where, "No assessed source content recorded.")
        if source.get("access") in {"abstract", "partial", "full"} and not source.get("read_locator"):
            add("READ_LOCATOR_MISSING", where, "Record sections/pages actually read.")
        for field in ("key", "doi", "arxiv"):
            value = source.get(field)
            if value is None or value == "":
                continue
            if not isinstance(value, str):
                add("IDENTIFIER_TYPE", where, f"{field} must be a string.")
                continue
            norm = normalize_doi(value) if field == "doi" else value.strip()
            token = (field, norm)
            if token in seen:
                add("DUPLICATE_IDENTIFIER", where, f"{field}={norm}; also {seen[token]}")
            seen[token] = where
        for flag in ("retraction_status", "version_status"):
            if not isinstance(source.get(flag), str) or source[flag] in {"", "not_checked", "unknown"}:
                add("SOURCE_STATUS_NOT_CHECKED", where, flag)

    for n, result in enumerate(tables["results"]):
        if not result.get("locator") or not result.get("text"):
            add("RESULT_INCOMPLETE", f"results[{n}]", "text and analysis/data locator required.")
        if result.get("synthetic") is True:
            add("SYNTHETIC_RESULT", f"results[{n}]", "Illustration only; not empirical evidence.")

    for n, claim in enumerate(tables["claims"]):
        where = f"claims[{n}]"
        if not claim.get("text") or claim.get("strength") not in {"descriptive", "associational", "causal"}:
            add("CLAIM_INCOMPLETE", where, "text and valid strength required.")
        evidence = claim.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            add("EVIDENCE_MISSING", where, "No registered evidence links.")
            continue
        for j, item in enumerate(evidence):
            if not isinstance(item, dict):
                add("EVIDENCE_FORMAT", where, f"evidence[{j}] must be an object.")
                continue
            kind = item.get("kind")
            bank = indexed.get({"source": "sources", "result": "results"}.get(kind, ""), {})
            identity = item.get("id")
            if not isinstance(identity, str) or identity not in bank:
                add("EVIDENCE_TARGET_MISSING", where, f"Unknown {kind}: {identity}.")
            if not item.get("locator"):
                add("EVIDENCE_LOCATOR_MISSING", where, f"evidence[{j}]")
            if item.get("relation") not in SUPPORT:
                add("EVIDENCE_RELATION", where, f"evidence[{j}] has unknown relation.")
            if item.get("relation") != "supporting":
                add("SUPPORT_UNRESOLVED", where, f"evidence[{j}]: {item.get('relation')}")
            if kind == "source" and isinstance(identity, str) and identity in bank:
                access = bank[identity].get("access")
                if access in {"metadata", "unavailable"}:
                    add("UNREAD_SUPPORT", where, f"{identity} has no read content.")
                elif access in {"abstract", "partial"}:
                    add("LIMITED_READING_SCOPE", where, f"{identity}: {access}; inspect claim boundary.")
        if claim.get("strength") == "causal" and not claim.get("causal_basis"):
            add("CAUSAL_BASIS_MISSING", where, "Document design/identification assumptions; not an automatic verdict.")

    for n, decision in enumerate(tables["decisions"]):
        if decision.get("origin") not in {"author", "ai_proposal"}:
            add("DECISION_ORIGIN", f"decisions[{n}]", "author or ai_proposal required.")
        if not decision.get("text") or not decision.get("provenance"):
            add("DECISION_PROVENANCE", f"decisions[{n}]", "text and actual decision provenance required.")

    for n, issue in enumerate(tables["issues"]):
        where = f"issues[{n}]"
        disposition, status = issue.get("disposition"), issue.get("status")
        if disposition not in {"accept", "partial", "decline", "pending"}:
            add("DISPOSITION_INVALID", where, "Unknown author disposition.")
        if status not in {"open", "resolved", "limitation"}:
            add("ISSUE_STATUS", where, "Unknown issue status.")
        if status != "resolved":
            add("ISSUE_UNRESOLVED", where, str(status))
        if disposition != "pending":
            decision_id = issue.get("decision_id")
            decision = indexed["decisions"].get(decision_id) if isinstance(decision_id, str) else None
            if not decision or decision.get("origin") != "author":
                add("AUTHOR_DECISION_MISSING", where, "Disposition has no linked author decision.")
        if status == "resolved" and (disposition == "pending" or not issue.get("response")):
            add("RESOLUTION_INCOMPLETE", where, "Resolved requires disposition and actual response.")
        if status == "resolved" and disposition in {"accept", "partial"} and not issue.get("change_locator"):
            add("CHANGE_LOCATOR_MISSING", where, "Point to actual change.")

    for n, artifact in enumerate(tables["artifacts"]):
        where = f"artifacts[{n}]"
        if not isinstance(artifact.get("path"), str) or not artifact["path"]:
            add("ARTIFACT_PATH", where, "Explicit path required.")
            continue
        path = Path(artifact["path"])
        path = path if path.is_absolute() else base / path
        if not path.is_file():
            add("ARTIFACT_MISSING", where, str(path))
        elif not isinstance(artifact.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"]):
            add("ARTIFACT_HASH_MISSING", where, "Record SHA-256 from original accepted bytes.")
        elif digest(path) != artifact["sha256"]:
            add("ARTIFACT_CHANGED", where, "Recorded bytes changed; inspect dependent work before reuse.")

    citation_scope = "not_checked"
    if manuscript is not None:
        text = Path(manuscript).read_text(encoding="utf-8-sig")
        cited = set(citation_keys(text))
        registered = {s["key"] for s in tables["sources"] if isinstance(s.get("key"), str)}
        citation_scope = "explicit_bracket_keys_only"
        if not cited:
            add("NO_EXPLICIT_KEYS", "manuscript", "No [@key] citations parsed; APA/Chinese/BibTeX not checked.")
        for key in sorted(cited - registered):
            add("CITED_KEY_UNREGISTERED", "manuscript", key)
        for key in sorted(registered - cited):
            add("REGISTERED_KEY_UNUSED", "manuscript", key)
        for n, term in enumerate(tables["terms"]):
            if not isinstance(term.get("canonical"), str) or not isinstance(term.get("variants"), list) or any(not isinstance(v, str) or not v for v in term.get("variants", [])):
                add("TERM_FORMAT", f"terms[{n}]", "canonical string and array of nonempty variant strings required.")
                continue
            for variant in term["variants"]:
                if variant == term["canonical"]:
                    continue
                # Chinese uses substring; ASCII words need word boundaries.
                pattern = re.escape(variant)
                if variant.isascii():
                    pattern = r"(?<!\w)" + pattern + r"(?!\w)"
                if re.search(pattern, text):
                    add("TERM_VARIANT", "manuscript", f"{variant} -> {term['canonical']} (context review)")

    return {"operation": "check", "status": "findings" if findings else "no_mechanical_findings",
            "coverage": {"registered": {k: len(v) for k, v in tables.items()},
                         "citation_parsing": citation_scope,
                         "semantic_claim_support": "not_checked_by_program",
                         "bibliographic_network_verification": "not_performed",
                         "unregistered_claim_completeness": "not_checked"},
            "findings": findings,
            "limitation": "Registration checks only; no scientific correctness or submission readiness certificate."}


def numeric_tokens(text):
    # Lexical inventory, including dates/reference numbers; no statistical interpretation.
    return Counter(re.findall(r"(?<![\w.])[-+−]?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?%?", text))


def compare_text(old_path, new_path, start_line=None, end_line=None):
    old = Path(old_path).read_text(encoding="utf-8-sig")
    new = Path(new_path).read_text(encoding="utf-8-sig")
    before, after = numeric_tokens(old), numeric_tokens(new)
    old_keys, new_keys = Counter(citation_keys(old)), Counter(citation_keys(new))
    scope = {"status": "not_checked"}
    if start_line is not None or end_line is not None:
        lines = old.splitlines(keepends=True)
        if start_line is None or end_line is None or not (1 <= start_line <= end_line <= len(lines)):
            raise ValueError("Provide both 1-based inclusive old-file line bounds within the old file.")
        prefix = "".join(lines[:start_line - 1])
        suffix = "".join(lines[end_line:])
        # Length check prevents overlapping prefix/suffix from hiding a deletion.
        preserved = len(new) >= len(prefix) + len(suffix) and new.startswith(prefix) and new.endswith(suffix)
        scope = {"status": "preserved" if preserved else "outside_scope_changed",
                 "old_start_line": start_line, "old_end_line": end_line,
                 "comparison": "decoded UTF-8 text; newline style normalized"}
    changed = before != after or old_keys != new_keys or scope["status"] == "outside_scope_changed"
    return {"operation": "diff", "status": "review_changes" if changed else "no_tracked_difference",
            "text_changed": old != new,
            "numbers_removed": dict(before - after), "numbers_added": dict(after - before),
            "citations_removed": dict(old_keys - new_keys), "citations_added": dict(new_keys - old_keys),
            "scope": scope,
            "limitation": "Lexical inventories only. Same numbers may move or attach to different claims; causality, meaning, quotes and APA citations require reading."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create a new directory, never overwrite.")
    init.add_argument("directory")
    init.add_argument("--title", required=True)
    check = commands.add_parser("check", help="Check explicitly registered local records.")
    check.add_argument("record")
    check.add_argument("--manuscript")
    check.add_argument("--output")
    diff = commands.add_parser("diff", help="Compare local UTF-8 manuscripts.")
    diff.add_argument("old")
    diff.add_argument("new")
    diff.add_argument("--start-line", type=int)
    diff.add_argument("--end-line", type=int)
    diff.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = new_project(args.directory, args.title)
        elif args.command == "check":
            result = check_project(args.record, args.manuscript)
        else:
            result = compare_text(args.old, args.new, args.start_line, args.end_line)
        output = getattr(args, "output", None)
        if output:
            protected = [getattr(args, f, None) for f in ("record", "manuscript", "old", "new")]
            if any(Path(p).resolve() == Path(output).resolve() for p in protected if p):
                raise ValueError("Report output must not overwrite an input file.")
            write_json(output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result["operation"] == "check" and result["findings"] else 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
