<?php
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, no-cache, must-revalidate');
header('X-Content-Type-Options: nosniff');

const MAX_VOTERS_PER_MARKET = 20000;

function respond(int $status, array $body): void
{
    http_response_code($status);
    echo json_encode($body, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function read_round_config(string $path): ?array
{
    $json = @file_get_contents($path);
    $config = $json === false ? null : json_decode($json, true);
    return is_array($config) && isset($config['round_id'], $config['predictions'], $config['closes_at'])
        ? $config
        : null;
}

function load_round_config(string $roundId): array
{
    $current = read_round_config(dirname(__DIR__) . '/predictions/round.json');
    if ($current === null) {
        respond(503, ['error' => '予想データを読み込めません']);
    }
    if (hash_equals((string) $current['round_id'], $roundId)) {
        return ['config' => $current, 'current' => true];
    }
    if (!preg_match('/^[a-zA-Z0-9_-]{1,80}$/', $roundId)) {
        respond(409, ['error' => 'この投票ラウンドは終了しました']);
    }
    $archived = read_round_config(dirname(__DIR__) . '/predictions/rounds/' . $roundId . '.json');
    if ($archived === null || !hash_equals((string) $archived['round_id'], $roundId)) {
        respond(409, ['error' => 'この投票ラウンドは終了しました']);
    }
    return ['config' => $archived, 'current' => false];
}

function data_path(string $roundId): string
{
    $documentRoot = realpath((string) ($_SERVER['DOCUMENT_ROOT'] ?? ''));
    $base = $documentRoot ? dirname($documentRoot) : dirname(__DIR__, 2);
    $directory = $base . '/hok_vote_data';
    if (!is_dir($directory) && !@mkdir($directory, 0700, true) && !is_dir($directory)) {
        respond(503, ['error' => '投票データの保存先を準備できません']);
    }
    return $directory . '/prediction_' . preg_replace('/[^a-zA-Z0-9_-]/', '_', $roundId) . '.json';
}

function initial_state(array $config): array
{
    $markets = [];
    foreach ($config['predictions'] as $prediction) {
        $markets[$prediction['id']] = ['do' => 0, 'not' => 0, 'voters' => []];
    }
    return [
        'round_id' => $config['round_id'],
        'updated_at' => null,
        'markets' => $markets,
    ];
}

function read_or_initialize_state($handle, array $config): array
{
    rewind($handle);
    $json = stream_get_contents($handle);
    $state = $json ? json_decode($json, true) : null;
    if (!is_array($state) || ($state['round_id'] ?? null) !== $config['round_id']) {
        return initial_state($config);
    }

    foreach ($config['predictions'] as $prediction) {
        $id = $prediction['id'];
        if (!isset($state['markets'][$id]) || !is_array($state['markets'][$id])) {
            $state['markets'][$id] = ['do' => 0, 'not' => 0, 'voters' => []];
        }
    }
    return $state;
}

function public_state(array $state, array $config, ?string $voterHash): array
{
    $markets = [];
    $ownVotes = [];
    foreach ($config['predictions'] as $prediction) {
        $id = $prediction['id'];
        $market = $state['markets'][$id];
        $markets[$id] = [
            'do' => max(0, (int) ($market['do'] ?? 0)),
            'not' => max(0, (int) ($market['not'] ?? 0)),
        ];
        if ($voterHash && isset($market['voters'][$voterHash])) {
            $ownVotes[$id] = $market['voters'][$voterHash];
        }
    }

    return [
        'round_id' => $config['round_id'],
        'updated_at' => $state['updated_at'] ?? null,
        'closed' => time() > strtotime($config['closes_at']),
        'markets' => $markets,
        'own_votes' => $ownVotes,
    ];
}

function valid_voter_token($token): ?string
{
    if (!is_string($token) || !preg_match('/^[A-Za-z0-9_-]{16,128}$/', $token)) {
        return null;
    }
    return hash('sha256', $token);
}

$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
if (!in_array($method, ['GET', 'POST'], true)) {
    header('Allow: GET, POST');
    respond(405, ['error' => '許可されていない操作です']);
}

$requestedRound = $method === 'GET' ? ($_GET['round_id'] ?? '') : null;
$voterHash = $method === 'GET' ? valid_voter_token($_GET['voter_token'] ?? null) : null;

if ($method === 'POST') {
    if ((int) ($_SERVER['CONTENT_LENGTH'] ?? 0) > 4096) {
        respond(413, ['error' => 'リクエストが大きすぎます']);
    }
    $payload = json_decode((string) file_get_contents('php://input'), true);
    if (!is_array($payload)) {
        respond(400, ['error' => '投票データが不正です']);
    }
    $requestedRound = $payload['round_id'] ?? '';
    $voterHash = valid_voter_token($payload['voter_token'] ?? null);
    if (!$voterHash) {
        respond(400, ['error' => '投票者IDが不正です']);
    }
}

$loadedRound = load_round_config((string) $requestedRound);
$config = $loadedRound['config'];
if ($method === 'POST' && !$loadedRound['current']) {
    respond(409, ['error' => 'この投票ラウンドは終了しました']);
}

$path = data_path($config['round_id']);
$handle = @fopen($path, 'c+');
if ($handle === false || !flock($handle, LOCK_EX)) {
    respond(503, ['error' => '投票データを開けません']);
}

$state = read_or_initialize_state($handle, $config);

if ($method === 'POST') {
    if (time() > strtotime($config['closes_at'])) {
        flock($handle, LOCK_UN);
        fclose($handle);
        respond(403, ['error' => '投票受付は終了しました']);
    }

    $predictionId = $payload['prediction_id'] ?? '';
    $choice = $payload['choice'] ?? '';
    if (!isset($state['markets'][$predictionId]) || !in_array($choice, ['do', 'not'], true)) {
        flock($handle, LOCK_UN);
        fclose($handle);
        respond(400, ['error' => '投票先が不正です']);
    }

    $market = &$state['markets'][$predictionId];
    $previousChoice = $market['voters'][$voterHash] ?? null;
    if ($previousChoice !== $choice) {
        if ($previousChoice === 'do' || $previousChoice === 'not') {
            $market[$previousChoice] = max(0, (int) $market[$previousChoice] - 1);
        } elseif (count($market['voters']) >= MAX_VOTERS_PER_MARKET) {
            flock($handle, LOCK_UN);
            fclose($handle);
            respond(503, ['error' => 'この投票は定員に達しました']);
        }
        $market[$choice] = (int) $market[$choice] + 1;
        $market['voters'][$voterHash] = $choice;
        $state['updated_at'] = gmdate('c');
    }

    rewind($handle);
    ftruncate($handle, 0);
    fwrite($handle, json_encode($state, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
    fflush($handle);
}

$response = public_state($state, $config, $voterHash);
flock($handle, LOCK_UN);
fclose($handle);
respond(200, $response);
