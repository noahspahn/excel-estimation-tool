# backend/app/services/calculation_service.py
from typing import Any, Dict, List, Optional
import math
from ..models import (
    EstimationInput, EstimationResult, Module, Role, 
    ComplexityMatrix, EstimationRules, ComplexityLevel
)
from .data_service import DataService

class CalculationService:
    def __init__(self):
        self.data_service = DataService()
        self.complexity_matrix = ComplexityMatrix()
        self.rules = EstimationRules()
    
    def calculate_estimate(self, input_data: EstimationInput) -> EstimationResult:
        """Main estimation calculation method"""
        
        # Get modules and roles from data service
        modules = [self.data_service.get_module(mid) for mid in input_data.modules]
        roles = self.data_service.get_all_roles()
        
        # Calculate total hours and costs by role
        role_breakdown = {}
        total_labor_hours = 0
        total_labor_cost = 0

        for role in roles.values():
            role_hours = self._calculate_role_hours(role, modules, input_data)
            if role_hours > 0:
                effective_rate = self._calculate_effective_rate(role, input_data)
                role_cost = role_hours * effective_rate
                
                role_breakdown[role.id] = {
                    "role_name": role.name,
                    "hours": role_hours,
                    "effective_rate": effective_rate,
                    "cost": role_cost
                }
                
                total_labor_hours += role_hours
                total_labor_cost += role_cost
        
        # Calculate module breakdown
        module_breakdown = {}
        for module in modules:
            module_hours = self._calculate_module_hours(module, input_data)
            module_cost = sum(
                role_breakdown.get(role_id, {}).get("cost", 0) 
                for role_id in module.base_hours_by_role.keys()
                if role_id in role_breakdown
            )
            
            module_breakdown[module.id] = {
                "module_name": module.name,
                "focus_area": module.focus_area.value,
                "hours": module_hours,
                "cost": module_cost
            }
        
        # Apply business rules
        risk_reserve = total_labor_cost * self.rules.risk_reserve_percentage
        overhead_cost = total_labor_cost * (self.rules.overhead_multiplier - 1)

        # Additional cost components
        odc_total = sum(float(item.get("price", 0)) for item in (input_data.odc_items or []))
        fixed_price_total = sum(float(item.get("price", 0)) for item in (input_data.fixed_price_items or []))
        hardware_subtotal = float(input_data.hardware_subtotal or 0)
        warranty_cost = float(input_data.warranty_cost or 0)

        # Add prime contractor margin if applicable
        subtotal = total_labor_cost + risk_reserve + overhead_cost + odc_total + fixed_price_total + hardware_subtotal + warranty_cost
        if input_data.is_prime_contractor:
            margin = subtotal * self.rules.prime_contractor_margin
            total_cost = subtotal + margin
        else:
            total_cost = subtotal
        
        effective_hourly_rate = total_cost / total_labor_hours if total_labor_hours > 0 else 0
        
        return EstimationResult(
            total_labor_hours=total_labor_hours,
            total_labor_cost=total_labor_cost,
            risk_reserve=risk_reserve,
            overhead_cost=overhead_cost,
            total_cost=total_cost,
            breakdown_by_module=module_breakdown,
            breakdown_by_role=role_breakdown,
            effective_hourly_rate=effective_hourly_rate,
            additional_costs={
                "odc_total": odc_total,
                "fixed_price_total": fixed_price_total,
                "hardware_subtotal": hardware_subtotal,
                "warranty_cost": warranty_cost,
                "sites": input_data.sites,
                "overtime": input_data.overtime,
            }
        )
    
    def build_module_subtasks(
        self,
        input_data: EstimationInput,
        contract_excerpt: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Build a structured list of module-aligned subtasks for reporting.

        The subtasks mirror an SOP-style breakdown and reuse the same module
        catalog and multiplier logic that drives cost calculations.
        """
        scope_templates: Dict[str, str] = {
            "DT": "Discovery, mapping, and transformation planning activities that align stakeholders and document current/future state.",
            "ITM": "Modernization execution covering infrastructure refresh, migrations, validation, and operational cutovers.",
            "SA": "Security and compliance support including assessments, control validation, and audit readiness coordination (e.g., DFARS/RMF).",
            "CM": "Cloud adoption tasks spanning readiness, landing zone alignment, migration planning, and cutover assistance.",
            "DA": "Data enablement tasks such as ingestion, pipeline buildout, quality checks, and analytics readiness.",
        }

        modules = [self.data_service.get_module(mid) for mid in input_data.modules]
        modules = [m for m in modules if m]
        roles = self.data_service.get_all_roles()
        multiplier = self._get_complexity_multiplier(input_data)
        multiplier_note = (
            f"complexity={input_data.complexity.value}, "
            f"environment={input_data.environment}, "
            f"integration={input_data.integration_level}, "
            f"sites={max(1, int(input_data.sites or 1))}"
        )

        subtasks: List[Dict[str, Any]] = []

        for idx, module in enumerate(modules, start=1):
            tasks = []
            for role_id, base_hours in module.base_hours_by_role.items():
                role = roles.get(role_id)
                override = input_data.custom_role_overrides.get(role_id, 1.0)
                role_hours = base_hours * multiplier * override
                calc_parts = [
                    f"{base_hours:.1f}h base",
                    f"x {multiplier:.2f} (complexity/env/integration/sites)",
                ]
                if override != 1.0:
                    calc_parts.append(f"x override {override:.2f}")
                tasks.append(
                    {
                        "title": f"{role.name if role else role_id} delivery",
                        "calculation": " ".join(calc_parts),
                        "hours": round(role_hours, 1),
                    }
                )

            total_hours = round(sum(t["hours"] for t in tasks), 1)
            focus_label = module.focus_area.name.replace("_", " ").title()

            subtask = {
                "sequence": idx,
                "module_id": module.id,
                "module_name": module.name,
                "focus_area": module.focus_area.value,
                "focus_label": focus_label,
                "work_scope": scope_templates.get(
                    module.focus_area.value,
                    f"Delivery tasks for the {module.name} module.",
                ),
                "estimating_method": "Engineering Discrete",
                "estimate_basis": (
                    "Discrete engineering estimate using cataloged role hours; no isolated historicals. "
                    "SME judgment applied for similar classified programs where direct actuals are unavailable."
                ),
                "period_of_performance": (
                    "Proposed Period of Performance: adjust to the customer schedule; "
                    f"default assumes a 12-month window across {max(1, int(input_data.sites or 1))} site(s)."
                ),
                "tasks": tasks,
                "total_hours": total_hours,
                "reasonableness": (
                    "Uses the same module catalog and multiplier logic as the cost "
                    "estimate to keep assumptions traceable and auditable."
                ),
            }

            if module.focus_area.value == "SA":
                if input_data.security_protocols:
                    subtask["security_protocols"] = input_data.security_protocols
                if input_data.compliance_frameworks:
                    subtask["compliance_frameworks"] = input_data.compliance_frameworks

            if contract_excerpt:
                subtask["customer_context"] = contract_excerpt.strip()[:1200]

            subtasks.append(subtask)

        # Light-weight tailoring: extract requirement hints from contract excerpt
        if contract_excerpt:
            lowered = contract_excerpt.lower()
            keywords = []
            compliance_map = {
                "rmf": "RMF",
                "dfars": "DFARS",
                "cmmc": "CMMC",
                "fedramp": "FedRAMP",
                "fisma": "FISMA",
                "hipaa": "HIPAA",
                "cjis": "CJIS",
                "pci dss": "PCI DSS",
                "iso 27001": "ISO 27001",
                "soc 2": "SOC 2",
                "nist 800-53": "NIST 800-53",
                "nist 800-171": "NIST 800-171",
            }
            for k in ["migration", "cloud", "server", "network", "audit", "compliance", "vmware", "aws", "azure", "tight timeline", "documentation"]:
                if k in lowered:
                    keywords.append(k)
            detected_compliance = []
            for key, label in compliance_map.items():
                if key in lowered:
                    detected_compliance.append(label)
            if detected_compliance:
                keywords.extend(detected_compliance)
            if keywords:
                for st in subtasks:
                    ctx = st.get("customer_context", "")
                    st["customer_context"] = (ctx + "\n\nDetected requirements: " + ", ".join(sorted(set(keywords)))).strip()
            if detected_compliance and not input_data.compliance_frameworks:
                frameworks = ", ".join(sorted(set(detected_compliance)))
                for st in subtasks:
                    if st.get("focus_area") == "SA":
                        st["compliance_frameworks"] = frameworks

        # Ensure subtasks are ordered and numbered
        for i, st in enumerate(subtasks, start=1):
            st["sequence"] = i

        return subtasks
    
    def _calculate_role_hours(self, role: Role, modules: List[Module], input_data: EstimationInput) -> float:
        """Calculate total hours for a specific role across all modules"""
        total_hours = 0
        
        for module in modules:
            base_hours = module.base_hours_by_role.get(role.id, 0)
            if base_hours > 0:
                # Apply complexity multiplier
                complexity_multiplier = self._get_complexity_multiplier(input_data)
                
                # Apply role-specific override if provided
                override_multiplier = input_data.custom_role_overrides.get(role.id, 1.0)
                
                # Calculate final hours for this role in this module
                module_role_hours = base_hours * complexity_multiplier * override_multiplier
                total_hours += module_role_hours
        
        return total_hours
    
    def _calculate_module_hours(self, module: Module, input_data: EstimationInput) -> float:
        """Calculate total hours for a specific module across all roles"""
        total_hours = 0
        complexity_multiplier = self._get_complexity_multiplier(input_data)
        
        for role_id, base_hours in module.base_hours_by_role.items():
            override_multiplier = input_data.custom_role_overrides.get(role_id, 1.0)
            module_role_hours = base_hours * complexity_multiplier * override_multiplier
            total_hours += module_role_hours
        
        return total_hours
    
    def _calculate_effective_rate(self, role: Role, input_data: EstimationInput) -> float:
        """Calculate effective hourly rate with all adjustments"""
        base_rate = role.base_hourly_rate
        
        # Apply geography multiplier
        geo_multiplier = role.geography_multiplier.get(input_data.geography, 1.0)
        
        # Apply clearance multiplier
        clearance_multiplier = role.clearance_multiplier.get(input_data.clearance_level, 1.0)
        
        # Overtime premium (if applicable) as a rate multiplier
        overtime_multiplier = 1.2 if input_data.overtime else 1.0

        # Calculate effective rate
        effective_rate = base_rate * geo_multiplier * clearance_multiplier * overtime_multiplier
        
        return effective_rate
    
    def _get_complexity_multiplier(self, input_data: EstimationInput) -> float:
        """Calculate combined complexity multiplier"""
        base_multiplier = self.complexity_matrix.base_multiplier[input_data.complexity]
        env_multiplier = self.complexity_matrix.environment_factor.get(input_data.environment, 1.0)
        integration_multiplier = self.complexity_matrix.integration_complexity.get(input_data.integration_level, 1.0)
        # Each additional site adds 15% to labor effort by default
        sites = max(1, int(input_data.sites or 1))
        sites_multiplier = 1.0 + 0.15 * (sites - 1)
        
        # Combined multiplier (multiplicative)
        return base_multiplier * env_multiplier * integration_multiplier * sites_multiplier
    
    def validate_estimate(self, input_data: EstimationInput) -> List[str]:
        """Validate estimation input and return any warnings/errors"""
        warnings = []
        
        # Check if modules exist
        for module_id in input_data.modules:
            if not self.data_service.get_module(module_id):
                warnings.append(f"Module {module_id} not found")
        
        # Check prerequisites
        selected_modules = [self.data_service.get_module(mid) for mid in input_data.modules if self.data_service.get_module(mid)]
        for module in selected_modules:
            for prereq in module.prerequisites:
                if prereq not in input_data.modules:
                    prereq_module = self.data_service.get_module(prereq)
                    prereq_name = prereq_module.name if prereq_module else prereq
                    warnings.append(f"Module '{module.name}' requires prerequisite '{prereq_name}'")
        
        # Check for reasonable complexity
        if len(input_data.modules) > 10 and input_data.complexity == ComplexityLevel.SMALL:
            warnings.append("Small complexity with many modules may be unrealistic")
        
        return warnings
