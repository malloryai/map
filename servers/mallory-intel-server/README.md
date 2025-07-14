# MCP Mallory Intelligence Server

This project provides a modular, auto-discovering MCP (Model Context Protocol) server for comprehensive threat intelligence analysis. It integrates multiple threat intelligence platforms including Mallory AI, VirusTotal, and URLScan.io for complete security analysis workflows.

## Features

- **Modular Tool Architecture**: Each tool is self-contained in its own directory with a `config.yaml` and `tool.py`.
- **Automatic Tool Discovery**: The server automatically discovers and loads any tools placed in the `tools/` directory on startup.
- **Dynamic Reloading**: The server automatically reloads when you add or modify tool files, making development fast.
- **Environment-Based Configuration**: Securely manage API keys using a `.env` file for local development or environment variables in production.
- **Interactive Config Generator**: An `index.html` page is included to easily generate the necessary MCP configuration for Cursor.
- **Comprehensive Threat Intelligence**: Real integrations with leading threat intelligence platforms.

## Included Tools

### **Enhanced Threat Intelligence Tools**

- **`virustotal.query`**: Complete VirusTotal v3 API integration
  - File hash analysis (MD5, SHA1, SHA256)
  - Domain and IP reputation checking
  - **NEW**: Full URL analysis with submission and result polling
  - Behavioral analysis and community comments

- **`mallory.query`**: **Real Mallory AI integration** (no longer placeholder)
  - **`action="sources"`**: Enumerate OSINT sources monitored by Mallory AI
  - **`action="references"`**: Query threat intelligence references with source filtering
  - **`action="vulnerability"`**: Product/vendor vulnerability inference with CPE support
  - **`action="exploits"`**: CVE exploit intelligence with maturity ratings

- **`urlscan.scan`**: **Real URLScan.io integration** (no longer placeholder)
  - Submit URLs for live scanning
  - Retrieve comprehensive scan results (screenshots, DOM, network analysis)
  - Search historical scan database
  - Automatic result polling with timeout handling

- **`howto.cve`**: Static instructions for CVE data lookup

### **Integrated Workflow Examples**
- **Threat Hunting**: `mallory.query(action="references")` → `virustotal.query` → `urlscan.scan`
- **Vulnerability Assessment**: `mallory.query(action="vulnerability")` → `mallory.query(action="exploits")`
- **URL Analysis**: `urlscan.scan` → `virustotal.query` → `mallory.query(action="references")`

---

## Setup and Installation

Follow these steps to get the server up and running.

### 1. Set Up the Environment

Create a `.env` file to store your API keys:

```bash
# Copy the example (if available) or create manually
cp .env.example .env
```

Edit the `.env` file with your API keys:

```bash
# Required for VirusTotal integration
VIRUSTOTAL_API_KEY="your_virustotal_api_key_here"

# Required for Mallory AI integration  
MALLORY_API_KEY="your_mallory_api_key_here"

# Optional for URLScan.io (fallback to search if not provided)
URLSCAN_API_KEY="your_urlscan_api_key_here"
```

**API Key Sources:**
- **VirusTotal**: Get your API key from [VirusTotal API Keys](https://www.virustotal.com/gui/my-apikey)
- **Mallory AI**: Contact the Mallory AI team for API access via [Mallory AI Docs](https://learn.mallory.ai/)
- **URLScan.io**: Sign up at [URLScan.io](https://urlscan.io/user/signup) for API access

### 2. Install Dependencies

It is recommended to use a Python virtual environment. Once your environment is active, install the required packages:

```bash
# It's best practice to use python -m pip to ensure installation in the correct environment
python -m pip install -r requirements.txt
```

### 3. Run the Server

You can start the server with the following command:

```bash
python server_stdio.py
```

The server will start and automatically discover all available tools.

---

## Configuration for Cursor

To make configuration easy, open the `index.html` file in your web browser.

This page will help you generate the correct JSON configuration for your environment.

1.  **Enter your Project Directory Path**: The absolute path to this `mcp-server` directory.
2.  **Enter your API Keys**: These will be embedded in the configuration.
3.  **Add to Cursor**: Click the "Add to Cursor" button to automatically configure the MCP server in your editor, or use the "Copy Config" button to do it manually.

---

## Usage Examples

### Enhanced Mallory AI Queries

```bash
# Get all OSINT sources
curl -X POST -H "Content-Type: application/json" \
-d '{"jsonrpc": "2.0", "method": "tools.execute", "params": {"tool_id": "mallory.query", "params": {"action": "sources"}}, "id": 1}' \
http://127.0.0.1:8000/jsonrpc

# Search for threat intelligence references
curl -X POST -H "Content-Type: application/json" \
-d '{"jsonrpc": "2.0", "method": "tools.execute", "params": {"tool_id": "mallory.query", "params": {"action": "references", "indicator": "malicious-domain.com"}}, "id": 2}' \
http://127.0.0.1:8000/jsonrpc

# Vulnerability search by product
curl -X POST -H "Content-Type: application/json" \
-d '{"jsonrpc": "2.0", "method": "tools.execute", "params": {"tool_id": "mallory.query", "params": {"action": "vulnerability", "product": "apache", "vendor": "apache"}}, "id": 3}' \
http://127.0.0.1:8000/jsonrpc

# Get exploit information for CVE
curl -X POST -H "Content-Type: application/json" \
-d '{"jsonrpc": "2.0", "method": "tools.execute", "params": {"tool_id": "mallory.query", "params": {"action": "exploits", "indicator": "CVE-2024-1234"}}, "id": 4}' \
http://127.0.0.1:8000/jsonrpc
```

### Enhanced VirusTotal Queries (Now with URL Support)

```bash
# Analyze a URL (new functionality)
curl -X POST -H "Content-Type: application/json" \
-d '{"jsonrpc": "2.0", "method": "tools.execute", "params": {"tool_id": "virustotal.query", "params": {"query": "https://suspicious-site.com"}}, "id": 5}' \
http://127.0.0.1:8000/jsonrpc

# Traditional IP/domain/hash analysis
curl -X POST -H "Content-Type: application/json" \
-d '{"jsonrpc": "2.0", "method": "tools.execute", "params": {"tool_id": "virustotal.query", "params": {"query": "8.8.8.8"}}, "id": 6}' \
http://127.0.0.1:8000/jsonrpc
```

### Real URLScan.io Integration

```bash
# Scan a URL with URLScan.io
curl -X POST -H "Content-Type: application/json" \
-d '{"jsonrpc": "2.0", "method": "tools.execute", "params": {"tool_id": "urlscan.scan", "params": {"url": "https://example.com"}}, "id": 7}' \
http://127.0.0.1:8000/jsonrpc
```

---

## How to Add a New Tool

Creating a new tool is simple:

1.  Create a new sub-directory inside the `tools/` directory (e.g., `tools/my_new_tool/`).
2.  Inside your new directory, create a `config.yaml` file that defines the tool's name, description, inputs, and outputs. The `name` must be unique.
3.  Create a corresponding `tool.py` script. This script must:
    -   Read a single JSON object from standard input (`sys.stdin`).
    -   Perform its logic.
    -   Write a single JSON object to standard output (`sys.stdout`) with a key that matches the `output` name in your config.
4.  Restart the server (or let it auto-reload). It will automatically discover and load your new tool.

---

## Security Considerations

- **API Key Management**: Store API keys securely in environment variables or `.env` files
- **Rate Limiting**: Be aware of API rate limits for external services
- **Data Privacy**: Consider the privacy implications of submitting URLs/files to external services
- **Human Oversight**: Always maintain human oversight for threat intelligence analysis workflows 