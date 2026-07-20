<?php
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, no-cache, must-revalidate');
header('X-Content-Type-Options: nosniff');

const MAX_COMMENTS = 1000;
const MAX_LIKES_PER_COMMENT = 20000;
const POST_INTERVAL_SECONDS = 20;
const ADMIN_TOKEN_HASH = 'c1290a444bf0dfecb3f7e129da9618c0cf9883ebfcc916110d31dc879151cfb9';

function respond(int $status, array $body): void
{
    http_response_code($status);
    echo json_encode($body, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function load_round_config(): array
{
    $path = dirname(__DIR__) . '/predictions/round.json';
    $json = @file_get_contents($path);
    $config = $json === false ? null : json_decode($json, true);
    if (!is_array($config) || !isset($config['round_id'])) {
        respond(503, ['error' => '予想データを読み込めません']);
    }
    return $config;
}

function data_path(string $roundId): string
{
    $documentRoot = realpath((string) ($_SERVER['DOCUMENT_ROOT'] ?? ''));
    $base = $documentRoot ? dirname($documentRoot) : dirname(__DIR__, 2);
    $directory = $base . '/hok_vote_data';
    if (!is_dir($directory) && !@mkdir($directory, 0700, true) && !is_dir($directory)) {
        respond(503, ['error' => 'コメントデータの保存先を準備できません']);
    }
    return $directory . '/prediction_comments_' . preg_replace('/[^a-zA-Z0-9_-]/', '_', $roundId) . '.json';
}

function valid_voter_token($token): ?string
{
    if (!is_string($token) || !preg_match('/^[A-Za-z0-9_-]{16,128}$/', $token)) {
        return null;
    }
    return hash('sha256', $token);
}

function text_length(string $value): int
{
    return preg_match_all('/./us', $value, $matches) ?: 0;
}

function clean_nickname($value): ?string
{
    if (!is_string($value)) {
        return null;
    }
    $value = preg_replace('/[\x00-\x1F\x7F]/u', '', $value);
    $value = is_string($value) ? trim(preg_replace('/\s+/u', ' ', $value) ?? '') : '';
    $length = text_length($value);
    return $length >= 1 && $length <= 24 ? $value : null;
}

function clean_body($value): ?string
{
    if (!is_string($value)) {
        return null;
    }
    $value = str_replace(["\r\n", "\r"], "\n", $value);
    $value = preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/u', '', $value);
    $value = is_string($value) ? trim($value) : '';
    $length = text_length($value);
    if ($length < 1 || $length > 500) {
        return null;
    }
    if (preg_match_all('#https?://#iu', $value, $matches) > 2) {
        return null;
    }
    return $value;
}

function initial_state(string $roundId): array
{
    return [
        'round_id' => $roundId,
        'next_id' => 1,
        'updated_at' => null,
        'posters' => [],
        'comments' => [],
    ];
}

function read_or_initialize_state($handle, string $roundId): array
{
    rewind($handle);
    $json = stream_get_contents($handle);
    $state = $json ? json_decode($json, true) : null;
    if (!is_array($state) || ($state['round_id'] ?? null) !== $roundId) {
        return initial_state($roundId);
    }
    $state['next_id'] = max(1, (int) ($state['next_id'] ?? 1));
    $state['posters'] = is_array($state['posters'] ?? null) ? $state['posters'] : [];
    $state['comments'] = is_array($state['comments'] ?? null) ? $state['comments'] : [];
    return $state;
}

function find_comment_index(array $comments, int $commentId): ?int
{
    foreach ($comments as $index => $comment) {
        if ((int) ($comment['id'] ?? 0) === $commentId) {
            return $index;
        }
    }
    return null;
}

function comment_depth(array $comments, int $commentId): int
{
    $depth = 0;
    $seen = [];
    while ($commentId > 0 && $depth <= 3) {
        if (isset($seen[$commentId])) {
            return 99;
        }
        $seen[$commentId] = true;
        $index = find_comment_index($comments, $commentId);
        if ($index === null) {
            return 99;
        }
        $commentId = (int) ($comments[$index]['parent_id'] ?? 0);
        if ($commentId > 0) {
            $depth++;
        }
    }
    return $depth;
}

function public_state(array $state, ?string $voterHash): array
{
    $comments = [];
    foreach ($state['comments'] as $comment) {
        $deleted = !empty($comment['deleted']);
        $likes = is_array($comment['likes'] ?? null) ? $comment['likes'] : [];
        $comments[] = [
            'id' => (int) $comment['id'],
            'parent_id' => isset($comment['parent_id']) ? (int) $comment['parent_id'] : null,
            'nickname' => $deleted ? '削除済み' : (string) ($comment['nickname'] ?? ''),
            'body' => $deleted ? '管理者により削除されました' : (string) ($comment['body'] ?? ''),
            'created_at' => (string) ($comment['created_at'] ?? ''),
            'updated_at' => $comment['updated_at'] ?? null,
            'deleted' => $deleted,
            'like_count' => $deleted ? 0 : count($likes),
            'liked_by_me' => !$deleted && $voterHash !== null && isset($likes[$voterHash]),
        ];
    }
    return [
        'round_id' => $state['round_id'],
        'updated_at' => $state['updated_at'] ?? null,
        'comment_count' => count(array_filter($comments, static fn(array $comment): bool => !$comment['deleted'])),
        'comments' => $comments,
    ];
}

function save_state($handle, array $state): void
{
    rewind($handle);
    ftruncate($handle, 0);
    fwrite($handle, json_encode($state, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
    fflush($handle);
}

function is_admin_request(): bool
{
    $token = (string) ($_SERVER['HTTP_X_ADMIN_TOKEN'] ?? '');
    $expected = getenv('HOK_COMMENT_ADMIN_HASH');
    $expected = is_string($expected) && preg_match('/^[a-f0-9]{64}$/', $expected) ? $expected : ADMIN_TOKEN_HASH;
    return $token !== '' && hash_equals($expected, hash('sha256', $token));
}

$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
if (!in_array($method, ['GET', 'POST'], true)) {
    header('Allow: GET, POST');
    respond(405, ['error' => '許可されていない操作です']);
}

$config = load_round_config();
$payload = [];
if ($method === 'POST') {
    if ((int) ($_SERVER['CONTENT_LENGTH'] ?? 0) > 8192) {
        respond(413, ['error' => 'リクエストが大きすぎます']);
    }
    $payload = json_decode((string) file_get_contents('php://input'), true);
    if (!is_array($payload)) {
        respond(400, ['error' => '送信データが不正です']);
    }
}

$requestedRound = (string) ($method === 'GET' ? ($_GET['round_id'] ?? '') : ($payload['round_id'] ?? ''));
if (!hash_equals((string) $config['round_id'], $requestedRound)) {
    respond(409, ['error' => 'この予想ラウンドは終了しました']);
}

$rawVoterToken = $method === 'GET' ? ($_GET['voter_token'] ?? null) : ($payload['voter_token'] ?? null);
$voterHash = valid_voter_token($rawVoterToken);
$path = data_path($requestedRound);
$handle = @fopen($path, 'c+');
if ($handle === false || !flock($handle, LOCK_EX)) {
    respond(503, ['error' => 'コメントデータを開けません']);
}
$state = read_or_initialize_state($handle, $requestedRound);

if ($method === 'POST') {
    $action = (string) ($payload['action'] ?? '');
    $now = time();

    if ($action === 'admin_delete') {
        if (!is_admin_request()) {
            flock($handle, LOCK_UN);
            fclose($handle);
            respond(403, ['error' => '管理者認証に失敗しました']);
        }
        $commentId = (int) ($payload['comment_id'] ?? 0);
        $index = find_comment_index($state['comments'], $commentId);
        if ($index === null) {
            flock($handle, LOCK_UN);
            fclose($handle);
            respond(404, ['error' => 'コメントが見つかりません']);
        }
        $state['comments'][$index]['deleted'] = true;
        $state['comments'][$index]['nickname'] = '';
        $state['comments'][$index]['body'] = '';
        $state['comments'][$index]['likes'] = [];
        $state['comments'][$index]['updated_at'] = gmdate('c');
    } elseif ($action === 'create') {
        if ($voterHash === null) {
            respond(400, ['error' => '投稿者IDが不正です']);
        }
        if (count($state['comments']) >= MAX_COMMENTS) {
            respond(503, ['error' => 'この掲示板は上限に達しました']);
        }
        $lastPostedAt = (int) ($state['posters'][$voterHash] ?? 0);
        if ($lastPostedAt > 0 && $now - $lastPostedAt < POST_INTERVAL_SECONDS) {
            respond(429, ['error' => '連続投稿はできません。少し待ってから投稿してください']);
        }
        $nickname = clean_nickname($payload['nickname'] ?? null);
        $body = clean_body($payload['body'] ?? null);
        if ($nickname === null) {
            respond(400, ['error' => 'ニックネームは1〜24文字で入力してください']);
        }
        if ($body === null) {
            respond(400, ['error' => 'コメントは1〜500文字、URLは2件以内で入力してください']);
        }
        $parentId = isset($payload['parent_id']) && $payload['parent_id'] !== null
            ? (int) $payload['parent_id']
            : null;
        if ($parentId !== null) {
            $parentIndex = find_comment_index($state['comments'], $parentId);
            if ($parentIndex === null || !empty($state['comments'][$parentIndex]['deleted'])) {
                respond(400, ['error' => '返信先のコメントが見つかりません']);
            }
            if (comment_depth($state['comments'], $parentId) >= 2) {
                respond(400, ['error' => '返信は2階層までです']);
            }
        }
        $commentId = (int) $state['next_id'];
        $state['next_id'] = $commentId + 1;
        $state['comments'][] = [
            'id' => $commentId,
            'parent_id' => $parentId,
            'nickname' => $nickname,
            'body' => $body,
            'created_at' => gmdate('c'),
            'updated_at' => null,
            'deleted' => false,
            'likes' => [],
        ];
        $state['posters'][$voterHash] = $now;
        if (count($state['posters']) > 20000) {
            $state['posters'] = array_filter(
                $state['posters'],
                static fn($timestamp): bool => (int) $timestamp >= $now - 604800
            );
        }
    } elseif ($action === 'like') {
        if ($voterHash === null) {
            respond(400, ['error' => '投稿者IDが不正です']);
        }
        $commentId = (int) ($payload['comment_id'] ?? 0);
        $index = find_comment_index($state['comments'], $commentId);
        if ($index === null || !empty($state['comments'][$index]['deleted'])) {
            respond(404, ['error' => 'コメントが見つかりません']);
        }
        $likes = &$state['comments'][$index]['likes'];
        if (!is_array($likes)) {
            $likes = [];
        }
        if (isset($likes[$voterHash])) {
            unset($likes[$voterHash]);
        } elseif (count($likes) >= MAX_LIKES_PER_COMMENT) {
            respond(503, ['error' => '賛成数が上限に達しました']);
        } else {
            $likes[$voterHash] = true;
        }
    } else {
        respond(400, ['error' => '操作が不正です']);
    }

    $state['updated_at'] = gmdate('c');
    save_state($handle, $state);
}

$response = public_state($state, $voterHash);
flock($handle, LOCK_UN);
fclose($handle);
respond(200, $response);

