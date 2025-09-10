# backend/app/services/data_service.py
from typing import Dict, List, Optional
from ..models import Module, Role, FocusArea

class DataService:
    """In-memory data service until database is implemented"""
    
    def __init__(self):
        self._roles = self._initialize_roles()
        self._modules = self._initialize_modules()
    
    def _initialize_roles(self) -> Dict[str, Role]:
        """Initialize role catalog based on original Excel system"""
        return {
            "solution_architect": Role(
                id="solution_architect",
                name="Solution Architect",
                base_hourly_rate=175.0
            ),
            "technical_lead": Role(
                id="technical_lead", 
                name="Technical Lead",
                base_hourly_rate=150.0
            ),
            "senior_engineer": Role(
                id="senior_engineer",
                name="Senior Engineer", 
                base_hourly_rate=135.0
            ),
            "engineer": Role(
                id="engineer",
                name="Engineer",
                base_hourly_rate=110.0
            ),
            "junior_engineer": Role(
                id="junior_engineer",
                name="Junior Engineer",
                base_hourly_rate=85.0
            ),
            "project_manager": Role(
                id="project_manager",
                name="Project Manager",
                base_hourly_rate=140.0
            ),
            "business_analyst": Role(
                id="business_analyst",
                name="Business Analyst",
                base_hourly_rate=125.0
            ),
            "security_specialist": Role(
                id="security_specialist",
                name="Security Specialist",
                base_hourly_rate=160.0
            ),
            "data_engineer": Role(
                id="data_engineer",
                name="Data Engineer",
                base_hourly_rate=145.0
            ),
            "cloud_architect": Role(
                id="cloud_architect",
                name="Cloud Architect",
                base_hourly_rate=165.0
            )
        }
    
    def _initialize_modules(self) -> Dict[str, Module]:
        """Initialize module library based on original Excel system"""
        return {
            # Digital Transformation Modules
            "dt_discovery": Module(
                id="dt_discovery",
                name="Discovery & Current State Mapping",
                focus_area=FocusArea.DIGITAL_TRANSFORMATION,
                base_hours_by_role={
                    "solution_architect": 40,
                    "business_analyst": 80,
                    "senior_engineer": 60,
                    "project_manager": 30
                }
            ),
            "dt_strategy": Module(
                id="dt_strategy",
                name="Digital Strategy Development",
                focus_area=FocusArea.DIGITAL_TRANSFORMATION,
                base_hours_by_role={
                    "solution_architect": 60,
                    "business_analyst": 100,
                    "project_manager": 40
                },
                prerequisites=["dt_discovery"]
            ),
            
            # IT Modernization Modules  
            "itm_assessment": Module(
                id="itm_assessment",
                name="Legacy System Assessment",
                focus_area=FocusArea.IT_MODERNIZATION,
                base_hours_by_role={
                    "solution_architect": 50,
                    "technical_lead": 80,
                    "senior_engineer": 120,
                    "security_specialist": 40
                }
            ),
            "itm_network_refresh": Module(
                id="itm_network_refresh", 
                name="Network Core Refresh",
                focus_area=FocusArea.IT_MODERNIZATION,
                base_hours_by_role={
                    "technical_lead": 100,
                    "senior_engineer": 200,
                    "engineer": 150,
                    "project_manager": 50
                }
            ),
            "itm_server_migration": Module(
                id="itm_server_migration",
                name="Server Infrastructure Migration", 
                focus_area=FocusArea.IT_MODERNIZATION,
                base_hours_by_role={
                    "solution_architect": 60,
                    "technical_lead": 80,
                    "senior_engineer": 160,
                    "engineer": 200,
                    "project_manager": 60
                }
            ),
            
            # Security Assurance Modules
            "sa_audit": Module(
                id="sa_audit",
                name="Security Audit & Assessment",
                focus_area=FocusArea.SECURITY_ASSURANCE,
                base_hours_by_role={
                    "security_specialist": 120,
                    "senior_engineer": 80,
                    "business_analyst": 40
                }
            ),
            "sa_compliance": Module(
                id="sa_compliance",
                name="Compliance Framework Implementation",
                focus_area=FocusArea.SECURITY_ASSURANCE, 
                base_hours_by_role={
                    "security_specialist": 160,
                    "solution_architect": 40,
                    "business_analyst": 80,
                    "project_manager": 60
                },
                prerequisites=["sa_audit"]
            ),
            "sa_license_audit": Module(
                id="sa_license_audit",
                name="License Audit & Rightsizing",
                focus_area=FocusArea.SECURITY_ASSURANCE,
                base_hours_by_role={
                    "business_analyst": 60,
                    "senior_engineer": 40,
                    "project_manager": 20
                }
            ),
            
            # Cloud Migration Modules
            "cm_assessment": Module(
                id="cm_assessment",
                name="Cloud Readiness Assessment",
                focus_area=FocusArea.CLOUD_MIGRATION,
                base_hours_by_role={
                    "cloud_architect": 80,
                    "solution_architect": 40,
                    "security_specialist": 60,
                    "business_analyst": 40
                }
            ),
            "cm_migration_plan": Module(
                id="cm_migration_plan",
                name="Cloud Migration Planning",
                focus_area=FocusArea.CLOUD_MIGRATION,
                base_hours_by_role={
                    "cloud_architect": 100,
                    "solution_architect": 60,
                    "project_manager": 80
                },
                prerequisites=["cm_assessment"]
            ),
            "cm_workload_migration": Module(
                id="cm_workload_migration",
                name="Workload Migration Execution",
                focus_area=FocusArea.CLOUD_MIGRATION,
                base_hours_by_role={
                    "cloud_architect": 60,
                    "technical_lead": 100,
                    "senior_engineer": 200,
                    "engineer": 240,
                    "project_manager": 80
                },
                prerequisites=["cm_migration_plan"]
            ),
            
            # Data Analytics Modules
            "da_discovery": Module(
                id="da_discovery", 
                name="Data Landscape Discovery",
                focus_area=FocusArea.DATA_ANALYTICS,
                base_hours_by_role={
                    "data_engineer": 80,
                    "business_analyst": 100,
                    "solution_architect": 40
                }
            ),
            "da_pipeline": Module(
                id="da_pipeline",
                name="Data Pipeline Development",
                focus_area=FocusArea.DATA_ANALYTICS,
                base_hours_by_role={
                    "data_engineer": 160,
                    "senior_engineer": 120,
                    "engineer": 100,
                    "project_manager": 40
                },
                prerequisites=["da_discovery"]
            )
        }
    
    def get_module(self, module_id: str) -> Optional[Module]:
        """Get a specific module by ID"""
        return self._modules.get(module_id)
    
    def get_modules_by_focus_area(self, focus_area: FocusArea) -> List[Module]:
        """Get all modules for a specific focus area"""
        return [module for module in self._modules.values() if module.focus_area == focus_area]
    
    def get_all_modules(self) -> Dict[str, Module]:
        """Get all modules"""
        return self._modules.copy()
    
    def get_role(self, role_id: str) -> Optional[Role]:
        """Get a specific role by ID"""
        return self._roles.get(role_id)
    
    def get_all_roles(self) -> Dict[str, Role]:
        """Get all roles"""
        return self._roles.copy()
    
    def get_focus_areas(self) -> List[str]:
        """Get list of all focus areas"""
        return [fa.value for fa in FocusArea]