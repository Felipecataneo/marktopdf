"""Lógica de conversão de Markdown para PDF e extração de documentos para Markdown.

Este módulo é independente da interface Streamlit para facilitar testes
e reuso. A UI vive em ``main.py``.
"""

from __future__ import annotations

import io
import re
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

PDF_ENGINES = ["Automático (layout por IA)", "Clássico (geométrico)"]


@dataclass
class PdfExtractOptions:
    """Opções de extração de Markdown a partir de PDFs.

    - ``engine``: "Automático" usa o motor de layout por IA do PyMuPDF
      (melhor para papers de duas colunas); "Clássico" usa a análise
      geométrica de colunas, útil quando o automático embaralha a ordem.
    - ``strip_headers_footers``: remove cabeçalhos/rodapés repetidos e
      números de página.
    - ``include_picture_text``: inclui o texto sobreposto a figuras e
      diagramas (costuma sair embaralhado em papers).
    """

    engine: str = PDF_ENGINES[0]
    strip_headers_footers: bool = True
    include_picture_text: bool = False


def extract_markdown(
    filename: str, data: bytes, pdf_options: PdfExtractOptions | None = None
) -> str:
    """Extrai texto Markdown a partir do conteúdo bruto de um arquivo.

    Suporta ``.docx`` (mammoth), ``.pdf`` (pymupdf4llm) e arquivos de texto (``.txt``/``.md``).
    """
    lower = filename.lower()
    if lower.endswith(".docx"):
        return _extract_text_from_docx(data)
    elif lower.endswith(".pdf"):
        return _extract_text_from_pdf(data, pdf_options or PdfExtractOptions())

    # Arquivos .txt, .md e afins são tratados como texto puro UTF-8.
    return data.decode("utf-8", errors="replace")


def _extract_text_from_docx(data: bytes) -> str:
    """Extrai o texto de um arquivo DOCX diretamente da memória (sem arquivos temporários)."""
    result = mammoth.extract_raw_text(io.BytesIO(data))
    return result.value


def _layout_engine_available() -> bool:
    """Indica se o motor de layout por IA (pymupdf-layout) está instalado."""
    try:
        import pymupdf.layout  # noqa: F401
    except ImportError:
        return False
    return True


def _extract_text_from_pdf(data: bytes, options: PdfExtractOptions) -> str:
    """Extrai texto no formato Markdown estruturado a partir de um PDF em memória.

    Papers acadêmicos de duas colunas são o caso crítico: o motor de layout
    por IA reconstrói a ordem de leitura e a hierarquia de títulos; o motor
    clássico ordena blocos geometricamente. Em ambos os casos o resultado
    passa por uma limpeza final (parágrafos religados, linhas soltas etc.).
    """
    use_layout = options.engine == PDF_ENGINES[0] and _layout_engine_available()
    pymupdf4llm.use_layout(use_layout)

    # Abre o PDF a partir de um buffer de bytes na memória para evitar escrita em disco
    doc = pymupdf.open(stream=data, filetype="pdf")

    strip = options.strip_headers_footers
    if use_layout:
        # Motor de IA: header/footer controlam cabeçalhos/rodapés repetidos;
        # force_text=False descarta o texto sobreposto a figuras/diagramas.
        md = pymupdf4llm.to_markdown(
            doc,
            header=not strip,
            footer=not strip,
            force_text=options.include_picture_text,
        )
    else:
        # Motor clássico: margins ignora faixas do topo/rodapé da página.
        # force_text=False não é suportado sem exportar imagens, então o
        # texto de figuras é sempre incluído neste motor.
        md = pymupdf4llm.to_markdown(
            doc,
            margins=(0, 50, 0, 50) if strip else 0,
            table_strategy="lines_strict",
        )
    return _clean_pdf_markdown(md)


# Prefixos de linha que indicam estrutura Markdown que não deve ser re-fluida
# (títulos, tabelas, listas, citações, imagens, HTML/comentários).
_STRUCTURAL_PREFIXES = ("#", "|", "-", "*", "+", ">", "!", "<", "```", "~~~")
_ORDERED_ITEM_RE = re.compile(r"^\d{1,3}[.)]\s")
_PAGE_NUMBER_RE = re.compile(r"^\d{1,4}$")
# Fim de linha que sugere frase interrompida (sem pontuação terminal).
_UNTERMINATED_RE = re.compile(r"[\w,;)]$")


def _is_structural(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith(_STRUCTURAL_PREFIXES) or bool(
        _ORDERED_ITEM_RE.match(stripped)
    )


def _clean_pdf_markdown(md: str) -> str:
    """Limpeza final do Markdown extraído de um PDF.

    - remove espaços à direita e números de página em linhas isoladas;
    - religa linhas quebradas no meio de uma frase (inclusive hifenização);
    - religa parágrafos partidos por quebras de página/coluna;
    - normaliza sequências longas de linhas em branco.
    """
    lines = [line.rstrip() for line in md.splitlines()]

    result: list[str] = []
    in_code = False
    for line in lines:
        if line.lstrip().startswith(("```", "~~~")):
            in_code = not in_code
            result.append(line)
            continue
        if in_code:
            result.append(line)
            continue

        if _PAGE_NUMBER_RE.match(line.strip()):
            # Número de página isolado: descarta se estiver "flutuando" após
            # uma linha em branco; caso contrário mantém como linha própria
            # (nunca funde com o parágrafo anterior).
            if not result or result[-1] == "":
                continue
            result.append(line)
            continue

        prev = result[-1] if result else ""
        if (
            line
            and prev
            and not _is_structural(line)
            and not _is_structural(prev)
            and not _PAGE_NUMBER_RE.match(prev.strip())
            and not prev.endswith("\\")
        ):
            # Linha de continuação dentro do mesmo parágrafo (quebra "dura"
            # produzida pelo motor clássico): junta na linha anterior.
            if prev.endswith("-") and line[0].islower():
                result[-1] = prev[:-1] + line
            else:
                result[-1] = prev + " " + line
            continue

        result.append(line)

    # Religa parágrafos separados por linhas em branco quando o anterior
    # termina sem pontuação final e o seguinte começa em minúscula — típico
    # de parágrafos partidos na transição de coluna ou de página.
    merged: list[str] = []
    in_code = False
    for line in result:
        if line.lstrip().startswith(("```", "~~~")):
            in_code = not in_code
        if line and not in_code and not _is_structural(line):
            j = len(merged) - 1
            while j >= 0 and merged[j] == "":
                j -= 1
            if (
                j >= 0
                and merged[j]
                and not _is_structural(merged[j])
                and _UNTERMINATED_RE.search(merged[j])
                and line[0].islower()
            ):
                if merged[j].endswith("-"):
                    merged[j] = merged[j][:-1] + line
                else:
                    merged[j] = merged[j] + " " + line
                del merged[j + 1 :]
                continue
        merged.append(line)

    text = "\n".join(merged)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


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
