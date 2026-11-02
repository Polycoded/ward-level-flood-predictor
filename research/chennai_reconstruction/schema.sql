-- Proposed PostGIS schema for review. Not executed by the application.
-- All geometries are stored in EPSG:32644; preserve source geometry separately.

CREATE TYPE label_state AS ENUM ('positive', 'negative', 'unknown');
CREATE TYPE confidence_level AS ENUM ('high', 'medium', 'low');
CREATE TYPE coverage_status AS ENUM ('complete', 'partial', 'unobserved');

CREATE TABLE boundary_versions (
    boundary_version      text PRIMARY KEY,
    label                 text NOT NULL,
    effective_from        date,
    effective_to          date,
    gazette_notification  text,
    gazette_date          date,
    source_id             text NOT NULL,
    source_url            text,
    licence               text,
    licence_status        text NOT NULL,
    crs                   text NOT NULL,
    geometry_sha256       text,
    status                text NOT NULL CHECK (status IN ('authoritative','provisional','rejected')),
    notes                 text
);

CREATE TABLE wards (
    boundary_version      text NOT NULL REFERENCES boundary_versions(boundary_version),
    ward_id               integer NOT NULL,
    official_number       text NOT NULL,
    ward_name             text,
    zone_number           text,
    zone_name             text,
    area_m2               double precision NOT NULL CHECK (area_m2 > 0),
    geometry              geometry(Geometry, 32644) NOT NULL,
    geometry_source_id    text,
    is_valid              boolean NOT NULL,
    PRIMARY KEY (boundary_version, ward_id),
    UNIQUE (boundary_version, official_number)
);

CREATE TABLE crosswalk (
    from_version          text NOT NULL REFERENCES boundary_versions(boundary_version),
    from_ward_id          integer NOT NULL,
    to_version            text NOT NULL REFERENCES boundary_versions(boundary_version),
    to_ward_id            integer NOT NULL,
    relation              text NOT NULL CHECK (relation IN ('same','split','merged','renumbered','ambiguous')),
    evidence_source_id    text,
    review_status         text NOT NULL,
    reviewer              text,
    notes                 text,
    PRIMARY KEY (from_version, from_ward_id, to_version, to_ward_id)
);

CREATE TABLE flood_events (
    event_id              text PRIMARY KEY,
    event_name            text NOT NULL,
    event_date            date,
    observation_start     timestamptz,
    observation_end       timestamptz,
    boundary_version      text NOT NULL REFERENCES boundary_versions(boundary_version),
    rainfall_source_id    text,
    event_metadata_json   jsonb NOT NULL DEFAULT '{}'::jsonb,
    review_status         text NOT NULL DEFAULT 'pending',
    notes                 text
);

CREATE TABLE scenes (
    scene_id              text PRIMARY KEY,
    sensor                text NOT NULL,
    platform              text,
    acquisition_start     timestamptz NOT NULL,
    acquisition_end       timestamptz,
    flight_direction      text,
    relative_orbit        integer,
    polarization          text,
    processing_level      text,
    footprint             geometry(Geometry, 4326),
    source_id             text NOT NULL,
    source_url            text,
    licence               text,
    file_sha256           text,
    coverage_status       coverage_status NOT NULL,
    notes                 text
);

CREATE TABLE ward_event_scenes (
    event_id              text NOT NULL REFERENCES flood_events(event_id),
    scene_id              text NOT NULL REFERENCES scenes(scene_id),
    role                  text NOT NULL CHECK (role IN ('pre','post','supporting')),
    PRIMARY KEY (event_id, scene_id, role)
);

