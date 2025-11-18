"""
llm-do: Spec-driven automation with LLM and progressive hardening

Write workflows as natural language specs, execute them with LLM + tools,
progressively harden proven patterns into tested functions.
"""

__version__ = "0.1.0"

from .toolbox import BaseToolbox
from .executor import execute_spec

__all__ = ["BaseToolbox", "execute_spec"]
