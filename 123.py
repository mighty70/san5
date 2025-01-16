from flask import Flask, request, jsonify, render_template_string
import time

app = Flask(__name__)

# ----------------------------------------------------------------
# Состояние в памяти
# ----------------------------------------------------------------

# Последние lobby_id от 4 ПК
latest_lobby_id = {
    "pc1": None,
    "pc2": None,
    "pc3": None,
    "pc4": None
}

# Запоминаем «последнего соперника» для каждого ПК, 
# чтобы не разрешать подряд одинаковую пару:
pc_last_partner = {
    "pc1": None,
    "pc2": None,
    "pc3": None,
    "pc4": None
}

# История логов (лобби). Показываем в /status
lobby_history = []

# История сыгранных матчей (кто с кем и когда)
games_history = []

def find_pair_if_any():
    """
    Ищем любые 2 ПК, у которых совпадает lobby_id (не None).
    Возвращаем (pcA, pcB, lobby_id) или (None,None,None).
    """
    not_none_ids = [(pc, lid) for pc, lid in latest_lobby_id.items() if lid is not None]
    for i in range(len(not_none_ids)):
        for j in range(i+1, len(not_none_ids)):
            pcA, lidA = not_none_ids[i]
            pcB, lidB = not_none_ids[j]
            if lidA == lidB:
                return (pcA, pcB, lidA)
    return (None, None, None)

def is_repeat_match(pcA, pcB):
    """Вернёт True, если pcA только что играл с pcB и наоборот."""
    return (pc_last_partner[pcA] == pcB) and (pc_last_partner[pcB] == pcA)

# ----------------------------------------------------------------
# /lobby_id — Приём и матчинг
# ----------------------------------------------------------------
@app.route('/lobby_id', methods=['POST'])
def handle_lobby_id():
    data = request.json
    pc = data.get("pc")
    new_lobby = data.get("lobby_id")

    if pc not in latest_lobby_id:
        return jsonify({"status": "error", "message": "Unknown PC name"})

    old_lobby = latest_lobby_id[pc]
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    # Обновляем lobby_id у ПК
    # Если действительно поменялся, то записываем "waiting" (только один раз).
    if new_lobby != old_lobby:
        latest_lobby_id[pc] = new_lobby
        # Добавляем в историю только если лобби действительно «новое»
        # (так не будет «спама» waiting для тех же самых ID).
        lobby_history.append({
            "timestamp": timestamp,
            "pc1_id": latest_lobby_id["pc1"],
            "pc2_id": latest_lobby_id["pc2"],
            "pc3_id": latest_lobby_id["pc3"],
            "pc4_id": latest_lobby_id["pc4"],
            "status": "waiting"
        })
    else:
        # Если новое == старое, просто возвращаем None, без спама истории
        # (т.е. ничего не записываем повторно)
        pass

    # Проверяем, не нашлась ли пара
    pcA, pcB, match_id = find_pair_if_any()
    if pcA and pcB and match_id:
        # Проверим, не играли ли они друг с другом сразу «подряд»
        if is_repeat_match(pcA, pcB):
            # Запишем статус "repeat_rejected" в историю
            lobby_history.append({
                "timestamp": timestamp,
                "pc1_id": latest_lobby_id["pc1"],
                "pc2_id": latest_lobby_id["pc2"],
                "pc3_id": latest_lobby_id["pc3"],
                "pc4_id": latest_lobby_id["pc4"],
                "status": "repeat_rejected"
            })
            return jsonify({"status": "search_again"})
        else:
            # Иначе — матчим
            pc_last_partner[pcA] = pcB
            pc_last_partner[pcB] = pcA
            games_history.append({
                "pc1": pcA,
                "pc2": pcB,
                "start_time": timestamp,
                "end_time": None
            })
            lobby_history.append({
                "timestamp": timestamp,
                "pc1_id": latest_lobby_id["pc1"],
                "pc2_id": latest_lobby_id["pc2"],
                "pc3_id": latest_lobby_id["pc3"],
                "pc4_id": latest_lobby_id["pc4"],
                "status": "match"
            })
            return jsonify({"status": "game_accepted"})
    else:
        # Пары нет, значит ждём
        return jsonify({"status": None})

# ----------------------------------------------------------------
# /game_end — Когда игра закончилась (pcX присылает)
# ----------------------------------------------------------------
@app.route('/game_end', methods=['POST'])
def handle_game_end():
    data = request.json
    pc = data.get("pc")
    if pc not in latest_lobby_id:
        return jsonify({"status": "error", "message": "Unknown PC"})

    now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    # Находим последнюю незавершённую игру, где участвовал pc
    for game in reversed(games_history):
        if game["end_time"] is None and (game["pc1"] == pc or game["pc2"] == pc):
            game["end_time"] = now
            break

    return jsonify({"status": "ok"})

# ----------------------------------------------------------------
# /reset — сброс состояния (lobby_id и т.п.)
# ----------------------------------------------------------------
@app.route('/reset', methods=['POST'])
def reset_state():
    latest_lobby_id["pc1"] = None
    latest_lobby_id["pc2"] = None
    latest_lobby_id["pc3"] = None
    latest_lobby_id["pc4"] = None
    # Можно сбросить и last_partner, если хотите
    # pc_last_partner["pc1"] = None
    # pc_last_partner["pc2"] = None
    # pc_last_partner["pc3"] = None
    # pc_last_partner["pc4"] = None
    return "OK"