CREATE TABLE label_protocols (
    protocol_version      text PRIMARY KEY,
    description           text NOT NULL,
    positive_rule         text NOT NULL,
    negative_rule         text NOT NULL,
    unknown_rule          text NOT NULL,
    min_patch_m2          double precision,
    min_fraction          double precision,
    min_coverage          double precision,
    permanent_water_source_id text,
    threshold_method      text,
    created_at            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ward_event_labels (
    label_id              bigserial PRIMARY KEY,
    ward_id               integer NOT NULL,
    boundary_version      text NOT NULL REFERENCES boundary_versions(boundary_version),
    event_id              text NOT NULL REFERENCES flood_events(event_id),
    protocol_version      text NOT NULL REFERENCES label_protocols(protocol_version),
    inundated_area_m2     double precision CHECK (inundated_area_m2 >= 0),
    ward_area_m2          double precision CHECK (ward_area_m2 > 0),
    inundated_fraction    double precision CHECK (inundated_fraction >= 0 AND inundated_fraction <= 1),
    observed_area_m2      double precision CHECK (observed_area_m2 >= 0),
    inundated_fraction_observed double precision CHECK (inundated_fraction_observed >= 0 AND inundated_fraction_observed <= 1),
    observation_start     timestamptz,
    observation_end       timestamptz,
    observation_coverage  double precision CHECK (observation_coverage >= 0 AND observation_coverage <= 1),
    label                 label_state NOT NULL,
    confidence            confidence_level NOT NULL,
    source                text NOT NULL,
    uncertainty_reason    text,
    negative_support_ref  text,
    scene_ids             text[] NOT NULL DEFAULT '{}',
    threshold_method      text,
    review_status         text NOT NULL DEFAULT 'pending',
    reviewer              text,
    reviewed_at           timestamptz,
    created_at            timestamptz NOT NULL DEFAULT now(),
    UNIQUE (ward_id, boundary_version, event_id),
    CHECK (inundated_area_m2 IS NULL OR ward_area_m2 IS NULL OR inundated_area_m2 <= ward_area_m2),
    CHECK (label <> 'positive' OR (inundated_area_m2 > 0 AND source IS NOT NULL)),
    CHECK (label <> 'negative' OR (observation_coverage IS NOT NULL AND negative_support_ref IS NOT NULL)),
    CHECK (label <> 'unknown' OR uncertainty_reason IS NOT NULL)
);

CREATE TABLE label_evidence (
    evidence_id           bigserial PRIMARY KEY,
    label_id              bigint NOT NULL REFERENCES ward_event_labels(label_id) ON DELETE CASCADE,
    source_id             text NOT NULL,
    evidence_type         text NOT NULL CHECK (evidence_type IN ('sar','optical','official_report','news','high_water_mark','field','model')),
    source_url            text,
    observed_at           timestamptz,
    geometry              geometry(Geometry, 4326),
    confidence            confidence_level NOT NULL,
    notes                 text
);

CREATE TABLE feature_catalog (
    feature_name          text PRIMARY KEY,
    unit                  text NOT NULL,
    physical_relevance    text NOT NULL,
    source_id             text NOT NULL,
    native_resolution     text,
    temporal_vintage      text,
    class                 text NOT NULL CHECK (class IN ('static','dynamic','event_forcing','exposure')),
    licence_status        text,
    notes                 text
);

CREATE TABLE ward_event_features (
    ward_id               integer NOT NULL,
    boundary_version      text NOT NULL REFERENCES boundary_versions(boundary_version),
    event_id              text REFERENCES flood_events(event_id),
    feature_name          text NOT NULL REFERENCES feature_catalog(feature_name),
    value                 double precision,
    observed_coverage     double precision,
    source_id             text NOT NULL,
    source_version        text,
    is_imputed            boolean NOT NULL DEFAULT false,
    PRIMARY KEY (ward_id, boundary_version, event_id, feature_name)
);

CREATE TABLE boundary_overlaps (
    overlap_id             bigserial PRIMARY KEY,
    boundary_version       text NOT NULL REFERENCES boundary_versions(boundary_version),
    ward_id_a              integer NOT NULL,
    ward_id_b              integer NOT NULL,
    area_m2                double precision NOT NULL CHECK (area_m2 > 0),
    fraction_of_smaller    double precision,
    compactness            double precision,
    classification         text NOT NULL CHECK (classification IN ('artifact','sliver','substantial','unresolved')),
    fold_relation          text,
    resolution_status      text NOT NULL DEFAULT 'unresolved',
    notes                  text,
    UNIQUE (boundary_version, ward_id_a, ward_id_b)
);
