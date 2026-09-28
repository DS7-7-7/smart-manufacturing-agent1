// === 자동차 조립 A라인 지식 그래프 (auto-generated) ===
// 초기화가 필요하면: MATCH (n) DETACH DELETE n;

CREATE CONSTRAINT IF NOT EXISTS FOR (n:Process) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Equipment) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Part) REQUIRE n.id IS UNIQUE;

// --- 노드 ---
MERGE (:Process {id:"P1_프레스", name:"프레스", code:"P1"});
MERGE (:Process {id:"P2_차체용접", name:"차체용접", code:"P2"});
MERGE (:Equipment {id:"E1_프레스기", name:"프레스기", code:"E1"});
MERGE (:Part {id:"강판", name:"강판"});
MERGE (:Equipment {id:"E2_용접로봇", name:"용접로봇", code:"E2"});
MERGE (:Part {id:"차체BIW", name:"차체BIW"});
MERGE (:Equipment {id:"E5_컨베이어A", name:"컨베이어A", code:"E5"});
MERGE (:Equipment {id:"E3_도장로봇", name:"도장로봇", code:"E3"});
MERGE (:Part {id:"도료", name:"도료"});
MERGE (:Equipment {id:"E4_건조오븐", name:"건조오븐", code:"E4"});
MERGE (:Equipment {id:"E6_조립로봇", name:"조립로봇", code:"E6"});
MERGE (:Part {id:"엔진모듈", name:"엔진모듈"});
MERGE (:Equipment {id:"E7_토크건", name:"토크건", code:"E7"});
MERGE (:Part {id:"볼트너트", name:"볼트너트"});
MERGE (:Equipment {id:"E8_비전검사기", name:"비전검사기", code:"E8"});
MERGE (:Equipment {id:"E9_에어컴프레서", name:"에어컴프레서", code:"E9"});
MERGE (:Equipment {id:"E10_배기설비", name:"배기설비", code:"E10"});
MERGE (:Process {id:"P3_도장", name:"도장", code:"P3"});

// --- 온톨로지 관계 ---
MATCH (a {id:"P1_프레스"}),(b {id:"P2_차체용접"}) MERGE (a)-[:PRECEDES]->(b);
MATCH (a {id:"E1_프레스기"}),(b {id:"강판"}) MERGE (a)-[:CONSUMES]->(b);
MATCH (a {id:"E2_용접로봇"}),(b {id:"차체BIW"}) MERGE (a)-[:PRODUCES]->(b);
MATCH (a {id:"E5_컨베이어A"}),(b {id:"E3_도장로봇"}) MERGE (a)-[:FEEDS]->(b);
MATCH (a {id:"E3_도장로봇"}),(b {id:"도료"}) MERGE (a)-[:CONSUMES]->(b);
MATCH (a {id:"E3_도장로봇"}),(b {id:"차체BIW"}) MERGE (a)-[:PRODUCES]->(b);
MATCH (a {id:"E3_도장로봇"}),(b {id:"E9_에어컴프레서"}) MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {id:"E3_도장로봇"}),(b {id:"E10_배기설비"}) MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {id:"E4_건조오븐"}),(b {id:"차체BIW"}) MERGE (a)-[:PRODUCES]->(b);
MATCH (a {id:"E6_조립로봇"}),(b {id:"엔진모듈"}) MERGE (a)-[:CONSUMES]->(b);
MATCH (a {id:"E6_조립로봇"}),(b {id:"차체BIW"}) MERGE (a)-[:PRODUCES]->(b);
MATCH (a {id:"E7_토크건"}),(b {id:"볼트너트"}) MERGE (a)-[:CONSUMES]->(b);
MATCH (a {id:"E7_토크건"}),(b {id:"E9_에어컴프레서"}) MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {id:"E8_비전검사기"}),(b {id:"E7_토크건"}) MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {id:"E9_에어컴프레서"}),(b {id:"P3_도장"}) MERGE (a)-[:RUNS_ON]->(b);
MATCH (a {id:"E10_배기설비"}),(b {id:"P3_도장"}) MERGE (a)-[:RUNS_ON]->(b);

// --- 유도 관계 IMPACTS (고장 전파: u 고장 시 v 피해) ---
MATCH (a {id:"P1_프레스"}),(b {id:"P2_차체용접"}) MERGE (a)-[:IMPACTS {via:"PRECEDES"}]->(b);
MATCH (a {id:"E5_컨베이어A"}),(b {id:"E3_도장로봇"}) MERGE (a)-[:IMPACTS {via:"FEEDS"}]->(b);
MATCH (a {id:"E7_토크건"}),(b {id:"E8_비전검사기"}) MERGE (a)-[:IMPACTS {via:"DEPENDS_ON"}]->(b);
MATCH (a {id:"E9_에어컴프레서"}),(b {id:"E3_도장로봇"}) MERGE (a)-[:IMPACTS {via:"DEPENDS_ON"}]->(b);
MATCH (a {id:"E9_에어컴프레서"}),(b {id:"E7_토크건"}) MERGE (a)-[:IMPACTS {via:"DEPENDS_ON"}]->(b);
MATCH (a {id:"E9_에어컴프레서"}),(b {id:"P3_도장"}) MERGE (a)-[:IMPACTS {via:"RUNS_ON"}]->(b);
MATCH (a {id:"E10_배기설비"}),(b {id:"E3_도장로봇"}) MERGE (a)-[:IMPACTS {via:"DEPENDS_ON"}]->(b);
MATCH (a {id:"E10_배기설비"}),(b {id:"P3_도장"}) MERGE (a)-[:IMPACTS {via:"RUNS_ON"}]->(b);

// === 예제 질의 ===
// 1) 전체 그래프 보기:
//   MATCH (n)-[r]->(m) RETURN n,r,m;
// 2) ★도미노★ 에어컴프레서(E9) 고장 시 연쇄 타격 전체:
//   MATCH (s {code:'E9'})-[:IMPACTS*1..]->(hit) RETURN DISTINCT hit.id;
// 3) 홉수까지 함께:
//   MATCH p=(s {code:'E9'})-[:IMPACTS*1..]->(hit)
//   RETURN hit.id, min(length(p)) AS hop ORDER BY hop;