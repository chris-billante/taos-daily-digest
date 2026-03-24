"""
HCI Expert Review: Taos Daily Digest Email Design
==================================================

CURRENT STATE PROBLEMS:
1. Cognitive overload: 7 sections in one email is too much to process
2. No clear prioritization or hierarchy of importance
3. Action paths unclear: user doesn't know what to do with each section
4. Competing CTAs: multiple links per section with no clear primary action
5. No progressive disclosure: everything shown at once
6. Scan-unfriendly: dense paragraphs make quick review difficult

CORE PRINCIPLE:
Email is an interrupt medium. People scan, don't read. The digest should:
- Support 10-second scan with value extraction
- Make 1 clear action obvious per section
- Reduce decisions, not increase them

RECOMMENDATIONS:

═══════════════════════════════════════════════════════════════════════════

R1: PRIORITY RANKING SYSTEM
═══════════════════════════════════════════════════════════════════════════

Instead of flat sections, use visual priority tiers:

🔴 HIGH PRIORITY (action needed today)
🟡 MEDIUM PRIORITY (review this week)  
🟢 LOW PRIORITY (FYI / background intel)

Implementation:
- Color-coded left border on cards (red/yellow/green)
- Priority icon in header
- High priority sections appear first
- Use constraints.json thresholds to auto-assign priority:
  * Land under $50K = high priority
  * Builder price increases = high priority
  * Generic market updates = low priority

═══════════════════════════════════════════════════════════════════════════

R2: SINGLE PRIMARY CTA PER SECTION
═══════════════════════════════════════════════════════════════════════════

BEFORE (bad):
- View listing
- See photos
- Contact realtor
- Save to favorites
- Compare prices

AFTER (good):
- ONE big button: "View on Zillow" or "Call Page Sullivan Group"

Secondary actions go in a "More options" collapsible or small text links.

═══════════════════════════════════════════════════════════════════════════

R3: SCANNABLE STRUCTURE
═══════════════════════════════════════════════════════════════════════════

Every section should have this structure:

┌─────────────────────────────────────────┐
│ 🔴 SECTION TITLE                        │
│ One-line summary (the "so what")        │
├─────────────────────────────────────────┤
│ Key finding #1                          │
│ Key finding #2                          │
│ Key finding #3                          │
├─────────────────────────────────────────┤
│ [PRIMARY ACTION BUTTON]                 │
└─────────────────────────────────────────┘

Maximum 3 key findings per section.
If more findings exist, use "View 4 more →" progressive disclosure.

═══════════════════════════════════════════════════════════════════════════

R4: SMART TRUNCATION
═══════════════════════════════════════════════════════════════════════════

Don't show 12 land listings. Show:
- Top 3 matches
- "View 9 more listings →" link to tracking issue

Benefits:
- Reduced decision fatigue
- Faster email load time
- Forces prioritization of best matches

═══════════════════════════════════════════════════════════════════════════

R5: MOBILE-FIRST DESIGN
═══════════════════════════════════════════════════════════════════════════

80% of emails opened on mobile. Current design problems:
- Side-by-side layouts break on mobile
- Small tap targets (links need 44px minimum)
- Horizontal scrolling required for wide tables

Fix:
- Single column layout
- Large touch-friendly buttons (min 44px height)
- No tables (use stacked cards instead)
- Test on iPhone SE screen width (320px)

═══════════════════════════════════════════════════════════════════════════

R6: ATTENTION-BASED LOADING
═══════════════════════════════════════════════════════════════════════════

Current: All 7 sections load at once
Better: Progressive disclosure based on attention

Pattern:
1. Header with date + weather
2. HIGH PRIORITY sections (expanded)
3. MEDIUM PRIORITY sections (collapsed by default, click to expand)
4. LOW PRIORITY sections (link to web view, not in email)

Trade-off: Requires HTML+CSS collapsible sections (limited email client support)
Fallback: All sections visible but visually de-emphasized via opacity/size

═══════════════════════════════════════════════════════════════════════════

R7: FEEDBACK FRICTION REDUCTION
═══════════════════════════════════════════════════════════════════════════

Current: "Add feedback" requires navigating to GitHub, finding issue, commenting
Better: One-click feedback buttons embedded in email

Implementation options:

OPTION A: GitHub Issue templates with pre-filled content
- Email contains links like: 
  github.com/user/repo/issues/new?title=Digest%20Feedback&body=Section:%20Land%20Listings%0ARelevance:%20👍

OPTION B: Google Forms embedded feedback
- Simple 1-5 rating: "Was today's Land Listings section useful?"
- Results logged to Google Sheets
- No GitHub account needed

OPTION C: mailto: links (simplest)
- Click "This section was not useful" → opens email to yourself
- Subject pre-filled: "Digest Feedback: Land Listings - Not Useful"
- You reply with details if desired, or just send as-is for tracking

═══════════════════════════════════════════════════════════════════════════

IMPLEMENTATION CODE: IMPROVED EMAIL STRUCTURE
═══════════════════════════════════════════════════════════════════════════
"""


