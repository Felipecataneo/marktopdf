import streamlit as st
import pypandoc
import tempfile
import os
import mammoth
import re
from weasyprint import HTML
import base64

st.set_page_config(
    page_title="Conversor de Markdown para PDF",
    page_icon="📄",
    layout="centered"
)

st.title("📝 Conversor de Markdown para PDF")
st.write("Carregue um documento Word (.docx) ou texto (.txt) contendo Markdown e converta-o para PDF formatado.")

uploaded_file = st.file_uploader("Escolha um arquivo", type=['docx', 'txt'])

def extract_text_from_docx(docx_file):
    """Extrai o texto de um arquivo DOCX."""
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as temp_file:
        temp_file.write(docx_file.getvalue())
        temp_file_path = temp_file.name
   
    try:
        result = mammoth.extract_raw_text(temp_file_path)
        text = result.value
        os.unlink(temp_file_path)
        return text
    except Exception as e:
        st.error(f"Erro ao extrair texto do arquivo DOCX: {e}")
        os.unlink(temp_file_path)
        return None

def read_text_file(txt_file):
    """Lê o conteúdo de um arquivo TXT."""
    return txt_file.getvalue().decode('utf-8')

def markdown_to_pdf(markdown_text):
    """Converte texto Markdown para PDF."""
    try:
        # Cria um arquivo HTML temporário
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8') as html_file:
            # Converte Markdown para HTML usando pypandoc
            html_content = pypandoc.convert_text(markdown_text, 'html', format='md')
           
            # Adiciona estilos CSS para melhorar a aparência
            styled_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        margin: 2em;
                        color: #333;
                    }}
                    h1, h2, h3, h4, h5, h6 {{
                        color: #2c3e50;
                        margin-top: 1.5em;
                        margin-bottom: 0.5em;
                    }}
                    h1 {{ font-size: 2.2em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }}
                    h2 {{ font-size: 1.8em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }}
                    h3 {{ font-size: 1.5em; }}
                    h4 {{ font-size: 1.3em; }}
                    p {{ margin-bottom: 1em; }}
                    code {{
                        background-color: #f7f7f7;
                        padding: 2px 4px;
                        border-radius: 3px;
                        font-family: monospace;
                    }}
                    pre {{
                        background-color: #f7f7f7;
                        padding: 16px;
                        border-radius: 3px;
                        overflow: auto;
                        line-height: 1.45;
                    }}
                    blockquote {{
                        border-left: 4px solid #ddd;
                        padding-left: 1em;
                        color: #666;
                        margin-left: 0;
                    }}
                    table {{
                        border-collapse: collapse;
                        width: 100%;
                        margin-bottom: 1em;
                    }}
                    th, td {{
                        border: 1px solid #ddd;
                        padding: 8px;
                        text-align: left;
                    }}
                    th {{
                        background-color: #f2f2f2;
                    }}
                    img {{
                        max-width: 100%;
                        height: auto;
                    }}
                    a {{
                        color: #3498db;
                        text-decoration: none;
                    }}
                    a:hover {{
                        text-decoration: underline;
                    }}
                    ul, ol {{
                        margin-bottom: 1em;
                    }}
                </style>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """
            html_file.write(styled_html)
            html_file_path = html_file.name
       
        # Gera o PDF a partir do HTML
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as pdf_file:
            pdf_file_path = pdf_file.name
       
        HTML(html_file_path).write_pdf(pdf_file_path)
       
        # Limpa o arquivo HTML temporário
        os.unlink(html_file_path)
       
        # Lê o PDF gerado
        with open(pdf_file_path, 'rb') as file:
            pdf_data = file.read()
       
        # Limpa o arquivo PDF temporário
        os.unlink(pdf_file_path)
       
        return pdf_data
   
    except Exception as e:
        st.error(f"Erro na conversão para PDF: {e}")
        return None

if uploaded_file is not None:
    st.info("Arquivo carregado. Processando...")
   
    # Extrai o texto dependendo do tipo de arquivo
    if uploaded_file.name.endswith('.docx'):
        markdown_text = extract_text_from_docx(uploaded_file)
    else:  # .txt
        markdown_text = read_text_file(uploaded_file)
   
    if markdown_text:
        # Exibe o texto Markdown extraído
        with st.expander("Visualizar Texto Markdown"):
            st.text_area("Conteúdo do arquivo", markdown_text, height=300)
       
        # Permite editar o texto Markdown antes da conversão
        edited_markdown = st.text_area("Editar Markdown (opcional)", markdown_text, height=300)
       
        # Botão para converter para PDF
        if st.button("Converter para PDF"):
            pdf_data = markdown_to_pdf(edited_markdown)
           
            if pdf_data:
                # Codifica o PDF em base64 para download
                b64_pdf = base64.b64encode(pdf_data).decode()
               
                # Cria um link de download
                pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="500" type="application/pdf"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)
               
                # Botão de download
                href = f'<a href="data:application/pdf;base64,{b64_pdf}" download="documento_convertido.pdf">📥 Baixar PDF</a>'
                st.markdown(href, unsafe_allow_html=True)
               
                st.success("Conversão concluída com sucesso!")

# Instruções e informações adicionais
with st.expander("ℹ️ Sobre este aplicativo"):
    st.markdown("""
    ### Como usar
    1. Carregue um arquivo Word (.docx) ou texto (.txt) que contenha texto formatado em Markdown
    2. Visualize e edite o texto Markdown se necessário
    3. Clique em 'Converter para PDF' para gerar o documento formatado
    4. Visualize o PDF gerado no navegador
    5. Baixe o PDF resultante).
    """)
