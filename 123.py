from flask import Flask, request, jsonify, render_template_string
import time

app = Flask(__name__)

# ----------------------------------------------------------------
# Состояние в памяти
# ----------------------------------------------------------------

# Храним последние lobby_id, которые прислали 4 ПК.
latest_lobby_id = {
    "pc1": None,
    "pc2": None,
    "pc3": None,
    "pc4": None
}

# Сохраняем «последнего соперника» для каждого ПК
# Если pc1 только что играл с pc2, то pc_last_partner["pc1"] = "pc2", и наоборот
pc_last_partner = {
    "pc1": None,
    "pc2": None,
    "pc3": None,
    "pc4": None
}

# Храним историю обращений (как было у вас в лобби-истории)
lobby_history = []

# Храним историю матчей (когда началась и когда закончилась)
games_history = []
# Пример структуры элемента:
# {
#   "pc1": "pc1",
#   "pc2": "pc2",
#   "start_time": "2025-01-16 10:00:00",
#   "end_time": None
# }


# ----------------------------------------------------------------
# Вспомогательная функция: найти пару ПК, у которых одинаковый lobby_id
# ----------------------------------------------------------------
def find_pair_if_any():
    """
    Возвращает кортеж (pcA, pcB, lobby_id), если нашли двух ПК с одинаковым lobby_id.
    Или (None, None, None) если ничего не нашли.
    """
    # Соберём все PC -> lobby_id, где lobby_id не None
    not_none_ids = [(pc, lid) for pc, lid in latest_lobby_id.items() if lid is not None]

    # Ищем любые 2 ПК с одним и тем же lobby_id
    for i in range(len(not_none_ids)):
        for j in range(i+1, len(not_none_ids)):
            pcA, lidA = not_none_ids[i]
            pcB, lidB = not_none_ids[j]
            if lidA == lidB:
                return (pcA, pcB, lidA)
    return (None, None, None)


# ----------------------------------------------------------------
# Проверка, не повторяется ли матч между теми же PC подряд
# ----------------------------------------------------------------
def is_repeat_match(pcA, pcB):
    """Вернёт True, если pcA только что играл с pcB (и наоборот)."""
    # Если последний соперник pcA == pcB И последний соперник pcB == pcA
    # значит они только что играли. Запретим.
    return (pc_last_partner[pcA] == pcB) and (pc_last_partner[pcB] == pcA)


# ----------------------------------------------------------------
# Маршрут для приёма lobby_id
# ----------------------------------------------------------------
@app.route('/lobby_id', methods=['POST'])
def handle_lobby_id():
    """
    Принимает JSON { "pc": "pc1", "lobby_id": "12345" }
    """
    data = request.json
    pc = data.get("pc")
    lobby_id = data.get("lobby_id")

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    # Проверка: действительно ли pc в ["pc1","pc2","pc3","pc4"] ?
    if pc not in latest_lobby_id:
        return jsonify({"status": "error", "message": "Unknown PC name"})

    # Обновляем
    latest_lobby_id[pc] = lobby_id

    # Пишем в историю
    # Статус "waiting" пока мы не знаем, матчится ли
    lobby_history.append({
        "timestamp": timestamp,
        "pc1_id": latest_lobby_id["pc1"],
        "pc2_id": latest_lobby_id["pc2"],
        "pc3_id": latest_lobby_id["pc3"],
        "pc4_id": latest_lobby_id["pc4"],
        "status": "waiting"
    })

    # Проверяем, есть ли 2 ПК с одинаковым lobby_id
    pcA, pcB, match_id = find_pair_if_any()
    if pcA and pcB and match_id:
        # Проверяем, не повторяется ли игра теми же двумя подряд
        if is_repeat_match(pcA, pcB):
            # Отклоняем (или "search_again")
            # Пишем в историю
            lobby_history.append({
                "timestamp": timestamp,
                "pc1_id": latest_lobby_id["pc1"],
                "pc2_id": latest_lobby_id["pc2"],
                "pc3_id": latest_lobby_id["pc3"],
                "pc4_id": latest_lobby_id["pc4"],
                "status": "repeat_rejected"  # наш статус
            })
            return jsonify({"status": "search_again"})
        else:
            # Иначе — это новый матч
            # Устанавливаем последнего соперника
            pc_last_partner[pcA] = pcB
            pc_last_partner[pcB] = pcA
            # Делаем запись в массив games_history (start_time — сейчас)
            games_history.append({
                "pc1": pcA,
                "pc2": pcB,
                "start_time": timestamp,
                "end_time": None
            })
            # Пишем в историю, что match
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
        # Ждём второго (или третьего) и т.д.
        return jsonify({"status": None})


