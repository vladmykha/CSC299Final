#!/usr/bin/env python3
"""
LogiTrack CLI — terminal client for the LogiTrack REST API.

Usage:
    python3 cli.py [--url URL] <command> [options]

Start the server first:
    python3 app.py

Commands:
    stats                       Show dashboard summary
    shipments [--status STATUS] List shipments
    shipment <id>               Show shipment details and route
    drivers                     List all drivers
    hubs                        List all hubs
    route <origin_id> <dest_id> Calculate shortest route between hubs
"""

import argparse
import sys

try:
    import requests
except ImportError:
    print("Error: 'requests' package is required. Run: pip3 install requests")
    sys.exit(1)

DEFAULT_URL = 'http://127.0.0.1:5000'

# ── Formatting helpers ────────────────────────────────────────────────────────

def _bar(pct, width=20):
    filled = int(width * pct / 100)
    return '█' * filled + '░' * (width - filled)

def _status_icon(status):
    return {'pending': '⏳', 'in-transit': '🚛', 'delivered': '✅'}.get(status, '•')

def _color(text, code):
    return f'\033[{code}m{text}\033[0m'

def green(t):  return _color(t, 32)
def yellow(t): return _color(t, 33)
def red(t):    return _color(t, 31)
def bold(t):   return _color(t, 1)
def dim(t):    return _color(t, 2)


def _progress_label(pct, days_left):
    if days_left is None:
        return ''
    if days_left < 0:
        return red(f'Overdue {abs(days_left)}d')
    label = 'Due today' if days_left == 0 else f'{days_left}d left'
    if pct >= 85:
        return red(label)
    elif pct >= 60:
        return yellow(label)
    return green(label)


# ── API helpers ───────────────────────────────────────────────────────────────

