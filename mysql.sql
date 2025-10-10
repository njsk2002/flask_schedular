select * from image_data;

select * from user;

select * from fileuploads;
DELETE FROM fileuploads WHERE id > 0;

select * from approval_routes;
select * from approval_route_steps;


select * from sign_layouts;
DELETE FROM sign_layouts WHERE id < 28;

select * from uploads;
DELETE FROM uploads WHERE id < 50;


SHOW COLUMNS FROM uploads LIKE 'target_dir';