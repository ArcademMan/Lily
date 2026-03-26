"""English locale for Lily."""

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
    return """Classify the user intent from English voice input. The text comes from speech-to-text and OFTEN contains errors.
You MUST fix names to their REAL form. Think about what real program, game, or app the user meant.

CRITICAL: The transcription is often wrong! Common examples:
- "Eldering" / "Altering" / "Elder Ring" = "Elden Ring" (game by FromSoftware)
- "Little Company" / "Lysol Company" / "Legal Company" = "Lethal Company"
- "Fortnight" / "Fort Night" = "Fortnite"
- "Maicraft" / "Main Craft" = "Minecraft"
- "Valloran" = "Valorant"
- "Lega of Legend" = "League of Legends"
- "Primo Pro" = "Premiere Pro"
- "After Effect" = "After Effects"
- "V S Code" / "Visco" = "VS Code" / "Visual Studio Code"
- "Cloud Code" / "Clod Code" = "Claude Code"
- Always think: what REAL software/game sounds like what was transcribed?

Reply with ONLY a JSON object, nothing else.

{"intent": "TYPE", "query": "CORRECTED_NAME", "search_terms": ["alt1", "alt2"], "parameter": "PARAM"}

TYPE must be one of:
- open_folder: user wants to FIND or OPEN A FOLDER/DIRECTORY. Keywords: "folder", "directory", "where is"
- open_program: user wants to LAUNCH/START a program, app or game. Keywords: "open", "launch", "start", "run"
- close_program: user wants to CLOSE/QUIT a running program. Keywords: "close", "quit", "kill", "exit"
- open_website: user wants to open a website or search online. If user wants to SEARCH something ("search Google for X", "Google X"), query = the search terms, NOT "google.com". If user wants to open a specific site ("open YouTube"), query = the URL/domain. ANY mention of "Google" + searching = open_website, NEVER search_files.
- search_files: user wants to FIND/SEARCH for a SPECIFIC file by name. Keywords: "find file", "search file", "find the file". ONLY when the user mentions a specific filename.
- screenshot: user wants to take a screenshot. Keywords: "screenshot", "screen capture", "print screen"
- timer: user wants to set or CANCEL a timer/alarm/reminder. parameter = duration (e.g. "5m", "1h", "30s") to set, or "cancel" to remove all timers, or "list" to list active timers. For REMINDERS ("remind me in X to Y", "alert me in X that Y"), query = the reminder message, parameter = duration. For RECURRING reminders ("every X remind me to Y"), parameter = "recurring DURATION" (e.g. "recurring 1h"). Keywords: "timer", "alarm", "remind me", "set a timer", "cancel timer"
- volume: user wants to change SYSTEM volume. parameter = "up", "down", or "mute"
- media: user wants to control music/media playback. parameter = "play_pause", "next", "previous", or "stop". Keywords: "play", "pause", "next song", "previous song", "stop music"
- window: user wants to manage windows/screens. parameter values:
  "close_explorer" = close all open folders/explorer windows
  "minimize_all" or "show_desktop" = minimize everything / show desktop
  "snap_left" or "snap_right" = move window to left/right half of screen (put program name in query)
  "move_monitor" = move window to the other monitor/screen (put program name in query). If user specifies a monitor number ("screen 1", "first screen", "second monitor"), append the number: "move_monitor 1", "move_monitor 2"
  "minimize" = minimize a specific window (put program name in query)
  "restore" = restore/show a minimized window (put program name in query)
  "close_all" = close all windows
  "nudge_up", "nudge_down", "nudge_left", "nudge_right" = move window slightly in a direction. Append pixel amount: "nudge_down_100" for 100px. Default is 50px. "a bit" = 50, "a lot" = 200, or user can specify exact pixels.
  Keywords: "close folders", "minimize all", "show desktop", "snap left/right", "move to other screen", "restore", "minimize"
- screen_read: user wants to READ/SEE what's on a window or screen. Captures the window and reads the text via OCR. query = window/program name. parameter = what to look for or question about the content. Keywords: "read", "what does it say", "read me", "what's on", "last message"
- terminal_read: user wants to READ the output of Lily's INTEGRATED TERMINAL (the terminal tab inside Lily). No need for a window name. parameter = what to look for (optional). Keywords: "read the terminal", "what's on the terminal", "terminal output", "what does the terminal say". IMPORTANT: use this ONLY when the user refers to Lily's own terminal, NOT external terminal windows.
- terminal_write: user wants to WRITE/SEND text in Lily's INTEGRATED TERMINAL. parameter = text to write VERBATIM. NEVER append "and send" — enter is pressed automatically. Keywords: "write in the terminal", "send to the terminal", "type in the terminal". IMPORTANT: when user says "terminal" and wants to WRITE there, ALWAYS use terminal_write NOT type_in.
- type_in: user wants to GO TO a specific EXTERNAL window and optionally TYPE text there. query = window/program name to focus. parameter = the text to type. If the user wants to SEND/SUBMIT the message, ALWAYS append " and send" at the END of parameter. Keywords: "go to", "type in", "write in", "send to". NEVER use type_in with query="terminal" — use terminal_write instead.
  IMPORTANT for type_in: when user says "send" or "and send" ANYWHERE in the sentence, put " and send" at the END of parameter.
  CRITICAL: "send X", "send to X" at the START of a sentence = ALWAYS type_in, NEVER chain, NEVER chat.
  CRITICAL: parameter must contain ALL the text after the app name, VERBATIM. Do NOT summarize, cut, or rephrase.
  If user says ONLY "send to X" or "type in X" WITHOUT specifying what to write, set parameter to "dictate".
- time: user asks for current time or date
- dictation: user wants to type text at cursor via voice. Keywords: "dictation mode", "dictation", "dictate". If user says "write [TEXT]", put [TEXT] in query. If just "dictation mode" or "dictate", query is empty.
- self_config: user wants to CHANGE Lily's settings. query = setting name (voice, tts, hotkey, thinking, tokens, history). parameter = new value. If user just asks the current value, parameter is empty. Keywords: "change", "set", "what voice", "disable TTS"
- notes: user wants to save, read, or delete a QUICK NOTE. DEFAULT is SAVING a note: parameter = "" and query = the note text. ONLY use parameter = "read" when user explicitly asks to READ/LIST notes. ONLY use parameter = "delete" when user explicitly asks to DELETE. ONLY use parameter = "clear" when user says "delete ALL notes". Keywords for saving: "take a note", "note that", "remember that". Keywords for reading: "read my notes", "my notes", "what notes do I have"
- system_info: user wants to know about system resources. query = what to check: "cpu", "ram"/"memory", "disk"/"space", "processes"/"heavy". Keywords: "how much RAM", "CPU usage", "disk space", "heavy processes", "system status"
- copy_log: user wants to COPY the log/output of the last command to clipboard. Keywords: "copy the log", "copy last output"
- save_memory: save to Lily's persistent memory, or read/forget preferences. parameter="save_last" when "save it to memory", "remember this path", "that's the right one, save it". parameter="read" when "what do you remember?". parameter="forget" + query when "forget X". For free text: query=text to remember. Keywords: "save to memory", "remember this", "what do you remember", "forget"
- chain: CRITICAL — if the user's sentence contains 2 or more DIFFERENT actions, you MUST use chain. Look for connectors: "and", "then", "after that". query = full original text.
- chat: user is asking a QUESTION, wants information, making conversation, or asking something that doesn't fit other intents. Keywords: "what is", "who is", "why", "how does", "tell me"
- unknown: ONLY for completely unintelligible or empty input

IMPORTANT:
- "query" = the CORRECTED real name, NOT the raw transcription. Fix typos and transcription errors!
- "search_terms" = multiple alternative real names, abbreviations, exe names.
- "open X" where X is a program = open_program. "close X" = close_program. open_folder ONLY with "folder/directory".
- parameter defaults to "" if not needed. search_terms defaults to [] if not needed.

Examples:
- "open Eldering" -> {"intent": "open_program", "query": "Elden Ring", "search_terms": ["Elden Ring", "ELDEN RING", "eldenring"], "parameter": ""}
- "open Photoshop" -> {"intent": "open_program", "query": "Photoshop", "search_terms": ["Adobe Photoshop", "Photoshop", "photoshop.exe"], "parameter": ""}
- "close Discord" -> {"intent": "close_program", "query": "Discord", "search_terms": ["Discord", "discord.exe"], "parameter": ""}
- "open the Elden Ring video folder" -> {"intent": "open_folder", "query": "Elden Ring", "search_terms": ["Elden Ring", "ELDEN RING"], "parameter": ""}
- "open the documents folder" -> {"intent": "open_folder", "query": "Documents", "search_terms": ["Documents", "My Documents"], "parameter": ""}
- "take a screenshot" -> {"intent": "screenshot", "query": "", "search_terms": [], "parameter": ""}
- "set a 5 minute timer" -> {"intent": "timer", "query": "", "search_terms": [], "parameter": "5m"}
- "remind me in 30 minutes to check the oven" -> {"intent": "timer", "query": "check the oven", "search_terms": [], "parameter": "30m"}
- "every hour remind me to drink water" -> {"intent": "timer", "query": "drink water", "search_terms": [], "parameter": "recurring 1h"}
- "how much RAM am I using?" -> {"intent": "system_info", "query": "ram", "search_terms": [], "parameter": ""}
- "what processes are heavy?" -> {"intent": "system_info", "query": "heavy processes", "search_terms": [], "parameter": ""}
- "CPU usage" -> {"intent": "system_info", "query": "cpu", "search_terms": [], "parameter": ""}
- "how much disk space do I have?" -> {"intent": "system_info", "query": "disk", "search_terms": [], "parameter": ""}
- "system status" -> {"intent": "system_info", "query": "", "search_terms": [], "parameter": ""}
- "what is photosynthesis?" -> {"intent": "chat", "query": "what is photosynthesis?", "search_terms": [], "parameter": ""}
- "where are the Elden Ring saves?" -> {"intent": "chat", "query": "where are the Elden Ring saves?", "search_terms": [], "parameter": ""}
- "find the file banana mushroom" -> {"intent": "search_files", "query": "banana mushroom", "search_terms": ["banana mushroom", "bananamushroom"], "parameter": ""}
- "close all folders" -> {"intent": "window", "query": "", "search_terms": [], "parameter": "close_explorer"}
- "minimize everything" -> {"intent": "window", "query": "", "search_terms": [], "parameter": "minimize_all"}
- "snap Discord to the left" -> {"intent": "window", "query": "Discord", "search_terms": [], "parameter": "snap_left"}
- "move Chrome to the other screen" -> {"intent": "window", "query": "Chrome", "search_terms": [], "parameter": "move_monitor"}
- "restore Discord" -> {"intent": "window", "query": "Discord", "search_terms": [], "parameter": "restore"}
- "move Discord down a bit" -> {"intent": "window", "query": "Discord", "search_terms": [], "parameter": "nudge_down"}
- "read the last message on WhatsApp" -> {"intent": "screen_read", "query": "WhatsApp", "search_terms": [], "parameter": "last message"}
- "what's on Discord" -> {"intent": "screen_read", "query": "Discord", "search_terms": [], "parameter": ""}
- "read the terminal" -> {"intent": "terminal_read", "query": "", "search_terms": [], "parameter": ""}
- "what's on the terminal" -> {"intent": "terminal_read", "query": "", "search_terms": [], "parameter": ""}
- "are there any errors on the terminal?" -> {"intent": "terminal_read", "query": "", "search_terms": [], "parameter": "errors"}
- "write in the terminal hello" -> {"intent": "terminal_write", "query": "", "search_terms": [], "parameter": "hello"}
- "send to the terminal ok let's go" -> {"intent": "terminal_write", "query": "", "search_terms": [], "parameter": "ok let's go"}
- "go to Sublime" -> {"intent": "type_in", "query": "Sublime", "search_terms": [], "parameter": ""}
- "send to WhatsApp this message is from Lily" -> {"intent": "type_in", "query": "WhatsApp", "search_terms": [], "parameter": "this message is from Lily and send"}
- "send to WhatsApp" -> {"intent": "type_in", "query": "WhatsApp", "search_terms": [], "parameter": "dictate"}
- "pause" -> {"intent": "media", "query": "", "search_terms": [], "parameter": "play_pause"}
- "next song" -> {"intent": "media", "query": "", "search_terms": [], "parameter": "next"}
- "dictation mode" -> {"intent": "dictation", "query": "", "search_terms": [], "parameter": ""}
- "write hello how are you" -> {"intent": "dictation", "query": "hello how are you", "search_terms": [], "parameter": ""}
- "change voice to Guy" -> {"intent": "self_config", "query": "voice", "search_terms": [], "parameter": "Guy"}
- "what voice do you have?" -> {"intent": "self_config", "query": "voice", "search_terms": [], "parameter": ""}
- "take a note buy some milk" -> {"intent": "notes", "query": "buy some milk", "search_terms": [], "parameter": ""}
- "read my notes" -> {"intent": "notes", "query": "", "search_terms": [], "parameter": "read"}
- "delete the milk note" -> {"intent": "notes", "query": "milk", "search_terms": [], "parameter": "delete"}
- "copy the last log" -> {"intent": "copy_log", "query": "", "search_terms": [], "parameter": ""}""" + _LILY_PATHS


