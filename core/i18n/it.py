"""Italian locale for Lily."""

import os as _os

# ── Prompts ──────────────────────────────────────────────────────────────────

def _get_lily_paths_block():
    appdata = _os.environ.get("APPDATA", _os.path.expanduser("~"))
    lily_dir = _os.path.join(appdata, "AmMstools", "Lily")
    settings_dir = _os.path.join(lily_dir, "settings")
    return (
        f"\nYou are Lily. Your settings: {settings_dir} — Your data: {lily_dir}. "
        f"If user asks about YOUR folders/settings, use open_folder with parameter=exact path."
    )

_LILY_PATHS = _get_lily_paths_block()


def _classify_ollama() -> str:
    return """Classify the user intent from Italian voice input. The text comes from speech-to-text and OFTEN contains errors.
You MUST fix names to their REAL form. Think about what real program, game, or app the user meant.

CRITICAL: The transcription is often wrong! Common examples:
- "Eldering" / "Altering" / "Elder Ring" = "Elden Ring" (game by FromSoftware)
- "Little Company" / "Lysol Company" / "Legal Company" = "Lethal Company"
- "Fortnight" / "Fort Night" = "Fortnite"
- "Maicraft" / "Main Craft" = "Minecraft"
- "Valloran" = "Valorant"
- "Lega of Legend" = "League of Legends"
- "Fottosciop" / "Foto Shop" = "Photoshop"
- "Primo Pro" = "Premiere Pro"
- "After Effect" = "After Effects"
- "Vi Es Code" / "Visco" = "VS Code" / "Visual Studio Code"
- "Cloud Code" / "Clod Code" = "Claude Code"
- Always think: what REAL software/game sounds like what was transcribed?

Reply with ONLY a JSON object, nothing else.

{"intent": "TYPE", "query": "CORRECTED_NAME", "search_terms": ["alt1", "alt2"], "parameter": "PARAM"}

TYPE must be one of:
- open_folder: user wants to FIND or OPEN A FOLDER/DIRECTORY. Keywords: "cartella", "directory", "dove si trova"
- open_program: user wants to LAUNCH/START a program, app or game. Keywords: "apri", "avvia", "lancia", "esegui"
- close_program: user wants to CLOSE/QUIT a running program. Keywords: "chiudi", "termina", "stoppa", "esci da"
- open_website: user wants to open a website or search online. If user wants to SEARCH something ("cerca su Google X", "cercalo su Google", "me lo cerchi su Google"), query = the search terms, NOT "google.com". If user wants to open a specific site ("apri YouTube"), query = the URL/domain. ANY mention of "Google" + searching = open_website, NEVER search_files.
- search_files: user wants to FIND/SEARCH for a SPECIFIC file by name. Keywords: "cerca file", "trova file", "trovami il file". ONLY when the user mentions a specific filename.
- screenshot: user wants to take a screenshot. Keywords: "screenshot", "schermata", "cattura schermo"
- timer: user wants to set or CANCEL a timer/alarm/reminder. parameter = duration (e.g. "5m", "1h", "30s") to set, or "cancel" to remove all timers, or "lista" to list active timers. For REMINDERS ("ricordami tra X di Y", "avvisami tra X che Y"), query = the reminder message, parameter = duration. For RECURRING reminders ("ogni X ricordami di Y"), parameter = "recurring DURATION" (e.g. "recurring 1h"). Keywords: "timer", "sveglia", "avvisami tra", "togli il timer", "cancella il timer", "ricordami", "ricordami tra", "ogni X ricordami"
- volume: user wants to change SYSTEM volume. parameter = "up", "down", or "mute"
- media: user wants to control music/media playback. parameter = "play_pause", "next", "previous", or "stop". Keywords: "metti play", "pausa", "prossima canzone", "canzone precedente", "stop musica", "riproduci", "metti in pausa"
- window: user wants to manage windows/screens. parameter values:
  "close_explorer" = close all open folders/explorer windows
  "minimize_all" or "show_desktop" = minimize everything / show desktop
  "snap_left" or "snap_right" = move window to left/right half of screen (put program name in query)
  "move_monitor" = move window to the other monitor/screen (put program name in query). If user specifies a monitor number ("schermo 1", "primo schermo", "secondo monitor"), append the number: "move_monitor 1", "move_monitor 2"
  "minimize" = minimize a specific window (put program name in query)
  "restore" = restore/show a minimized window (put program name in query)
  "close_all" = close all windows
  "nudge_up", "nudge_down", "nudge_left", "nudge_right" = move window slightly in a direction. Append pixel amount: "nudge_down_100" for 100px. Default is 50px. "un po'" = 50, "molto" = 200, or user can specify exact pixels.
  Keywords: "chiudi le cartelle", "minimizza tutto", "mostra desktop", "sposta a sinistra/destra", "sposta sull'altro schermo", "ripristina", "minimizza", "più in alto", "più in basso", "più a sinistra", "più a destra"
- screen_read: user wants to READ/SEE what's on a window or screen. Captures the window and reads the text via OCR. query = window/program name. parameter = what to look for or question about the content. Keywords: "leggi", "cosa c'è scritto", "leggimi", "cosa vedi su", "ultimo messaggio", "cosa dice"
- terminal_read: user wants to READ the output of Lily's INTEGRATED TERMINAL (the terminal tab inside Lily). No need for a window name. parameter = what to look for (optional). Keywords: "leggi il terminale", "cosa c'è sul terminale", "output del terminale", "cosa dice il terminale". IMPORTANT: use this ONLY when the user refers to Lily's own terminal, NOT external terminal windows.
- terminal_write: user wants to WRITE/SEND text in Lily's INTEGRATED TERMINAL. parameter = ALL text after "scrivi sul terminale"/"invia sul terminale" VERBATIM, copy the ENTIRE message exactly as the user said it, do NOT cut or filter any part. NEVER append "e invia" — enter is pressed automatically. Keywords: "scrivi sul terminale", "scrivi nel terminale", "invia sul terminale", "invia nel terminale", "manda al terminale". IMPORTANT: when user says "terminale" and wants to WRITE there, ALWAYS use terminal_write NOT type_in.
- type_in: user wants to GO TO a specific EXTERNAL window and optionally TYPE text there. query = window/program name to focus. parameter = the text to type. If the user wants to SEND/SUBMIT the message, ALWAYS append " e invia" at the END of parameter. Keywords: "vai su", "vai sul", "scrivi su", "scrivi nel", "scrivi a", "digita su", "invia a/su". NEVER use type_in with query="terminale" — use terminal_write instead.
  IMPORTANT for type_in: when user says "invia" or "e invia" ANYWHERE in the sentence, put " e invia" at the END of parameter.
  CRITICAL: "invia X", "invia su X", "invia a X" at the START of a sentence = ALWAYS type_in, NEVER chain, NEVER chat. The app name follows "invia" directly or after "su/a".
  CRITICAL: parameter must contain ALL the text after the app name, VERBATIM. Do NOT summarize, cut, or rephrase. Copy the ENTIRE message exactly as the user said it.
  If user says ONLY "invia su X" or "scrivi su X" WITHOUT specifying what to write, set parameter to "dictate" — the system will activate voice dictation mode for that window.
- time: user asks for current time or date
- dictation: user wants to type text at cursor via voice. Keywords: "modalità dettatura", "dettatura", "scrivi", "dettami". If user says "scrivi [TEXT]", put [TEXT] in query (the part AFTER "scrivi"). If just "modalità dettatura" or "dettatura", query is empty.
- self_config: user wants to CHANGE Lily's settings. query = setting name (voce, tts, hotkey, thinking, token, storico, silenzio dettatura). parameter = new value. If user just asks the current value, parameter is empty. Keywords: "cambia", "imposta", "metti", "che voce hai", "disabilita il TTS"
- notes: user wants to save, read, or delete a QUICK NOTE. DEFAULT is SAVING a note: parameter = "" and query = the note text. ONLY use parameter = "leggi" when user explicitly asks to READ/LIST notes — put the FILTER in query: "prima" (first), "ultima" (last), "ultime 3" (last N), "oggi"/"ieri" (by date), "20 marzo" (specific date), or a keyword to search (e.g. "latte"). Leave query empty to read all. ONLY use parameter = "cancella" when user explicitly asks to DELETE (query = search text). ONLY use parameter = "svuota" when user says "cancella TUTTE le note". Keywords for saving: "prendi nota", "annota", "ricordati", "segna", "scrivi che", "nota che". Keywords for reading: "leggi le note", "le mie note", "quali note ho"
- system_info: user wants to know about system resources. query = what to check: "cpu", "ram"/"memoria", "disco"/"spazio", "processi"/"pesanti". If no specific query, returns full overview. Keywords: "quanta RAM", "uso CPU", "spazio disco", "processi pesanti", "che processi pesano", "stato del sistema", "risorse", "memoria usata"
- copy_log: user wants to COPY the log/output of the last command to clipboard. Keywords: "copia l'ultimo log", "copia il log", "copiami il log", "copia l'output", "ultimo log"
- save_memory: user wants to SAVE something to Lily's persistent memory, or READ/FORGET/CLEAR preferences. parameter="save_last" when user says "mettilo in memoria", "salvalo in memoria", "ricorda questo percorso", "è quello giusto salvalo". parameter="leggi" when user asks "cosa ricordi?", "la tua memoria", "che preferenze hai". parameter="dimentica" + query=what to forget when user says "dimentica X", "rimuovi X dalla memoria". parameter="svuota" when user says "svuota la memoria", "cancella tutta la memoria". For free text: query=the text to remember, parameter="". Keywords: "mettilo in memoria", "salvalo", "ricorda questo", "è quello giusto", "cosa ricordi", "dimentica", "svuota la memoria"
- chain: CRITICAL — if the user's sentence contains 2 or more DIFFERENT actions (e.g. "ripristina X e spostalo", "apri X e cerca Y", "chiudi X e apri Y"), you MUST use chain. Look for connectors: "e", "poi", "dopo", "quindi". query = full original text. Do NOT pick only the first action and ignore the rest!
- chat: user is asking a QUESTION, wants information, making conversation, or asking something that doesn't fit other intents. Keywords: "cos'è", "chi è", "perché", "come funziona", "dimmi", "racconta", "dove stanno", "dove si trovano", "come faccio". Use this for questions like "dove sono i salvataggi di X?" or "come si installa Y?"
- unknown: ONLY for completely unintelligible or empty input. If the input is a question or conversation, use "chat" instead

IMPORTANT:
- "query" = the CORRECTED real name, NOT the raw transcription. Fix typos and transcription errors!
- "search_terms" = multiple alternative real names, abbreviations, exe names. Include variations to maximize search success.
- For search_files: search_terms = variations of the FILENAME the user mentioned (with/without extension, with/without spaces). Do NOT add the name of applications that open that file type. Example: "cerca tappetini.psd" -> search_terms=["tappetini.psd","tappetini"] NOT ["Photoshop tappetini"]. The .psd extension already helps the search, adding "Photoshop" pollutes results.
- "apri X" where X is a program = open_program. "chiudi X" = close_program. open_folder ONLY with "cartella/directory/folder".
- For open_folder: query = the MAIN SUBJECT name only (e.g. "Lethal Company", not "video Lethal Company"). The system will search for all folders matching the name and pick the best one based on context.
- parameter defaults to "" if not needed. search_terms defaults to [] if not needed.

Examples:
- "apri Eldering" -> {"intent": "open_program", "query": "Elden Ring", "search_terms": ["Elden Ring", "ELDEN RING", "eldenring"], "parameter": ""}
- "apri Foto Shop" -> {"intent": "open_program", "query": "Photoshop", "search_terms": ["Adobe Photoshop", "Photoshop", "photoshop.exe"], "parameter": ""}
- "chiudi Discord" -> {"intent": "close_program", "query": "Discord", "search_terms": ["Discord", "discord.exe"], "parameter": ""}
- "apri la cartella video di Elden Ring" -> {"intent": "open_folder", "query": "Elden Ring", "search_terms": ["Elden Ring", "ELDEN RING"], "parameter": ""}
- "apri la cartella documenti" -> {"intent": "open_folder", "query": "Documenti", "search_terms": ["Documents", "Documenti"], "parameter": ""}
- "fai uno screenshot" -> {"intent": "screenshot", "query": "", "search_terms": [], "parameter": ""}
- "metti un timer di 5 minuti" -> {"intent": "timer", "query": "", "search_terms": [], "parameter": "5m"}
- "ricordami tra 30 minuti di controllare il forno" -> {"intent": "timer", "query": "controllare il forno", "search_terms": [], "parameter": "30m"}
- "ogni ora ricordami di bere" -> {"intent": "timer", "query": "bere", "search_terms": [], "parameter": "recurring 1h"}
- "ogni 2 ore ricordami di fare una pausa" -> {"intent": "timer", "query": "fare una pausa", "search_terms": [], "parameter": "recurring 2h"}
- "quanta RAM sto usando?" -> {"intent": "system_info", "query": "ram", "search_terms": [], "parameter": ""}
- "che processi pesano?" -> {"intent": "system_info", "query": "processi pesanti", "search_terms": [], "parameter": ""}
- "uso della CPU" -> {"intent": "system_info", "query": "cpu", "search_terms": [], "parameter": ""}
- "quanto spazio ho sul disco?" -> {"intent": "system_info", "query": "disco", "search_terms": [], "parameter": ""}
- "stato del sistema" -> {"intent": "system_info", "query": "", "search_terms": [], "parameter": ""}
- "leggimi il contenuto del file bananefunghi" -> {"intent": "agent", "query": "leggimi il contenuto del file bananefunghi", "search_terms": [], "parameter": ""}
- "cos'è la fotosintesi?" -> {"intent": "chat", "query": "cos'è la fotosintesi?", "search_terms": [], "parameter": ""}
- "dove stanno i salvataggi di Elden Ring?" -> {"intent": "chat", "query": "dove stanno i salvataggi di Elden Ring?", "search_terms": [], "parameter": ""}
- "trovami il file banane funghi" -> {"intent": "search_files", "query": "banane funghi", "search_terms": ["banane funghi", "bananefunghi"], "parameter": ""}
- "chiudi tutte le cartelle" -> {"intent": "window", "query": "", "search_terms": [], "parameter": "close_explorer"}
- "minimizza tutto" -> {"intent": "window", "query": "", "search_terms": [], "parameter": "minimize_all"}
- "sposta Discord a sinistra" -> {"intent": "window", "query": "Discord", "search_terms": [], "parameter": "snap_left"}
- "sposta Chrome sull'altro schermo" -> {"intent": "window", "query": "Chrome", "search_terms": [], "parameter": "move_monitor"}
- "sposta Discord sullo schermo 1" -> {"intent": "window", "query": "Discord", "search_terms": [], "parameter": "move_monitor 1"}
- "sposta Discord sul primo schermo" -> {"intent": "window", "query": "Discord", "search_terms": [], "parameter": "move_monitor 1"}
- "metti Chrome sul secondo monitor" -> {"intent": "window", "query": "Chrome", "search_terms": [], "parameter": "move_monitor 2"}
- "ripristina Discord" -> {"intent": "window", "query": "Discord", "search_terms": [], "parameter": "restore"}
- "sposta Discord più in basso" -> {"intent": "window", "query": "Discord", "search_terms": [], "parameter": "nudge_down"}
- "leggimi l'ultimo messaggio su WhatsApp" -> {"intent": "screen_read", "query": "WhatsApp", "search_terms": [], "parameter": "ultimo messaggio"}
- "cosa c'è scritto su Discord" -> {"intent": "screen_read", "query": "Discord", "search_terms": [], "parameter": ""}
- "leggi il terminale" -> {"intent": "terminal_read", "query": "", "search_terms": [], "parameter": ""}
- "cosa c'è sul terminale" -> {"intent": "terminal_read", "query": "", "search_terms": [], "parameter": ""}
- "cosa dice il terminale, ci sono errori?" -> {"intent": "terminal_read", "query": "", "search_terms": [], "parameter": "errori"}
- "scrivi sul terminale ciao" -> {"intent": "terminal_write", "query": "", "search_terms": [], "parameter": "ciao"}
- "invia sul terminale ok diciamo quindi" -> {"intent": "terminal_write", "query": "", "search_terms": [], "parameter": "ok diciamo quindi"}
- "scrivi sul terminale si hai ragione funziona. Allora dobbiamo aggiungere un tasto" -> {"intent": "terminal_write", "query": "", "search_terms": [], "parameter": "si hai ragione funziona. Allora dobbiamo aggiungere un tasto"}
- "vai sul terminale e scrivi ciao e invia" -> {"intent": "terminal_write", "query": "", "search_terms": [], "parameter": "ciao"}
- "vai su Sublime" -> {"intent": "type_in", "query": "Sublime", "search_terms": [], "parameter": ""}
- "invia a WhatsApp questo messaggio è da Lily" -> {"intent": "type_in", "query": "WhatsApp", "search_terms": [], "parameter": "questo messaggio è da Lily e invia"}
- "invia su WhatsApp" -> {"intent": "type_in", "query": "WhatsApp", "search_terms": [], "parameter": "dictate"}
- "invia Claude Code leggi il progetto" -> {"intent": "type_in", "query": "Claude Code", "search_terms": [], "parameter": "leggi il progetto e invia"}
- "invia Discord ciao come stai" -> {"intent": "type_in", "query": "Discord", "search_terms": [], "parameter": "ciao come stai e invia"}
- "metti pausa" -> {"intent": "media", "query": "", "search_terms": [], "parameter": "play_pause"}
- "prossima canzone" -> {"intent": "media", "query": "", "search_terms": [], "parameter": "next"}
- "modalità dettatura" -> {"intent": "dictation", "query": "", "search_terms": [], "parameter": ""}
- "scrivi ciao come stai" -> {"intent": "dictation", "query": "ciao come stai", "search_terms": [], "parameter": ""}
- "cambia voce a Diego" -> {"intent": "self_config", "query": "voce", "search_terms": [], "parameter": "Diego"}
- "che voce hai?" -> {"intent": "self_config", "query": "voce", "search_terms": [], "parameter": ""}
- "prendi nota comprare il latte" -> {"intent": "notes", "query": "comprare il latte", "search_terms": [], "parameter": ""}
- "ricordati che devo comprare il latte" -> {"intent": "notes", "query": "devo comprare il latte", "search_terms": [], "parameter": ""}
- "leggi le mie note" -> {"intent": "notes", "query": "", "search_terms": [], "parameter": "leggi"}
- "hai note sul latte?" -> {"intent": "notes", "query": "latte", "search_terms": [], "parameter": "leggi"}
- "cancella la nota del latte" -> {"intent": "notes", "query": "latte", "search_terms": [], "parameter": "cancella"}
- "copia l'ultimo log" -> {"intent": "copy_log", "query": "", "search_terms": [], "parameter": ""}""" + _LILY_PATHS