def build_improved_section_card(
    title: str,
    summary: str,
    findings: list,
    primary_cta: dict,
    priority: str = "medium",
    show_more_url: str = None
):
    """
    Build HCI-optimized section card.
    
    Args:
        title: Section heading
        summary: One-line "so what" statement
        findings: List of 1-3 key bullet points (strings)
        primary_cta: Dict with 'text' and 'url' keys
        priority: 'high', 'medium', or 'low'
        show_more_url: Optional URL for "View more" link
    """
    
    # Priority color mapping
    priority_colors = {
        'high': {
            'border': '#e74c3c',
            'icon': '🔴',
            'label': 'HIGH PRIORITY'
        },
        'medium': {
            'border': '#f39c12',
            'icon': '🟡',
            'label': 'REVIEW THIS WEEK'
        },
        'low': {
            'border': '#95a5a6',
            'icon': '🟢',
            'label': 'BACKGROUND INFO'
        }
    }
    
    p_config = priority_colors.get(priority, priority_colors['medium'])
    
    # Build findings HTML
    findings_html = ""
    for finding in findings[:3]:  # Max 3 findings
        findings_html += f'''
        <div style="background: #f8f9fa; padding: 12px; margin: 8px 0; border-radius: 6px; border-left: 3px solid {p_config['border']};">
            <p style="margin: 0; color: #2c3e50; font-size: 15px;">{finding}</p>
        </div>
        '''
    
    # Show more link if provided
    show_more_html = ""
    if show_more_url:
        remaining_count = max(0, len(findings) - 3)
        if remaining_count > 0:
            show_more_html = f'''
            <p style="text-align: center; margin: 15px 0;">
                <a href="{show_more_url}" style="color: #3498db; font-size: 14px; text-decoration: none;">
                    View {remaining_count} more → 
                </a>
            </p>
            '''
    
    # Primary CTA button
    cta_html = f'''
    <div style="text-align: center; margin: 20px 0;">
        <a href="{primary_cta['url']}" 
           style="display: inline-block; background: {p_config['border']}; color: white; 
                  padding: 14px 32px; border-radius: 8px; text-decoration: none; 
                  font-weight: 600; font-size: 16px; min-width: 200px;">
            {primary_cta['text']}
        </a>
    </div>
    '''
    
    # Complete card
    card_html = f'''
    <div style="background: white; border: 1px solid #dee2e6; border-left: 5px solid {p_config['border']}; 
                border-radius: 8px; padding: 24px; margin-bottom: 20px;">
        
        <!-- Priority badge -->
        <div style="color: {p_config['border']}; font-size: 12px; font-weight: 700; 
                    text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">
            {p_config['icon']} {p_config['label']}
        </div>
        
        <!-- Section title -->
        <h2 style="color: #2c3e50; margin: 0 0 8px 0; font-size: 22px;">
            {title}
        </h2>
        
        <!-- One-line summary -->
        <p style="color: #7f8c8d; font-size: 16px; margin: 0 0 20px 0; font-style: italic;">
            {summary}
        </p>
        
        <!-- Key findings -->
        {findings_html}
        
        <!-- Show more link -->
        {show_more_html}
        
        <!-- Primary CTA -->
        {cta_html}
    </div>
    '''
    
    return card_html


