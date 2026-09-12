#!/bin/bash
set -e
cd /var/www/html
wp option update timezone_string "Asia/Seoul" --allow-root
wp option update date_format "Y년 n월 jIl" --allow-root
wp option update time_format "A g:i" --allow-root
wp rewrite structure "/%postname%/" --hard --allow-root
wp post delete 1 --force --allow-root || true
wp post delete 2 --force --allow-root || true
wp comment delete 1 --force --allow-root || true
wp theme install generatepress --activate --allow-root
wp plugin install seo-by-rank-math wp-super-cache --activate --allow-root
a2enmod rewrite
chown -R www-data:www-data /var/www/html
echo "WORDPRESS_SETUP_COMPLETED"
