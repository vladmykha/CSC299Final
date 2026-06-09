from datetime import datetime, date

from flask import Flask, render_template
import db
from routes.shipments import bp as shipments_bp
from routes.drivers   import bp as drivers_bp
from routes.hubs      import bp as hubs_bp
from routes.analytics import bp as analytics_bp
from routes.api       import bp as api_bp

app = Flask(__name__)
app.secret_key = 'csc299-logitrack-secret'

app.register_blueprint(shipments_bp)
app.register_blueprint(drivers_bp)
app.register_blueprint(hubs_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(api_bp)

db.init_db()


@app.template_global()
def shipment_progress(s):
    """Deadline progress: pct elapsed, color (success/warning/danger), label, overdue flag."""
    if s['status'] == 'delivered':
        return {'pct': 100, 'color': 'success', 'label': 'Delivered', 'overdue': False}
    try:
        created   = datetime.strptime(s['created_at'][:10], '%Y-%m-%d').date()
        deadline  = datetime.strptime(s['deadline'], '%Y-%m-%d').date()
        today     = date.today()
        total     = max((deadline - created).days, 1)
        elapsed   = (today - created).days
        pct       = min(100, max(0, int(elapsed / total * 100)))
        days_left = (deadline - today).days
        overdue   = days_left < 0
        label     = (f'Overdue {abs(days_left)}d' if overdue
                     else ('Due today' if days_left == 0 else f'{days_left}d left'))
        color     = 'danger' if pct >= 85 else ('warning' if pct >= 60 else 'success')
        return {'pct': pct, 'color': color, 'label': label, 'overdue': overdue}
    except Exception:
        return {'pct': 0, 'color': 'secondary', 'label': '', 'overdue': False}


@app.route('/')
def index():
    conn = db.get_db()
    today = datetime.now().strftime('%Y-%m-%d')
    stats = {
        'total':      conn.execute('SELECT COUNT(*) FROM shipments').fetchone()[0],
        'pending':    conn.execute("SELECT COUNT(*) FROM shipments WHERE status='pending'").fetchone()[0],
        'in_transit': conn.execute("SELECT COUNT(*) FROM shipments WHERE status='in-transit'").fetchone()[0],
        'delivered':  conn.execute("SELECT COUNT(*) FROM shipments WHERE status='delivered'").fetchone()[0],
    }
    delayed = conn.execute(
        "SELECT s.*, h1.city AS origin_city, h2.city AS dest_city, d.name AS driver_name "
        "FROM shipments s JOIN hubs h1 ON s.origin_hub=h1.id "
        "JOIN hubs h2 ON s.destination_hub=h2.id "
        "LEFT JOIN drivers d ON s.driver_id=d.id "
        "WHERE s.status != 'delivered' AND s.deadline < ? ORDER BY s.deadline", (today,)
    ).fetchall()
    recent = conn.execute(
        "SELECT s.*, h1.city AS origin_city, h2.city AS dest_city, d.name AS driver_name "
        "FROM shipments s JOIN hubs h1 ON s.origin_hub=h1.id "
        "JOIN hubs h2 ON s.destination_hub=h2.id "
        "LEFT JOIN drivers d ON s.driver_id=d.id "
        "ORDER BY s.created_at DESC LIMIT 6"
    ).fetchall()
    conn.close()
    return render_template('index.html', stats=stats, delayed=delayed, recent=recent)


if __name__ == '__main__':
    app.run(debug=True)
