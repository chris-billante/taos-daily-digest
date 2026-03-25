"""
Fixes for HTML table nesting issues and learning resource fallback logic.

PROBLEM 1: HTML Table Nesting
==============================
Current issue: Tables inside card divs break email client rendering.
Email clients (especially Outlook) have poor CSS support and can't handle:
- Nested flexbox layouts
- Complex div structures
- Modern CSS grid

Solution: Use <table> for layout structure (yes, like 1999, because email clients are stuck in 1999).

PROBLEM 2: Learning Resource Fallback
======================================
Current issue: If web_search returns no results for learning resources, section is empty.
Solution: Maintain a curated fallback library of evergreen resources.
"""

# ═══════════════════════════════════════════════════════════════════════════
# FIX 1: EMAIL-SAFE TABLE STRUCTURE
# ═══════════════════════════════════════════════════════════════════════════

def build_email_safe_card(title, content, priority='medium'):
    """
    Build a card using table-based layout for email client compatibility.
    Outlook-tested structure.
    """
    
    priority_colors = {
        'high': '#e74c3c',
        'medium': '#f39c12',
        'low': '#95a5a6'
    }
    
    border_color = priority_colors.get(priority, '#f39c12')
    
    # Use table for layout structure (email-safe)
    card_html = f'''
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 20px;">
        <tr>
            <td style="background: white; border: 1px solid #dee2e6; border-left: 5px solid {border_color}; 
                       border-radius: 8px; padding: 24px;">
                
                <!-- Title -->
                <table width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td>
                            <h2 style="color: #2c3e50; margin: 0 0 15px 0; font-size: 20px; 
                                       font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                                {title}
                            </h2>
                        </td>
                    </tr>
                </table>
                
                <!-- Content -->
                <table width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td style="color: #2c3e50; line-height: 1.6; 
                                   font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                            {content}
                        </td>
                    </tr>
                </table>
                
            </td>
        </tr>
    </table>
    '''
    
    return card_html


def build_two_column_layout(left_content, right_content):
    """
    Build a responsive two-column layout using tables.
    Falls back to stacked on mobile.
    """
    
    layout_html = f'''
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
            <!-- Left column -->
            <td width="48%" valign="top" style="padding-right: 2%;">
                {left_content}
            </td>
            
            <!-- Right column -->
            <td width="48%" valign="top" style="padding-left: 2%;">
                {right_content}
            </td>
        </tr>
    </table>
    
    <!-- Mobile fallback: stack columns -->
    <style>
        @media only screen and (max-width: 600px) {{
            table[class="responsive-table"] td {{
                display: block !important;
                width: 100% !important;
                padding: 0 !important;
            }}
        }}
    </style>
    '''
    
    return layout_html


def build_data_table(headers, rows):
    """
    Build a clean data table for email.
    
    Args:
        headers: List of column header strings
        rows: List of lists (each inner list is a row)
    """
    
    # Build header row
    header_cells = []
    for header in headers:
        header_cells.append(f'''
            <th style="background: #34495e; color: white; padding: 12px; text-align: left; 
                       font-weight: 600; border-bottom: 2px solid #2c3e50;">
                {header}
            </th>
        ''')
    
    header_row = '<tr>' + ''.join(header_cells) + '</tr>'
    
    # Build data rows
    data_rows = []
    for i, row in enumerate(rows):
        bg_color = '#f8f9fa' if i % 2 == 0 else 'white'
        
        row_cells = []
        for cell in row:
            row_cells.append(f'''
                <td style="padding: 12px; border-bottom: 1px solid #dee2e6; background: {bg_color};">
                    {cell}
                </td>
            ''')
        
        data_rows.append('<tr>' + ''.join(row_cells) + '</tr>')
    
    # Complete table
    table_html = f'''
    <table width="100%" cellpadding="0" cellspacing="0" border="0" 
           style="border: 1px solid #dee2e6; border-radius: 8px; overflow: hidden;">
        <thead>
            {header_row}
        </thead>
        <tbody>
            {''.join(data_rows)}
        </tbody>
    </table>
    '''
    
    return table_html


# ═══════════════════════════════════════════════════════════════════════════
# FIX 2: LEARNING RESOURCE FALLBACK LIBRARY
# ═══════════════════════════════════════════════════════════════════════════

