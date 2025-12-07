"""
Helper functions for adding context notes to Neo4j nodes.
"""

def add_note_to_node(graph_manager, node_type, node_id, note):
    """
    Adds a note property to a Neo4j node.
    
    Args:
        graph_manager: GraphManager instance
        node_type: 'Event', 'Transaction', or 'Entry'
        node_id: ID of the node
        note: Text note to attach
    
    Returns:
        Success message or error
    """
    if not graph_manager.verify_connection():
        return "Neo4j is not connected"
    
    query = f"""
    MATCH (n:{node_type} {{id: $id}})
    SET n.note = $note
    RETURN n
    """
    
    try:
        result = graph_manager.query(query, {'id': node_id, 'note': note})
        if result:
            return f"Note added to {node_type}"
        else:
            return f"{node_type} not found"
    except Exception as e:
        return f"Error: {str(e)}"

def get_note_from_node(graph_manager, node_type, node_id):
    """
    Retrieves the note from a Neo4j node.
    
    Args:
        graph_manager: GraphManager instance
        node_type: 'Event', 'Transaction', or 'Entry'
        node_id: ID of the node
    
    Returns:
        Note text or None
    """
    if not graph_manager.verify_connection():
        return None
    
    query = f"""
    MATCH (n:{node_type} {{id: $id}})
    RETURN n.note as note
    """
    
    try:
        result = graph_manager.query(query, {'id': node_id})
        if result and len(result) > 0:
            return result[0].get('note')
        return None
    except Exception:
        return None