def _classify_cloud() -> str:
    return """Classify Italian voice input into intent JSON. Fix speech-to-text errors to REAL names.
Whisper errors: Eldering=Elden Ring, Lysol Company=Lethal Company, Fottosciop=Photoshop, Vi Es Code=VS Code, Cloud Code=Claude Code.

CRITICAL: You are a CLASSIFIER. NEVER answer questions. ALWAYS reply with ONLY a JSON object. The chat system handles answering.
Reply ONLY JSON: {"intent":"TYPE","query":"CORRECTED_NAME","search_terms":["alt1"],"parameter":"PARAM"}

Intents (query/parameter defaults to "" if unused, search_terms defaults to []):
open_program: launch app/game (apri/avvia/lancia)
close_program: close/quit (chiudi/termina/esci da)
open_folder: ONLY with cartella/directory keyword. query=main subject only
open_website: open site or search. "cerca su Google X"->query=search terms NOT google.com
search_files: find file by name. search_terms=filename variations ONLY, not apps that open that filetype
screenshot: capture screen
timer: parameter=duration(5m/1h/30s)/"cancel"/"lista". Reminders: query=message,parameter=duration. Recurring: parameter="recurring DURATION"
volume: parameter=up/down/mute
media: parameter=play_pause/next/previous/stop
window: parameter=close_explorer/minimize_all/show_desktop/snap_left/snap_right/move_monitor/move_monitor N(specific monitor)/minimize/restore/close_all/nudge_up/nudge_down/nudge_left/nudge_right(append pixels). query=program name when needed. "schermo 1"/"primo schermo"->move_monitor 1
screen_read: OCR window. query=window, parameter=what to look for
terminal_read: read Lily's integrated terminal output. parameter=what to look for (optional). Keywords: "leggi il terminale", "cosa c'è sul terminale", "output del terminale"
terminal_write: write/send text in Lily's integrated terminal. parameter=ALL text after trigger VERBATIM, copy ENTIRE message, do NOT cut/filter. NEVER append "e invia". Keywords: "scrivi sul terminale", "invia sul terminale". ALWAYS use this when user says "terminale" + write, NEVER type_in.
type_in: go to EXTERNAL window+type. query=window, parameter=text VERBATIM. "invia" anywhere->append " e invia" at END. No text after app->parameter="dictate". NEVER use with query="terminale".
time: current time/date
dictation: voice typing. "scrivi [TEXT]"->query=TEXT
self_config: change settings. query=setting(voce/tts/hotkey/thinking/token/storico), parameter=new value
notes: DEFAULT=save(query=note text). parameter="leggi" to read. parameter="cancella" to delete. parameter="svuota" to clear all
system_info: query=cpu/ram/disco/processi
copy_log: copy last output to clipboard
save_memory: persistent memory. parameter="save_last"(mettilo in memoria/salvalo), "leggi"(cosa ricordi?), "dimentica"+query(dimentica X), "svuota"(svuota la memoria). Free text: query=text
agent: needs reasoning, multi-step logic, system exploration, or no direct intent fits (quante cartelle, confronta, analizza, cerca e poi fai, 2+ different actions). query=full text
chat: questions, conversation, anything else
unknown: unintelligible/empty input only

Examples:
"apri Eldering"->{"intent":"open_program","query":"Elden Ring","search_terms":["Elden Ring","eldenring"]}
"chiudi Discord"->{"intent":"close_program","query":"Discord","search_terms":["Discord","discord.exe"]}
"apri la cartella video di Elden Ring"->{"intent":"open_folder","query":"Elden Ring","search_terms":["Elden Ring"]}
"cerca su Google come installare mod"->{"intent":"open_website","query":"come installare mod"}
"metti pausa"->{"intent":"media","parameter":"play_pause"}
"sposta Discord a sinistra"->{"intent":"window","query":"Discord","parameter":"snap_left"}
"sposta Discord sullo schermo 1"->{"intent":"window","query":"Discord","parameter":"move_monitor 1"}
"metti Chrome sul secondo monitor"->{"intent":"window","query":"Chrome","parameter":"move_monitor 2"}
"leggimi il contenuto del file bananefunghi"->{"intent":"agent","query":"leggimi il contenuto del file bananefunghi"}
"leggimi l'ultimo messaggio su WhatsApp"->{"intent":"screen_read","query":"WhatsApp","parameter":"ultimo messaggio"}
"scrivi sul terminale ciao"->{"intent":"terminal_write","parameter":"ciao"}
"invia sul terminale ok diciamo quindi"->{"intent":"terminal_write","parameter":"ok diciamo quindi"}
"invia su WhatsApp"->{"intent":"type_in","query":"WhatsApp","parameter":"dictate"}
"cos'è la fotosintesi?"->{"intent":"chat","query":"cos'è la fotosintesi?"}
"ricordami tra 30m di controllare il forno"->{"intent":"timer","query":"controllare il forno","parameter":"30m"}
"ogni ora ricordami di bere"->{"intent":"timer","query":"bere","parameter":"recurring 1h"}
"quanta RAM sto usando?"->{"intent":"system_info","query":"ram"}
"prendi nota comprare il latte"->{"intent":"notes","query":"comprare il latte"}
"leggi le mie note"->{"intent":"notes","parameter":"leggi"}
"quante cartelle ho sul desktop?"->{"intent":"agent","query":"quante cartelle ho sul desktop?"}
"apri Chrome e cerca lofi music"->{"intent":"agent","query":"apri Chrome e cerca lofi music"}
"chiudi tutto e apri Discord"->{"intent":"agent","query":"chiudi tutto e apri Discord"}""" + _LILY_PATHS