def _get(base_url, path):
    try:
        r = requests.get(f'{base_url}{path}', timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.ConnectionError:
        print(red(f'Cannot connect to {base_url}. Is the server running?'))
        sys.exit(1)
    except requests.HTTPError as e:
        print(red(f'API error {e.response.status_code}: {e.response.text}'))
        sys.exit(1)


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_stats(base_url, _args):
    d = _get(base_url, '/api/stats')
    print(bold('\n  LogiTrack — Dashboard Summary'))
    print('  ' + '─' * 34)
    print(f'  Total shipments : {bold(str(d["total"]))}')
    print(f'  Pending         : {yellow(str(d["pending"]))}')
    print(f'  In transit      : {str(d["in_transit"])}')
    print(f'  Delivered       : {green(str(d["delivered"]))}')
    print(f'  Delayed         : {red(str(d["delayed"])) if d["delayed"] else green("0")}')
    print(f'  Drivers         : {d["drivers"]}')
    print(f'  Hubs            : {d["hubs"]}')
    print()


def cmd_shipments(base_url, args):
    data = _get(base_url, '/api/shipments')
    status_filter = getattr(args, 'status', None)
    if status_filter:
        data = [s for s in data if s['status'] == status_filter]

    if not data:
        print(dim('  No shipments found.'))
        return

    print(bold(f'\n  Shipments{" [" + status_filter + "]" if status_filter else ""}'))
    print('  ' + '─' * 72)
    fmt = '  {:<4} {:<22} {:<12} {:<12} {:<10} {}'
    print(dim(fmt.format('#', 'Route', 'Cargo', 'Driver', 'Pay', 'Status')))
    print('  ' + '─' * 72)
    for s in data:
        route  = f'{s["origin_code"]} → {s["dest_code"]}'
        driver = (s['driver_name'] or dim('Unassigned'))[:11]
        pay    = f'${s["total_pay"]:,.0f}'
        status = _status_icon(s['status']) + ' ' + s['status']
        print(fmt.format(f'#{s["id"]}', route, s['cargo_type'][:11], driver, pay, status))
    print()


def cmd_shipment(base_url, args):
    d = _get(base_url, f'/api/shipments/{args.id}')
    if 'error' in d:
        print(red(f'  {d["error"]}'))
        return

    print(bold(f'\n  Shipment #{d["id"]}'))
    print('  ' + '─' * 42)
    print(f'  Route    : {d["origin_city"]} ({d["origin_code"]}) → {d["dest_city"]} ({d["dest_code"]})')
    print(f'  Cargo    : {d["cargo_type"]}  |  Weight: {d["weight_lbs"]:,.0f} lbs')
    print(f'  Pay      : ${d["total_pay"]:,.2f}')
    print(f'  Deadline : {d["deadline"]}')
    print(f'  Status   : {_status_icon(d["status"])} {d["status"]}')
    print(f'  Driver   : {d.get("driver_name") or dim("Unassigned")}')

    if 'route_distance' in d:
        dist  = d['route_distance']
        rpm   = d.get('rate_per_mile', 0)
        is_good = d.get('is_good_route', False)
        path  = ' → '.join(d.get('route_path', []))
        quality = green('✓ Good Route') if is_good else red('✗ Below $3.50/mi threshold')
        print(f'\n  {bold("Optimized Route")}')
        print(f'  Distance : {dist:,.1f} mi  |  Rate: ${rpm:.2f}/mi  |  {quality}')
        print(f'  Path     : {path}')
    print()


def cmd_drivers(base_url, _args):
    data = _get(base_url, '/api/drivers')
    if not data:
        print(dim('  No drivers registered.'))
        return
    print(bold('\n  Drivers'))
    print('  ' + '─' * 48)
    fmt = '  {:<4} {:<20} {:<14} {:<10} {}'
    print(dim(fmt.format('#', 'Name', 'Phone', 'CDL', 'Status')))
    print('  ' + '─' * 48)
    for d in data:
        status_str = (green('● Available') if d['status'] == 'available'
                      else (yellow('● On Route') if d['status'] == 'on-route'
                            else dim('● Off Duty')))
        print(fmt.format(
            f'#{d["id"]}',
            d['name'][:19],
            (d.get('phone') or dim('—'))[:13],
            (d.get('license_number') or dim('—'))[:9],
            status_str
        ))
    print()


def cmd_hubs(base_url, _args):
    data = _get(base_url, '/api/hubs')
    hubs = data['hubs']
    print(bold(f'\n  Hubs ({len(hubs)})'))
    print('  ' + '─' * 36)
    fmt = '  {:<6} {:<22} {}'
    print(dim(fmt.format('Code', 'City', 'State')))
    print('  ' + '─' * 36)
    for h in hubs:
        print(fmt.format(h['code'], h['city'], h['state']))
    print()


def cmd_route(base_url, args):
    d = _get(base_url, f'/api/distance/hubs/{args.origin}/{args.dest}')
    if 'error' in d:
        print(red(f'  {d["error"]}'))
        return
    path_str = ' → '.join(f'{h["city"]} ({h["code"]})' for h in d['path'])
    print(bold(f'\n  Route: hub {args.origin} → hub {args.dest}'))
    print('  ' + '─' * 52)
    print(f'  Distance     : {d["distance"]:,.1f} miles')
    print(f'  Stops        : {d["hops"]} intermediate hub(s)')
    print(f'  Min good pay : {green("$" + f"{d[\"min_good_pay\"]:,.2f}")} (3.5× rate)')
    print(f'  Path         : {path_str}')
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog='logitrack',
        description='LogiTrack CLI — interact with the server via the REST API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--url', default=DEFAULT_URL,
                        help=f'Server base URL (default: {DEFAULT_URL})')
    sub = parser.add_subparsers(dest='command', metavar='<command>')

    sub.add_parser('stats', help='Show dashboard summary')

    p_ships = sub.add_parser('shipments', help='List shipments')
    p_ships.add_argument('--status', choices=['pending', 'in-transit', 'delivered'],
                         help='Filter by status')

    p_ship = sub.add_parser('shipment', help='Show details + route for a shipment')
    p_ship.add_argument('id', type=int, help='Shipment ID')

    sub.add_parser('drivers', help='List all drivers')
    sub.add_parser('hubs',    help='List all hubs')

    p_route = sub.add_parser('route', help='Calculate shortest route between two hubs')
    p_route.add_argument('origin', type=int, help='Origin hub ID')
    p_route.add_argument('dest',   type=int, help='Destination hub ID')

    args = parser.parse_args()

    commands = {
        'stats':     cmd_stats,
        'shipments': cmd_shipments,
        'shipment':  cmd_shipment,
        'drivers':   cmd_drivers,
        'hubs':      cmd_hubs,
        'route':     cmd_route,
    }

    if args.command not in commands:
        parser.print_help()
        sys.exit(0)

    commands[args.command](args.url, args)


if __name__ == '__main__':
    main()
