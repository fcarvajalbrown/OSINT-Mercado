<?php
// refresh.php — pull the latest published flags into the live dashboard.
//
// Intended to be called by a Hostinger cron job. It fetches published/flags.json
// from the (private) GitHub repo and writes it to ./data/flags.json next to this
// file. Only human-confirmed flags ever reach published/flags.json (built in CI),
// so this never publishes unreviewed data.
//
// Setup: copy gh_config.sample.php to gh_config.php and fill in a read-only token.
// gh_config.php holds the secret and must never be committed or world-served.

declare(strict_types=1);

$configFile = __DIR__ . '/gh_config.php';
if (!is_file($configFile)) {
    http_response_code(500);
    exit("gh_config.php missing (copy gh_config.sample.php and add a token)\n");
}
require $configFile;

// Optional shared-secret guard so a random visitor can't spam the puller.
if (defined('REFRESH_KEY') && REFRESH_KEY !== '') {
    $provided = $_GET['key'] ?? '';
    if (!hash_equals(REFRESH_KEY, (string) $provided)) {
        http_response_code(403);
        exit("forbidden\n");
    }
}

$url = sprintf(
    'https://api.github.com/repos/%s/%s/contents/%s?ref=%s',
    rawurlencode(GH_OWNER),
    rawurlencode(GH_REPO),
    GH_PATH,                       // path segments kept literal (e.g. published/flags.json)
    rawurlencode(GH_BRANCH)
);

$ch = curl_init($url);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT => 30,
    CURLOPT_HTTPHEADER => [
        'Authorization: Bearer ' . GH_TOKEN,
        'Accept: application/vnd.github.raw',   // return the file body directly
        'User-Agent: osint-mercado-refresh',
        'X-GitHub-Api-Version: 2022-11-28',
    ],
]);
$body = curl_exec($ch);
$code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$err = curl_error($ch);
curl_close($ch);

if ($body === false || $code !== 200) {
    http_response_code(502);
    exit("fetch failed (HTTP $code) $err\n");
}

// Never write anything that is not valid JSON.
json_decode($body);
if (json_last_error() !== JSON_ERROR_NONE) {
    http_response_code(502);
    exit("source was not valid JSON\n");
}

$dataDir = __DIR__ . '/data';
if (!is_dir($dataDir)) {
    @mkdir($dataDir, 0755, true);
}

// Write atomically: temp file then rename, so readers never see a half file.
$tmp = $dataDir . '/flags.json.tmp';
if (file_put_contents($tmp, $body) === false || !rename($tmp, $dataDir . '/flags.json')) {
    http_response_code(500);
    exit("write failed\n");
}

echo 'ok: ' . strlen($body) . ' bytes @ ' . date('c') . "\n";
