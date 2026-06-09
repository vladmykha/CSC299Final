CREATE TABLE IF NOT EXISTS hubs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    code TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS hub_routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hub_from INTEGER NOT NULL,
    hub_to INTEGER NOT NULL,
    distance_miles REAL NOT NULL,
    FOREIGN KEY (hub_from) REFERENCES hubs(id),
    FOREIGN KEY (hub_to) REFERENCES hubs(id),
    UNIQUE(hub_from, hub_to)
);

CREATE TABLE IF NOT EXISTS shipments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origin_hub INTEGER NOT NULL,
    destination_hub INTEGER NOT NULL,
    cargo_type TEXT NOT NULL,
    weight_lbs REAL NOT NULL,
    deadline TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'in-transit', 'delivered')),
    total_pay REAL NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    notes TEXT DEFAULT '',
    FOREIGN KEY (origin_hub) REFERENCES hubs(id),
    FOREIGN KEY (destination_hub) REFERENCES hubs(id)
);
