from flask import Flask, jsonify, request
from flask_cors import CORS
import subprocess
import threading
import os
import time

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

logs = []
history = []

status = {
    "passed": 0,
    "failed": 0,
    "executing": 0,
    "last_execution": "-"
}

flows = {
    "Receitas": "flows/Receitas/CT-168635.py",
}

def execute_flow(flow_name):

    status["executing"] = 1

    logs.clear()

    start_time = time.time()

    file_path = flows.get(flow_name)

    absolute_path = os.path.join(BASE_DIR, file_path)

    try:

        process = subprocess.Popen(
            ["python", absolute_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        for line in process.stdout:
            logs.append(line.strip())

        process.wait()

        duration = round(time.time() - start_time, 2)

        if process.returncode == 0:
            result = "PASSOU"
            status["passed"] += 1
        else:
            result = "FALHOU"
            status["failed"] += 1

        history.insert(0, {
            "flow": flow_name,
            "date": time.strftime("%d/%m/%Y %H:%M:%S"),
            "duration": f"{duration}s",
            "result": result
        })

        status["last_execution"] = flow_name

    except Exception as e:
        logs.append(f"[ERROR] {str(e)}")

    finally:
        status["executing"] = 0


@app.route("/api/flows")
def get_flows():
    return jsonify(list(flows.keys()))


@app.route("/api/run", methods=["POST"])
def run_flow():

    data = request.json

    flow = data["flow"]

    thread = threading.Thread(
        target=execute_flow,
        args=(flow,)
    )

    thread.start()

    return jsonify({
        "message": "Fluxo iniciado"
    })


@app.route("/api/logs")
def get_logs():
    return jsonify(logs)


@app.route("/api/status")
def get_status():
    return jsonify(status)


@app.route("/api/history")
def get_history():
    return jsonify(history)


if __name__ == "__main__":
    app.run(debug=True)