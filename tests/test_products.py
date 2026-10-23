"""
Integration test runner against a running ag-tools API: PII Vault, EvalForge, Guardrail, DocParse.
Usage:
    AG_API_KEY=ag_live_... AG_JWT=eyJ... python3 tests/test_products.py
    AG_API_KEY=ag_live_... AG_JWT=eyJ... python3 tests/test_products.py --local
    AG_API_KEY=ag_live_... AG_JWT=eyJ... python3 tests/test_products.py --product guardrail
AG_API_URL overrides the target (default https://ai-api.artifact-network.org).
"""

import json
import os
import sys
import time
import argparse
from pathlib import Path
from typing import Any

import requests

# ── Config ────────────────────────────────────────────────────────────────────

FIXTURES = Path(__file__).parent / "fixtures"
API_KEY  = os.environ.get("AG_API_KEY", "")
JWT      = os.environ.get("AG_JWT", "")

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--local",   action="store_true")
parser.add_argument("--product", default=None)
args, _ = parser.parse_known_args()

BASE         = "http://localhost:8100" if args.local else os.environ.get("AG_API_URL", "https://ai-api.artifact-network.org")
API_HEADERS  = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
JWT_HEADERS  = {"Authorization": f"Bearer {JWT}",     "Content-Type": "application/json"}

# ── Helpers ───────────────────────────────────────────────────────────────────

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

results: list[dict] = []


def post(path: str, body: dict, jwt: bool = False) -> requests.Response:
    h = JWT_HEADERS if jwt else API_HEADERS
    return requests.post(f"{BASE}{path}", headers=h, json=body, timeout=30)


def get(path: str, jwt: bool = False) -> requests.Response:
    h = JWT_HEADERS if jwt else API_HEADERS
    return requests.get(f"{BASE}{path}", headers=h, timeout=30)


def delete(path: str, jwt: bool = False) -> requests.Response:
    h = JWT_HEADERS if jwt else API_HEADERS
    return requests.delete(f"{BASE}{path}", headers=h, timeout=30)


def record(suite: str, case_id: str, passed: bool, detail: str = ""):
    icon = PASS if passed else FAIL
    print(f"  {icon} [{suite}][{case_id}] {detail}")
    results.append({"suite": suite, "id": case_id, "passed": passed, "detail": detail})


def check_eu_headers(resp: requests.Response, suite: str, case_id: str):
    for h in ("x-eu-ai-act-article", "x-eu-ai-act-control", "x-eu-ai-act-regulation"):
        present = h in resp.headers
        record(suite, f"{case_id}_hdr_{h.split('-')[-1]}", present,
               f"header {h} {'present' if present else 'MISSING'}")


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


# ── PII Vault ─────────────────────────────────────────────────────────────────

