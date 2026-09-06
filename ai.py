import os
import random
import re
from flask import Blueprint, request, jsonify, current_app
import requests

ai_bp = Blueprint('ai', __name__, url_prefix='/api')

_conversation_history = []


def detect_language(text):
    lower = (text or '').lower()
    tamil_markers = ['enna', 'ennai', 'nee', 'naan', 'ungal', 'mana', 'sollu', 'nala', 'kadavul', 'pesa', 'payanam', 'un', 'thozhi', 'vazh', 'vaazh', 'manam', 'siripu', 'pirachanai', 'oru']
    hindi_markers = ['main', 'aap', 'hai', 'kya', 'kyon', 'bahut', 'dil', 'shayari', 'mujhe', 'tum', 'ho', 'raat', 'khwaab', 'safar', 'dukh', 'pyaar']
    if any(marker in lower for marker in tamil_markers):
        return 'ta'
    if any(marker in lower for marker in hindi_markers):
        return 'hi'
    return 'en'


def choose_response(options, message_key):
    recent = [item for item in _conversation_history if item[0] == message_key]
    if recent:
        used = [item[1] for item in recent]
        available = [opt for opt in options if opt not in used]
        if available:
            options = available
    choice = random.choice(options)
    _conversation_history.append((message_key, choice))
    if len(_conversation_history) > 12:
        del _conversation_history[:-12]
    return choice


