import os
import time
import openai
import sys

OV = getattr(openai, '__version__', None)

def using_legacy():
    return OV is not None and OV.split('.')[0] == '0'


"""
Upload `data/finetune.jsonl` and create an OpenAI fine-tune job.

Requirements: set `OPENAI_API_KEY` in the environment.

Usage:
  python fine_tune_openai.py

On success it will print the fine-tuned model name and write it to
`instance/fine_tuned_model.txt` for `ai.py` to pick up via `FINE_TUNED_MODEL`.
"""

DATA_PATH = os.path.join('data', 'finetune.jsonl')
os.makedirs('instance', exist_ok=True)

api_key = os.environ.get('OPENAI_API_KEY')
if not api_key:
    raise SystemExit('Please set OPENAI_API_KEY in the environment before running.')
if not os.path.exists(DATA_PATH):
    raise SystemExit(f'Data file not found: {DATA_PATH}. Run prepare_finetune_jsonl.py first.')

base_model = os.environ.get('FINE_TUNE_BASE_MODEL') or 'gpt-4o-mini'

print('Uploading training file...')

try:
    if using_legacy():
        # legacy openai client (0.28.x)
        openai.api_key = api_key
        with open(DATA_PATH, 'rb') as f:
            uploaded = openai.File.create(file=f, purpose='fine-tune')
        file_id = uploaded['id']
        print('Uploaded file id:', file_id)
        print('Creating fine-tune job (legacy client) ...')
        ft = openai.FineTune.create(training_file=file_id, model=base_model)
        ft_id = ft['id']

        # Poll status
        while True:
            status = openai.FineTune.retrieve(ft_id)
            s = status['status']
            print('status:', s)
            if s in ('succeeded', 'failed'):
                break
            time.sleep(10)

        if status['status'] == 'succeeded':
            fine_model = status['fine_tuned_model']
            print('Fine-tune succeeded. Model name:', fine_model)
            with open(os.path.join('instance', 'fine_tuned_model.txt'), 'w', encoding='utf-8') as w:
                w.write(fine_model)
            print('Wrote instance/fine_tuned_model.txt — set FINE_TUNED_MODEL to this value in production.')
        else:
            print('Fine-tune failed. See the OpenAI dashboard for details.')

    else:
        # modern OpenAI Python client (>=1.0)
        try:
            from openai import OpenAI
        except Exception:
            raise SystemExit('openai>=1.0 detected but OpenAI client class not available.\nPlease ensure the package is correctly installed.')
        client = OpenAI(api_key=api_key)
        with open(DATA_PATH, 'rb') as f:
            uploaded = client.files.create(file=f, purpose='fine-tune')
        # uploaded may be a dict-like or object; try both
        file_id = uploaded.get('id') if isinstance(uploaded, dict) else getattr(uploaded, 'id', None)
        print('Uploaded file id:', file_id)
        print('Creating fine-tune job (modern client) ...')
        ft = client.fine_tunes.create(training_file=file_id, model=base_model)
        ft_id = ft.get('id') if isinstance(ft, dict) else getattr(ft, 'id', None)
        print('Fine-tune job id:', ft_id)

        # Poll status
        while True:
            status = client.fine_tunes.retrieve(ft_id)
            s = status.get('status') if isinstance(status, dict) else getattr(status, 'status', None)
            print('status:', s)
            if s in ('succeeded', 'failed'):
                break
            time.sleep(10)

        final_status = status.get('status') if isinstance(status, dict) else getattr(status, 'status', None)
        if final_status == 'succeeded':
            fine_model = status.get('fine_tuned_model') if isinstance(status, dict) else getattr(status, 'fine_tuned_model', None)
            print('Fine-tune succeeded. Model name:', fine_model)
            with open(os.path.join('instance', 'fine_tuned_model.txt'), 'w', encoding='utf-8') as w:
                w.write(fine_model)
            print('Wrote instance/fine_tuned_model.txt — set FINE_TUNED_MODEL to this value in production.')
        else:
            print('Fine-tune failed. See the OpenAI dashboard for details.')

except Exception as e:
    print('An error occurred during fine-tune flow:')
    # Print concise error and suggest steps
    print(repr(e))
    print('\nIf this is an API key error, revoke and create a new key at https://platform.openai.com/account/api-keys')
    sys.exit(1)
