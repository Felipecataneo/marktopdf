from __future__ import annotations

import io
import zipfile

import streamlit as st

from converter import (
    HIGHLIGHT_STYLES,
    PAGE_SIZES,
    PDF_ENGINES,
    THEME_NAMES,
    PdfExtractOptions,
    PdfOptions,
    extract_markdown,
    markdown_to_pdf,
)

st.set_page_config(
    page_title="Conversor de Documentos e PDFs",
    page_icon="📄",
    layout="wide",
)

st.title("📝 Conversor Inteligente de Documentos para Markdown & PDF")
st.write(
    "Cole o seu Markdown ou carregue arquivos (`.pdf`, `.docx`, `.md`, `.txt`) "
    "para extrair Markdown estruturado para LLMs ou converter para PDF formatado."
)

# ---------------------------------------------------------------------------
# Barra lateral: opções de saída do PDF
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Opções de Exportação (PDF)")
    theme = st.selectbox("Tema", THEME_NAMES, index=0)
    page_size = st.selectbox("Tamanho da página", PAGE_SIZES, index=0)
    margin = st.select_slider(
        "Margem", options=["1cm", "1.5cm", "2cm", "2.5cm", "3cm"], value="2cm"
    )
    highlight_style = st.selectbox("Estilo do código", HIGHLIGHT_STYLES, index=0)
    show_page_numbers = st.checkbox("Numerar páginas", value=True)

    st.header("📑 Opções de Extração (PDF → Markdown)")
    pdf_engine = st.selectbox(
        "Motor de extração",
        PDF_ENGINES,
        index=0,
        help=(
            "O motor automático usa análise de layout por IA e é o melhor para "
            "papers de duas colunas. Se a ordem de leitura sair embaralhada, "
            "experimente o motor clássico."
        ),
    )
    strip_headers_footers = st.checkbox(
        "Remover cabeçalhos, rodapés e nº de página",
        value=True,
        help="Descarta o texto repetido no topo/rodapé de cada página do PDF.",
    )
    include_picture_text = st.checkbox(
        "Incluir texto sobreposto a figuras",
        value=False,
        help=(
            "O texto dentro de diagramas e figuras costuma sair embaralhado; "
            "mantenha desligado para um Markdown mais limpo."
        ),
    )

options = PdfOptions(
    theme=theme,
    page_size=page_size,
    margin=margin,
    show_page_numbers=show_page_numbers,
    highlight_style=highlight_style,
)

extract_options = PdfExtractOptions(
    engine=pdf_engine,
    strip_headers_footers=strip_headers_footers,
    include_picture_text=include_picture_text,
)


def _safe_convert(text: str) -> bytes | None:
    """Converte tratando erros e reportando na UI."""
    if not text or not text.strip():
        st.warning("Não há conteúdo para converter.")
        return None
    try:
        return markdown_to_pdf(text, options)
    except Exception as exc:
        st.error(f"Erro na conversão para PDF: {exc}")
        return None


tab_texto, tab_arquivos = st.tabs(["✍️ Colar texto / Editor", "📁 Processar arquivos & PDFs"])

# ---------------------------------------------------------------------------
# Aba 1: colar Markdown direto, com preview ao vivo
# ---------------------------------------------------------------------------
with tab_texto:
    col_edit, col_preview = st.columns(2)
    with col_edit:
        st.subheader("Editor Markdown")
        markdown_text = st.text_area(
            "Markdown",
            height=420,
            placeholder="# Título\n\nEscreva **Markdown** aqui ou edite o conteúdo extraído...",
            label_visibility="collapsed",
        )
    with col_preview:
        st.subheader("Pré-visualização")
        if markdown_text.strip():
            st.markdown(markdown_text)
        else:
            st.caption("A pré-visualização aparece aqui conforme você digita.")

    if st.button("Converter para PDF", type="primary", key="btn_texto"):
        pdf_data = _safe_convert(markdown_text)
        if pdf_data:
            st.success("Conversão concluída!")
            st.download_button(
                "📥 Baixar PDF",
                data=pdf_data,
                file_name="documento.pdf",
                mime="application/pdf",
                key="dl_texto",
            )