FALLBACK_LEARNING_RESOURCES = {
    'monday': {
        'topic': 'Off-Grid Solar Basics',
        'resources': [
            {
                'title': 'Will Prowse: Complete Off-Grid Solar Design Course',
                'url': 'https://www.mobile-solarpower.com/solar-training.html',
                'description': 'Comprehensive course covering system sizing, battery banks, inverter selection. Chris\'s EG4 18kPV system uses principles from this course.',
                'type': 'Video Course'
            },
            {
                'title': 'DIY Solar Power Forum: System Design Section',
                'url': 'https://diysolarforum.com/forums/system-design.8/',
                'description': 'Active community with real-world off-grid builds. Search for "EG4" to see user experiences with your inverter model.',
                'type': 'Forum'
            },
            {
                'title': 'Victron Energy System Examples',
                'url': 'https://www.victronenergy.com/upload/documents/Victron-Energy-Off-grid-solar-systems-examples.pdf',
                'description': 'Professional system design examples with wiring diagrams. Principles apply across all inverter brands.',
                'type': 'PDF Guide'
            }
        ]
    },
    
    'tuesday': {
        'topic': 'Modular Home Construction',
        'resources': [
            {
                'title': 'Modular Building Institute: Construction Process',
                'url': 'https://www.modular.org/htmlPage.aspx?name=why_modular',
                'description': 'Industry overview of modular vs. site-built construction. Explains IRC compliance and permitting.',
                'type': 'Industry Guide'
            },
            {
                'title': 'New Mexico CID Title 14 Regulations',
                'url': 'https://www.rld.nm.gov/construction-industries-division/',
                'description': 'Official NM construction regulations. Bookmark Title 14.7.3 (modular homes) and 14.12.2 (manufactured homes).',
                'type': 'Regulatory'
            },
            {
                'title': 'Zook Cabins Owner Forum',
                'url': 'https://www.facebook.com/groups/zookcabins',
                'description': 'Facebook group of Zook owners. Real delivery timelines, foundation tips, and finish quality reviews.',
                'type': 'Community'
            }
        ]
    },
    
    'wednesday': {
        'topic': 'Rural Land Acquisition',
        'resources': [
            {
                'title': 'New Mexico Water Rights Guide',
                'url': 'https://www.ose.nm.gov/WR/index.php',
                'description': 'NM Office of State Engineer water rights database and transfer process. Essential before any land purchase.',
                'type': 'Government Resource'
            },
            {
                'title': 'Taos County Comprehensive Plan',
                'url': 'https://www.taoscounty.org/154/Comprehensive-Plan',
                'description': 'Zoning regulations, minimum parcel sizes, and development standards for RA-zoned land.',
                'type': 'Planning Document'
            },
            {
                'title': 'LandWatch Buying Guide',
                'url': 'https://www.landwatch.com/land-buyers-guide',
                'description': 'Checklist for rural land due diligence: access, utilities, easements, restrictions.',
                'type': 'Buyer Guide'
            }
        ]
    },
    
    'thursday': {
        'topic': 'Off-Grid Heating Systems',
        'resources': [
            {
                'title': 'Blaze King Owner\'s Forum',
                'url': 'https://www.hearth.com/talk/forums/blaze-king.71/',
                'description': 'Active forum for Blaze King wood stove owners. Burn efficiency tips and maintenance schedules.',
                'type': 'Forum'
            },
            {
                'title': 'Rinnai Tankless Installation Guide',
                'url': 'https://www.rinnai.us/tankless-water-heater/support/installation-manuals',
                'description': 'Official installation manuals for Rinnai propane water heaters. Venting requirements for high altitude.',
                'type': 'Technical Manual'
            },
            {
                'title': 'Propane Education & Research Council',
                'url': 'https://propane.com/for-homeowners/',
                'description': 'Sizing propane tanks, annual usage estimates, and safety regulations.',
                'type': 'Educational'
            }
        ]
    },
    
    'friday': {
        'topic': 'Construction Financing',
        'resources': [
            {
                'title': 'Fannie Mae Construction-to-Permanent Loans',
                'url': 'https://singlefamily.fanniemae.com/originating-underwriting/mortgage-products/construction-permanent-mortgage',
                'description': 'Official guidelines for construction-to-perm financing. What lenders require for off-grid builds.',
                'type': 'Lending Guide'
            },
            {
                'title': 'USDA Rural Development Programs',
                'url': 'https://www.rd.usda.gov/programs-services/single-family-housing-programs',
                'description': 'Low-interest loan programs for rural properties. Check income eligibility for Taos County.',
                'type': 'Government Program'
            },
            {
                'title': 'Centinel Bank of Taos',
                'url': 'https://www.centinelbank.com/personal/home-loans',
                'description': 'Local NM lender with experience in off-grid construction loans. Start here for pre-qualification.',
                'type': 'Lender'
            }
        ]
    },
    
    'saturday': {
        'topic': 'Vehicle & Van Life',
        'resources': [
            {
                'title': 'Sprinter Forum: Market Trends',
                'url': 'https://sprinter-source.com/forums/index.php?forums/general-discussion.8/',
                'description': 'Active Sprinter owner community. Best months to sell, common buyer questions, pricing comps.',
                'type': 'Forum'
            },
            {
                'title': 'Toyota Tacoma Buyer\'s Guide',
                'url': 'https://www.tacomaworld.com/threads/3rd-gen-tacoma-buyers-guide.517621/',
                'description': 'Comprehensive guide to 2020-2023 Tacoma models. Known issues, trim comparisons, feature differences.',
                'type': 'Buyer Guide'
            },
            {
                'title': 'CarGurus vs. Cars.com: Where to List',
                'url': 'https://www.cargurus.com/Cars/articles/how_to_sell_your_car',
                'description': 'Comparison of major listing platforms. Audience reach, fees, and sale speed data.',
                'type': 'Comparison Guide'
            }
        ]
    },
    
    'sunday': {
        'topic': 'Project Planning & Budgeting',
        'resources': [
            {
                'title': 'Crystal Ball Monte Carlo Analysis',
                'url': 'https://www.oracle.com/applications/crystalball/',
                'description': 'Monte Carlo simulation tool for financial projections. Free trial available.',
                'type': 'Software'
            },
            {
                'title': 'Homebuilder Cost Estimating Guide',
                'url': 'https://www.constructionbook.com/guides/cost-estimating',
                'description': 'Industry-standard cost breakdown structure. Use this to validate builder quotes.',
                'type': 'Estimating Guide'
            },
            {
                'title': 'Project Management for Tiny Homes',
                'url': 'https://www.tinyhomebuilders.com/plans/project-management',
                'description': 'Timeline templates, permit checklists, contractor evaluation rubrics.',
                'type': 'Template Library'
            }
        ]
    }
}