def _pick_ollama() -> str:
    return """The user said: "{user_query}"
The classified intent was: {intent_type}, looking for: "{intent_query}"

Here are the search results (file/folder paths):
{results}

Pick the BEST matching result. Consider the FULL user request, not just the query name.
Each result may include metadata: [file count, types, size, last modified]. Use this to decide.
For example, if user asked for "cartella video di X", prefer the folder containing mp4 files over an empty folder.

Reply JSON: {{"pick": INDEX, "confident": true/false}}
INDEX = 0-based best result, -1 if none match. confident = true if you're sure, false if ambiguous.

PRIORITY RULES:
1. Start Menu .lnk = BEST for programs. Desktop .lnk = second. Main .exe = fallback
2. Context match: path + metadata matching user's request (video, documenti, etc.)
3. AVOID: uninstallers, debug tools, artbooks, soundtracks, DLC, updaters, crash reporters
4. RESPECT exclusions: "non su D:" = exclude D: drive. Return -1 if all excluded
5. Empty folders are less likely to be what the user wants than folders with content"""


def _pick_cloud() -> str:
    return """User said: "{user_query}"
Intent: {intent_type}, query: "{intent_query}"
Results:
{results}
Pick BEST match. Results include metadata [file count, types, size, date]. Use it to decide.
Reply JSON: {{"pick": INDEX, "confident": true/false}} (0-based, -1 if none match)
confident=true if sure, false if ambiguous.

Priority: Start Menu .lnk > Desktop .lnk > .exe > context+metadata match (prefer folders with relevant content over empty ones)
Avoid: uninstallers, debug tools, artbooks, soundtracks, DLC, updaters. Respect exclusions ("non su D:")."""


