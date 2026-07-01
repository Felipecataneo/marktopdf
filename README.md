# 📝 Conversor de Markdown para PDF

Aplicativo web em [Streamlit](https://streamlit.io/) que converte Markdown em
PDFs formatados. Você pode colar o texto diretamente (com pré-visualização ao
vivo) ou enviar arquivos `.md`, `.txt` e `.docx` — inclusive vários de uma vez,
baixando tudo em um `.zip`.

## ✨ Recursos

- **Duas formas de entrada**: colar Markdown ou enviar arquivos (`.md`, `.txt`, `.docx`).
- **Pré-visualização ao vivo** ao colar o texto.
- **Conversão em lote** com download em ZIP.
- **Temas de PDF**: Clássico, Moderno e Acadêmico.
- **Tamanho de página** (A4, Letter, Legal), **margem** e **numeração de páginas** configuráveis.
- **Destaque de sintaxe** em blocos de código, com estilo selecionável (tango, pygments, kate, zenburn, breezedark, etc.) e cores aplicadas de fato no PDF.
- **Fórmulas matemáticas** em LaTeX (`$...$` e `$$...$$`) via MathJax.
- Download nativo do Streamlit (sem hacks de HTML/base64).

## 🚀 Como executar localmente

Pré-requisitos de sistema (Debian/Ubuntu) — os mesmos listados em `packages.txt`:

```bash
sudo apt-get install -y pandoc libcairo2-dev pango1.0-dev libffi-dev
```

Instale as dependências Python e rode:

```bash
pip install -r requirements.txt
streamlit run main.py
```

O app abre em `http://localhost:8501`.

## ☁️ Deploy no Streamlit Community Cloud

O repositório já está pronto para deploy:

- `requirements.txt` — dependências Python (com versões fixadas).
- `packages.txt` — pacotes de sistema (`apt`) necessários para pandoc/WeasyPrint.

Basta apontar o Streamlit Cloud para este repositório e para o arquivo `main.py`.

## 🗂️ Estrutura

| Arquivo | Descrição |
|---|---|
| `main.py` | Interface Streamlit (UI). |
| `converter.py` | Lógica de conversão Markdown → HTML → PDF (independente da UI). |
| `requirements.txt` | Dependências Python. |
| `packages.txt` | Dependências de sistema para o deploy. |

## 🔧 Como funciona

1. O texto é extraído do arquivo (mammoth para `.docx`, leitura direta para texto).
2. O Markdown é convertido para HTML5 com [pandoc](https://pandoc.org/) via `pypandoc`.
3. O HTML é estilizado conforme o tema/opções escolhidos.
4. [WeasyPrint](https://weasyprint.org/) renderiza o HTML em PDF.