def get_learning_resources_for_day(day_of_week):
    """
    Get curated learning resources for a specific day.
    Falls back to this library if web search returns nothing.
    
    Args:
        day_of_week: 'monday', 'tuesday', etc. (lowercase)
    
    Returns:
        Dict with 'topic' and 'resources' list
    """
    return FALLBACK_LEARNING_RESOURCES.get(day_of_week.lower(), FALLBACK_LEARNING_RESOURCES['monday'])


def format_learning_resources(resources_data):
    """
    Format learning resources as email-safe HTML.
    
    Args:
        resources_data: Dict from get_learning_resources_for_day()
    """
    
    topic = resources_data['topic']
    resources = resources_data['resources']
    
    # Build resource cards
    resource_cards = []
    for resource in resources:
        card = f'''
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 15px;">
            <tr>
                <td style="background: #f8f9fa; border-left: 3px solid #3498db; padding: 15px; border-radius: 6px;">
                    <p style="margin: 0 0 5px 0; font-weight: 600; color: #2c3e50; font-size: 16px;">
                        {resource['title']}
                    </p>
                    <p style="margin: 0 0 10px 0; color: #6c757d; font-size: 13px;">
                        {resource['type']}
                    </p>
                    <p style="margin: 0 0 10px 0; color: #495057; font-size: 14px; line-height: 1.5;">
                        {resource['description']}
                    </p>
                    <a href="{resource['url']}" 
                       style="color: #3498db; text-decoration: none; font-weight: 500; font-size: 14px;">
                        Visit Resource →
                    </a>
                </td>
            </tr>
        </table>
        '''
        resource_cards.append(card)
    
    # Complete section
    section_html = f'''
    <p style="color: #2c3e50; font-size: 15px; margin: 0 0 20px 0;">
        <strong>Today's Learning Focus:</strong> {topic}
    </p>
    
    {''.join(resource_cards)}
    '''
    
    return section_html


# ═══════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Example 1: Email-safe card
    card = build_email_safe_card(
        title="Land Listings",
        content="<p>3 new parcels found today in your target area.</p>",
        priority='high'
    )
    print("Email-safe card structure created")
    
    # Example 2: Data table
    table = build_data_table(
        headers=['Parcel', 'Acres', 'Price', 'Road Access'],
        rows=[
            ['Tres Piedras Lot 14', '3.2', '$48,500', 'CR 87 (paved)'],
            ['Carson Mesa Parcel', '2.8', '$52,000', 'BLM easement'],
            ['Ojo Caliente Land', '5.0', '$65,000', 'Private road']
        ]
    )
    print("Data table created")
    
    # Example 3: Learning resources with fallback
    import datetime
    today = datetime.datetime.now().strftime('%A').lower()
    resources = get_learning_resources_for_day(today)
    resources_html = format_learning_resources(resources)
    print(f"\nLearning resources for {today}: {resources['topic']}")
    print(f"Total resources: {len(resources['resources'])}")
