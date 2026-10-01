<?php
/** Central WordPress MU-plugin syntax and standalone contract test runner. */

function run_command(array $command, string $label): void {
    $escaped = array_map('escapeshellarg', $command);
    passthru(implode(' ', $escaped), $code);
    if ($code !== 0) {
        fwrite(STDERR, "FAIL: {$label}\n");
        exit($code ?: 1);
    }
}

$root = dirname(__DIR__);
$php = PHP_BINARY;
$pluginFiles = glob($root . '/mu-plugins/*.php') ?: [];
$testFiles = glob(__DIR__ . '/*.php') ?: [];
sort($pluginFiles);
sort($testFiles);

foreach (array_merge($pluginFiles, $testFiles) as $file) {
    if (realpath($file) === __FILE__) {
        continue;
    }
    run_command([$php, '-l', $file], 'syntax ' . basename($file));
}

$syntaxOnly = [
    'wp-post-id-column-smoke.php',
];

foreach ($testFiles as $file) {
    $name = basename($file);
    if (realpath($file) === __FILE__ || in_array($name, $syntaxOnly, true)) {
        continue;
    }
    if (!str_ends_with($name, '-test.php')) {
        continue;
    }
    run_command([$php, $file], 'contract ' . $name);
}

echo "PASS wordpress test runner\n";
