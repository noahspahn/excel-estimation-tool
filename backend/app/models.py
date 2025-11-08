from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

class ComplexityLevel(str, Enum):
    SMALL = "S"
    MEDIUM = "M" 
    LARGE = "L"
    EXTRA_LARGE = "XL"

class FocusArea(str, Enum):
    DIGITAL_TRANSFORMATION = "DT"
    IT_MODERNIZATION = "ITM"
    SECURITY_ASSURANCE = "SA"
    CLOUD_MIGRATION = "CM"
    DATA_ANALYTICS = "DA"

@dataclass
class Role:
    id: str
    name: str
    base_hourly_rate: float
    clearance_multiplier: Dict[str, float] = field(default_factory=lambda: {
        "none": 1.0,
        "public_trust": 1.1,
        "secret": 1.3,
        "top_secret": 1.6
    })
    geography_multiplier: Dict[str, float] = field(default_factory=lambda: {
        "dc_metro": 1.2,
        "major_city": 1.1,
        "standard": 1.0,
        "rural": 0.9
    })

@dataclass
class Module:
    id: str
    name: str
    focus_area: FocusArea
    base_hours_by_role: Dict[str, float]
    prerequisites: List[str] = field(default_factory=list)
    risk_factor: float = 1.0

@dataclass
class ComplexityMatrix:
    base_multiplier: Dict[ComplexityLevel, float] = field(default_factory=lambda: {
        ComplexityLevel.SMALL: 0.7,
        ComplexityLevel.MEDIUM: 1.0,
        ComplexityLevel.LARGE: 1.6,
        ComplexityLevel.EXTRA_LARGE: 2.3
    })
    
    environment_factor: Dict[str, float] = field(default_factory=lambda: {
        "development": 1.0,
        "staging": 1.2,
        "production": 1.5,
        "classified": 2.0
    })
    
    integration_complexity: Dict[str, float] = field(default_factory=lambda: {
        "standalone": 1.0,
        "light_integration": 1.2,
        "moderate_integration": 1.5,
        "heavy_integration": 2.0
    })

@dataclass
class EstimationRules:
    min_project_hours: float = 40.0
    max_single_module_hours: float = 2000.0
    utilization_rate: float = 0.85
    risk_reserve_percentage: float = 0.15
    overhead_multiplier: float = 1.2
    prime_contractor_margin: float = 0.15

@dataclass
class EstimationInput:
    modules: List[str]
    complexity: ComplexityLevel
    environment: str = "production"
    integration_level: str = "moderate_integration"
    geography: str = "dc_metro"
    clearance_level: str = "secret"
    is_prime_contractor: bool = True
    custom_role_overrides: Dict[str, float] = field(default_factory=dict)
    # Extended inputs inspired by legacy INPUT sheet
    project_name: Optional[str] = None
    government_poc: Optional[str] = None
    account_manager: Optional[str] = None
    service_delivery_mgr: Optional[str] = None
    service_delivery_exec: Optional[str] = None
    site_location: Optional[str] = None
    email: Optional[str] = None
    fy: Optional[str] = None
    rap_number: Optional[str] = None
    psi_code: Optional[str] = None
    additional_comments: Optional[str] = None
    sites: int = 1
    overtime: bool = False
    # Other costs and fixed-price items (simple shape: {description, price})
    odc_items: List[Dict[str, Any]] = field(default_factory=list)
    fixed_price_items: List[Dict[str, Any]] = field(default_factory=list)
    hardware_subtotal: float = 0.0
    warranty_months: int = 0
    warranty_cost: float = 0.0

@dataclass
class EstimationResult:
    total_labor_hours: float
    total_labor_cost: float
    risk_reserve: float
    overhead_cost: float
    total_cost: float
    breakdown_by_module: Dict[str, Any]
    breakdown_by_role: Dict[str, Any]
    effective_hourly_rate: float
    # Additional cost components
    additional_costs: Dict[str, Any] = field(default_factory=dict)
