# Python App for Talking To Machines

Simple Python app to run experiments with the [talkingtomachines](https://github.com/talking-to-machines/talking-to-machines) framework.

## 🚀 Installation

### 1. Install Poetry (if not already installed)

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Or follow the [official Poetry installation guide](https://python-poetry.org/docs/#installation).

### 2. Install dependencies

This project uses Poetry for dependency management. Install all dependencies with:

```bash
poetry install
```

This will install:
- `talkingtomachines` (from test.pypi.org)
- `python-dotenv`
- `openpyxl`
- `streamlit` (per l'interfaccia web)
- `pandas` (per la gestione dati)
- `psutil` (per il monitoraggio sistema)
- `openai` (per i test API)

**Alternative: Using pip (not recommended)**

If you prefer using pip directly:

```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple talkingtomachines
pip install python-dotenv openpyxl psutil streamlit pandas openai
```

### 2. Configure API Keys

**Recommended method: .env file**

Create a `.env` file in the project directory by copying the template:

```bash
cp .env.example .env
```

Then edit the `.env` file with your API keys:

```bash
OPENAI_API_KEY=sk-your-actual-key-here
HF_API_KEY=hf_your-actual-key-here
OPENROUTER_API_KEY=sk-or-your-actual-key-here
```

**Alternative method: Environment variables**

**macOS/Linux:**
```bash
export OPENAI_API_KEY=sk-...
export HF_API_KEY=hf_...
export OPENROUTER_API_KEY=sk-...
```

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY='sk-...'
$env:HF_API_KEY='hf_...'
$env:OPENROUTER_API_KEY='sk-...'
```

## 📖 Usage

### 🖥️ Streamlit Web Interface (Recommended)

L'app Streamlit fornisce un'interfaccia completa per gestire gli esperimenti con monitoraggio live.

**Avvia l'app:**

```bash
# Con Poetry
poetry run streamlit run app.py

# O direttamente
streamlit run app.py
```

L'app si aprirà nel browser all'indirizzo `http://localhost:8501`

**Funzionalità dell'interfaccia:**

- **📊 Dashboard**: Panoramica generale con statistiche e cronologia esperimenti
- **📁 Templates**: Gestione template (upload, preview, eliminazione)
  - Upload nuovi template Excel nella cartella `experiments_templates`
  - Preview dei fogli Excel
  - Eliminazione template
- **🚀 Run Experiment**: Esecuzione esperimenti con monitoraggio live
  - Selezione template e modalità (test/full)
  - Monitoraggio in tempo reale: CPU, memoria, tempo trascorso, file generati
  - Output live durante l'esecuzione
- **📈 Results**: Visualizzazione e gestione risultati
  - Lista file JSON e CSV generati
  - Visualizzazione contenuti
  - Download risultati
  - Statistiche per file CSV

### 💻 Command Line Interface

**Using Poetry (recommended):**

```bash
poetry run python run_experiment.py <excel_template_file>
```

**Or activate the Poetry shell first:**

```bash
poetry shell
python run_experiment.py <excel_template_file>
```

**Or using Python directly (if dependencies are installed in your environment):**

```bash
python run_experiment.py <excel_template_file>
```

### Examples

```bash
# Test mode (default - runs one randomly selected group per treatment)
poetry run python run_experiment.py template.xlsx

# Explicit test mode
poetry run python run_experiment.py template.xlsx test

# Full mode (runs all groups)
poetry run python run_experiment.py template.xlsx full

# With verbose output
poetry run python run_experiment.py template.xlsx full --verbose
```

## 📋 Execution modes

- **test**: Runs the experiment in TEST mode (one randomly selected group per treatment)
- **full**: Runs the complete experiment with all groups

## 📁 Results

Results are saved in the `experiment_results` folder in the current directory:
- `<session_id>.json`: Raw output in JSON format
- `<session_id>.csv`: Formatted output in CSV format

## 📝 Notes

- Make sure the Excel template file is in the correct format required by talkingtomachines
- For more details on the template format, see the [official documentation](https://github.com/talking-to-machines/talking-to-machines)
- The `talkingtomachines` command must be available in your PATH

## 🔗 Useful links

- [GitHub Repository](https://github.com/talking-to-machines/talking-to-machines)
- [Prompt Template Documentation](https://talking-to-machines.github.io/talking-to-machines/)

