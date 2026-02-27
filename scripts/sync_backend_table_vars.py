#!/usr/bin/env python3
"""
Sync backend Dynamo table names from CloudFormation outputs to GitHub environment variables.

Example:
  python scripts/sync_backend_table_vars.py --repo noahspahn/excel-estimation-tool --env dev
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Dict


OUTPUT_TO_VAR = {
    "ReportJobsTableName": "REPORT_JOBS_TABLE_NAME",
    "ProposalsTableName": "PROPOSALS_TABLE_NAME",
    "ProposalVersionsTableName": "PROPOSAL_VERSIONS_TABLE_NAME",
    "ProposalDocumentsTableName": "PROPOSAL_DOCUMENTS_TABLE_NAME",
    "ContractsTableName": "CONTRACTS_TABLE_NAME",
    "ContractSyncTableName": "CONTRACT_SYNC_TABLE_NAME",
}


def run_command(args: list[str]) -> str:
    completed = subprocess.run(args, capture_output=True, text=True)
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        details = stderr or stdout or f"exit code {completed.returncode}"
        raise RuntimeError(f"Command failed: {' '.join(args)}\n{details}")
    return (completed.stdout or "").strip()


def infer_repo() -> str:
    remote = run_command(["git", "remote", "get-url", "origin"]).strip()
    # Supports:
    # - https://github.com/owner/repo.git
    # - git@github.com:owner/repo.git
    if remote.startswith("git@github.com:"):
        path = remote.split(":", 1)[1]
    elif "github.com/" in remote:
        path = remote.split("github.com/", 1)[1]
    else:
        raise RuntimeError(
            "Unable to infer GitHub repo from origin remote. Pass --repo owner/name."
        )
    if path.endswith(".git"):
        path = path[:-4]
    if "/" not in path:
        raise RuntimeError("Inferred repo is invalid. Pass --repo owner/name.")
    return path


def get_stack_outputs(stack_name: str, region: str) -> Dict[str, str]:
    raw = run_command(
        [
            "aws",
            "cloudformation",
            "describe-stacks",
            "--stack-name",
            stack_name,
            "--region",
            region,
            "--query",
            "Stacks[0].Outputs",
            "--output",
            "json",
        ]
    )
    outputs = json.loads(raw) if raw else []
    values: Dict[str, str] = {}
    for item in outputs:
        key = str(item.get("OutputKey") or "").strip()
        value = str(item.get("OutputValue") or "").strip()
        if key:
            values[key] = value
    return values


def set_github_var(repo: str, env_name: str, key: str, value: str) -> None:
    run_command(
        [
            "gh",
            "variable",
            "set",
            key,
            "--repo",
            repo,
            "--env",
            env_name,
            "--body",
            value,
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync backend table names from CloudFormation outputs to GitHub environment variables."
    )
    parser.add_argument("--repo", help="GitHub repo in owner/name format. Defaults to origin remote.")
    parser.add_argument("--env", default="dev", help="GitHub environment name (default: dev).")
    parser.add_argument(
        "--stack-name",
        default="EstimationBackendLambdaStack",
        help="CloudFormation stack name (default: EstimationBackendLambdaStack).",
    )
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1).")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero exit code if any required output is missing.",
    )
    args = parser.parse_args()

    try:
        repo = args.repo or infer_repo()
        outputs = get_stack_outputs(args.stack_name, args.region)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    missing = []
    updated = []
    for output_key, env_var in OUTPUT_TO_VAR.items():
        value = outputs.get(output_key, "").strip()
        if not value:
            missing.append((output_key, env_var))
            continue
        try:
            set_github_var(repo, args.env, env_var, value)
            updated.append((env_var, value))
        except Exception as exc:
            print(f"ERROR setting {env_var}: {exc}", file=sys.stderr)
            return 1

    print(f"Repo: {repo}")
    print(f"Environment: {args.env}")
    if updated:
        print("Updated GitHub environment variables:")
        for key, value in updated:
            print(f"  - {key}={value}")
    else:
        print("No variables were updated.")

    if missing:
        print("Missing CloudFormation outputs:")
        for output_key, env_var in missing:
            print(f"  - {output_key} (needed for {env_var})")
        if args.strict:
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
