from dataclasses import dataclass

@dataclass(frozen=True)
class HazardCategoryDefinition:
    hazard_name: str
    description: str
    response_time_days: int