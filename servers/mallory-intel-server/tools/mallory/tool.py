import sys
import json
import os
import requests
from urllib.parse import quote

# --- Configuration ---
MALLORY_API_URL = "https://api.mallory.ai/v1"
MALLORY_API_KEY = os.environ.get("MALLORY_API_KEY")

def mallory_sources() -> dict:
    """
    Retrieve all OSINT sources monitored by Mallory AI.
    """
    headers = {"Authorization": f"Bearer {MALLORY_API_KEY}"}
    response = requests.get(f"{MALLORY_API_URL}/sources", headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        return {
            "error": "Failed to retrieve sources",
            "status_code": response.status_code,
            "response": response.text,
        }

def mallory_references(indicator: str = None, source_filter: str = None) -> dict:
    """
    Query Mallory AI for intelligence references.
    """
    headers = {"Authorization": f"Bearer {MALLORY_API_KEY}"}
    params = {}
    
    if source_filter:
        params["filter"] = source_filter
    if indicator:
        params["q"] = indicator
    
    response = requests.get(f"{MALLORY_API_URL}/references", headers=headers, params=params)
    
    if response.status_code == 200:
        return response.json()
    else:
        return {
            "error": "Failed to retrieve references",
            "status_code": response.status_code,
            "response": response.text,
        }

def mallory_vulnerability_search(product: str = None, vendor: str = None, cpe: str = None) -> dict:
    """
    Search for products in Mallory's vulnerability database.
    """
    headers = {"Authorization": f"Bearer {MALLORY_API_KEY}", "Content-Type": "application/json"}
    
    payload = {}
    if cpe:
        payload["cpe"] = cpe
    if product:
        payload["product"] = product
    if vendor:
        payload["vendor"] = vendor
    
    # Default to application type if not specified
    if not cpe and not payload.get("type"):
        payload["type"] = "application"
    
    response = requests.post(f"{MALLORY_API_URL}/products/search", headers=headers, json=payload)
    
    if response.status_code == 200:
        return response.json()
    else:
        return {
            "error": "Failed to search products",
            "status_code": response.status_code,
            "response": response.text,
        }

def mallory_exploits(cve_identifier: str) -> dict:
    """
    Get exploit information for a specific CVE.
    """
    headers = {"Authorization": f"Bearer {MALLORY_API_KEY}"}
    
    # URL encode the CVE identifier
    encoded_cve = quote(cve_identifier, safe='')
    response = requests.get(f"{MALLORY_API_URL}/vulnerabilities/{encoded_cve}/exploits", headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        return {
            "error": "Failed to retrieve exploits",
            "status_code": response.status_code,
            "response": response.text,
        }

def mallory_query(action: str, **kwargs) -> dict:
    """
    Main query function that routes to appropriate Mallory AI endpoints.
    """
    if action == "sources":
        return mallory_sources()
    
    elif action == "references":
        indicator = kwargs.get("indicator")
        source_filter = kwargs.get("source_filter")
        return mallory_references(indicator, source_filter)
    
    elif action == "vulnerability":
        product = kwargs.get("product")
        vendor = kwargs.get("vendor")
        cpe = kwargs.get("cpe")
        return mallory_vulnerability_search(product, vendor, cpe)
    
    elif action == "exploits":
        cve_identifier = kwargs.get("indicator")
        if not cve_identifier:
            return {"error": "CVE identifier required for exploits query"}
        return mallory_exploits(cve_identifier)
    
    else:
        return {"error": f"Unknown action: {action}. Supported actions: sources, references, vulnerability, exploits"}

# --- Main Execution ---
if __name__ == "__main__":
    if not MALLORY_API_KEY:
        json.dump({"error": "MALLORY_API_KEY environment variable not set."}, sys.stdout)
        sys.exit(1)

    if sys.stdin.isatty():
        # Command line usage for testing
        if len(sys.argv) < 2:
            print("Usage: python tool.py <action> [additional_args...]")
            print("Actions: sources, references, vulnerability, exploits")
            sys.exit(1)
        
        action = sys.argv[1]
        kwargs = {}
        
        # Parse additional arguments
        for i in range(2, len(sys.argv), 2):
            if i + 1 < len(sys.argv):
                kwargs[sys.argv[i]] = sys.argv[i + 1]
        
        result = mallory_query(action, **kwargs)
    else:
        # JSON input from MCP server
        input_data = json.load(sys.stdin)
        action = input_data.get("action")
        
        if not action:
            json.dump({"error": "Action parameter required"}, sys.stdout)
            sys.exit(1)
        
        # Extract all other parameters
        kwargs = {k: v for k, v in input_data.items() if k != "action"}
        result = mallory_query(action, **kwargs)

    json.dump({"intel": result}, sys.stdout) 