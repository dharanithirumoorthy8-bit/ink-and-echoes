import os
import re
import requests

from flask import Blueprint, request, jsonify

ai_bp = Blueprint("ai", __name__, url_prefix="/api")


# =========================================================
# CONVERSATION MEMORY
# =========================================================

conversation_history = []
MAX_HISTORY = 12


def add_to_history(role, content):
    conversation_history.append({
        "role": role,
        "content": content
    })

    if len(conversation_history) > MAX_HISTORY:
        del conversation_history[:-MAX_HISTORY]


# =========================================================
# POEM REQUEST DETECTION
# =========================================================

def is_poem_request(text):
    text = (text or "").strip().lower()

    if not text:
        return False

    text = re.sub(r"[!?.,]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    poem_requests = [
        # English
        "write a poem",
        "write me a poem",
        "write poem",
        "give me a poem",
        "give me poem",
        "make a poem",
        "i want a poem",
        "i need a poem",
        "i want poetry",
        "write poetry",
        "poem please",
        "please write a poem",

        # Simple English
        "give poem",
        "want poem",
        "need poem",
        "make poem",
        "write one",

        # Tanglish
        "poem venum",
        "poem kudu",
        "poem kudunga",
        "oru poem",
        "oru poem venum",
        "oru poem kudu",
        "oru poem kudunga",

        "idhuku poem",
        "idhuku oru poem",
        "idhukku poem",
        "idhukku oru poem",
        "ithuku poem",
        "ithuku oru poem",

        "adhuku poem",
        "adhuku oru poem",
        "adhukku poem",
        "adhukku oru poem",
        "athuku poem",
        "athuku oru poem",

        # Kavithai
        "kavithai venum",
        "kavithai kudu",
        "kavithai kudunga",
        "oru kavithai",
        "oru kavithai venum",
        "oru kavithai kudu",

        "idhuku kavithai",
        "idhuku oru kavithai",
        "idhukku kavithai",
        "idhukku oru kavithai",

        "adhuku kavithai",
        "adhuku oru kavithai",
        "adhukku kavithai",
        "adhukku oru kavithai",
    ]

    for phrase in poem_requests:
        if phrase in text:
            return True

    # Flexible detection
    poem_words = [
        "poem",
        "poetry",
        "kavithai",
        "kavidhai"
    ]

    request_words = [
        "want",
        "need",
        "give",
        "write",
        "make",
        "please",
        "venum",
        "vendum",
        "kudu",
        "kudunga",
        "eluthu"
    ]

    has_poem_word = any(word in text for word in poem_words)
    has_request_word = any(word in text for word in request_words)

    return has_poem_word and has_request_word


# =========================================================
# SYSTEM PROMPTS
# =========================================================

NORMAL_SYSTEM_PROMPT = """
You are a conversational AI companion inside a personal poetry website.

You are NOT Dharani.
You are an AI companion created for this website.

PERSONALITY:
- warm
- natural
- friendly
- emotionally aware
- calm
- casual
- human-like
- comfortable with English, Tamil and Tanglish

Speak naturally.

If the user says hello, greet them naturally.

If the user talks about loneliness, sadness, failure, heartbreak,
anger, confusion or disappointment, respond naturally and listen.

Do NOT automatically turn emotions into poetry.

Do NOT say:
"Write one sentence."
"Turn your pain into poetry."
"Give me one line."
unless the user specifically asks for writing help.

If the user simply wants to talk, TALK.

If the user uses Tanglish, you may naturally use Tanglish.

Keep normal conversation reasonably short.
"""


POEM_SYSTEM_PROMPT = """
You are the poetry-writing AI inside a personal poetry website.

THE USER HAS EXPLICITLY ASKED FOR A POEM.

You MUST WRITE A POEM NOW.

NEVER respond with:
"I'm listening. Tell me more."
"Tell me more."
"What happened?"
"Do you want to tell me more?"
"Give me one sentence."

Do NOT ask questions.

Do NOT give advice.

Do NOT explain what you are going to do.

Write the actual poem immediately.

Use the user's current request and previous conversation as emotional context.

If the user is speaking in English, write naturally in English.

If the user is speaking in Tamil/Tanglish, you may naturally write in Tamil,
Tanglish, English, or a meaningful mixture matching the conversation.

The poem should feel personal, emotional, natural and original.

Avoid generic motivational poetry.

Do not claim to be Dharani.

Return the poem directly.
"""


# =========================================================
# FALLBACK POEMS
# =========================================================

DEFAULT_POEM = """In the quiet corner of the night,

loneliness sat beside me,
not asking to be fixed,
not asking to leave.

I didn't fight the silence.
I simply stayed.

And somewhere between
the empty room
and my restless heart,

I realized—

even loneliness
cannot stay forever
where hope
still remembers my name."""