def local_poetry_reply(message):
    text = (message or '').strip()
    if not text:
        return 'Tell me what you feel, and I will listen.'

    cleaned = re.sub(r'\s+', ' ', text)
    lower = cleaned.lower()
    lang = detect_language(cleaned)
    key = (lang, cleaned.lower())

    if any(word in lower for word in ['help', 'guid', 'solla', 'sollu', 'madad', 'sahayta', 'help me']):
        if lang == 'ta':
            options = [
                'நீங்க எழுத விரும்பும் உணர்வை முதலில் ஒரு வரியாக சொல்லுங்கள். பிறகு நான் அதை மென்மையான கவிதை வடிவத்துக்கு மாற்ற உதவுறேன்.',
                'நீங்கள் மனதில் நினைக்கும் சின்ன காட்சியை எழுதுங்கள். நான் அதை கற்பனை, மெளனம், பாடல் போல மாற்றுவேன்.',
                'முதலில் emotion-ஐ சொல்லுங்க; அடுத்து imagery-ஐ சேர்ப்போம். அதுதான் நல்ல கவிதை ஆகும்.'
            ]
            return choose_response(options, key)
        if lang == 'hi':
            options = [
                'Aap apni feeling ko ek line mein boliye. Main usse ek sukoon bhari shayari mein badal dunga.',
                'Aap jo khwaab ya dukh ya pyaar mehsoos kar rahe ho, usko ek chhota sa vakya boliye. Main usko kavita bana dunga.',
                'Pehle emotion bataiye, phir imagery add karte hain. Tab kavita asli feel banegi.'
            ]
            return choose_response(options, key)
        options = [
            'Start with the feeling you want to keep. I can turn that feeling into a beautiful poem line by line.',
            'Tell me the emotion, the image, and the moment. Then I will shape it into a poem that sounds honest and alive.',
            'Share one memory, one ache, or one joy. I can help you build it into a poem with rhythm and warmth.'
        ]
        return choose_response(options, key)

    if any(word in lower for word in ['sad', 'hurt', 'lonely', 'dukha', 'dard', 'manam', 'dukkam', 'pazham', 'thookam']):
        if lang == 'ta':
            options = [
                'உங்கள் உணர்வு காயமாக இருக்கலாம்; ஆனால் அதை மெதுவாக எழுதினால் அது ஒரு கவிதையாக மாறும்.\n\n“' + cleaned + '”\n\nமுதலில் ஒரு வரி எழுதுங்கள், பிறகு இரண்டாவது வரியை மென்மையாக சேர்க்கவும்.',
                'சில நேரம் கண்ணீர் கூட ஒரு நல்ல வரி உருவாக்கும்.\n\n“' + cleaned + '”\n\nஇதை மெதுவாக, சாந்தமாக, உண்மையாக எழுதுங்கள்.',
                'கண்ணீரை கவிதையாக மாற்ற வேண்டுமென்றால், முதலில் அதை உண்மையாக சொல்லுங்கள்.\n\n“' + cleaned + '”\n\nபிறகு அடுத்த வரியில் ஒளி சேர்க்கவும்.'
            ]
            return choose_response(options, key)
        if lang == 'hi':
            options = [
                'Aapka dard sun raha hoon. Kabhi-kabhi isse ek shant line mein likh dena hi sabse accha hota hai.\n\n“' + cleaned + '”\n\nEk sakoon bhari line likho, phir uske peeche ek aur line jodo.',
                'Raat ki khamoshi bhi kabhi-kabhi kavita ban jaati hai.\n\n“' + cleaned + '”\n\nAaj ek sachchi line likhiye, bina judge kiye.',
                'Dard ko shabd dena hi usko samajhne ka ek tarika hai.\n\n“' + cleaned + '”\n\nAb ek soft line likh kar usse roshan kijiye.'
            ]
            return choose_response(options, key)
        options = [
            'I hear the ache in your words. Let the silence hold it gently and turn it into a line that feels honest.\n\n“' + cleaned + '”\n\nWrite one raw sentence first; the rest of the poem can bloom from there.',
            'Pain can become poetry when it is witnessed with tenderness.\n\n“' + cleaned + '”\n\nKeep the next line soft, slow, and true.',
            'The ache is real, and that makes it valid material for a poem.\n\n“' + cleaned + '”\n\nWrite the next line like you are comforting yourself.'
        ]
        return choose_response(options, key)

    if any(word in lower for word in ['love', 'heart', 'pyaar', 'prema', 'anbu', 'kadhali', 'manas', 'bheart']):
        if lang == 'ta':
            options = [
                'அன்பு வெறும் வார்த்தை இல்லை; அது ஒரு மௌனம், ஒரு காத்திருப்பு, ஒரு நினைவு.\n\n“' + cleaned + '”\n\nஅடுத்த வரியில் அந்த மனநிலையை மென்மையாக கவிதையாக மாற்றுங்கள்.',
                'நீங்கள் நினைக்கும் அன்பு, உண்மையில் ஒருவரின் முகத்தை மின்னவைக்கும் ஒரு சின்ன வெளிச்சம்.\n\n“' + cleaned + '”\n\nஇதை இன்னும் நேர்த்தியாக, மென்மையாக, உண்மையாக சொல்லுங்கள்.',
                'அன்பு சமீபத்தில் பிறந்த வெளிச்சம் போல இருக்கிறது; அதை மெலிதாக, நுணுக்கமாக எழுதுங்கள்.\n\n“' + cleaned + '”'
            ]
            return choose_response(options, key)
        if lang == 'hi':
            options = [
                'Pyaar sirf ek shabd nahin hota; woh ek sabr, ek yaad, ek dua hota hai.\n\n“' + cleaned + '”\n\nAb agla sher us feeling ko ek narm line mein laaye.',
                'Jo tum mehsoos kar rahe ho, wahi toh kavita banne ki sabse sachchi jagah hai.\n\n“' + cleaned + '”\n\nAaj ek pyaar bhari, gehrayi wali line likho.',
                'Pyaar ki sabse gehri baat yahi hoti hai ki woh khamoshi ko bhi language bana deti hai.\n\n“' + cleaned + '”'
            ]
            return choose_response(options, key)
        options = [
            'Love is not only a feeling — it is a room you keep opening for someone else.\n\n“' + cleaned + '”\n\nWrite the next line as if you are offering a promise, not just a memory.',
            'That feeling is already poetry; it only needs one clear line to bloom.\n\n“' + cleaned + '”\n\nLet the next line be honest, soft, and brave.',
            'Love is at its strongest when it sounds like a quiet certainty.\n\n“' + cleaned + '”\n\nWrite the next line as if you trust it.'
        ]
        return choose_response(options, key)

    if any(word in lower for word in ['angry', 'mad', 'rage', 'gussa', 'ros', 'krodh', 'nervous', 'tensed', 'irrita']):
        if lang == 'ta':
            options = [
                'கோபம் ஒரு தீமையல்ல; அது உண்மையை சுட்டிக்காட்டும் வெளிச்சம்.\n\n“' + cleaned + '”\n\nஅதை கவிதை வடிவத்தில் மாற்ற வேண்டுமெனில், முதல் வரி உண்மையாக இருங்கள்.',
                'உண்மையான கோபம் எந்தவொரு அச்சுறுத்தலும் இல்லை; அது ஒரு அலை. அதை நேர்த்தியாக எழுதுங்கள்.\n\n“' + cleaned + '”',
                'நீங்கள் கோபமாக இருக்கலாம், ஆனால் அந்த கோபம் ஒரு வரியில் அழகாக குடியேறலாம்.\n\n“' + cleaned + '”'
            ]
            return choose_response(options, key)
        if lang == 'hi':
            options = [
                'Gussa ek aag hai, par agar use sahi tareeke se likha jaaye to woh shayari ban sakta hai.\n\n“' + cleaned + '”\n\nIsse ek sachchi, strong line mein rakho.',
                'Aag ko kabhi kabhi kavita ka roop milta hai, bas uska sahi saaz chahiye.\n\n“' + cleaned + '”',
                'Gussa kabhi-kabhi asli truth ka ek shabd hota hai.\n\n“' + cleaned + '”\n\nUse ek clear, sharp line mein rakho.'
            ]
            return choose_response(options, key)
        options = [
            'Your fire is not the enemy; it is the lantern that keeps the truth from disappearing.\n\n“' + cleaned + '”\n\nShape it into a clean, sharp line and let the feeling become art.',
            'Anger can become a poem when you give it structure instead of letting it shout alone.\n\n“' + cleaned + '”',
            'Use that anger as pressure, not as chaos.\n\n“' + cleaned + '”\n\nTurn it into a line with a strong center.'
        ]
        return choose_response(options, key)

    if lang == 'ta':
        options = [
            'உங்கள் எண்ணம் ஏற்கனவே ஒரு கவிதை. ஒரு உண்மையான வரி எழுதுங்கள்.\n\n“' + cleaned + '”\n\nஅடுத்து, அந்த எண்ணத்தின் பிம்பத்தை இறக்கி வைக்கவும்.',
            'நீங்கள் சொல்ல விரும்புவது, சின்ன காட்சி, சின்ன உணர்வு, அல்லது ஒரு நினைவு. அதைத்தான் கவிதையில் சேர்க்க வேண்டும்.\n\n“' + cleaned + '”',
            'சொல்லவந்ததை உடனே முழுமையாக சொல்ல வேண்டாம்; சின்னதாகத் தொடங்குங்கள்.\n\n“' + cleaned + '”',
            'ஒரே ஒரு பிம்பம் மட்டும் தேர்ந்தெடுங்கள்; அதுதான் உங்கள் அடுத்த கவிதை வரியின் ஆரம்பம்.\n\n“' + cleaned + '”'
        ]
        return choose_response(options, key)

    if lang == 'hi':
        options = [
            'Aapki soch ek kavita ki seedhi si shuruaat hai. Ek sachchi line likho.\n\n“' + cleaned + '”\n\nPhir usme ek image ya ek yaad jodo.',
            'Ek kavita mein sabse bada kaam yahi hota hai ki feeling ko sahi rhythm mein rakha jaaye.\n\n“' + cleaned + '”',
            'Aaj ek chhota sa shabd aur ek gehrayi wali line likhiye.\n\n“' + cleaned + '”',
            'Jo tum mehsoos kar rahe ho, usse ek image mein badlo.\n\n“' + cleaned + '”'
        ]
        return choose_response(options, key)

    options = [
        'I am listening. Your words already carry a rhythm.\n\n“' + cleaned + '”\n\nLet me help you turn that feeling into a line that feels honest, bright, and alive.',
        'There is already a poem inside that thought.\n\n“' + cleaned + '”\n\nTurn one feeling into a real image, and the rest of the poem will follow.',
        'Tell me one image, one memory, or one emotion behind that sentence.\n\n“' + cleaned + '”\n\nThen I can help you shape it into a poem with detail and softness.',
        'Your sentence has a pulse already.\n\n“' + cleaned + '”\n\nGive it one clear image and it will become a poem.'
    ]
    return choose_response(options, key)


