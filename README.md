# Mallory Automation Platform

Mallory is a powerful, flexible automation platform designed to create and manage virtual MCP (Anthropic's Model Control Protocol) servers. It allows you to aggregate tools from various underlying MCP servers, create custom prompts, and expose them through a unified, secure interface.

## Key Features

- **Virtual Server Creation**: Define virtual servers that aggregate tools and prompts from multiple real servers.
- **Dynamic Tool & Prompt Aggregation**: Automatically lists all available tools and prompts from the underlying servers associated with a virtual server.
- **Centralized Configuration**: Manage all your virtual servers, tools, and custom prompts through a user-friendly web interface.
- **Secure by Default**: Virtual servers can be protected with API keys, ensuring that only authorized clients can access them.
- **Standard-Compliant**: Implements the Mallory Control Protocol (MCP) for interoperability with compliant clients and servers.

## Local Development Setup

This guide will walk you through setting up the Mallory platform for local development. Docker is ignored for now.

### 1. Prerequisites

- Python 3.10+
- `pip` for package management
- A virtual environment tool like `venv`

### 2. Installation

First, clone the repository to your local machine.

```bash
git clone <repository_url>
cd agent
```

Next, set up a Python virtual environment to keep dependencies isolated.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Now, install the required Python packages for both the web interface and the backend intel server.

```bash
# Install web interface dependencies
pip install -r web-interface/requirements.txt

# Install intel server dependencies
pip install -r servers/mallory-intel-server/requirements.txt
```

### 3. Configuration

Some of the tools provided by the `mallory-intel-server` require API keys to function correctly. You will need to create a `.env` file to store these secrets.

Create a new file named `.env` inside the `servers/mallory-intel-server/` directory:

`servers/mallory-intel-server/.env`

Add your API keys to this file, following the format below:

```dotenv
# servers/mallory-intel-server/.env

VIRUSTOTAL_API_KEY=your_virustotal_api_key
URLSCAN_API_KEY=your_urlscan_api_key
MALLORY_API_KEY=your_mallory_api_key
```

### 4. Running the Application

The main entry point for the platform is the Flask web interface. To start the server, run the following command from the project root:

```bash
python3 web-interface/run.py
```

The server will start, and you can access the web interface by navigating to `http://127.0.0.1:8080` in your web browser.

The `mallory-intel-server` is started automatically as a subprocess by the web interface proxy when one of its tools is called, so you do not need to run it separately.

---

## Project Status

### Done:
- Rename Server to Registry
- Add the ability to define a server in the registry either as remote, local, GitHub
- Add a single vulnerability/cve hunt Virtual Server 
- Downstream key management
- Upstream key management (.env atm)
- Ability to add and edit custom prompts
- Ability to generate API Keys
- Downloadable configs

### In flight:
- Add th e ability to define a server in the registry either as remote, local, GitHub
  - Add the ability to download local server from a GitHub repo
  - Partially, needs so more testing and likely some fixes
- Take care of port collision
- Backing store started but not finished, only working with YAML

### TODO:
- Smithery like configuration per virtual server
- Add 5 to 10 cyber servers to registry
- Backing store layer (creds may be separate)
    - Check what type of store its using, update that store eg yaml
- Move custom-prompts out of web-interface

### Stretch
- Add a script to scrape/download servers off smithery and add to our registry (focus on cyber)
- Move to React 
- Branding 

### Minor TODO
- When copying config, api key is no longer hidden.
- Tool when added to a virtual server should be removed from the left side.
- Minor tweaks across the page, overlapping icons etc
