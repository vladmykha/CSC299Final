import csv
import io
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
import db
import routing

bp = Blueprint('analytics', __name__)


@bp.route('/analytics')
def show_analytics():
    conn = db.get_db()
    status_counts = {r['status']: r['cnt'] for r in conn.execute(
        "SELECT status, COUNT(*) AS cnt FROM shipments GROUP BY status"
    )}
    today = datetime.now().strftime('%Y-%m-%d')
    delayed_count = conn.execute(
        "SELECT COUNT(*) FROM shipments WHERE status != 'delivered' AND deadline < ?", (today,)
    ).fetchone()[0]

    all_shipments = conn.execute(
        'SELECT id, origin_hub, destination_hub, total_pay FROM shipments'
    ).fetchall()
    good = bad = 0
    rates = []
    for s in all_shipments:
        result = routing.get_route(conn, s['origin_hub'], s['destination_hub'])
        if result and result['distance'] > 0:
            rate = s['total_pay'] / result['distance']
            rates.append(rate)
            if s['total_pay'] >= 3.5 * result['distance']:
                good += 1
            else:
                bad += 1

    avg_rate = round(sum(rates) / len(rates), 2) if rates else 0
    top_routes = conn.execute(
        "SELECT h1.city || ' → ' || h2.city AS route, COUNT(*) AS cnt "
        "FROM shipments s "
        "JOIN hubs h1 ON s.origin_hub=h1.id "
        "JOIN hubs h2 ON s.destination_hub=h2.id "
        "GROUP BY s.origin_hub, s.destination_hub "
        "ORDER BY cnt DESC LIMIT 5"
    ).fetchall()
    conn.close()
    return render_template('analytics.html',
                           status_counts=status_counts,
                           good_count=good, bad_count=bad,
                           avg_rate=avg_rate,
                           delayed_count=delayed_count,
                           top_routes=top_routes,
                           total=len(all_shipments))


@bp.route('/import', methods=['GET', 'POST'])
def import_csv():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename.endswith('.csv'):
            flash('Please upload a valid .csv file.', 'danger')
            return redirect(url_for('analytics.import_csv'))
        conn = db.get_db()
        hub_map = {r['code']: r['id'] for r in conn.execute('SELECT id, code FROM hubs')}
        stream = io.StringIO(file.stream.read().decode('utf-8'))
        reader = csv.DictReader(stream)
        count, errors = 0, []
        for i, row in enumerate(reader, 1):
            try:
                origin_id = hub_map.get(row['origin_code'].strip().upper())
                dest_id   = hub_map.get(row['destination_code'].strip().upper())
                if not origin_id or not dest_id:
                    errors.append(f'Row {i}: unknown hub code.')
                    continue
                conn.execute(
                    'INSERT INTO shipments (origin_hub, destination_hub, cargo_type, '
                    'weight_lbs, deadline, total_pay, notes) VALUES (?,?,?,?,?,?,?)',
                    (origin_id, dest_id, row['cargo_type'].strip(),
                     float(row['weight_lbs']), row['deadline'].strip(),
                     float(row['total_pay']), row.get('notes', '').strip())
                )
                count += 1
            except Exception as e:
                errors.append(f'Row {i}: {e}')
        conn.commit()
        conn.close()
        flash(f'Imported {count} shipment(s).', 'success')
        for err in errors[:5]:
            flash(err, 'warning')
        return redirect(url_for('shipments.list_shipments'))
    return render_template('import.html')
