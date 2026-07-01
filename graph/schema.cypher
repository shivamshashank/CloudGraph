// =============================================================================
// CloudGraph — Neo4j Database Schema Setup
// Week 3: Constraints & Indexes
// =============================================================================

// Unique Identity Constraints
CREATE CONSTRAINT service_name_unique IF NOT EXISTS
FOR (s:Service) REQUIRE s.name IS UNIQUE;

CREATE CONSTRAINT pod_id_unique IF NOT EXISTS
FOR (p:Pod) REQUIRE p.id IS UNIQUE;

CREATE CONSTRAINT node_name_unique IF NOT EXISTS
FOR (n:Node) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT deployment_name_unique IF NOT EXISTS
FOR (d:Deployment) REQUIRE d.name IS UNIQUE;

CREATE CONSTRAINT incident_id_unique IF NOT EXISTS
FOR (i:Incident) REQUIRE i.id IS UNIQUE;

CREATE CONSTRAINT commit_sha_unique IF NOT EXISTS
FOR (c:Commit) REQUIRE c.sha IS UNIQUE;

CREATE CONSTRAINT log_id_unique IF NOT EXISTS
FOR (l:Log) REQUIRE l.id IS UNIQUE;

CREATE CONSTRAINT metric_id_unique IF NOT EXISTS
FOR (m:Metric) REQUIRE m.id IS UNIQUE;

// Performance Indexes
CREATE INDEX metric_time_idx IF NOT EXISTS
FOR (m:Metric) ON (m.timestamp);

CREATE INDEX log_time_idx IF NOT EXISTS
FOR (l:Log) ON (l.timestamp);

CREATE INDEX log_level_idx IF NOT EXISTS
FOR (l:Log) ON (l.level);

CREATE INDEX incident_time_idx IF NOT EXISTS
FOR (i:Incident) ON (i.startTime);
