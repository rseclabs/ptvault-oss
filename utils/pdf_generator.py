"""PDF generation utility for PTVault reports using WeasyPrint."""

import html
import logging
from io import BytesIO

logger = logging.getLogger(__name__)

try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
    HAS_WEASYPRINT = True
except (ImportError, OSError) as e:
    HAS_WEASYPRINT = False
    logger.warning(f"WeasyPrint not available: {str(e)}. PDF export will fall back to browser print dialog.")


def _data_only_url_fetcher():
    """A WeasyPrint URL fetcher that loads only data: URLs.

    Report content is user-controlled; with the default fetcher an
    <a rel="attachment" href="file://..."> or <img src="file://..."> embeds a
    server file (the database, its key) in the PDF, and http(s) URLs make the
    server send requests. Images in reports are inline data: URLs.
    """
    try:
        from weasyprint.urls import URLFetcher  # WeasyPrint 68+
        return URLFetcher(allowed_protocols={'data'})
    except ImportError:
        from weasyprint.urls import default_url_fetcher  # older WeasyPrint

        def fetcher(url, *args, **kwargs):
            if not url.lower().startswith('data:'):
                raise ValueError(f"external resource blocked: {url.split(':', 1)[0]}")
            return default_url_fetcher(url, *args, **kwargs)
        return fetcher


def generate_pdf_from_html(html_content, report_name=None):
    """
    Generate a PDF file from HTML content.

    Args:
        html_content (str): Complete HTML document as string
        report_name (str, optional): Report name for logging

    Returns:
        bytes: PDF file content as bytes

    Raises:
        ImportError: If WeasyPrint is not installed
        Exception: If PDF generation fails
    """
    if not HAS_WEASYPRINT:
        raise ImportError("WeasyPrint is not installed. Run: pip install WeasyPrint>=60.0")

    try:
        logger.info(f"Generating PDF for report: {report_name or 'Untitled'}")

        # Create font configuration for better font handling
        font_config = FontConfiguration()

        # Generate PDF with proper font configuration
        pdf_bytes = HTML(string=html_content, url_fetcher=_data_only_url_fetcher()).write_pdf(
            font_config=font_config
        )

        logger.info(f"PDF generated successfully: {len(pdf_bytes)} bytes")
        return pdf_bytes

    except Exception as e:
        logger.error(f"Failed to generate PDF: {str(e)}")
        raise Exception(f"PDF generation failed: {str(e)}")


def get_print_css():
    """
    Get CSS optimized for PDF/print output.

    Returns:
        str: CSS rules for print media
    """
    return '''
        /* Print-specific styles */
        @page {
            size: A4;
            margin: 2cm 1.5cm;

            @bottom-center {
                content: counter(page) " of " counter(pages);
                font-size: 9pt;
                color: #666;
            }
        }

        /* Prevent page breaks inside important elements */
        .preview-finding,
        .preview-narrative,
        .preview-codeblock,
        .preview-table,
        .preview-keyfinding,
        .preview-evidence {
            break-inside: avoid;
            page-break-inside: avoid;
        }

        /* Force page breaks */
        .preview-pagebreak {
            break-after: page;
            page-break-after: always;
            visibility: hidden;
            height: 0;
            margin: 0;
            padding: 0;
        }

        /* Section headers should stay with following content */
        .preview-sectionheader {
            break-after: avoid;
            page-break-after: avoid;
        }

        /* Table handling */
        .preview-table table {
            break-inside: auto;
        }

        .preview-table tr {
            break-inside: avoid;
            page-break-inside: avoid;
        }

        /* Keep headers visible on every page for tables */
        .preview-table thead {
            display: table-header-group;
        }

        /* Optimize font rendering for print */
        body {
            font-size: 10pt;
            line-height: 1.4;
        }

        /* Adjust code blocks for print */
        .preview-codeblock pre,
        .preview-commandoutput {
            font-size: 8pt;
            line-height: 1.3;
            overflow: visible;
            white-space: pre-wrap;
            word-wrap: break-word;
        }

        /* Two-column layout should stay together */
        .preview-twocolumn {
            break-inside: avoid;
            page-break-inside: avoid;
        }

        /* Timeline should not break awkwardly */
        .preview-timeline .timeline-step {
            break-inside: avoid;
            page-break-inside: avoid;
        }
    '''


def generate_pdf_with_cover(html_content, engagement_data=None, report_name=None):
    """
    Generate a PDF with a cover page and engagement details.

    Args:
        html_content (str): Report HTML content
        engagement_data (dict, optional): Engagement metadata (name, client, dates, etc.)
        report_name (str, optional): Report name

    Returns:
        bytes: PDF file content with cover page
    """
    if not HAS_WEASYPRINT:
        raise ImportError("WeasyPrint is not installed. Run: pip install WeasyPrint>=60.0")

    # Generate cover page HTML
    cover_html = _generate_cover_page(engagement_data, report_name)

    # Combine cover with report content
    # Extract body content from the report HTML
    import re
    body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.DOTALL)
    if body_match:
        report_body = body_match.group(1)
    else:
        report_body = html_content

    # Build complete HTML with cover
    full_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{html.escape(report_name or "PTVault Report")}</title>
    {_get_combined_styles()}
</head>
<body>
    {cover_html}
    <div class="page-break"></div>
    {report_body}
</body>
</html>'''

    return generate_pdf_from_html(full_html, report_name)


def _generate_cover_page(engagement_data, report_name):
    """Generate HTML for cover page."""
    if not engagement_data:
        engagement_data = {}

    # Every field is user-controlled text: escape it before it reaches WeasyPrint.
    title = html.escape(str(report_name or engagement_data.get('name') or 'Penetration Test Report'))
    client = html.escape(str(engagement_data.get('client_name') or engagement_data.get('client') or ''))
    start_date = html.escape(str(engagement_data.get('start_date') or ''))
    end_date = html.escape(str(engagement_data.get('end_date') or ''))

    # Format dates if present
    date_range = ''
    if start_date or end_date:
        if start_date and end_date:
            date_range = f'<p class="cover-dates">{start_date} to {end_date}</p>'
        elif start_date:
            date_range = f'<p class="cover-dates">Started: {start_date}</p>'
        elif end_date:
            date_range = f'<p class="cover-dates">Completed: {end_date}</p>'

    client_html = f'<p class="cover-client">{client}</p>' if client else ''

    return f'''
    <div class="cover-page">
        <div class="cover-content">
            <h1 class="cover-title">{title}</h1>
            {client_html}
            {date_range}
        </div>
        <div class="cover-footer">
            <p>Generated by PTVault</p>
        </div>
    </div>
    '''


def _get_combined_styles():
    """Get combined CSS for cover page and report."""
    return f'''
    <style>
        /* Cover page styles */
        .cover-page {{
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            height: 100vh;
            page-break-after: always;
        }}

        .cover-content {{
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
        }}

        .cover-title {{
            font-size: 2.5rem;
            font-weight: 700;
            color: #1a202c;
            margin-bottom: 1.5rem;
            line-height: 1.2;
        }}

        .cover-client {{
            font-size: 1.5rem;
            color: #4a5568;
            margin-bottom: 1rem;
        }}

        .cover-dates {{
            font-size: 1rem;
            color: #718096;
        }}

        .cover-footer {{
            text-align: center;
            padding: 2rem;
            color: #718096;
            font-size: 0.9rem;
        }}

        .page-break {{
            page-break-after: always;
        }}

        /* Report styles with print optimizations */
        {get_print_css()}
    </style>
    '''
