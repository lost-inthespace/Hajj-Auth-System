# workflow_phase.py
from enum import Enum, auto

class WorkflowPhase(Enum):
    """Authentication workflow phases"""
    PHASE_ONE = auto()  # NFC scanning and fingerprint verification
    PHASE_TWO = auto()  # PIN entry and trip management