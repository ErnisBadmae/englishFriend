// ingest.cypher
// Batch MERGE scripts for sync-graph worker.

// Simple test - just create a node with the data
merge (n:TestNode {id: 'test'})
  on create set n.created = datetime()
  on match set n.updated = datetime()
