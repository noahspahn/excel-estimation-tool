# backend/app/services/export_service.py
from typing import Dict, Any, Optional, List
from datetime import datetime
import io
import re
from xml.sax.saxutils import escape
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

        self.styles.add(ParagraphStyle(
            name='SubtaskHeader',
            parent=self.styles['Heading3'],
            fontSize=12,
            spaceAfter=6,
            textColor=colors.darkblue,
        ))
        self.styles.add(ParagraphStyle(
            name='SubtaskLabel',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.black,
            fontName='Helvetica-Bold',
        ))
        self.styles.add(ParagraphStyle(
            name='SubtaskBody',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.black,
            wordWrap='CJK',  # wrap long continuous strings
            leading=10,
        ))
        self.styles.add(ParagraphStyle(
            name='SubsectionHeader',
            parent=self.styles['Heading3'],
            fontSize=12,
            spaceAfter=6,
            textColor=colors.darkblue,
        ))
        self.styles.add(ParagraphStyle(
            name='ProjectInfoLabel',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.black,
            fontName='Helvetica-Bold',
        ))
        self.styles.add(ParagraphStyle(
            name='ProjectInfoValue',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.black,
            leading=11,
            wordWrap='CJK',
        ))
        self.styles.add(ParagraphStyle(
            name='ContractBody',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.black,
            leading=13,
            wordWrap='CJK',
        ))

    def _build_services_summary(self, result: Dict[str, Any]) -> str:
        modules = result.get("breakdown_by_module") or {}
        names: List[str] = []
        if isinstance(modules, dict):
            for item in modules.values():
                name = item.get("module_name")
                if name and name not in names:
                    names.append(name)
        return ", ".join(names)

    def _format_contract_excerpt(self, excerpt: str) -> List[Paragraph]:
        cleaned = re.sub(r"\r\n?", "\n", str(excerpt or "")).strip()
        if not cleaned:
            return []
        chunks = [c.strip() for c in re.split(r"\n\s*\n", cleaned) if c.strip()]
        if not chunks:
            chunks = [cleaned]
        paragraphs: List[Paragraph] = []
        for chunk in chunks:
            line = " ".join(chunk.split())
            intro = ""
            rest = ""
            match = re.match(r"(.{0,180}?[.!?:])\s+(.*)", line)
            if match:
                intro = match.group(1).strip()
                rest = match.group(2).strip()
            else:
                words = line.split()
                if len(words) > 12:
                    intro = " ".join(words[:12])
                    rest = " ".join(words[12:])
                else:
                    intro = line
                    rest = ""
            safe_intro = escape(intro)
            safe_rest = escape(rest)
            if safe_rest:
                formatted = f"<b>{safe_intro}</b> {safe_rest}"
            else:
                formatted = f"<b>{safe_intro}</b>"
            paragraphs.append(Paragraph(formatted, self.styles['ContractBody']))
        return paragraphs

    def _safe_float(self, value: Any) -> Optional[float]:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except Exception:
            return None

    def _format_money(self, value: Optional[float]) -> str:
        if value is None:
            return "n/a"
        return f"${value:,.2f}"

    def _format_money_range(self, low: Optional[float], high: Optional[float]) -> str:
        if low is None and high is None:
            return "n/a"
        if high is None or low is None or abs(high - low) < 0.01:
            return self._format_money(low if low is not None else high)
        return f"${low:,.2f} - ${high:,.2f}"

    def _compute_roi_summary(self, estimation_data: Dict[str, Any], total_cost: float) -> Optional[Dict[str, Any]]:
        roi_inputs = estimation_data.get("roi_inputs") or {}
        horizon_years = int(estimation_data.get("roi_horizon_years") or 5)
        capex_low = self._safe_float(roi_inputs.get("capex_event_cost_low"))
        capex_high = self._safe_float(roi_inputs.get("capex_event_cost_high"))
        interval_months = self._safe_float(roi_inputs.get("capex_event_interval_months"))
        downtime_cost = self._safe_float(roi_inputs.get("downtime_cost_per_hour"))
        current_avail = self._safe_float(roi_inputs.get("current_availability"))
        target_avail = self._safe_float(roi_inputs.get("target_availability"))
        legacy_annual = self._safe_float(roi_inputs.get("legacy_support_savings_annual"))

        has_inputs = any(
            v is not None
            for v in [capex_low, capex_high, interval_months, downtime_cost, current_avail, target_avail, legacy_annual]
        )
        if not has_inputs:
            return None

        capex_events = None
        if interval_months and interval_months > 0:
            capex_events = (horizon_years * 12) / interval_months

        capex_savings_low = capex_low * capex_events if capex_low is not None and capex_events else None
        capex_savings_high = capex_high * capex_events if capex_high is not None and capex_events else None
        if capex_savings_low is None and capex_savings_high is None and capex_events and capex_low is not None:
            capex_savings_low = capex_low * capex_events

        downtime_savings = None
        if downtime_cost is not None and current_avail is not None and target_avail is not None:
            hours_per_year = 24 * 365
            current_down = hours_per_year * max(0.0, 1 - (current_avail / 100))
            target_down = hours_per_year * max(0.0, 1 - (target_avail / 100))
            delta = max(0.0, current_down - target_down)
            downtime_savings = delta * downtime_cost * horizon_years

        legacy_savings = legacy_annual * horizon_years if legacy_annual is not None else None

        total_savings_low = 0.0
        total_savings_high = 0.0
        has_range = capex_savings_low is not None and capex_savings_high is not None

        for val in [capex_savings_low, downtime_savings, legacy_savings]:
            if val is not None:
                total_savings_low += val
        for val in [capex_savings_high or capex_savings_low, downtime_savings, legacy_savings]:
            if val is not None:
                total_savings_high += val

        net_benefit_low = total_savings_low - total_cost
        net_benefit_high = total_savings_high - total_cost

        return {
            "horizon_years": horizon_years,
            "capex_events": capex_events,
            "capex_savings_low": capex_savings_low,
            "capex_savings_high": capex_savings_high if has_range else None,
            "downtime_savings": downtime_savings,
            "legacy_savings": legacy_savings,
            "total_savings_low": total_savings_low,
            "total_savings_high": total_savings_high if has_range else None,
            "net_benefit_low": net_benefit_low,
            "net_benefit_high": net_benefit_high if has_range else None,
            "current_availability": current_avail,
            "target_availability": target_avail,
            "downtime_cost_per_hour": downtime_cost,
            "capex_interval_months": interval_months,
        }

    def generate_estimation_pdf(
        self,
        estimation_data: Dict[str, Any],
        input_summary: Dict[str, Any],
        narrative_sections: Optional[Dict[str, str]] = None,
        module_subtasks: Optional[List[Dict[str, Any]]] = None,
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
        project_info = estimation_data.get('project_info') or {}

        services_summary = self._build_services_summary(result)
        if services_summary:
            story.append(Paragraph(f"<b>Services Summary:</b> {escape(services_summary)}", self.styles['Normal']))
            story.append(Spacer(1, 10))

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
        story.append(Spacer(1, 8))

        roi_summary = self._compute_roi_summary(estimation_data, float(result.get('total_cost', 0) or 0))

        if narrative_sections and narrative_sections.get('executive_summary'):
            story.append(Paragraph(narrative_sections['executive_summary'], self.styles['Normal']))
            story.append(Spacer(1, 12))
        else:
            story.append(Spacer(1, 4))

        if roi_summary:
            story.append(Paragraph("5-Year Net Fiscal Benefit Summary", self.styles['SubsectionHeader']))
            savings_rows = [
                ["Avoided Emergency CapEx", self._format_money_range(roi_summary.get("capex_savings_low"), roi_summary.get("capex_savings_high"))],
                ["Avoided Downtime Loss", self._format_money(roi_summary.get("downtime_savings"))],
                ["Legacy Support Savings", self._format_money(roi_summary.get("legacy_savings"))],
                ["Total Avoided Cost", self._format_money_range(roi_summary.get("total_savings_low"), roi_summary.get("total_savings_high"))],
                ["Net Fiscal Benefit (5-year)", self._format_money_range(roi_summary.get("net_benefit_low"), roi_summary.get("net_benefit_high"))],
            ]
            savings_table = Table(savings_rows, colWidths=[3.1*inch, 1.9*inch])
            savings_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]))
            story.append(savings_table)
            assumptions_bits = []
            if roi_summary.get("capex_interval_months"):
                assumptions_bits.append(f"CapEx interval: {roi_summary.get('capex_interval_months'):.0f} months")
            if roi_summary.get("current_availability") is not None and roi_summary.get("target_availability") is not None:
                assumptions_bits.append(
                    f"Availability: {roi_summary.get('current_availability'):.2f}% → {roi_summary.get('target_availability'):.2f}%"
                )
            if roi_summary.get("downtime_cost_per_hour") is not None:
                assumptions_bits.append(f"Downtime cost: ${roi_summary.get('downtime_cost_per_hour'):,.2f}/hr")
            if assumptions_bits:
                story.append(Spacer(1, 6))
                story.append(Paragraph("Assumptions: " + "; ".join(assumptions_bits), self.styles['Normal']))
            story.append(Spacer(1, 12))

        if project_info:
            story.append(Paragraph("Project Information", self.styles['SubsectionHeader']))
            pi_rows = []
            placeholder = "Not provided (not found in RFP)"
            def add_pi(label: str, key: str):
                val = project_info.get(key)
                display = val if val not in (None, "", []) else placeholder
                pi_rows.append([
                    Paragraph(escape(label), self.styles['ProjectInfoLabel']),
                    Paragraph(escape(str(display)), self.styles['ProjectInfoValue']),
                ])
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
            add_pi('Security Protocols', 'security_protocols')
            add_pi('Compliance Frameworks', 'compliance_frameworks')
            add_pi('Additional Assumptions', 'additional_assumptions')
            add_pi('Comments', 'additional_comments')

            if pi_rows:
                pi_table = Table(pi_rows, colWidths=[2.2*inch, 4.3*inch])
                pi_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
                ]))
                story.append(pi_table)
                story.append(Spacer(1, 16))

        # Optional scraped contract context (if provided)
        contract_src = estimation_data.get('contract_source') or {}
        if contract_src.get('url') or contract_src.get('excerpt'):
            story.append(Spacer(1, 12))
            story.append(Paragraph("Contract Source (Scraped)", self.styles['SectionHeader']))
            excerpt = contract_src.get('excerpt')
            if excerpt:
                paragraphs = self._format_contract_excerpt(str(excerpt))
                for para in paragraphs:
                    story.append(para)
                    story.append(Spacer(1, 6))
                story.append(Spacer(1, 10))

        # Optional AI-generated narrative blocks
        if narrative_sections:
            for key in ["assumptions", "risks", "next_steps"]:
                if narrative_sections.get(key):
                    title = key.replace('_', ' ').title()
                    story.append(Paragraph(title, self.styles['SectionHeader']))
                    story.append(Paragraph(narrative_sections[key], self.styles['Normal']))
                    story.append(Spacer(1, 16))

        raci_rows = estimation_data.get("raci_matrix") or []
        if raci_rows:
            story.append(Paragraph("Roles & Responsibilities (RACI)", self.styles['SectionHeader']))
            story.append(Paragraph(
                "This RACI chart is intended as a binding appendix to the Statement of Work.",
                self.styles['Normal']
            ))
            table_rows = [["Milestone", "Responsible", "Accountable", "Consulted", "Informed"]]
            for row in raci_rows:
                table_rows.append([
                    str(row.get("milestone") or ""),
                    str(row.get("responsible") or ""),
                    str(row.get("accountable") or ""),
                    str(row.get("consulted") or ""),
                    str(row.get("informed") or ""),
                ])
            raci_table = Table(table_rows, colWidths=[1.6*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1.2*inch])
            raci_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(raci_table)
            story.append(Spacer(1, 16))

        roadmap_phases = estimation_data.get("roadmap_phases") or []
        if roadmap_phases:
            story.append(Paragraph("Phased Implementation Roadmap", self.styles['SectionHeader']))
            roadmap_rows = [["Phase", "Timeline", "Description"]]
            for phase in roadmap_phases:
                title = str(phase.get("title") or "").strip()
                description = str(phase.get("description") or "")
                if title and description:
                    description = f"{title}: {description}"
                elif title and not description:
                    description = title
                roadmap_rows.append([
                    str(phase.get("phase") or ""),
                    str(phase.get("timeline") or ""),
                    description,
                ])
            roadmap_table = Table(roadmap_rows, colWidths=[1.3*inch, 1.3*inch, 3.8*inch])
            roadmap_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(roadmap_table)
            story.append(Spacer(1, 16))
        
        # Cost Breakdown
        story.append(Paragraph("Cost Breakdown", self.styles['SectionHeader']))
        
        add_costs = result.get('additional_costs') or {}
        cost_data = [
            ['Component', 'Amount', 'Percentage'],
            ['Labor Cost', f"${result['total_labor_cost']:,.2f}", 
             f"{(result['total_labor_cost']/result['total_cost']*100):.1f}%"],
            ['Management Reserve', f"${result['risk_reserve']:,.2f}", 
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

        mr_total = float(result.get('risk_reserve', 0) or 0)
        if mr_total > 0:
            story.append(Paragraph("Management Reserve Allocation", self.styles['SectionHeader']))
            mr_allocations = [
                ("Hardware Contingency", 0.40, "Rapid-response buffer for essential high-failure replacement parts."),
                ("Schedule Buffer & Surge Staffing", 0.35, "Pre-approved overtime or surge staffing to recover schedule slips."),
                ("Data Conversion Validation Buffer", 0.25, "Independent validation services to confirm data migration quality."),
            ]
            rows = [['Category', 'Allocation', 'Use']]
            allocated = 0.0
            for idx, (label, pct, note) in enumerate(mr_allocations):
                amount = round(mr_total * pct, 2)
                allocated += amount
                rows.append([label, f"${amount:,.2f}", note])
            if allocated != mr_total:
                delta = round(mr_total - allocated, 2)
                rows.append(["Adjustment", f"${delta:,.2f}", "Rounding correction to match total reserve."])
            mr_table = Table(rows, colWidths=[2.2*inch, 1.3*inch, 3.3*inch])
            mr_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ]))
            story.append(mr_table)
            story.append(Spacer(1, 6))
            story.append(Paragraph(
                "Management Reserve is held for risk mitigation and is not returned to the customer. "
                "Any unused balance is retained as profit.",
                self.styles['Normal']
            ))
            story.append(Spacer(1, 16))
        
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

        # SOP-style Subtasks for each module
        subtask_blocks = module_subtasks if module_subtasks is not None else estimation_data.get('module_subtasks')
        if subtask_blocks:
            story.append(Paragraph("Module Subtasks", self.styles['SectionHeader']))
            status = estimation_data.get("subtask_generation_status")
            error_msg = estimation_data.get("subtask_generation_error")
            if status and status != "ai_generated":
                msg = "AI subtasks not used; showing deterministic subtasks."
                if status == "ai_failed":
                    msg = f"AI subtasks failed; showing deterministic subtasks. Error: {error_msg or 'unknown'}"
                elif status == "ai_disabled":
                    msg = "AI subtasks disabled; showing deterministic subtasks."
                story.append(Paragraph(msg, self.styles['Normal']))
                story.append(Spacer(1, 6))
            for subtask in subtask_blocks:
                seq = subtask.get("sequence")
                heading = f"{seq}. {subtask.get('module_name')}" if seq else str(subtask.get("module_name") or "Subtask")
                focus = subtask.get("focus_label") or subtask.get("focus_area") or ""
                story.append(Paragraph(f"{heading} ({focus})", self.styles['SubtaskHeader']))

                def p(txt: str, style_name: str = 'SubtaskBody'):
                    return Paragraph(str(txt or ''), self.styles[style_name])

                detail_rows = [
                    [p('What is the work scope for this subtask?', 'SubtaskLabel'), p(subtask.get('work_scope', ''))],
                    [p('Estimating Method', 'SubtaskLabel'), p(subtask.get('estimating_method', 'Engineering Discrete'))],
                    [p('How is the estimate of this subtask derived?', 'SubtaskLabel'), p(subtask.get('period_of_performance', ''))],
                ]
                if subtask.get('reasonableness'):
                    detail_rows.append([p('What makes the estimate reasonable?', 'SubtaskLabel'), p(subtask.get('reasonableness', ''))])
                if subtask.get('security_protocols'):
                    detail_rows.append([p('Security Protocols', 'SubtaskLabel'), p(subtask.get('security_protocols', ''))])
                if subtask.get('compliance_frameworks'):
                    detail_rows.append([p('Compliance Frameworks', 'SubtaskLabel'), p(subtask.get('compliance_frameworks', ''))])
                if subtask.get('customer_context'):
                    detail_rows.append([p('Customer Context', 'SubtaskLabel'), p(subtask.get('customer_context', ''))])

                # Keep within the ~6.5in content width (letter page with 1in margins)
                details_table = Table(detail_rows, colWidths=[1.9*inch, 4.1*inch])
                details_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))
                story.append(details_table)
                story.append(Spacer(1, 8))

                tasks = subtask.get('tasks') or []
                if tasks:
                    task_rows = [['Subtask Description', 'Calculation', 'Hours']]
                    # Header row with module name and total
                    task_rows.append([
                        p(f"{subtask.get('module_name', 'Subtask')} ({subtask.get('focus_area', '')})", 'SubtaskLabel'),
                        '',
                        f"{float(subtask.get('total_hours', 0)):.1f}"
                    ])
                    for task in tasks:
                        task_rows.append([
                            p(task.get('title', ''), 'SubtaskBody'),
                            p(task.get('calculation', ''), 'SubtaskBody'),
                            f"{float(task.get('hours', 0)):.1f}"
                        ])
                    task_rows.append(['Subtask Total', '', f"{float(subtask.get('total_hours', 0)):.1f}"])

                    task_table = Table(task_rows, colWidths=[2.3*inch, 2.9*inch, 1.0*inch])
                    task_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                        ('TOPPADDING', (0, 0), (-1, -1), 3),
                        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
                        ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                    ]))
                    story.append(task_table)
                story.append(Spacer(1, 18))
        elif subtask_blocks is not None:
            story.append(Paragraph("Module Subtasks", self.styles['SectionHeader']))
            story.append(Paragraph("No module subtasks were generated for the selected modules.", self.styles['Normal']))
            story.append(Spacer(1, 12))
        
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
        tool_version = estimation_data.get("tool_version")
        if tool_version:
            story.append(Paragraph(
                f"Tool version: {escape(str(tool_version))}",
                self.styles['Normal']
            ))
        story.append(Paragraph(
            f"Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            self.styles['Normal']
        ))

        # Build and return PDF
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
