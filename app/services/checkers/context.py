from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class ValidationContext:
    buckets: Dict[str, int]
    deficiency_map: Dict[str, Any]
    passed_courses: List
    planned_courses: List
    req: Any
    transcript: Any