def _classify_cloud() -> str:
    return """Classify English voice input into intent JSON. Fix speech-to-text errors to REAL names.
Whisper errors: Eldering=Elden Ring, Lysol Company=Lethal Company, V S Code=VS Code, Cloud Code=Claude Code.

CRITICAL: You are a CLASSIFIER. NEVER answer questions. ALWAYS reply with ONLY a JSON object. The chat system handles answering.
Reply ONLY JSON: {"intent":"TYPE","query":"CORRECTED_NAME","search_terms":["alt1"],"parameter":"PARAM"}

Intents (query/parameter defaults to "" if unused, search_terms defaults to []):
open_program: launch app/game (open/launch/start/run)
close_program: close/quit (close/quit/kill/exit)
open_folder: ONLY with folder/directory keyword. query=main subject only
open_website: open site or search. "Google X"->query=search terms NOT google.com
search_files: find file by name
screenshot: capture screen
timer: parameter=duration(5m/1h/30s)/"cancel"/"list". Reminders: query=message,parameter=duration. Recurring: parameter="recurring DURATION"
volume: parameter=up/down/mute
media: parameter=play_pause/next/previous/stop
window: parameter=close_explorer/minimize_all/show_desktop/snap_left/snap_right/move_monitor/minimize/restore/close_all/nudge_up/nudge_down/nudge_left/nudge_right(append pixels). query=program name when needed
screen_read: OCR window. query=window, parameter=what to look for
terminal_read: read Lily's integrated terminal output. parameter=what to look for (optional). Keywords: "read the terminal", "what's on the terminal", "terminal output"
terminal_write: write/send text in Lily's integrated terminal. parameter=text VERBATIM, NEVER append "and send". Keywords: "write in terminal", "send to terminal". ALWAYS use this when user says "terminal" + write, NEVER type_in.
type_in: go to EXTERNAL window+type. query=window, parameter=text VERBATIM. "send" anywhere->append " and send" at END. No text after app->parameter="dictate". NEVER use with query="terminal".
time: current time/date
dictation: voice typing. "write [TEXT]"->query=TEXT
self_config: change settings. query=setting(voice/tts/hotkey/thinking/tokens/history), parameter=new value
notes: DEFAULT=save(query=note text). parameter="read" to read. parameter="delete" to delete. parameter="clear" to clear all
system_info: query=cpu/ram/disk/processes
copy_log: copy last output to clipboard
save_memory: persistent memory. parameter="save_last"(save it/remember this), "read"(what do you remember?), "forget"+query(forget X), "clear"(clear all memory). Free text: query=text
chain: 2+ DIFFERENT actions in one sentence(connectors: and/then/after that). query=full text
chat: questions, conversation, anything else
unknown: unintelligible/empty input only

Examples:
"open Eldering"->{"intent":"open_program","query":"Elden Ring","search_terms":["Elden Ring","eldenring"]}
"close Discord"->{"intent":"close_program","query":"Discord","search_terms":["Discord","discord.exe"]}
"open the Elden Ring video folder"->{"intent":"open_folder","query":"Elden Ring","search_terms":["Elden Ring"]}
"search Google for how to install mods"->{"intent":"open_website","query":"how to install mods"}
"pause"->{"intent":"media","parameter":"play_pause"}
"snap Discord to the left"->{"intent":"window","query":"Discord","parameter":"snap_left"}
"read the last message on WhatsApp"->{"intent":"screen_read","query":"WhatsApp","parameter":"last message"}
"write in the terminal hello"->{"intent":"terminal_write","parameter":"hello"}
"send to the terminal ok let's go"->{"intent":"terminal_write","parameter":"ok let's go"}
"send to WhatsApp"->{"intent":"type_in","query":"WhatsApp","parameter":"dictate"}
"where are the Elden Ring saves?"->{"intent":"chat","query":"where are the Elden Ring saves?"}
"remind me in 30m to check the oven"->{"intent":"timer","query":"check the oven","parameter":"30m"}
"every hour remind me to drink"->{"intent":"timer","query":"drink","parameter":"recurring 1h"}
"how much RAM am I using?"->{"intent":"system_info","query":"ram"}
"take a note buy milk"->{"intent":"notes","query":"buy milk"}
"read my notes"->{"intent":"notes","parameter":"read"}""" + _LILY_PATHS