def run_pii():
    print("\n=== PII Vault ===")
    data = load("pii_samples.json")
    stored_token: str = ""

    for case in data["tokenize_cases"]:
        cid = case["id"]
        r = post("/v1/pii-vault/tokenize", {"text": case["text"]})
        ok = r.status_code == 200
        if ok:
            # Response: {text, entities: [{original, replacement, entity_type, start, end}], stored}
            entities = r.json().get("entities", [])
            detected = {e["entity_type"] for e in entities}
            expected = set(case["expected_entities"])
            if expected:
                match = expected.issubset(detected)
                record("pii", cid, match, f"expected {expected} detected {detected}")
            else:
                match = len(entities) == 0
                record("pii", cid, match, f"expected no PII, got {len(entities)} entities")
            check_eu_headers(r, "pii", cid)
        else:
            record("pii", cid, False, f"HTTP {r.status_code}: {r.text[:120]}")

    for case in data["detokenize_cases"]:
        cid = case["id"]
        r1 = post("/v1/pii-vault/tokenize", {"text": case["text"]})
        if r1.status_code != 200:
            record("pii", cid, False, f"tokenize step failed HTTP {r1.status_code}")
            continue
        entities = r1.json().get("entities", [])
        if not entities:
            record("pii", cid, False, "tokenize returned no entities")
            continue
        anon_text = r1.json().get("text", "")
        # replacements are the fake values substituted into the text
        replacements = [e["replacement"] for e in entities]
        r2 = post("/v1/pii-vault/detokenize", {"text": anon_text, "tokens": replacements})
        ok = r2.status_code == 200
        if ok:
            restored = r2.json().get("text", "")
            # Check at least one original value is restored
            originals = [e["original"] for e in entities]
            match = any(orig in restored for orig in originals)
            record("pii", cid, match, "round-trip OK" if match else f"got: {restored[:80]}")
        else:
            record("pii", cid, False, f"detokenize HTTP {r2.status_code}: {r2.text[:120]}")

    for case in data["tokens_store_cases"]:
        cid = case["id"]
        import secrets as _secrets
        test_token = f"tok_{_secrets.token_urlsafe(8)}"
        r = post("/v1/pii-vault/tokens", {"entries": [{
            "token": test_token,
            "value": case["value"],
            "entity_type": case["entity_type"],
            "subject_id": case["subject_id"],
        }]})
        ok = r.status_code == 200
        if ok and not stored_token:
            stored_token = test_token
        record("pii", cid, ok,
               f"HTTP {r.status_code} stored={r.json().get('stored')}" if ok else f"HTTP {r.status_code}: {r.text[:80]}")

    if stored_token:
        r = post("/v1/pii-vault/tokens/lookup", {"tokens": [stored_token]})
        ok = r.status_code == 200
        if ok:
            values = r.json().get("values", {})
            record("pii", "token_lookup", stored_token in values,
                   f"values={values}")
        else:
            record("pii", "token_lookup", False, f"HTTP {r.status_code}: {r.text[:80]}")

    for case in data["subject_dsar_cases"]:
        cid = case["id"]
        if "delete" in cid.lower():
            r = delete(f"/v1/pii-vault/subjects/{case['subject_id']}")
            record("pii", cid, r.status_code in (200, 204, 404), f"DELETE HTTP {r.status_code}")
        else:
            r = get(f"/v1/pii-vault/subjects/{case['subject_id']}")
            record("pii", cid, r.status_code in (200, 404), f"GET HTTP {r.status_code}")

    r = get("/v1/pii-vault/stats")
    record("pii", "stats_global", r.status_code == 200, f"HTTP {r.status_code}")
    # me/stats requires JWT
    r = get("/v1/pii-vault/me/stats", jwt=True)
    record("pii", "stats_me", r.status_code == 200, f"HTTP {r.status_code}")

    for case in data["edge_cases"]:
        cid = case["id"]
        r = post("/v1/pii-vault/tokenize", {"text": case["text"]})
        # E01/E02 empty text → 422 is correct validation behavior
        if case["id"] in ("E01_empty_text", "E02_whitespace_only"):
            record("pii", cid, r.status_code == 422, f"HTTP {r.status_code} (422 expected — empty input rejected)")
        elif r.status_code == 200:
            entities = r.json().get("entities", [])
            has_pii = len(case["expected_entities"]) > 0
            match = (has_pii and len(entities) > 0) or (not has_pii and len(entities) == 0)
            record("pii", cid, match, f"entities={len(entities)} expected_entities={case['expected_entities']}")
        else:
            record("pii", cid, False, f"HTTP {r.status_code}: {r.text[:80]}")


# ── EvalForge ─────────────────────────────────────────────────────────────────

