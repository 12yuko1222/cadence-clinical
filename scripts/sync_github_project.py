#!/usr/bin/env python3
"""
Cadence Clinical — Automated GitHub Project & Issue Sync Tool

Automates GitHub Project 17 ('Cadence-Clinical') synchronization, body formatting with native GitHub tasklists,
dynamic issue unblocking, label synchronization, priority classification, and developer readiness mapping.

Usage:
    python3 scripts/sync_github_project.py
    pnpm project:sync
"""

import json
import re
import subprocess
import sys
import time

PROJECT_NUMBER = 17
OWNER = "fderuiter"
PROJECT_ID = "PVT_kwHOB5yjmM4Beuvn"

# Field IDs
STATUS_FIELD_ID = "PVTSSF_lAHOB5yjmM4BeuvnzhZGxXA"
PRIORITY_FIELD_ID = "PVTSSF_lAHOB5yjmM4BeuvnzhZGxaM"
SIZE_FIELD_ID = "PVTSSF_lAHOB5yjmM4BeuvnzhZGxaQ"

# Option IDs
STATUS_OPTIONS = {
    "Backlog": "f75ad846",
    "Ready": "e18bf179",
    "In progress": "47fc9ee4",
    "In review": "aba860b9",
    "Done": "98236657",
}

PRIORITY_OPTIONS = {"P0": "79628723", "P1": "0a877460", "P2": "da944a9c"}

SIZE_OPTIONS = {
    "XS": "911790be",
    "S": "b277fb01",
    "M": "86db8eb3",
    "L": "853c8207",
    "XL": "2d0801e2",
}


def run_cmd(args):
    res = subprocess.run(args, capture_output=True, text=True)
    if res.returncode != 0:
        print(
            f"Command failed: {' '.join(args)}\nError: {res.stderr.strip()}",
            file=sys.stderr,
        )
        return None
    return res.stdout


def assign_work_stream(i):
    title = i["title"].lower()
    body = (i.get("body") or "").lower()
    labels = [lbl["name"].lower() for lbl in i.get("labels", [])]

    if any(
        k in title or k in body for k in ["etmf", "isf", "document", "archiving", "tmf"]
    ):
        return (
            "Stream 1: eTMF & Regulated Document Management",
            "Document Management & Archiving",
        )
    elif any(
        k in title or k in body
        for k in ["rtsm", "irt", "dispensation", "randomization", "supply", "blinded"]
    ):
        return "Stream 2: RTSM & IP Supply Chain", "RTSM / IRT v1.0"
    elif any(
        k in title or k in body
        for k in ["ecrf", "soa", "mdr", "protocol", "designer", "form", "crf"]
    ):
        return "Stream 3: Study Designer, eCRF & SoA", "Ultimate CRF Builder"
    elif any(
        k in title or k in body
        for k in ["ecoa", "epro", "subject portal", "patient", "econsent"]
    ):
        return (
            "Stream 4: eCOA, ePRO & Subject Portal",
            "Native eCOA/ePRO Subject Portal v1.6.0",
        )
    elif "scope: frontend" in labels or any(
        k in title or k in body for k in ["spa", "vue", "ui", "widget", "component"]
    ):
        return "Stream 5: Frontend Vue 3 SPA", "Frontend SPA Completion"
    elif any(
        k in title or k in body
        for k in [
            "rbac",
            "security",
            "keycloak",
            "audit",
            "aes",
            "crypto",
            "auth",
            "ticket",
        ]
    ):
        return (
            "Stream 6: Platform Security, RBAC & Audit Ledger",
            "Compliance & Security Controls",
        )
    elif any(
        k in title or k in body
        for k in ["sdtm", "adam", "dataset", "export", "biostat", "cdisc"]
    ):
        return (
            "Stream 7: Biostatistics & Dataset Exports",
            "Biostatistical Export Pipeline v1.7.0 Completion",
        )
    elif any(
        k in title or k in body
        for k in ["sdv", "lab", "monitoring", "site", "query", "sae", "reconciliation"]
    ):
        return "Stream 8: Clinical Operations, SDV & Lab Ranges", "SDV/TSDV Hardening"
    else:
        return (
            "Stream 6: Platform Security, RBAC & Audit Ledger",
            "Compliance & Security Controls",
        )