@ai_bp.route('/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({'error': 'no message'}), 400

    api_key = os.environ.get('OPENAI_API_KEY')
    # If an API key is available, prefer calling the upstream API. Try these
    # sources for the model name (in order): env FINE_TUNED_MODEL, instance file,
    # then the default base model.
    if api_key:
        model_name = os.environ.get('FINE_TUNED_MODEL')
        if not model_name:
            try:
                with open(os.path.join('instance', 'fine_tuned_model.txt'), 'r', encoding='utf-8') as rf:
                    candidate = rf.read().strip()
                    if candidate:
                        model_name = candidate
            except Exception:
                # file missing or unreadable; ignore and fall back
                pass
        if not model_name:
            model_name = 'gpt-4o-mini'
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
        payload = {
            'model': model_name,
            'messages': [
                {'role': 'system', 'content': 'You are a poetic writing companion for a poetry website. Keep replies warm, supportive, and short but thoughtful.'},
                {'role': 'user', 'content': message}
            ],
            'max_tokens': 220
        }
        try:
            resp = requests.post('https://api.openai.com/v1/chat/completions', json=payload, headers=headers, timeout=15)
            resp.raise_for_status()
            j = resp.json()
            # robustly extract content for chat or older completion formats
            content = None
            if 'choices' in j and j['choices']:
                first = j['choices'][0]
                if isinstance(first.get('message'), dict):
                    content = first['message'].get('content')
                else:
                    content = first.get('text')
            if not content:
                raise ValueError('no content in response')
            return jsonify({'reply': content})
        except Exception:
            current_app.logger.exception('AI request failed; using local poem companion fallback')
            return jsonify({'reply': local_poetry_reply(message)})

    return jsonify({'reply': local_poetry_reply(message)})
