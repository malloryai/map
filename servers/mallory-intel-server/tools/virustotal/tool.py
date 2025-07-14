import sys
import json
import os
import re
import requests
import base64
import time

# --- Configuration ---
VT_API_URL = "https://www.virustotal.com/api/v3"
VT_API_KEY = os.environ.get("VIRUSTOTAL_API_KEY")

# --- Query Type Detection ---
def get_query_type(query: str) -> str:
    """
    Determines if the query is an IP, domain, URL, or file hash.
    """
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", query):
        return "ip_address"
    if re.match(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,6}$", query):
        return "domain"
    if re.match(r"^[a-fA-F0-9]{32}$", query) or \
       re.match(r"^[a-fA-F0-9]{40}$", query) or \
       re.match(r"^[a-fA-F0-9]{64}$", query):
        return "file"
    if query.startswith("http://") or query.startswith("https://"):
        return "url"
    return "unknown"

def url_to_id(url: str) -> str:
    """
    Convert URL to VirusTotal URL ID (base64 encoded without padding).
    """
    url_id = base64.urlsafe_b64encode(url.encode()).decode().rstrip('=')
    return url_id

# --- API Call Logic ---
def query_virustotal_api(endpoint: str) -> dict:
    """
    Queries the VirusTotal API with the given endpoint.
    """
    headers = {"x-apikey": VT_API_KEY}
    response = requests.get(f"{VT_API_URL}/{endpoint}", headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        return {
            "error": "API request failed",
            "status_code": response.status_code,
            "response": response.text,
        }

def submit_url_for_analysis(url: str) -> dict:
    """
    Submit a URL for analysis to VirusTotal.
    """
    headers = {"x-apikey": VT_API_KEY, "Content-Type": "application/x-www-form-urlencoded"}
    data = {"url": url}
    
    response = requests.post(f"{VT_API_URL}/urls", headers=headers, data=data)
    
    if response.status_code == 200:
        return response.json()
    else:
        return {
            "error": "Failed to submit URL for analysis",
            "status_code": response.status_code,
            "response": response.text,
        }

def get_analysis_result(analysis_id: str) -> dict:
    """
    Get analysis results from VirusTotal.
    """
    headers = {"x-apikey": VT_API_KEY}
    response = requests.get(f"{VT_API_URL}/analyses/{analysis_id}", headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        return {
            "error": "Failed to get analysis result",
            "status_code": response.status_code,
            "response": response.text,
        }

def virustotal_url_analysis(url: str, wait_for_completion: bool = True, max_wait: int = 60) -> dict:
    """
    Analyze a URL with VirusTotal, optionally waiting for completion.
    """
    # First, try to get existing analysis
    url_id = url_to_id(url)
    existing_result = query_virustotal_api(f"urls/{url_id}")
    
    if "error" not in existing_result:
        return {
            "url": url,
            "url_id": url_id,
            "strategy": "existing_analysis",
            "result": existing_result
        }
    
    # Submit for new analysis
    submission = submit_url_for_analysis(url)
    if "error" in submission:
        return submission
    
    analysis_id = submission.get("data", {}).get("id")
    if not analysis_id:
        return {"error": "No analysis ID returned from URL submission"}
    
    if not wait_for_completion:
        return {
            "url": url,
            "strategy": "submitted_for_analysis",
            "submission": submission,
            "analysis_id": analysis_id,
            "message": f"URL submitted for analysis. Check results manually with analysis ID: {analysis_id}"
        }
    
    # Wait for analysis completion
    wait_time = 0
    while wait_time < max_wait:
        time.sleep(5)
        wait_time += 5
        
        analysis_result = get_analysis_result(analysis_id)
        
        if "error" not in analysis_result:
            status = analysis_result.get("data", {}).get("attributes", {}).get("status")
            if status == "completed":
                # Get the final URL report
                url_report = query_virustotal_api(f"urls/{url_id}")
                return {
                    "url": url,
                    "url_id": url_id,
                    "strategy": "new_analysis_completed",
                    "submission": submission,
                    "analysis": analysis_result,
                    "result": url_report
                }
            elif status in ["queued", "running"]:
                continue  # Keep waiting
            else:
                return {
                    "url": url,
                    "strategy": "analysis_failed",
                    "submission": submission,
                    "analysis": analysis_result,
                    "status": status
                }
    
    # Timeout
    return {
        "url": url,
        "strategy": "analysis_timeout",
        "submission": submission,
        "analysis_id": analysis_id,
        "message": f"Analysis submitted but not completed after {max_wait} seconds. Check manually."
    }

def virustotal_query(query: str) -> dict:
    """
    Determines query type and fetches data from the correct VirusTotal API endpoint.
    """
    query_type = get_query_type(query)
    
    if query_type == "ip_address":
        endpoint = f"ip_addresses/{query}"
        return query_virustotal_api(endpoint)
    
    elif query_type == "domain":
        endpoint = f"domains/{query}"
        return query_virustotal_api(endpoint)
    
    elif query_type == "file":
        endpoint = f"files/{query}"
        return query_virustotal_api(endpoint)
    
    elif query_type == "url":
        return virustotal_url_analysis(query)
    
    else:
        return {"error": f"Could not determine query type for '{query}'."}

# --- Main Execution ---
if __name__ == "__main__":
    if not VT_API_KEY:
        json.dump({"error": "VIRUSTOTAL_API_KEY environment variable not set."}, sys.stdout)
        sys.exit(1)

    if sys.stdin.isatty():
        if len(sys.argv) > 1:
            input_query = sys.argv[1]
        else:
            print("Usage: python tool.py <query>")
            sys.exit(1)
    else:
        input_data = json.load(sys.stdin)
        input_query = input_data.get("query")

    if not input_query:
        json.dump({"error": "No query provided"}, sys.stdout)
        sys.exit(1)

    result = virustotal_query(input_query)
    json.dump({"result": result}, sys.stdout) 