import sys
import json

def entry_point() -> str:
    """
    Returns a static string of instructions for fetching CVE data.
    """
    return """
To fetch data for a CVE:
1. Identify the CVE ID (e.g., CVE-2023-12345).
2. Use the 'virustotal.query' tool or 'mallory.query' tool with the CVE ID as input.
3. Review the results from both tools for a full view.
""".strip()

if __name__ == "__main__":
    # This tool has no inputs, so we can directly generate the output.
    instructions = entry_point()
    json.dump({"instructions": instructions}, sys.stdout) 