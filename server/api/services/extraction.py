"""
Text extraction service for documents (PDF, DOCX, plain text)
"""
import base64
import io
import warnings
from pathlib import Path
from typing import Optional
import anthropic
from fastapi import HTTPException
from core.config import PDF_BATCH_SIZE, PDF_BATCHES_PER_MINUTE, PDF_MAX_BATCHES
from utils.logging import log
from utils.progress import send_progress

# Global Claude client instance
claude_client = None

# Rate limiting for PDF batches
last_batch_time = None


def init_claude_client(api_key: str, http_client=None):
    """Initialize Claude API client."""
    global claude_client
    if http_client:
        claude_client = anthropic.Anthropic(api_key=api_key, http_client=http_client)
    else:
        claude_client = anthropic.Anthropic(api_key=api_key)
    log("✅ Claude client initialized")


async def rate_limit_batch():
    """Rate limit PDF batch processing to avoid API rate limits."""
    global last_batch_time

    if PDF_BATCHES_PER_MINUTE <= 0:
        return  # No rate limiting

    min_interval = 60.0 / PDF_BATCHES_PER_MINUTE  # Seconds between batches

    if last_batch_time is not None:
        import time
        elapsed = time.time() - last_batch_time
        if elapsed < min_interval:
            wait_time = min_interval - elapsed
            log(f"   ⏸️  Rate limiting: waiting {wait_time:.1f}s before next batch...")
            import asyncio
            await asyncio.sleep(wait_time)

    import time
    last_batch_time = time.time()


