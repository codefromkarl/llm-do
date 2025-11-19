"""Helper tools for working with templates."""

from typing import Iterable

import llm


class TemplateHelpers(llm.Toolbox):
    """Helper functions for template generation and manipulation."""

    name = "TemplateHelpers"

    def make_template(self, prompt_text: str) -> str:
        """
        Create a standard template YAML with user-provided prompt text.

        Returns a properly formatted YAML template string that can be written
        to a .yaml file and used with TemplateCall.

        Args:
            prompt_text: The prompt instructions for the template

        Returns:
            Complete YAML template as a string
        """
        return f"""system: |
  You solve exactly one unit of work.
  Respect any attached procedures/fragments.
  Provide a clear, well-structured response.

prompt: |
  {prompt_text}
"""


__all__: Iterable[str] = ["TemplateHelpers"]
