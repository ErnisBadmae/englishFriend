// emotions_summary.cypher
// Params: $userId (int), $since (datetime string)
match (:User {userId:$userId})-[:PARTICIPATED_IN]->(s:Session)-[:CONTAINS]->(:Utterance)-[e:EXPRESSES]->(emo:Emotion)
where s.startedAt >= datetime($since)
return emo.code as emotion, count(*) as cnt
order by cnt desc;
