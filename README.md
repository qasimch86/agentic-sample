# Agentic Chatbot - Command Guide

This chatbot supports structured commands using JSON and natural language. Below are the main features and how to use them:

## 1. Table Generation
- **Command:** Ask for a table, e.g., "Create a 5x3 table about project milestones."
- **Format:**
  - JSON: `{ "tasks": [{ "kind": "table", "params": { "rows": 5, "cols": 3, "title": "Project Milestones" } }] }`
  - Output: HTML `<table class="llm-table">...</table>`

## 2. List Generation
- **Command:** "List 7 key features of the app."
- **Format:**
  - JSON: `{ "tasks": [{ "kind": "list", "params": { "ordered": true, "count": 7, "topic": "Key Features" } }] }`
  - Output: HTML `<ol>...</ol>` or `<ul>...</ul>`

## 3. Formatting Sections
- **Command:** "Summarize the architecture in 3 sections, highlight main points."
- **Format:**
  - JSON: `{ "tasks": [{ "kind": "formatting", "params": { "title": "Architecture", "sections": 3, "emphasis": ["bold"] } }] }`
  - Output: HTML with `<h1>`, `<h2>`, `<strong>`, `<em>`

## 4. Flow Chart
- **Command:** "Show a flow chart for the login process."
- **Format:**
  - JSON: `{ "tasks": [{ "kind": "flow_chart", "params": { "topic": "Login Process" } }] }`
  - Output: HTML `<div class="mermaid">flowchart TD ...</div>`

## 5. Guardrails (Safety)
- Unsafe or policy-violating content is denied with a JSON response:
  - `{ "allowed": false, "reason": "Unsafe request" }`

## 6. Custom Prompts
- You can add your own prompt templates in `llm/prompts/custom_prompts.txt`.

## 7. System Prompt
- The chatbot is a helpful AI assistant for this website.

---

### Example Usage
- "Create a numbered list of 5 steps for deployment."
- "Generate a 3x3 table of user roles."
- "Show a flow chart for user registration."
- "Summarize the setup guide in 2 sections with bold and italic emphasis."

---
For advanced usage, refer to the prompt files in `llm/prompts/` for exact JSON schemas and output formats.
