import os
import threading
import queue
import datetime
import re
from flask import Flask, render_template, request, Response, jsonify, send_file
import csv
import scholar_scraper

app = Flask(__name__)
log_queue = queue.Queue()

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_CSV = os.path.join(BASE_DIR, "Data Folder", "scholar_results.csv")

_stop_event    = threading.Event()
_scrape_thread = None

def enqueue_log(msg):
    log_queue.put(msg)

scholar_scraper.LOG_CALLBACK = enqueue_log

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/preview')
def preview():
    return render_template('data_view.html')

@app.route('/start-scrape', methods=['POST'])
def start_scrape():
    global OUTPUT_CSV, _stop_event, _scrape_thread
    _stop_event.clear()

    data         = request.json
    query        = data.get('query')
    raw_max      = data.get('max_results')
    target_count = int(raw_max) if raw_max and str(raw_max).strip() else 1000000
    year_low     = int(data['year_low'])  if data.get('year_low')  else None
    year_high    = int(data['year_high']) if data.get('year_high') else None

    # Drain any stale messages from a previous run
    while not log_queue.empty():
        try:
            log_queue.get_nowait()
        except Exception:
            break

    # ── Build filters dict ────────────────────────────────────────────────────
    filters = {}

    if data.get('open_access'):
        filters['open_access'] = True

    quartiles = [q for q in data.get('quartiles', []) if q]
    if quartiles:
        filters['quartiles'] = quartiles

    if data.get('min_h_index') not in (None, '', 0, '0'):
        filters['min_h_index'] = float(data['min_h_index'])

    if data.get('min_sjr') not in (None, '', 0, '0'):
        filters['min_sjr'] = float(data['min_sjr'])

    if data.get('min_citations') not in (None, '', 0, '0'):
        filters['min_citations'] = int(data['min_citations'])

    journals = [j for j in data.get('journals', []) if j and j.strip()]
    if journals:
        filters['journals'] = journals

    publishers = [p for p in data.get('publishers', []) if p and p.strip()]
    if publishers:
        filters['publishers'] = publishers

    # ── Generate output filename ──────────────────────────────────────────────
    clean_query = re.sub(r'[^a-zA-Z0-9]', '_', query)[:20]
    timestamp   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename    = f"scrape_{clean_query}_{timestamp}.csv"
    OUTPUT_CSV  = os.path.join(BASE_DIR, "Data Folder", filename)

    def run_scraper():
        try:
            scholar_scraper.setup_custom_tor()
            scholar_scraper.search_scholar(
                query,
                output_file  = OUTPUT_CSV,
                target_count = target_count,
                year_low     = year_low,
                year_high    = year_high,
                stop_event   = _stop_event,
                filters      = filters if filters else None
            )
        except Exception as e:
            enqueue_log(f"ERROR: {str(e)}")
        finally:
            enqueue_log("STOPPED" if _stop_event.is_set() else "DONE")

    _scrape_thread = threading.Thread(target=run_scraper, daemon=True)
    _scrape_thread.start()
    return jsonify({"status": "started", "file": filename})

@app.route('/stop', methods=['POST'])
def stop_scrape():
    global _stop_event
    _stop_event.set()
    enqueue_log("[STOPPED] Stop signal sent. Finishing current paper...")
    return jsonify({"status": "stopping"})

@app.route('/stream')
def stream():
    def event_stream():
        while True:
            try:
                msg = log_queue.get(timeout=30)
                yield f"data: {msg}\n\n"
            except Exception:
                # Send a keepalive heartbeat comment so the browser
                # doesn't time out the SSE connection during slow scrapes
                yield ": heartbeat\n\n"
    return Response(event_stream(), mimetype="text/event-stream")

@app.route('/download')
def download():
    if os.path.exists(OUTPUT_CSV):
        return send_file(OUTPUT_CSV, as_attachment=True)
    return "File not found", 404

@app.route('/data')
def get_data():
    if os.path.exists(OUTPUT_CSV):
        rows = []
        with open(OUTPUT_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        return jsonify(rows)
    return jsonify([])

if __name__ == '__main__':
    while not log_queue.empty():
        log_queue.get()
    app.run(port=5000, debug=False)
