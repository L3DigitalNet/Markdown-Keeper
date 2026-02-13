# Project Design Document: MarkdownKeeper

## *LLM-Optimized Documentation Management*

## Executive Summary

**MarkdownKeeper** is a Linux-native CLI utility and background service that automatically manages, organizes, and maintains markdown documentation repositories. It provides continuous monitoring, intelligent organization, link validation, and indexing capabilities for markdown-based knowledge bases, **with specialized optimizations for LLM coding agent consumption**.

------

## 1. Project Overview

### 1.1 Purpose

To provide automated, continuous maintenance of markdown documentation collections with **efficient, token-optimized access for LLM coding agents**, reducing manual overhead and ensuring documentation remains accurate, accessible, and machine-queryable.

### 1.2 Key Objectives

- **Automated Organization**: Maintain consistent structure and metadata
- **Link Integrity**: Detect and repair broken internal/external links
- **Search & Discovery**: Generate and maintain comprehensive indexes
- **Quality Assurance**: Enforce documentation standards and best practices
- **Low Overhead**: Minimal resource consumption as a background service
- **🤖 LLM-Optimized Access**: Token-efficient querying with semantic search and progressive content delivery

### 1.3 Target Users

- System administrators managing technical documentation
- Development teams with markdown-based wikis
- Technical writers maintaining knowledge bases
- DevOps teams managing runbooks and procedures
- **LLM coding agents (Claude Code, Cursor, Continue, etc.)**

------

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     MarkdownKeeper Service                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   File       │  │   Content    │  │   Index      │    │
│  │   Watcher    │─▶│   Processor  │─▶│   Generator  │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│         │                  │                  │            │
│         ▼                  ▼                  ▼            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Event      │  │   Link       │  │   Metadata   │    │
│  │   Queue      │  │   Validator  │  │   Manager    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│         │                  │                  │            │
│         └──────────────────┴──────────────────┘            │
│                            │                                │
│              ┌─────────────▼─────────────┐                 │
│              │  🤖 LLM Query Engine      │                 │
│              │  - Semantic Search        │                 │
│              │  - Embedding Cache        │                 │
│              │  - Token Budget Manager   │                 │
│              │  - Progressive Delivery   │                 │
│              └─────────────┬─────────────┘                 │
│                            │                                │
│                    ┌───────▼────────┐                      │
│                    │   SQLite DB    │                      │
│                    │  + Vector Ext  │                      │
│                    └────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  Watched Docs  │
                    │   Directory    │
                    └────────────────┘
```

### 2.2 Core Components

#### 2.2.1 File Watcher

- **Technology**: `inotify` (Linux kernel subsystem)
- **Responsibilities**:
  - Monitor filesystem events (CREATE, MODIFY, DELETE, MOVE)
  - Filter markdown files (`.md`, `.markdown`)
  - Debounce rapid changes
  - Queue events for processing
  - Trigger embedding regeneration on content changes

#### 2.2.2 Content Processor

- **Responsibilities**:
  - Parse markdown frontmatter (YAML)
  - Extract headings and structure
  - Normalize formatting
  - Apply organization rules
  - Update timestamps
  - **Generate document summaries for LLM consumption**
  - **Extract key concepts and topics**

#### 2.2.3 Link Validator

- **Responsibilities**:
  - Extract all links (internal and external)
  - Validate internal references
  - Check external URLs (HTTP HEAD requests)
  - Suggest fixes for broken links
  - Update link mappings when files move

#### 2.2.4 Index Generator

- **Responsibilities**:
  - Build full-text search index
  - Generate table of contents files
  - Create tag/category indexes
  - Maintain document relationship graph
  - Update `README.md` files per directory
  - **Generate LLM-optimized manifest files**

#### 2.2.5 Metadata Manager

- **Responsibilities**:
  - Enforce frontmatter schema
  - Auto-generate missing metadata
  - Track document versions/history
  - Manage tags and categories
  - **Generate semantic embeddings**
  - **Maintain token count metadata**

#### 2.2.6 🤖 LLM Query Engine (New)

- **Responsibilities**:
  - Process natural language queries from LLM agents
  - Semantic search using document embeddings
  - Return structured, token-efficient responses
  - Progressive content delivery (metadata → summary → full content)
  - Query result caching
  - Token budget-aware responses

------

## 3. Technical Specifications

### 3.1 Technology Stack

**Primary Language**: Python 3.10+

**Key Libraries**:

```
# Existing dependencies
- watchdog (>=3.0.0)          # Cross-platform file monitoring
- python-markdown (>=3.4)      # Markdown parsing
- PyYAML (>=6.0)               # Frontmatter parsing
- requests (>=2.31)            # External link validation
- whoosh (>=2.7.4)             # Full-text search indexing
- click (>=8.1)                # CLI framework
- python-daemon (>=3.0)        # Service daemonization
- sqlalchemy (>=2.0)           # Database ORM
- aiohttp (>=3.9)              # Async HTTP for link checking

# NEW: LLM Integration dependencies
- sentence-transformers (>=2.2) # Document embeddings
- numpy (>=1.24)               # Vector operations
- faiss-cpu (>=1.7)            # Efficient similarity search
- tiktoken (>=0.5)             # Token counting
- jinja2 (>=3.1)               # Response templating
```

### 3.2 Data Storage

**SQLite Database Schema** (Extended):

```sql
-- Document registry
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    filepath TEXT UNIQUE NOT NULL,
    title TEXT,
    created_at TIMESTAMP,
    modified_at TIMESTAMP,
    last_checked TIMESTAMP,
    checksum TEXT,
    word_count INTEGER,
    token_count INTEGER,           -- NEW: for LLM budget planning
    summary TEXT,                   -- NEW: auto-generated summary
    embedding_version INTEGER       -- NEW: track embedding model version
);

