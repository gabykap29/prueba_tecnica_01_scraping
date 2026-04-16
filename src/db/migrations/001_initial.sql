-- =============================================================================
-- Database Schema: Rappi Analytics System
-- Version: 1.0.0
-- Description: Initial schema for multi-platform food delivery analytics
-- Target: PostgreSQL 15+ with PostGIS extension
-- =============================================================================

-- Enable PostGIS for geospatial queries
CREATE EXTENSION IF NOT EXISTS postgis;

-- -----------------------------------------------------------------------------
-- Table: platforms
-- Description: Supported food delivery platforms
-- -----------------------------------------------------------------------------
CREATE TABLE platforms (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    base_url VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_platforms_name ON platforms(name);

-- -----------------------------------------------------------------------------
-- Table: zones
-- Description: Geographic zones in Mexico City for delivery analysis
-- -----------------------------------------------------------------------------
CREATE TABLE zones (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    zone_type VARCHAR(20) NOT NULL CHECK (zone_type IN ('high', 'mid', 'periphery')),
    coordinates GEOMETRY(Point, 4326),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_zones_type ON zones(zone_type);

-- -----------------------------------------------------------------------------
-- Table: addresses
-- Description: Delivery addresses associated with zones
-- -----------------------------------------------------------------------------
CREATE TABLE addresses (
    id SERIAL PRIMARY KEY,
    zone_id INTEGER NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    full_address VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_addresses_zone ON addresses(zone_id);

-- -----------------------------------------------------------------------------
-- Table: restaurants
-- Description: Restaurant entities from different platforms
-- -----------------------------------------------------------------------------
CREATE TABLE restaurants (
    id SERIAL PRIMARY KEY,
    platform_id INTEGER NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    external_id VARCHAR(100),
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    rating DECIMAL(2, 1),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(platform_id, external_id)
);

CREATE INDEX idx_restaurants_platform ON restaurants(platform_id);

-- -----------------------------------------------------------------------------
-- Table: products
-- Description: Menu products from restaurants
-- -----------------------------------------------------------------------------
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    platform_id INTEGER NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    external_id VARCHAR(100),
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(platform_id, external_id)
);

CREATE INDEX idx_products_restaurant ON products(restaurant_id);

-- -----------------------------------------------------------------------------
-- Table: raw_scrape
-- Description: Raw scraped data from web scraping operations
-- -----------------------------------------------------------------------------
CREATE TABLE raw_scrape (
    id SERIAL PRIMARY KEY,
    platform_id INTEGER NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    address_id INTEGER NOT NULL REFERENCES addresses(id) ON DELETE CASCADE,
    restaurant_id INTEGER REFERENCES restaurants(id) ON DELETE SET NULL,
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    product_price DECIMAL(10, 2),
    delivery_fee DECIMAL(10, 2),
    service_fee DECIMAL(10, 2),
    estimated_time_min INTEGER,
    active_promo TEXT,
    scraped_at TIMESTAMP NOT NULL DEFAULT NOW(),
    raw_json JSONB,
    error TEXT
);

CREATE INDEX idx_raw_scrape_platform_address ON raw_scrape(platform_id, address_id, scraped_at);
CREATE INDEX idx_raw_scrape_product ON raw_scrape(product_id, scraped_at);

-- -----------------------------------------------------------------------------
-- Table: price_analytics
-- Description: Processed data for analytics and reporting
-- -----------------------------------------------------------------------------
CREATE TABLE price_analytics (
    id SERIAL PRIMARY KEY,
    platform_id INTEGER NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    address_id INTEGER NOT NULL REFERENCES addresses(id) ON DELETE CASCADE,
    restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    product_price DECIMAL(10, 2),
    delivery_fee DECIMAL(10, 2),
    total_cost DECIMAL(10, 2),
    estimated_time_min INTEGER,
    promo_applied VARCHAR(100),
    scraped_at DATE NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(platform_id, address_id, product_id, scraped_at)
);

CREATE INDEX idx_price_analytics_date ON price_analytics(scraped_at);
CREATE INDEX idx_price_analytics_zone ON price_analytics(address_id, scraped_at);

-- -----------------------------------------------------------------------------
-- Table: promotions
-- Description: Active promotional campaigns
-- -----------------------------------------------------------------------------
CREATE TABLE promotions (
    id SERIAL PRIMARY KEY,
    platform_id INTEGER NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    restaurant_id INTEGER REFERENCES restaurants(id) ON DELETE CASCADE,
    promo_code VARCHAR(50),
    description TEXT,
    discount_percent DECIMAL(5, 2),
    min_order_amount DECIMAL(10, 2),
    valid_from DATE,
    valid_until DATE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- Initial Data: Platforms
-- -----------------------------------------------------------------------------
INSERT INTO platforms (name, base_url) VALUES
    ('ubereats', 'https://www.ubereats.com/mx'),
    ('rappi', 'https://www.rappi.com.mx'),
    ('didi', 'https://www.didifood.com/mx');

-- -----------------------------------------------------------------------------
-- Initial Data: Zones
-- -----------------------------------------------------------------------------
INSERT INTO zones (name, zone_type) VALUES
    ('Polanco', 'high'),
    ('Santa Fe', 'high'),
    ('Condesa', 'mid'),
    ('Roma Norte', 'mid'),
    ('Del Valle', 'mid'),
    ('Centro Historico', 'mid'),
    ('Iztapalapa', 'periphery'),
    ('Xochimilco', 'periphery'),
    ('Gustavo A. Madero', 'periphery');