-- Seed: 5 MVP pro players with serve + forehand reference data
-- Thumbnails use placeholder paths — replace with real S3 URLs before launch.

insert into pro_players (name, gender, thumbnail_url, shot_types, is_active) values
    ('Carlos Alcaraz',   'atp', 'https://your-s3-bucket.s3.amazonaws.com/pros/alcaraz.jpg',   array['serve','forehand'], true),
    ('Jannik Sinner',    'atp', 'https://your-s3-bucket.s3.amazonaws.com/pros/sinner.jpg',    array['serve','forehand'], true),
    ('Novak Djokovic',   'atp', 'https://your-s3-bucket.s3.amazonaws.com/pros/djokovic.jpg',  array['serve','forehand'], true),
    ('Aryna Sabalenka',  'wta', 'https://your-s3-bucket.s3.amazonaws.com/pros/sabalenka.jpg', array['serve','forehand'], true),
    ('Iga Swiatek',      'wta', 'https://your-s3-bucket.s3.amazonaws.com/pros/swiatek.jpg',   array['serve','forehand'], true);
