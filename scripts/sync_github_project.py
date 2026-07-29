#!/usr/bin/env python3
"""
Cadence Clinical — GitHub Project & Issue Sync Tool

Automates GitHub Project 17 ('Cadence-Clinical') synchronization, board status routing,
priority classification, size estimation, and developer readiness mapping.

Usage:
    python3 scripts/sync_github_project.py
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
    "Done": "98236657"
}

PRIORITY_OPTIONS = {
    "P0": "79628723",
    "P1": "0a877460",
    "P2": "da944a9c"
}

SIZE_OPTIONS = {
    "XS": "911790be",
    "S": "b277fb01",
    "M": "86db8eb3",
    "L": "853c8207",
    "XL": "2d0801e2"
}

def run_cmd(args):
    res = subprocess.run(args, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Command failed: {' '.join(args)}\nError: {res.stderr.strip()}", file=sys.stderr)
        return None
    return res.stdout

def main():
    print("=== Cadence Clinical — GitHub Project Sync ===", flush=True)
    
    # 1. Fetch all repo issues
    print("1. Fetching all repository issues...", flush=True)
    raw_issues = run_cmd([
        "gh", "issue", "list", "--limit", "1000", "--state", "all",
        "--json", "number,title,state,labels,milestone,body,url"
    ])
    if not raw_issues:
        print("Failed to fetch repository issues.", file=sys.stderr)
        sys.exit(1)
        
    issues = json.loads(raw_issues)
    issue_by_num = {i['number']: i for i in issues}
    print(f"Loaded {len(issues)} total issues ({sum(1 for i in issues if i['state']=='OPEN')} open, {sum(1 for i in issues if i['state']=='CLOSED')} closed).", flush=True)

    # 2. Fetch project items
    print("2. Fetching items from GitHub Project 17...", flush=True)
    raw_project = run_cmd([
        "gh", "project", "item-list", str(PROJECT_NUMBER), "--owner", OWNER, "--format", "json", "--limit", "1000"
    ])
    if not raw_project:
        print("Failed to fetch project items.", file=sys.stderr)
        sys.exit(1)
        
    project_data = json.loads(raw_project)
    items = project_data.get('items', [])
    print(f"Loaded {len(items)} items currently on Project Board.", flush=True)
    
    # Map project item ID by issue number
    item_by_issue_num = {}
    for item in items:
        if item.get('content', {}).get('type') == 'Issue':
            num = item['content'].get('number')
            if num:
                item_by_issue_num[num] = item

    # 3. Add missing open issues to Project
    missing_issues = [i for i in issues if i['state'] == 'OPEN' and i['number'] not in item_by_issue_num]
    if missing_issues:
        print(f"Adding {len(missing_issues)} missing open issues to Project Board...", flush=True)
        for idx, i in enumerate(missing_issues, 1):
            run_cmd(["gh", "project", "item-add", str(PROJECT_NUMBER), "--owner", OWNER, "--url", i['url']])
            time.sleep(0.05)
        # Refresh item list
        raw_project = run_cmd([
            "gh", "project", "item-list", str(PROJECT_NUMBER), "--owner", OWNER, "--format", "json", "--limit", "1000"
        ])
        project_data = json.loads(raw_project)
        items = project_data.get('items', [])
        for item in items:
            if item.get('content', {}).get('type') == 'Issue':
                num = item['content'].get('number')
                if num:
                    item_by_issue_num[num] = item

    # 4. Sync Status, Priority, Size for all project items
    print(f"3. Synchronizing fields for {len(item_by_issue_num)} project items...", flush=True)
    
    updated_count = 0
    
    for idx, (num, item) in enumerate(item_by_issue_num.items(), 1):
        item_id = item['id']
        issue = issue_by_num.get(num)
        if not issue:
            continue
            
        labels = [l['name'].lower() for l in issue.get('labels', [])]
        title = issue['title']
        body = issue.get('body') or ''
        state = issue['state']
        
        # Determine Status
        if state == 'CLOSED':
            target_status = "Done"
        elif '🟢 **ready for dev**' in body.lower():
            target_status = "Ready"
        elif '🔴 **blocked**' in body.lower() or 'blocked' in labels:
            target_status = "Backlog"
        elif '🔵 **parent epic**' in body.lower() or 'parent' in labels or title.startswith('EPIC:'):
            target_status = "Backlog"
        else:
            target_status = "Ready"
            
        # Determine Priority
        if 'priority: high' in labels or 'p0' in labels or 'critical' in labels:
            target_priority = "P0"
        elif 'priority: medium' in labels or 'p1' in labels:
            target_priority = "P1"
        else:
            target_priority = "P2"
            
        # Determine Size
        if 'parent' in labels or title.startswith('EPIC:'):
            target_size = "XL"
        elif len(re.findall(r'`(apps/[^`]+|packages/[^`]+)`', body)) >= 5 or 'architecture' in labels:
            target_size = "L"
        elif len(re.findall(r'`(apps/[^`]+|packages/[^`]+)`', body)) >= 2:
            target_size = "M"
        elif 'scope: frontend' in labels or 'type: bug' in labels:
            target_size = "S"
        else:
            target_size = "M"
            
        # Set Status
        current_status = item.get('status')
        if current_status != target_status:
            run_cmd([
                "gh", "project", "item-edit",
                "--id", item_id,
                "--project-id", PROJECT_ID,
                "--field-id", STATUS_FIELD_ID,
                "--single-select-option-id", STATUS_OPTIONS[target_status]
            ])
            
        # Set Priority
        current_priority = item.get('priority')
        if current_priority != target_priority:
            run_cmd([
                "gh", "project", "item-edit",
                "--id", item_id,
                "--project-id", PROJECT_ID,
                "--field-id", PRIORITY_FIELD_ID,
                "--single-select-option-id", PRIORITY_OPTIONS[target_priority]
            ])

        # Set Size
        current_size = item.get('size')
        if current_size != target_size:
            run_cmd([
                "gh", "project", "item-edit",
                "--id", item_id,
                "--project-id", PROJECT_ID,
                "--field-id", SIZE_FIELD_ID,
                "--single-select-option-id", SIZE_OPTIONS[target_size]
            ])

        updated_count += 1
        if idx % 20 == 0 or idx == len(item_by_issue_num):
            print(f"[{idx}/{len(item_by_issue_num)}] Synchronized item #{num} (Status: {target_status}, Priority: {target_priority}, Size: {target_size})", flush=True)
            
        time.sleep(0.02)
        
    print(f"\n✅ Synchronization complete! {updated_count} project items updated.", flush=True)

if __name__ == "__main__":
    main()
