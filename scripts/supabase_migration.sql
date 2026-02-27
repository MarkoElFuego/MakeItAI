-- ============================================================================
-- RAG Pipeline Migration: match_documents_filtered
--
-- Run this in Supabase SQL Editor (Dashboard > SQL Editor > New Query)
-- This adds a new RPC function that supports metadata filtering.
-- The existing match_documents function is NOT modified.
-- ============================================================================

-- New function: match_documents_filtered
-- Supports optional jsonb metadata filter using the @> containment operator.
-- When filter is empty '{}', it behaves identically to match_documents.
CREATE OR REPLACE FUNCTION match_documents_filtered(
    query_embedding vector(768),
    match_threshold float,
    match_count int,
    filter jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE (
    id bigint,
    content text,
    metadata jsonb,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        documents.id,
        documents.content,
        documents.metadata,
        1 - (documents.embedding <=> query_embedding) AS similarity
    FROM documents
    WHERE
        1 - (documents.embedding <=> query_embedding) > match_threshold
        AND (filter = '{}'::jsonb OR documents.metadata @> filter)
    ORDER BY documents.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Optional: Create a GIN index on metadata for faster @> queries
-- (only run if you don't already have one)
CREATE INDEX IF NOT EXISTS idx_documents_metadata_gin
    ON documents USING gin (metadata);