async def extract_text_from_pdf_batch(content: bytes, filename: str, page_start: int, page_end: int) -> str:
    """Extract text from a range of PDF pages using Claude."""
    from PyPDF2 import PdfReader, PdfWriter

    # Suppress PyPDF2 warnings about PDF structure issues
    warnings.filterwarnings('ignore', category=UserWarning, module='PyPDF2')

    # Split PDF to page range
    reader = PdfReader(io.BytesIO(content))
    writer = PdfWriter()

    for page_num in range(page_start, min(page_end, len(reader.pages))):
        writer.add_page(reader.pages[page_num])

    # Write batch to bytes
    batch_buffer = io.BytesIO()
    writer.write(batch_buffer)
    batch_pdf = batch_buffer.getvalue()

    base64_pdf = base64.standard_b64encode(batch_pdf).decode("utf-8")

    try:
        log(f"   ⏳ Sending pages {page_start+1}-{page_end} to Claude API...")
        log(f"   DEBUG: PDF batch size: {len(base64_pdf)} base64 chars, ~{len(batch_pdf)} bytes")

        import time
        start_time = time.time()

        message = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=16000,
            timeout=300.0,  # 5 minute timeout per batch
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": base64_pdf,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Extract all text content from this PDF document. Preserve the structure including headings, paragraphs, and lists. Output only the extracted text, no commentary."
                    }
                ],
            }],
        )

        elapsed = time.time() - start_time
        log(f"   DEBUG: API call completed in {elapsed:.1f}s")

        usage = message.usage
        log(f"   ✅ Pages {page_start+1}-{page_end}: {usage.input_tokens} input tokens, {usage.output_tokens} output tokens")

        return message.content[0].text
    except anthropic.APITimeoutError as e:
        log(f"   ❌ Timeout on pages {page_start+1}-{page_end}: {str(e)}")
        raise HTTPException(status_code=504, detail=f"Claude API timeout on pages {page_start+1}-{page_end}")
    except anthropic.BadRequestError as e:
        log(f"   DEBUG: BadRequestError: {str(e)}")
        if "content filtering policy" in str(e):
            raise HTTPException(
                status_code=400,
                detail=f"PDF content blocked by content filtering policy (pages {page_start+1}-{page_end})"
            )
        raise HTTPException(status_code=400, detail=f"Claude API error on pages {page_start+1}-{page_end}: {str(e)}")
    except Exception as e:
        log(f"   ❌ UNEXPECTED ERROR in extract_text_from_pdf_batch: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


async def extract_text_from_pdf(content: bytes, filename: str, upload_id: Optional[str] = None) -> str:
    """Extract text from PDF using Claude's vision capability with batching for large files."""
    if not claude_client:
        raise HTTPException(status_code=500, detail="Claude API not configured")

    file_size_mb = len(content) / (1024 * 1024)
    log(f"📄 Processing PDF: {filename} ({file_size_mb:.1f}MB)")

    try:
        import pikepdf
        from PyPDF2 import PdfReader

        # Suppress PyPDF2 warnings about PDF structure issues
        warnings.filterwarnings('ignore', category=UserWarning, module='PyPDF2')

        # First, unlock/decrypt the PDF if it's protected using pikepdf
        log(f"🔓 Unlocking PDF (if protected)...")
        try:
            pdf = pikepdf.open(io.BytesIO(content))
            unlocked_buffer = io.BytesIO()
            pdf.save(unlocked_buffer)
            pdf.close()
            content = unlocked_buffer.getvalue()
            log(f"✅ PDF unlocked successfully")
        except Exception as e:
            log(f"⚠️  pikepdf unlock failed (may not be encrypted): {str(e)}")
            # Continue with original content if unlock fails

        # Get page count
        reader = PdfReader(io.BytesIO(content))
        total_pages = len(reader.pages)
        log(f"📚 PDF has {total_pages} pages")

        # For large PDFs (>5MB) or many pages (>50), process in batches
        if file_size_mb > 5 or total_pages > 50:
            log(f"📑 Large PDF detected - splitting into batches of {PDF_BATCH_SIZE} pages each")
            if PDF_BATCHES_PER_MINUTE > 0:
                log(f"⏱️  Rate limit: {PDF_BATCHES_PER_MINUTE} batches/minute")

            extracted_parts = []
            total_batches = (total_pages + PDF_BATCH_SIZE - 1) // PDF_BATCH_SIZE

            # Optional: Limit batches for testing
            if PDF_MAX_BATCHES is not None and PDF_MAX_BATCHES > 0 and total_batches > PDF_MAX_BATCHES:
                log(f"⚠️  Batch limit enabled: Processing {PDF_MAX_BATCHES} batches (out of {total_batches})")
                batches_to_process = PDF_MAX_BATCHES
            else:
                batches_to_process = total_batches

            for batch_num, batch_start in enumerate(range(0, total_pages, PDF_BATCH_SIZE), 1):
                # Stop after configured number of batches
                if batch_num > batches_to_process:
                    log(f"⚠️  Stopped after {batches_to_process} batches (PDF_MAX_BATCHES limit)")
                    break

                batch_end = min(batch_start + PDF_BATCH_SIZE, total_pages)
                log(f"⚙️  Processing batch {batch_num}/{total_batches} (pages {batch_start+1}-{batch_end})...")

                # Send progress update
                if upload_id:
                    await send_progress(upload_id, f"Processing {filename}: Batch {batch_num}/{total_batches} (pages {batch_start+1}-{batch_end})...")

                # Rate limit to avoid API limits
                if batch_num > 1:  # Don't wait before first batch
                    await rate_limit_batch()

                batch_text = await extract_text_from_pdf_batch(content, filename, batch_start, batch_end)
                extracted_parts.append(batch_text)

            # Combine all batches
            full_text = "\n\n".join(extracted_parts)
            log(f"✅ Extraction complete: {len(full_text):,} characters from {total_pages} pages ({total_batches} batches)")
            return full_text

        else:
            # Small PDF - process in one go
            log(f"⚙️  Processing all {total_pages} pages in single request...")
            base64_pdf = base64.standard_b64encode(content).decode("utf-8")

            message = claude_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=16000,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": base64_pdf,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Extract all text content from this PDF document. Preserve the structure including headings, paragraphs, and lists. Output only the extracted text, no commentary."
                        }
                    ],
                }],
            )

            usage = message.usage
            print(f"   📖 {usage.input_tokens} input tokens, {usage.output_tokens} output tokens")

            extracted_text = message.content[0].text
            print(f"✅ Extracted {len(extracted_text):,} characters")
            return extracted_text

    except anthropic.BadRequestError as e:
        if "content filtering policy" in str(e):
            raise HTTPException(
                status_code=400,
                detail="PDF content was blocked by Claude's content filtering policy. This can happen with certain documents. Try a different PDF or contact support if this persists."
            )
        raise HTTPException(status_code=400, detail=f"Claude API error: {str(e)}")
    except Exception as e:
        print(f"PDF extraction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"PDF extraction failed: {str(e)}")


async def extract_text_from_docx(content: bytes) -> str:
    """Extract text from DOCX file."""
    import zipfile
    from xml.etree import ElementTree

    text_parts = []

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        if 'word/document.xml' in zf.namelist():
            xml_content = zf.read('word/document.xml')
            tree = ElementTree.fromstring(xml_content)

            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            for para in tree.findall('.//w:p', ns):
                para_text = ''.join(node.text or '' for node in para.findall('.//w:t', ns))
                if para_text.strip():
                    text_parts.append(para_text)

    return '\n\n'.join(text_parts)


async def extract_text(content: bytes, filename: str, upload_id: Optional[str] = None) -> str:
    """Extract text from file based on extension."""
    ext = Path(filename).suffix.lower()

    if ext == '.pdf':
        return await extract_text_from_pdf(content, filename, upload_id)
    elif ext == '.docx':
        return await extract_text_from_docx(content)
    elif ext in {'.md', '.txt', '.org', '.rst', '.html', '.htm'}:
        # Try common encodings
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode('utf-8', errors='replace')
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
