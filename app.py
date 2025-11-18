#!/usr/bin/env python3
"""
Streamlit app per gestire esperimenti talkingtomachines.
Interfaccia completa con gestione template, esecuzione esperimenti e monitoraggio live.
"""

import streamlit as st
import os
import sys
import platform
import subprocess
import threading
import time
import json
import pandas as pd
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

# Importa secrets_helper per caricare .env in locale (load_dotenv viene chiamato nel modulo)
# e rendere disponibile get_secret() per eventuali utilizzi futuri
from secrets_helper import get_secret

# Configurazione pagina
st.set_page_config(
    page_title="TTM Experiments Manager",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Aggiungi Material Icons e stili personalizzati per la sidebar
st.markdown("""
<link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
<style>
.material-icons { 
    font-family: 'Material Icons'; 
    font-weight: normal; 
    font-style: normal; 
    font-size: 20px; 
    display: inline-block; 
    vertical-align: middle;
    margin-right: 8px;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #2c3e50 0%, #34495e 100%);
}
[data-testid="stSidebar"] * {
    color: #ffffff !important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1 {
    color: #ffffff !important;
    font-weight: 700;
    margin-bottom: 1rem;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2 {
    color: #ecf0f1 !important;
    font-weight: 600;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 1.5rem;
    margin-bottom: 0.75rem;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}
[data-testid="stSidebar"] .stRadio > div {
    gap: 0.5rem;
}
[data-testid="stSidebar"] .stRadio > div > label {
    color: #ffffff !important;
    padding: 0.75rem 1rem;
    border-radius: 8px;
    transition: all 0.2s ease;
    cursor: pointer;
    margin-bottom: 0.5rem;
    font-weight: 500;
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
}
[data-testid="stSidebar"] .stRadio > div > label:hover {
    background-color: rgba(255, 255, 255, 0.15) !important;
    border-color: rgba(255, 255, 255, 0.3);
    transform: translateX(2px);
}
[data-testid="stSidebar"] .stRadio > div > label[data-baseweb="radio"] {
    background-color: rgba(255, 255, 255, 0.1);
}
[data-testid="stSidebar"] .stRadio input[type="radio"]:checked + label {
    background-color: rgba(52, 152, 219, 0.3) !important;
    border-color: rgba(52, 152, 219, 0.6);
    font-weight: 600;
    color: #ffffff !important;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}
[data-testid="stSidebar"] hr {
    border-color: rgba(255, 255, 255, 0.3) !important;
    margin: 1.5rem 0;
    border-width: 1px;
}
[data-testid="stSidebar"] .stRadio > div > label::before {
    color: #ffffff !important;
    opacity: 0.9;
    font-size: 20px;
    vertical-align: middle;
}
[data-testid="stSidebar"] .stRadio > div > label:nth-of-type(1)::before {
    content: "dashboard";
    font-family: 'Material Icons';
    margin-right: 8px;
    display: inline-block;
}
[data-testid="stSidebar"] .stRadio > div > label:nth-of-type(2)::before {
    content: "folder";
    font-family: 'Material Icons';
    margin-right: 8px;
    display: inline-block;
}
[data-testid="stSidebar"] .stRadio > div > label:nth-of-type(3)::before {
    content: "play_arrow";
    font-family: 'Material Icons';
    margin-right: 8px;
    display: inline-block;
}
[data-testid="stSidebar"] .stRadio > div > label:nth-of-type(4)::before {
    content: "bar_chart";
    font-family: 'Material Icons';
    margin-right: 8px;
    display: inline-block;
}
[data-testid="stSidebar"] .stRadio > div > label:nth-of-type(5)::before {
    content: "settings";
    font-family: 'Material Icons';
    margin-right: 8px;
    display: inline-block;
}
[data-testid="stSidebar"] .stRadio input[type="radio"]:checked + label::before {
    opacity: 1;
    color: #3498db !important;
}
</style>
""", unsafe_allow_html=True)

def icon(name: str) -> str:
    """Restituisce un'icona Material Icons."""
    return f'<span class="material-icons">{name}</span>'

# Costanti
TEMPLATES_DIR = Path("experiments_templates")
RESULTS_DIR = Path("experiment_results")
EXPERIMENTS_STATE_FILE = Path(".experiments_state.json")
TEMPLATES_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

# Thread-safe storage per esperimenti in esecuzione
_experiments_lock = threading.Lock()
_experiments_state: Dict[str, Dict] = {}

def load_experiments_state() -> Dict[str, Dict]:
    """Carica lo stato degli esperimenti da file."""
    global _experiments_state
    if EXPERIMENTS_STATE_FILE.exists():
        try:
            with open(EXPERIMENTS_STATE_FILE, 'r') as f:
                _experiments_state = json.load(f)
        except Exception:
            _experiments_state = {}
    return _experiments_state

def save_experiments_state(state: Dict[str, Dict]):
    """Salva lo stato degli esperimenti su file."""
    try:
        with open(EXPERIMENTS_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2, default=str)
    except Exception:
        pass

def update_experiment_state(experiment_id: str, data: Dict):
    """Aggiorna lo stato di un esperimento in modo thread-safe."""
    global _experiments_state
    with _experiments_lock:
        _experiments_state[experiment_id] = data
        save_experiments_state(_experiments_state)

def get_experiment_state(experiment_id: str) -> Optional[Dict]:
    """Ottiene lo stato di un esperimento."""
    with _experiments_lock:
        return _experiments_state.get(experiment_id)

def get_all_experiments_state() -> Dict[str, Dict]:
    """Ottiene tutti gli stati degli esperimenti."""
    with _experiments_lock:
        return _experiments_state.copy()

def stop_experiment(experiment_id: str) -> bool:
    """Ferma un esperimento in esecuzione."""
    import psutil
    
    with _experiments_lock:
        exp_data = _experiments_state.get(experiment_id)
        if not exp_data:
            return False
        
        if exp_data.get('status') != 'running':
            return False
        
        # Ottieni il PID del processo
        process_pid = exp_data.get('process_pid')
        processes_to_kill = []
        
        # Se abbiamo il PID, prova a usarlo
        if process_pid:
            try:
                main_proc = psutil.Process(process_pid)
                processes_to_kill.append(main_proc)
                
                # Cerca anche i processi figli
                try:
                    children = main_proc.children(recursive=True)
                    processes_to_kill.extend(children)
                except Exception:
                    pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Il processo principale potrebbe essere già terminato
                pass
        
        # Se non abbiamo trovato processi, cerca per nome
        if not processes_to_kill:
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        cmdline = proc.info.get('cmdline', [])
                        if cmdline and 'talkingtomachines' in ' '.join(cmdline):
                            # Verifica che sia un processo correlato all'esperimento
                            # Controlla se il template path è nel comando
                            template_path = exp_data.get('template', '')
                            if template_path and any(template_path in str(arg) for arg in cmdline):
                                processes_to_kill.append(psutil.Process(proc.info['pid']))
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except Exception:
                pass
        
        # Se ancora non abbiamo trovato processi, cerca tutti i processi talkingtomachines
        if not processes_to_kill:
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        cmdline = proc.info.get('cmdline', [])
                        if cmdline and 'talkingtomachines' in ' '.join(cmdline):
                            processes_to_kill.append(psutil.Process(proc.info['pid']))
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except Exception:
                pass
        
        if not processes_to_kill:
            # Nessun processo trovato, aggiorna comunque lo stato
            update_experiment_state(experiment_id, {
                **exp_data,
                'status': 'stopped',
                'elapsed': time.time() - exp_data.get('start_time', time.time()),
                'error': 'No process found to stop'
            })
            return False
        
        # Termina tutti i processi trovati
        success = False
        errors = []
        
        for proc in processes_to_kill:
            try:
                proc.terminate()  # Invia SIGTERM
                success = True
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                errors.append(str(e))
                continue
        
        # Aspetta che i processi terminino
        if success:
            time.sleep(2)
            # Forza la terminazione se necessario
            for proc in processes_to_kill:
                try:
                    if proc.is_running():
                        proc.kill()  # Forza la terminazione con SIGKILL
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        
        # Aggiorna lo stato
        update_experiment_state(experiment_id, {
            **exp_data,
            'status': 'stopped',
            'elapsed': time.time() - exp_data.get('start_time', time.time()),
            'process_pid': None,
            'error': '; '.join(errors) if errors else None
        })
        
        return success

# Carica stato iniziale
load_experiments_state()

# Ricarica stato all'inizio di ogni run (per persistenza tra refresh)
_experiments_state = load_experiments_state()

# Inizializzazione session state
if 'experiment_history' not in st.session_state:
    st.session_state.experiment_history = []
if 'selected_template' not in st.session_state:
    st.session_state.selected_template = None
if 'selected_page' not in st.session_state:
    st.session_state.selected_page = "Dashboard"




def get_process_info(pid: int) -> Optional[Dict]:
    """Ottiene informazioni dettagliate sul processo."""
    try:
        import psutil
        proc = psutil.Process(pid)
        return {
            'cpu_percent': proc.cpu_percent(interval=0.1),
            'memory_mb': proc.memory_info().rss / 1024 / 1024,
            'num_threads': proc.num_threads(),
            'num_connections': len(proc.connections()),
            'status': proc.status()
        }
    except Exception:
        return None


def get_template_files() -> List[Path]:
    """Ottiene la lista dei template disponibili."""
    templates = []
    if TEMPLATES_DIR.exists():
        templates = list(TEMPLATES_DIR.glob("*.xlsx")) + list(TEMPLATES_DIR.glob("*.xls"))
    return sorted(templates)


def get_result_files() -> List[Path]:
    """Ottiene la lista dei file di risultati, cercando anche nelle sottocartelle."""
    results = []
    if RESULTS_DIR.exists():
        # Cerca file nella root (per retrocompatibilità)
        results.extend(list(RESULTS_DIR.glob("*.json")) + list(RESULTS_DIR.glob("*.csv")))
        # Cerca file nelle sottocartelle
        for subdir in RESULTS_DIR.iterdir():
            if subdir.is_dir():
                results.extend(list(subdir.glob("*.json")) + list(subdir.glob("*.csv")))
    return sorted(results, key=lambda x: x.stat().st_mtime, reverse=True)

def organize_results_by_experiment() -> Dict[str, Dict[str, Path]]:
    """Organizza i risultati per esperimento, raggruppando CSV e JSON per cartella."""
    experiments = {}
    
    if not RESULTS_DIR.exists():
        return experiments
    
    # Cerca nelle sottocartelle (nuova struttura)
    for subdir in RESULTS_DIR.iterdir():
        if subdir.is_dir():
            csv_files = list(subdir.glob("*.csv"))
            json_files = list(subdir.glob("*.json"))
            
            if csv_files or json_files:
                # Usa il nome della cartella come chiave esperimento
                exp_name = subdir.name
                
                # Trova il timestamp più recente tra i file
                all_files = csv_files + json_files
                max_timestamp = max(f.stat().st_mtime for f in all_files) if all_files else subdir.stat().st_mtime
                
                experiments[exp_name] = {
                    'csv': csv_files[0] if csv_files else None,
                    'json': json_files[0] if json_files else None,
                    'timestamp': max_timestamp,
                    'folder': subdir,
                    'all_csv': csv_files,
                    'all_json': json_files
                }
    
    # Per retrocompatibilità: cerca anche file nella root
    root_csv = list(RESULTS_DIR.glob("*.csv"))
    root_json = list(RESULTS_DIR.glob("*.json"))
    
    for csv_file in root_csv:
        base_name = csv_file.stem
        if base_name not in experiments:
            experiments[base_name] = {
                'csv': csv_file,
                'json': None,
                'timestamp': csv_file.stat().st_mtime,
                'folder': None,
                'all_csv': [csv_file],
                'all_json': []
            }
        else:
            # Se esiste già, aggiungi alla lista
            if csv_file not in experiments[base_name]['all_csv']:
                experiments[base_name]['all_csv'].append(csv_file)
    
    for json_file in root_json:
        base_name = json_file.stem
        if base_name not in experiments:
            experiments[base_name] = {
                'csv': None,
                'json': json_file,
                'timestamp': json_file.stat().st_mtime,
                'folder': None,
                'all_csv': [],
                'all_json': [json_file]
            }
        else:
            # Se esiste già, aggiungi alla lista
            if json_file not in experiments[base_name]['all_json']:
                experiments[base_name]['all_json'].append(json_file)
            # Aggiorna il file principale se non c'è
            if experiments[base_name]['json'] is None:
                experiments[base_name]['json'] = json_file
    
    # Ordina per timestamp (più recenti prima)
    return dict(sorted(experiments.items(), key=lambda x: x[1]['timestamp'], reverse=True))


def run_experiment_async(template_path: str, mode: str, experiment_id: str):
    """Esegue un esperimento in modo asincrono."""
    start_time = time.time()
    process = None
    
    # Crea una cartella per i risultati di questo esperimento
    # Nome formato: nome_template_timestamp
    template_name = Path(template_path).stem
    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    experiment_folder_name = f"{template_name}_{timestamp_str}"
    experiment_folder = RESULTS_DIR / experiment_folder_name
    experiment_folder.mkdir(exist_ok=True)
    
    # Traccia i file esistenti prima dell'esecuzione per spostare solo quelli nuovi
    existing_files_before = set()
    if RESULTS_DIR.exists():
        existing_files_before = {
            f.name for f in RESULTS_DIR.iterdir() 
            if f.is_file() and f.suffix in ['.csv', '.json']
        }
    
    try:
        process = subprocess.Popen(
            ['talkingtomachines', template_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        process.stdin.write(f"{mode}\n")
        process.stdin.flush()
        process.stdin.close()
        
        # Salva il PID, il template path e la cartella risultati nello stato
        update_experiment_state(experiment_id, {
            'status': 'running',
            'start_time': start_time,
            'elapsed': 0,
            'process_pid': process.pid,
            'template': template_path,
            'result_folder': str(experiment_folder),
            'process_info': None,
            'result_files_count': 0,
            'stdout': '',
            'stderr': '',
            'return_code': None
        })
        
        stdout_lines = []
        stderr_lines = []
        
        # Leggi output in tempo reale
        def read_stdout():
            try:
                for line in iter(process.stdout.readline, ''):
                    if line:
                        stdout_lines.append(line)
            except Exception:
                pass
            finally:
                if process.stdout:
                    process.stdout.close()
        
        def read_stderr():
            try:
                for line in iter(process.stderr.readline, ''):
                    if line:
                        stderr_lines.append(line)
            except Exception:
                pass
            finally:
                if process.stderr:
                    process.stderr.close()
        
        stdout_thread = threading.Thread(target=read_stdout, daemon=True)
        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        
        # Aggiorna stato durante l'esecuzione
        while process.poll() is None:
            # Controlla se l'esperimento è stato fermato
            exp_state = get_experiment_state(experiment_id)
            if exp_state and exp_state.get('status') == 'stopped':
                # Termina il processo
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass
                break
            
            elapsed = time.time() - start_time
            proc_info = get_process_info(process.pid) if process.pid else None
            
            result_files = get_result_files()
            
            # Serializza proc_info per JSON
            proc_info_serializable = None
            if proc_info:
                proc_info_serializable = {
                    'cpu_percent': proc_info['cpu_percent'],
                    'memory_mb': proc_info['memory_mb'],
                    'num_threads': proc_info['num_threads'],
                    'num_connections': proc_info['num_connections'],
                    'status': str(proc_info['status'])
                }
            
            update_experiment_state(experiment_id, {
                'status': 'running',
                'start_time': start_time,
                'elapsed': elapsed,
                'process_pid': process.pid,
                'process_info': proc_info_serializable,
                'result_files_count': len(result_files),
                'stdout': ''.join(stdout_lines),
                'stderr': ''.join(stderr_lines),
                'return_code': None
            })
            time.sleep(1)
        
        if process:
            return_code = process.poll() if process.poll() is not None else -1
            stdout_thread.join(timeout=2)
            stderr_thread.join(timeout=2)
            
            elapsed = time.time() - start_time
            
            # Sposta i file generati nella cartella dell'esperimento
            # Sposta solo i file nuovi (non esistenti prima dell'esecuzione)
            files_moved = []
            if RESULTS_DIR.exists():
                # Cerca file CSV e JSON nella root di RESULTS_DIR
                for result_file in RESULTS_DIR.glob("*.csv"):
                    if (result_file.is_file() and 
                        result_file.parent == RESULTS_DIR and 
                        result_file.name not in existing_files_before):
                        try:
                            dest = experiment_folder / result_file.name
                            shutil.move(str(result_file), str(dest))
                            files_moved.append(dest.name)
                        except Exception as e:
                            # Se il file è già stato spostato o c'è un errore, continua
                            pass
                
                for result_file in RESULTS_DIR.glob("*.json"):
                    if (result_file.is_file() and 
                        result_file.parent == RESULTS_DIR and 
                        result_file.name not in existing_files_before):
                        try:
                            dest = experiment_folder / result_file.name
                            shutil.move(str(result_file), str(dest))
                            files_moved.append(dest.name)
                        except Exception as e:
                            # Se il file è già stato spostato o c'è un errore, continua
                            pass
            
            final_status = 'stopped' if exp_state and exp_state.get('status') == 'stopped' else ('completed' if return_code == 0 else 'failed')
            
            # Conta i file nella cartella dell'esperimento
            result_files_in_folder = list(experiment_folder.glob("*.csv")) + list(experiment_folder.glob("*.json"))
            
            update_experiment_state(experiment_id, {
                'status': final_status,
                'start_time': start_time,
                'elapsed': elapsed,
                'process_info': None,
                'process_pid': None,
                'result_folder': str(experiment_folder),
                'result_files_count': len(result_files_in_folder),
                'files_moved': files_moved,
                'stdout': ''.join(stdout_lines),
                'stderr': ''.join(stderr_lines),
                'return_code': return_code
            })
        
    except Exception as e:
        update_experiment_state(experiment_id, {
            'status': 'error',
            'error': str(e),
            'start_time': start_time,
            'elapsed': time.time() - start_time,
            'process_pid': None,
            'result_folder': str(experiment_folder) if 'experiment_folder' in locals() else None
        })


def format_time(seconds: float) -> str:
    """Formatta il tempo in formato leggibile."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


# Sidebar
with st.sidebar:
    st.markdown("""
    <div style="padding: 1rem 0;">
        <h1 style="margin: 0; display: flex; align-items: center;">
            <span class="material-icons" style="font-size: 28px; margin-right: 10px;">⚗️</span>
            TTM Experiments
        </h1>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Navigazione con icone
    st.markdown('<h2>Navigation</h2>', unsafe_allow_html=True)
    
    nav_options = {
        "Dashboard": "dashboard",
        "Templates": "folder",
        "Run Experiment": "play_arrow",
        "Results": "bar_chart",
        "System Status": "settings"
    }
    
    # Crea opzioni di navigazione con icone
    page_names = list(nav_options.keys())
    
    # Determina l'indice iniziale
    page_index = 0
    if 'selected_page' in st.session_state and st.session_state.selected_page in page_names:
        page_index = page_names.index(st.session_state.selected_page)
    
    # Usa solo i nomi delle pagine per il radio, le icone verranno aggiunte via CSS
    selected_page_name = st.radio(
        "Seleziona sezione",
        page_names,
        index=page_index,
        label_visibility="collapsed"
    )
    
    # Se la pagina selezionata è cambiata, aggiorna lo stato e fai rerun
    if 'selected_page' not in st.session_state or st.session_state.selected_page != selected_page_name:
        st.session_state.selected_page = selected_page_name
        st.rerun()
    
    page = selected_page_name


# Pagina Dashboard
if page == "Dashboard":
    st.title("Dashboard")
    
    col1, col2, col3, col4 = st.columns(4)
    
    templates = get_template_files()
    experiments = organize_results_by_experiment()
    experiments_state = get_all_experiments_state()
    running = len([e for e in experiments_state.values() if e.get('status') == 'running'])
    completed = len([e for e in st.session_state.experiment_history if e.get('status') == 'completed'])
    
    with col1:
        st.metric("Templates", len(templates))
    with col2:
        st.metric("Experiments", len(experiments))
    with col3:
        st.metric("Running", running)
    with col4:
        st.metric("Completed", completed)
    
    st.markdown("---")
    
    # Esperimenti in esecuzione
    experiments_state = get_all_experiments_state()
    if experiments_state:
        st.subheader("Running Experiments")
        for exp_id, exp_data in experiments_state.items():
            if exp_data.get('status') == 'running':
                with st.expander(f"Running: {exp_id}", expanded=True):
                    # Pulsante Stop
                    col_stop1, col_stop2 = st.columns([4, 1])
                    with col_stop2:
                        if st.button("Stop", key=f"stop_dash_{exp_id}", type="secondary", use_container_width=True):
                            if stop_experiment(exp_id):
                                st.success("Experiment stopped successfully")
                                st.rerun()
                            else:
                                st.error("Failed to stop experiment")
                    
            elapsed = exp_data.get('elapsed', 0)
            proc_info = exp_data.get('process_info')
            result_folder = exp_data.get('result_folder')
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Elapsed Time", format_time(elapsed))
            if proc_info and isinstance(proc_info, dict):
                with col2:
                    st.metric("CPU", f"{proc_info.get('cpu_percent', 0):.1f}%")
                with col3:
                    st.metric("Memory", f"{proc_info.get('memory_mb', 0):.1f} MB")
            else:
                with col2:
                    st.metric("CPU", "N/A")
                with col3:
                    st.metric("Memory", "N/A")
            
            result_count = exp_data.get('result_files_count', 0)
            if result_folder:
                folder_name = Path(result_folder).name
                st.write(f"Result folder: `{folder_name}` ({result_count} files)")
            else:
                st.write(f"Result files: {result_count}")
    
    # Cronologia esperimenti
    if st.session_state.experiment_history:
        st.subheader("Experiment History")
        history_df = pd.DataFrame(st.session_state.experiment_history)
        
        # Assicurati che tutte le colonne necessarie esistano
        required_columns = ['id', 'template', 'mode', 'status', 'elapsed']
        available_columns = [col for col in required_columns if col in history_df.columns]
        
        # Formatta elapsed se presente
        if 'elapsed' in history_df.columns:
            history_df['elapsed'] = history_df['elapsed'].apply(
                lambda x: format_time(x) if pd.notna(x) and isinstance(x, (int, float)) else str(x) if pd.notna(x) else 'N/A'
            )
        
        # Mostra solo le colonne disponibili
        if available_columns:
            st.dataframe(
                history_df[available_columns],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.dataframe(
                history_df,
                use_container_width=True,
                hide_index=True
            )


# Pagina Templates
elif page == "Templates":
    st.title("Template Management")
    
    # Upload nuovo template
    st.subheader("Upload New Template")
    uploaded_file = st.file_uploader(
        "Choose an Excel file",
        type=['xlsx', 'xls'],
        help="Upload a new experiment template to the experiments_templates folder"
    )
    
    if uploaded_file is not None:
        if st.button("Save Template"):
            try:
                template_path = TEMPLATES_DIR / uploaded_file.name
                with open(template_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                st.success(f"Template saved: {uploaded_file.name}")
                st.rerun()
            except Exception as e:
                st.error(f"Error saving template: {str(e)}")
    
    st.markdown("---")
    
    # Lista template disponibili
    st.subheader("Available Templates")
    templates = get_template_files()
    
    if not templates:
        st.info("No templates found. Upload a template using the form above.")
    else:
        for template in templates:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{template.name}**")
                size = template.stat().st_size / 1024
                mtime = datetime.fromtimestamp(template.stat().st_mtime)
                st.caption(f"Size: {size:.1f} KB | Modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
            
            with col2:
                preview_key = f"preview_{template.name}"
                show_preview = st.checkbox("Preview", key=preview_key, value=False)
            
            with col3:
                if st.button("Delete", key=f"delete_{template.name}"):
                    try:
                        template.unlink()
                        st.success(f"Deleted {template.name}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
            
            # Preview Excel
            if show_preview:
                try:
                    df_dict = pd.read_excel(template, sheet_name=None)
                    for sheet_name, df in df_dict.items():
                        with st.expander(f"Sheet: {sheet_name}"):
                            st.dataframe(df, use_container_width=True)
                except Exception as e:
                    st.error(f"Error reading Excel: {str(e)}")
            
            st.markdown("---")


# Pagina Run Experiment
elif page == "Run Experiment":
    st.title("Run Experiment")
    
    templates = get_template_files()
    
    if not templates:
        st.warning("No templates available. Please upload a template first.")
    else:
        # Selezione template
        template_names = [str(t.name) for t in templates]
        selected_template_name = st.selectbox(
            "Select Template",
            template_names,
            index=0 if st.session_state.selected_template is None else 
                  template_names.index(st.session_state.selected_template) if st.session_state.selected_template in template_names else 0
        )
        
        selected_template_path = TEMPLATES_DIR / selected_template_name
        st.session_state.selected_template = selected_template_name
        
        # Informazioni template
        if selected_template_path.exists():
            size = selected_template_path.stat().st_size / 1024
            mtime = datetime.fromtimestamp(selected_template_path.stat().st_mtime)
            st.info(f"**{selected_template_name}** | Size: {size:.1f} KB | Modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Selezione modalità
        mode = st.radio(
            "Execution Mode",
            ["test", "full"],
            help="test: Runs one randomly selected group per treatment\nfull: Runs the complete experiment with all groups"
        )
        
        # Pulsante esecuzione
        col1, col2 = st.columns([1, 4])
        with col1:
            run_button = st.button("Run Experiment", type="primary", use_container_width=True)
        
        if run_button:
            experiment_id = f"{selected_template_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Avvia esperimento in thread separato
            thread = threading.Thread(
                target=run_experiment_async,
                args=(str(selected_template_path), mode, experiment_id),
                daemon=True
            )
            thread.start()
            
            update_experiment_state(experiment_id, {
                'status': 'starting',
                'start_time': time.time(),
                'elapsed': 0,
                'template': str(selected_template_path)
            })
            
            # Aggiungi alla cronologia
            st.session_state.experiment_history.append({
                'id': experiment_id,
                'template': str(selected_template_path),
                'mode': mode,
                'start_time': datetime.now().isoformat(),
                'status': 'starting',
                'elapsed': 0
            })
            
            st.success(f"Experiment started: {experiment_id}")
            st.rerun()
        
        st.markdown("---")
        
        # Monitoraggio esperimenti in esecuzione
        experiments_state = get_all_experiments_state()
        running_exps = {k: v for k, v in experiments_state.items() 
                       if v.get('status') == 'running'}
        
        if running_exps:
            st.subheader("Live Monitoring")
            
            # Placeholder per auto-refresh
            auto_refresh_placeholder = st.empty()
            
            for exp_id, exp_data in running_exps.items():
                with st.container():
                    # Header con pulsante Stop
                    col_header1, col_header2 = st.columns([4, 1])
                    with col_header1:
                        st.markdown(f"### Running: {exp_id}")
                    with col_header2:
                        if st.button("Stop", key=f"stop_{exp_id}", type="secondary", use_container_width=True):
                            if stop_experiment(exp_id):
                                st.success(f"Experiment {exp_id} stopped")
                                st.rerun()
                            else:
                                st.error(f"Failed to stop experiment {exp_id}")
                    
                    elapsed = exp_data.get('elapsed', 0)
                    proc_info = exp_data.get('process_info')
                    
                    # Metriche principali
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Elapsed Time", format_time(elapsed))
                    if proc_info and isinstance(proc_info, dict):
                        with col2:
                            st.metric("CPU Usage", f"{proc_info.get('cpu_percent', 0):.1f}%")
                        with col3:
                            st.metric("Memory", f"{proc_info.get('memory_mb', 0):.1f} MB")
                        with col4:
                            st.metric("Connections", proc_info.get('num_connections', 0))
                    else:
                        with col2:
                            st.metric("CPU Usage", "N/A")
                        with col3:
                            st.metric("Memory", "N/A")
                        with col4:
                            st.metric("Connections", "N/A")
                    
                    # File risultati
                    result_count = exp_data.get('result_files_count', 0)
                    st.metric("Result Files", result_count)
                    
                    # Output in tempo reale
                    stdout = exp_data.get('stdout', '')
                    if stdout:
                        with st.expander("Live Output"):
                            st.text(stdout[-5000:])  # Ultimi 5000 caratteri
                    
                    st.markdown("---")
            
            # Auto-refresh controllato
            with auto_refresh_placeholder.container():
                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button("Refresh Status", key="refresh_status", use_container_width=True):
                        st.rerun()
                with col2:
                    st.caption("Tip: Click refresh to update metrics. Auto-refresh every 3 seconds when experiments are running.")
            
            # Auto-refresh ogni 3 secondi se ci sono esperimenti in esecuzione
            time.sleep(3)
            st.rerun()
        
        # Esperimenti completati di recente
        experiments_state = get_all_experiments_state()
        recent_completed = [
            (k, v) for k, v in experiments_state.items()
            if v.get('status') in ['completed', 'failed', 'error']
        ]
        
        if recent_completed:
            st.subheader("Recent Results")
            for exp_id, exp_data in recent_completed[-5:]:  # Ultimi 5
                status_text = "Completed" if exp_data.get('status') == 'completed' else "Failed"
                with st.expander(f"{status_text}: {exp_id}"):
                    elapsed = exp_data.get('elapsed', 0)
                    return_code = exp_data.get('return_code')
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Elapsed Time", format_time(elapsed))
                    with col2:
                        st.metric("Return Code", return_code if return_code is not None else "N/A")
                    
                    stdout = exp_data.get('stdout', '')
                    stderr = exp_data.get('stderr', '')
                    
                    if stdout:
                        with st.expander("Output"):
                            st.text(stdout)
                    if stderr:
                        with st.expander("Errors/Warnings"):
                            st.text(stderr)


# Pagina Results
elif page == "Results":
    st.title("Experiment Results")
    
    experiments = organize_results_by_experiment()
    
    if not experiments:
        st.info("No results found. Run an experiment to generate results.")
    else:
        st.subheader(f"Experiments ({len(experiments)} total)")
        
        # Dropdown per selezionare l'esperimento
        experiment_names = list(experiments.keys())
        selected_experiment = st.selectbox(
            "Select Experiment",
            experiment_names,
            index=0 if experiment_names else None,
            help="Select an experiment to view its results"
        )
        
        if selected_experiment:
            exp_data = experiments[selected_experiment]
            csv_file = exp_data['csv']
            json_file = exp_data['json']
            timestamp = exp_data['timestamp']
            folder = exp_data.get('folder')
            all_csv = exp_data.get('all_csv', [])
            all_json = exp_data.get('all_json', [])
            
            # Informazioni generali esperimento
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Experiment Name", selected_experiment)
            with col2:
                files_count = len(all_csv) + len(all_json)
                st.metric("Files", files_count)
            with col3:
                mtime_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                st.metric("Last Modified", mtime_str.split()[0])
            with col4:
                if folder:
                    st.metric("Folder", folder.name)
                else:
                    st.metric("Location", "Root (legacy)")
            
            st.markdown("---")
            
            # Tabs per CSV e JSON
            if csv_file and json_file:
                tab1, tab2 = st.tabs(["CSV Results", "JSON Results"])
            elif csv_file:
                tab1 = None
                tab2 = None
            elif json_file:
                tab1 = None
                tab2 = None
            else:
                st.warning("No files found for this experiment.")
                tab1 = None
                tab2 = None
            
            # Tab CSV
            if csv_file:
                if tab1:
                    container = tab1
                else:
                    container = st.container()
                
                with container:
                    st.subheader("CSV Results")
                    
                    col_info1, col_info2, col_info3 = st.columns(3)
                    with col_info1:
                        size = csv_file.stat().st_size / 1024
                        st.write(f"**Size:** {size:.2f} KB")
                    with col_info2:
                        mtime = datetime.fromtimestamp(csv_file.stat().st_mtime)
                        st.write(f"**Modified:** {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
                    with col_info3:
                        if st.button("Delete CSV", key=f"del_csv_{selected_experiment}"):
                            try:
                                csv_file.unlink()
                                st.success("CSV file deleted")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                    
                    try:
                        df = pd.read_csv(csv_file)
                        st.dataframe(df, use_container_width=True, height=400)
                        
                        # Statistiche
                        st.subheader("Statistics")
                        col_stat1, col_stat2, col_stat3 = st.columns(3)
                        with col_stat1:
                            st.metric("Rows", len(df))
                        with col_stat2:
                            st.metric("Columns", len(df.columns))
                        with col_stat3:
                            st.metric("Size", f"{size:.2f} KB")
                        
                        # Download button
                        csv = df.to_csv(index=False)
                        st.download_button(
                            "Download CSV",
                            csv,
                            file_name=csv_file.name,
                            mime="text/csv"
                        )
                    except Exception as e:
                        st.error(f"Error reading CSV file: {str(e)}")
            
            # Tab JSON
            if json_file:
                if tab2:
                    container = tab2
                else:
                    container = st.container()
                
                with container:
                    st.subheader("JSON Results")
                    
                    col_info1, col_info2, col_info3 = st.columns(3)
                    with col_info1:
                        size = json_file.stat().st_size / 1024
                        st.write(f"**Size:** {size:.2f} KB")
                    with col_info2:
                        mtime = datetime.fromtimestamp(json_file.stat().st_mtime)
                        st.write(f"**Modified:** {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
                    with col_info3:
                        if st.button("Delete JSON", key=f"del_json_{selected_experiment}"):
                            try:
                                json_file.unlink()
                                st.success("JSON file deleted")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                    
                    try:
                        with open(json_file, 'r') as f:
                            data = json.load(f)
                        st.json(data)
                        
                        # Statistiche
                        st.subheader("Statistics")
                        col_stat1, col_stat2 = st.columns(2)
                        with col_stat1:
                            st.metric("Size", f"{size:.2f} KB")
                        with col_stat2:
                            if isinstance(data, dict):
                                st.metric("Top-level Keys", len(data.keys()))
                            elif isinstance(data, list):
                                st.metric("Array Length", len(data))
                        
                        # Download button
                        st.download_button(
                            "Download JSON",
                            json.dumps(data, indent=2),
                            file_name=json_file.name,
                            mime="application/json"
                        )
                    except Exception as e:
                        st.error(f"Error reading JSON file: {str(e)}")
            
            # Pulsante per eliminare tutto l'esperimento
            st.markdown("---")
            col_del1, col_del2 = st.columns([3, 1])
            with col_del2:
                if st.button("Delete Experiment", key=f"del_exp_{selected_experiment}", type="secondary"):
                    try:
                        deleted_count = 0
                        if folder and folder.exists():
                            # Elimina l'intera cartella
                            for file in folder.iterdir():
                                if file.is_file():
                                    file.unlink()
                                    deleted_count += 1
                            # Rimuovi la cartella se è vuota
                            try:
                                folder.rmdir()
                            except OSError:
                                pass  # Cartella non vuota o errore
                            st.success(f"Experiment folder deleted ({deleted_count} files removed)")
                        else:
                            # Elimina i file nella root (retrocompatibilità)
                            deleted = []
                            for csv_f in all_csv:
                                csv_f.unlink()
                                deleted.append("CSV")
                            for json_f in all_json:
                                json_f.unlink()
                                deleted.append("JSON")
                            st.success(f"Experiment deleted ({', '.join(deleted)} files removed)")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting experiment: {str(e)}")


# Pagina System Status
elif page == "System Status":
    st.title("System Status")
    
    # Informazioni ambiente
    st.subheader("Environment Information")
    col_env1, col_env2 = st.columns(2)
    
    with col_env1:
        # Rileva se siamo su Streamlit Cloud o locale
        is_cloud = False
        try:
            if hasattr(st, "secrets") and st.secrets is not None:
                # Prova a verificare se st.secrets contiene dati (indicatore di Cloud)
                try:
                    # Se st.secrets è accessibile e non è vuoto, probabilmente siamo su Cloud
                    if hasattr(st.secrets, "get"):
                        # Prova ad accedere a una chiave comune
                        _ = st.secrets.get("OPENAI_API_KEY", None)
                        is_cloud = True
                    elif isinstance(st.secrets, dict) and len(st.secrets) > 0:
                        is_cloud = True
                except (AttributeError, TypeError, KeyError):
                    pass
        except Exception:
            pass
        
        env_type = "🌐 Streamlit Cloud" if is_cloud else "💻 Local"
        st.metric("Environment", env_type)
    
    with col_env2:
        st.metric("Python Version", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Informazioni sistema
    st.markdown("---")
    st.subheader("System Information")
    
    col_sys1, col_sys2, col_sys3 = st.columns(3)
    with col_sys1:
        st.write(f"**OS:** {platform.system()} {platform.release()}")
    with col_sys2:
        st.write(f"**Architecture:** {platform.machine()}")
    with col_sys3:
        st.write(f"**Streamlit:** {st.__version__}")
    
    # Credenziali caricate
    st.markdown("---")
    st.subheader("API Keys Status")
    
    api_keys = {
        'OPENAI_API_KEY': get_secret('OPENAI_API_KEY'),
        'HF_API_KEY': get_secret('HF_API_KEY'),
        'OPENROUTER_API_KEY': get_secret('OPENROUTER_API_KEY')
    }
    
    def mask_key(key: Optional[str]) -> str:
        """Maschera una chiave API mostrando solo i primi e ultimi caratteri."""
        if not key:
            return "❌ Not configured"
        if len(key) <= 10:
            return "⚠️ Invalid (too short)"
        return f"✅ {key[:8]}...{key[-6:]}"
    
    for key_name, key_value in api_keys.items():
        col_key1, col_key2 = st.columns([2, 3])
        with col_key1:
            st.write(f"**{key_name}:**")
        with col_key2:
            st.write(mask_key(key_value))
    
    # Informazioni directory
    st.markdown("---")
    st.subheader("Directory Status")
    
    directories_info = [
        ("Templates Directory", TEMPLATES_DIR),
        ("Results Directory", RESULTS_DIR),
        ("State File", EXPERIMENTS_STATE_FILE),
    ]
    
    for dir_name, dir_path in directories_info:
        col_dir1, col_dir2, col_dir3 = st.columns([2, 2, 2])
        with col_dir1:
            st.write(f"**{dir_name}:**")
        with col_dir2:
            exists = dir_path.exists() if isinstance(dir_path, Path) else os.path.exists(dir_path)
            status = "✅ Exists" if exists else "❌ Not found"
            st.write(status)
        with col_dir3:
            if exists:
                if isinstance(dir_path, Path) and dir_path.is_dir():
                    file_count = len(list(dir_path.glob("*"))) if dir_path.exists() else 0
                    st.write(f"({file_count} items)")
                elif isinstance(dir_path, Path) and dir_path.is_file():
                    size = dir_path.stat().st_size / 1024
                    st.write(f"({size:.2f} KB)")
                else:
                    st.write("")
            else:
                st.write("")
    
    # Statistiche file
    st.markdown("---")
    st.subheader("File Statistics")
    
    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
    
    templates = get_template_files()
    experiments = organize_results_by_experiment()
    experiments_state = get_all_experiments_state()
    running = len([e for e in experiments_state.values() if e.get('status') == 'running'])
    
    with col_stat1:
        st.metric("Templates", len(templates))
    with col_stat2:
        st.metric("Experiment Folders", len(experiments))
    with col_stat3:
        st.metric("Running Experiments", running)
    with col_stat4:
        total_experiments = len(experiments_state)
        st.metric("Total Experiments", total_experiments)
    
    # Informazioni aggiuntive
    st.markdown("---")
    st.subheader("Additional Information")
    
    with st.expander("Python Environment Details"):
        st.code(f"""
Python Version: {sys.version}
Platform: {platform.platform()}
Executable: {sys.executable}
""", language="text")
    
    with st.expander("Secrets Source"):
        secrets_source_info = []
        for key_name in ['OPENAI_API_KEY', 'HF_API_KEY', 'OPENROUTER_API_KEY']:
            key_value = get_secret(key_name)
            if key_value:
                # Prova a capire da dove viene
                source = "Unknown"
                try:
                    if hasattr(st, "secrets") and st.secrets is not None:
                        try:
                            if hasattr(st.secrets, "get"):
                                if st.secrets.get(key_name) is not None:
                                    source = "st.secrets (Cloud)"
                            elif isinstance(st.secrets, dict) and key_name in st.secrets:
                                source = "st.secrets (Cloud)"
                        except (AttributeError, TypeError, KeyError):
                            pass
                except Exception:
                    pass
                
                if source == "Unknown":
                    # Controlla se è nelle env vars
                    if os.getenv(key_name):
                        source = "Environment Variable (.env)"
                    else:
                        source = "Environment Variable (system)"
                
                secrets_source_info.append(f"**{key_name}:** {source}")
            else:
                secrets_source_info.append(f"**{key_name}:** ❌ Not configured")
        
        st.markdown("\n".join(secrets_source_info))


if __name__ == "__main__":
    pass