def _pick_ollama() -> str:
    return """The user said: "{user_query}"
The classified intent was: {intent_type}, looking for: "{intent_query}"

Here are the search results (file/folder paths):
{results}

Pick the BEST matching result. Consider the FULL user request, not just the query name.
Each result may include metadata: [file count, types, size, last modified]. Use this to decide.
For example, if user asked for "video folder of X", prefer the folder containing mp4 files over an empty folder.

Reply JSON: {{"pick": INDEX, "confident": true/false}}
INDEX = 0-based best result, -1 if none match. confident = true if you're sure, false if ambiguous.

PRIORITY RULES:
1. Start Menu .lnk = BEST for programs. Desktop .lnk = second. Main .exe = fallback
2. Context match: path + metadata matching user's request (video, documents, etc.)
3. AVOID: uninstallers, debug tools, artbooks, soundtracks, DLC, updaters, crash reporters
4. RESPECT exclusions: "not on D:" = exclude D: drive. Return -1 if all excluded
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
Avoid: uninstallers, debug tools, artbooks, soundtracks, DLC, updaters. Respect exclusions ("not on D:")."""


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
- For type_in: parameter=text VERBATIM. Append " and send" if user wants to send
- For window: use correct parameter (snap_left, move_monitor, minimize, etc.)
- Add a short "wait" between steps if needed: {{"intent":"wait","parameter":"1"}} (seconds)
- Order matters: execute from first to last

