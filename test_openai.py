#!/usr/bin/env python3
"""
Script di test per verificare la connessione con OpenAI API.
Carica la chiave API dal file .env e esegue una chiamata di test.
"""

import os
from dotenv import load_dotenv
from openai import OpenAI


def test_openai_connection():
    """Testa la connessione con OpenAI API."""
    # Carica le variabili d'ambiente dal file .env
    load_dotenv()
    
    # Ottieni la chiave API
    api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        print("❌ Errore: OPENAI_API_KEY non trovata nel file .env")
        return False
    
    print(f"✅ Chiave API trovata: {api_key[:10]}...{api_key[-10:]}")
    
    try:
        # Inizializza il client OpenAI
        client = OpenAI(api_key=api_key)
        
        print("\n🔄 Invio richiesta di test a OpenAI...")
        
        # Esegui una chiamata di test semplice
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "Rispondi solo con 'OK' se ricevi questo messaggio."}
            ],
            max_tokens=10
        )
        
        # Stampa il risultato
        message = response.choices[0].message.content
        print(f"✅ Risposta ricevuta: {message}")
        print(f"✅ Token utilizzati: {response.usage.total_tokens}")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore durante la chiamata a OpenAI: {str(e)}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("Test connessione OpenAI API")
    print("=" * 50)
    
    success = test_openai_connection()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ Test completato con successo!")
    else:
        print("❌ Test fallito!")
    print("=" * 50)