# ---------------------------------------------------------------------------
# Aba 2: upload de arquivos, incluindo PDFs (ZIP para múltiplos arquivos)
# ---------------------------------------------------------------------------
with tab_arquivos:
    uploaded_files = st.file_uploader(
        "Carregue um ou mais arquivos (PDFs, Word ou arquivos de texto)",
        type=["pdf", "docx", "txt", "md"],  # PDF adicionado aqui
        accept_multiple_files=True,
    )

    if uploaded_files:
        results: list[tuple[str, bytes]] = []
        for uploaded in uploaded_files:
            with st.expander(f"📄 {uploaded.name}", expanded=len(uploaded_files) == 1):
                try:
                    # Chamar extrator que agora processa PDFs pelo pymupdf4llm
                    text = extract_markdown(
                        uploaded.name, uploaded.getvalue(), extract_options
                    )
                except Exception as exc:
                    st.error(f"Erro ao ler '{uploaded.name}': {exc}")
                    continue

                edited = st.text_area(
                    "Markdown extraído (pode editar antes de converter ou copiar)",
                    value=text,
                    height=300,
                    key=f"edit_{uploaded.name}",
                )
                
                col_btn_conv, col_btn_down = st.columns(2)
                with col_btn_conv:
                    converter_clicado = st.button("Converter para Novo PDF", key=f"conv_{uploaded.name}")
                
                pdf_data = _safe_convert(edited) if converter_clicado else None

                if pdf_data:
                    pdf_name = uploaded.name.rsplit(".", 1)[0] + "_formatado.pdf"
                    results.append((pdf_name, pdf_data))
                    with col_btn_down:
                        st.download_button(
                            "📥 Baixar PDF Formatado",
                            data=pdf_data,
                            file_name=pdf_name,
                            mime="application/pdf",
                            key=f"dl_{uploaded.name}",
                        )

        # Processar todos de uma vez e empacotar em ZIP
        if len(uploaded_files) > 1 and st.button(
            "Converter todos os arquivos enviados para PDF (ZIP)", type="primary"
        ):
            zip_buffer = io.BytesIO()
            converted = 0
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for uploaded in uploaded_files:
                    try:
                        text = extract_markdown(
                            uploaded.name, uploaded.getvalue(), extract_options
                        )
                        pdf_data = markdown_to_pdf(text, options)
                    except Exception as exc:
                        st.error(f"Falha em '{uploaded.name}': {exc}")
                        continue
                    zf.writestr(uploaded.name.rsplit(".", 1)[0] + "_formatado.pdf", pdf_data)
                    converted += 1

            if converted:
                st.success(f"{converted} arquivo(s) processado(s).")
                st.download_button(
                    "📥 Baixar ZIP com PDFs",
                    data=zip_buffer.getvalue(),
                    file_name="documentos_formatados.zip",
                    mime="application/zip",
                )

# ---------------------------------------------------------------------------
# Ajuda
# ---------------------------------------------------------------------------
with st.expander("ℹ️ Sobre este aplicativo"):
    st.markdown(
        """
        ### Funcionalidades
        1. **Conversor de PDF para LLM-Ready Markdown**: Envie arquivos `.pdf` de artigos ou relatórios de duas colunas para extrair texto estruturado com tabelas nativas de forma otimizada para IAs.
        2. **Processamento em Memória**: Toda a extração ocorre diretamente na memória RAM, sem salvar arquivos no servidor, tornando o processo mais seguro e rápido.
        3. **Editor em Tempo Real**: Altere o Markdown gerado e decida se quer copiar para o LLM ou converter em um novo PDF elegante e diagramado.
        
        ### Recursos suportados
        - Reconstrução da ordem de leitura em papers de duas colunas (motor de layout por IA).
        - Remoção automática de cabeçalhos, rodapés e números de página repetidos.
        - Religação de parágrafos quebrados entre colunas e páginas.
        - Extração inteligente de tabelas de PDFs estruturados.
        - Detecção de equações matemáticas no formato LaTeX (`$...$` e `$$...$$`).
        - Formatação de títulos, listas e códigos em blocos de programação.
        """
    )
