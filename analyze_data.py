#!/usr/bin/env python3
"""
Analyze Terraform Cloud data collected by terraform_api_client.py
"""

import json
import argparse
from collections import defaultdict, Counter
from datetime import datetime
import sys

def load_data(file_path: str) -> dict:
    """Load JSON data from file"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File {file_path} not found")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {file_path}")
        sys.exit(1)

def analyze_organizations(data: dict):
    """Analyze organization data"""
    print("\n" + "="*60)
    print("ORGANIZATION ANALYSIS")
    print("="*60)
    
    organizations = data.get('organizations', [])
    
    for org in organizations:
        attrs = org.get('attributes', {})
        print(f"\nOrganization: {attrs.get('name', 'N/A')}")
        print(f"  Email: {attrs.get('email', 'N/A')}")
        print(f"  Created: {attrs.get('created-at', 'N/A')}")
        print(f"  Plan: {attrs.get('plan', 'N/A')}")
        print(f"  Users: {attrs.get('users', 'N/A')}")

def analyze_workspaces(data: dict):
    """Analyze workspace data"""
    print("\n" + "="*60)
    print("WORKSPACE ANALYSIS")
    print("="*60)
    
    workspaces_data = data.get('workspaces', {})
    workspace_stats = defaultdict(int)
    terraform_versions = Counter()
    
    for org_name, workspaces in workspaces_data.items():
        print(f"\nOrganization: {org_name}")
        print(f"  Total Workspaces: {len(workspaces)}")
        
        for workspace in workspaces:
            attrs = workspace.get('attributes', {})
            workspace_stats['total'] += 1
            
            # Count by execution mode
            execution_mode = attrs.get('execution-mode', 'unknown')
            workspace_stats[f'execution_mode_{execution_mode}'] += 1
            
            # Count Terraform versions
            tf_version = attrs.get('terraform-version', 'unknown')
            terraform_versions[tf_version] += 1
            
            # Workspace details
            print(f"    - {attrs.get('name', 'N/A')}")
            print(f"      Terraform Version: {tf_version}")
            print(f"      Execution Mode: {execution_mode}")
            print(f"      Auto Apply: {attrs.get('auto-apply', False)}")
            print(f"      Created: {attrs.get('created-at', 'N/A')}")
    
    print(f"\nWorkspace Statistics:")
    print(f"  Total Workspaces: {workspace_stats['total']}")
    
    print(f"\nTerraform Versions:")
    for version, count in terraform_versions.most_common():
        print(f"  {version}: {count}")

def analyze_runs(data: dict):
    """Analyze run data"""
    print("\n" + "="*60)
    print("RUN ANALYSIS")
    print("="*60)
    
    runs_data = data.get('runs', {})
    run_stats = defaultdict(int)
    status_counts = Counter()
    
    for org_name, org_runs in runs_data.items():
        print(f"\nOrganization: {org_name}")
        
        for workspace_name, workspace_data in org_runs.items():
            runs = workspace_data.get('runs', [])
            print(f"  Workspace: {workspace_name}")
            print(f"    Total Runs: {len(runs)}")
            
            run_stats['total'] += len(runs)
            
            for run in runs:
                attrs = run.get('attributes', {})
                status = attrs.get('status', 'unknown')
                status_counts[status] += 1
                
                # Recent runs (last 10)
                if len([r for r in runs if r == run]) <= 10:
                    print(f"      - Run {run.get('id', 'N/A')[:8]}...")
                    print(f"        Status: {status}")
                    print(f"        Created: {attrs.get('created-at', 'N/A')}")
                    print(f"        Message: {attrs.get('message', 'N/A')[:50]}...")
    
    print(f"\nRun Statistics:")
    print(f"  Total Runs: {run_stats['total']}")
    
    print(f"\nRun Status Distribution:")
    for status, count in status_counts.most_common():
        percentage = (count / run_stats['total'] * 100) if run_stats['total'] > 0 else 0
        print(f"  {status}: {count} ({percentage:.1f}%)")

def generate_summary_report(data: dict):
    """Generate a comprehensive summary report"""
    print("\n" + "="*60)
    print("COMPREHENSIVE SUMMARY REPORT")
    print("="*60)
    
    summary = data.get('summary', {})
    
    print(f"Total Organizations: {summary.get('total_organizations', 0)}")
    print(f"Total Workspaces: {summary.get('total_workspaces', 0)}")
    print(f"Total Runs: {summary.get('total_runs', 0)}")
    
    # Calculate averages
    total_orgs = summary.get('total_organizations', 0)
    total_workspaces = summary.get('total_workspaces', 0)
    
    if total_orgs > 0:
        avg_workspaces_per_org = total_workspaces / total_orgs
        print(f"Average Workspaces per Organization: {avg_workspaces_per_org:.1f}")
    
    if total_workspaces > 0:
        avg_runs_per_workspace = summary.get('total_runs', 0) / total_workspaces
        print(f"Average Runs per Workspace: {avg_runs_per_workspace:.1f}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Analyze Terraform Cloud data')
    parser.add_argument('--input', default='terraform_data.json', help='Input JSON file')
    parser.add_argument('--organizations', action='store_true', help='Analyze organizations')
    parser.add_argument('--workspaces', action='store_true', help='Analyze workspaces')
    parser.add_argument('--runs', action='store_true', help='Analyze runs')
    parser.add_argument('--all', action='store_true', help='Run all analyses')
    
    args = parser.parse_args()
    
    # Load data
    data = load_data(args.input)
    
    # Generate summary report (always shown)
    generate_summary_report(data)
    
    # Run specific analyses
    if args.all or args.organizations:
        analyze_organizations(data)
    
    if args.all or args.workspaces:
        analyze_workspaces(data)
    
    if args.all or args.runs:
        analyze_runs(data)
    
    if not any([args.organizations, args.workspaces, args.runs, args.all]):
        print("\nUse --all or specify --organizations, --workspaces, or --runs for detailed analysis")

if __name__ == "__main__":
    main()
