// ingest.cypher
// Batch MERGE scripts for sync-graph worker.

// Process sessions data
merge (u:User {userId: $user_id})
  on create set u.created = datetime()
  on match set u.updated = datetime()

with $started_at as startedAtParam,
     $ended_at as endedAtParam,
     $lang_code as langParam
merge (s:Session {id: $id})
  on create set
    s.startedAt = datetime(startedAtParam),
    s.endedAt = CASE WHEN endedAtParam IS NULL THEN NULL ELSE datetime(endedAtParam) END,
    s.langCode = coalesce(langParam, 'en')
  on match set s.updated = datetime()

merge (u)-[:PARTICIPATED_IN]->(s)
