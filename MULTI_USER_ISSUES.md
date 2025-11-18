# Problemi Multi-Utente: Analisi e Soluzioni

## 🔴 Problemi Critici Identificati

### 1. Race Conditions sul File di Stato

**Problema:**
```python
# app.py:166-171
def update_experiment_state(experiment_id: str, data: Dict):
    global _experiments_state
    with _experiments_lock:  # ⚠️ Lock solo thread-safe, non process-safe!
        _experiments_state[experiment_id] = data
        save_experiments_state(_experiments_state)  # ⚠️ Sovrascrive tutto il file
```

**Scenario di fallimento:**
1. Utente A carica stato: `{exp1: {...}, exp2: {...}}`
2. Utente B carica stato: `{exp1: {...}, exp2: {...}}`
3. Utente A aggiorna exp1 → salva: `{exp1: {...updated...}, exp2: {...}}`
4. Utente B aggiorna exp2 → salva: `{exp1: {...old...}, exp2: {...updated...}}`
5. **Risultato:** Le modifiche di A su exp1 vengono perse!

**Impatto:** ⚠️ **ALTO** - Perdita di dati, stati inconsistenti

---

### 2. Nessun Isolamento tra Utenti

**Problema:**
- Tutti gli utenti vedono tutti gli esperimenti di tutti
- Chiunque può fermare gli esperimenti di altri
- Nessuna autenticazione/autorizzazione

**Codice problematico:**
```python
# app.py:808-813
if st.button("Stop", key=f"stop_{exp_id}"):
    if stop_experiment(exp_id):  # ⚠️ Nessun controllo di ownership!
        st.success(f"Experiment {exp_id} stopped")
```

**Impatto:** ⚠️ **CRITICO** - Sicurezza compromessa, possibile sabotaggio

---

### 3. Variabile Globale Condivisa

**Problema:**
```python
# app.py:144-145
_experiments_lock = threading.Lock()
_experiments_state: Dict[str, Dict] = {}  # ⚠️ Globale, condivisa tra sessioni
```

**Scenario:**
- Streamlit in deployment può avere più worker processes
- Ogni worker ha la sua copia di `_experiments_state`
- Modifiche in un worker non sono visibili agli altri
- Il file JSON diventa l'unica fonte di verità, ma con race conditions

**Impatto:** ⚠️ **ALTO** - Stati inconsistenti tra worker

---

### 4. File di Risultato Condivisi

**Problema:**
```python
# app.py:138, 330-335
RESULTS_DIR = Path("experiment_results")
def get_result_files() -> List[Path]:
    results = list(RESULTS_DIR.glob("*.json")) + list(RESULTS_DIR.glob("*.csv"))
```

**Scenario:**
- Due utenti eseguono lo stesso template contemporaneamente
- Entrambi generano file con stesso nome base
- Possibile sovrascrittura dei risultati

**Impatto:** ⚠️ **MEDIO** - Perdita di risultati

---

## ✅ Soluzioni Proposte

### Soluzione 1: File Locking Process-Safe

**Implementazione:**
```python
import fcntl  # Unix
# oppure
import msvcrt  # Windows
import portalocker  # Cross-platform (raccomandato)

def save_experiments_state(state: Dict[str, Dict]):
    """Salva lo stato con file locking process-safe."""
    try:
        with open(EXPERIMENTS_STATE_FILE, 'r+') as f:
            portalocker.lock(f, portalocker.LOCK_EX)  # Lock esclusivo
            # Leggi stato corrente
            try:
                current_state = json.load(f)
            except json.JSONDecodeError:
                current_state = {}
            
            # Merge con nuovo stato
            current_state.update(state)
            
            # Scrivi
            f.seek(0)
            f.truncate()
            json.dump(current_state, f, indent=2, default=str)
            # Lock rilasciato automaticamente alla chiusura
    except Exception as e:
        st.error(f"Error saving state: {e}")
```

**Vantaggi:**
- ✅ Previene race conditions tra processi
- ✅ Cross-platform con `portalocker`
- ✅ Mantiene compatibilità con codice esistente

---

### Soluzione 2: Isolamento per Utente

**Implementazione:**
```python
import hashlib

def get_user_id() -> str:
    """Ottiene un ID univoco per l'utente corrente."""
    # Opzione 1: Session ID di Streamlit
    if 'user_id' not in st.session_state:
        st.session_state.user_id = hashlib.md5(
            str(st.session_state.get('_session_id', str(time.time()))).encode()
        ).hexdigest()[:8]
    return st.session_state.user_id

def update_experiment_state(experiment_id: str, data: Dict):
    """Aggiorna con ownership tracking."""
    user_id = get_user_id()
    data['owner'] = user_id  # ⚠️ Aggiungi ownership
    data['created_at'] = time.time()
    
    with _experiments_lock:
        _experiments_state[experiment_id] = data
        save_experiments_state(_experiments_state)

def can_modify_experiment(experiment_id: str) -> bool:
    """Verifica se l'utente corrente può modificare l'esperimento."""
    exp_state = get_experiment_state(experiment_id)
    if not exp_state:
        return False
    return exp_state.get('owner') == get_user_id()

# Nel codice UI:
if st.button("Stop", key=f"stop_{exp_id}"):
    if not can_modify_experiment(exp_id):
        st.error("You don't have permission to stop this experiment")
    elif stop_experiment(exp_id):
        st.success(f"Experiment {exp_id} stopped")
```

