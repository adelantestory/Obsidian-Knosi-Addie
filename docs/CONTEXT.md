# Knosi - Project Context

## Origin Story

This project was born on December 24, 2024 at 3:25 AM when the user asked:

> "I wonder how hard it would be for you to generate an app like Khoj that I could run in a Docker container that would function entirely the same way, but would not have the 10MB limit."

### The Problem We Were Solving

The user (Joshua) needed a way to index and chat with theological documents - specifically large PDFs like Christian History Magazine issues and other ministry-related materials. The goal was simple: upload documents, have them indexed, and be able to ask questions that get answered using the document content (RAG - Retrieval Augmented Generation).

### Solutions We Tried and Their Limitations

#### 1. Khoj (Self-Hosted)

We successfully deployed Khoj on a Vultr VPS with:
- Docker Compose setup
- PostgreSQL backend
- Obsidian plugin integration
- Resend email service for magic link authentication

**Limitations encountered:**
- **10MB file size limit** - This was the dealbreaker. Many theological PDFs exceed this limit.
- **Email service requirement** - Khoj doesn't support standard SMTP; only Resend API works for self-hosted auth
- **Complex multi-user architecture** - Overkill for single-user personal use
- **Web search default** - Tends to search the public web instead of indexed documents unless explicitly configured

#### 2. Claude Projects

We explored using Claude's Projects feature as an alternative:
- Supports PDFs up to 32MB and 100 pages
- Uses the same PDF parsing capability we tested earlier (successfully parsed a locked Christian History Magazine PDF that other OCR tools couldn't read)
- RAG activates automatically for large knowledge bases

**Limitations encountered:**
- **No API access** - The Projects knowledge base can only be populated manually through the UI
- **No automation possible** - We attempted to build a Puppeteer script to automate uploads, but this approach is brittle and UI-dependent
- **Not self-hosted** - Dependent on Anthropic's infrastructure and pricing

#### 3. Other Considerations

- **Standard PDF libraries** - Many couldn't parse the locked/protected PDFs the user had
- **Claude's native PDF support** - Proved excellent at extracting text from problematic PDFs, making it the ideal choice for document processing

## The Solution: Knosi

A minimal, self-hosted document RAG system with:
- **No file size limits** (configurable, default 100MB)
- **Claude API for PDF parsing** - Uses the same capability that successfully read locked PDFs
- **PostgreSQL + pgvector** - Production-ready vector storage with easy backups
- **Multiple sync options** - Obsidian plugin OR filesystem watcher, user's choice
- **Single-user focused** - No complex auth flows, just an API key

## Name Origin

**Knosi** comes from the Greek word *gnosis* (γνῶσις), meaning "knowledge" - specifically experiential or personal knowledge. The "k" spelling:
- Modernizes the name for tech branding
- Avoids religious connotations of "gnosis"
- Creates a unique, ownable brand

**Domain:** knosi.ai

## Core Design Principles

1. **Simplicity over features** - ~500 lines of Python vs Khoj's full application
2. **Leverage Claude's strengths** - Use Claude for both PDF parsing and chat (no separate OCR pipeline)
3. **Production-ready storage** - PostgreSQL over embedded databases for reliability and backups
4. **Flexible client options** - Support different workflows (Obsidian-only vs multi-editor)
5. **Cost-conscious** - Queue-based sync to batch API calls, hash-based deduplication to avoid re-indexing

## User Context

Joshua is:
- Founder/CEO of Discipled Church (nonprofit ministry with three business units)
- Works with theological documents, Bible study materials, Christian history resources
- Uses Obsidian as primary note-taking/document management tool
- Self-hosts services on Vultr VPS
- Comfortable with Docker, command line, and technical configuration
- Balancing ministry work with full-time Microsoft employment

The tool needs to be:
- Reliable enough for daily use
- Cost-effective (API calls cost money)
- Simple to maintain
- Able to handle large theological PDFs and reference materials
