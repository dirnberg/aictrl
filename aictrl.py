import os
import openai
import logging
import yaml
from datetime import datetime
import re
import time
import argparse
import shutil
shutil.copy

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize global variables for data transfer measurement
total_data_sent, total_data_received = 0, 0

def load_config(file_path):
    try:
        with open(file_path, 'r') as file:
            return yaml.safe_load(file)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return None

def ensure_directory_exists(directory_path):
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

def apply_placeholders(template, placeholders):
    for key, value in placeholders.items():
        template = template.replace(f"{{{{ {key} }}}}", value)
    return template

def generate_filename(prefix, assistant_name, max_length=12):
    sanitized_name = re.sub(r'[^a-zA-Z0-9]', '_', assistant_name)[:max_length].rstrip('_')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{timestamp}_{sanitized_name}.md"

def handle_openai_error(func):
    def wrapper(*args, **kwargs):
        global total_data_sent, total_data_received
        for _ in range(3):
            try:
                response = func(*args, **kwargs)
                if response:
                    total_data_received += len(str(response))
                return response
            except Exception as e:
                logger.error(f"OpenAI API error: {e}. Retrying...")
                time.sleep(2)
        logger.error("Failed after retries.")
        return None
    return wrapper

@handle_openai_error
def get_or_create_assistant(client, params):
    assistants = client.beta.assistants.list().data
    assistant = next((a for a in assistants if a.name == params['name']), None)
    if assistant:
        logger.info(f"Assistant '{params['name']}' found.")
        return assistant
    new_assistant = client.beta.assistants.create(
        name=params['name'],
        instructions=params['instructions'],
        model=params['model'],
        tools=params['tools']
    )
    logger.info(f"Created new assistant '{params['name']}' with ID: {new_assistant.id}")
    return new_assistant

@handle_openai_error
def get_or_create_vector_store(client, name):
    vector_stores = client.beta.vector_stores.list().data
    vector_store = next((vs for vs in vector_stores if vs.name == name), None)
    if vector_store:
        logger.info(f"Vector store '{name}' found.")
        return vector_store
    new_vector_store = client.beta.vector_stores.create(name=name)
    logger.info(f"Created vector store '{name}' with ID: {new_vector_store.id}")
    return new_vector_store

@handle_openai_error
def create_thread(client, assistant, query, attachment_paths):
    attachments = []
    for path in attachment_paths:
        try:
            with open(path, "rb") as file:
                file_id = client.files.create(file=file, purpose="assistants").id
                attachments.append({"file_id": file_id, "tools": [{"type": "file_search"}]})
        except Exception as e:
            logger.error(f"Error uploading attachment '{path}': {e}")
    thread = client.beta.threads.create(
        messages=[{"role": "user", "content": query, "attachments": attachments}]
    )
    logger.info(f"Created thread with ID: {thread.id}")
    return thread

@handle_openai_error
def run_assistant_and_get_output(client, assistant, thread, chat_params):
    run = client.beta.threads.runs.create_and_poll(thread_id=thread.id, assistant_id=assistant.id)
    messages = client.beta.threads.messages.list(thread_id=thread.id, run_id=run.id).data
    output = "\n\n".join(f"## {msg.role.capitalize()} Message:\n{msg.content}" for msg in messages)
    logger.info(f"Model used: {run.model}")
    return output

def convert_text_to_markdown(client, input_file, output_file, params):
    try:
        with open(input_file, 'r') as file:
            input_content = file.read().strip()
        prompt_template = open(params['prompt_file_path'], 'r').read()
        prompt = apply_placeholders(prompt_template, params['placeholders']) + f"\n\nText to format:\n\n{input_content}"
        completion = client.chat.completions.create(
            model=params['model'],
            messages=[{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}],
            max_tokens=params['max_tokens'],
            temperature=params['temperature'],
            top_p=params['top_p'],
            frequency_penalty=params['frequency_penalty'],
            presence_penalty=params['presence_penalty']
        )
        with open(output_file, 'w') as file:
            file.write(completion.choices[0].message.content)
    except Exception as e:
        logger.error(f"Error converting text to Markdown: {e}")

def main():
    parser = argparse.ArgumentParser(description="Run the OpenAI Assistant Script")
    parser.add_argument('config', type=str, help='Path to the configuration YAML file')
    args = parser.parse_args()

    config = load_config(args.config)
    if not config:
        return

    api_key = config.get('api_key')
    if not api_key:
        logger.error("Invalid API key.")
        return
    openai.api_key = api_key

    client = openai.Client()
    global total_data_sent, total_data_received
    start_time = datetime.now()

    assistant_params = config['assistant']
    chat_params = config['chat_completion']
    thread_params = config['thread']
    folders = config['folders']

    ensure_directory_exists(folders['raw'])
    ensure_directory_exists(folders['outputs'])

    instructions_file_path = assistant_params.get('instructions_file_path')
    if not os.path.isfile(instructions_file_path):
        logger.error(f"Instructions file '{instructions_file_path}' not found.")
        return

    query_file_path = thread_params.get('query_file_path')
    if not os.path.isfile(query_file_path):
        logger.error(f"Query file '{query_file_path}' not found.")
        return

    instructions = open(instructions_file_path, 'r').read()
    query = open(query_file_path, 'r').read()

    assistant = get_or_create_assistant(client, {
        'name': assistant_params['name'],
        'instructions': instructions,
        'model': assistant_params['model'],
        'tools': assistant_params['tools']
    })
    if not assistant:
        return

    vector_store = get_or_create_vector_store(client, config['vector_store']['name'])
    if not vector_store:
        return

    thread = create_thread(client, assistant, query, thread_params['attachment_paths'])
    if not thread:
        return

    raw_output = run_assistant_and_get_output(client, assistant, thread, chat_params)
    if not raw_output:
        return

    raw_output_filename = generate_filename("raw", assistant_params['name'])
    raw_output_path = os.path.join(folders['raw'], raw_output_filename)
    with open(raw_output_path, 'w') as raw_file:
        raw_file.write(raw_output)
    logger.info(f"Raw output saved to '{raw_output_path}'.")

    try:
        last_raw_output_path = os.path.join(folders['raw'], 'last_raw_output.md')
        shutil.copy(raw_output_path, last_raw_output_path)
        logger.info(f"Last raw output saved to '{last_raw_output_path}'.")
    except FileNotFoundError as e:
        logger.error(f"File not found during renaming: {e}")

    markdown_output_filename = generate_filename("formatted", assistant_params['name'])
    markdown_output_path = os.path.join(folders['outputs'], markdown_output_filename)
    convert_text_to_markdown(client, last_raw_output_path, markdown_output_path, chat_params)

    try:
        last_output_path = os.path.join(folders['outputs'], 'last_output.md')
        shutil.copy(markdown_output_path, last_output_path)
        logger.info(f"Last formatted output saved to '{last_output_path}'.")
    except FileNotFoundError as e:
        logger.error(f"File not found during renaming: {e}")

    end_time = datetime.now()
    runtime = end_time - start_time
    logger.info(f"=== Final Summary ===\nTotal runtime: {runtime}\n"
                f"Total data sent to OpenAI: {total_data_sent / 1024:.2f} KB\n"
                f"Total data received from OpenAI: {total_data_received / 1024:.2f} KB")

if __name__ == "__main__":
    main()
