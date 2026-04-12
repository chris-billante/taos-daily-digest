"""
Improved email formatter for taos-daily-digest
Fixes:
1. Strips Claude jargon/preamble ("I'll search for...", "Let me...")
2. Shows actual search parameters used
3. Cleaner HTML structure
"""

import re


def strip_claude_preamble(text: str) -> str:
    """
    Remove Claude's narration/preamble from responses.
    Patterns to remove:
    - "I'll search for..." / "Let me search..." / "I searched for..."
    - "Here's what I found..." / "I found..."
    - "Based on my search..." / "According to..."
    - Single-sentence intros before actual content
    """
    lines = text.split('\n')

    # Patterns that indicate Claude narration
    preamble_patterns = [
        r"^I'll\s",
        r"^I\s+searched\s+for",
        r"^Let\s+me\s+search",
        r"^Here's\s+what\s+I\s+found",
        r"^I\s+found\s+the\s+following",
        r"^Based\s+on\s+my\s+search",
        r"^According\s+to\s+my\s+search",
        r"^Here\s+are\s+the\s+results",
        r"^I've\s+searched",
        r"^After\s+searching",
    ]

    cleaned_lines = []

    for line in lines:
        stripped = line.strip()

        # Skip empty lines at start
        if not cleaned_lines and not stripped:
            continue

        # Check if this line is preamble
        is_preamble = any(re.match(pattern, stripped, re.IGNORECASE) for pattern in preamble_patterns)

        if is_preamble:
            # Skip this line and check if next line is also intro fluff
            continue

        cleaned_lines.append(line)

    result = '\n'.join(cleaned_lines)

    # Remove leading empty lines from final result
    result = result.lstrip('\n')

    return result


def extract_search_params(prompt: str) -> dict[str, str]:
    """
    Extract the actual search intent from the prompt.
    Returns a human-readable description of what was searched.
    """
    # Map prompt files to search descriptions
    search_descriptions = {
        'land_listings': 'Taos County RA-zoned land: 2-3 acres, under $60K, legal road access',
        'builder_intelligence': 'Zook Cabins, Mighty Small Homes, DC Structures: pricing, lead times, NM compliance updates',
        'offgrid_news': 'EG4 solar systems, off-grid HVAC, cistern/well systems, NM off-grid forums',
        'nm_regulatory': 'NM CID modular rules, Taos County zoning, IRC compliance, construction loan lenders',
        'van_market': 'Sprinter van market trends, optimal sale timing, current market conditions',
        'vehicle_search': 'Toyota Tacoma Double Cab Long Bed 4WD: 2020-2023, under $40K, under 60K miles',
        'bridge_housing': 'Taos short-term rentals, yurts compatible with EG4 solar, used fifth wheels'
    }

    # Try to identify which prompt this is from the content
    for key, description in search_descriptions.items():
        if key.replace('_', ' ').lower() in prompt.lower():
            return {
                'query_type': key.replace('_', ' ').title(),
                'search_params': description
            }

    return {
        'query_type': 'General Research',
        'search_params': 'Current market conditions and availability'
    }


