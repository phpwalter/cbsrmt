<html>
<head><title>Test Page of new Virtual Domain</title></head>
<body>

<?php


// var_dump(opcache_get_configuration());

echo '<h2 align="center">http://' . $_SERVER['SERVER_NAME'] . '</h2>';

echo '<h2 align="center">' . __FILE__ . '</h2>';

phpinfo();

?>

</body>
</html>
