"""Azione self_config: Lily modifica i propri settings."""

from core.actions.base import Action


# Mapping nomi parlati → chiavi settings
SETTING_ALIASES = {
    "voce": "tts_voice",
    "voice": "tts_voice",
    "tts": "tts_enabled",
    "text to speech": "tts_enabled",
    "hotkey": "hotkey",
    "tasto": "hotkey",
    "thinking": "thinking_enabled",
    "ragionamento": "thinking_enabled",
    "num predict": "num_predict",
    "token": "num_predict",
    "chat token": "chat_num_predict",
    "storico": "chat_max_history",
    "storia": "chat_max_history",
    "silenzio dettatura": "dictation_silence_duration",
    "durata dettatura": "dictation_max_duration",
    "timeout dettatura": "dictation_silence_timeout",
}

# Valori speciali parlati → valori reali
VALUE_ALIASES = {
    "sì": True, "si": True, "attiva": True, "abilita": True, "on": True, "accendi": True,
    "no": False, "disattiva": False, "disabilita": False, "off": False, "spegni": False,
    "isabella": "Isabella", "diego": "Diego", "elsa": "Elsa",
    "paola": "Paola",
}


class SelfConfigAction(Action):
    def execute(self, intent: dict, config) -> str:
        query = intent.get("query", "").strip().lower()
        parameter = intent.get("parameter", "").strip()

        if not query:
            return "Non hai specificato quale impostazione cambiare."

        # Trova la chiave del setting
        setting_key = SETTING_ALIASES.get(query)
        if not setting_key:
            # Prova match parziale
            for alias, key in SETTING_ALIASES.items():
                if alias in query:
                    setting_key = key
                    break

        if not setting_key:
            return f"Non conosco l'impostazione {query}."

        # Verifica che sia un setting di Lily (non utente)
        if not config.is_lily_setting(setting_key):
            return f"Non posso modificare {setting_key}, è un'impostazione utente."

        if not parameter:
            # Leggi il valore attuale
            current = getattr(config, setting_key, None)
            return f"{query} è impostato a {current}."

        # Converti il valore
        value = VALUE_ALIASES.get(parameter.lower(), parameter)

        # Type casting basato sul valore attuale
        current = getattr(config, setting_key, None)
        if isinstance(current, bool) and not isinstance(value, bool):
            value = value.lower() in ("true", "1", "sì", "si", "on")
        elif isinstance(current, int) and isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                return f"Il valore {parameter} non è valido per {query}."
        elif isinstance(current, float) and isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                return f"Il valore {parameter} non è valido per {query}."

        # Applica
        old_value = current
        setattr(config, setting_key, value)
        config.save_lily()
        print(f"[SelfConfig] {setting_key}: {old_value} → {value}")

        return f"Ho cambiato {query} da {old_value} a {value}."
