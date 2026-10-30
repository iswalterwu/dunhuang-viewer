-- 目录数据与原始材料分离；稳定 UUID 由应用分配，不从路径生成。
CREATE TABLE import_run (
    id bigserial PRIMARY KEY,
    started_at timestamptz NOT NULL DEFAULT now(),
    ended_at timestamptz,
    status text NOT NULL,
    triggered_by text NOT NULL,
    rule_version text NOT NULL,
    code_version text NOT NULL,
    v0_snapshot_status text NOT NULL DEFAULT 'unavailable',
    v0_snapshot_error text,
    health_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    cache_access jsonb NOT NULL DEFAULT '[]'::jsonb,
    counts jsonb NOT NULL DEFAULT '{}'::jsonb,
    error text
);

CREATE TABLE item (
    id uuid PRIMARY KEY,
    serial bigint NOT NULL UNIQUE,
    grouping_key text UNIQUE,
    parent_id uuid REFERENCES item(id) DEFERRABLE INITIALLY DEFERRED,
    original_positions jsonb NOT NULL,
    display_policy text NOT NULL,
    provenance jsonb NOT NULL,
    clues jsonb NOT NULL,
    field_basis jsonb NOT NULL,
    created_run bigint NOT NULL REFERENCES import_run(id),
    updated_run bigint NOT NULL REFERENCES import_run(id)
);

CREATE TABLE identifier (
    id bigserial PRIMARY KEY,
    item_id uuid NOT NULL REFERENCES item(id),
    system text NOT NULL,
    raw text NOT NULL,
    normalized text NOT NULL,
    parent_number text,
    part text,
    source text NOT NULL,
    source_path text NOT NULL,
    is_primary boolean NOT NULL DEFAULT false,
    compliant boolean NOT NULL,
    state text NOT NULL,
    since_run bigint NOT NULL REFERENCES import_run(id),
    until_run bigint REFERENCES import_run(id),
    field_basis jsonb NOT NULL,
    CHECK (NOT is_primary OR (compliant AND system IN ('pelliot', 'nlc')))
);
CREATE UNIQUE INDEX identifier_one_primary ON identifier(item_id) WHERE is_primary AND state = 'current';
CREATE INDEX identifier_lookup ON identifier(lower(normalized)) WHERE state = 'current';
CREATE INDEX identifier_parent_lookup ON identifier(lower(parent_number)) WHERE state = 'current';
CREATE INDEX identifier_item ON identifier(item_id, state);

CREATE TABLE image (
    id uuid PRIMARY KEY,
    root text NOT NULL,
    relative_path text NOT NULL,
    original_name text NOT NULL,
    original_path text NOT NULL,
    hidden boolean NOT NULL,
    kind text NOT NULL,
    size bigint NOT NULL,
    mtime_ns bigint NOT NULL,
    inode bigint NOT NULL,
    read_ok boolean NOT NULL,
    read_error text,
    facts jsonb NOT NULL,
    lineage text NOT NULL,
    collection text NOT NULL,
    acquisition text NOT NULL,
    license text NOT NULL,
    attribution text NOT NULL,
    display_policy text NOT NULL,
    external_policy text NOT NULL,
    canvas_number integer,
    canvas_id text,
    state text NOT NULL,
    first_seen bigint NOT NULL REFERENCES import_run(id),
    last_seen bigint NOT NULL REFERENCES import_run(id),
    missing_since timestamptz,
    field_basis jsonb NOT NULL
);
CREATE UNIQUE INDEX image_present_position ON image(root, relative_path) WHERE state = 'present';
CREATE INDEX image_signature ON image(root, inode, size, mtime_ns);
CREATE INDEX image_lineage ON image(lineage);

CREATE TABLE image_path_history (
    image_id uuid NOT NULL REFERENCES image(id),
    root text NOT NULL,
    relative_path text NOT NULL,
    since_run bigint NOT NULL REFERENCES import_run(id),
    until_run bigint REFERENCES import_run(id),
    PRIMARY KEY (image_id, since_run)
);

CREATE TABLE item_image (
    item_id uuid NOT NULL REFERENCES item(id),
    image_id uuid NOT NULL REFERENCES image(id),
    role text NOT NULL,
    source_directory text NOT NULL,
    unit_key text NOT NULL,
    field_basis jsonb NOT NULL,
    PRIMARY KEY (item_id, image_id)
);
CREATE INDEX item_image_reverse ON item_image(image_id);

CREATE TABLE attachment (
    id uuid PRIMARY KEY,
    root text NOT NULL,
    relative_path text NOT NULL,
    kind text NOT NULL,
    raw bytea NOT NULL,
    encoding text,
    created_run bigint NOT NULL REFERENCES import_run(id),
    updated_run bigint NOT NULL REFERENCES import_run(id),
    UNIQUE (root, relative_path)
);
CREATE TABLE item_attachment (
    item_id uuid NOT NULL REFERENCES item(id),
    attachment_id uuid NOT NULL REFERENCES attachment(id),
    PRIMARY KEY (item_id, attachment_id)
);

CREATE TABLE derivation (
    image_id uuid NOT NULL REFERENCES image(id),
    source_image_id uuid NOT NULL REFERENCES image(id),
    method text NOT NULL,
    evidence_file text NOT NULL,
    evidence_line integer NOT NULL,
    field_basis jsonb NOT NULL,
    PRIMARY KEY (image_id, source_image_id)
);

CREATE TABLE provenance_history (
    id bigserial PRIMARY KEY,
    item_id uuid NOT NULL REFERENCES item(id),
    run_id bigint NOT NULL REFERENCES import_run(id),
    value jsonb NOT NULL,
    field_basis jsonb NOT NULL
);
CREATE INDEX provenance_history_item ON provenance_history(item_id, run_id);

CREATE TABLE history (
    object_kind text NOT NULL,
    object_id uuid NOT NULL,
    run_id bigint NOT NULL REFERENCES import_run(id),
    snapshot jsonb NOT NULL,
    field_basis jsonb NOT NULL,
    PRIMARY KEY (object_kind, object_id, run_id)
);

CREATE TABLE anomaly (
    id bigserial PRIMARY KEY,
    run_id bigint NOT NULL REFERENCES import_run(id),
    category text NOT NULL,
    object_kind text NOT NULL,
    object_key text NOT NULL,
    root text,
    relative_path text,
    raw text NOT NULL,
    description text NOT NULL
);
CREATE INDEX anomaly_run_category ON anomaly(run_id, category);
CREATE INDEX anomaly_object ON anomaly(run_id, object_kind, object_key);

CREATE TABLE excluded (
    run_id bigint NOT NULL REFERENCES import_run(id),
    root text NOT NULL,
    relative_path text NOT NULL,
    reason text NOT NULL,
    PRIMARY KEY (run_id, root, relative_path)
);

CREATE TABLE v0_volume (
    run_id bigint NOT NULL REFERENCES import_run(id),
    volume_id text NOT NULL,
    relative_directory text NOT NULL,
    PRIMARY KEY (run_id, volume_id)
);
