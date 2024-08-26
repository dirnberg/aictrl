import logging
import yaml
from openai import OpenAI
import os
import time
from datetime import datetime
import coloredlogs



# Function to load content from a file
def load_file_content(file_path):
    with open(file_path, "r") as file:
        return file.read()

# Function to replace placeholders in the message content
def replace_placeholders(template, placeholders):
    for key, value in placeholders.items():
        template = template.replace(f"{{{{ {key} }}}}", value)
    return template

# Step 0

# Setup Logging
logging.basicConfig(
    level=logging.INFO,  # Set the logging level
    format="%(asctime)s - %(levelname)s - %(message)s")  # Set the logging format)

logger = logging.getLogger()  # Get the root logger (or create your own)

coloredlogs.install(
    level='INFO',  # Set the logging level
    logger=logger,  # Use the logger created above
    fmt="%(asctime)s - %(levelname)s - %(message)s",  # Define the format
    datefmt="%Y-%m-%d %H:%M:%S"  # Define the date format
)


### Achtung DBU3 
logger = logging.getLogger(__name__)
with open("dbu3.yml", "r") as config_file:
    config = yaml.safe_load(config_file)

logger.info(f"---------------------------")
logger.info(f">>> Step 1: Init System")
logger.info(f"Load configuration from config.yml done") 
logger.info(f"Setup Logging done")


logger.info(f"Initialize OpenAI Client")
# Initialize OpenAI Client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY') or config['openai_api_key'])

 # Step 1
logger.info(f">>> Step 1: Load or modify Assistant")
assistant_name = config['assistant']['name']
existing_assistants = client.beta.assistants.list()
assistant = next((a for a in existing_assistants if a.name == assistant_name), None)

if not assistant:
    logger.info("Assistant not found. Creating a new assistant...")
    assistant_instructions = load_file_content(config['assistant']['instructions_file'])
    assistant = client.beta.assistants.create(
        name=assistant_name,
        instructions=assistant_instructions,
        model=config['assistant']['model'],
        tools=config['assistant']['tools'],
        temperature=config['assistant']['parameters']['temperature'],
        top_p=config['assistant']['parameters']['top_p']
    )
    logger.info(f"Assistant created with ID: {assistant.id}")
else:
    logger.info(f"Using existing assistant with ID: {assistant.id}")
    # Update assistant parameters if necessary
    updated = False
    if assistant.model != config['assistant']['model']:
        assistant.model = config['assistant']['model']
        updated = True

    if assistant.tools != config['assistant']['tools']:
        assistant.tools = config['assistant']['tools']
        updated = True

    if updated:
        assistant = client.beta.assistants.update(
            assistant_id=assistant.id,
            model=assistant.model,
            tools=assistant.tools
        )
        logger.info(f"Assistant with ID {assistant.id} updated.")

 # Step 2
logger.info(f">>> Step 2: Load or modify Vector Store")
vector_store_name = config['vector_store']['name']
existing_vector_stores = client.beta.vector_stores.list()
vector_store = next((vs for vs in existing_vector_stores if vs.name == vector_store_name), None)

if not vector_store:
    logger.info("Vector Store not found. Creating a new vector store...")
    vector_store = client.beta.vector_stores.create(name=vector_store_name)
    file_paths = config['vector_store']['file_paths']
    file_streams = [open(path, "rb") for path in file_paths]
    file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vector_store.id, files=file_streams)
    logger.info(f"Files uploaded to Vector Store with ID: {vector_store.id}")
else:
    logger.info(f"Using existing Vector Store with ID: {vector_store.id}")

# Associate Vector Store with Assistant if not already associated
if 'file_search' not in assistant.tool_resources or vector_store.id not in [vs.id for vs in assistant.tool_resources.file_search.vector_stores]:
    logger.info("Associating Vector Store with Assistant...")
    assistant = client.beta.assistants.update(
        assistant_id=assistant.id,
        tool_resources={
            "file_search": {
                "vector_store_ids": [vector_store.id]
            }
        }
    )
    logger.info("Assistant updated to use Vector Store.")

 # Step 3
logger.info(f">>> Step 3: Execute each thread in threads")

for thread_config in config['threads']:
    thread_name = thread_config['name']
    logger.info(f"Executing thread: {thread_name}")
    
    # Load and prepare thread message content
    message_content = load_file_content(thread_config['message']['content_file'])
    message_content = replace_placeholders(message_content, thread_config['placeholders'])

    # Create a new thread
    thread = client.beta.threads.create()

    # Send thread message to the assistant
    message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role=thread_config['message']['role'],
        content=message_content
    )

    # Run the assistant thread with specific parameters and monitor progress
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id,
        temperature=thread_config.get('temperature', config['assistant']['parameters']['temperature']),
        top_p=thread_config.get('top_p', config['assistant']['parameters']['top_p']),
        #max_tokens=thread_config.get('max_tokens', config['assistant']['parameters']['max_tokens'])  # Add max_tokens here 
    )

    while True:
        current_run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if current_run.status in ['completed', 'failed', 'cancelled']:
            logger.info(f"Run status for thread '{thread_name}': {current_run.status}")
            break
        logger.info(f"Run status for thread '{thread_name}': {current_run.status}. Waiting for completion...")
        time.sleep(5)

    if current_run.status == 'completed':
        # Retrieve and process assistant's response
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        assistant_message = ""
        for message in messages:
            if message.role == 'assistant':
                content = message.content
                if isinstance(content, list):
                    for item in content:
                        assistant_message += str(item) + "\n"
                elif isinstance(content, str):
                    assistant_message += content + "\n"
                else:
                    logger.warning(f"Unexpected content type: {type(content)} in message: {message}")

        # Check if we should save the raw output
        if thread_config.get('output_file_path'):
            output_file_path = os.path.join("raw", thread_config['output_file_path'])
            with open(output_file_path, "w") as file:
                file.write(assistant_message)
            logger.info(f"Thread '{thread_name}' raw output saved to {output_file_path}.")
        
        logger.info(f"Combine the raw output using the completion prompt for each thread")
        
        if thread_config.get('completion'):
            logger.info(f"Running completion prompt for thread '{thread_name}'...")
            completion_prompt_template = load_file_content(thread_config['completion']['prompt_file'])
            completion_prompt = replace_placeholders(completion_prompt_template, thread_config['completion']['placeholders'])

            completion = client.chat.completions.create(
                model=thread_config['completion']['model'],
                messages=[
                    {"role": "user", "content": assistant_message},
                    {"role": "user", "content": completion_prompt}
                ],
                #max_tokens=thread_config['completion']['max_tokens'],
                temperature=thread_config['completion']['temperature'],
                top_p=thread_config['completion']['top_p'],
                frequency_penalty=thread_config['completion']['frequency_penalty'],
                presence_penalty=thread_config['completion']['presence_penalty']
            )

            formatted_markdown = completion.choices[0].message.content

            # Check if we should save the out output
        if thread_config.get('output_file_path'):
            output_file_path = os.path.join("out", thread_config['output_file_path'])
            with open(output_file_path, "w") as file:
                file.write(formatted_markdown)
            logger.info(f"Thread '{thread_name}' output saved to {output_file_path}.")
        
        logger.info(f"Thread '{thread_name}' completed")

    else:
        logger.error(f"Thread '{thread_name}' did not complete successfully. Status: {current_run.status}")