def clean_and_format_body(i, epics, issue_by_num):
    num = i["number"]
    body = (i.get("body") or "").strip()
    is_epic = num in epics

    lines = body.split("\n")
    cleaned_lines = []

    for line in lines:
        line_str = line.strip()
        if any(
            k in line_str
            for k in [
                "BLOCKED",
                "READY FOR DEV",
                "PARENT EPIC",
                "Developer Readiness",
                "Work Stream",
                "Requirements Traceability",
                "Target Modules",
                "🔴",
                "🟢",
                "🔵",
            ]
        ):
            continue
        cleaned_lines.append(line)

    body_core = "\n".join(cleaned_lines).strip()
    body_core = re.sub(r"^(---|\s+|\n)+", "", body_core).strip()

    # Strip any trailing DoD or tasklist headers that were previously appended
    body_core = re.sub(
        r"## 📋 Definition of Done \(DoD\) Checklist.*",
        "",
        body_core,
        flags=re.DOTALL,
    ).strip()
    body_core = re.sub(
        r"### 🔗 Prerequisites / Dependencies.*",
        "",
        body_core,
        flags=re.DOTALL,
    ).strip()
    body_core = re.sub(
        r"### 📋 Child Issues / Sub-Tasks.*",
        "",
        body_core,
        flags=re.DOTALL,
    ).strip()
    body_core = re.sub(r"\n---\n*$", "", body_core).strip()

    # Extract references
    all_refs = [
        int(r)
        for r in re.findall(r"#(\d+)", body)
        if int(r) in issue_by_num and int(r) != num
    ]

    # Leaf prerequisites are non-epic references
    prereqs = sorted(list(set([r for r in all_refs if r not in epics])))
    # Parent child tasks are all references
    children = sorted(list(set(all_refs)))

    stream_name, default_ms = assign_work_stream(i)
    current_ms = i["milestone"]["title"] if i.get("milestone") else default_ms

    req_ids = sorted(list(set(re.findall(r"(PRD-[A-Z0-9-]+|Trace-\d+|ADR-\d+)", body))))
    req_str = (
        ", ".join(req_ids) if req_ids else "PRD-SYS-001 (Core Platform Compliance)"
    )

    file_targets = sorted(
        list(
            set(
                re.findall(
                    r"`(apps/[^`,\s]+|packages/[^`,\s]+|docs/[^`,\s]+|tests/[^`,\s]+)`",
                    body,
                )
            )
        )
    )
    files_str = ", ".join(file_targets[:4]) if file_targets else "See issue body specs"
    if len(file_targets) > 4:
        files_str += f" (+{len(file_targets) - 4} more)"

    metadata_block = f"""| **Work Stream**: `{stream_name}` | **Milestone**: `{current_ms}`

> 🔒 **Requirements Traceability**: `{req_str}` | GxP 21 CFR Part 11 Regulated
> 📁 **Target Modules / Files**: `{files_str}`"""

    tasklist_section = ""
    if is_epic and children:
        items = []
        for c in children:
            c_issue = issue_by_num.get(c, {})
            title = c_issue.get("title", "")
            state = c_issue.get("state", "OPEN")
            box = "[x]" if state == "CLOSED" else "[ ]"
            items.append(f"- {box} #{c} — {title}")
        tasklist_section = "\n\n### 📋 Child Issues / Sub-Tasks\n" + "\n".join(items)
    elif not is_epic and prereqs:
        items = []
        for p in prereqs:
            p_issue = issue_by_num.get(p, {})
            title = p_issue.get("title", "")
            state = p_issue.get("state", "OPEN")
            box = "[x]" if state == "CLOSED" else "[ ]"
            items.append(f"- {box} #{p} — {title}")
        tasklist_section = "\n\n### 🔗 Prerequisites / Dependencies\n" + "\n".join(
            items
        )

    dod_block = """## 📋 Definition of Done (DoD) Checklist
- [ ] Implementation complete across target file paths.
- [ ] Unit & integration tests added/updated in `tests/` (`uv run pytest`).
- [ ] Code formatted and typed cleanly (`uv run ruff check .`).
- [ ] GxP audit fields preserved/updated (`created_by`, `reason_for_change`, versioning) if models modified.
- [ ] Traceability docs or ADR updated if architectural/contract changes introduced."""

    formatted_body = f"""{metadata_block}

---

{body_core}{tasklist_section}

---

{dod_block}"""

    was_changed = body.strip() != formatted_body.strip()
    return formatted_body, was_changed, prereqs


