select * from image_data;

select * from document_infos order by id desc;
select * from document_approval_steps order by id desc;
select * from document_approval_steps where status = 'pending';
select * from document_versions;
select * from documents;

UPDATE document_infos
SET stored_path = 'D:/eink_docs/njsk2002/approval_process/74',
    target_dir  = 'in_review',
    status      = 'in_review'
WHERE id = 74;

update document_approval_steps
SET status = 'wait'
WHERE id = 197;

delete from document_infos where id >= 0;

select * from device_jobs;

select * from user;

SELECT DISTINCT user.department
FROM user
WHERE user.department IS NOT NULL;

select * from fileuploads;
DELETE FROM fileuploads WHERE id > 0;

select * from approval_routes;
select * from approval_route_steps;


select * from sign_layouts order by id desc;
select * from sign_slots order by id desc;
DELETE FROM sign_layouts WHERE id < 100;

SELECT * FROM uploads order by id desc;
DELETE FROM uploads WHERE id < 100;


select * from upload_approval_steps order by id desc;
select * from sign_slots;


SHOW COLUMNS FROM uploads LIKE 'target_dir';



select * from eink_asset order by id desc;

select * from eink_posting order by id desc;

select * from device_access_logs order by id desc;


select * from eink_company;
delete from eink_company where id >0;

select * from eink_device;
select * from eink_building;
select * from eink_board;
select * from eink_board_binding;

update eink_device set company_id = '2' where id between 1 and 6;
update eink_device set user_no =1, user_userid = 'njsk2002' where id = 8;
delete from eink_board_binding where id = 3;



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

ALTER TABLE document_infos
  DROP CHECK ck_docinfo_status;

ALTER TABLE document_infos
  ADD CONSTRAINT ck_docinfo_status
  CHECK (status IN ('draft','in_review','checked','approved','rejected','uploads','bulletin_files'));
  
  SHOW COLUMNS FROM document_approval_steps LIKE 'status';
SELECT status, COUNT(*) FROM document_approval_steps GROUP BY status;


SHOW INDEX FROM eink_board_binding;

ALTER TABLE eink_board_binding DROP INDEX ix_eink_board_binding_board_id;
