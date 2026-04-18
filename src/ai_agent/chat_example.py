"""Example HTML/JavaScript for the AI Agent Chat Interface.

This file demonstrates how to use the streaming chat endpoint
with Server-Sent Events to show real-time agent states.

Save this as a .html file and open in browser to test.
"""

EXAMPLE_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Agent Chat - Rappi Analytics</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
        }
        .chat-area {
            height: 400px;
            overflow-y: auto;
            padding: 20px;
            background: #fafafa;
        }
        .message {
            margin-bottom: 15px;
            padding: 12px 16px;
            border-radius: 12px;
            max-width: 80%;
        }
        .message.user {
            background: #667eea;
            color: white;
            margin-left: auto;
        }
        .message.assistant {
            background: white;
            border: 1px solid #e0e0e0;
        }
        .status-bar {
            padding: 15px 20px;
            background: #f0f0f0;
            border-top: 1px solid #e0e0e0;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        .progress-bar {
            flex: 1;
            height: 8px;
            background: #e0e0e0;
            border-radius: 4px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            border-radius: 4px;
            transition: width 0.3s ease;
        }
        .status-text {
            font-size: 14px;
            color: #666;
            min-width: 200px;
        }
        .input-area {
            padding: 20px;
            border-top: 1px solid #e0e0e0;
            display: flex;
            gap: 10px;
        }
        input {
            flex: 1;
            padding: 12px 16px;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
        }
        button {
            padding: 12px 24px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover { background: #5568d3; }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
        .state-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
            text-transform: uppercase;
        }
        .state-understanding { background: #e3f2fd; color: #1976d2; }
        .state-searching { background: #fff3e0; color: #f57c00; }
        .state-extracting { background: #f3e5f5; color: #7b1fa2; }
        .state-validating { background: #e8f5e9; color: #388e3c; }
        .state-comparing { background: #fce4ec; color: #c2185b; }
        .state-completed { background: #d4edda; color: #155724; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>?? AI Agent Chat</h1>
            <p>Rappi Analytics - Comparador de Precios</p>
        </div>
        
        <div class="chat-area" id="chatArea"></div>
        
        <div class="status-bar">
            <div class="status-text" id="statusText">Listo</div>
            <div class="progress-bar">
                <div class="progress-fill" id="progressFill" style="width: 0%"></div>
            </div>
        </div>
        
        <div class="input-area">
            <input type="text" id="messageInput" 
                   placeholder="Ej: Cuanto cuesta un Big Mac?" 
                   onkeypress="if(event.key==='Enter') sendMessage()">
            <button onclick="sendMessage()" id="sendBtn">Enviar</button>
        </div>
    </div>

    <script>
        const API_URL = 'http://localhost:8000/api/v1/ai-agent';
        
        function addMessage(role, content) {
            const chatArea = document.getElementById('chatArea');
            const div = document.createElement('div');
            div.className = `message ${role}`;
            div.innerHTML = content;
            chatArea.appendChild(div);
            chatArea.scrollTop = chatArea.scrollHeight;
        }
        
        function updateStatus(status, message, progress) {
            const statusText = document.getElementById('statusText');
            const progressFill = document.getElementById('progressFill');
            
            const stateClass = `state-${status}`;
            statusText.innerHTML = `<span class="state-badge ${stateClass}">${status}</span> ${message}`;
            progressFill.style.width = `${progress}%`;
        }
        
        async function sendMessage() {
            const input = document.getElementById('messageInput');
            const btn = document.getElementById('sendBtn');
            const message = input.value.trim();
            
            if (!message) return;
            
            // Add user message
            addMessage('user', message);
            input.value = '';
            btn.disabled = true;
            
            // Connect to SSE endpoint
            const eventSource = new EventSource(
                `${API_URL}/chat/stream?message=${encodeURIComponent(message)}`
            );
            
            eventSource.onmessage = (event) => {
                const state = JSON.parse(event.data);
                
                // Update status
                updateStatus(state.status, state.message, state.progress);
                
                // If completed, add response
                if (state.status === 'completed') {
                    addMessage('assistant', state.response_text);
                    eventSource.close();
                    btn.disabled = false;
                    updateStatus('idle', 'Listo', 0);
                }
            };
            
            eventSource.onerror = (error) => {
                console.error('SSE Error:', error);
                eventSource.close();
                btn.disabled = false;
                updateStatus('error', 'Error de conexion', 0);
            };
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    print(EXAMPLE_HTML)
