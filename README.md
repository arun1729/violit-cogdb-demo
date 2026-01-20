# Violit Blog Demo (CogDB Version)

A [CogDB](https://github.com/arun1729/cog) port of the original SQLite-based [Violit Blog demo](https://github.com/violit-dev/violit/tree/main/examples/2_violit_blog).

## Quick Start

```bash
pip install violit cogdb
python blog.py
```

Open http://localhost:8000 in your browser.

## Data Model

```mermaid
graph LR
    subgraph Users Graph
        U[username] -->|password| P[password_value]
        U -->|user_id| UID[user_id_value]
    end
    
    subgraph Posts Graph
        POST[post_id] -->|_type| T[post]
        POST -->|title| TITLE[title_value]
        POST -->|content| CONTENT[content_value]
        POST -->|author_name| AUTHOR[author_name]
        POST -->|user_id| PUID[user_id]
        POST -->|created_at| DATE[timestamp]
        USERID[user_id] -->|has_post| POST
    end
```

## Query Pattern

Uses CogDB's chained `out().tag().inc()` pattern to retrieve all properties in a single traversal:

```python
posts_graph.v().has("_type", "post").tag("post_id") \
    .out('title').tag('title').inc('title') \
    .out('content').tag('content').inc('content') \
    .out('author_name').tag('author_name').all()
```
