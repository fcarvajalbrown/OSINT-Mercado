<?php
// gh_config.sample.php — template for refresh.php configuration.
//
// On the Hostinger server, copy this to gh_config.php (same directory) and fill in
// a real, READ-ONLY GitHub token. gh_config.php holds the secret: never commit it,
// and it must live where PHP executes it (so the token is never served as text).
//
//   cp gh_config.sample.php gh_config.php
//   # then edit gh_config.php and set GH_TOKEN (and optionally REFRESH_KEY)
//
// Token: create a fine-grained Personal Access Token scoped to ONLY this repository
// with "Contents: Read-only". Nothing else.

declare(strict_types=1);

define('GH_TOKEN', 'REPLACE_WITH_READ_ONLY_TOKEN');
define('GH_OWNER', 'fcarvajalbrown');
define('GH_REPO', 'OSINT-Mercado');
define('GH_BRANCH', 'master');
define('GH_PATH', 'published/flags.json');

// Optional: a shared secret the cron URL must include (?key=...) so the puller
// cannot be triggered by random visitors. Leave '' to disable the check.
define('REFRESH_KEY', '');
