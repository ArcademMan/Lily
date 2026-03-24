"""Azione self_config: Lily modifica i propri settings."""

from core.actions.base import Action
from core.i18n import t, t_dict, t_set


# Mapping nomi parlati → chiavi settings (loaded from locale)
def _get_setting_aliases():
    return t_dict("setting_aliases")

# Valori speciali parlati → valori reali
def _get_value_aliases_true():
    return t_set("value_aliases_true")

def _get_value_aliases_false():
    return t_set("value_aliases_false")


class SelfConfigAction(Action):
    def execute(self, intent: dict, config, **kwargs) -> str:
        query = intent.get("query", "").strip().lower()
        parameter = intent.get("parameter", "").strip()

        if not query:
            return t("config_no_setting")

        # Trova la chiave del setting
        aliases = _get_setting_aliases()
        setting_key = aliases.get(query)
        if not setting_key:
            # Prova match parziale
            for alias, key in aliases.items():
                if alias in query:
                    setting_key = key
                    break

        if not setting_key:
            return t("config_unknown_setting", query=query)

        # Verifica che sia un setting di Lily (non utente)
        if not config.is_lily_setting(setting_key):
            return t("config_readonly", key=setting_key)

        if not parameter:
            # Leggi il valore attuale
            current = getattr(config, setting_key, None)
            return t("config_current_value", query=query, value=current)

        # Converti il valore
        true_vals = _get_value_aliases_true()
        false_vals = _get_value_aliases_false()
        param_lower = parameter.lower()
        if param_lower in true_vals:
            value = True
        elif param_lower in false_vals:
            value = False
        else:
            value = parameter

        # Type casting basato sul valore attuale
        current = getattr(config, setting_key, None)
        if isinstance(current, bool) and not isinstance(value, bool):
            value = value.lower() in true_vals
        elif isinstance(current, int) and isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                return t("config_invalid_value", parameter=parameter, query=query)
        elif isinstance(current, float) and isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                return t("config_invalid_value", parameter=parameter, query=query)

        # Applica
        old_value = current
        setattr(config, setting_key, value)
        config.save_lily()
        print(f"[SelfConfig] {setting_key}: {old_value} → {value}")

        return t("config_changed", query=query, old=old_value, new=value)