def markdown_to_html(markdown_text: str) -> str:
    """
    Convert markdown to HTML with proper list handling.
    Handles: headers, bold, italic, links, lists (nested), code blocks.
    """
    html = markdown_text

    # Code blocks first (before other conversions)
    html = re.sub(r'```(\w+)?\n(.*?)\n```', r'<pre><code>\2</code></pre>', html, flags=re.DOTALL)

    # Headers (h1-h4)
    html = re.sub(r'^#### (.*?)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

    # Bold and italic
    html = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', html)
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    html = re.sub(r'__(.+?)__', r'<strong>\1</strong>', html)
    html = re.sub(r'_(.+?)_', r'<em>\1</em>', html)

    # Links
    html = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', html)

    # Process lists with proper nesting
    html = process_lists(html)

    # Paragraphs (but not for lines that are already wrapped in tags)
    lines = html.split('\n')
    processed_lines = []
    in_block = False

    for line in lines:
        stripped = line.strip()

        # Check if we're in a block element
        if stripped.startswith('<pre>') or stripped.startswith('<ul>') or stripped.startswith('<ol>'):
            in_block = True
        if stripped.endswith('</pre>') or stripped.endswith('</ul>') or stripped.endswith('</ol>'):
            in_block = False

        # Don't wrap lines that are already HTML elements or empty
        if (stripped.startswith('<') or not stripped or in_block):
            processed_lines.append(line)
        else:
            processed_lines.append(f'<p>{line}</p>')

    html = '\n'.join(processed_lines)

    # Clean up excessive blank lines (more than 2 consecutive)
    html = re.sub(r'\n{3,}', '\n\n', html)

    return html


def process_lists(text: str) -> str:
    """
    Convert markdown lists to HTML with proper nesting.
    Handles both unordered (-,*,+) and ordered (1.,2.) lists.
    """
    lines = text.split('\n')
    result = []
    list_stack = []  # Track nested list levels

    for line in lines:
        # Check for list items
        unordered_match = re.match(r'^(\s*)[-*+]\s+(.+)$', line)
        ordered_match = re.match(r'^(\s*)(\d+)\.\s+(.+)$', line)

        if unordered_match:
            indent = len(unordered_match.group(1))
            content = unordered_match.group(2)
            handle_list_item(result, list_stack, indent, content, 'ul')
        elif ordered_match:
            indent = len(ordered_match.group(1))
            content = ordered_match.group(3)
            handle_list_item(result, list_stack, indent, content, 'ol')
        else:
            # Close all open lists when we hit non-list content
            while list_stack:
                list_type, _ = list_stack.pop()
                result.append(f'</{list_type}>')
            result.append(line)

    # Close any remaining open lists
    while list_stack:
        list_type, _ = list_stack.pop()
        result.append(f'</{list_type}>')

    return '\n'.join(result)


def handle_list_item(result: list[str], list_stack: list, indent: int, content: str, list_type: str):
    """Helper to handle a single list item with proper nesting."""

    # Close lists that are deeper than current indent
    while list_stack and list_stack[-1][1] > indent:
        old_type, _ = list_stack.pop()
        result.append(f'</{old_type}>')

    # Open new list if needed
    if not list_stack or list_stack[-1][1] < indent:
        result.append(f'<{list_type}>')
        list_stack.append((list_type, indent))

    # Add the list item
    result.append(f'<li>{content}</li>')


def format_section_card(title: str, content: str, search_params: str = None) -> str:
    """
    Format a section as a clean card with optional search params display.
    """
    # Strip Claude preamble from content
    cleaned_content = strip_claude_preamble(content)

    # Convert markdown to HTML
    html_content = markdown_to_html(cleaned_content)

    # Build search params line if provided
    params_html = ''
    if search_params:
        params_html = f'''
        <div style="background: #f8f9fa; border-left: 3px solid #007bff; padding: 8px 12px; margin-bottom: 12px; font-size: 13px; color: #495057;">
            <strong>Search:</strong> {search_params}
        </div>
        '''

    card_html = f'''
    <div style="background: white; border: 1px solid #dee2e6; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
        <h2 style="color: #2c3e50; margin-top: 0; margin-bottom: 15px; font-size: 20px; border-bottom: 2px solid #3498db; padding-bottom: 8px;">
            {title}
        </h2>
        {params_html}
        <div style="color: #2c3e50; line-height: 1.6;">
            {html_content}
        </div>
    </div>
    '''

    return card_html


def build_daily_digest_email(sections: list[dict], date_str: str) -> str:
    """
    Build the complete daily digest email HTML.
    
    sections: List of dicts with keys 'title', 'content', 'search_params' (optional)
    """

    # Build section cards
    section_cards = []
    for section in sections:
        title = section.get('title', 'Untitled Section')
        content = section.get('content', '')
        search_params = section.get('search_params')

        card_html = format_section_card(title, content, search_params)
        section_cards.append(card_html)

    sections_html = '\n'.join(section_cards)

    # Complete email template
    email_html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                line-height: 1.6;
                color: #2c3e50;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f6fa;
            }}
            a {{
                color: #3498db;
                text-decoration: none;
            }}
            a:hover {{
                text-decoration: underline;
            }}
            pre {{
                background: #f8f9fa;
                padding: 12px;
                border-radius: 4px;
                overflow-x: auto;
            }}
            code {{
                font-family: "SF Mono", Monaco, Consolas, monospace;
                font-size: 13px;
            }}
            ul, ol {{
                margin: 10px 0;
                padding-left: 25px;
            }}
            li {{
                margin: 5px 0;
            }}
            h1, h2, h3, h4 {{
                margin-top: 0;
            }}
            p {{
                margin: 10px 0;
            }}
        </style>
    </head>
    <body>
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px; margin-bottom: 30px; text-align: center;">
            <h1 style="margin: 0; font-size: 28px;">Taos Off-Grid Build Daily Digest</h1>
            <p style="margin: 10px 0 0 0; font-size: 16px; opacity: 0.9;">{date_str}</p>
        </div>
        
        {sections_html}
        
        <div style="text-align: center; padding: 20px; color: #6c757d; font-size: 13px; border-top: 1px solid #dee2e6; margin-top: 30px;">
            <p>Automated digest generated by taos-daily-digest agent</p>
            <p style="margin: 5px 0;">Running on GitHub Actions • Powered by Claude Haiku 4.5</p>
        </div>
    </body>
    </html>
    '''

    return email_html


# Example usage
if __name__ == '__main__':
    # Test the formatter
    test_sections = [
        {
            'title': 'Land Listings',
            'content': '''I'll search for available land listings in the Taos area.

Here's what I found:

## Active Listings

- **Parcel A**: 3 acres in Tres Piedras - $45,000
  - Legal road access
  - Cistern water system possible
  - [View listing](https://example.com/listing1)

- **Parcel B**: 2.5 acres in Carson area - $52,000
  - Good southern exposure
  - Power nearby
  - [View listing](https://example.com/listing2)

Based on my search, both properties meet your criteria.''',
            'search_params': 'Taos County RA-zoned land: 2-3 acres, under $60K, legal road access'
        }
    ]

    html = build_daily_digest_email(test_sections, 'Monday, March 24, 2026')
    print(html)
