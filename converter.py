"""Lógica de conversão de Markdown para PDF e extração de documentos para Markdown.

Este módulo é independente da interface Streamlit para facilitar testes
e reuso. A UI vive em ``main.py``.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from functools import lru_cache

import mammoth
import pymupdf
import pymupdf4llm
import pypandoc
from weasyprint import HTML

# ---------------------------------------------------------------------------
# Temas de PDF
# ---------------------------------------------------------------------------

# Estilos base compartilhados por todos os temas (tabelas, código, imagens...).
_BASE_CSS = """
    p { margin-bottom: 1em; }
    code {
        background-color: #f4f4f4;
        padding: 2px 5px;
        border-radius: 3px;
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
        font-size: 0.9em;
    }
    pre {
        background-color: #f4f4f4;
        padding: 16px;
        border-radius: 4px;
        overflow: auto;
        line-height: 1.45;
    }
    pre code { background: none; padding: 0; }
    blockquote {
        border-left: 4px solid #ddd;
        padding-left: 1em;
        color: #666;
        margin-left: 0;
    }
    table {
        border-collapse: collapse;
        width: 100%;
        margin-bottom: 1em;
    }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    th { background-color: #f2f2f2; }
    img { max-width: 100%; height: auto; }
    a { color: #3498db; text-decoration: none; }
    a:hover { text-decoration: underline; }
    ul, ol { margin-bottom: 1em; }
"""

_THEMES: dict[str, str] = {
    "Clássico": """
        body {
            font-family: Arial, Helvetica, sans-serif;
            line-height: 1.6;
            color: #333;
        }
        h1, h2, h3, h4, h5, h6 { color: #2c3e50; margin-top: 1.5em; margin-bottom: 0.5em; }
        h1 { font-size: 2.2em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }
        h2 { font-size: 1.8em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }
        h3 { font-size: 1.5em; }
        h4 { font-size: 1.3em; }
    """,
    "Moderno": """
        body {
            font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
            line-height: 1.7;
            color: #1a1a1a;
        }
        h1, h2, h3, h4, h5, h6 { color: #0f172a; font-weight: 600; margin-top: 1.6em; margin-bottom: 0.5em; }
        h1 { font-size: 2.4em; letter-spacing: -0.02em; }
        h2 { font-size: 1.9em; letter-spacing: -0.01em; }
        h3 { font-size: 1.5em; }
        h4 { font-size: 1.25em; }
        a { color: #2563eb; }
        blockquote { border-left: 4px solid #2563eb; color: #475569; }
    """,
    "Acadêmico": """
        body {
            font-family: "Georgia", "Times New Roman", serif;
            line-height: 1.8;
            color: #222;
            text-align: justify;
        }
        h1, h2, h3, h4, h5, h6 { font-family: "Georgia", serif; color: #111; margin-top: 1.5em; margin-bottom: 0.5em; }
        h1 { font-size: 2em; text-align: center; }
        h2 { font-size: 1.6em; }
        h3 { font-size: 1.35em; }
        h4 { font-size: 1.15em; }
    """,
}

THEME_NAMES = list(_THEMES.keys())
PAGE_SIZES = ["A4", "Letter", "Legal"]
HIGHLIGHT_STYLES = [
    "tango",
    "pygments",
    "kate",
    "espresso",
    "zenburn",
    "breezedark",
    "haddock",
    "monochrome",
]


@dataclass
class PdfOptions:
    """Opções de renderização do PDF."""

    theme: str = "Clássico"
    page_size: str = "A4"
    margin: str = "2cm"
    show_page_numbers: bool = True
    highlight_style: str = "tango"


# ---------------------------------------------------------------------------
# Extração de texto de arquivos de entrada (PDF, DOCX, TXT, MD)
# ---------------------------------------------------------------------------

def extract_markdown(filename: str, data: bytes) -> str:
    """Extrai texto Markdown a partir do conteúdo bruto de um arquivo.

    Suporta ``.docx`` (mammoth), ``.pdf`` (pymupdf4llm) e arquivos de texto (``.txt``/``.md``).
    """
    lower = filename.lower()
    if lower.endswith(".docx"):
        return _extract_text_from_docx(data)
    elif lower.endswith(".pdf"):
        return _extract_text_from_pdf(data)
    
    # Arquivos .txt, .md e afins são tratados como texto puro UTF-8.
    return data.decode("utf-8", errors="replace")


def _extract_text_from_docx(data: bytes) -> str:
    """Extrai o texto de um arquivo DOCX diretamente da memória (sem arquivos temporários)."""
    result = mammoth.extract_raw_text(io.BytesIO(data))
    return result.value


def _extract_text_from_pdf(data: bytes) -> str:
    """Extrai texto no formato Markdown estruturado a partir de um PDF em memória."""
    # Abre o PDF a partir de um buffer de bytes na memória para evitar escrita em disco
    doc = pymupdf.open(stream=data, filetype="pdf")
    # Converte o documento PDF para Markdown formatado para consumo por LLMs
    return pymupdf4llm.to_markdown(doc)


# ---------------------------------------------------------------------------
# Conversão Markdown -> HTML -> PDF
# ---------------------------------------------------------------------------

def markdown_to_html(markdown_text: str, options: PdfOptions | None = None) -> str:
    """Converte Markdown em um documento HTML completo e estilizado."""
    options = options or PdfOptions()

    pandoc_format = "markdown+tex_math_dollars+backtick_code_blocks+pipe_tables+footnotes"
    extra_args = [f"--highlight-style={options.highlight_style}", "--mathjax"]
    body = pypandoc.convert_text(
        markdown_text, "html5", format=pandoc_format, extra_args=extra_args
    )

    theme_css = _THEMES.get(options.theme, _THEMES["Clássico"])
    highlight_css = _highlight_css(options.highlight_style)
    page_css = _page_css(options)
    mathjax = (
        '<script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>'
        '<script id="MathJax-script" async '
        'src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>'
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <style>
        {page_css}
        body {{ margin: 0; }}
        {theme_css}
        {_BASE_CSS}
        {highlight_css}
    </style>
    {mathjax}
</head>
<body>
{body}
</body>
</html>"""


_HIGHLIGHT_MARKER = "/* CSS for syntax highlighting */"


@lru_cache(maxsize=None)
def _highlight_css(style: str) -> str:
    """Retorna o CSS de destaque de sintaxe do pandoc para um estilo."""
    sample = "```python\ndef _f(x):\n    return x\n```"
    try:
        standalone = pypandoc.convert_text(
            sample,
            "html5",
            format="markdown",
            extra_args=["--standalone", f"--highlight-style={style}"],
        )
    except Exception:
        return ""

    start = standalone.find("<style")
    end = standalone.find("</style>", start)
    if start == -1 or end == -1:
        return ""
    block = standalone[standalone.find(">", start) + 1 : end]

    marker_pos = block.find(_HIGHLIGHT_MARKER)
    if marker_pos == -1:
        return ""
    return block[marker_pos + len(_HIGHLIGHT_MARKER):].strip()


def _page_css(options: PdfOptions) -> str:
    """Gera a regra @page (tamanho, margem e numeração de página)."""
    footer = ""
    if options.show_page_numbers:
        footer = """
            @bottom-center {
                content: counter(page) " / " counter(pages);
                font-size: 9pt;
                color: #888;
            }
        """
    return f"""
        @page {{
            size: {options.page_size};
            margin: {options.margin};
            {footer}
        }}
    """


def markdown_to_pdf(markdown_text: str, options: PdfOptions | None = None) -> bytes:
    """Converte texto Markdown para os bytes de um PDF."""
    html = markdown_to_html(markdown_text, options)
    return HTML(string=html).write_pdf()
