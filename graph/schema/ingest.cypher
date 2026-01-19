// ingest.cypher
// Batch MERGE scripts for sync-graph worker.

// Process sessions data
merge (u:User {userId: $user_id})
  on create set u.created = datetime()
  on match set u.updated = datetime()

// Convert microseconds epoch to milliseconds for Neo4j datetime
with u,
     $started_at as startedAtParam,
     $ended_at as endedAtParam,
     $lang_code as langParam
merge (s:Session {id: $id})
  on create set
    s.startedAt = datetime({epochMillis: toInteger(startedAtParam / 1000)}),
    s.endedAt = CASE WHEN endedAtParam IS NULL THEN NULL ELSE datetime({epochMillis: toInteger(endedAtParam / 1000)}) END,
    s.langCode = coalesce(langParam, 'en')
  on match set s.updated = datetime()

merge (u)-[:PARTICIPATED_IN]->(s)
