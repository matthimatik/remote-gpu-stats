from abc import ABC, abstractmethod

class Metric(ABC):
    identifier: str
    """short metric identifier, e.g. 'cpu'"""
    command: str
    """shell command to collect data"""
    columns: list[str]
    """column names for display"""

    @abstractmethod
    def parse(self, raw_output: str) -> dict:
        """Parse raw command output into structured data."""
