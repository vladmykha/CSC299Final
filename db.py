import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'logistics.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    with open(os.path.join(os.path.dirname(__file__), 'schema.sql')) as f:
        conn.executescript(f.read())
    conn.commit()
    if conn.execute('SELECT COUNT(*) FROM hubs').fetchone()[0] == 0:
        _seed_data(conn)
    conn.close()


def _seed_data(conn):
    hubs = [
        ('Chicago Hub',        'Chicago',       'IL', 'CHI'),
        ('Atlanta Hub',        'Atlanta',        'GA', 'ATL'),
        ('Dallas Hub',         'Dallas',         'TX', 'DAL'),
        ('Los Angeles Hub',    'Los Angeles',    'CA', 'LAX'),
        ('New York Hub',       'New York',       'NY', 'NYC'),
        ('Memphis Hub',        'Memphis',        'TN', 'MEM'),
        ('Louisville Hub',     'Louisville',     'KY', 'LOU'),
        ('Columbus Hub',       'Columbus',       'OH', 'CMH'),
        ('Indianapolis Hub',   'Indianapolis',   'IN', 'IND'),
        ('Kansas City Hub',    'Kansas City',    'MO', 'KCI'),
        ('Denver Hub',         'Denver',         'CO', 'DEN'),
        ('Phoenix Hub',        'Phoenix',        'AZ', 'PHX'),
        ('Seattle Hub',        'Seattle',        'WA', 'SEA'),
        ('Miami Hub',          'Miami',          'FL', 'MIA'),
        ('Houston Hub',        'Houston',        'TX', 'HOU'),
        ('Charlotte Hub',      'Charlotte',      'NC', 'CLT'),
        ('Nashville Hub',      'Nashville',      'TN', 'BNA'),
        ('St. Louis Hub',      'St. Louis',      'MO', 'STL'),
        ('Cincinnati Hub',     'Cincinnati',     'OH', 'CVG'),
        ('Philadelphia Hub',   'Philadelphia',   'PA', 'PHL'),
        ('Detroit Hub',        'Detroit',        'MI', 'DTW'),
        ('Minneapolis Hub',    'Minneapolis',    'MN', 'MSP'),
        ('Portland Hub',       'Portland',       'OR', 'PDX'),
        ('Salt Lake City Hub', 'Salt Lake City', 'UT', 'SLC'),
        ('San Antonio Hub',    'San Antonio',    'TX', 'SAT'),
    ]
    conn.executemany('INSERT INTO hubs (name, city, state, code) VALUES (?,?,?,?)', hubs)
    conn.commit()

    hub_map = {r['code']: r['id'] for r in conn.execute('SELECT id, code FROM hubs')}

    edges = [
        ('CHI', 'IND',  181), ('CHI', 'STL',  300), ('CHI', 'DTW',  281),
        ('CHI', 'MSP',  411), ('CHI', 'KCI',  500), ('IND', 'CMH',  175),
        ('IND', 'LOU',  114), ('IND', 'KCI',  480), ('CMH', 'PHL',  460),
        ('CMH', 'DTW',  173), ('CMH', 'CVG',  107), ('CVG', 'LOU',  100),
        ('CVG', 'CLT',  336), ('LOU', 'BNA',  175), ('LOU', 'MEM',  382),
        ('BNA', 'ATL',  250), ('BNA', 'MEM',  213), ('MEM', 'ATL',  393),
        ('MEM', 'DAL',  453), ('MEM', 'STL',  285), ('ATL', 'CLT',  245),
        ('ATL', 'MIA',  659), ('ATL', 'HOU',  790), ('CLT', 'PHL',  482),
        ('PHL', 'NYC',   95), ('MIA', 'HOU', 1188), ('HOU', 'DAL',  239),
        ('HOU', 'SAT',  197), ('DAL', 'SAT',  272), ('DAL', 'KCI',  490),
        ('DAL', 'DEN',  878), ('DAL', 'PHX', 1000), ('KCI', 'STL',  250),
        ('KCI', 'DEN',  600), ('KCI', 'MSP',  440), ('STL', 'MEM',  285),
        ('DEN', 'PHX',  602), ('DEN', 'SLC',  525), ('DEN', 'MSP',  920),
        ('PHX', 'LAX',  372), ('PHX', 'SAT',  855), ('SLC', 'SEA',  840),
        ('SLC', 'LAX',  690), ('SLC', 'PDX',  770), ('SEA', 'PDX',  174),
        ('LAX', 'PDX', 1080), ('DTW', 'PHL',  490), ('DTW', 'MSP',  698),
        ('MSP', 'STL',  560),
    ]

    route_data = [
        (hub_map[f], hub_map[t], d)
        for f, t, d in edges
        if f in hub_map and t in hub_map
    ]
    conn.executemany(
        'INSERT INTO hub_routes (hub_from, hub_to, distance_miles) VALUES (?,?,?)',
        route_data
    )
    conn.commit()