def main():
    print(
        "=== Cadence Clinical — Standardized Project & Dynamic Issue Sync ===",
        flush=True,
    )

    # 1. Fetch all repo issues
    print("1. Fetching all repository issues...", flush=True)
    raw_issues = run_cmd(
        [
            "gh",
            "issue",
            "list",
            "--limit",
            "1000",
            "--state",
            "all",
            "--json",
            "number,title,state,labels,milestone,body,url",
        ]
    )
    if not raw_issues:
        print("Failed to fetch repository issues.", file=sys.stderr)
        sys.exit(1)

    issues = json.loads(raw_issues)
    issue_by_num = {i["number"]: i for i in issues}

    epics = set()
    for i in issues:
        labels = [lbl["name"] for lbl in i.get("labels", [])]
        if "Parent" in labels or i["title"].startswith("EPIC:"):
            epics.add(i["number"])

    # 2. Standardize issue bodies and update dynamic blocked status
    print(
        "2. Standardizing issue descriptions & updating dynamic blocked states...",
        flush=True,
    )
    open_issues = [i for i in issues if i["state"] == "OPEN"]
    formatted_count = 0
    unblocked_count = 0
    blocked_count = 0
    tmp_file = "/tmp/cadence_issue_body.md"

    open_prereqs_by_num = {}

    for i in open_issues:
        num = i["number"]
        new_body, was_changed, prereqs = clean_and_format_body(i, epics, issue_by_num)

        open_prereqs = [
            p for p in prereqs if issue_by_num.get(p, {}).get("state") == "OPEN"
        ]
        open_prereqs_by_num[num] = open_prereqs

        current_labels = [lbl["name"] for lbl in i.get("labels", [])]
        has_blocked_label = "blocked" in current_labels

        if open_prereqs and not has_blocked_label:
            run_cmd(["gh", "issue", "edit", str(num), "--add-label", "blocked"])
            blocked_count += 1
        elif not open_prereqs and has_blocked_label:
            run_cmd(["gh", "issue", "edit", str(num), "--remove-label", "blocked"])
            unblocked_count += 1

        if was_changed:
            with open(tmp_file, "w") as f:
                f.write(new_body)
            run_cmd(["gh", "issue", "edit", str(num), "--body-file", tmp_file])
            formatted_count += 1
            time.sleep(0.05)

    print(
        f"Reformatted {formatted_count} issues. Dynamically unblocked {unblocked_count} issues. Added blocked label to {blocked_count} issues.",
        flush=True,
    )

    # 3. Fetch project items
    print("3. Fetching items from GitHub Project 17...", flush=True)
    raw_project = run_cmd(
        [
            "gh",
            "project",
            "item-list",
            str(PROJECT_NUMBER),
            "--owner",
            OWNER,
            "--format",
            "json",
            "--limit",
            "1000",
        ]
    )
    if not raw_project:
        print(
            "Warning: Could not fetch GitHub Project items.",
            file=sys.stderr,
        )
        return

    project_data = json.loads(raw_project)
    items = project_data.get("items", [])

    item_by_issue_num = {}
    for item in items:
        if item.get("content", {}).get("type") == "Issue":
            num = item["content"].get("number")
            if num:
                item_by_issue_num[num] = item

    # 4. Add missing issues to Project
    missing_issues = [i for i in open_issues if i["number"] not in item_by_issue_num]
    if missing_issues:
        print(
            f"Adding {len(missing_issues)} missing issues to Project Board...",
            flush=True,
        )
        for i in missing_issues:
            run_cmd(
                [
                    "gh",
                    "project",
                    "item-add",
                    str(PROJECT_NUMBER),
                    "--owner",
                    OWNER,
                    "--url",
                    i["url"],
                ]
            )
            time.sleep(0.05)
        # Refresh items
        raw_project = run_cmd(
            [
                "gh",
                "project",
                "item-list",
                str(PROJECT_NUMBER),
                "--owner",
                OWNER,
                "--format",
                "json",
                "--limit",
                "1000",
            ]
        )
        project_data = json.loads(raw_project)
        items = project_data.get("items", [])
        for item in items:
            if item.get("content", {}).get("type") == "Issue":
                num = item["content"].get("number")
                if num:
                    item_by_issue_num[num] = item

    # 5. Sync Project Board fields
    print(
        f"4. Synchronizing fields for {len(item_by_issue_num)} project items...",
        flush=True,
    )
    for idx, (num, item) in enumerate(item_by_issue_num.items(), 1):
        item_id = item["id"]
        issue = issue_by_num.get(num)
        if not issue:
            continue

        labels = [lbl["name"].lower() for lbl in issue.get("labels", [])]
        body = issue.get("body") or ""
        state = issue["state"]

        open_prereqs = open_prereqs_by_num.get(num, [])

        # Status
        if state == "CLOSED":
            target_status = "Done"
        elif "jules" in labels:
            target_status = "In progress"
        elif open_prereqs or num in epics:
            target_status = "Backlog"
        else:
            target_status = "Ready"

        # Priority
        if "priority: high" in labels or "p0" in labels or "critical" in labels:
            target_priority = "P0"
        elif "priority: medium" in labels or "p1" in labels:
            target_priority = "P1"
        else:
            target_priority = "P2"

        # Size
        if num in epics:
            target_size = "XL"
        elif (
            len(re.findall(r"`(apps/[^`]+|packages/[^`]+)`", body)) >= 5
            or "architecture" in labels
        ):
            target_size = "L"
        elif len(re.findall(r"`(apps/[^`]+|packages/[^`]+)`", body)) >= 2:
            target_size = "M"
        elif "scope: frontend" in labels or "type: bug" in labels:
            target_size = "S"
        else:
            target_size = "M"

        if item.get("status") != target_status:
            run_cmd(
                [
                    "gh",
                    "project",
                    "item-edit",
                    "--id",
                    item_id,
                    "--project-id",
                    PROJECT_ID,
                    "--field-id",
                    STATUS_FIELD_ID,
                    "--single-select-option-id",
                    STATUS_OPTIONS[target_status],
                ]
            )
        if item.get("priority") != target_priority:
            run_cmd(
                [
                    "gh",
                    "project",
                    "item-edit",
                    "--id",
                    item_id,
                    "--project-id",
                    PROJECT_ID,
                    "--field-id",
                    PRIORITY_FIELD_ID,
                    "--single-select-option-id",
                    PRIORITY_OPTIONS[target_priority],
                ]
            )
        if item.get("size") != target_size:
            run_cmd(
                [
                    "gh",
                    "project",
                    "item-edit",
                    "--id",
                    item_id,
                    "--project-id",
                    PROJECT_ID,
                    "--field-id",
                    SIZE_FIELD_ID,
                    "--single-select-option-id",
                    SIZE_OPTIONS[target_size],
                ]
            )

        time.sleep(0.02)

    print(
        "✅ Standardized Project Board & Dynamic Issue Automation Sync Complete!",
        flush=True,
    )


if __name__ == "__main__":
    main()
