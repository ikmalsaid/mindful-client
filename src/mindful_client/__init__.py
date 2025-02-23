import os
import ast
import json
import uuid
import time
import base64
import requests
import tempfile
from importlib import resources
from colorpaws import setup_logger
from datetime import datetime
from typing import Union, List

class MindfulClient:
    def __init__(self, mode='default', log_on=False, log_to=None, model='omniverse', save_to='outputs', save_as='json',
                 timeout=60, stream_output=True, stream_delay=0.01):
        """Initialize the MindfulClient.
        
        Parameters:
        - mode    (str): The mode to use ('default', 'chat', 'api', 'webui')
        - log_on (bool): Enable logging.
        - log_to  (str): Directory to save logs.
        - save_to (str): The directory to save the chat history (None to disable saving)
        - save_as (str): The format to save the chat history ('json', 'txt', 'md')
        - timeout (int): The timeout for each request
        - stream_output (bool): Stream output characters as they arrive
        - stream_delay (float): Delay between characters during streaming (default: 0.01s)
        """
        self.logger = setup_logger(
            name=self.__class__.__name__,
            log_on=log_on,
            log_to=log_to
        )

        self.version = "25.1"
        self.stream_output = stream_output
        self.stream_delay = stream_delay

        self.__online_check()
        self.__load_preset()
        self.__load_locale()
        
        self.__init_checks(save_to, save_as, model, timeout)        
        self.logger.info("Mindful Client is ready!")
        
        if mode != "default":
            self.__startup_mode(mode)

    def __init_checks(self, save_to: str, save_as: str, model: str, timeout: int):
        """

        Initialize essential checks.
        """
        try:
            if save_to is None:
                self.save_to = None
                self.save_as = None
                self.logger.warning("Chat history will not be saved!")
            else:
                self.save_to = save_to if save_to else tempfile.gettempdir()
                self.save_to = os.path.join(self.save_to, "mindful")
                
                # Only check save_as format if we're actually saving
                if save_as.lower() in ['json', 'txt', 'md']:
                    self.save_as = save_as.lower()
                else:
                    self.logger.warning("Invalid save_as format, defaulting to 'json'")
                    self.save_as = 'json'
            
            self.__model = self.__preset['model'][model]
            if not self.__model:
                raise ValueError(f"Invalid model: {model}")
            
            self.timeout = timeout
        
        except Exception as e:
            self.logger.error(f"Error in init_checks: {e}")
            raise

    def __startup_mode(self, mode: str):
        """
        Startup mode for api or webui with default values.
        """
        try:
            if mode == "webui":
                self.start_wui()
            
            elif mode == "api":
                self.start_api()
            
            elif mode == "chat":
                self.start_chat()
            
            else:
                raise ValueError(f"Invalid startup mode: {mode}")
        
        except Exception as e:
            self.logger.error(f"Error in startup_mode: {str(e)}")
            raise
    
    def __online_check(self, url: str = 'https://www.google.com', timeout: int = 10):
        """
        Check if there is an active internet connection.
        """
        try:
            requests.get(url, timeout=timeout)
        
        except Exception:
            self.logger.error("No internet! Please check your network connection.")
            raise

    def __load_preset(self, preset_path='mf.py'):
        """
        Load the preset file.
        """
        try:
            preset_file = resources.path(__name__, preset_path)
            with open(str(preset_file), encoding="utf-8") as f:
                content = f.read()
                self.__preset = json.loads(content)
        
        except Exception as e:
            self.logger.error(f"Error in load_preset: {e}")
            raise

    def __get_agent(self, agent: str, instruction: str = None):
        """
        Get the agent prompt, handling custom system prompts if provided.
        """
        try:
            agent_template = self.__preset["agent"][agent]
            
            # If this is a custom agent with instruction, format the template
            if agent == 'custom' and instruction:
                return agent_template.format(system_prompt=instruction)
            
            return agent_template
            
        except Exception as e:
            self.logger.error(f"Error in get_agent: {e}")
            raise

    def __load_locale(self):
        """
        Load the locales.
        """
        try:
            self.__hd = {'bearer': base64.b64decode(self.__preset["locale"][0]).decode('utf-8')}
            self.__ur = base64.b64decode(self.__preset["locale"][1]).decode('utf-8')
            self.__up = base64.b64decode(self.__preset["locale"][2]).decode('utf-8')
            
        except Exception as e:
            self.logger.error(f"Error in load_locale: {e}")
            raise

    def __upload_image(self, image_path: str) -> str:
        """
        Upload an image to the server and return the URL.
        """
        try:
            with open(image_path, 'rb') as image_file:
                files = {'files': ('file.jpg', image_file, 'image/jpeg')}
                response = requests.post(self.__up, files=files, headers=self.__hd)
                response.raise_for_status()
                result = response.json().get('file.jpg')
                return result
        
        except Exception as e:
            self.logger.error(f"Error in upload_image: {e}")
            raise


    def __get_task_id(self):
        """
        Generate a unique task ID for request tracking.
        Returns a combination of timestamp and UUID to ensure uniqueness.
        Format: YYYYMMDD_HHMMSS_UUID8
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            uuid_part = str(uuid.uuid4())[:8]
            task_id = f"{timestamp}_{uuid_part}"
            return task_id
        
        except Exception as e:
            self.logger.error(f"Error in get_task_id: {e}")
            raise

    def __convert_chat(self, history: list, file_path: str, format: str):
        """
        Convert chat history to specified format while preserving JSON.
        Supports: txt, md
        """
        try:
            base_path = os.path.splitext(file_path)[0]
            task_id = history[0].get('id', 'unknown')
            
            if format == 'txt':
                output = [f"Chat History (ID: {task_id})\n\n"]
                for msg in history:
                    role = msg.get('role', '')
                    content = msg.get('content', '')
                    
                    # Handle different content types
                    if isinstance(content, list):
                        text_parts = []
                        for item in content:
                            if item.get('type') == 'text':
                                text_parts.append(item.get('text', ''))
                            elif item.get('type') == 'image_url':
                                text_parts.append(f"[Image: {item.get('file_url', {}).get('url', 'No URL')}]")
                        content = ' '.join(text_parts)
                        
                    output.append(f"{role.upper()}: {content}\n")
                
                with open(f"{base_path}.txt", 'w', encoding='utf-8') as f:
                    f.writelines(output)
                    
            elif format == 'md':
                output = [f"# Chat History (ID: {task_id})\n\n"]
                for msg in history:
                    role = msg.get('role', '')
                    content = msg.get('content', '')
                    
                    # Handle different content types
                    if isinstance(content, list):
                        text_parts = []
                        for item in content:
                            if item.get('type') == 'text':
                                text_parts.append(item.get('text', ''))
                            elif item.get('type') == 'image_url':
                                url = item.get('file_url', {}).get('url', 'No URL')
                                text_parts.append(f"\n![Image]({url})\n")
                        content = '\n'.join(text_parts)
                        
                    output.append(f"### {role.title()}\n{content}\n\n")
                
                with open(f"{base_path}.md", 'w', encoding='utf-8') as f:
                    f.writelines(output)
            
            self.logger.info(f"[{task_id}] Successfully converted chat to {format} format")
            
        except Exception as e:
            self.logger.error(f"Error in convert_chat: {e}")
            raise


    def __save_history(self, history: list):
        """
        Save the chat history to a file organized by date and task ID.
        """
        if self.save_to is None:
            return
            
        try:
            task_id = history[0].get('id', 'unknown')
            
            date_part = task_id.split('_')[0]
            formatted_date = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
            
            chat_dir = os.path.join(self.save_to, formatted_date)
            os.makedirs(chat_dir, exist_ok=True)
            
            file_path = os.path.join(chat_dir, f'{task_id}.json')
            
            # Check if file exists and load existing history
            if os.path.exists(file_path):
                self.logger.info(f"[{task_id}] Updating existing chat history file")
                try:
                    with open(file_path, 'r') as f:
                        existing_history = json.load(f)
                        
                    # Compare and append only new messages
                    existing_len = len(existing_history)
                    new_messages = history[existing_len:]
                    if new_messages:
                        existing_history.extend(new_messages)
                        history = existing_history
                
                except json.JSONDecodeError:
                    self.logger.warning(f"[{task_id}] Existing file was corrupted, overwriting")
            else:
                self.logger.info(f"[{task_id}] Creating new chat history file")


            with open(file_path, 'w') as f:
                json.dump(history, f, indent=2)
            self.logger.info(f"[{task_id}] Successfully saved JSON chat history")
            
            try:
                if self.save_as != 'json':
                    self.__convert_chat(history, file_path, self.save_as)
            
            except Exception as conv_error:
                raise Exception(f"[{task_id}] Failed to convert chat to {self.save_as} format: {conv_error}")
            
            self.logger.info(f"[{task_id}] Chat history save process completed")

        except Exception as e:
            self.logger.error(f"[{task_id}] Error in save_history: {e}")
            raise

    def __switch_agent(self, agent: str, instruction: str = None):
        """
        Switch to a different agent mid-conversation.
        
        Parameters:
        - agent (str): The new agent to use
        - instruction (str): Optional custom system prompt
        """
        try:
            if instruction:
                self.logger.info("Custom system prompt provided, switched to custom agent")
                agent = 'custom'
            
            self.__agent = self.__get_agent(agent, instruction)
            self.logger.info(f"Switched to {agent} agent")
            return self.__agent
            
        except Exception as e:
            self.logger.error(f"Error switching agent: {e}")
            raise

    def __stream_response(self, response, stream_text=""):
        """
        Process the streaming response and return the full response.
        
        Parameters:
        - response: Response object from the API
        - stream_text: Initial stream content
        """
        try:
            buffer = ""
            
            for chunk in response.iter_content(chunk_size=1024):
                if not chunk:
                    continue
                    
                buffer += chunk.decode('utf-8')
                lines = buffer.split('\n')
                
                for line in lines[:-1]:
                    if line.strip() and line.startswith('data: '):
                        try:
                            data = json.loads(line[6:])
                            if 'content' in data:
                                new_content = data['content']
                                stream_text += new_content
                                if self.stream_output:
                                    for char in new_content:
                                        print(char, end='', flush=True)
                                        time.sleep(self.stream_delay)
                        except json.JSONDecodeError:
                            self.logger.debug(f"Incomplete JSON chunk: {line}")
                            continue
                
                buffer = lines[-1]
            
            # Process remaining buffer
            if buffer.strip() and buffer.startswith('data: '):
                try:
                    data = json.loads(buffer[6:])
                    if 'content' in data:
                        new_content = data['content']
                        stream_text += new_content
                        if self.stream_output:
                            for char in new_content:
                                print(char, end='', flush=True)
                                time.sleep(self.stream_delay)
                except json.JSONDecodeError:
                    self.logger.debug(f"Incomplete final JSON chunk: {buffer}")
            
            if self.stream_output:
                print()
            return stream_text.strip('"')
            
        except Exception as e:
            self.logger.error(f"Error in stream_response: Unexpected error!")
            return None

    def load_history(self, file_path: str):
        """
        Load chat history from a JSON file.
        
        Parameters:
        - file_path (str): Path to the JSON file containing chat history
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                history = json.load(f)
                
            if not isinstance(history, list) or not history:
                raise ValueError("Invalid chat history format")
                
            # Validate required fields in first message
            first_msg = history[0]
            required_fields = ['id', 'role', 'content', 'model']
            if not all(field in first_msg for field in required_fields):
                raise ValueError("Chat history missing required fields")
                
            self.logger.info(f"[{first_msg['id']}] Loaded chat history with {len(history)} messages")
            return history

        except Exception as e:
            self.logger.error(f"Error in load_history: {e}")
            raise

    def get_completions(self, prompt, image_path=None, history=None, agent: str = 'default', instruction: str = None):
        """
        Integrated chat function supporting multimodal conversations (text and images).
        
        Parameters:
        - prompt (str): The user's input prompt
        - image_path (str): Optional path to image file or list of image paths
        - history (list): Optional chat history for continuing conversations
        - agent (str): Agent to use ('default' or 'custom')
        - instruction (str): Custom system prompt (will change agent to 'custom')
        """
        if history is not None and not isinstance(history, list):
            raise ValueError("History must be a list or None")
        
        if image_path is not None and not isinstance(image_path, (str, list)):
            raise ValueError("image_path must be a string or list")
        
        try:
            start_time = time.time()
            task_id = None
            
            # Handle custom instructions
            if instruction:
                if agent != 'custom':
                    self.logger.info("Custom instructions used. Switching to 'custom' agent")
                agent = 'custom'
            
            # Check if agent/instruction has changed from current history
            agent_changed = False
            if history and len(history) > 0:
                current_system = history[0]['content']
                new_system = self.__get_agent(agent, instruction if agent == 'custom' else None)
                agent_changed = current_system != new_system
                
                if not agent_changed:
                    self.logger.info("Using existing agent - no system prompt change needed")
                else:
                    self.logger.info("Agent/instruction changed - updating system prompt")
            
            # Only create new history if agent changed or no history exists
            if agent_changed or not history:
                system_prompt = self.__get_agent(agent, instruction if agent == 'custom' else None)
                
                new_history = [{
                    "id": self.__get_task_id() if not history else history[0].get('id'),
                    "role": "system",
                    "content": system_prompt,
                    "model": self.__model
                }]
                
                # Transfer existing conversation messages if they exist
                if history and len(history) > 1:
                    new_history.extend([msg for msg in history[1:] if msg['role'] in ('user', 'assistant')])
                    self.logger.info(f"Transferred {len(new_history)-1} messages to new history with updated agent")
                
                history = new_history
                
            task_id = history[0]['id']
            
            message_content = []
            
            if prompt:
                message_content.append({
                    "type": "text",
                    "text": prompt
                })
            
            if image_path:
                if isinstance(image_path, str):
                    image_paths = [image_path]
                elif isinstance(image_path, (list, tuple)):
                    image_paths = image_path
                else:
                    raise ValueError("image_path must be a string or list of strings")
                
                for img_path in image_paths:
                    image_url = self.__upload_image(img_path)
                    message_content.append({
                        "type": "image_url",
                        "file_url": {"url": image_url}
                    })
                    self.logger.info(f"[{task_id}] Added image to message content: {img_path}")
            
            history.append({
                "id": task_id,
                "role": "user",
                "content": message_content,
                "model": self.__model
            })
            self.logger.info(f"[{task_id}] Added user message to chat history")
            
            data = json.dumps({
                "id": task_id,
                "messages": history,
                "model": self.__model,
                "stream": False
            })
            
            files = {
                'model_version': (None, '1'),
                'data': (None, data)
            }
            
            self.logger.info(f"[{task_id}] Processing request in {self.timeout} seconds")
            with requests.post(self.__ur, files=files, headers=self.__hd, stream=True, timeout=self.timeout) as response:
                response.raise_for_status()
                response_text = self.__stream_response(response)
            
            history.append({
                "id": task_id,
                "role": "assistant",
                "content": response_text,
                "model": self.__model
            })
            
            self.__save_history(history)
            self.logger.info(f"[{task_id}] Request completed in {time.time() - start_time:.2f} seconds")
            
            return response_text, history

        except Exception as e:
            self.logger.error(f"Error in get_completions: Unexpected error!")
            return None, history
        
    def start_chat(self, agent: str = 'default', instruction: str = None):
        """
        Start an interactive chat session in the console.
        
        Commands:
        - /exit: Exit the chat
        - /reset: Reset the conversation
        - /agent "agent_name": Change the agent (default/custom)
        - /image "path" "question" or ["path1", "path2"] "question" - Send image(s) with optional question
        - /instruction "new instruction": Change the system instruction
        - /load "path/to/history.json": Load chat history from file
        - /help: Show available commands
        
        Parameters:
        - agent (str): Starting agent ('default' or 'custom')
        - instruction (str): Optional custom system prompt (will set agent to 'custom')
        - stream (bool): If True, streams the response character by character
        """
        history = None
        task_id = None
        
        # Initialize with the correct agent prompt
        current_agent = agent
        current_instruction = instruction
        
        # Ensure we load the correct system prompt at start
        try:
            self.__switch_agent(current_agent, current_instruction)
        except Exception as e:
            print(f"\nError initializing agent: {e}")
            return

        def print_help():
            print("\nAvailable commands:")
            print("  /exit - Exit the chat")
            print("  /reset - Reset the conversation")
            print("  /agent \"agent_name\" - Change the agent (default/custom)")
            print("  /image \"path\" \"question\" or [\"path1\", \"path2\"] \"question\" - Send image(s) with optional question")
            print("  /instruction \"new instruction\" - Change system instruction")
            print("  /load \"path/to/history.json\" - Load chat history from a JSON file")
            print("  /help - Show this help message")
            
            if self.save_to and self.save_as:
                print(f"\nChat history is saved to: {self.save_to}/*.{self.save_as}\n")
            else:
                print("\nWarning: Chat history will not be saved!\n")
        
        def parse_quoted_content(text: str) -> str:
            """Extract content between quotes."""
            import re
            match = re.search(r'"([^"]*)"', text)
            return match.group(1) if match else None
        
        def parse_image_command(text: str) -> tuple[Union[str, List[str], None], str]:
            """Parse image path(s) and question from command."""
            content = text.strip()
            
            # Extract question if present (everything after the last quotation mark pair)
            question = None
            path_part = content
            
            # Look for quoted question at the end
            if '"' in content:
                last_quote_pair = content.rfind('"')
                second_last_quote = content.rfind('"', 0, last_quote_pair)
                if second_last_quote != -1:
                    question = content[second_last_quote + 1:last_quote_pair].strip()
                    path_part = content[:second_last_quote].strip()
            
            # Parse image paths
            if path_part.startswith('['):
                try:
                    paths = ast.literal_eval(path_part)
                    if isinstance(paths, list) and all(isinstance(p, str) for p in paths):
                        return paths, question or "Please analyze this image"
                    print("Invalid image path list format")
                    return None, None
                except:
                    print("Invalid image path list format")
                    return None, None
            else:
                # Single path
                path = path_part.strip('"').strip()
                if path and os.path.exists(path):
                    return path, question or "Please analyze this image"
                print(f"Image file not found: {path}")
                return None, None

        def reset_chat():
            nonlocal history, task_id
            history = None
            task_id = None
            print("\nChat reset. Starting new conversation...")
            if current_agent != 'default' or current_instruction:
                print(f"Current agent: {current_agent}")
                if current_instruction:
                    print(f"Current instruction: {current_instruction}")
            print()

        print(f"*** Welcome to Mindful Client {self.version} ***")
        print("Type '/help' for available commands\n")
        
        if self.save_to and self.save_as:
            print(f"Chat history will be saved to: '{self.save_to}' as '*.{self.save_as}'")
        else:
            print("Warning: Chat history will not be saved!")
            
        print("Type your message or command below:\n")

        while True:
            try:
                user_input = input("You: ").strip()
                
                # Handle commands
                if user_input.lower() == '/exit':
                    print("Ending chat session...")
                    if task_id:
                        print(f"Chat history saved with ID: {task_id}")
                    break
                    
                elif user_input.lower() == '/help':
                    print_help()
                    continue
                    
                elif user_input.lower() == '/reset':
                    reset_chat()
                    continue
                    
                elif user_input.lower().startswith('/agent'):
                    new_agent = parse_quoted_content(user_input[6:])
                    if new_agent in ['default', 'custom']:
                        current_agent = new_agent
                        # Update the agent in the client
                        self.__switch_agent(new_agent, current_instruction)
                        print(f"Switched to agent: {new_agent}")
                    else:
                        print("Invalid agent. Available agents: default, custom")
                    continue
                    
                elif user_input.lower().startswith('/image'):
                    image_content = user_input[6:].strip()
                    image_paths, question = parse_image_command(image_content)
                    if image_paths:
                        # Use current agent/instruction without switching
                        response, history = self.get_completions(
                            prompt=question,
                            image_path=image_paths,
                            history=history,
                            agent=current_agent,
                            instruction=current_instruction
                        )
                        if response:
                            print(f"\nAssistant: {response}\n")
                        if not task_id and history:
                            task_id = history[0].get('id')
                            print(f"Chat ID: {task_id}\n")
                    continue
                    
                elif user_input.lower().startswith('/instruction'):
                    new_instruction = parse_quoted_content(user_input[12:])
                    if new_instruction:
                        current_instruction = new_instruction
                        current_agent = 'custom'
                        # Update the agent with new instruction without resetting history
                        self.__switch_agent('custom', new_instruction)
                        print(f"Updated system instruction.")
                    continue
                    
                elif user_input.lower().startswith('/load'):
                    history_path = parse_quoted_content(user_input[5:])
                    if history_path:
                        try:
                            loaded_history = self.load_history(history_path)
                            if loaded_history:
                                history = loaded_history
                                task_id = history[0].get('id')
                                # Update current agent/instruction from loaded history
                                system_msg = history[0].get('content', '')
                                if system_msg == self.__get_agent('custom', current_instruction):
                                    current_agent = 'custom'
                                else:
                                    current_agent = 'default'
                                print(f"\nLoaded chat history with ID: {task_id}")
                                print(f"Current agent: {current_agent}")
                                if current_agent == 'custom':
                                    print(f"Current instruction: {current_instruction}\n")
                        except Exception as e:
                            print(f"\nError loading history: {str(e)}")
                    continue
                    
                # Regular message
                if user_input:
                    if self.stream_output:
                        print("\nAssistant: ", end='', flush=True)
                    response, history = self.get_completions(
                        prompt=user_input,
                        history=history,
                        agent=current_agent,
                        instruction=current_instruction
                    )
                    if response and not self.stream_output:
                        print(f"\nAssistant: {response}\n")
                    elif response and self.stream_output:
                        print()
                    if not task_id and history:
                        task_id = history[0].get('id')
                        print(f"Chat ID: {task_id}\n")
                
            except KeyboardInterrupt:
                print("\nEnding chat session...")
                if task_id and self.save_to:
                    print(f"Chat history saved with ID: {task_id}")
                break
                
            except Exception as e:
                print(f"\nError: {str(e)}")
                print("Try again or type '/exit' to end the chat\n")