def run_eval():
    print("\n=== EvalForge ===")
    data = load("eval_cases.json")

    def score_case(cid: str, scorer: str, cases: list[dict],
                   expected_range: tuple[float, float], extra: dict = {}):
        payload = {"scorer": scorer, "cases": cases, **extra}
        r = post("/v1/eval/score", payload)
        ok = r.status_code == 200
        if ok:
            body = r.json()
            score = body.get("mean_score", -1)
            lo, hi = expected_range
            in_range = lo <= score <= hi
            record("eval", cid, in_range,
                   f"mean_score={score:.3f} expected=[{lo},{hi}]" + ("" if in_range else " OUT OF RANGE"))
            check_eu_headers(r, "eval", cid)
        else:
            record("eval", cid, False, f"HTTP {r.status_code}: {r.text[:150]}")

    for case in data["exact_match_cases"]:
        score_case(case["id"], "exact_match",
                   [{"input": case["input"], "output": case["output"], "expected": case["expected"]}],
                   tuple(case["expected_score_range"]))

    for case in data["rouge_l_cases"]:
        score_case(case["id"], "rouge_l",
                   [{"input": case["input"], "output": case["output"], "expected": case["expected"]}],
                   tuple(case["expected_score_range"]))

    for case in data["regex_cases"]:
        score_case(case["id"], "regex",
                   [{"input": case["input"], "output": case["output"], "expected": case["expected"]}],
                   tuple(case["expected_score_range"]),
                   extra={"pattern": case["expected"]})

    for case in data["llm_judge_cases"]:
        score_case(case["id"], "llm_judge",
                   [{"input": case["input"], "output": case["output"], "expected": case["expected"]}],
                   tuple(case["expected_score_range"]),
                   extra={"criteria": case["criteria"]})

    # Multi-scorer: call each scorer individually and report all
    case = data["multi_scorer_cases"][0]
    all_pass = True
    for scorer in case["scorers"]:
        extra = {}
        if scorer == "regex":
            extra["pattern"] = case["regex_pattern"]
        if scorer == "llm_judge":
            extra["criteria"] = case["criteria"]
        r = post("/v1/eval/score", {
            "scorer": scorer,
            "cases": [{"input": case["input"], "output": case["output"], "expected": case["expected"]}],
            **extra,
        })
        ok = r.status_code == 200
        if not ok:
            all_pass = False
        record("eval", f"{case['id']}_{scorer}", ok,
               f"mean_score={r.json().get('mean_score','?')}" if ok else f"HTTP {r.status_code}")
    record("eval", case["id"], all_pass, "all scorers called successfully" if all_pass else "some scorers failed")


# ── Guardrail ─────────────────────────────────────────────────────────────────

def run_guardrail():
    print("\n=== Guardrail ===")
    data = load("guardrail_samples.json")

    def check_case(cid: str, text: str, direction: str, expect_blocked: bool):
        r = post("/v1/guardrail/check", {"text": text, "direction": direction})
        ok = r.status_code == 200
        if not ok:
            record("guardrail", cid, False, f"HTTP {r.status_code}: {r.text[:120]}")
            return
        body = r.json()
        # Response shape: {passed, blocked_by, results: [{detector, passed, score, reason}]}
        is_blocked = not body.get("passed", True)
        passed_test = is_blocked == expect_blocked
        blocked_by  = body.get("blocked_by")
        record("guardrail", cid, passed_test,
               f"passed={body.get('passed')} blocked_by={blocked_by} expect_blocked={expect_blocked}")
        check_eu_headers(r, "guardrail", cid)

    for case in data["prompt_injection_cases"]:
        check_case(case["id"], case["text"], case["direction"], bool(case["expected_triggered"]))

    for case in data["jailbreak_cases"]:
        check_case(case["id"], case["text"], case["direction"], bool(case["expected_triggered"]))

    for case in data["harmful_content_cases"]:
        check_case(case["id"], case["text"], case["direction"], bool(case["expected_triggered"]))

    for case in data["pii_output_cases"]:
        check_case(case["id"], case["text"], case["direction"], bool(case["expected_triggered"]))

    for case in data["safe_cases"]:
        check_case(case["id"], case["text"], case["direction"], bool(case["expected_triggered"]))

    # Policy CRUD
    created_policy_ids: list[str] = []
    for case in data["policy_cases"]:
        cid = case["id"]
        if "create" in cid:
            p = case["policy"]
            # PolicyCreate: {name, rules: [{type, pattern, action}], is_active}
            payload = {
                "name": p["name"],
                "is_active": True,
                "rules": [{
                    "type": p.get("rule_type", "keyword"),
                    "pattern": p["pattern"],
                    "action": p.get("action", "block"),
                }]
            }
            r = post("/v1/guardrail/policies", payload)
            ok = r.status_code in (200, 201)
            if ok:
                pid = r.json().get("id", "")
                created_policy_ids.append(pid)
                record("guardrail", cid, True, f"created id={pid[:8]}")
            else:
                record("guardrail", cid, False, f"HTTP {r.status_code}: {r.text[:120]}")
        elif "test" in cid:
            expect_blocked = bool(case.get("expected_triggered"))
            check_case(cid, case["text"], case["direction"], expect_blocked)

    r = get("/v1/guardrail/policies")
    record("guardrail", "policies_list", r.status_code == 200, f"HTTP {r.status_code}")

    for pid in created_policy_ids:
        r = delete(f"/v1/guardrail/policies/{pid}")
        record("guardrail", f"policy_delete_{pid[:8]}", r.status_code in (200, 204), f"HTTP {r.status_code}")

    # me/audit requires JWT
    r = get("/v1/guardrail/me/audit", jwt=True)
    record("guardrail", "audit_me", r.status_code == 200, f"HTTP {r.status_code}")

    r = get("/v1/guardrail/stats")
    record("guardrail", "stats", r.status_code == 200, f"HTTP {r.status_code}")

    # LLM classifier
    for case in data["llm_classifier_cases"]:
        r = post("/v1/guardrail/check",
                 {"text": case["text"], "direction": case["direction"],
                  "detectors": ["llm_classifier"]})
        ok = r.status_code == 200
        if ok:
            is_blocked = not r.json().get("passed", True)
            passed_test = is_blocked == case["expected_flagged"]
            record("guardrail", case["id"], passed_test,
                   f"blocked={is_blocked} expected={case['expected_flagged']}")
        else:
            record("guardrail", case["id"], False, f"HTTP {r.status_code}: {r.text[:120]}")


