-- Create properties table
CREATE TABLE properties (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    property_name TEXT NOT NULL,
    address TEXT,
    floor_suite TEXT,
    space_available TEXT,
    price TEXT,
    listing_url TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create property_changes table to track modifications
CREATE TABLE property_changes (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    property_id UUID REFERENCES properties(id),
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    source TEXT NOT NULL,
    modified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create scrape_logs table
CREATE TABLE scrape_logs (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    properties_count INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_properties_source ON properties(source);
CREATE INDEX idx_properties_created_at ON properties(created_at);
CREATE INDEX idx_property_changes_modified_at ON property_changes(modified_at);
CREATE INDEX idx_scrape_logs_source_created ON scrape_logs(source, created_at);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_properties_updated_at
    BEFORE UPDATE ON properties
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