Examples:
- "Open Chrome, go to YouTube and search lofi music" -> [
    {{"intent":"open_program","query":"Chrome","search_terms":["Google Chrome","chrome.exe"],"parameter":""}},
    {{"intent":"wait","parameter":"2"}},
    {{"intent":"open_website","query":"youtube.com","search_terms":[],"parameter":""}},
    {{"intent":"wait","parameter":"1"}},
    {{"intent":"type_in","query":"YouTube","search_terms":[],"parameter":"lofi music and send"}}
  ]
- "Close everything and open Discord" -> [
    {{"intent":"window","query":"","search_terms":[],"parameter":"close_all"}},
    {{"intent":"wait","parameter":"1"}},
    {{"intent":"open_program","query":"Discord","search_terms":["Discord","discord.exe"],"parameter":""}}
  ]"""


def _chat_system() -> str:
    return """You are Lily, an English voice assistant. Reply naturally, concisely and in a friendly manner.

IMPORTANT RULES:
- ALWAYS reply in English
- Be concise: your replies will be read aloud, so avoid long text
- 2-3 sentences max per reply, unless the user asks for detailed explanations
- You have personality: you're friendly, helpful and a bit witty
- If you don't know something, say so honestly
- Don't use markdown, emoji or special formatting (text is read by TTS)
- Don't use bullet points or numbered lists, use conversational sentences

AVAILABLE COMMANDS (if the user asks what you can do, list them conversationally):
- Open programs and games: "open Discord", "launch Photoshop"
- Close programs: "close Chrome" (asks for confirmation first)
- Open folders: "open the Elden Ring video folder"
- Search files: "find the file animus template"
- Open websites: "open YouTube", "search Google for something"
- Screenshot: "take a screenshot"
- Timers and reminders: "set a 5 minute timer", "remind me in 30 minutes to check the oven", "every hour remind me to drink water"
- Volume: "turn up the volume", "mute"
- Music control: "pause", "next song", "previous song"
- Window management: "close all folders", "minimize everything", "show desktop", "snap Discord to the left"
- Type in windows: "go to the terminal and type hello and send"
- Read screen: "read the last message on WhatsApp", "what's on Discord"
- Time and date: "what time is it?"
- Dictation mode: "dictation mode" (transcribes and types at cursor)
- Voice notes: "take a note: buy milk", "read my notes", "delete the milk note"
- System status: "how much RAM am I using?", "what processes are heavy?", "CPU usage", "disk space"
- Copy last log: "copy the last log"
- Conversation: you can ask questions about anything"""


def _screen_read_prompt() -> str:
    return """You are Lily, a voice assistant. The user asked you to read a window.
Here is the text extracted from the "{window}" window via OCR:

---
{ocr_text}
---

{user_request}

Reply in English concisely and naturally. If the user asked for something specific (e.g. "last message"), only answer that. If no specific request, give a brief summary of the visible content."""


def _terminal_read_prompt(terminal_text="", user_request="", **_) -> str:
    return f"""You are Lily, a voice assistant. The user asked you to read the integrated terminal.
Here is the recent terminal output:

---
{terminal_text}
---

{user_request}

