// recommend_topics.cypher
// Input params: $userId (int)
match (u:User {userId:$userId})-[i:INTEREST_IN]->(t:Topic)-[rel:RELATED_TO]->(t2:Topic)
with t2, sum(i.weight * rel.weight) as score
order by score desc
return t2.slug as topic, score
limit 10;
