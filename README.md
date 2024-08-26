# AI CTRL: Cognitive Tech Resource Learning

Welcome to the AI CTRL repository! This project provides tools for automated text analysis and document processing using Python, along with configurable prompts for various applications.

## Overview

This repository contains two main tools:

1. **`analyse_cmd.py`:** A Python-based tool for extracting, translating, and summarizing text from various document formats (PDF, PowerPoint, HTML, etc.).
2. **`aictrl2.py`:** A Python-based tool that processes the extracted texts, analyzes them, and generates new content such as reports, summaries, or recommendations.

These tools are designed to automate the manual processes involved in document analysis and content generation, saving time and increasing accuracy.

## Features

- **Text Extraction:** Extracts content from PDF, PowerPoint, and HTML documents.
- **Text Translation and Explanation:** Automatically translates and explains extracted text.
- **Report Generation:** Creates structured reports or Markdown files based on the extracted content.
- **Flexible Prompt Use:** Utilizes customizable prompts with placeholders to adapt to various use cases.
- **Legal Document Analysis:** Includes specialized prompts for generating legal opinion letters and analyzing contracts.

## Installation

To use the tools provided in this repository, follow these steps:

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/dirnberg/aictrl.git
   ```
2. **Navigate to the Project Directory:**
   ```bash
   cd aictrl
   ```
3. **Install Dependencies:**
   Make sure you have Python installed. Then, install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```
4. **Set Up OpenAI API Key:**
   Obtain an API key from OpenAI and set it up in your environment:
   ```bash
   export OPENAI_API_KEY='your-api-key'
   ```

## Usage

### `analyse_cmd.py`

This tool extracts, translates, and summarizes text from documents. You can run it as follows:

```bash
python analyse_cmd.py --input yourfile.pdf --output result.md --translate True
```

### `aictrl2.py`

This tool processes the extracted text, analyzing it and generating new content:

```bash
python aictrl2.py --config config.yml
```

Ensure that the `config.yml` file is correctly configured for your specific use case.

## Configuration

The tools use a `config.yml` file to define various parameters, including the AI model to use, prompts, and other settings. Here’s an example configuration:

```yaml
assistant:
  name: "LegalDocumentAnalyzer"
  model: "gpt-4"
  instructions_file_path: "prompts/instructions.md"
  tools:
    - "file_search"
    - "code_interpreter"
  temperature: 0.7
  top_p: 0.9
  frequency_penalty: 0.0
  presence_penalty: 0.0
```

## Prompts

This repository includes several prompts that are used by the tools to generate text outputs. The prompts are stored in the `prompts` directory and can be customized as needed.

- **`instructions.md`:** Provides general instructions for the AI assistant.
- **`legal.md`:** Specialized prompt for drafting legal opinion letters.
- **`convert_to_markdown.md`:** Prompt for converting text to Markdown format.

## Examples

### Legal Document Analysis

Use `aictrl2.py` to analyze a legal contract and generate a formal opinion letter:

```bash
python aictrl2.py --config config.yml
```

### Text Summarization

Extract and summarize text from a PDF file using `analyse_cmd.py`:

```bash
python analyse_cmd.py --input contract.pdf --output summary.md --translate False
```

## Contribution

Contributions are welcome! If you have suggestions, feature requests, or want to contribute code, please create an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact

For more information, please visit the [GitHub repository](https://github.com/dirnberg/aictrl) or contact the repository owner.

---

This `README.md` provides a comprehensive overview of your project, guiding users on how to install, configure, and use the tools, as well as where to find further information or contribute to the project..