-- Document embeddings for semantic search
CREATE TABLE embeddings (
    document_id INTEGER PRIMARY KEY,
    embedding BLOB,                 -- Serialized numpy array
    model_name TEXT,                -- e.g., "all-MiniLM-L6-v2"
    generated_at TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

-- Semantic chunks for long documents
CREATE TABLE document_chunks (
    id INTEGER PRIMARY KEY,
    document_id INTEGER,
    chunk_index INTEGER,
    heading_path TEXT,              -- e.g., "Installation/Prerequisites"
    content TEXT,
    token_count INTEGER,
    embedding BLOB,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

-- LLM query cache
CREATE TABLE query_cache (
    id INTEGER PRIMARY KEY,
    query_hash TEXT UNIQUE,
    query_text TEXT,
    result_json TEXT,               -- Cached response
    created_at TIMESTAMP,
    hit_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP
);

-- Key concepts extracted from documents
CREATE TABLE concepts (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    category TEXT                   -- e.g., "technology", "procedure", "tool"
);

CREATE TABLE document_concepts (
    document_id INTEGER,
    concept_id INTEGER,
    relevance_score REAL,           -- 0.0 to 1.0
    FOREIGN KEY (document_id) REFERENCES documents(id),
    FOREIGN KEY (concept_id) REFERENCES concepts(id),
    PRIMARY KEY (document_id, concept_id)
);

-- Existing tables (links, tags, etc.)
-- ... [previous schema] ...
```

### 3.3 Configuration

**Configuration File**: `/etc/markdownkeeper/config.yaml`

```yaml
# Core settings
watch_directory: /var/docs/markdown
exclude_patterns:
  - "*.tmp"
  - ".git/*"
  - "node_modules/*"

# Processing settings
debounce_seconds: 2
batch_processing: true
max_batch_size: 50

# Link validation
external_link_check: true
link_check_interval: 86400  # 24 hours
http_timeout: 10
user_agent: "MarkdownKeeper/1.0"

# Organization rules
auto_organize: true
enforce_frontmatter: true
required_frontmatter_fields:
  - title
  - created
  - tags

# Indexing
index_directory: .markdownkeeper
generate_toc: true
toc_filename: "README.md"
max_toc_depth: 3

# 🤖 NEW: LLM Integration settings
llm:
  enabled: true
  embedding_model: "all-MiniLM-L6-v2"  # Fast, good quality
  chunk_size: 512                       # Tokens per chunk for long docs
  chunk_overlap: 50                     # Token overlap between chunks
  max_results: 10                       # Default max search results
  similarity_threshold: 0.5             # Min cosine similarity
  
  # Token budget management
  token_counting: true
  default_token_budget: 8000           # Conservative default
  
  # Caching
  cache_queries: true
  cache_ttl: 3600                      # 1 hour
  
  # Summary generation
  auto_summarize: true
  summary_max_tokens: 150
  
  # API settings
  api_enabled: true
  api_port: 8765
  api_bind: "127.0.0.1"               # Local only by default

# Service settings
log_level: INFO
log_file: /var/log/markdownkeeper/service.log
pid_file: /var/run/markdownkeeper.pid
database_path: /var/lib/markdownkeeper/index.db

# Notifications (optional)
notify_on_broken_links: true
notification_methods:
  - email
notification_email: admin@example.com
```

------

## 4. LLM Agent Integration Features

### 4.1 Query Interface

#### 4.1.1 CLI Query Interface

```bash
# Natural language search with semantic understanding
mdkeeper query "how to install docker on ubuntu"

# Structured output for programmatic consumption
mdkeeper query "kubernetes deployment guide" --format json

# Token-budget aware queries
mdkeeper query "all linux security procedures" --max-tokens 4000

# Progressive loading (get metadata first, then content on demand)
mdkeeper query "database backup procedures" --metadata-only

# Get specific document by ID without exploration
mdkeeper get-doc 42 --format markdown
```

#### 4.1.2 JSON-RPC API Interface

**Endpoint**: `http://localhost:8765/api/v1/query`

**Request**:

```json
{
  "jsonrpc": "2.0",
  "method": "semantic_query",
  "params": {
    "query": "how to configure nginx as reverse proxy",
    "max_results": 5,
    "max_tokens": 2000,
    "include_content": false,
    "include_summary": true,
    "min_similarity": 0.6
  },
  "id": 1
}
```

**Response**:

```json
{
  "jsonrpc": "2.0",
  "result": {
    "query": "how to configure nginx as reverse proxy",
    "total_matches": 8,
    "returned": 5,
    "token_budget_used": 847,
    "documents": [
      {
        "id": 156,
        "filepath": "guides/web-servers/nginx-reverse-proxy.md",
        "title": "NGINX Reverse Proxy Configuration",
        "similarity_score": 0.94,
        "token_count": 1250,
        "summary": "Complete guide for configuring NGINX as a reverse proxy, including SSL/TLS termination, load balancing, and common use cases.",
        "tags": ["nginx", "reverse-proxy", "web-server"],
        "created": "2024-01-15T10:30:00Z",
        "modified": "2024-02-01T14:22:00Z",
        "related_docs": [157, 158],
        "content_preview": "# NGINX Reverse Proxy Configuration\n\n## Overview\n\nThis guide covers setting up NGINX as a reverse proxy...",
        "key_sections": [
          "Installation",
          "Basic Configuration",
          "SSL/TLS Setup",
          "Load Balancing",
          "Troubleshooting"
        ]
      },
      {
        "id": 157,
        "filepath": "guides/web-servers/nginx-ssl-config.md",
        "title": "NGINX SSL/TLS Configuration",
        "similarity_score": 0.78,
        "token_count": 890,
        "summary": "Detailed SSL/TLS configuration for NGINX including certificate management and security best practices.",
        "tags": ["nginx", "ssl", "security"],
        "created": "2024-01-16T09:15:00Z",
        "modified": "2024-01-28T16:45:00Z"
      }
      // ... 3 more results
    ],
    "suggestions": [
      "For load balancing specifically, see document ID 234",
      "Related runbooks: server-deployment (ID 312)"
    ]
  },
  "id": 1
}
```

### 4.2 Optimized Response Formats

#### 4.2.1 Metadata-Only Response (Minimal Tokens)

```json
{
  "type": "metadata",
  "documents": [
    {
      "id": 156,
      "path": "guides/web-servers/nginx-reverse-proxy.md",
      "title": "NGINX Reverse Proxy Configuration",
      "score": 0.94,
      "tokens": 1250,
      "tags": ["nginx", "reverse-proxy"]
    }
  ],
  "token_cost": 45
}
```

#### 4.2.2 Summary Response (Low Tokens)

```json
{
  "type": "summary",
  "documents": [
    {
      "id": 156,
      "title": "NGINX Reverse Proxy Configuration",
      "summary": "Complete guide for configuring NGINX as a reverse proxy, including SSL/TLS termination, load balancing, and common use cases.",
      "sections": ["Installation", "Basic Configuration", "SSL/TLS Setup"],
      "tokens": 1250
    }
  ],
  "token_cost": 156
}
```

#### 4.2.3 Full Content Response (High Tokens)

```json
{
  "type": "full",
  "documents": [
    {
      "id": 156,
      "title": "NGINX Reverse Proxy Configuration",
      "content": "# NGINX Reverse Proxy Configuration\n\n...[full markdown]",
      "tokens": 1250
    }
  ],
  "token_cost": 1295
}
```

### 4.3 Manifest Files for Quick Discovery

#### 4.3.1 Generated LLM Manifest

**File**: `.markdownkeeper/llm-manifest.json`

```json
{
  "generated_at": "2024-02-06T14:32:00Z",
  "total_documents": 347,
  "total_tokens": 425680,
  "categories": {
    "guides": {
      "count": 89,
      "subcategories": {
        "installation": {"count": 23, "docs": [12, 15, 18, ...]},
        "configuration": {"count": 34, "docs": [45, 47, 52, ...]},
        "troubleshooting": {"count": 32, "docs": [78, 82, 89, ...]}
      }
    },
    "runbooks": {
      "count": 67,
      "subcategories": {
        "deployment": {"count": 18, "docs": [156, 167, 172, ...]},
        "maintenance": {"count": 25, "docs": [201, 209, 215, ...]},
        "incident-response": {"count": 24, "docs": [298, 301, 312, ...]}
      }
    },
    "reference": {
      "count": 191,
      "subcategories": {
        "api": {"count": 78, "docs": [...]},
        "cli": {"count": 56, "docs": [...]},
        "architecture": {"count": 57, "docs": [...]}
      }
    }
  },
  "top_concepts": [
    {
      "name": "docker",
      "document_count": 45,
      "related_docs": [12, 15, 23, 34, 56, ...]
    },
    {
      "name": "kubernetes",
      "document_count": 38,
      "related_docs": [78, 82, 91, 103, ...]
    },
    {
      "name": "nginx",
      "document_count": 27,
      "related_docs": [156, 157, 158, ...]
    }
  ],
  "quick_links": {
    "getting_started": [12, 15, 18],
    "common_tasks": [156, 234, 312],
    "troubleshooting": [78, 82, 89, 92]
  }
}
```

#### 4.3.2 Category Index Files

**File**: `.markdownkeeper/indexes/guides-installation.json`

```json
{
  "category": "guides/installation",
  "document_count": 23,
  "total_tokens": 28450,
  "documents": [
    {
      "id": 12,
      "path": "guides/installation/docker-ubuntu.md",
      "title": "Docker Installation on Ubuntu",
      "tokens": 1240,
      "summary": "Step-by-step guide for installing Docker Engine on Ubuntu 20.04 and 22.04",
      "tags": ["docker", "ubuntu", "installation"]
    },
    {
      "id": 15,
      "path": "guides/installation/kubernetes-cluster.md",
      "title": "Kubernetes Cluster Setup",
      "tokens": 2150,
      "summary": "Complete guide for setting up a production-ready Kubernetes cluster",
      "tags": ["kubernetes", "cluster", "installation"]
    }
    // ... more documents
  ]
}
```

### 4.4 Smart Query Processing

#### 4.4.1 Query Understanding

```python
# Example query processing flow
class LLMQueryEngine:
    def process_query(self, query: str, params: QueryParams):
        # 1. Parse intent
        intent = self.parse_intent(query)
        # Types: "find_document", "learn_concept", "get_instructions", "troubleshoot"
        
        # 2. Extract key concepts
        concepts = self.extract_concepts(query)
        # e.g., ["nginx", "reverse proxy", "configuration"]
        
        # 3. Determine search strategy
        if intent == "find_document":
            # Direct semantic search
            results = self.semantic_search(query, concepts)
        elif intent == "learn_concept":
            # Concept-based retrieval
            results = self.concept_search(concepts)
        elif intent == "get_instructions":
            # Prioritize guides and runbooks
            results = self.filtered_search(query, categories=["guides", "runbooks"])
        
        # 4. Rank and filter
        results = self.rerank_by_relevance(results)
        results = self.apply_token_budget(results, params.max_tokens)
        
        # 5. Format response
        return self.format_response(results, params.format)
```

#### 4.4.2 Concept Extraction

```python
# Auto-extracted concepts from query
QUERY: "How do I deploy a containerized application to production?"

EXTRACTED_CONCEPTS:
- docker (0.9 confidence)
- deployment (0.95 confidence)
- production (0.85 confidence)
- containers (0.9 confidence)

MATCHED_DOCUMENTS:
1. guides/deployment/docker-production.md (3 concepts matched)
2. runbooks/container-deployment.md (3 concepts matched)
3. guides/docker/best-practices.md (2 concepts matched)
```

### 4.5 Progressive Content Delivery

```bash
# LLM agent workflow example

# Step 1: Find relevant documents (minimal tokens)
$ mdkeeper query "nginx ssl setup" --metadata-only
{
  "matches": 5,
  "docs": [
    {"id": 157, "title": "NGINX SSL/TLS Configuration", "score": 0.92, "tokens": 890}
  ],
  "token_cost": 34
}

# Step 2: Get summary to verify relevance
$ mdkeeper get-doc 157 --summary
{
  "id": 157,
  "summary": "Detailed SSL/TLS configuration for NGINX including certificate management...",
  "sections": ["Prerequisites", "Certificate Setup", "NGINX Configuration", "Testing"],
  "token_cost": 67
}

# Step 3: Get specific section
$ mdkeeper get-doc 157 --section "NGINX Configuration"
{
  "section": "NGINX Configuration",
  "content": "## NGINX Configuration\n\nAdd the following to your nginx.conf...",
  "token_cost": 234
}

# Step 4: Get full document only if needed
$ mdkeeper get-doc 157 --full
{
  "content": "[full markdown content]",
  "token_cost": 890
}

# Total token cost: 34 + 67 + 234 = 335 tokens (vs 890 if loaded full doc immediately)
```

### 4.6 Specialized Query Commands

```bash
# Find by concept
mdkeeper find-concept "kubernetes" --limit 5

# Get related documents
mdkeeper related 156 --max 3

# Find by use case
mdkeeper find-use-case "database backup"

# Get document by exact path (zero exploration)
mdkeeper get "guides/web-servers/nginx-reverse-proxy.md"

# Search with filters
mdkeeper query "installation" --category guides --tags docker,ubuntu

# Token-budget optimizer
mdkeeper query "all deployment procedures" \
  --max-tokens 4000 \
  --optimize-coverage

# Get table of contents for category
mdkeeper toc guides/installation --format json
```

### 4.7 Embeddings Management

```bash
# Generate/update embeddings
mdkeeper embeddings generate

# Rebuild embeddings for specific category
mdkeeper embeddings rebuild --category guides

# Check embedding coverage
mdkeeper embeddings status
┌─────────────────────────────────────────────┐
│ Embedding Coverage Report                   │
├─────────────────────────────────────────────┤
│ Total Documents: 347                        │
│ Embedded: 347 (100%)                        │
│ Model: all-MiniLM-L6-v2                     │
│ Last Update: 2024-02-06 14:32              │
│ Pending Updates: 0                          │
└─────────────────────────────────────────────┘

# Change embedding model (triggers rebuild)
mdkeeper embeddings set-model "all-mpnet-base-v2"
```

------

## 5. Feature Specifications

### 5.1 File Organization

**Auto-Organization Rules**:

1. **Date-based Filing**: Move documents to `YYYY/MM/` subdirectories based on creation date
2. **Category-based Filing**: Organize by frontmatter `category` field
3. **Naming Standards**: Enforce kebab-case filenames
4. **Duplicate Detection**: Identify and flag duplicate content

**Example Frontmatter** (Extended):

```yaml
---
title: "System Installation Guide"
created: 2024-02-06
modified: 2024-02-06
tags: [linux, installation, tutorial]
category: guides
status: published

# NEW: LLM-specific metadata
summary: "Complete guide for installing and configuring the system"
concepts: [linux, installation, systemd, configuration]
difficulty: intermediate
estimated_reading_time: 15
token_count: 1420
---
```

### 5.2 Link Management

**Internal Link Validation**:

- Resolve relative paths (`./`, `../`)
- Track anchor references (`#heading`)
- Auto-update when files move
- Suggest similar paths for broken links

**External Link Validation**:

- Periodic HTTP HEAD requests
- Cache results to avoid rate limiting
- Retry with exponential backoff
- Support custom headers/authentication

**Link Repair Strategies**:

```
1. File moved → Update all references automatically
2. File deleted → Flag links, suggest alternatives
3. External 404 → Check Wayback Machine, flag for review
4. Redirects → Update to final destination
```

### 5.3 Index Generation

**Generated Indexes**:

1. **Directory README.md**:

   ```markdown
   # Directory Name
   
   ## Contents
   
   - [Document Title](./document-name.md) - Brief description (1420 tokens)
   - [Another Doc](./another-doc.md) - Brief description (890 tokens)
   
   ## Subdirectories
   
   - [Subfolder](./subfolder/) - 12 documents (15,340 tokens)
   ```

2. **Master Index** (`_index/master.md`):

   - Alphabetical listing
   - By category
   - By tag
   - Recently modified
   - **NEW: By concept**
   - **NEW: By token count**

3. **Search Index**:

   - Full-text search via Whoosh
   - **Semantic search via embeddings**
   - Queryable via CLI: `mdkeeper search "installation guide"`

4. **🤖 LLM Manifest** (`.markdownkeeper/llm-manifest.json`):

   - Optimized for programmatic consumption
   - Includes token counts and summaries
   - Category and concept hierarchies

### 5.4 Quality Checks

**Automated Checks**:

- [ ] Frontmatter presence and validity
- [ ] Heading hierarchy (no skipped levels)
- [ ] Minimum word count
- [ ] Image references valid
- [ ] No trailing whitespace
- [ ] Consistent line endings
- [ ] No duplicate headings in same document
- [ ] **NEW: Summary present and accurate**
- [ ] **NEW: Token count within reasonable range**

**Reports**:

```bash
$ mdkeeper report
┌─────────────────────────────────────────────┐
│ MarkdownKeeper Health Report                │
├─────────────────────────────────────────────┤
│ Total Documents: 347                        │
│ Total Tokens: 425,680                       │
│ Broken Internal Links: 12                   │
│ Broken External Links: 8                    │
│ Missing Frontmatter: 23                     │
│ Missing Summaries: 15                       │
│ Orphaned Documents: 5                       │
│ Embedding Coverage: 100%                    │
│ Last Full Scan: 2024-02-06 14:32           │
└─────────────────────────────────────────────┘
```

------

## 6. CLI Interface

### 6.1 Command Structure

```bash
# Service management
mdkeeper start              # Start daemon
mdkeeper stop               # Stop daemon
mdkeeper restart            # Restart daemon
mdkeeper status             # Show service status

# Operations
mdkeeper scan [PATH]        # Full scan and rebuild index
mdkeeper check-links        # Validate all links
mdkeeper organize           # Apply organization rules
mdkeeper repair             # Attempt to fix issues

# 🤖 LLM Query Interface
mdkeeper query QUERY [OPTIONS]        # Natural language search
mdkeeper get-doc ID [OPTIONS]         # Get specific document
mdkeeper find-concept CONCEPT         # Find by concept
mdkeeper related ID                   # Get related documents
mdkeeper toc PATH                     # Get category TOC

# Queries
mdkeeper search QUERY       # Full-text search
mdkeeper list [--tag TAG]   # List documents
mdkeeper info FILE          # Show document metadata
mdkeeper links FILE         # Show all links in/to file

# Reporting
mdkeeper report             # Generate health report
mdkeeper stats              # Show statistics

# 🤖 Embeddings Management
mdkeeper embeddings generate          # Generate embeddings
mdkeeper embeddings rebuild           # Rebuild all embeddings
mdkeeper embeddings status            # Show embedding coverage

# Configuration
mdkeeper config show        # Display current config
mdkeeper config set KEY VAL # Update configuration
mdkeeper init PATH          # Initialize watched directory

# 🤖 API Server
mdkeeper api start          # Start JSON-RPC API server
mdkeeper api stop           # Stop API server
```

### 6.2 LLM Agent Usage Examples

#### Example 1: Find Installation Instructions

```bash
# Agent needs to find docker installation docs
$ mdkeeper query "install docker on ubuntu" --metadata-only --format json

{
  "documents": [
    {
      "id": 12,
      "path": "guides/installation/docker-ubuntu.md",
      "title": "Docker Installation on Ubuntu",
      "score": 0.95,
      "tokens": 1240,
      "tags": ["docker", "ubuntu", "installation"]
    }
  ],
  "token_cost": 28
}

# Get just the summary first
$ mdkeeper get-doc 12 --summary --format json

{
  "id": 12,
  "summary": "Step-by-step guide for installing Docker Engine on Ubuntu 20.04 and 22.04, including repository setup, package installation, and post-installation configuration.",
  "sections": ["Prerequisites", "Add Docker Repository", "Install Docker", "Post-Install"],
  "token_cost": 52
}

# Load full content
$ mdkeeper get-doc 12 --full --format markdown > /tmp/docker-install.md
```

#### Example 2: Multi-Document Research

```bash
# Agent needs comprehensive nginx documentation
$ mdkeeper query "nginx configuration" --max-tokens 4000 --format json

{
  "documents": [
    {"id": 156, "title": "NGINX Reverse Proxy", "tokens": 1250, "priority": 1},
    {"id": 157, "title": "NGINX SSL/TLS", "tokens": 890, "priority": 2},
    {"id": 158, "title": "NGINX Performance Tuning", "tokens": 1650, "priority": 3}
  ],
  "total_tokens": 3790,
  "documents_truncated": 2,
  "token_budget_used": 3790
}

# Get all three documents
$ mdkeeper get-doc 156,157,158 --full
```

#### Example 3: Concept Exploration

```bash
# Agent wants to understand kubernetes-related documentation
$ mdkeeper find-concept "kubernetes" --format json

{
  "concept": "kubernetes",
  "document_count": 38,
  "related_concepts": ["docker", "containers", "orchestration", "helm"],
  "documents": [
    {"id": 78, "title": "Kubernetes Cluster Setup", "relevance": 0.95},
    {"id": 82, "title": "Kubernetes Deployment Guide", "relevance": 0.92},
    {"id": 91, "title": "Kubernetes Troubleshooting", "relevance": 0.88}
  ]
}
```

### 6.3 Example Workflows

**Initial Setup**:

```bash
# Install and configure
sudo pip install markdownkeeper
sudo mdkeeper init /var/docs/markdown

# Edit configuration
sudo nano /etc/markdownkeeper/config.yaml

# Generate initial embeddings
sudo mdkeeper embeddings generate

# Enable and start service
sudo systemctl enable markdownkeeper
sudo systemctl start markdownkeeper

# Start API server for LLM agents
sudo mdkeeper api start
```

**LLM Agent Integration** (e.g., Claude Code):

```bash
# In agent's tool configuration
{
  "name": "docs_query",
  "command": "mdkeeper query '{query}' --metadata-only --format json",
  "description": "Search documentation repository"
}

{
  "name": "docs_get",
  "command": "mdkeeper get-doc {id} --full --format markdown",
  "description": "Retrieve full document by ID"
}
```

------

## 7. Service Implementation

### 7.1 systemd Unit File

**File**: `/etc/systemd/system/markdownkeeper.service`

```ini
[Unit]
Description=MarkdownKeeper Document Management Service
After=network.target

[Service]
Type=forking
User=markdownkeeper
Group=markdownkeeper
PIDFile=/var/run/markdownkeeper.pid
ExecStart=/usr/local/bin/mdkeeper start
ExecStop=/usr/local/bin/mdkeeper stop
ExecReload=/usr/local/bin/mdkeeper restart
Restart=on-failure
RestartSec=5s

# Security hardening
PrivateTmp=true
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/docs/markdown /var/lib/markdownkeeper /var/log/markdownkeeper

[Install]
WantedBy=multi-user.target
```

### 7.2 API Server systemd Unit

**File**: `/etc/systemd/system/markdownkeeper-api.service`

```ini
[Unit]
Description=MarkdownKeeper LLM Query API
After=markdownkeeper.service
Requires=markdownkeeper.service

[Service]
Type=simple
User=markdownkeeper
Group=markdownkeeper
ExecStart=/usr/local/bin/mdkeeper api start --foreground
Restart=on-failure
RestartSec=5s

# Security
PrivateTmp=true
NoNewPrivileges=true
ProtectSystem=strict

[Install]
WantedBy=multi-user.target
```

### 7.3 Daemon Process

**Key Behaviors**:

- Fork to background on start
- Drop privileges after binding resources
- Graceful shutdown on SIGTERM
- Reload config on SIGHUP
- Write PID file
- Proper log rotation support
- **Automatic embedding regeneration on content changes**

### 7.4 Logging

**Log Levels**:

- **DEBUG**: File events, processing details, query details
- **INFO**: Service lifecycle, batch completions, API requests
- **WARNING**: Broken links, missing metadata, embedding failures
- **ERROR**: Processing failures, I/O errors, API errors
- **CRITICAL**: Service failures

**Log Format**:

```
2024-02-06 14:32:15 INFO [FileWatcher] Detected change: /var/docs/markdown/guides/install.md
2024-02-06 14:32:15 DEBUG [Processor] Parsing frontmatter
2024-02-06 14:32:16 INFO [EmbeddingManager] Regenerating embedding for doc_id=12
2024-02-06 14:32:16 WARNING [LinkValidator] Broken link in install.md: ./old-guide.md
2024-02-06 14:32:17 INFO [API] Query received: "install docker" (tokens: 28)
2024-02-06 14:32:17 DEBUG [QueryEngine] Semantic search returned 5 results
2024-02-06 14:32:17 INFO [IndexGenerator] Updated directory index
```

------

## 8. Performance Considerations

### 8.1 Resource Optimization

**Memory**:

- Stream large files instead of loading entirely
- LRU cache for parsed documents
- **LRU cache for embeddings (keep frequent docs in memory)**
- Periodic garbage collection
- Target: < 150MB RSS for 10,000 documents (including embeddings)

**CPU**:

- Event debouncing to avoid thrashing
- Batch processing of multiple events
- Async I/O for link validation
- **Batch embedding generation**
- **Use smaller embedding models for speed (all-MiniLM-L6-v2)**
- Nice level: 19 (lowest priority)

**I/O**:

- Use inotify instead of polling
- Batch database writes
- Compress old search indexes
- Read-only mode when inactive
- **Lazy-load embeddings from disk**

### 8.2 Scalability

**Tested Limits**:

- Documents: Up to 50,000 files
- Watch depth: 20 subdirectory levels
- Concurrent events: 100/second burst
- Database size: ~800MB for 50k docs (with embeddings)
- **Embedding generation: ~500 docs/minute on modest hardware**
- **Query latency: <100ms for semantic search**

**Optimization Strategies**:

- Incremental indexing
- Partial tree scans
- Database partitioning by date
- Archive old indexes
- **FAISS index for fast similarity search**
- **Precompute frequently accessed embeddings**

### 8.3 LLM Query Performance

**Optimization Techniques**:

1. **Query Result Caching**: Cache frequent queries for 1 hour
2. **Embedding Preloading**: Keep top 100 documents' embeddings in memory
3. **Lazy Content Loading**: Return metadata first, content on demand
4. **Batch Operations**: Process multiple doc retrievals in single DB query
5. **Connection Pooling**: Reuse DB connections for API requests

**Performance Targets**:

- Metadata-only query: <50ms
- Semantic search (5 results): <150ms
- Full document retrieval: <100ms
- Summary generation: <200ms

------

## 9. Testing Strategy

### 9.1 Unit Tests

```python
# Example test structure
tests/
├── test_file_watcher.py
├── test_content_processor.py
├── test_link_validator.py
├── test_index_generator.py
├── test_metadata_manager.py
├── test_llm_query_engine.py        # NEW
├── test_embedding_manager.py       # NEW
├── test_api_server.py              # NEW
└── fixtures/
    └── sample_docs/
```

**Coverage Target**: 85%+

### 9.2 Integration Tests

**Test Scenarios**:

1. Full scan of 1000-document repository
2. Rapid file creation (100 files/second)
3. Link validation with external timeouts
4. Service restart during processing
5. Configuration reload without downtime
6. **Semantic query accuracy (precision/recall)**
7. **Embedding generation for 1000 documents**
8. **API concurrent request handling (100 requests)**

### 9.3 Performance Tests

**Benchmarks**:

- Initial scan time vs. document count
- Memory usage over 24 hours
- Link check duration for 10k external URLs
- Index query response time
- **Embedding generation throughput**
- **Semantic search latency at scale**
- **API request throughput**

### 9.4 LLM Integration Tests

**Test Queries**:

1. "How do I install docker?" → Should find installation guides
2. "nginx ssl configuration" → Should rank SSL docs highest
3. "troubleshoot database connection" → Should find relevant runbooks
4. "kubernetes deployment best practices" → Should find guides + reference docs

**Evaluation Metrics**:

- Query precision @ 5
- Query recall @ 10
- Mean reciprocal rank (MRR)
- Token efficiency (tokens used vs. value delivered)

------

## 10. Security Considerations

### 10.1 Privilege Management

- Run as dedicated `markdownkeeper` user
- No root access required after installation
- Restricted filesystem access via systemd
- No network bind privileges needed (API is localhost-only by default)
- **API authentication for remote access (if enabled)**

### 10.2 Input Validation

- Sanitize all file paths (prevent directory traversal)
- Validate YAML frontmatter (prevent code injection)
- Limit external HTTP requests (prevent SSRF)
- Timeout all network operations
- **Validate and sanitize LLM query inputs**
- **Rate limiting on API endpoints**

### 10.3 Data Protection

- Read-only access to source documents
- Atomic file updates (write to temp + rename)
- Database backups before schema migrations
- No sensitive data in logs
- **Embeddings contain only semantic info, no raw sensitive data**
- **API access logs for audit trail**

### 10.4 API Security

**Default Configuration**:

- Bind to localhost only (`127.0.0.1:8765`)
- No authentication required for local access
- Rate limiting: 100 requests/minute per IP

**Production Configuration**:

```yaml
llm:
  api_enabled: true
  api_bind: "0.0.0.0"  # Allow remote access
  api_port: 8765
  api_auth:
    enabled: true
    method: "token"  # or "jwt"
    tokens:
      - "secure-random-token-here"
  rate_limit:
    enabled: true
    requests_per_minute: 60
```

------

## 11. Installation & Deployment

### 11.1 Installation Script

```bash
#!/bin/bash
# install.sh

set -e

echo "Installing MarkdownKeeper..."

# Create system user
sudo useradd -r -s /bin/false markdownkeeper

# Create directories
sudo mkdir -p /etc/markdownkeeper
sudo mkdir -p /var/lib/markdownkeeper
sudo mkdir -p /var/log/markdownkeeper

# Install Python package
sudo pip3 install markdownkeeper

# Install embedding model dependencies
sudo pip3 install sentence-transformers faiss-cpu

# Download default embedding model
echo "Downloading embedding model (this may take a few minutes)..."
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy default configuration
sudo cp config.yaml.example /etc/markdownkeeper/config.yaml

# Set permissions
sudo chown -R markdownkeeper:markdownkeeper /var/lib/markdownkeeper
sudo chown -R markdownkeeper:markdownkeeper /var/log/markdownkeeper

# Install systemd services
sudo cp markdownkeeper.service /etc/systemd/system/
sudo cp markdownkeeper-api.service /etc/systemd/system/
sudo systemctl daemon-reload

echo "Installation complete!"
echo "Edit /etc/markdownkeeper/config.yaml and run:"
echo "  sudo systemctl enable markdownkeeper"
echo "  sudo systemctl start markdownkeeper"
echo "  sudo systemctl enable markdownkeeper-api"
echo "  sudo systemctl start markdownkeeper-api"
```

### 11.2 Upgrade Path

```bash
# Stop services
sudo systemctl stop markdownkeeper markdownkeeper-api

# Backup database
sudo cp /var/lib/markdownkeeper/index.db \
        /var/lib/markdownkeeper/index.db.backup

# Upgrade package
sudo pip3 install --upgrade markdownkeeper

# Run migrations
sudo -u markdownkeeper mdkeeper migrate

# Rebuild embeddings if model changed
sudo -u markdownkeeper mdkeeper embeddings rebuild

# Start services
sudo systemctl start markdownkeeper markdownkeeper-api
```

------

## 12. Future Enhancements

### Phase 2 Features

- [ ] Git integration (commit changes, track history)
- [ ] Web UI dashboard for monitoring
- [ ] Plugin system for custom processors
- [ ] Multi-repository support
- [ ] Real-time collaboration conflict detection
- [ ] **Multi-modal embeddings (images, diagrams)**
- [ ] **Query suggestion/autocomplete**

### Phase 3 Features

- [ ] Machine learning for auto-tagging
- [ ] Similarity detection and deduplication
- [ ] Natural language document summarization
- [ ] Export to other formats (PDF, HTML, DocBook)
- [ ] Cloud storage backend support (S3, GCS)
- [ ] **Fine-tuned domain-specific embedding models**
- [ ] **LLM-powered document generation from templates**
- [ ] **Conversational query interface**

### Long-term Vision

- [ ] Distributed deployment across multiple nodes
- [ ] Advanced analytics and insights
- [ ] Automated documentation generation from code
- [ ] **Multi-agent collaboration support**
- [ ] **Knowledge graph visualization**
- [ ] **Integration with popular LLM frameworks (LangChain, LlamaIndex)**

------

## 13. Success Metrics

**Key Performance Indicators**:

1. **Uptime**: 99.9% service availability
2. **Accuracy**: <1% false positive broken links
3. **Performance**: <5 seconds to process file change
4. **Coverage**: 100% of markdown files indexed
5. **Efficiency**: <150MB memory for 5k documents (with embeddings)
6. **🤖 Query Accuracy**: >90% precision@5 for semantic search
7. **🤖 Token Efficiency**: <100 tokens average for metadata queries
8. **🤖 API Latency**: <150ms p95 for semantic search queries

**User Satisfaction**:

- Reduced time spent on manual documentation maintenance
- Improved documentation discoverability
- Fewer broken links in production documentation
- Faster onboarding for new team members
- **LLM agents can find relevant docs without manual exploration**
- **Average 70% token savings vs. loading full documents**

------

## 14. LLM Agent Integration Examples

### 14.1 Claude Code Integration

**.claude/tools/docs-search.json**:

```json
{
  "name": "search_docs",
  "description": "Search documentation repository for relevant guides, runbooks, and reference material",
  "command": "mdkeeper query '{query}' --metadata-only --max-results 10 --format json",
  "output_format": "json"
}
```

**.claude/tools/docs-get.json**:

```json
{
  "name": "get_document",
  "description": "Retrieve full content of a specific document by ID",
  "command": "mdkeeper get-doc {id} --full --format markdown",
  "output_format": "markdown"
}
```

### 14.2 VS Code Extension Integration

```javascript
// Extension API call
const results = await fetch('http://localhost:8765/api/v1/query', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    jsonrpc: '2.0',
    method: 'semantic_query',
    params: {
      query: userInput,
      max_results: 5,
      include_summary: true
    },
    id: 1
  })
});

const docs = await results.json();
// Display results in VS Code quick pick
```

### 14.3 Shell Script Integration

```bash
#!/bin/bash
# helper-script.sh - Find and display relevant documentation

QUERY="$1"

# Search for documents
RESULTS=$(mdkeeper query "$QUERY" --metadata-only --format json)

# Extract top result ID
DOC_ID=$(echo "$RESULTS" | jq -r '.documents[0].id')

if [ "$DOC_ID" != "null" ]; then
    echo "Found: $(echo "$RESULTS" | jq -r '.documents[0].title')"
    echo "Loading content..."
    mdkeeper get-doc "$DOC_ID" --full
else
    echo "No documentation found for: $QUERY"
fi
```

------

## Appendix A: File Structure Example

```
/var/docs/markdown/
├── .markdownkeeper/
│   ├── index.db                    # SQLite database with embeddings
│   ├── llm-manifest.json           # LLM-optimized manifest
│   ├── search_index/               # Whoosh full-text index
│   ├── embeddings_cache/           # Serialized embeddings
│   └── indexes/
│       ├── guides-installation.json
│       ├── runbooks-deployment.json
│       └── reference-api.json
├── _index/
│   ├── master.md
│   ├── by-category.md
│   ├── by-tag.md
│   └── by-concept.md               # NEW: Concept-based index
├── guides/
│   ├── README.md
│   ├── installation/
│   │   ├── README.md
│   │   ├── docker-ubuntu.md        # id: 12, tokens: 1240
│   │   └── kubernetes-cluster.md   # id: 15, tokens: 2150
│   └── configuration/
├── runbooks/
│   ├── README.md
│   └── deployment/
│       └── container-deploy.md     # id: 156, tokens: 1650
└── reference/
    └── README.md
```

------

## Appendix B: API Reference

### B.1 Query Endpoint

**POST** `/api/v1/query`

**Request**:

```json
{
  "jsonrpc": "2.0",
  "method": "semantic_query",
  "params": {
    "query": "string",
    "max_results": 10,
    "max_tokens": 8000,
    "include_content": false,
    "include_summary": true,
    "min_similarity": 0.5,
    "categories": ["guides"],
    "tags": ["docker"]
  },
  "id": 1
}
```

### B.2 Get Document Endpoint

**POST** `/api/v1/get_doc`

**Request**:

```json
{
  "jsonrpc": "2.0",
  "method": "get_document",
  "params": {
    "document_id": 156,
    "include_content": true,
    "include_related": true,
    "section": "Installation"
  },
  "id": 2
}
```

### B.3 Concept Search Endpoint

**POST** `/api/v1/find_concept`

**Request**:

```json
{
  "jsonrpc": "2.0",
  "method": "find_by_concept",
  "params": {
    "concept": "kubernetes",
    "max_results": 10,
    "include_related_concepts": true
  },
  "id": 3
}
```

------

**Document Version**: 2.0
 **Last Updated**: 2024-02-06
 **Author**: System Design
 **Status**: Ready for Implementation

**Key Enhancement**: LLM Agent Integration with token-optimized querying, semantic search, and progressive content delivery