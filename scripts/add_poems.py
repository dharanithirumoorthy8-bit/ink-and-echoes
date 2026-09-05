import os
import sys

# Ensure project root is on sys.path so imports like `from app import create_app` work
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from models import db, Poem, Category
from auth import get_admin_user

POEMS = [
    {
        'title': 'Symmetry of a Broken Pulse',
        'category': 'sacrifice,grief',
        'body': '''I mothered the dreams of a young-heart boy,
Building the halls where he could safely sleep.
I was the architect, the soul, the joy,
With promises I wasn’t meant to keep.
A double-sided sun that turned to gray,
He closed the book as casual as a breath;
I stayed behind to sweep the dust away,
And tended ghosts within a house of death.
I sacrificed my path to guard his light,
A silent witness in a town of stone.
I whispered truths into the void of night,
To ensure he’d never have to be alone.
Then came the second—peace within his hand,
Who claimed to heal the scars the first had left;
But sanctuary was a house of sand,
And mercy was a blade, both sharp and deft.
He used my history to wound the air,
Turning my nurturing to bitter debt.
I gave the last of all I had to spare,
Until the sun of my own spirit set.
Two phones both rang with news of heavy cost,
A tired heartbeat finding final rest;
They didn’t know the mother they had lost,
Until the bird had flown the empty nest.''',
    },
    {
        'title': 'The Art of Love',
        'category': 'love,family,gratitude',
        'body': '''When the world doubted what I could do,
You held my hand and said, "I believe in you."
Through the hard days and the lonely tears,
Your quiet voice chased away my fears.
When my plans failed and things went wrong,
You told me it’s okay, you kept me strong.
You promised to guide me, come what may,
And helped me find an evergreen way.
Now, when you see me win and smile,
I see your eyes light up for a while.
You don't ask for much, you just want to see
The happiest version of who I can be.
Though friends may fade and people change,
Your constant love is my saving grace.
For everything you do, and all that you are,
You are my world, my brightest star.''',
    },
    {
        'title': 'The Beauty of Recompile',
        'category': 'growth',
        'body': '''I held a crowded room within my heart,
Where laughter played its simple part.
But shadows fell—the trust, the lies,
And silence grew beneath the skies.
My circle faded, one by one,
Like dusk before the setting sun.
I wandered through my lonely days,
Lost within the dark of days.
I took the wrong turns, one by one,
And left behind the things I’d won.
Struggling hard to find my way,
Through all the mess of yesterday.
But then I chose to start again,
To wash away the hidden pain.
I dropped the paths that led to grief,
And found a sense of relief.
I’m fixing all the things I broke,
Stepping out from all the smoke.
I’m on the right track, clear and bright,
Guided by my own new light.
The struggle taught me how to grow,
To heal the hurt and let it go.
It’s a brand new start, a bolder mile—
The beauty of my own recompile.''',
    },
    {
        'title': 'The Moon Knew Us First',
        'category': 'love',
        'body': '''The moon knew us first,
long before the world
gave us names to remember.

It watched two wandering souls
carry the same quiet ache,
believing loneliness
was their only language.

Then somehow,
without asking the stars,
without pleading with time,
my heart found yours
like a river
remembering its sea.

You never felt
like a beginning.

You felt like
something my soul
had been searching for
long before
my eyes learned
how to recognize you.

Even now,
when distance stretches
between our days,
I do not fear it.

The moon still rises,
the sky still remembers,
and somewhere beyond
everything we cannot explain,
our souls are still
walking toward each other.

Perhaps that is
what destiny has always been—

not two strangers
falling in love,

but two souls
finding their way back

to the place

they never truly left.''',
    }
]


def normalize_text(s):
    return ' '.join((s or '').strip().split()).lower()


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
        try:
            get_admin_user()
        except Exception:
            pass

        for item in POEMS:
            title = item['title'].strip()
            body = item['body'].strip()
            category_names = [c.strip() for c in item.get('category','').split(',') if c.strip()]
            normalized_title = normalize_text(title)
            normalized_body = normalize_text(body)

            # check for duplicate
            exists = False
            for p in Poem.query.all():
                if normalize_text(p.title) == normalized_title and normalize_text(p.body) == normalized_body:
                    print(f"Skipping duplicate: {title}")
                    exists = True
                    break
            if exists:
                continue

            # create or get category (use first category if provided)
            category = None
            if category_names:
                cat_name = category_names[0]
                category = Category.query.filter_by(name=cat_name).first()
                if not category:
                    category = Category(name=cat_name)
                    db.session.add(category)
                    db.session.flush()

            poem = Poem(title=title, body=body, category_id=category.id if category else None, published=True)
            db.session.add(poem)
            db.session.commit()
            print(f"Inserted poem: {title} (id={poem.id})")

    print('Done inserting poems.')