# ----------------------------------------------------------------
# Маршрут для конца игры
# ----------------------------------------------------------------
@app.route('/game_end', methods=['POST'])
def handle_game_end():
    """
    Клиент присылает: { "pc": "pc1" }
    означает, что pc1 закончил игру.
    Но нам нужно понять, с кем он играл.
    Найдём последнюю игру в games_history, где (pc1=pc или pc2=pc) и end_time=None
    Запишем end_time = текущее время
    """
    data = request.json
    pc = data.get("pc")
    if pc not in ["pc1", "pc2", "pc3", "pc4"]:
        return jsonify({"status": "error", "message": "Unknown PC"})

    now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    # Ищем последнюю незавершённую игру, где участвовал pc
    for game in reversed(games_history):
        if game["end_time"] is None and (game["pc1"] == pc or game["pc2"] == pc):
            # Закрываем игру
            game["end_time"] = now
            break

    return jsonify({"status": "ok"})


# ----------------------------------------------------------------
# Сброс состояния
# ----------------------------------------------------------------
@app.route('/reset', methods=['POST'])
def reset_state():
    latest_lobby_id["pc1"] = None
    latest_lobby_id["pc2"] = None
    latest_lobby_id["pc3"] = None
    latest_lobby_id["pc4"] = None

    # Можно сбросить last_partner, если хотите заново разрешить пары
    # pc_last_partner["pc1"] = None
    # pc_last_partner["pc2"] = None
    # pc_last_partner["pc3"] = None
    # pc_last_partner["pc4"] = None

    return "OK"


# ----------------------------------------------------------------
# Вспомогательная функция для HTML-рендеринга
# ----------------------------------------------------------------
def format_end_time(et):
    return et if et else "—"


# ----------------------------------------------------------------
# Маршрут статуса (4 ПК + история + история игр)
# ----------------------------------------------------------------
@app.route('/status')
def fancy_status():
    # Берём последний lobby_id для каждого
    pc1_id = latest_lobby_id["pc1"] or "—"
    pc2_id = latest_lobby_id["pc2"] or "—"
    pc3_id = latest_lobby_id["pc3"] or "—"
    pc4_id = latest_lobby_id["pc4"] or "—"

    # Последние ~5 событий лобби
    recent_lobby = lobby_history[-5:] if len(lobby_history) > 0 else []

    # Последние ~5 матчей
    recent_games = games_history[-5:] if len(games_history) > 0 else []

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
    .status-no_match { color: #e53935; }
    .status-waiting { color: #ffb300; }
    .status-repeat_rejected { color: #e53935; }
    .status-search_again { color: #e53935; }
  </style>
</head>
<body>
  <h1>Dota Lobby Status</h1>
  
  <!-- 4 панели -->
  <div class="board">
    <!-- pc1 -->
    <div class="panel">
      <div class="circle">PC1</div>
      <div class="label">Last Found Lobby ID</div>
      <div class="value">{{ pc1_id }}</div>
    </div>

    <!-- pc2 -->
    <div class="panel">
      <div class="circle">PC2</div>
      <div class="label">Last Found Lobby ID</div>
      <div class="value">{{ pc2_id }}</div>
    </div>

    <!-- pc3 -->
    <div class="panel">
      <div class="circle">PC3</div>
      <div class="label">Last Found Lobby ID</div>
      <div class="value">{{ pc3_id }}</div>
    </div>

    <!-- pc4 -->
    <div class="panel">
      <div class="circle">PC4</div>
      <div class="label">Last Found Lobby ID</div>
      <div class="value">{{ pc4_id }}</div>
    </div>
  </div>

  <!-- Блок истории Lobby -->
  <div class="history-panel">
    <h2>Recent History</h2>
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

  <!-- История игр (pcA vs pcB) -->
  <div class="games-panel">
    <h2>Recent Games</h2>
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