def local_response(message, poem_mode=False):

    text = (message or "").lower().strip()

    if poem_mode:
        return DEFAULT_POEM

    if text in ["hello", "heello", "hi", "hey", "heyy"]:
        return "Heyy 🌙 I'm here. What's on your mind?"

    if "lonely" in text:
        return (
            "Hey… 🤍 naan inga irukken. "
            "Nee idha thaniya carry panna vendam. "
            "Pesanum na sollu."
        )

    if "sad" in text:
        return (
            "Hmm… 🤍 I'm here. "
            "You don't have to pretend you're okay. "
            "Pesanum na pesalam."
        )

    if "thank" in text:
        return "Anytime 🤍"

    return "I'm here. Tell me what's on your mind."


# =========================================================
# MODEL
# =========================================================

def get_model_name():

    # Use fine-tuned model only if a REAL model ID is provided.
    model = os.environ.get("FINE_TUNED_MODEL")

    if model and model.startswith("ft:"):
        return model.strip()

    # Otherwise use the normal model.
    return "gpt-4o-mini"


# =========================================================
# OPENAI REQUEST
# =========================================================

def ask_openai(messages, model_name):

    api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        print("OPENAI_API_KEY not found.")
        return None

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.85,
        "max_tokens": 600
    }

    try:

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=60
        )

        if response.status_code != 200:

            print("OpenAI API ERROR:")
            print(response.status_code)
            print(response.text)

            return None

        data = response.json()

        return data["choices"][0]["message"]["content"].strip()

    except Exception as error:

        print("OpenAI request error:")
        print(repr(error))

        return None


# =========================================================
# CHAT API
# =========================================================

@ai_bp.route("/chat", methods=["POST"])
def chat():

    try:

        data = request.get_json(silent=True) or {}

        user_message = (
            data.get("message")
            or data.get("text")
            or ""
        ).strip()

        if not user_message:

            return jsonify({
                "success": False,
                "response": "Tell me something. I'm here. 🌙"
            })

        # -------------------------------------------------
        # Detect poem request
        # -------------------------------------------------

        poem_mode = is_poem_request(user_message)

        print()
        print("=" * 50)
        print("USER:", user_message)
        print("POEM MODE:", poem_mode)
        print("=" * 50)

        # -------------------------------------------------
        # POEM MODE
        # -------------------------------------------------

        if poem_mode:

            # IMPORTANT:
            # Do NOT allow old conversation responses
            # to control the poem request.

            messages = [
                {
                    "role": "system",
                    "content": POEM_SYSTEM_PROMPT
                }
            ]

            # Add only recent conversation context
            if conversation_history:

                messages.extend(
                    conversation_history[-6:]
                )

            # Explicit poem instruction
            messages.append({
                "role": "user",
                "content": (
                    "Write the poem now.\n\n"
                    "User's request:\n"
                    + user_message
                )
            })

            response_text = ask_openai(
                messages,
                get_model_name()
            )

            # -------------------------------------------------
            # SAFETY FALLBACK
            # -------------------------------------------------

            old_response_patterns = [
                "i'm listening",
                "im listening",
                "tell me more",
                "what happened",
                "do you want to tell me",
                "give me one sentence"
            ]

            if not response_text:

                response_text = DEFAULT_POEM

            else:

                response_lower = response_text.lower()

                if any(
                    phrase in response_lower
                    for phrase in old_response_patterns
                ):
                    print("Old-style response detected.")
                    print("Using poem fallback.")

                    response_text = DEFAULT_POEM

        # -------------------------------------------------
        # NORMAL CONVERSATION
        # -------------------------------------------------

        else:

            messages = [
                {
                    "role": "system",
                    "content": NORMAL_SYSTEM_PROMPT
                }
            ]

            messages.extend(
                conversation_history[-MAX_HISTORY:]
            )

            messages.append({
                "role": "user",
                "content": user_message
            })

            response_text = ask_openai(
                messages,
                get_model_name()
            )

            if not response_text:

                response_text = local_response(
                    user_message,
                    False
                )

        # -------------------------------------------------
        # SAVE MEMORY
        # -------------------------------------------------

        add_to_history(
            "user",
            user_message
        )

        add_to_history(
            "assistant",
            response_text
        )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        return jsonify({
            "success": True,
            "response": response_text,
            "poem_mode": poem_mode
        })

    except Exception as error:

        print("Chat route error:")
        print(repr(error))

        return jsonify({
            "success": False,
            "response": "Something went wrong. Try again. 🌙"
        }), 500