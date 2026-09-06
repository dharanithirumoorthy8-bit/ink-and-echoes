import os
import json

"""
Prepare a JSONL file for OpenAI fine-tuning.

Usage:
  python prepare_finetune_jsonl.py [--out data/finetune.jsonl]

If no source dataset exists, this script will write a small example
dataset to `data/finetune.jsonl` so the user can run the upload script.
"""

OUT = os.path.join('data', 'finetune.jsonl')

os.makedirs('data', exist_ok=True)

examples = [
    {
        'prompt': 'Human: I am feeling very sad and cannot find words.\nAssistant:',
        'completion': " I hear your ache. Write one raw line about the feeling; we'll shape it together.\n"
    },
    {
        'prompt': 'Human: I want a short poem about a lost lover.\nAssistant:',
        'completion': " A single memory opens like a window; light falls and we remember.\n"
    },
    {
        'prompt': 'Human: Give me a friendly prompt to help write a poem.\nAssistant:',
        'completion': " Start with one image: a smell, a sound, or a color. Describe it plainly.\n"
    }
]

with open(OUT, 'w', encoding='utf-8') as f:
    for ex in examples:
        f.write(json.dumps({'prompt': ex['prompt'], 'completion': ex['completion']}, ensure_ascii=False) + '\n')

print(f'Wrote {OUT} with {len(examples)} examples. Edit or replace this file with your dataset.')