# ── DocParse ──────────────────────────────────────────────────────────────────

def run_docparse():
    print("\n=== DocParse ===")
    data = load("doc_custom_fields.json")

    # Built-in schema extractions (API key auth)
    for case in data["builtin_schema_overrides"]:
        cid = case["id"]
        text = (FIXTURES / case["fixture_file"]).read_text()
        r = post("/v1/doc/extract", {"text": text, "schema_name": case["schema"]})
        ok = r.status_code == 200
        if ok:
            body    = r.json()
            # Response: {schema_name, fields: {name: {value, confidence}}}
            extracted = body.get("fields", {})
            present = [f for f in case["expected_field_presence"] if f in extracted and extracted[f].get("value")]
            missing = [f for f in case["expected_field_presence"] if f not in extracted or not extracted[f].get("value")]
            passed  = len(missing) == 0
            record("docparse", cid, passed,
                   f"present={present}" + (f" MISSING={missing}" if missing else ""))
            check_eu_headers(r, "docparse", cid)
        else:
            record("docparse", cid, False, f"HTTP {r.status_code}: {r.text[:150]}")

    # Custom schema CRUD + extraction (schema CRUD requires JWT)
    created_schema_ids: list[str] = []
    for case in data["custom_schema_cases"]:
        cid = case["id"]
        schema_def = case["schema"]
        # SchemaCreate: {name, description, fields: [{name, description, type, required}]}
        create_payload = {
            "name": schema_def["name"],
            "fields": [
                {"name": f["name"], "description": f["description"],
                 "type": f.get("type", "string"), "required": f.get("required", False)}
                for f in schema_def["fields"]
            ]
        }
        r = post("/v1/doc/schemas", create_payload, jwt=True)
        if r.status_code not in (200, 201):
            record("docparse", f"{cid}_schema_create", False,
                   f"HTTP {r.status_code}: {r.text[:120]}")
            continue
        sid = r.json().get("id", "")
        created_schema_ids.append(sid)
        record("docparse", f"{cid}_schema_create", True, f"id={sid[:8]}")

        # Extract using the custom schema fields directly (custom schemas can't be referenced by name in /extract)
        r2 = post("/v1/doc/extract", {
            "text": case["text"],
            "fields": [
                {"name": f["name"], "description": f["description"],
                 "type": f.get("type", "string"), "required": f.get("required", False)}
                for f in schema_def["fields"]
            ],
        })
        ok  = r2.status_code == 200
        if ok:
            extracted = r2.json().get("fields", {})
            expected  = case["expected_extractions"]
            hits   = [k for k in expected if k in extracted and extracted[k].get("value") is not None]
            misses = [k for k in expected if k not in extracted or extracted[k].get("value") is None]
            passed = len(misses) == 0
            record("docparse", f"{cid}_extract", passed,
                   f"matched {len(hits)}/{len(expected)} fields" + (f" MISSING={misses}" if misses else ""))
        else:
            record("docparse", f"{cid}_extract", False, f"HTTP {r2.status_code}: {r2.text[:120]}")

    # Async job — invoice doc
    invoice_text = (FIXTURES / "doc_invoice.txt").read_text()
    r = post("/v1/doc/jobs", {"text": invoice_text, "schema_name": "invoice"})
    if r.status_code == 202:
        body   = r.json()
        job_id = body.get("job_id") or body.get("id", "")
        record("docparse", "async_job_create", True, f"job_id={job_id[:16]}")
        deadline = time.time() + 60
        status_val = "pending"
        while time.time() < deadline:
            time.sleep(2)
            rp = get(f"/v1/doc/jobs/{job_id}")
            if rp.status_code == 200:
                status_val = rp.json().get("status", "pending")
                if status_val in ("completed", "done", "failed", "error"):
                    break
        record("docparse", "async_job_complete", status_val in ("completed", "done"),
               f"final status={status_val}")
    else:
        record("docparse", "async_job_create", False, f"HTTP {r.status_code}: {r.text[:120]}")

    r = get("/v1/doc/jobs")
    record("docparse", "jobs_list", r.status_code == 200, f"HTTP {r.status_code}")

    # Schema list + info require JWT
    r = get("/v1/doc/schemas", jwt=True)
    record("docparse", "schemas_list", r.status_code == 200, f"HTTP {r.status_code}")

    r = get("/v1/doc/schemas-info", jwt=True)
    record("docparse", "schemas_info", r.status_code == 200, f"HTTP {r.status_code}")

    for sid in created_schema_ids:
        r = delete(f"/v1/doc/schemas/{sid}", jwt=True)
        record("docparse", f"schema_delete_{sid[:8]}", r.status_code in (200, 204),
               f"HTTP {r.status_code}")


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary():
    total  = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    print(f"\n{'='*55}")
    print(f"  Results: {passed}/{total} passed", end="")
    if failed:
        print(f"  ({failed} FAILED)", end="")
    print()

    if failed:
        print("\nFailed cases:")
        for r in results:
            if not r["passed"]:
                print(f"  [{r['suite']}][{r['id']}] {r['detail']}")

    by_suite: dict[str, dict] = {}
    for r in results:
        s = r["suite"]
        by_suite.setdefault(s, {"pass": 0, "fail": 0})
        by_suite[s]["pass" if r["passed"] else "fail"] += 1

    print("\nBy product:")
    for suite, counts in by_suite.items():
        t = counts["pass"] + counts["fail"]
        print(f"  {suite:12s}  {counts['pass']}/{t}")
    print('='*55)
    return failed == 0


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: set AG_API_KEY env var")
        sys.exit(1)
    if not JWT:
        print("WARNING: AG_JWT not set: JWT-only endpoints (schema CRUD, audit, schemas-info) will fail")

    print(f"Target: {BASE}")
    print(f"Key:    {API_KEY[:18]}...")

    suites = {
        "pii":       run_pii,
        "eval":      run_eval,
        "guardrail": run_guardrail,
        "docparse":  run_docparse,
    }

    if args.product:
        if args.product not in suites:
            print(f"Unknown product '{args.product}'. Choose from: {list(suites)}")
            sys.exit(1)
        suites[args.product]()
    else:
        for fn in suites.values():
            fn()

    ok = print_summary()
    sys.exit(0 if ok else 1)
