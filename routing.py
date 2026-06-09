import networkx as nx


def build_graph(conn):
    G = nx.Graph()
    for hub in conn.execute('SELECT * FROM hubs'):
        G.add_node(hub['id'], city=hub['city'], code=hub['code'], state=hub['state'])
    for r in conn.execute('SELECT * FROM hub_routes'):
        G.add_edge(r['hub_from'], r['hub_to'], weight=r['distance_miles'])
    return G


def get_route(conn, origin_id, dest_id):
    G = build_graph(conn)
    if not G.has_node(origin_id) or not G.has_node(dest_id):
        return None
    try:
        path = nx.dijkstra_path(G, origin_id, dest_id, weight='weight')
        distance = nx.dijkstra_path_length(G, origin_id, dest_id, weight='weight')
        hub_map = {h['id']: dict(h) for h in conn.execute('SELECT * FROM hubs')}
        return {
            'path': path,
            'path_details': [hub_map[n] for n in path],
            'distance': round(distance, 1),
            'hops': len(path) - 1,
        }
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None
