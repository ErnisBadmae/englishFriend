// query_checks.cypher
// Seeds a small subgraph and validates recommendation/emotion queries.

match (n) detach delete n;

create (u:User {userId:1})
create (t1:Topic {id:'A', slug:'ai', name:'AI'})
create (t2:Topic {id:'B', slug:'design', name:'Design'})
create (t1)-[:RELATED_TO {weight:0.8}]->(t2)
create (u)-[:INTEREST_IN {weight:0.9}]->(t1)
create (s:Session {id:'S1', startedAt:datetime('2025-01-10T10:00:00Z')})
create (u)-[:PARTICIPATED_IN]->(s)
create (utt:Utterance {id:'U1'})
create (s)-[:CONTAINS]->(utt)
create (emo:Emotion {code:'joy', valence:4, arousal:3})
create (utt)-[:EXPRESSES {score:0.7}]->(emo);

// Test recommendation query
call {
  match (u:User {userId:1})-[i:INTEREST_IN]->(t:Topic)-[rel:RELATED_TO]->(t2:Topic)
  with t2, sum(i.weight * rel.weight) as score
  order by score desc
  return collect({topic:t2.slug, score:score}) as recs
}
// Test emotion summary
call {
  match (:User {userId:1})-[:PARTICIPATED_IN]->(s:Session)-[:CONTAINS]->(:Utterance)-[e:EXPRESSES]->(emo:Emotion)
  where s.startedAt >= datetime('2025-01-01T00:00:00Z')
  with emo.code as emotion, count(e) as cnt
  return collect({emotion:emotion, cnt:cnt}) as emotions
}
return recs, emotions;
