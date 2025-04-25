from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({"status": "ok", "message": "Server is running"})

@app.route('/api/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    print("Starting Flask server on port 5001")
    app.run(host='0.0.0.0', port=5001, debug=True) 

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({"status": "ok", "message": "Server is running"})

@app.route('/api/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    print("Starting Flask server on port 5001")
    app.run(host='0.0.0.0', port=5001, debug=True) 