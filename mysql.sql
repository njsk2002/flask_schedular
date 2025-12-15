select * from image_data;

select * from document_infos order by id desc;

select * from document_approval_steps;
select * from document_versions;
select * from documents;

select * from user;

SELECT DISTINCT user.department
FROM user
WHERE user.department IS NOT NULL;

select * from fileuploads;
DELETE FROM fileuploads WHERE id > 0;

select * from approval_routes;
select * from approval_route_steps;


select * from sign_layouts;
select * from sign_slots;
DELETE FROM sign_layouts WHERE id < 100;

SELECT * FROM uploads order by id desc;
DELETE FROM uploads WHERE id < 100;


select * from upload_approval_steps order by id desc;
select * from sign_slots;


SHOW COLUMNS FROM uploads LIKE 'target_dir';

select * from eink_device;

select * from eink_asset;


-- user.no = 1 인 경우 직접 지정
INSERT INTO eink_device (
    user_no,
    user_userid,
    device_id,
    device_name,
    panel_res,
    bpp,
    cap,
    supports_partial,
    supports_rle,
    supports_zlib,
    current_ver,
    last_seen,
    created_at,
    updated_at
)
SELECT
    1          AS user_no,         -- 여기만 해당 사용자의 no로 교체
    'njsk2002'     AS user_userid,
    d.device_id,
    d.device_name,
    d.panel_res,
    d.bpp,
    d.cap,
    1, 1, 1,
    0,
    NULL,
    NOW(),
    NOW()
FROM (
    SELECT 'E01' AS device_id, 'E01' AS device_name, '1200x1600' AS panel_res, 4 AS bpp, 'BWR' AS cap
    UNION ALL SELECT 'E02','E02','1200x1600',4,'BWR'
    UNION ALL SELECT 'E03','E03','1200x1600',4,'BWR'
    UNION ALL SELECT 'E04','E04','1200x1600',4,'BWR'
    UNION ALL SELECT 'E05','E05','1200x1600',4,'BWR'
    UNION ALL SELECT 'E06','E06','1200x1600',4,'BWR'
) AS d
ON DUPLICATE KEY UPDATE
    device_name   = VALUES(device_name),
    panel_res     = VALUES(panel_res),
    bpp           = VALUES(bpp),
    cap           = VALUES(cap),
    supports_partial = VALUES(supports_partial),
    supports_rle     = VALUES(supports_rle),
    supports_zlib    = VALUES(supports_zlib),
    user_userid      = VALUES(user_userid),
    updated_at    = VALUES(updated_at);
    
    

DROP TABLE documents;

SELECT * FROM alembic_version;
