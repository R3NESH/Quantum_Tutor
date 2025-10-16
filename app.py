# Enhanced Quantum Tutor Web Dashboard - Combined & Corrected
from dotenv import load_dotenv
load_dotenv()

import sys
import os
import time
import json
import re
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
from groq import Groq
from typing import List, Dict, Any

# This will be False when running in Docker, as intended.
IN_COLAB = False

# ==============================================================================
# PART 1: CORE AGENT LOGIC (From your Jupyter Notebook)
# ==============================================================================

class Agent:
    """Base Agent Definition"""
    def run(self, message: str, **kwargs):
        raise NotImplementedError

class ConversationMemory:
    """Manages the conversation history and context."""
    def __init__(self, max_history: int = 10):
        self.history: List[Dict[str, Any]] = []
        self.max_history = max_history
        self.session_start = datetime.now()

    def add_interaction(self, user_message: str, bot_response: str, category: str, metadata: Dict = None):
        interaction = {
            'timestamp': datetime.now().isoformat(),
            'user_message': user_message,
            'bot_response': bot_response,
            'category': category,
            'metadata': metadata or {}
        }
        self.history.append(interaction)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def get_context_summary(self) -> str:
        if not self.history:
            return "This is the start of our conversation."
        recent_topics = [f"({i['category']}): {i['user_message'][:50]}..." for i in self.history[-3:]]
        return f"Recent conversation context: {'; '.join(recent_topics)}"

    def get_learning_progress(self) -> Dict[str, int]:
        categories = {}
        for interaction in self.history:
            cat = interaction['category']
            categories[cat] = categories.get(cat, 0) + 1
        return categories

    def is_follow_up_question(self, current_message: str) -> bool:
        indicators = ['explain more', 'tell me more', 'what about', 'how about', 'also', 'why', 'how']
        return any(indicator in current_message.lower() for indicator in indicators)

class QuantumTutorAgent(Agent):
    """The full, intelligent agent for tutoring quantum computing."""
    def __init__(self, groq_client):
        self.groq_client = groq_client
        self.memory = ConversationMemory()
        self.session_stats = {'total_queries': 0, 'session_start': datetime.now()}

    def format_response(self, text):
        replacements = {
            r'\bquantum\b': 'Quantum ⚛️', r'\bentanglement\b': 'entanglement 🔗',
            r'\bsuperposition\b': 'superposition ⚡', r'\bqubit\b': 'qubit 🎯',
            r'\bcircuit\b': 'circuit 🔌'
        }
        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text

    def classify_query(self, message: str) -> str:
        lowered = message.lower()
        if self.memory.is_follow_up_question(message) and self.memory.history:
            return f"followup_{self.memory.history[-1]['category']}"
        
        rules = {
            'code': ['code', 'python', 'program', 'qiskit'], 'research': ['arxiv', 'paper', 'research'],
            'comparison': ['difference', 'vs', 'compare'], 'math': ['formula', 'equation', 'math'],
            'application': ['application', 'real world', 'use case'], 'history': ['history', 'who discovered'],
            'fun': ['fun fact', 'joke', 'trivia'], 'quiz': ['mcq', 'quiz', 'test'],
            'help': ['help', 'what can you do'], 'progress': ['progress', 'summary']
        }
        for category, keywords in rules.items():
            if any(key in lowered for key in keywords):
                return category
        return 'general'

    def build_contextual_prompt(self, message: str, category: str) -> str:
        context = self.memory.get_context_summary()
        progress = self.memory.get_learning_progress()
        return (f"You are QuantumTutor 🤖, an expert quantum computing tutor. "
                f"CONVERSATION CONTEXT: {context}. "
                f"CURRENT QUERY: '{message}'. QUERY CATEGORY: {category}. "
                f"LEARNING PROGRESS: {progress or 'New learner'}. "
                f"Instructions: Be friendly, use simple analogies, and keep responses engaging and well-structured.")

    def get_help_response(self) -> str:
        return ("🤖 **QuantumTutor Capabilities**\n\nI can help you with:\n"
                "• 💻 **Code**: Python/Qiskit examples\n"
                "• 📚 **Research**: arXiv paper suggestions\n"
                "• ⚖️ **Comparisons**: Classical vs. Quantum concepts\n"
                "• 🌍 **Applications**: Real-world use cases\n"
                "• 🎯 **Quizzes**: Test your knowledge\n\n"
                "Try asking: *'Explain quantum superposition'* or *'Show me a simple Qiskit circuit'*.")

    def generate_session_summary(self) -> str:
        progress = self.memory.get_learning_progress()
        total = len(self.memory.history)
        if total == 0:
            return "🌟 Welcome! We haven't started our learning journey yet."
        most_discussed = max(progress, key=progress.get) if progress else 'None'
        return (f"📊 **Session Summary**\n"
                f"• **Total questions asked**: {total}\n"
                f"• **Topics explored**: {', '.join(progress.keys())}\n"
                f"• **Most discussed topic**: {most_discussed}")

    def run(self, message: str, **kwargs):
        start_time = time.time()
        try:
            self.session_stats['total_queries'] += 1
            category = self.classify_query(message)

            if category == 'help':
                response_content = self.get_help_response()
            elif category == 'progress':
                response_content = self.generate_session_summary()
            else:
                prompt = self.build_contextual_prompt(message, category)
                chat_completion = self.groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama-3.1-8b-instant", 
                    temperature=0.7, max_tokens=2048
                )
                response_content = chat_completion.choices[0].message.content

            formatted_response = self.format_response(response_content)
            self.memory.add_interaction(message, formatted_response, category, {'response_time': time.time() - start_time})

            return {
                'response': formatted_response,
                'category': category,
                'conversation_length': len(self.memory.history)
            }
        except Exception as e:
            error_response = f'🔧 Oops! An error occurred: {str(e)}'
            return {'response': error_response, 'category': 'error'}

    def reset_conversation(self):
        self.memory = ConversationMemory()
        print("Conversation reset.")

