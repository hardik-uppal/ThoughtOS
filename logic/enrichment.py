class EnrichmentManager:
    def __init__(self, graph_manager):
        self.gm = graph_manager

    def link_temporal_context(self):
        """
        Links Transactions and Events that happened on the same day.
        """
        if not self.gm.driver:
            return 0

        # Cypher query to link nodes based on date matching
        # Note: e.start is ISO8601 (YYYY-MM-DDTHH:MM:SS), t.date is YYYY-MM-DD
        query = """
        MATCH (t:Transaction), (e:Event)
        WHERE t.date = substring(e.start, 0, 10)
        MERGE (t)-[r:HAPPENED_ON_DAY]->(e)
        RETURN count(r) as links_created
        """
        
        try:
            result = self.gm.run_cypher(query)
            if result:
                return result[0]['links_created']
            return 0
        except Exception as e:
            print(f"Enrichment Error: {e}")
            return 0
