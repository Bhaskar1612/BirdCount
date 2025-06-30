CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_guest BOOLEAN DEFAULT false,
    is_admin BOOLEAN DEFAULT false,
    reset_token VARCHAR(255),
    reset_token_expiry TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    species_code VARCHAR(10) -- TGR, LEO, ELE, etc.
);

-- Species individual counters for consistent ID generation
CREATE TABLE IF NOT EXISTS species_individual_counters (
    species_id INTEGER PRIMARY KEY REFERENCES classes(id),
    next_individual_id INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS images (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    filepath VARCHAR(255) NOT NULL,
    width FLOAT NOT NULL,
    height FLOAT NOT NULL,
    user_id INTEGER REFERENCES users(id),
    model_type INTEGER NOT NULL,
    consent BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS model_predicted_boxes (
    id SERIAL PRIMARY KEY,
    image_id INTEGER REFERENCES images(id),
    class_id INTEGER REFERENCES classes(id),
    x FLOAT NOT NULL,
    y FLOAT NOT NULL,
    width FLOAT NOT NULL,
    height FLOAT NOT NULL,
    confidence FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_annotated_boxes (
    id SERIAL PRIMARY KEY,
    image_id INTEGER REFERENCES images(id),
    user_id INTEGER REFERENCES users(id),
    class_id INTEGER REFERENCES classes(id),
    x FLOAT NOT NULL,
    y FLOAT NOT NULL,
    width FLOAT NOT NULL,
    height FLOAT NOT NULL,
    confidence FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS active_learning_boxes (
    id SERIAL PRIMARY KEY,
    image_id INTEGER REFERENCES images(id),
    user_id INTEGER REFERENCES users(id),
    class_id INTEGER REFERENCES classes(id),
    x FLOAT NOT NULL,
    y FLOAT NOT NULL,
    width FLOAT NOT NULL,
    height FLOAT NOT NULL,
    confidence FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS annotations (
    id SERIAL PRIMARY KEY,
    image_id INTEGER REFERENCES images(id),
    width FLOAT NOT NULL,
    height FLOAT NOT NULL,
    cluster_centers JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS active_learning_rankings (
    id SERIAL PRIMARY KEY,
    image_id INTEGER REFERENCES images(id),
    algorithm_type VARCHAR(50) NOT NULL,
    ranking_score FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(image_id, algorithm_type)
);

CREATE EXTENSION IF NOT EXISTS vector;

-- ReID Schema

CREATE TABLE IF NOT EXISTS reid_sessions (
    id VARCHAR(255) PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    species_id INTEGER REFERENCES classes(id) NOT NULL,
    use_global_gallery BOOLEAN DEFAULT false,
    query_pre_cropped BOOLEAN DEFAULT false,
    gallery_pre_cropped BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    consent BOOLEAN DEFAULT false,
    processing_status VARCHAR(50) DEFAULT 'uploading', -- uploading, processing, completed, failed
    progress_percentage INTEGER DEFAULT 0,
    feature_model VARCHAR(50) DEFAULT 'megadescriptor' -- 'megadescriptor' or 'miewid'
);

-- Stores original uploaded images (query or gallery sets)
CREATE TABLE IF NOT EXISTS uploaded_images (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) REFERENCES reid_sessions(id),
    image_path VARCHAR(255) NOT NULL,
    image_type VARCHAR(10) NOT NULL, -- 'query' or 'gallery'
    user_id INTEGER REFERENCES users(id),
    species_id INTEGER REFERENCES classes(id),
    is_pre_cropped BOOLEAN DEFAULT false,
    is_global BOOLEAN DEFAULT false, -- for gallery images that become part of global gallery
    created_at TIMESTAMP DEFAULT NOW()
);

-- Store individual animal crops from each uploaded image
CREATE TABLE IF NOT EXISTS animal_crops (
    id SERIAL PRIMARY KEY,
    uploaded_image_id INTEGER REFERENCES uploaded_images(id),
    crop_coordinates JSONB NOT NULL, -- {x, y, width, height, confidence}
    animal_sequence INTEGER NOT NULL, -- 1st, 2nd, 3rd animal in the image
    animal_id VARCHAR(255),
    detection_confidence FLOAT, -- MegaDetector confidence
    cropped_image_path VARCHAR(255), -- Path to saved crop file
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(uploaded_image_id, animal_sequence)
);

-- Main gallery table with embeddings
CREATE TABLE IF NOT EXISTS gallery_images (
    id SERIAL PRIMARY KEY,
    animal_crop_id INTEGER REFERENCES animal_crops(id),
    session_id VARCHAR(255) REFERENCES reid_sessions(id),
    species_id INTEGER REFERENCES classes(id),
    animal_id VARCHAR(255) NOT NULL,
    user_id INTEGER REFERENCES users(id),
    is_global BOOLEAN DEFAULT false,
    model_used VARCHAR(50) DEFAULT 'megadescriptor', -- 'megadescriptor' or 'miewid'
    embedding VECTOR(1536), -- Stores MegaDescriptor embeddings directly
    embedding_miewid VECTOR(2152), -- Stores MiewID embeddings directly
    created_at TIMESTAMP DEFAULT NOW()
);

-- Query images (crops from query set)
CREATE TABLE IF NOT EXISTS query_images (
    id SERIAL PRIMARY KEY,
    animal_crop_id INTEGER REFERENCES animal_crops(id),
    session_id VARCHAR(255) REFERENCES reid_sessions(id),
    model_used VARCHAR(50) DEFAULT 'megadescriptor', -- 'megadescriptor' or 'miewid'
    embedding VECTOR(1536), -- Store MegaDescriptor embeddings directly
    embedding_miewid VECTOR(2152), -- Store MiewID embeddings directly
    assigned_animal_id VARCHAR(255), -- Auto-assigned ID based on top match
    assignment_confidence FLOAT, -- Similarity score for the assignment
    is_new_individual BOOLEAN DEFAULT false, -- True if no strong match found
    created_at TIMESTAMP DEFAULT NOW()
);

-- Matches between query and gallery crops
CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) REFERENCES reid_sessions(id),
    query_image_id INTEGER REFERENCES query_images(id),
    gallery_image_id INTEGER REFERENCES gallery_images(id),
    score FLOAT NOT NULL,
    rank INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_feedback (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) REFERENCES reid_sessions(id),
    query_image_id INTEGER REFERENCES query_images(id),
    gallery_image_id INTEGER REFERENCES gallery_images(id),
    is_correct BOOLEAN NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Gallery management: Track user's uploaded gallery sets
CREATE TABLE IF NOT EXISTS user_gallery_sets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    species_id INTEGER REFERENCES classes(id),
    set_name VARCHAR(255), -- User-defined name for their gallery set
    upload_session_id VARCHAR(255) REFERENCES reid_sessions(id),
    total_images INTEGER DEFAULT 0,
    total_animals INTEGER DEFAULT 0,
    is_global BOOLEAN DEFAULT false, -- Whether contributed to global gallery
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, species_id, set_name)
);

CREATE INDEX IF NOT EXISTS ix_reid_sessions_user_id ON reid_sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_reid_sessions_user_species ON reid_sessions(user_id, species_id);
CREATE INDEX IF NOT EXISTS ix_uploaded_images_session_type ON uploaded_images(session_id, image_type);
CREATE INDEX IF NOT EXISTS ix_animal_crops_uploaded_image ON animal_crops(uploaded_image_id);
CREATE INDEX IF NOT EXISTS ix_gallery_images_species_global ON gallery_images(species_id, is_global);
CREATE INDEX IF NOT EXISTS ix_gallery_images_user_species ON gallery_images(user_id, species_id);
CREATE INDEX IF NOT EXISTS ix_gallery_images_model ON gallery_images(model_used);
CREATE INDEX IF NOT EXISTS ix_query_images_session ON query_images(session_id);
CREATE INDEX IF NOT EXISTS ix_query_images_model ON query_images(model_used);
CREATE INDEX IF NOT EXISTS ix_matches_session_query ON matches(session_id, query_image_id);
CREATE INDEX IF NOT EXISTS ix_matches_rank ON matches(rank);
CREATE INDEX IF NOT EXISTS ix_user_feedback_session ON user_feedback(session_id);
CREATE INDEX IF NOT EXISTS ix_user_gallery_sets_user_species ON user_gallery_sets(user_id, species_id);

CREATE TABLE IF NOT EXISTS image_embeddings (
    image_id INTEGER PRIMARY KEY
        REFERENCES images(id) ON DELETE CASCADE,
    embedding vector(512)
);

CREATE TABLE IF NOT EXISTS active_learning_birdcount (
    id SERIAL PRIMARY KEY,
    image_id INTEGER REFERENCES images(id),
    user_ids INTEGER[] DEFAULT '{}',
    boxes JSONB NOT NULL,
    dots JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW()
);