# ----------------------------------------------------------------
# /status — HTML-страница с панелями PC1..PC4, 
#            историей лобби (посл. 8 записей), 
#            историей игр (посл. 8).
# ----------------------------------------------------------------
@app.route('/status')
def fancy_status():
    pc1_id = latest_lobby_id["pc1"] or "—"
    pc2_id = latest_lobby_id["pc2"] or "—"
    pc3_id = latest_lobby_id["pc3"] or "—"
    pc4_id = latest_lobby_id["pc4"] or "—"

    # Последние 8 записей
    recent_lobby = lobby_history[-8:] if len(lobby_history) > 0 else []
    recent_games = games_history[-8:] if len(games_history) > 0 else []

    html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Dota Lobby Status</title>
  <style>
    body {
      background: #f0f0f0;
      font-family: "Segoe UI", Arial, sans-serif;
      margin: 0; 
      padding: 0;
      display: flex; 
      flex-direction: column;
      align-items: center;
      color: #333;
    }
    h1 {
      margin-top: 30px; 
      font-size: 28px;
    }
    .board {
      display: flex;
      gap: 20px;
      margin-top: 20px;
    }
    .panel {
      background: #222;
      color: #fff;
      width: 220px;
      border-radius: 15px;
      padding: 20px;
      box-shadow: 0 0 10px rgba(0,0,0,0.3);
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    .circle {
      width: 80px; 
      height: 80px;
      border: 4px solid #555;
      border-radius: 50%;
      display: flex; 
      align-items: center; 
      justify-content: center;
      font-size: 24px;
      margin-bottom: 15px;
      background: linear-gradient(to bottom, #333, #111);
    }
    .label {
      font-size: 14px;
      color: #bbb;
      margin-top: 8px;
    }
    .value {
      font-size: 18px; 
      margin-top: 4px;
      color: #0f0;
    }
    .history-panel, .games-panel {
      margin-top: 30px;
      background: #fff;
      width: 600px;
      border-radius: 15px;
      padding: 20px;
      box-shadow: 0 0 10px rgba(0,0,0,0.2);
    }
    .history-panel h2, .games-panel h2 {
      margin-top: 0;
      color: #333;
    }
    .history {
      margin-top: 10px;
      width: 100%;
      border-top: 1px solid #ccc;
      padding-top: 10px;
    }
    .history-item {
      font-size: 14px;
      margin: 5px 0;
      line-height: 1.4;
    }
    .status-match { color: #4caf50; }
    .status-waiting { color: #ffb300; }
    .status-repeat_rejected { color: #e53935; }
    .status-search_again { color: #e53935; }
  </style>
</head>
<body>
  <h1>Dota Lobby Status</h1>
  
  <div class="board">
    <div class="panel">
      <div class="circle">PC1</div>
      <div class="label">Last Found Lobby ID</div>
      <div class="value">{{ pc1_id }}</div>
    </div>
    <div class="panel">
      <div class="circle">PC2</div>
      <div class="label">Last Found Lobby ID</div>
      <div class="value">{{ pc2_id }}</div>
    </div>
    <div class="panel">
      <div class="circle">PC3</div>
      <div class="label">Last Found Lobby ID</div>
      <div class="value">{{ pc3_id }}</div>
    </div>
    <div class="panel">
      <div class="circle">PC4</div>
      <div class="label">Last Found Lobby ID</div>
      <div class="value">{{ pc4_id }}</div>
    </div>
  </div>

  <div class="history-panel">
    <h2>Recent Lobby History (last 8)</h2>
    <div class="history">
      {% if recent_lobby %}
        {% for entry in recent_lobby %}
          <div class="history-item">
            {{ entry.timestamp }} — 
            PC1: {{ entry.pc1_id or '—' }},
            PC2: {{ entry.pc2_id or '—' }},
            PC3: {{ entry.pc3_id or '—' }},
            PC4: {{ entry.pc4_id or '—' }}
            <span class="status-{{ entry.status }}">[{{ entry.status }}]</span>
          </div>
        {% endfor %}
      {% else %}
        <p>Нет записей</p>
      {% endif %}
    </div>
  </div>

  <div class="games-panel">
    <h2>Recent Games (last 8)</h2>
    <div class="history">
      {% if recent_games %}
        {% for g in recent_games %}
          <div class="history-item">
            {{ g.start_time }} — <strong>{{ g.pc1 }}</strong> vs <strong>{{ g.pc2 }}</strong>
            {% if g.end_time %}
               — Окончена в {{ g.end_time }}
            {% else %}
               — Идёт...
            {% endif %}
          </div>
        {% endfor %}
      {% else %}
        <p>Нет сыгранных матчей</p>
      {% endif %}
    </div>
  </div>

</body>
</html>
    """
    return render_template_string(
        html_template,
        pc1_id=pc1_id,
        pc2_id=pc2_id,
        pc3_id=pc3_id,
        pc4_id=pc4_id,
        recent_lobby=recent_lobby,
        recent_games=recent_games
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
