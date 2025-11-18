#!/usr/bin/env python3
"""
Helper module per gestire secrets in modo compatibile con Streamlit Cloud e locale.
In locale legge da .env (via python-dotenv), su Streamlit Cloud da st.secrets.
"""

import os
from typing import Optional

# In locale carica .env (su Cloud non darà problemi se il file non esiste)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv non installato, usa solo variabili d'ambiente
    pass


def get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Ottiene un secret da st.secrets (Streamlit Cloud) o da variabili d'ambiente (locale).
    
    Args:
        name: Nome della chiave del secret
        default: Valore di default se la chiave non viene trovata
    
    Returns:
        Il valore del secret o default se non trovato
    """
    # 1) Prova a leggere da st.secrets (Streamlit Cloud)
    try:
        import streamlit as st
        if hasattr(st, "secrets") and st.secrets is not None:
            # Prova prima come chiave diretta
            if name in st.secrets:
                return st.secrets[name]
            # Prova anche con notazione a punti (es. st.secrets["api_keys"]["OPENAI_API_KEY"])
            # Dividi il nome in parti separate da punti o underscore
            parts = name.split('.')
            if len(parts) > 1:
                current = st.secrets
                for part in parts:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        break
                else:
                    return current if isinstance(current, str) else None
    except Exception:
        # Nel caso st.secrets non sia disponibile o dia errore (locale senza Streamlit)
        pass
    
    # 2) Se non trovato, prova dalle variabili d'ambiente (locale con dotenv)
    return os.getenv(name, default)

