#!/usr/bin/env python3
"""
Terraform Cloud API Client
Efficiently retrieves organizations, workspaces, and runs using async requests.
"""

import asyncio
import aiohttp
import json
import sys
from typing import List, Dict, Any
from dataclasses import dataclass
import argparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class TerraformConfig:
    """Configuration for Terraform Cloud API"""
    api_token: str
    base_url: str = "https://app.terraform.io/api/v2"
    max_concurrent_requests: int = 10
    timeout: int = 30

class TerraformAPIClient:
    """Async client for Terraform Cloud API"""
    
    def __init__(self, config: TerraformConfig):
        self.config = config
        self.session = None
        self.semaphore = asyncio.Semaphore(config.max_concurrent_requests)
        
    async def __aenter__(self):
        """Async context manager entry"""
        headers = {
            'Authorization': f'Bearer {self.config.api_token}',
            'Content-Type': 'application/vnd.api+json'
        }
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        self.session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def _make_request(self, url: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make an async HTTP request with rate limiting"""
        async with self.semaphore:
            try:
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:
                        # Rate limited, wait and retry
                        retry_after = int(response.headers.get('Retry-After', 5))
                        logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                        await asyncio.sleep(retry_after)
                        return await self._make_request(url, params)
                    else:
                        logger.error(f"Request failed: {response.status} - {await response.text()}")
                        response.raise_for_status()
            except Exception as e:
                logger.error(f"Request error for {url}: {str(e)}")
                raise
    
    async def _paginated_request(self, url: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Handle paginated API responses"""
        all_data = []
        current_url = url
        
        while current_url:
            response = await self._make_request(current_url, params)
            
            if 'data' in response:
                all_data.extend(response['data'])
            
            # Check for next page
            if 'links' in response and 'next' in response['links'] and response['links']['next']:
                current_url = response['links']['next']
                params = None  # Clear params for subsequent requests as they're in the URL
            else:
                current_url = None
                
        return all_data
    
    async def get_organizations(self) -> List[Dict[str, Any]]:
        """Get all organizations"""
        logger.info("Fetching organizations...")
        url = f"{self.config.base_url}/organizations"
        organizations = await self._paginated_request(url)
        logger.info(f"Found {len(organizations)} organizations")
        return organizations
    
    async def get_workspaces_for_organization(self, org_name: str) -> List[Dict[str, Any]]:
        """Get all workspaces for a specific organization"""
        logger.info(f"Fetching workspaces for organization: {org_name}")
        url = f"{self.config.base_url}/organizations/{org_name}/workspaces"
        params = {'include': 'current-run,organization'}
        workspaces = await self._paginated_request(url, params)
        logger.info(f"Found {len(workspaces)} workspaces in {org_name}")
        return workspaces
    
    async def get_runs_for_workspace(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Get all runs for a specific workspace"""
        logger.info(f"Fetching runs for workspace: {workspace_id}")
        url = f"{self.config.base_url}/workspaces/{workspace_id}/runs"
        params = {'include': 'plan,apply,configuration-version'}
        runs = await self._paginated_request(url, params)
        logger.info(f"Found {len(runs)} runs for workspace {workspace_id}")
        return runs
    
    async def get_all_data(self) -> Dict[str, Any]:
        """Get all organizations, workspaces, and runs"""
        logger.info("Starting comprehensive data collection...")
        
        # Step 1: Get all organizations
        organizations = await self.get_organizations()
        
        # Step 2: Get all workspaces for each organization (concurrent)
        workspace_tasks = []
        for org in organizations:
            org_name = org['attributes']['name']
            task = self.get_workspaces_for_organization(org_name)
            workspace_tasks.append((org_name, task))
        
        # Execute workspace requests concurrently
        org_workspaces = {}
        for org_name, task in workspace_tasks:
            workspaces = await task
            org_workspaces[org_name] = workspaces
        
        # Step 3: Get all runs for each workspace (concurrent)
        run_tasks = []
        workspace_runs = {}
        
        for org_name, workspaces in org_workspaces.items():
            for workspace in workspaces:
                workspace_id = workspace['id']
                workspace_name = workspace['attributes']['name']
                task = self.get_runs_for_workspace(workspace_id)
                run_tasks.append((org_name, workspace_name, workspace_id, task))
        
        # Execute run requests concurrently
        for org_name, workspace_name, workspace_id, task in run_tasks:
            runs = await task
            if org_name not in workspace_runs:
                workspace_runs[org_name] = {}
            workspace_runs[org_name][workspace_name] = {
                'workspace_id': workspace_id,
                'runs': runs
            }
        
        # Combine all data
        result = {
            'organizations': organizations,
            'workspaces': org_workspaces,
            'runs': workspace_runs,
            'summary': {
                'total_organizations': len(organizations),
                'total_workspaces': sum(len(workspaces) for workspaces in org_workspaces.values()),
                'total_runs': sum(
                    len(workspace_data['runs']) 
                    for org_runs in workspace_runs.values() 
                    for workspace_data in org_runs.values()
                )
            }
        }
        
        logger.info(f"Data collection complete: {result['summary']}")
        return result

async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Terraform Cloud API Data Collector')
    parser.add_argument('--token', required=True, help='Terraform Cloud API token')
    parser.add_argument('--output', default='terraform_data.json', help='Output file path')
    parser.add_argument('--max-concurrent', type=int, default=10, help='Max concurrent requests')
    parser.add_argument('--timeout', type=int, default=30, help='Request timeout in seconds')
    
    args = parser.parse_args()
    
    # Create configuration
    config = TerraformConfig(
        api_token=args.token,
        max_concurrent_requests=args.max_concurrent,
        timeout=args.timeout
    )
    
    try:
        # Collect all data
        async with TerraformAPIClient(config) as client:
            data = await client.get_all_data()
        
        # Save to file
        with open(args.output, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Data saved to {args.output}")
        
        # Print summary
        summary = data['summary']
        print("\n" + "="*50)
        print("TERRAFORM CLOUD DATA COLLECTION SUMMARY")
        print("="*50)
        print(f"Organizations: {summary['total_organizations']}")
        print(f"Workspaces: {summary['total_workspaces']}")
        print(f"Runs: {summary['total_runs']}")
        print(f"Output file: {args.output}")
        print("="*50)
        
    except Exception as e:
        logger.error(f"Error during data collection: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