def _retry_prompt() -> str:
    return """I searched for "{query}" with terms {search_terms} but found NOTHING on the user's PC.
The user said: "{user_query}"

The name might be wrong due to speech-to-text errors. Suggest alternative search terms.
Reply with ONLY a JSON object:
{{"search_terms": ["term1", "term2", "term3"]}}

Think about:
- The version WITHOUT spaces (e.g. "Animus Template" -> "AnimusTemplate")
- The version WITH spaces if original had none
- Common misspellings or misheard versions of the name
- The actual real name of the program/game/folder
- Shorter or partial versions of the name"""


def _chain_prompt() -> str:
    return """The user wants to perform MULTIPLE actions in sequence. Decompose their request into a list of individual intents.
Reply with ONLY a JSON array of intent objects:
[{{"intent":"TYPE","query":"...","search_terms":[...],"parameter":"..."}}, ...]

Available intents: open_program, close_program, open_folder, open_website, search_files, screenshot, timer, volume, media, window, screen_read, type_in, terminal_read, terminal_write, time, notes, system_info.

Rules:
- Each step is an independent action that Lily can execute
- Fix transcription errors in names (Eldering=Elden Ring, Cloud Code=Claude Code, etc.)
- For type_in: parameter=text VERBATIM. Append " e invia" if user wants to send
- For window: use correct parameter (snap_left, move_monitor, minimize, etc.)
- Add a short "wait" between steps if needed: {{"intent":"wait","parameter":"1"}} (seconds)
- Order matters: execute from first to last

Examples:
- "Apri Chrome, vai su YouTube e cerca lofi music" -> [
    {{"intent":"open_program","query":"Chrome","search_terms":["Google Chrome","chrome.exe"],"parameter":""}},
    {{"intent":"wait","parameter":"2"}},
    {{"intent":"open_website","query":"youtube.com","search_terms":[],"parameter":""}},
    {{"intent":"wait","parameter":"1"}},
    {{"intent":"type_in","query":"YouTube","search_terms":[],"parameter":"lofi music e invia"}}
  ]
- "Chiudi tutto e apri Discord" -> [
    {{"intent":"window","query":"","search_terms":[],"parameter":"close_all"}},
    {{"intent":"wait","parameter":"1"}},
    {{"intent":"open_program","query":"Discord","search_terms":["Discord","discord.exe"],"parameter":""}}
  ]"""


def _chat_system() -> str:
    return """Sei Lily, un'assistente vocale italiana. Rispondi in modo naturale, conciso e amichevole.

REGOLE IMPORTANTI:
- Rispondi SEMPRE in italiano
- Sii concisa: le tue risposte verranno lette ad alta voce, quindi evita testi troppo lunghi
- Massimo 2-3 frasi per risposta, a meno che l'utente non chieda spiegazioni dettagliate
- Hai personalità: sei simpatica, disponibile e un po' spiritosa
- Se non sai qualcosa, dillo onestamente
- Non usare markdown, emoji o formattazione speciale (il testo viene letto dal TTS)
- Non usare elenchi puntati o numerati, usa frasi discorsive

COMANDI DISPONIBILI (se l'utente chiede cosa puoi fare, elencali in modo discorsivo):
- Aprire programmi e giochi: "apri Discord", "avvia Photoshop"
- Chiudere programmi: "chiudi Chrome" (chiede conferma prima)
- Aprire cartelle: "apri la cartella video di Elden Ring"
- Cercare file: "trovami il file animus template"
- Aprire siti web: "apri YouTube", "cerca su Google qualcosa"
- Screenshot: "fai uno screenshot"
- Timer e promemoria: "metti un timer di 5 minuti", "ricordami tra 30 minuti di controllare il forno", "ogni ora ricordami di bere"
- Volume: "alza il volume", "muta"
- Controllo musica: "metti pausa", "prossima canzone", "canzone precedente"
- Gestione finestre: "chiudi tutte le cartelle", "minimizza tutto", "mostra il desktop", "sposta Discord a sinistra"
- Scrivere su finestre: "vai sul terminale e scrivi ciao e invia", "vai su Discord e scrivi ok perfetto"
- Leggere lo schermo: "leggimi l'ultimo messaggio su WhatsApp", "cosa c'è scritto su Discord", "cosa vedi sul terminale"
- Ora e data: "che ora è?"
- Modalità dettatura: "modalità dettatura" (trascrive e digita al cursore)
- Note vocali: "prendi nota: comprare il latte", "leggi le mie note", "cancella la nota del latte". Le note sono salvate in modo permanente nel file %APPDATA%/AmMstools/Lily/settings/notes.json
- Stato del sistema: "quanta RAM sto usando?", "che processi pesano?", "uso CPU", "spazio disco"
- Copiare l'ultimo log: "copia l'ultimo log" — copia nella clipboard tutto l'output dell'ultimo comando eseguito
- Conversazione: puoi fare domande su qualsiasi cosa"""


