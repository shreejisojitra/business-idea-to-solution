import json
import re
from typing import Any, Dict


class ExportService:
    """Formats full transformation blueprint into Markdown, JSON, HTML, or PDF export files."""

    @staticmethod
    def export_as_json(blueprint_data: Dict[str, Any]) -> str:
        return json.dumps(blueprint_data, indent=2)

    @staticmethod
    def export_as_markdown(project_name: str, blueprint_data: Dict[str, Any]) -> str:
        ba = blueprint_data.get("business_analysis", {})
        ai_opps = blueprint_data.get("ai_opportunities", {}).get("opportunities", [])
        sb = blueprint_data.get("solution_blueprint", {})
        arch = blueprint_data.get("architecture", {})
        data_api = blueprint_data.get("data_api_design", {})
        ux = blueprint_data.get("ux_design", {})
        roadmap = blueprint_data.get("roadmap", {})

        md = f"""# Business Transformation Blueprint — {project_name}

---

## 1. Business Analysis

### Core Problem
{ba.get('problem', 'N/A')}

### Pain Points
"""
        for pt in ba.get('pain_points', []):
            md += f"- {pt}\n"

        md += "\n### Strategic Goals\n"
        for goal in ba.get('goals', []):
            md += f"- {goal}\n"

        md += "\n### Stakeholders\n"
        for sh in ba.get('stakeholders', []):
            md += f"- {sh}\n"

        md += "\n### Key Requirements\n"
        for req in ba.get('requirements', []):
            md += f"- {req}\n"

        md += "\n---\n\n## 2. AI Opportunities\n\n"
        for opp in ai_opps:
            md += f"### {opp.get('opportunity_name')}\n"
            md += f"- **Capability**: {opp.get('ai_capability')}\n"
            md += f"- **Description**: {opp.get('description')}\n"
            md += f"- **Expected Benefit**: {opp.get('expected_benefit')}\n"
            md += f"- **Priority**: {opp.get('priority')} | **Complexity**: {opp.get('complexity')}\n\n"

        md += "---\n\n## 3. Solution Blueprint\n\n"
        md += f"### Recommended Solution\n{sb.get('recommended_solution', 'N/A')}\n\n"
        md += "### System Modules\n"
        for mod in sb.get('system_modules', []):
            md += f"- **{mod.get('module_name')}**: {mod.get('description')}\n"

        tech = sb.get('technology_stack', {})
        md += f"\n### Technology Stack\n"
        md += f"- **Frontend**: {', '.join(tech.get('frontend', []))}\n"
        md += f"- **Backend**: {', '.join(tech.get('backend', []))}\n"
        md += f"- **Database**: {', '.join(tech.get('database', []))}\n"
        md += f"- **AI Engine**: {', '.join(tech.get('ai_llm', []))}\n\n"

        md += "---\n\n## 4. Architecture & Technical Design\n\n"
        md += f"### Frontend Architecture\n{arch.get('frontend_architecture', 'N/A')}\n\n"
        md += f"### Backend Architecture\n{arch.get('backend_architecture', 'N/A')}\n\n"

        md += "---\n\n## 5. Database & API Specification\n\n"
        md += "### Database Schema SQL\n```sql\n"
        md += f"{data_api.get('database_schema_sql', '-- DDL Script')}\n```\n\n"

        md += "---\n\n## 6. UX Recommendations & Wireframes\n\n"
        for screen in ux.get('required_screens', []):
            md += f"- **{screen.get('screen_name')}**: {screen.get('purpose')}\n"

        md += "\n---\n\n## 7. Implementation Roadmap\n\n"
        for phase in roadmap.get('phases', []):
            md += f"### {phase.get('phase_name')} ({phase.get('duration_weeks')} weeks)\n"
            for t in phase.get('tasks', []):
                md += f"- {t}\n"

        return md

    @staticmethod
    def export_as_html(project_name: str, blueprint_data: Dict[str, Any]) -> str:
        md_text = ExportService.export_as_markdown(project_name, blueprint_data)
        # Convert markdown to basic HTML
        html_body = ""
        for line in md_text.split("\n"):
            if line.startswith("# "):
                html_body += f"<h1>{line[2:]}</h1>\n"
            elif line.startswith("## "):
                html_body += f"<h2>{line[3:]}</h2>\n"
            elif line.startswith("### "):
                html_body += f"<h3>{line[4:]}</h3>\n"
            elif line.startswith("- "):
                html_body += f"<li>{line[2:]}</li>\n"
            elif line.startswith("```"):
                if "<pre>" not in html_body[-10:]:
                    html_body += "<pre><code>"
                else:
                    html_body += "</code></pre>\n"
            elif line.strip() == "---":
                html_body += "<hr>\n"
            elif line.strip():
                html_body += f"<p>{line}</p>\n"
            else:
                html_body += "<br>\n"

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Transformation Blueprint — {project_name}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; max-width: 900px; margin: 40px auto; padding: 0 20px; color: #1e293b; background: #f8fafc; }}
        h1, h2, h3 {{ color: #0f172a; }}
        pre, code {{ background: #e2e8f0; padding: 10px; border-radius: 6px; font-family: monospace; display: block; overflow-x: auto; }}
        hr {{ border: none; border-top: 1px solid #cbd5e1; margin: 30px 0; }}
        li {{ margin-left: 20px; }}
    </style>
</head>
<body>
{html_body}
</body>
</html>
"""

    @staticmethod
    def export_as_pdf(project_name: str, blueprint_data: Dict[str, Any]) -> bytes:
        """Generates a PDF from the project blueprint using reportlab."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
            from reportlab.lib import colors
            import io as _io

            buf = _io.BytesIO()
            doc = SimpleDocTemplate(buf, pagesize=A4,
                                    leftMargin=20*mm, rightMargin=20*mm,
                                    topMargin=20*mm, bottomMargin=20*mm)
            styles = getSampleStyleSheet()
            h1 = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=18, spaceAfter=8)
            h2 = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=14, spaceAfter=6)
            h3 = ParagraphStyle('H3', parent=styles['Heading3'], fontSize=12, spaceAfter=4)
            body = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10, spaceAfter=4)
            bullet = ParagraphStyle('Bullet', parent=styles['Normal'], fontSize=10, leftIndent=15, spaceAfter=2)

            md_text = ExportService.export_as_markdown(project_name, blueprint_data)
            story = []

            for line in md_text.split("\n"):
                safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                if safe.startswith("# "):
                    story.append(Paragraph(safe[2:], h1))
                elif safe.startswith("## "):
                    story.append(Spacer(1, 4*mm))
                    story.append(Paragraph(safe[3:], h2))
                elif safe.startswith("### "):
                    story.append(Paragraph(safe[4:], h3))
                elif safe.startswith("- "):
                    story.append(Paragraph(f"• {safe[2:]}", bullet))
                elif safe.strip() == "---":
                    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
                    story.append(Spacer(1, 3*mm))
                elif safe.strip():
                    story.append(Paragraph(safe, body))

            doc.build(story)
            return buf.getvalue()
        except ImportError:
            raise ExportError("PDF export requires 'reportlab'. Install it with: pip install reportlab")


class ExportError(Exception):
    pass
