import sys
import json
import os
import requests
import time
from urllib.parse import quote

# --- Configuration ---
URLSCAN_API_URL = "https://urlscan.io/api/v1"
URLSCAN_API_KEY = os.environ.get("URLSCAN_API_KEY")

def urlscan_submit(url: str, visibility: str = "public") -> dict:
    """
    Submit a URL for scanning to urlscan.io.
    """
    headers = {
        "API-Key": URLSCAN_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "url": url,
        "visibility": visibility
    }
    
    response = requests.post(f"{URLSCAN_API_URL}/scan/", headers=headers, json=payload)
    
    if response.status_code == 200:
        return response.json()
    else:
        return {
            "error": "Failed to submit scan",
            "status_code": response.status_code,
            "response": response.text,
        }

def urlscan_result(scan_uuid: str) -> dict:
    """
    Retrieve scan results from urlscan.io.
    """
    response = requests.get(f"{URLSCAN_API_URL}/result/{scan_uuid}/")
    
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        return {"error": "Scan not found or still processing"}
    else:
        return {
            "error": "Failed to retrieve scan results",
            "status_code": response.status_code,
            "response": response.text,
        }

def urlscan_search(query: str, size: int = 100) -> dict:
    """
    Search urlscan.io database for historical scans.
    """
    params = {
        "q": query,
        "size": size
    }
    
    response = requests.get(f"{URLSCAN_API_URL}/search/", params=params)
    
    if response.status_code == 200:
        return response.json()
    else:
        return {
            "error": "Failed to search urlscan database",
            "status_code": response.status_code,
            "response": response.text,
        }

def urlscan_scan_and_wait(url: str, visibility: str = "public", max_wait: int = 60) -> dict:
    """
    Submit a URL for scanning and wait for results.
    """
    # Submit the scan
    submit_result = urlscan_submit(url, visibility)
    
    if "error" in submit_result:
        return submit_result
    
    scan_uuid = submit_result.get("uuid")
    if not scan_uuid:
        return {"error": "No scan UUID returned from submission"}
    
    # Wait for results
    wait_time = 0
    while wait_time < max_wait:
        time.sleep(5)
        wait_time += 5
        
        result = urlscan_result(scan_uuid)
        
        if "error" not in result:
            # Scan completed successfully
            return {
                "submission": submit_result,
                "result": result,
                "scan_uuid": scan_uuid
            }
        elif "still processing" not in result.get("error", ""):
            # Actual error, not just processing
            return result
    
    # Timeout - return submission info for manual checking
    return {
        "submission": submit_result,
        "scan_uuid": scan_uuid,
        "status": "timeout",
        "message": f"Scan submitted but results not ready after {max_wait} seconds. Check manually at: https://urlscan.io/result/{scan_uuid}/"
    }

def urlscan_scan(url: str) -> dict:
    """
    Main function that handles URL scanning with multiple strategies.
    """
    if not URLSCAN_API_KEY:
        # If no API key, try to search for existing scans
        search_result = urlscan_search(f"domain:{url}")
        if "error" not in search_result and search_result.get("results"):
            return {
                "url": url,
                "strategy": "search_existing",
                "message": "No API key provided, returning existing scan data",
                "search_results": search_result
            }
        else:
            return {
                "error": "URLSCAN_API_KEY not set and no existing scans found",
                "url": url
            }
    
    # Try to scan and wait for results
    return urlscan_scan_and_wait(url)

# --- Main Execution ---
if __name__ == "__main__":
    if sys.stdin.isatty():
        if len(sys.argv) > 1:
            input_url = sys.argv[1]
        else:
            print("Usage: python tool.py <url>")
            sys.exit(1)
    else:
        input_data = json.load(sys.stdin)
        input_url = input_data.get("url")

    if not input_url:
        json.dump({"error": "No URL provided"}, sys.stdout)
        sys.exit(1)

    scan_data = urlscan_scan(input_url)
    json.dump({"scan_data": scan_data}, sys.stdout) 