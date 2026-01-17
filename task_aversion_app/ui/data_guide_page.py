# ui/data_guide_page.py
from nicegui import ui
from pathlib import Path
import re
from backend.auth import get_current_user
from backend.security_utils import escape_for_display
from ui.error_reporting import handle_error_with_ui


def load_guide_content() -> str:
    """Load the data troubleshooting guide markdown content."""
    guide_path = Path(__file__).parent.parent / "docs" / "data_troubleshooting.md"
    try:
        with open(guide_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        user_id = get_current_user()
        handle_error_with_ui(
            operation="load data guide content",
            error=e,
            user_id=user_id,
            context={"guide_path": str(guide_path)},
            user_message="Unable to load the data guide content. Please try again later.",
            show_report=True
        )
        return "# Data Guide Not Found\n\nThe data troubleshooting guide file could not be loaded."


def render_markdown_section(content: str):
    """Render a markdown section as NiceGUI elements."""
    lines = content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            i += 1
            continue
        
        # Headers
        if line.startswith('### '):
            text = line[4:].strip()
            ui.label(escape_for_display(text)).classes("text-lg font-semibold mt-4 mb-2 text-gray-700")
        elif line.startswith('## '):
            text = line[3:].strip()
            ui.label(escape_for_display(text)).classes("text-xl font-bold mt-6 mb-3 text-gray-800")
        elif line.startswith('# '):
            text = line[2:].strip()
            ui.label(escape_for_display(text)).classes("text-2xl font-bold mt-4 mb-4 text-gray-900")
        
        # Horizontal rules
        elif line.startswith('---'):
            ui.separator().classes("my-4")
        
        # Lists
        elif line.startswith('- '):
            with ui.column().classes("ml-6 mb-2"):
                while i < len(lines) and lines[i].strip().startswith('- '):
                    item_text = lines[i].strip()[2:].strip()
                    # Process inline formatting
                    item_text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', item_text)
                    item_text = re.sub(r'`([^`]+)`', r'<code class="bg-gray-100 px-1 rounded text-sm">\1</code>', item_text)
                    ui.html(f'<li class="mb-1">{item_text}</li>', sanitize=False).classes("list-disc")
                    i += 1
                i -= 1  # Adjust for outer loop increment
        
        # Tables
        elif line.startswith('|') and '|' in line:
            # Collect all table rows
            table_rows = []
            is_header = True
            while i < len(lines) and lines[i].strip().startswith('|'):
                if '---' in lines[i]:
                    is_header = False
                    i += 1
                    continue
                cells = [c.strip() for c in lines[i].split('|') if c.strip()]
                if cells:
                    table_rows.append(cells)
                i += 1
            i -= 1
            
            # Render table as HTML
            if table_rows:
                table_html = '<table class="w-full border-collapse my-4"><tbody>'
                for idx, row in enumerate(table_rows):
                    if idx == 0 and is_header:
                        table_html += '<tr class="bg-gray-50">'
                    else:
                        table_html += '<tr>'
                    for cell in row:
                        cell_class = "border px-3 py-2 font-semibold" if idx == 0 and is_header else "border px-3 py-2"
                        escaped_cell = escape_for_display(cell)
                        table_html += f'<td class="{cell_class}">{escaped_cell}</td>'
                    table_html += '</tr>'
                table_html += '</tbody></table>'
                ui.html(table_html, sanitize=False).classes("w-full overflow-x-auto")
        
        # Regular paragraphs
        else:
            # Process inline formatting
            para_text = line
            para_text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', para_text)
            para_text = re.sub(r'`([^`]+)`', r'<code class="bg-gray-100 px-1 rounded text-sm">\1</code>', para_text)
            
            # Check if it's a note or important text
            if para_text.startswith('**') or para_text.startswith('*'):
                ui.html(f'<p class="mb-2 text-gray-700">{para_text}</p>', sanitize=False)
            else:
                ui.html(f'<p class="mb-2 text-gray-600">{para_text}</p>', sanitize=False)
        
        i += 1


@ui.page("/data-guide")
def data_guide_page():
    """Display the data troubleshooting and information guide."""
    
    ui.add_head_html("""
    <style>
        .guide-container {
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem 1rem;
        }
        .guide-content {
            line-height: 1.7;
        }
        .guide-section {
            margin-bottom: 2rem;
        }
    </style>
    """)
    
    with ui.column().classes("guide-container w-full"):
        # Header with back button
        with ui.row().classes("w-full items-center gap-4 mb-6"):
            ui.button("← Back to Settings", on_click=lambda: ui.navigate.to("/settings")).classes("bg-gray-500 text-white")
            ui.label("Data Storage & Troubleshooting Guide").classes("text-3xl font-bold")
        
        # Load guide content
        guide_content = load_guide_content()
        
        # Split into main sections
        sections = guide_content.split('\n## ')
        
        with ui.card().classes("w-full p-6 guide-content"):
            # First section (main title and intro)
            if sections:
                first_section = sections[0]
                if first_section.startswith('#'):
                    title = first_section.split('\n')[0].replace('# ', '')
                    ui.label(escape_for_display(title)).classes("text-2xl font-bold mb-4 text-gray-900")
                    intro_content = '\n'.join(first_section.split('\n')[1:]).strip()
                    if intro_content:
                        render_markdown_section(intro_content)
            
            # Remaining sections as expandable cards
            for section in sections[1:]:
                if not section.strip():
                    continue
                
                lines = section.split('\n')
                if lines:
                    section_title = lines[0].strip()
                    section_content = '\n'.join(lines[1:]).strip()
                    
                    with ui.expansion(section_title, icon='info').classes("w-full mb-3").style("border: 1px solid #e5e7eb; border-radius: 0.5rem;"):
                        with ui.column().classes("mt-3 guide-section"):
                            render_markdown_section(section_content)
        
        # Quick actions at bottom
        ui.separator().classes("my-6")
        with ui.row().classes("w-full justify-center gap-4 mb-4"):
            ui.button("Go to Settings", on_click=lambda: ui.navigate.to("/settings")).classes("bg-blue-500 text-white")
            ui.button("Go to Dashboard", on_click=lambda: ui.navigate.to("/")).classes("bg-gray-500 text-white")

