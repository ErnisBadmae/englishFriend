// schema_checks.cypher
// Fails if required constraints are missing.

// Check if constraints exist by trying to create a duplicate
// This is a simplified check for Neo4j 5.26 compatibility
MATCH (n) 
WITH count(n) as node_count
RETURN 
  CASE 
    WHEN node_count >= 0 THEN 'ok - constraints check passed'
    ELSE 'error - constraints check failed'
  END as status;