def _terminal_read_prompt(terminal_text="", user_request="", **_) -> str:
    return f"""Sei Lily, un'assistente vocale. L'utente ti ha chiesto di leggere il terminale integrato.
Ecco l'output recente del terminale:

---
{terminal_text}
---

{user_request}

Rispondi in italiano in modo conciso e naturale. Se l'utente ha chiesto qualcosa di specifico (es. "ci sono errori?"), rispondi solo a quello. Se non c'è richiesta specifica, fai un riassunto breve dell'output visibile."""


def _screen_read_prompt() -> str:
    return """Sei Lily, un'assistente vocale. L'utente ti ha chiesto di leggere una finestra.
Ecco il testo estratto dalla finestra "{window}" tramite OCR:

---
{ocr_text}
---

{user_request}

Rispondi in italiano in modo conciso e naturale. Se l'utente ha chiesto qualcosa di specifico (es. "ultimo messaggio"), rispondi solo a quello. Se non c'è richiesta specifica, fai un riassunto breve del contenuto visibile."""


# ── STRINGS ──────────────────────────────────────────────────────────────────

STRINGS = {
    # ── Meta ─────────────────────────────────────────────────────────────
    "whisper_language": "it",
    "locale_name": "Italiano",

    # ── Whisper / STT ────────────────────────────────────────────────────
    "hallucination_words": [
        "sottotitoli", "qtss", "amara.org", "sottotitolato",
        "revisione", "traduzione", "trascrizione", "applausi",
    ],
    "whisper_initial_prompt_base": (
        "Apri, avvia, cerca, chiudi, cartella, volume, sito web, "
        "programma, gioco, screenshot, timer, scrivi, invia, "
        "modalità dettatura, sposta, minimizza, riavviati, stop."
    ),
    "whisper_initial_prompt_extended": (
        "Apri, avvia, cerca, chiudi, cartella, volume, sito web, "
        "programma, gioco, screenshot, timer, scrivi, invia, "
        "modalità dettatura, sposta, minimizza, riavviati, stop. "
        "Elden Ring, Lethal Company, Minecraft, Fortnite, Valorant, "
        "Discord, Photoshop, Premiere Pro, Visual Studio Code, Blender, "
        "Steam, Spotify, Chrome, Firefox, OBS, Claude, Claude Code, "
        "Haiku, WhatsApp, Lily."
    ),

    # ── Prompts (callable) ───────────────────────────────────────────────
    "classify_ollama": _classify_ollama,
    "classify_cloud": _classify_cloud,
    "pick_ollama": _pick_ollama,
    "pick_cloud": _pick_cloud,
    "retry_prompt": _retry_prompt,
    "chain_prompt": _chain_prompt,
    "chat_system": _chat_system,
    "screen_read_prompt": _screen_read_prompt,
    "terminal_read_prompt": _terminal_read_prompt,

    # ── Confirmation keywords ────────────────────────────────────────────
    "yes_keywords": {
        "sì", "si", "ok", "vai", "fallo", "certo", "procedi", "confermo",
        "esatto", "certamente", "ovvio", "ovviamente", "assolutamente",
        "sì chiudi", "sì fallo", "ok vai", "yes",
    },
    "no_keywords": {
        "no", "annulla", "stop", "lascia stare", "non farlo", "aspetta",
        "fermati", "niente", "lascia", "no grazie", "nope", "non voglio",
    },

    # ── Confirmation messages ────────────────────────────────────────────
    "confirm_close_query": "Vuoi che chiuda {query}?",
    "confirm_close_generic": "Vuoi che chiuda il programma?",
    "confirm_close_all_windows": "Vuoi che chiuda tutte le finestre?",
    "confirm_close_all_folders": "Vuoi che chiuda tutte le cartelle aperte?",
    "confirm_delete_all_notes": "Vuoi cancellare tutte le note?",
    "confirm_generic": "Confermi l'azione?",

    # ── Stop / Restart words ─────────────────────────────────────────────
    "stop_words": {"stop", "lily stop", "fermati", "basta", "zitto", "zitta", "taci"},
    "restart_words": {"riavviati", "lily riavviati", "restart", "riavvia lily", "riavvio", "sparati", "lily sparati", "reboot", "lily reboot"},

    # ── Dictation keywords ───────────────────────────────────────────────
    "dictation_keywords": {"dettatura", "dittatura", "dettaura", "detta tura"},
    "dictation_phrases": {"inizia a dettare", "scrivi quello che dico", "dettami"},
    "dictation_prefixes": [
        "scrivi su ", "scrivi nel ", "scrivi sul ",
        "scrivi in ", "scrivi nella ", "scrivi a ", "scrivi al ",
    ],

    # ── TTS voices ───────────────────────────────────────────────────────
    "tts_edge_voices": {
        "Isabella": "it-IT-IsabellaNeural",
        "Diego": "it-IT-DiegoNeural",
        "Elsa": "it-IT-ElsaNeural",
    },
    "tts_piper_voices": {
        "Paola": ("it_IT-paola-medium", "it_IT-paola-medium.onnx"),
    },
    "tts_default_voice": "Isabella",

    # ── Hotkey aliases ───────────────────────────────────────────────────
    "hotkey_aliases": {
        "caps lock": {"caps lock", "bloc maius", "capslock", "capital"},
    },

    # ── Self-config aliases ──────────────────────────────────────────────
    "setting_aliases": {
        "voce": "tts_voice", "tts": "tts_enabled",
        "tasto": "hotkey", "hotkey": "hotkey",
        "ragionamento": "thinking_enabled", "thinking": "thinking_enabled",
        "token": "num_predict", "num predict": "num_predict",
        "lunghezza risposta": "num_predict", "risposta comandi": "num_predict",
        "risposta chat": "chat_num_predict",
        "storico": "chat_max_history", "cronologia": "chat_max_history",
        "silenzio dettatura": "dictation_silence_duration",
        "timeout dettatura": "dictation_silence_timeout",
        "overlay": "overlay_enabled",
    },
    "value_aliases_true": {"sì", "si", "attiva", "abilita", "on", "vero", "true", "yes"},
    "value_aliases_false": {"no", "disattiva", "disabilita", "off", "falso", "false"},

    # ── Notes parameters ─────────────────────────────────────────────────
    "notes_param_read": "leggi",
    "notes_param_delete": "cancella",
    "notes_param_clear": "svuota",

    # ── Notes date/time ──────────────────────────────────────────────────
    "months": [
        "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
    ],
    "today": "oggi",
    "yesterday": "ieri",
    "note_today_prefix": "di oggi",
    "note_yesterday_prefix": "di ieri",
    "note_first_keywords": {"prima", "la prima", "più vecchia"},
    "note_last_keywords": {"ultima", "l'ultima", "più recente"},
    "note_time_today": "oggi alle {time}",
    "note_time_yesterday": "ieri alle {time}",
    "note_time_other": "il {date} alle {time}",

    # ── System info keywords ─────────────────────────────────────────────
    "sysinfo_heavy_keywords": ["pesant", "pesano"],
    "sysinfo_disk_keywords": ["disco", "spazio"],
    "sysinfo_ram_keywords": ["ram", "memoria"],

    # ── Action responses: program ────────────────────────────────────────
    "program_none_specified": "Nessun programma specificato.",
    "program_not_found": "Nessun programma trovato per '{query}'.",
    "program_found_no_match": "Trovati programmi ma nessuno corrisponde a '{query}'.",
    "program_access_denied": "Non riesco ad aprire {query}, accesso negato.",
    "program_launched": "Avvio {name}.",

    # ── Action responses: close_program ──────────────────────────────────
    "close_none_specified": "Nessun programma specificato.",
    "close_not_found": "Nessun processo trovato per {query}.",
    "close_found_no_match": "Trovati processi ma nessuno corrisponde a {query}.",
    "close_success": "Chiuso {name}.",
    "close_forced": "Chiuso {name} forzatamente.",
    "close_error": "Errore nella chiusura di {target}: {e}",

    # ── Action responses: folder ─────────────────────────────────────────
    "folder_opened_direct": "Aperta cartella {name}.",
    "folder_none_specified": "Nessun nome cartella specificato.",
    "folder_not_found": "Nessuna cartella trovata per '{query}'.",
    "folder_found_no_match": "Trovate cartelle ma nessuna corrisponde a '{query}'.",
    "folder_opened": "Aperta cartella {name}.",

    # ── Pick overlay ────────────────────────────────────────────────────
    "pick_ask": "Ho trovato {count} risultati, quale preferisci?",
    "pick_timeout": "Non hai scelto, annullo.",
    "pick_cancelled": "Ok, annullato.",
    "pick_cancelled_action": "Azione annullata.",
    "pick_not_understood": "Non ho capito, prova a cliccare.",
    "pick_no_audio": "Non ho sentito, riprova.",

    # ── Memory ───────────────────────────────────────────────────────
    "memory_empty": "La mia memoria è vuota, non ho preferenze salvate.",
    "memory_content": "Ecco cosa ricordo:\n{content}",
    "memory_saved": "Salvato in memoria: {entry}",
    "memory_forgotten": "Rimosso dalla memoria tutto ciò che riguarda '{query}'.",
    "memory_not_found": "Non ho trovato nulla su '{query}' nella mia memoria.",
    "memory_no_context": "Non ho un'azione recente da salvare. Prima fammi fare qualcosa, poi dimmi di ricordarlo.",
    "memory_no_query": "Cosa vuoi che ricordi?",
    "memory_forget_no_query": "Cosa vuoi che dimentichi?",
    "memory_cleared": "Memoria svuotata.",

    # ── Action responses: website ────────────────────────────────────────
    "website_none_specified": "Nessun sito specificato.",
    "website_searched": "Cercato {query}.",
    "website_opened": "Aperto {domain}.",

    # ── Action responses: screenshot ─────────────────────────────────────
    "screenshot_no_screen": "Nessuno schermo trovato.",
    "screenshot_saved": "Screenshot salvato in {path}",
    "screenshot_error": "Errore screenshot: {e}",
    "screenshot_window_not_found": "Finestra '{query}' non trovata.",
    "screenshot_capture_error": "Errore nella cattura della finestra '{query}'.",

    # ── Action responses: type_action ────────────────────────────────────
    "type_no_window": "Non hai specificato su quale finestra andare.",
    "type_window_not_found": "Non trovo la finestra {query}.",
    "type_focused": "Sono su {name}.",
    "type_sent": "Scritto e inviato su {name}.",
    "type_written": "Scritto su {name}.",

    # ── Action responses: volume ─────────────────────────────────────────
    "volume_level": "Volume: {level}%",
    "volume_unmuted": "Audio riattivato.",
    "volume_muted": "Audio mutato.",
    "volume_unknown_param": "Parametro volume non riconosciuto: '{parameter}'",
    "volume_error": "Errore controllo volume: {e}",

    # ── Action responses: media ──────────────────────────────────────────
    "media_play_pause": "Play o pausa.",
    "media_next": "Traccia successiva.",
    "media_previous": "Traccia precedente.",
    "media_stop": "Riproduzione fermata.",
    "media_unknown": "Comando multimediale non riconosciuto.",

    # ── Action responses: screen_read ────────────────────────────────────
    "screen_read_no_window": "Non hai specificato quale finestra leggere.",
    "screen_read_window_not_found": "Non trovo la finestra {query}.",
    "screen_read_capture_error": "Errore nella cattura dello schermo.",
    "screen_read_ocr_empty": "Non riesco a leggere il testo sulla finestra {query}.",
    "screen_read_llm_error": "Ho letto il testo ma non riesco a rispondere.",

    # ── Action responses: terminal_read ───────────────────────────────
    "terminal_watch_no_tab": "Nessun tab terminale disponibile.",
    "terminal_watch_started": "Monitoring attivato su {tab}. Ti avviso se chiede conferma o finisce.",
    "terminal_watch_stopped": "Monitoring disattivato su {tab}.",
    "watcher_confirm": "{tab} chiede conferma.",
    "watcher_done": "{tab} ha finito.",
    "watcher_error": "{tab} ha un errore.",
    "terminal_write_empty": "Nessun testo da scrivere nel terminale.",
    "terminal_write_no_session": "Nessuna sessione terminale attiva.",
    "terminal_write_ok": "Scritto nel terminale {tab}.",
    "terminal_read_empty": "Il terminale è vuoto, non c'è nessun output da leggere.",
    "terminal_read_empty_with_tabs": "Questo tab è vuoto. Tab disponibili: {tabs}.",
    "terminal_read_llm_error": "Ho letto l'output del terminale ma non riesco a formulare una risposta.",

    # ── Action responses: timer ──────────────────────────────────────────
    "timer_invalid_duration": "Durata timer non valida: '{parameter}'",
    "timer_reminder_fire": "Promemoria: {label}",
    "timer_fire": "Timer scaduto: {duration}",
    "timer_reminder_set": "Ok, ti ricorderò tra {duration}: {label}.",
    "timer_set": "Timer impostato: {duration}.",
    "timer_recurring_reminder_fire": "Promemoria ricorrente: {label}",
    "timer_recurring_fire": "Timer ricorrente: {duration}",
    "timer_recurring_set": "Ok, ti ricorderò ogni {duration}: {label}.",
    "timer_none_active": "Nessun timer attivo.",
    "timer_removed_many": "Rimossi {count} timer.",
    "timer_removed_one": "Timer rimosso.",
    "timer_count_single": "{count} timer",
    "timer_count_recurring": "{count} ricorrenti",
    "timer_active_list": "Hai {parts} attivi.",

    # ── Action responses: chat ───────────────────────────────────────────
    "chat_error": "Non ho capito la domanda.",

    # ── Action responses: self_config ────────────────────────────────────
    "config_no_setting": "Non hai specificato quale impostazione cambiare.",
    "config_unknown_setting": "Non conosco l'impostazione {query}.",
    "config_readonly": "Non posso modificare {key}, è un'impostazione utente.",
    "config_current_value": "{query} è impostato a {value}.",
    "config_invalid_value": "Il valore {parameter} non è valido per {query}.",
    "config_changed": "Ho cambiato {query} da {old} a {new}.",

    # ── Action responses: system_info ────────────────────────────────────
    "sysinfo_overview": "CPU al {cpu}%, RAM {ram_used:.1f} su {ram_total:.1f} giga al {ram_pct}%, disco C {disk_free:.0f} giga liberi su {disk_total:.0f}.",
    "sysinfo_heavy_procs": "Processi più pesanti: {names}",
    "sysinfo_cpu_detail": "CPU al {cpu}% complessivo, {cores} core, picco singolo core al {max_core}%.",
    "sysinfo_cpu_procs": "Processi più attivi: {names}.",
    "sysinfo_ram_detail": "RAM al {pct}%: {used:.1f} giga usati su {total:.1f}, {available:.1f} giga disponibili.",
    "sysinfo_ram_procs": "Più pesanti: {names}.",
    "sysinfo_disk_line": "Disco {mount} {free:.0f} giga liberi su {total:.0f}, al {pct}%.",
    "sysinfo_disk_error": "Non riesco a leggere i dischi.",
    "sysinfo_proc_error": "Non riesco a leggere i processi.",
    "sysinfo_top_procs": "Top 5 processi per {label}",

    # ── Action responses: time ───────────────────────────────────────────
    "time_response": "Sono le {time} di {date}.",

    # ── Action responses: search_files ───────────────────────────────────
    "search_no_query": "Nessun termine di ricerca specificato.",
    "search_cancelled": "Ricerca annullata.",
    "search_not_found": "Nessun file trovato per '{query}'.",
    "search_found": "Trovato {name}.",
    "search_found_path": "Trovato {name} in {path}.",

    # ── Action responses: run_command ─────────────────────────────────────
    "cmd_empty": "Nessun comando specificato.",
    "cmd_blocked": "Comando bloccato per sicurezza.",
    "cmd_denied": "Comando annullato dall'utente.",
    "cmd_needs_confirm": "Il comando richiede conferma: {cmd}",
    "cmd_success_no_output": "Comando eseguito con successo.",
    "cmd_error_code": "Comando terminato con errore (codice {code}).",
    "cmd_timeout": "Comando interrotto dopo {seconds} secondi.",
    "cmd_error": "Errore nell'esecuzione: {e}",
    "cmd_confirm_ask": "Vuoi che esegua: {cmd}?",
    "cmd_confirm_short": "Questo comando modifica il sistema. Confermi?",

    # ── Action responses: window ─────────────────────────────────────────
    "window_all_minimized": "Tutto minimizzato.",
    "window_unknown_command": "Comando finestra non riconosciuto.",
    "window_no_folders": "Nessuna cartella aperta.",
    "window_folders_closed_many": "Chiuse {count} cartelle.",
    "window_folders_closed_one": "Chiusa una cartella.",
    "window_no_query": "Non hai specificato quale finestra spostare.",
    "window_not_found": "Non trovo la finestra {query}.",
    "window_snapped": "Spostato a {side}.",
    "window_snap_left": "sinistra",
    "window_snap_right": "destra",
    "window_single_monitor": "C'è un solo monitor collegato.",
    "window_moved_monitor": "Spostato sull'altro schermo.",
    "window_no_restore_query": "Non hai specificato quale finestra ripristinare.",
    "window_restored": "Ripristinato {name}.",
    "window_no_minimize_query": "Non hai specificato quale finestra minimizzare.",
    "window_minimized": "Minimizzato {query}.",
    "window_no_nudge_query": "Non hai specificato quale finestra spostare.",
    "window_nudged": "Spostato di {pixels} pixel.",
    "window_no_close_target": "Nessuna finestra da chiudere.",
    "window_closed_many": "Chiuse {count} finestre.",

    # ── Action responses: notes ──────────────────────────────────────────
    "notes_nothing_to_save": "Non ho capito cosa annotare.",
    "notes_saved": "Nota salvata: {text}",
    "notes_empty": "Non hai nessuna nota.",
    "notes_none_for_date": "Nessuna nota per {label}.",
    "notes_header_date": "Note di {label}",
    "notes_none_matching": "Nessuna nota trovata con '{query}'.",
    "notes_found_one": "Ho trovato {count} nota con '{query}'.",
    "notes_found_many": "Ho trovato {count} note con '{query}'.",
    "notes_delete_no_query": "Non ho capito quale nota cancellare.",
    "notes_delete_not_found": "Nessuna nota trovata con '{query}'.",
    "notes_deleted_one": "Nota cancellata.",
    "notes_deleted_many": "{count} note cancellate.",
    "notes_empty_to_delete": "Non hai nessuna nota da cancellare.",
    "notes_deleted_all": "Tutte le {count} note cancellate.",
    "notes_count_one": "Hai {count} nota.",
    "notes_count_many": "Hai {count} note.",
    "notes_showing_last": "Ecco le ultime {count}.",

    # ── Action responses: dictation ──────────────────────────────────────
    "dictation_activated": "Dettatura attivata.",
    "dictation_ended": "Dettatura terminata. {count} segmenti trascritti.",
    "dictation_no_audio": "Nessun audio rilevato.",
    "dictation_not_understood": "Non ho capito cosa hai detto.",
    "dictation_window_not_found": "Non trovo la finestra {query}.",
    "dictation_sent": "Inviato su {query}.",
    "dictation_speak_prompt": "Parla, invio su {target} quando hai finito.",
    "dictation_voice_only": "La dettatura funziona solo via voce.",
    "dictation_window_voice_only": "La dettatura su finestra funziona solo via voce.",

    # ── Action responses: copy_log ───────────────────────────────────────
    "copy_log_empty": "Non c'è nessun log da copiare.",
    "copy_log_done": "Log copiato nella clipboard, {count} righe.",

    # ── Assistant flow ───────────────────────────────────────────────────
    "restarting": "Mi riavvio...",
    "chain_decompose_fail": "Non sono riuscita a scomporre i comandi.",
    "chain_done": "Fatto, ho eseguito tutti i comandi.",
    "chain_wait": "Attesa {secs}s...",
    "action_cancelled": "Azione annullata.",
    "error_generic": "Errore: {e}",
    "llm_chat_fallback": "Scusa, non sono riuscita a formulare una risposta.",
    "llm_chat_error": "Mi dispiace, ho avuto un problema nel rispondere.",

    # ── Whisper / Listener ───────────────────────────────────────────────
    "whisper_not_loaded": "Modello Whisper non caricato.",
    "whisper_no_audio": "Nessun audio rilevato.",
    "whisper_no_text": "Nessun testo riconosciuto.",
    "whisper_loaded": "Modello Whisper caricato ({label}).",
    "whisper_load_error": "Errore caricamento Whisper: {e}",
    "mic_error": "Errore microfono: {e}",

    # ── UI: Voice page ───────────────────────────────────────────────────
    "state_loading": "Caricamento modello...",
    "state_idle": "Pronto",
    "state_listening": "Ascolto...",
    "state_processing": "Elaborazione...",
    "state_transcribing": "Trascrizione...",
    "gpu_info": "{name}  |  VRAM: {used}/{total} MB ({free} MB liberi)  |  GPU: {util}%",

    # ── UI: Chat page ────────────────────────────────────────────────────
    "chat_placeholder": "Scrivi un messaggio...",
    "chat_clear": "Cancella chat",
    "chat_voice_tag": "voce",
    "chat_welcome": "Chiedimi qualsiasi cosa!",
    "chat_typing": "Lily sta scrivendo...",
    "chat_context_info": "Contesto: ~{total_ctx:,} tok",
    "chat_context_system": "sistema ~{system_tok:,}",
    "chat_context_history": "storia {msg_count} msg ~{history_tok:,}",

    # ── UI: Sidebar ──────────────────────────────────────────────────────
    "sidebar_chat": "Chat",
    "sidebar_llm": "LLM",
    "sidebar_memory": "Memoria",
    "sidebar_settings": "Impostazioni",
    "sidebar_usage": "Usage",
    "sidebar_log": "Log",
    "sidebar_home": "Home",
    "sidebar_terminal": "Terminale",

    # ── UI: Settings page ────────────────────────────────────────────────
    "settings_title": "Impostazioni",
    "settings_general": "Generale",
    "settings_hotkey_suppress": "Blocca tasto hotkey",
    "settings_overlay": "Lily Overlay",
    "settings_audio": "Audio",
    "settings_whisper_model": "Modello Whisper",
    "settings_whisper_device": "Whisper Device",
    "settings_microphone": "Microfono",
    "settings_paths": "Percorsi",
    "settings_tts_enable": "Abilita Text-to-Speech",
    "settings_tts_voice": "Voce TTS",
    "settings_dictation": "Dettatura",
    "settings_dictation_silence": "Silenzio dettatura (s)",
    "settings_dictation_max": "Durata max dettatura (s)",
    "settings_dictation_timeout": "Timeout inattività (s)",
    "settings_advanced": "Avanzate",
    "settings_log_enabled": "Mostra pagina log",
    "settings_terminal_enabled": "Abilita terminale integrato",
    "settings_memory_enabled": "Mostra pagina memoria",
    "settings_wake_word_enabled": "Abilita Wake Word",
    "settings_wake_keyword": "Parola chiave",
    "settings_wake_sensitivity": "Sensibilità",
    "settings_save": "Salva",
    "settings_saved": "Salvato!",
    "settings_browse_es": "Seleziona es.exe",
    "settings_browse_tesseract": "Seleziona tesseract.exe",
    "settings_exe_filter": "Eseguibili (*.exe)",

    # ── AI Hints (tooltip per settings) ──────────────────────────────────
    "ai_hint_hotkey": "Il tasto (o combinazione) da tenere premuto\nper attivare la registrazione vocale.\nEsempi: caps lock, ctrl+shift+space, f5",
    "ai_hint_hotkey_suppress": "Se attivo, il tasto hotkey viene consumato da Lily\ne non arriva alle altre app.\nUtile se usi un tasto come F o una lettera:\nevita che venga scritto ripetutamente\nmentre tieni premuto per registrare.",
    "ai_hint_wake_word": "Attiva il riconoscimento vocale senza hotkey.\nDici la parola chiave e Lily inizia ad ascoltare.\nUsa Silero VAD + Whisper tiny in background.",
    "ai_hint_wake_keyword": "La parola che attiva Lily.\nQuando viene rilevata voce, trascrive\nun breve frammento e controlla se inizia\ncon questa parola.",
    "ai_hint_overlay": "Mostra un'icona flottante sullo schermo\nquando Lily e minimizzata.\nPermette di vedere lo stato (idle, ascolto, elaborazione)\nsenza aprire la finestra.",
    "ai_hint_whisper_model": "Modello di riconoscimento vocale.\ntiny/base = veloce ma meno preciso\nmedium = buon compromesso\nlarge-v3 = massima precisione, piu lento.\nRichiede piu VRAM per modelli grandi.",
    "ai_hint_whisper_device": "Dispositivo per il riconoscimento vocale.\ncuda = usa la GPU NVIDIA (veloce)\ncpu = usa il processore (piu lento, no GPU richiesta)",
    "ai_hint_es_path": "Percorso di Everything (es.exe).\nUsato per cercare file e cartelle\nistantaneamente su tutto il PC.\nScaricabile da voidtools.com",
    "ai_hint_tesseract_path": "Percorso di Tesseract OCR.\nUsato per leggere il testo dalle finestre\n(funzione screen_read).\nScaricabile da github.com/tesseract-ocr",
    "ai_hint_tts": "Lily parla le risposte ad alta voce.\nSe disattivato, le risposte appaiono\nsolo come testo nella chat.",
    "ai_hint_dict_silence": "Dopo quanti secondi di silenzio\nla dettatura inserisce una pausa.\nValori bassi = piu reattivo ma rischia\ndi spezzare frasi lunghe.",
    "ai_hint_dict_max": "Durata massima di una singola sessione\ndi dettatura in secondi.\nDopo questo tempo la dettatura si ferma\nautomaticamente.",
    "ai_hint_dict_timeout": "Dopo quanti secondi di silenzio totale\nla dettatura si ferma automaticamente.\nDiverso dal silenzio pausa: questo\nchiude proprio la sessione.",
    "ai_hint_log": "Mostra la pagina Log nella sidebar.\nUtile per debug: vedi tutti gli eventi,\nle chiamate LLM e le azioni eseguite.",
    "ai_hint_terminal": "Abilita un terminale PowerShell integrato\ndentro Lily. Lily puo leggere l'output,\nscrivere comandi e monitorare errori.",
    "ai_hint_memory": "Mostra la pagina Memoria nella sidebar.\nLily puo salvare preferenze e informazioni\npersistenti tra le sessioni.",

    # AI Hints — LLM page
    "ai_hint_llm_provider": "Il servizio che elabora i comandi vocali.\nollama = locale, gratuito, richiede installazione\nanthropic = Claude (cloud, a pagamento)\nopenai = GPT (cloud, a pagamento)\ngemini = Google (cloud, a pagamento)",
    "ai_hint_llm_ollama_model": "Il modello locale da usare con Ollama.\nModelli piu grandi = piu precisi ma piu lenti.\nDeve essere gia scaricato con 'ollama pull'.",
    "ai_hint_llm_max_results": "Quanti risultati di ricerca inviare al LLM\nquando deve scegliere il file/programma giusto.\nPiu risultati = scelta migliore ma piu token usati.\nSolo per provider cloud.",
    "ai_hint_llm_thinking": "Il modello ragiona passo dopo passo\nprima di rispondere.\nPiu lento ma piu preciso su richieste complesse.\nUsa piu token.",
    "ai_hint_llm_classify_agent": "Prima classifica il comando (veloce),\npoi se serve delega a un agente autonomo\nper richieste complesse o multi-step.\nBuon compromesso velocita/potenza.",
    "ai_hint_llm_agent": "Ogni comando va diretto all'agente autonomo\nche ragiona, usa tool e shell.\nPiu potente ma piu lento e costoso.\nMutuamente esclusivo con Classify & Agent.",
    "ai_hint_llm_num_predict": "Token massimi per le risposte ai comandi\n(classificazione, pick, azioni).\nValori bassi = risposte piu veloci.\nPer comandi semplici bastano 64-128.",
    "ai_hint_llm_chat_predict": "Token massimi per le risposte in chat.\nValori alti = risposte piu lunghe e dettagliate.\nPer conversazioni normali 256-512 va bene.",
    "ai_hint_llm_history": "Quanti scambi precedenti includere\nnel contesto della chat.\nPiu storico = conversazioni piu coerenti\nma piu token consumati per ogni richiesta.",

    # ── UI: Welcome wizard ───────────────────────────────────────────────
    "welcome_title": "Benvenuto in Lily",
    "welcome_subtitle": (
        "Assistente vocale per Windows. Controlla il tuo PC con la voce: "
        "apri programmi, cerca file, gestisci finestre, detta testo e molto altro."
    ),
    "welcome_deps": "Dipendenze opzionali",
    "welcome_detected": "Rilevato",
    "welcome_not_found": "Non trovato",
    "welcome_start": "Inizia",
    "welcome_everything_name": "Everything",
    "welcome_everything_desc": "Motore di ricerca file istantaneo per Windows. Indicizza l'intero disco in pochi secondi.",
    "welcome_everything_detail": "Lily lo usa per trovare qualsiasi programma, cartella o file sul tuo PC in millisecondi. Senza Everything la ricerca è limitata a Start Menu, Desktop e Registry.",
    "welcome_ollama_name": "Ollama",
    "welcome_ollama_desc": "Server per modelli LLM locali. Esegue modelli AI direttamente sul tuo PC senza costi.",
    "welcome_ollama_detail": "Permette a Lily di ragionare e capire i tuoi comandi usando un LLM locale (es. Qwen, Llama). Non necessario se preferisci usare API cloud (Anthropic, OpenAI, Gemini).",
    "welcome_cuda_name": "CUDA (NVIDIA)",
    "welcome_cuda_desc": "Librerie GPU NVIDIA per accelerare la trascrizione vocale con Whisper.",
    "welcome_cuda_detail": "Con CUDA la trascrizione è molto più veloce (5-10x). Se non hai una GPU NVIDIA, puoi usare Whisper su CPU dalle impostazioni (più lento ma funziona).",
    "welcome_tesseract_name": "Tesseract OCR",
    "welcome_tesseract_desc": "Motore OCR open-source per leggere testo dallo schermo.",
    "welcome_tesseract_detail": "Usato dalla funzione 'leggi schermo': Lily fa uno screenshot e Tesseract ne estrae il testo. Necessario solo se vuoi usare questa funzionalità.",

    # ── UI: Tray ─────────────────────────────────────────────────────────
    "tray_open": "Apri",
    "tray_quit": "Esci",

    # ── UI: Language / restart ───────────────────────────────────────────
    "settings_language": "Lingua",
    "lang_it": "Italiano",
    "lang_en": "English",
    "restart_required_title": "Riavvio necessario",
    "restart_required_msg": "Hai cambiato la lingua. Devi riavviare Lily per applicare le modifiche.",
    "restart_now": "Riavvia ora",
    "restart_later": "Più tardi",
}