**Filtro per utente:**
```python
def get_user_experiments() -> Dict[str, Dict]:
    """Ottiene solo gli esperimenti dell'utente corrente."""
    user_id = get_user_id()
    all_exps = get_all_experiments_state()
    return {
        k: v for k, v in all_exps.items()
        if v.get('owner') == user_id
    }
```

**Vantaggi:**
- ✅ Isolamento tra utenti
- ✅ Protezione da modifiche non autorizzate
- ✅ Privacy dei dati

---

### Soluzione 3: Database invece di JSON

**Implementazione con SQLite:**
```python
import sqlite3
import threading

_db_lock = threading.Lock()

def init_db():
    """Inizializza il database."""
    conn = sqlite3.connect('.experiments_state.db', check_same_thread=False)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS experiments (
            experiment_id TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            status TEXT NOT NULL,
            start_time REAL,
            elapsed REAL,
            process_pid INTEGER,
            template TEXT,
            stdout TEXT,
            stderr TEXT,
            return_code INTEGER,
            created_at REAL,
            updated_at REAL
        )
    ''')
    conn.commit()
    return conn

def update_experiment_state(experiment_id: str, data: Dict):
    """Aggiorna con transazione atomica."""
    user_id = get_user_id()
    conn = init_db()
    
    with _db_lock:
        conn.execute('''
            INSERT OR REPLACE INTO experiments 
            (experiment_id, owner, status, start_time, elapsed, process_pid, 
             template, stdout, stderr, return_code, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            experiment_id,
            user_id,
            data.get('status'),
            data.get('start_time'),
            data.get('elapsed'),
            data.get('process_pid'),
            data.get('template'),
            data.get('stdout', ''),
            data.get('stderr', ''),
            data.get('return_code'),
            time.time(),
            time.time()
        ))
        conn.commit()
```

**Vantaggi:**
- ✅ Transazioni atomiche (ACID)
- ✅ Query efficienti
- ✅ Scalabile
- ✅ Previene race conditions nativamente

---

### Soluzione 4: Directory per Utente

**Implementazione:**
```python
def get_user_results_dir() -> Path:
    """Ottiene la directory risultati per l'utente corrente."""
    user_id = get_user_id()
    user_dir = RESULTS_DIR / f"user_{user_id}"
    user_dir.mkdir(exist_ok=True)
    return user_dir

def get_result_files() -> List[Path]:
    """Ottiene solo i file dell'utente corrente."""
    user_dir = get_user_results_dir()
    results = list(user_dir.glob("*.json")) + list(user_dir.glob("*.csv"))
    return sorted(results, key=lambda x: x.stat().st_mtime, reverse=True)
```

**Vantaggi:**
- ✅ Isolamento completo dei risultati
- ✅ Nessun conflitto di nomi
- ✅ Privacy garantita

---

## 🎯 Raccomandazione: Implementazione Graduale

### Fase 1: Quick Fix (Immediato)
1. ✅ Aggiungi file locking con `portalocker`
2. ✅ Aggiungi ownership tracking con user_id
3. ✅ Filtra esperimenti per utente nella UI

### Fase 2: Miglioramenti (Breve termine)
1. ✅ Migra a SQLite per lo stato
2. ✅ Directory separate per risultati utente
3. ✅ Aggiungi autenticazione base (opzionale)

### Fase 3: Scalabilità (Lungo termine)
1. ✅ Database PostgreSQL/MySQL per multi-server
2. ✅ Redis per session state
3. ✅ Autenticazione completa (OAuth, JWT)
4. ✅ Rate limiting per prevenire abusi

---

## 📦 Dipendenze Aggiuntive

```toml
# pyproject.toml
[tool.poetry.dependencies]
portalocker = "^2.10.0"  # File locking cross-platform
```

---

## ⚠️ Note Importanti

1. **Streamlit Session State:** Non persistente tra riavvii server
2. **Deployment:** Considera se usi Streamlit Cloud, Docker, o self-hosted
3. **Backup:** Implementa backup automatici del database/stato
4. **Monitoring:** Aggiungi logging per tracciare problemi multi-utente

---

## 🔍 Testing Multi-Utente

Per testare:
1. Apri due browser/incognito windows
2. Avvia esperimenti simultanei
3. Verifica che non ci siano race conditions
4. Verifica isolamento tra utenti