def build_feedback_widget(section_name: str, digest_date: str, recipient_email: str):
    """
    Build one-click feedback buttons using mailto: links (zero friction).
    """
    
    subject_useful = f"Digest Feedback: {section_name} - Useful ({digest_date})"
    subject_not_useful = f"Digest Feedback: {section_name} - Not Useful ({digest_date})"
    
    feedback_html = f'''
    <div style="background: #f8f9fa; border-top: 1px solid #dee2e6; padding: 15px; margin-top: 20px; text-align: center;">
        <p style="color: #6c757d; font-size: 13px; margin: 0 0 10px 0;">
            Was this section useful?
        </p>
        <div style="display: inline-flex; gap: 10px;">
            <a href="mailto:{recipient_email}?subject={subject_useful}" 
               style="display: inline-block; background: #2ecc71; color: white; 
                      padding: 8px 20px; border-radius: 6px; text-decoration: none; font-size: 14px;">
                👍 Useful
            </a>
            <a href="mailto:{recipient_email}?subject={subject_not_useful}" 
               style="display: inline-block; background: #e74c3c; color: white; 
                      padding: 8px 20px; border-radius: 6px; text-decoration: none; font-size: 14px;">
                👎 Not Useful
            </a>
        </div>
    </div>
    '''
    
    return feedback_html


# ═══════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═══════════════════════════════════════════════════════════════════════════

def example_improved_digest():
    """Example showing the improved digest structure."""
    
    # HIGH PRIORITY SECTION: Active land listing under budget
    section1 = build_improved_section_card(
        title="Land Listings: New Match Found",
        summary="1 new parcel under $55K with legal road access posted today",
        findings=[
            "3.2 acres in Tres Piedras - $48,500 (listed today)",
            "Deeded legal road access via County Road 87",
            "South-facing slope, cistern water feasible"
        ],
        primary_cta={
            'text': 'View Listing on LandWatch',
            'url': 'https://landwatch.com/example'
        },
        priority='high'
    )
    
    # MEDIUM PRIORITY: Builder update
    section2 = build_improved_section_card(
        title="Builder Intelligence: Zook Lead Time Update",
        summary="Zook Cabins lead times decreased to 12-14 weeks (from 16-18)",
        findings=[
            "Heritage series now 12-14 weeks from order to NM delivery",
            "No price changes on Grove or Rivara ADU models",
            "Spring 2026 delivery slots still available"
        ],
        primary_cta={
            'text': 'Request Quote from Zook',
            'url': 'https://zookcabins.com/contact'
        },
        priority='medium'
    )
    
    # LOW PRIORITY: Market trend (no action needed)
    section3 = build_improved_section_card(
        title="Van Market Analysis",
        summary="Sprinter diesel van prices holding steady, no seasonal dip yet",
        findings=[
            "2020-2022 Sprinter 144\" 4x4 average: $87K (unchanged from last week)",
            "Spring selling season typically starts mid-April",
            "Current market favors waiting until late March for listing"
        ],
        primary_cta={
            'text': 'View Market Comp Report',
            'url': 'https://github.com/user/repo/issues/123'
        },
        priority='low',
        show_more_url='https://github.com/user/repo/issues/123'
    )
    
    # Add feedback widgets
    feedback1 = build_feedback_widget("Land Listings", "March 24, 2026", "chris@example.com")
    feedback2 = build_feedback_widget("Builder Intelligence", "March 24, 2026", "chris@example.com")
    
    # Combine into full email
    full_email = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                 background: #f5f6fa; margin: 0; padding: 20px;">
        
        <div style="max-width: 600px; margin: 0 auto;">
            
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        color: white; padding: 30px; border-radius: 12px; margin-bottom: 30px; text-align: center;">
                <h1 style="margin: 0; font-size: 24px;">Taos Off-Grid Build Daily Digest</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">Monday, March 24, 2026</p>
            </div>
            
            <!-- Sections (priority-sorted) -->
            {section1}
            {feedback1}
            
            {section2}
            {feedback2}
            
            {section3}
            
            <!-- Footer -->
            <div style="text-align: center; padding: 20px; color: #6c757d; font-size: 13px;">
                <p>Automated digest • Powered by Claude Haiku 4.5</p>
            </div>
            
        </div>
        
    </body>
    </html>
    '''
    
    return full_email


if __name__ == '__main__':
    print("HCI Improvement Recommendations loaded")
    print("\nKey changes:")
    print("1. Priority color coding (red/yellow/green)")
    print("2. One-line summary per section")
    print("3. Max 3 key findings per section")
    print("4. Single primary CTA button")
    print("5. One-click mailto: feedback")
    print("\nRun example_improved_digest() to see sample output")