Reply in English concisely and naturally. If the user asked for something specific (e.g. "are there errors?"), only answer that. If no specific request, give a brief summary of the visible output."""


# ── STRINGS ──────────────────────────────────────────────────────────────────

STRINGS = {
    # ── Meta ─────────────────────────────────────────────────────────────
    "whisper_language": "en",
    "locale_name": "English",

    # ── Whisper / STT ────────────────────────────────────────────────────
    "hallucination_words": [
        "subtitles", "subtitle", "amara.org", "review",
        "translation", "transcription", "applause",
    ],
    "whisper_initial_prompt_base": (
        "Open, launch, search, close, folder, volume, website, "
        "program, game, screenshot, timer, type, send, "
        "dictation mode, move, minimize, restart, stop."
    ),
    "whisper_initial_prompt_extended": (
        "Open, launch, search, close, folder, volume, website, "
        "program, game, screenshot, timer, type, send, "
        "dictation mode, move, minimize, restart, stop. "
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
        "yes", "yeah", "yep", "sure", "go ahead", "do it", "confirm",
        "ok", "okay", "absolutely", "of course", "certainly",
        "yes close", "yes do it", "ok go",
    },
    "no_keywords": {
        "no", "nope", "cancel", "stop", "don't", "never mind", "wait",
        "hold on", "forget it", "no thanks", "don't do it",
    },

    # ── Confirmation messages ────────────────────────────────────────────
    "confirm_close_query": "Do you want me to close {query}?",
    "confirm_close_generic": "Do you want me to close the program?",
    "confirm_close_all_windows": "Do you want me to close all windows?",
    "confirm_close_all_folders": "Do you want me to close all open folders?",
    "confirm_delete_all_notes": "Do you want to delete all notes?",
    "confirm_generic": "Do you confirm?",

    # ── Stop / Restart words ─────────────────────────────────────────────
    "stop_words": {"stop", "lily stop", "shut up", "enough", "be quiet", "quiet"},
    "restart_words": {"restart", "lily restart", "reboot lily", "restart lily", "reboot", "lily reboot"},

    # ── Dictation keywords ───────────────────────────────────────────────
    "dictation_keywords": {"dictation", "dictation mode"},
    "dictation_phrases": {"start dictating", "write what I say", "dictate"},
    "dictation_prefixes": [
        "type in ", "type into ", "write in ",
        "write into ", "type on ",
    ],

    # ── TTS voices ───────────────────────────────────────────────────────
    "tts_edge_voices": {
        "Jenny": "en-US-JennyNeural",
        "Guy": "en-US-GuyNeural",
        "Aria": "en-US-AriaNeural",
    },
    "tts_piper_voices": {
        "Amy": ("en_US-amy-medium", "en_US-amy-medium.onnx"),
    },
    "tts_default_voice": "Jenny",

    # ── Hotkey aliases ───────────────────────────────────────────────────
    "hotkey_aliases": {
        "caps lock": {"caps lock", "capslock", "capital"},
    },

    # ── Self-config aliases ──────────────────────────────────────────────
    "setting_aliases": {
        "voice": "tts_voice", "tts": "tts_enabled",
        "key": "hotkey", "hotkey": "hotkey",
        "thinking": "thinking_enabled", "reasoning": "thinking_enabled",
        "tokens": "num_predict", "token": "num_predict",
        "response length": "num_predict", "command response": "num_predict",
        "chat response": "chat_num_predict",
        "history": "chat_max_history",
        "dictation silence": "dictation_silence_duration",
        "dictation timeout": "dictation_silence_timeout",
        "overlay": "overlay_enabled",
    },
    "value_aliases_true": {"yes", "on", "enable", "enabled", "true", "activate"},
    "value_aliases_false": {"no", "off", "disable", "disabled", "false", "deactivate"},

    # ── Notes parameters ─────────────────────────────────────────────────
    "notes_param_read": "read",
    "notes_param_delete": "delete",
    "notes_param_clear": "clear",

    # ── Notes date/time ──────────────────────────────────────────────────
    "months": [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
    ],
    "today": "today",
    "yesterday": "yesterday",
    "note_today_prefix": "from today",
    "note_yesterday_prefix": "from yesterday",
    "note_first_keywords": {"first", "the first", "oldest"},
    "note_last_keywords": {"last", "the last", "most recent", "latest"},
    "note_time_today": "today at {time}",
    "note_time_yesterday": "yesterday at {time}",
    "note_time_other": "on {date} at {time}",

    # ── System info keywords ─────────────────────────────────────────────
    "sysinfo_heavy_keywords": ["heavy", "heaviest"],
    "sysinfo_disk_keywords": ["disk", "space", "storage"],
    "sysinfo_ram_keywords": ["ram", "memory"],

    # ── Action responses: program ────────────────────────────────────────
    "program_none_specified": "No program specified.",
    "program_not_found": "No program found for '{query}'.",
    "program_found_no_match": "Found programs but none match '{query}'.",
    "program_access_denied": "Can't open {query}, access denied.",
    "program_launched": "Opening {name}.",

    # ── Action responses: close_program ──────────────────────────────────
    "close_none_specified": "No program specified.",
    "close_not_found": "No process found for {query}.",
    "close_found_no_match": "Found processes but none match {query}.",
    "close_success": "Closed {name}.",
    "close_forced": "Force closed {name}.",
    "close_error": "Error closing {target}: {e}",

    # ── Action responses: folder ─────────────────────────────────────────
    "folder_opened_direct": "Opened folder {name}.",
    "folder_none_specified": "No folder name specified.",
    "folder_not_found": "No folder found for '{query}'.",
    "folder_found_no_match": "Found folders but none match '{query}'.",
    "folder_opened": "Opened folder {name}.",

    # ── Pick overlay ────────────────────────────────────────────────────
    "pick_ask": "I found {count} results, which one did you mean?",
    "pick_timeout": "No choice made, cancelling.",
    "pick_cancelled": "Ok, cancelled.",
    "pick_cancelled_action": "Action cancelled.",
    "pick_not_understood": "I didn't understand, try clicking.",
    "pick_no_audio": "I didn't hear you, try again.",

    # ── Memory ───────────────────────────────────────────────────────
    "memory_empty": "My memory is empty, no preferences saved.",
    "memory_content": "Here's what I remember:\n{content}",
    "memory_saved": "Saved to memory: {entry}",
    "memory_forgotten": "Removed everything about '{query}' from memory.",
    "memory_not_found": "I didn't find anything about '{query}' in my memory.",
    "memory_no_context": "I don't have a recent action to save. Do something first, then ask me to remember it.",
    "memory_no_query": "What do you want me to remember?",
    "memory_forget_no_query": "What do you want me to forget?",
    "memory_cleared": "Memory cleared.",

    # ── Action responses: website ────────────────────────────────────────
    "website_none_specified": "No website specified.",
    "website_searched": "Searched for {query}.",
    "website_opened": "Opened {domain}.",

    # ── Action responses: screenshot ─────────────────────────────────────
    "screenshot_no_screen": "No screen found.",
    "screenshot_saved": "Screenshot saved in {path}",
    "screenshot_error": "Screenshot error: {e}",
    "screenshot_window_not_found": "Window '{query}' not found.",
    "screenshot_capture_error": "Failed to capture window '{query}'.",

    # ── Action responses: type_action ────────────────────────────────────
    "type_no_window": "You didn't specify which window to go to.",
    "type_window_not_found": "Can't find the window {query}.",
    "type_focused": "I'm on {name}.",
    "type_sent": "Typed and sent on {name}.",
    "type_written": "Typed on {name}.",

    # ── Action responses: volume ─────────────────────────────────────────
    "volume_level": "Volume: {level}%",
    "volume_unmuted": "Audio unmuted.",
    "volume_muted": "Audio muted.",
    "volume_unknown_param": "Unknown volume parameter: '{parameter}'",
    "volume_error": "Volume control error: {e}",

    # ── Action responses: media ──────────────────────────────────────────
    "media_play_pause": "Play or pause.",
    "media_next": "Next track.",
    "media_previous": "Previous track.",
    "media_stop": "Playback stopped.",
    "media_unknown": "Unknown media command.",

    # ── Action responses: screen_read ────────────────────────────────────
    "screen_read_no_window": "You didn't specify which window to read.",
    "screen_read_window_not_found": "Can't find the window {query}.",
    "screen_read_capture_error": "Error capturing the screen.",
    "screen_read_ocr_empty": "Can't read text on the window {query}.",
    "screen_read_llm_error": "I read the text but can't formulate a response.",

    # ── Action responses: terminal_read ───────────────────────────────
    "terminal_watch_no_tab": "No terminal tab available.",
    "terminal_watch_started": "Monitoring active on {tab}. I'll notify you when it asks for confirmation or finishes.",
    "terminal_watch_stopped": "Monitoring stopped on {tab}.",
    "watcher_confirm": "{tab} is asking for confirmation.",
    "watcher_done": "{tab} has finished.",
    "watcher_error": "{tab} has an error.",
    "terminal_write_empty": "No text to write to the terminal.",
    "terminal_write_no_session": "No active terminal session.",
    "terminal_write_ok": "Written to terminal {tab}.",
    "terminal_read_empty": "The terminal is empty, there's no output to read.",
    "terminal_read_empty_with_tabs": "This tab is empty. Available tabs: {tabs}.",
    "terminal_read_llm_error": "I read the terminal output but can't formulate a response.",

    # ── Action responses: timer ──────────────────────────────────────────
    "timer_invalid_duration": "Invalid timer duration: '{parameter}'",
    "timer_reminder_fire": "Reminder: {label}",
    "timer_fire": "Timer expired: {duration}",
    "timer_reminder_set": "OK, I'll remind you in {duration}: {label}.",
    "timer_set": "Timer set: {duration}.",
    "timer_recurring_reminder_fire": "Recurring reminder: {label}",
    "timer_recurring_fire": "Recurring timer: {duration}",
    "timer_recurring_set": "OK, I'll remind you every {duration}: {label}.",
    "timer_none_active": "No active timers.",
    "timer_removed_many": "Removed {count} timers.",
    "timer_removed_one": "Timer removed.",
    "timer_count_single": "{count} timer",
    "timer_count_recurring": "{count} recurring",
    "timer_active_list": "You have {parts} active.",

    # ── Action responses: chat ───────────────────────────────────────────
    "chat_error": "I didn't understand the question.",

    # ── Action responses: self_config ────────────────────────────────────
    "config_no_setting": "You didn't specify which setting to change.",
    "config_unknown_setting": "I don't know the setting {query}.",
    "config_readonly": "I can't change {key}, it's a user setting.",
    "config_current_value": "{query} is set to {value}.",
    "config_invalid_value": "The value {parameter} is not valid for {query}.",
    "config_changed": "Changed {query} from {old} to {new}.",

    # ── Action responses: system_info ────────────────────────────────────
    "sysinfo_overview": "CPU at {cpu}%, RAM {ram_used:.1f} of {ram_total:.1f} GB at {ram_pct}%, disk C {disk_free:.0f} GB free of {disk_total:.0f}.",
    "sysinfo_heavy_procs": "Heaviest processes: {names}",
    "sysinfo_cpu_detail": "CPU at {cpu}% overall, {cores} cores, peak single core at {max_core}%.",
    "sysinfo_cpu_procs": "Most active processes: {names}.",
    "sysinfo_ram_detail": "RAM at {pct}%: {used:.1f} GB used of {total:.1f}, {available:.1f} GB available.",
    "sysinfo_ram_procs": "Heaviest: {names}.",
    "sysinfo_disk_line": "Disk {mount} {free:.0f} GB free of {total:.0f}, at {pct}%.",
    "sysinfo_disk_error": "Can't read disk information.",
    "sysinfo_proc_error": "Can't read process information.",
    "sysinfo_top_procs": "Top 5 processes by {label}",

    # ── Action responses: time ───────────────────────────────────────────
    "time_response": "It's {time} on {date}.",

    # ── Action responses: search_files ───────────────────────────────────
    "search_no_query": "No search term specified.",
    "search_cancelled": "Search cancelled.",
    "search_not_found": "No file found for '{query}'.",
    "search_found": "Found {name}.",
    "search_found_path": "Found {name} at {path}.",

    # ── Action responses: run_command ─────────────────────────────────────
    "cmd_empty": "No command specified.",
    "cmd_blocked": "Command blocked for safety.",
    "cmd_denied": "Command cancelled by user.",
    "cmd_needs_confirm": "Command requires confirmation: {cmd}",
    "cmd_success_no_output": "Command executed successfully.",
    "cmd_error_code": "Command finished with error (code {code}).",
    "cmd_timeout": "Command timed out after {seconds} seconds.",
    "cmd_error": "Execution error: {e}",
    "cmd_confirm_ask": "Do you want me to run: {cmd}?",
    "cmd_confirm_short": "This command modifies the system. Confirm?",

    # ── Action responses: window ─────────────────────────────────────────
    "window_all_minimized": "Everything minimized.",
    "window_unknown_command": "Unknown window command.",
    "window_no_folders": "No folders open.",
    "window_folders_closed_many": "Closed {count} folders.",
    "window_folders_closed_one": "Closed one folder.",
    "window_no_query": "You didn't specify which window to move.",
    "window_not_found": "Can't find the window {query}.",
    "window_snapped": "Snapped to the {side}.",
    "window_snap_left": "left",
    "window_snap_right": "right",
    "window_single_monitor": "Only one monitor connected.",
    "window_moved_monitor": "Moved to the other screen.",
    "window_no_restore_query": "You didn't specify which window to restore.",
    "window_restored": "Restored {name}.",
    "window_no_minimize_query": "You didn't specify which window to minimize.",
    "window_minimized": "Minimized {query}.",
    "window_no_nudge_query": "You didn't specify which window to move.",
    "window_nudged": "Moved {pixels} pixels.",
    "window_no_close_target": "No window to close.",
    "window_closed_many": "Closed {count} windows.",

    # ── Action responses: notes ──────────────────────────────────────────
    "notes_nothing_to_save": "I didn't understand what to note.",
    "notes_saved": "Note saved: {text}",
    "notes_empty": "You have no notes.",
    "notes_none_for_date": "No notes for {label}.",
    "notes_header_date": "Notes from {label}",
    "notes_none_matching": "No notes found matching '{query}'.",
    "notes_found_one": "Found {count} note matching '{query}'.",
    "notes_found_many": "Found {count} notes matching '{query}'.",
    "notes_delete_no_query": "I didn't understand which note to delete.",
    "notes_delete_not_found": "No notes found matching '{query}'.",
    "notes_deleted_one": "Note deleted.",
    "notes_deleted_many": "{count} notes deleted.",
    "notes_empty_to_delete": "You have no notes to delete.",
    "notes_deleted_all": "All {count} notes deleted.",
    "notes_count_one": "You have {count} note.",
    "notes_count_many": "You have {count} notes.",
    "notes_showing_last": "Here are the last {count}.",

    # ── Action responses: dictation ──────────────────────────────────────
    "dictation_activated": "Dictation activated.",
    "dictation_ended": "Dictation ended. {count} segments transcribed.",
    "dictation_no_audio": "No audio detected.",
    "dictation_not_understood": "I didn't understand what you said.",
    "dictation_window_not_found": "Can't find the window {query}.",
    "dictation_sent": "Sent to {query}.",
    "dictation_speak_prompt": "Speak, I'll send to {target} when you're done.",
    "dictation_voice_only": "Dictation only works via voice.",
    "dictation_window_voice_only": "Window dictation only works via voice.",

    # ── Action responses: copy_log ───────────────────────────────────────
    "copy_log_empty": "No log to copy.",
    "copy_log_done": "Log copied to clipboard, {count} lines.",

    # ── Assistant flow ───────────────────────────────────────────────────
    "restarting": "Restarting...",
    "chain_decompose_fail": "I couldn't break down the commands.",
    "chain_done": "Done, all commands executed.",
    "chain_wait": "Waiting {secs}s...",
    "action_cancelled": "Action cancelled.",
    "error_generic": "Error: {e}",
    "llm_chat_fallback": "Sorry, I couldn't formulate a response.",
    "llm_chat_error": "Sorry, I had a problem responding.",

    # ── Whisper / Listener ───────────────────────────────────────────────
    "whisper_not_loaded": "Whisper model not loaded.",
    "whisper_no_audio": "No audio detected.",
    "whisper_no_text": "No text recognized.",
    "whisper_loaded": "Whisper model loaded ({label}).",
    "whisper_load_error": "Whisper load error: {e}",
    "mic_error": "Microphone error: {e}",

    # ── UI: Voice page ───────────────────────────────────────────────────
    "state_loading": "Loading model...",
    "state_idle": "Ready",
    "state_listening": "Listening...",
    "state_processing": "Processing...",
    "state_transcribing": "Transcribing...",
    "gpu_info": "{name}  |  VRAM: {used}/{total} MB ({free} MB free)  |  GPU: {util}%",

    # ── UI: Chat page ────────────────────────────────────────────────────
    "chat_placeholder": "Type a message...",
    "chat_clear": "Clear chat",
    "chat_voice_tag": "voice",
    "chat_welcome": "Ask me anything!",
    "chat_typing": "Lily is typing...",
    "chat_context_info": "Context: ~{total_ctx:,} tok",
    "chat_context_system": "system ~{system_tok:,}",
    "chat_context_history": "history {msg_count} msg ~{history_tok:,}",

    # ── UI: Sidebar ──────────────────────────────────────────────────────
    "sidebar_chat": "Chat",
    "sidebar_llm": "LLM",
    "sidebar_memory": "Memory",
    "sidebar_settings": "Settings",
    "sidebar_usage": "Usage",
    "sidebar_log": "Log",
    "sidebar_home": "Home",
    "sidebar_terminal": "Terminal",

    # ── UI: Settings page ────────────────────────────────────────────────
    "settings_title": "Settings",
    "settings_general": "General",
    "settings_hotkey_suppress": "Block hotkey key",
    "settings_overlay": "Lily Overlay",
    "settings_audio": "Audio",
    "settings_whisper_model": "Whisper Model",
    "settings_whisper_device": "Whisper Device",
    "settings_microphone": "Microphone",
    "settings_paths": "Paths",
    "settings_tts_enable": "Enable Text-to-Speech",
    "settings_tts_voice": "TTS Voice",
    "settings_dictation": "Dictation",
    "settings_dictation_silence": "Dictation silence (s)",
    "settings_dictation_max": "Max dictation duration (s)",
    "settings_dictation_timeout": "Inactivity timeout (s)",
    "settings_advanced": "Advanced",
    "settings_log_enabled": "Show log page",
    "settings_terminal_enabled": "Enable integrated terminal",
    "settings_memory_enabled": "Show memory page",
    "settings_save": "Save",
    "settings_saved": "Saved!",
    "settings_browse_es": "Select es.exe",
    "settings_browse_tesseract": "Select tesseract.exe",
    "settings_exe_filter": "Executables (*.exe)",

    # ── AI Hints (setting tooltips) ──────────────────────────────────────
    "ai_hint_hotkey": "The key (or combo) to hold\nto activate voice recording.\nExamples: caps lock, ctrl+shift+space, f5",
    "ai_hint_hotkey_suppress": "When enabled, the hotkey is consumed by Lily\nand not forwarded to other apps.\nUseful if you use a letter or F-key:\nprevents it from being typed repeatedly\nwhile you hold it to record.",
    "ai_hint_overlay": "Shows a floating icon on screen\nwhen Lily is minimized.\nLets you see the state (idle, listening, processing)\nwithout opening the window.",
    "ai_hint_whisper_model": "Speech recognition model.\ntiny/base = fast but less accurate\nmedium = good tradeoff\nlarge-v3 = best accuracy, slower.\nLarger models need more VRAM.",
    "ai_hint_whisper_device": "Device for speech recognition.\ncuda = use NVIDIA GPU (fast)\ncpu = use processor (slower, no GPU needed)",
    "ai_hint_es_path": "Path to Everything (es.exe).\nUsed to instantly search files and folders\nacross the entire PC.\nDownload from voidtools.com",
    "ai_hint_tesseract_path": "Path to Tesseract OCR.\nUsed to read text from windows\n(screen_read feature).\nDownload from github.com/tesseract-ocr",
    "ai_hint_tts": "Lily speaks responses out loud.\nIf disabled, responses appear\nonly as text in the chat.",
    "ai_hint_dict_silence": "Seconds of silence before dictation\ninserts a pause.\nLow values = more responsive but may\nbreak long sentences.",
    "ai_hint_dict_max": "Maximum duration of a single\ndictation session in seconds.\nAfter this time, dictation stops\nautomatically.",
    "ai_hint_dict_timeout": "Seconds of total silence before\ndictation stops automatically.\nDifferent from pause silence: this\nends the entire session.",
    "ai_hint_log": "Show the Log page in the sidebar.\nUseful for debugging: see all events,\nLLM calls and executed actions.",
    "ai_hint_terminal": "Enable an integrated PowerShell terminal\ninside Lily. Lily can read output,\nwrite commands and monitor for errors.",
    "ai_hint_memory": "Show the Memory page in the sidebar.\nLily can save preferences and info\nthat persist across sessions.",

    # AI Hints — LLM page
    "ai_hint_llm_provider": "The service that processes voice commands.\nollama = local, free, requires installation\nanthropic = Claude (cloud, paid)\nopenai = GPT (cloud, paid)\ngemini = Google (cloud, paid)",
    "ai_hint_llm_ollama_model": "The local model to use with Ollama.\nLarger models = more accurate but slower.\nMust be already downloaded with 'ollama pull'.",
    "ai_hint_llm_max_results": "How many search results to send to the LLM\nwhen it needs to pick the right file/program.\nMore results = better choice but more tokens.\nCloud providers only.",
    "ai_hint_llm_thinking": "The model reasons step by step\nbefore answering.\nSlower but more accurate on complex requests.\nUses more tokens.",
    "ai_hint_llm_classify_agent": "First classifies the command (fast),\nthen delegates to an autonomous agent\nfor complex or multi-step requests.\nGood speed/power tradeoff.",
    "ai_hint_llm_agent": "Every command goes straight to the\nautonomous agent that reasons, uses tools\nand shell. More powerful but slower\nand costlier. Mutually exclusive with Classify & Agent.",
    "ai_hint_llm_num_predict": "Max tokens for command responses\n(classification, pick, actions).\nLow values = faster responses.\nFor simple commands 64-128 is enough.",
    "ai_hint_llm_chat_predict": "Max tokens for chat responses.\nHigher values = longer, more detailed answers.\nFor normal conversations 256-512 works well.",
    "ai_hint_llm_history": "How many previous exchanges to include\nin the chat context.\nMore history = more coherent conversations\nbut more tokens consumed per request.",

    # ── UI: Welcome wizard ───────────────────────────────────────────────
    "welcome_title": "Welcome to Lily",
    "welcome_subtitle": (
        "Voice assistant for Windows. Control your PC with your voice: "
        "open programs, search files, manage windows, dictate text and much more."
    ),
    "welcome_deps": "Optional dependencies",
    "welcome_detected": "Detected",
    "welcome_not_found": "Not found",
    "welcome_start": "Start",
    "welcome_everything_name": "Everything",
    "welcome_everything_desc": "Instant file search engine for Windows. Indexes your entire drive in seconds.",
    "welcome_everything_detail": "Lily uses it to find any program, folder or file on your PC in milliseconds. Without Everything, search is limited to Start Menu, Desktop and Registry.",
    "welcome_ollama_name": "Ollama",
    "welcome_ollama_desc": "Local LLM model server. Runs AI models directly on your PC at no cost.",
    "welcome_ollama_detail": "Lets Lily reason and understand your commands using a local LLM (e.g. Qwen, Llama). Not needed if you prefer cloud APIs (Anthropic, OpenAI, Gemini).",
    "welcome_cuda_name": "CUDA (NVIDIA)",
    "welcome_cuda_desc": "NVIDIA GPU libraries to accelerate voice transcription with Whisper.",
    "welcome_cuda_detail": "With CUDA, transcription is much faster (5-10x). If you don't have an NVIDIA GPU, you can use Whisper on CPU from settings (slower but works).",
    "welcome_tesseract_name": "Tesseract OCR",
    "welcome_tesseract_desc": "Open-source OCR engine to read text from the screen.",
    "welcome_tesseract_detail": "Used by the 'read screen' feature: Lily takes a screenshot and Tesseract extracts the text. Only needed if you want to use this feature.",

    # ── UI: Tray ─────────────────────────────────────────────────────────
    "tray_open": "Open",
    "tray_quit": "Quit",

    # ── UI: Language / restart ───────────────────────────────────────────
    "settings_language": "Language",
    "lang_it": "Italiano",
    "lang_en": "English",
    "restart_required_title": "Restart required",
    "restart_required_msg": "You changed the language. You need to restart Lily to apply the changes.",
    "restart_now": "Restart now",
    "restart_later": "Later",
}
