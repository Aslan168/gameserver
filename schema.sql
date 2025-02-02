DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL,
  `leader_card_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);


DROP TABLE IF EXISTS `room`;
CREATE TABLE `room` (
  `room_id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` int DEFAULT NULL,
  `joined_user_count` int DEFAULT 1,
  `max_user_count` int DEFAULT 4,
  `room_status` int DEFAULT 1,
  PRIMARY KEY (`room_id`)
);

DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `user_id` bigint NOT NULL,
  `room_id` bigint NOT NULL,
  `name` varchar(255) DEFAULT NULL,
  `leader_card_id` int DEFAULT NULL,
  `select_difficulty` int DEFAULT 1,
  `is_me` boolean DEFAULT NULL,
  `is_host` boolean DEFAULT NULL,
  `score` int DEFAULT NULL,
  `score_perfect` int DEFAULT NULL,
  `score_great` int DEFAULT NULL,
  `score_good` int DEFAULT NULL,
  `score_bad` int DEFAULT NULL,
  `score_miss` int DEFAULT NULL,
  PRIMARY KEY (`room_id`, `user_id`)
);