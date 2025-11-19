# backend/app/services/export_service.py
from typing import Dict, Any, Optional
from datetime import datetime
import io
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

from ..models import EstimationResult

class ExportService:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom styles for the PDF"""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=20,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        ))
        
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            textColor=colors.darkblue,
            borderWidth=1,
            borderColor=colors.darkblue,
            borderPadding=5
        ))
        
        self.styles.add(ParagraphStyle(
            name='Highlight',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=colors.darkgreen,
            fontName='Helvetica-Bold'
        ))

    def generate_estimation_pdf(
        self,
        estimation_data: Dict[str, Any],
        input_summary: Dict[str, Any],
        narrative_sections: Optional[Dict[str, str]] = None,
    ) -> bytes:
        """Generate a professional PDF estimation report"""
        
        # Create PDF buffer
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72,
                               topMargin=72, bottomMargin=18)
        
        # Build content
        story = []
        
        # Title
        story.append(Paragraph("Project Estimation Report", self.styles['CustomTitle']))
        story.append(Spacer(1, 20))
        
        # Executive Summary
        story.append(Paragraph("Executive Summary", self.styles['SectionHeader']))
        
        result = estimation_data['estimation_result']
        
        summary_data = [
            ['Total Project Hours:', f"{result['total_labor_hours']:,.1f}"],
            ['Total Project Cost:', f"${result['total_cost']:,.2f}"],
            ['Effective Hourly Rate:', f"${result['effective_hourly_rate']:,.2f}"],
            ['Project Complexity:', input_summary['complexity']],
            ['Number of Modules:', str(input_summary['module_count'])]
        ]
        
        summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 20))

        # Project Information (if available)
        project_info = estimation_data.get('project_info') or {}
        if project_info:
            story.append(Spacer(1, 12))
            story.append(Paragraph("Project Information", self.styles['SectionHeader']))
            pi_rows = []
            def add_pi(label: str, key: str):
                val = project_info.get(key)
                if val:
                    pi_rows.append([label, str(val)])
            add_pi('Project Name', 'project_name')
            add_pi('Government POC', 'government_poc')
            add_pi('Account Manager', 'account_manager')
            add_pi('Service Delivery Mgr', 'service_delivery_mgr')
            add_pi('Service Delivery Exec', 'service_delivery_exec')
            add_pi('Site Location', 'site_location')
            add_pi('Email', 'email')
            add_pi('Fiscal Year', 'fy')
            add_pi('RAP #', 'rap_number')
            add_pi('PSI Code', 'psi_code')
            if project_info.get('additional_comments'):
                pi_rows.append(['Comments', project_info.get('additional_comments')])

            if pi_rows:
                pi_table = Table(pi_rows, colWidths=[2.2*inch, 4.3*inch])
                pi_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ]))
                story.append(pi_table)
                story.append(Spacer(1, 16))

        # Optional scraped contract context (if provided)
        contract_src = estimation_data.get('contract_source') or {}
        if contract_src.get('url') or contract_src.get('excerpt'):
            story.append(Spacer(1, 12))
            story.append(Paragraph("Contract Source (Scraped)", self.styles['SectionHeader']))
            url = contract_src.get('url')
            if url:
                story.append(Paragraph(f"URL: {url}", self.styles['Normal']))
                story.append(Spacer(1, 6))
            excerpt = contract_src.get('excerpt')
            if excerpt:
                story.append(Paragraph(str(excerpt), self.styles['Normal']))
                story.append(Spacer(1, 16))

        # Optional AI-generated narrative blocks
        if narrative_sections:
            if narrative_sections.get('executive_summary'):
                story.append(Paragraph("Narrative Summary", self.styles['SectionHeader']))
                story.append(Paragraph(narrative_sections['executive_summary'], self.styles['Normal']))
                story.append(Spacer(1, 16))
            for key in ["assumptions", "risks", "recommendations", "next_steps"]:
                if narrative_sections.get(key):
                    title = key.replace('_', ' ').title()
                    story.append(Paragraph(title, self.styles['SectionHeader']))
                    story.append(Paragraph(narrative_sections[key], self.styles['Normal']))
                    story.append(Spacer(1, 16))
        
        # Cost Breakdown
        story.append(Paragraph("Cost Breakdown", self.styles['SectionHeader']))
        
        add_costs = result.get('additional_costs') or {}
        cost_data = [
            ['Component', 'Amount', 'Percentage'],
            ['Labor Cost', f"${result['total_labor_cost']:,.2f}", 
             f"{(result['total_labor_cost']/result['total_cost']*100):.1f}%"],
            ['Risk Reserve', f"${result['risk_reserve']:,.2f}", 
             f"{(result['risk_reserve']/result['total_cost']*100):.1f}%"],
            ['Overhead', f"${result['overhead_cost']:,.2f}", 
             f"{(result['overhead_cost']/result['total_cost']*100):.1f}%"],
        ]

        # Add margin if applicable
        margin = result['total_cost'] - result['total_labor_cost'] - result['risk_reserve'] - result['overhead_cost']
        # Back out additional costs before computing margin percentage row
        margin -= float(add_costs.get('odc_total', 0))
        margin -= float(add_costs.get('fixed_price_total', 0))
        margin -= float(add_costs.get('hardware_subtotal', 0))
        margin -= float(add_costs.get('warranty_cost', 0))
        if margin > 0:
            cost_data.append(['Prime Contractor Margin', f"${margin:,.2f}", 
                             f"{(margin/result['total_cost']*100):.1f}%"])

        # Append additional costs if present
        if float(add_costs.get('hardware_subtotal', 0)) > 0:
            cost_data.append(['Hardware Subtotal', f"${float(add_costs['hardware_subtotal']):,.2f}", 
                             f"{(float(add_costs['hardware_subtotal'])/result['total_cost']*100):.1f}%"])
        if float(add_costs.get('odc_total', 0)) > 0:
            cost_data.append(['Other Direct Costs', f"${float(add_costs['odc_total']):,.2f}", 
                             f"{(float(add_costs['odc_total'])/result['total_cost']*100):.1f}%"])
        if float(add_costs.get('fixed_price_total', 0)) > 0:
            cost_data.append(['Fixed-Price Items', f"${float(add_costs['fixed_price_total']):,.2f}", 
                             f"{(float(add_costs['fixed_price_total'])/result['total_cost']*100):.1f}%"])
        if float(add_costs.get('warranty_cost', 0)) > 0:
            cost_data.append(['Warranty Cost', f"${float(add_costs['warranty_cost']):,.2f}", 
                             f"{(float(add_costs['warranty_cost'])/result['total_cost']*100):,.1f}%"])

        cost_data.append(['Total Project Cost', f"${result['total_cost']:,.2f}", "100.0%"])
        
        cost_table = Table(cost_data, colWidths=[2.5*inch, 1.5*inch, 1*inch])
        cost_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightblue),
        ]))
        
        story.append(cost_table)
        story.append(Spacer(1, 20))
        
        # Module Breakdown
        if result.get('breakdown_by_module'):
            story.append(Paragraph("Module Breakdown", self.styles['SectionHeader']))
            
            module_data = [['Module', 'Focus Area', 'Hours', 'Cost']]
            for module_id, module_info in result['breakdown_by_module'].items():
                module_data.append([
                    module_info['module_name'],
                    module_info['focus_area'],
                    f"{module_info['hours']:,.1f}",
                    f"${module_info['cost']:,.2f}"
                ])
            
            module_table = Table(module_data, colWidths=[2.5*inch, 1*inch, 1*inch, 1.5*inch])
            module_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ]))
            
            story.append(module_table)
            story.append(Spacer(1, 20))
        
        # Role Breakdown
        if result.get('breakdown_by_role'):
            story.append(Paragraph("Resource Breakdown", self.styles['SectionHeader']))
            
            role_data = [['Role', 'Hours', 'Rate', 'Cost']]
            for role_id, role_info in result['breakdown_by_role'].items():
                role_data.append([
                    role_info['role_name'],
                    f"{role_info['hours']:,.1f}",
                    f"${role_info['effective_rate']:,.2f}",
                    f"${role_info['cost']:,.2f}"
                ])
            
            role_table = Table(role_data, colWidths=[2*inch, 1*inch, 1.25*inch, 1.75*inch])
            role_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))

            story.append(role_table)
            story.append(Spacer(1, 20))

        # Optional detailed lists for other costs
        if add_costs:
            # ODC items
            if estimation_data.get('odc_items'):
                story.append(Spacer(1, 12))
                story.append(Paragraph("Other Direct Costs (detail)", self.styles['SectionHeader']))
                rows = [['Description', 'Price']]
                for item in estimation_data.get('odc_items'):
                    rows.append([str(item.get('description') or ''), f"${float(item.get('price') or 0):,.2f}"])
                tbl = Table(rows, colWidths=[4.0*inch, 2.0*inch])
                tbl.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ]))
                story.append(tbl)

            # Fixed price items
            if estimation_data.get('fixed_price_items'):
                story.append(Spacer(1, 12))
                story.append(Paragraph("Fixed-Price Items (detail)", self.styles['SectionHeader']))
                rows = [['Description', 'Price']]
                for item in estimation_data.get('fixed_price_items'):
                    rows.append([str(item.get('description') or ''), f"${float(item.get('price') or 0):,.2f}"])
                tbl = Table(rows, colWidths=[4.0*inch, 2.0*inch])
                tbl.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ]))
                story.append(tbl)

        # Generation timestamp
        story.append(Paragraph(
            f"Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            self.styles['Normal']
        ))

        # Build and return PDF
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
