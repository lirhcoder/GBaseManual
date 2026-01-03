"""
PDF conversion utilities.

Provides additional PDF generation options and utilities.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, Any


class PDFConverter:
    """
    Converts HTML files to PDF with configurable options.

    Uses WeasyPrint for conversion.
    """

    def __init__(
        self,
        page_size: str = "A4",
        margin: str = "20mm",
        orientation: str = "portrait",
    ):
        self.page_size = page_size
        self.margin = margin
        self.orientation = orientation

    def convert(
        self,
        html_path: str | Path,
        output_path: Optional[str | Path] = None,
        stylesheets: Optional[list] = None,
    ) -> Path:
        """
        Convert an HTML file to PDF.

        Args:
            html_path: Path to HTML file
            output_path: Output PDF path (default: same name with .pdf)
            stylesheets: Additional CSS stylesheets

        Returns:
            Path to the generated PDF
        """
        try:
            from weasyprint import HTML, CSS
        except ImportError:
            raise ImportError(
                "WeasyPrint is required for PDF conversion. "
                "Install it with: pip install weasyprint"
            )

        html_path = Path(html_path)

        if output_path is None:
            output_path = html_path.with_suffix(".pdf")
        else:
            output_path = Path(output_path)

        # Build page style
        page_css = CSS(string=f"""
            @page {{
                size: {self.page_size} {self.orientation};
                margin: {self.margin};
            }}
        """)

        css_list = [page_css]
        if stylesheets:
            for stylesheet in stylesheets:
                if isinstance(stylesheet, str) and not stylesheet.startswith("http"):
                    css_list.append(CSS(filename=stylesheet))
                else:
                    css_list.append(CSS(string=stylesheet))

        # Convert
        HTML(filename=str(html_path)).write_pdf(
            str(output_path),
            stylesheets=css_list,
        )

        return output_path

    def convert_string(
        self,
        html_content: str,
        output_path: str | Path,
        base_url: Optional[str] = None,
    ) -> Path:
        """
        Convert HTML string to PDF.

        Args:
            html_content: HTML content as string
            output_path: Output PDF path
            base_url: Base URL for resolving relative links

        Returns:
            Path to the generated PDF
        """
        try:
            from weasyprint import HTML, CSS
        except ImportError:
            raise ImportError(
                "WeasyPrint is required for PDF conversion. "
                "Install it with: pip install weasyprint"
            )

        output_path = Path(output_path)

        page_css = CSS(string=f"""
            @page {{
                size: {self.page_size} {self.orientation};
                margin: {self.margin};
            }}
        """)

        HTML(string=html_content, base_url=base_url).write_pdf(
            str(output_path),
            stylesheets=[page_css],
        )

        return output_path


def html_to_pdf(
    html_path: str | Path,
    output_path: Optional[str | Path] = None,
    **options,
) -> Path:
    """
    Convenience function to convert HTML to PDF.

    Args:
        html_path: Path to HTML file
        output_path: Output PDF path
        **options: PDFConverter options

    Returns:
        Path to the generated PDF
    """
    converter = PDFConverter(**options)
    return converter.convert(html_path, output_path)
