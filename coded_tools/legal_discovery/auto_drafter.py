from __future__ import annotations

"""Automated motion drafting using Gemini 2.5 models."""

from datetime import datetime
from pathlib import Path

from google import genai
import os
from docx import Document as DocxDocument
from weasyprint import HTML

from neuro_san.interfaces.coded_tool import CodedTool

from .template_library import TemplateLibrary


class AutoDrafter(CodedTool):
    """Generate legal motion drafts and export them."""

    def __init__(self, model_name: str = "gemini-2.5-flash", temperature: float = 0.2, **kwargs):
        super().__init__(**kwargs)
        self.templates = TemplateLibrary()
        self.model_name = model_name
        self.temperature = temperature

    def generate(self, motion_type: str, *, temperature: float | None = None) -> str:
        """Generate a draft for the given motion type using Gemini 2.5.

        Parameters
        ----------
        motion_type:
            The key of the motion template to use.
        temperature:
            Optional override for the sampling temperature.
        """
        prompt = self.templates.build_prompt(motion_type)
        temp = self.temperature if temperature is None else temperature
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY", ""))
        response = client.models.generate_content(
            model=self.model_name, contents=prompt, config=genai.types.GenerateContentConfig(temperature=temp)
        )
        return response.text

    def export(self, content: str, file_path: str, fmt: str | None = None) -> str:
        """Export reviewed content to DOCX or PDF.

        Parameters
        ----------
        content:
            The draft text that has been manually reviewed.
        file_path:
            Desired output path. The directory will be created if missing.
        fmt:
            Optional explicit format (``"docx"`` or ``"pdf"``). When omitted, the
            format is inferred from ``file_path``'s extension.
        """

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        format_ext = (fmt or path.suffix.lstrip(".")).lower()
        if format_ext == "pdf":
            if path.suffix.lower() != ".pdf":
                path = path.with_suffix(".pdf")
            html = f"<pre>{content}</pre>"
            HTML(string=html).write_pdf(str(path))
        else:
            if path.suffix.lower() != ".docx":
                path = path.with_suffix(".docx")
            doc = DocxDocument()
            for line in content.splitlines():
                doc.add_paragraph(line)
            doc.save(str(path))
        return str(path)
