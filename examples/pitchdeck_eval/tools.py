"""
Custom toolbox for pitchdeck evaluation

Extends BaseToolbox with domain-specific hardened tools.
"""

import re
import sys
from pathlib import Path

# Add parent directory to path to import llm_do
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from llm_do import BaseToolbox


class PitchdeckToolbox(BaseToolbox):
    """
    Toolbox for pitchdeck evaluation workflows.

    Adds hardened tools for filename normalization and other
    pitchdeck-specific operations.
    """

    def normalize_filename(self, filename: str) -> str:
        """
        Normalize a filename for use as company name.
        Removes .pdf/.PDF extension, spaces, special characters.
        Keeps alphanumeric characters and hyphens only.

        This is a hardened tool - consistent, tested behavior.

        Examples:
            normalize_filename("Real Research (YC S24).pdf") -> "RealResearchYCS24"
            normalize_filename("Startup Name - Deck.pdf") -> "StartupName-Deck"
            normalize_filename("Company_Name.pdf") -> "CompanyName"

        Args:
            filename: PDF filename to normalize

        Returns:
            Normalized company name
        """
        # Remove PDF extension (case insensitive)
        name = filename.replace('.pdf', '').replace('.PDF', '')

        # Remove spaces and special chars except hyphens
        name = re.sub(r'[^a-zA-Z0-9-]', '', name.replace(' ', ''))

        return name
