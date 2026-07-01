from __future__ import annotations

import io
import zipfile

import streamlit as st

from converter import (
    PAGE_SIZES,
    THEME_NAMES,
    PdfOptions,
    extract_markdown,
    markdown_to_pdf,
)

st.set_page_config(
    page_title="Conversor de Markdown para PDF",
    page_icon="📄",
    layout="wide",
)

st.title("📝 Conversor de Markdown para PDF")
st.write(
    "Cole o seu Markdown ou carregue arquivos `.md`, `.txt` ou `.docx` "
    "e converta para um PDF formatado."
)

# ---------------------------------------------------------------------------
# Barra lateral: opções de saída do PDF
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Opções do PDF")
    theme = st.selectbox("Tema", THEME_NAMES, index=0)
    page_size = st.selectbox("Tamanho da página", PAGE_SIZES, index=0)
    margin = st.select_slider(
        "Margem", options=["1cm", "1.5cm", "2cm", "2.5cm", "3cm"], value="2cm"
    )
    show_page_numbers = st.checkbox("Numerar páginas", value=True)

options = PdfOptions(
    theme=theme,
    page_size=page_size,
    margin=margin,
    show_page_numbers=show_page_numbers,
)


def _safe_convert(text: str) -> bytes | None:
    """Converte tratando erros e reportando na UI."""
    if not text or not text.strip():
        st.warning("Não há conteúdo para converter.")
        return None
    try:
        return markdown_to_pdf(text, options)
    except Exception as exc:  # noqa: BLE001 - queremos mostrar qualquer erro ao usuário
        st.error(f"Erro na conversão para PDF: {exc}")
        return None


tab_texto, tab_arquivos = st.tabs(["✍️ Colar texto", "📁 Enviar arquivos"])

# ---------------------------------------------------------------------------
# Aba 1: colar Markdown direto, com preview ao vivo
# ---------------------------------------------------------------------------
with tab_texto:
    col_edit, col_preview = st.columns(2)
    with col_edit:
        st.subheader("Editor")
        markdown_text = st.text_area(
            "Markdown",
            height=420,
            placeholder="# Título\n\nEscreva **Markdown** aqui...",
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
# Aba 2: upload de um ou vários arquivos (ZIP quando há mais de um)
# ---------------------------------------------------------------------------
with tab_arquivos:
    uploaded_files = st.file_uploader(
        "Escolha um ou mais arquivos",
        type=["docx", "txt", "md"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        results: list[tuple[str, bytes]] = []
        for uploaded in uploaded_files:
            with st.expander(f"📄 {uploaded.name}", expanded=len(uploaded_files) == 1):
                try:
                    text = extract_markdown(uploaded.name, uploaded.getvalue())
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Erro ao ler '{uploaded.name}': {exc}")
                    continue

                edited = st.text_area(
                    "Editar Markdown antes de converter",
                    value=text,
                    height=260,
                    key=f"edit_{uploaded.name}",
                )
                pdf_data = _safe_convert(edited) if st.button(
                    "Converter", key=f"conv_{uploaded.name}"
                ) else None

                if pdf_data:
                    pdf_name = uploaded.name.rsplit(".", 1)[0] + ".pdf"
                    results.append((pdf_name, pdf_data))
                    st.download_button(
                        "📥 Baixar PDF",
                        data=pdf_data,
                        file_name=pdf_name,
                        mime="application/pdf",
                        key=f"dl_{uploaded.name}",
                    )

        # Converter todos de uma vez e empacotar em ZIP.
        if len(uploaded_files) > 1 and st.button(
            "Converter todos e baixar ZIP", type="primary"
        ):
            zip_buffer = io.BytesIO()
            converted = 0
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for uploaded in uploaded_files:
                    try:
                        text = extract_markdown(uploaded.name, uploaded.getvalue())
                        pdf_data = markdown_to_pdf(text, options)
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Falha em '{uploaded.name}': {exc}")
                        continue
                    zf.writestr(uploaded.name.rsplit(".", 1)[0] + ".pdf", pdf_data)
                    converted += 1

            if converted:
                st.success(f"{converted} arquivo(s) convertido(s).")
                st.download_button(
                    "📥 Baixar ZIP",
                    data=zip_buffer.getvalue(),
                    file_name="pdfs_convertidos.zip",
                    mime="application/zip",
                )

# ---------------------------------------------------------------------------
# Ajuda
# ---------------------------------------------------------------------------
with st.expander("ℹ️ Sobre este aplicativo"):
    st.markdown(
        """
        ### Como usar
        1. **Colar texto**: escreva ou cole Markdown e veja a pré-visualização ao vivo.
        2. **Enviar arquivos**: carregue `.md`, `.txt` ou `.docx` (um ou vários).
        3. Ajuste **tema**, **tamanho de página** e **margem** na barra lateral.
        4. Clique em **Converter para PDF** e baixe o resultado.

        ### Recursos suportados
        - Tabelas, listas, citações e blocos de código com destaque de sintaxe
        - Fórmulas matemáticas em LaTeX (`$...$` e `$$...$$`)
        - Numeração de páginas e escolha de tamanho (A4, Letter, Legal)
        """
    )
