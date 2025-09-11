# backend/app/services/export_service.py
from typing import Dict, Any
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

    def generate_estimation_pdf(self, estimation_data: Dict[str, Any], input_summary: Dict[str, Any]) -> bytes:
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
        
        # Cost Breakdown
        story.append(Paragraph("Cost Breakdown", self.styles['SectionHeader']))
        
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
        if margin > 0:
            cost_data.append(['Prime Contractor Margin', f"${margin:,.2f}", 
                             f"{(margin/result['total_cost']*100):.1f}%"])
        
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