# ==============================================================================
# PART 2: FLASK WEB APP (The User Interface part)
# ==============================================================================

class QuantumTutorWebApp:
    def __init__(self):
        self.app = Flask(__name__)
        self.agent = None
        self.session_stats = {
            'start_time': datetime.now(), 'total_queries': 0,
            'topics_covered': set(), 'avg_response_time': 0
        }
        self.colors = {
            'primary': '#2563eb', 'secondary': '#7c3aed', 'accent': '#06b6d4',
            'success': '#10b981', 'warning': '#f59e0b', 'error': '#ef4444',
            'bg_light': '#f8fafc', 'bg_dark': '#1e293b',
            'text_primary': '#1f2937', 'text_secondary': '#6b7280'
        }
        self.initialize_system()
        self.setup_routes()

    def initialize_system(self):
        """Initialize the quantum tutor system for Docker."""
        try:
            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY environment variable not set.")
            self.groq_client = Groq(api_key=api_key)
            self.agent = QuantumTutorAgent(self.groq_client)
            print("✅ QuantumTutor initialized successfully!")
            return True
        except Exception as e:
            print(f"❌ Initialization Error: {str(e)}")
            self.agent = None # Ensure agent is None on failure
            return False

    def setup_routes(self):
        """Setup Flask routes"""
        @self.app.route('/')
        def index():
            return render_template_string(self.get_html_template())

        @self.app.route('/chat', methods=['POST'])
        def chat():
            if not self.agent:
                return jsonify({'success': False, 'error': 'System not initialized'})
            try:
                data = request.json
                user_query = data.get('message', '').strip()
                if not user_query:
                    return jsonify({'success': False, 'error': 'Empty message'})

                start_time = time.time()
                result = self.agent.run(user_query)
                response_time = time.time() - start_time

                self.session_stats['total_queries'] += 1
                self.session_stats['topics_covered'].add(result.get('category', 'general'))
                total_queries = self.session_stats['total_queries']
                if total_queries > 0:
                    self.session_stats['avg_response_time'] = (
                        (self.session_stats['avg_response_time'] * (total_queries - 1) + response_time) / total_queries
                    )

                return jsonify({
                    'success': True,
                    'response': result['response'],
                    'metadata': {
                        'response_time': round(response_time, 2),
                        'category': result.get('category', 'general'),
                        'conversation_length': result.get('conversation_length', 0)
                    },
                    'stats': self.get_stats()
                })
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})

        @self.app.route('/clear', methods=['POST'])
        def clear_chat():
            if self.agent: self.agent.reset_conversation()
            # Reset stats as well
            self.session_stats = {
                'start_time': datetime.now(), 'total_queries': 0,
                'topics_covered': set(), 'avg_response_time': 0
            }
            return jsonify({'success': True})

        @self.app.route('/progress', methods=['GET'])
        def get_progress():
            if self.agent:
                summary = self.agent.generate_session_summary()
                return jsonify({'success': True, 'summary': summary})
            return jsonify({'success': False, 'error': 'Agent not initialized'})

        @self.app.route('/stats', methods=['GET'])
        def get_stats_endpoint():
            return jsonify(self.get_stats())

    def get_stats(self):
        """Get current session statistics"""
        duration = datetime.now() - self.session_stats['start_time']
        minutes = int(duration.total_seconds() // 60)
        seconds = int(duration.total_seconds() % 60)
        return {
            'total_queries': self.session_stats['total_queries'],
            'topics_covered': len(self.session_stats['topics_covered']),
            'avg_response_time': round(self.session_stats['avg_response_time'], 2),
            'duration': f"{minutes}m {seconds}s"
        }

    def get_html_template(self):
        """Returns the full HTML, CSS, and JS for the web dashboard."""
        return f'''
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Quantum Computing Tutor</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: {self.colors['bg_light']}; margin: 0; padding: 20px; }}
                    .container {{ max-width: 1200px; margin: auto; }}
                    .header {{ background: linear-gradient(135deg, {self.colors['primary']} 0%, {self.colors['secondary']} 100%); padding: 30px; border-radius: 20px; color: white; text-align: center; margin-bottom: 30px; box-shadow: 0 8px 32px rgba(37, 99, 235, 0.3); }}
                    h1 {{ font-size: 2.5em; margin: 0; }}
                    .dashboard {{ display: grid; grid-template-columns: 1fr 2.5fr; gap: 30px; }}
                    .control-panel, .chat-container {{ background: white; padding: 25px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1); }}
                    .btn {{ padding: 12px 20px; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; transition: all 0.3s ease; width: 100%; }}
                    .btn-primary {{ background: {self.colors['primary']}; color: white; }}
                    .chat-messages {{ height: 500px; overflow-y: auto; padding: 10px; border: 1px solid #e5e7eb; border-radius: 8px; margin-bottom: 1rem; }}
                    .message {{ margin-bottom: 1rem; display: flex; flex-direction: column; }}
                    .user-message {{ align-items: flex-end; }}
                    .bot-message {{ align-items: flex-start; }}
                    .message div {{ max-width: 80%; padding: 10px 15px; line-height: 1.5; }}
                    .user-message div {{ background: {self.colors['primary']}; color: white; border-radius: 18px 18px 4px 18px; }}
                    .bot-message div {{ background: #f3f4f6; border-radius: 4px 18px 18px 18px; }}
                    .chat-input-form {{ display: flex; gap: 10px; }}
                    .chat-input {{ flex: 1; padding: 15px; border: 2px solid #e5e7eb; border-radius: 12px; }}
                    @media (max-width: 900px) {{ .dashboard {{ grid-template-columns: 1fr; }} }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header"><h1>🚀 Quantum Computing Tutor</h1><p>Interactive AI-powered quantum learning</p></div>
                    <div class="dashboard">
                        <div class="control-panel">
                            <h3>🎛️ Controls</h3>
                            <button class="btn" style="background:{self.colors['success']}; color:white;" onclick="clearChat()">🔄 Clear Chat</button>
                            <div id="stats" style="margin-top:20px;">
                                <h4>📊 Session Stats</h4>
                                <p>Queries: <span id="stat-queries">0</span></p>
                                <p>Duration: <span id="stat-duration">0m 0s</span></p>
                                <p>Avg Response: <span id="stat-response">0.0s</span></p>
                            </div>
                        </div>
                        <div class="chat-container">
                            <div class="chat-messages" id="chatMessages">
                                <div class="message bot-message"><div>Welcome! What quantum mystery can I unravel for you today?</div></div>
                            </div>
                            <form class="chat-input-form" onsubmit="sendMessage(event)">
                                <input class="chat-input" id="messageInput" placeholder="Ask about quantum gates, superposition..." autocomplete="off">
                                <button type="submit" class="btn btn-primary">Send</button>
                            </form>
                        </div>
                    </div>
                </div>
                <script>
                    async function sendMessage(event) {{
                        event.preventDefault();
                        const input = document.getElementById('messageInput');
                        const message = input.value.trim();
                        if (!message) return;

                        const chatMessages = document.getElementById('chatMessages');
                        chatMessages.innerHTML += `<div class="message user-message"><div>${{message}}</div></div>`;
                        input.value = '';
                        chatMessages.scrollTop = chatMessages.scrollHeight;

                        try {{
                            const response = await fetch('/chat', {{
                                method: 'POST',
                                headers: {{ 'Content-Type': 'application/json' }},
                                body: JSON.stringify({{ message }})
                            }});
                            const data = await response.json();
                            const botResponse = data.success ? data.response : `Error: ${{data.error}}`;
                            chatMessages.innerHTML += `<div class="message bot-message"><div>${{botResponse.replace(/\\n/g, '<br>')}}</div></div>`;
                            if(data.stats) updateStats(data.stats);
                        }} catch (error) {{
                            chatMessages.innerHTML += `<div class="message bot-message"><div>Error: Could not connect to the server.</div></div>`;
                        }}
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }}
                    function updateStats(stats) {{
                        document.getElementById('stat-queries').textContent = stats.total_queries;
                        document.getElementById('stat-duration').textContent = stats.duration;
                        document.getElementById('stat-response').textContent = stats.avg_response_time + 's';
                    }}
                    async function clearChat() {{
                        await fetch('/clear', {{ method: 'POST' }});
                        document.getElementById('chatMessages').innerHTML = `<div class="message bot-message"><div>Chat cleared. Ready for a new quantum journey!</div></div>`;
                        updateStats({{total_queries: 0, duration: '0m 0s', avg_response_time: 0}});
                    }}
                    setInterval(async () => {{
                        try {{
                           const response = await fetch('/stats');
                           if(response.ok) {{
                               const stats = await response.json();
                               updateStats(stats);
                           }}
                        }} catch (e) {{ console.error("Stat update failed", e) }}
                    }}, 30000);
                </script>
            </body>
            </html>
        '''

# ==============================================================================
# PART 3: CODE TO START THE SERVER
# ==============================================================================

def run_server():
    """Run the Flask server, optimized for a container."""
    app_instance = QuantumTutorWebApp()
    if app_instance.agent:
        print("🚀 Starting Quantum Tutor Web Dashboard on http://localhost:5000")
        app_instance.app.run(host='0.0.0.0', port=5000)
    else:
        print("❌ Could not start server: Agent failed to initialize.")

if __name__ == '__main__':
    run_server()
