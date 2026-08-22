// Receives a Boxing Day submission from submit.html and commits it to
// data/submissions.csv in the GitHub repo, so the repo stays the single
// source of truth (no separate database). Validates the payload's shape
// and re-validates the squad server-side against the real eligible-players
// list pulled from GitHub - never trusts the client's own validation.

const SQUAD_SIZE = 11;
const SQUAD_RULES = { GKP: [1, 1], DEF: [3, 5], MID: [3, 5], FWD: [1, 3] };
const MAX_PER_CLUB = 3;

export default {
  async fetch(request, env) {
    const cors = {
      "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    if (request.method === "OPTIONS") return new Response(null, { headers: cors });
    if (request.method !== "POST") return json({ error: "Method not allowed" }, 405, cors);

    let payload;
    try {
      payload = await request.json();
    } catch {
      return json({ error: "Invalid JSON body" }, 400, cors);
    }

    const shapeError = validateShape(payload);
    if (shapeError) return json({ error: shapeError }, 400, cors);

    const repo = env.GITHUB_REPO;
    const branch = env.GITHUB_BRANCH || "main";

    let matches, players, categories;
    try {
      [matches, players, categories] = await Promise.all([
        rawCSV(repo, branch, "data/matches.csv"),
        rawCSV(repo, branch, "data/eligible-players.csv"),
        rawCSV(repo, branch, "data/categories.csv"),
      ]);
    } catch (err) {
      return json({ error: `Couldn't load reference data: ${err.message}` }, 502, cors);
    }

    const matchIds = new Set(matches.map((m) => String(m.match_id)));
    for (const s of payload.scores) {
      if (!matchIds.has(String(s.match_id))) return json({ error: `Unknown match_id ${s.match_id}` }, 400, cors);
    }

    const categoryIds = new Set(categories.map((c) => c.id).filter((id) => id !== "kamper" && id !== "fpl_score"));
    for (const a of payload.answers) {
      if (!categoryIds.has(a.category_id)) return json({ error: `Unknown category ${a.category_id}` }, 400, cors);
    }

    const squadError = validateSquad(payload.squad, players);
    if (squadError) return json({ error: squadError }, 400, cors);

    const now = new Date().toISOString();
    const newRows = [];
    for (const s of payload.scores) {
      newRows.push([payload.season, payload.player_name, now, "kamper", s.match_id, `${s.home}-${s.away}`]);
    }
    for (const a of payload.answers) {
      newRows.push([payload.season, payload.player_name, now, a.category_id, "", String(a.answer)]);
    }
    newRows.push([payload.season, payload.player_name, now, "fpl_score", "", payload.squad.join(";")]);

    const token = env.GITHUB_TOKEN;
    const path = "data/submissions.csv";
    const apiUrl = `https://api.github.com/repos/${repo}/contents/${path}`;

    let sha, existingRows = [];
    const getRes = await fetch(`${apiUrl}?ref=${branch}`, { headers: ghHeaders(token) });
    if (getRes.status === 200) {
      const data = await getRes.json();
      sha = data.sha;
      const content = decodeURIComponent(escape(atob(data.content.replace(/\n/g, ""))));
      existingRows = parseCSV(content).map((r) => [r.season, r.player_name, r.submitted_at, r.category_id, r.ref_id, r.answer]);
    } else if (getRes.status !== 404) {
      return json({ error: `Couldn't read submissions.csv: ${getRes.status}` }, 502, cors);
    }

    // a resubmission before kickoff replaces this player's prior rows for this season
    const kept = existingRows.filter((r) => !(String(r[0]) === String(payload.season) && r[1] === payload.player_name));
    const allRows = [...kept, ...newRows];

    const header = ["season", "player_name", "submitted_at", "category_id", "ref_id", "answer"];
    const csv = [header, ...allRows].map((r) => r.map(csvEscape).join(",")).join("\n") + "\n";

    const putRes = await fetch(apiUrl, {
      method: "PUT",
      headers: ghHeaders(token),
      body: JSON.stringify({
        message: `Submission: ${payload.player_name} (${payload.season})`,
        content: btoa(unescape(encodeURIComponent(csv))),
        sha,
        branch,
      }),
    });
    if (!putRes.ok) {
      const t = await putRes.text();
      return json({ error: `GitHub commit failed (${putRes.status}): ${t}` }, 502, cors);
    }

    return json({ ok: true }, 200, cors);
  },
};

function validateShape(p) {
  if (!p || typeof p !== "object") return "Missing payload";
  if (!p.season) return "Missing season";
  if (!p.player_name || typeof p.player_name !== "string" || !p.player_name.trim()) return "Missing player_name";
  if (!Array.isArray(p.scores)) return "Missing scores";
  if (!Array.isArray(p.answers)) return "Missing answers";
  if (!Array.isArray(p.squad)) return "Missing squad";
  for (const s of p.scores) {
    if (s.match_id == null || !Number.isFinite(+s.home) || !Number.isFinite(+s.away)) return "Malformed score entry";
  }
  for (const a of p.answers) {
    if (!a.category_id || a.answer === undefined || a.answer === "") return "Malformed answer entry";
  }
  return null;
}

function validateSquad(squad, players) {
  if (!Array.isArray(squad) || squad.length !== SQUAD_SIZE || new Set(squad).size !== SQUAD_SIZE) {
    return `Squad must be exactly ${SQUAD_SIZE} distinct players.`;
  }
  const byId = new Map(players.map((p) => [String(p.element_id), p]));
  const posCount = {}, teamCount = {};
  for (const id of squad) {
    const p = byId.get(String(id));
    if (!p) return `Player ${id} is not eligible this year.`;
    posCount[p.position] = (posCount[p.position] || 0) + 1;
    teamCount[p.team] = (teamCount[p.team] || 0) + 1;
  }
  for (const [pos, [min, max]] of Object.entries(SQUAD_RULES)) {
    const n = posCount[pos] || 0;
    if (n < min || n > max) return `Squad needs ${min}-${max} ${pos}, got ${n}.`;
  }
  for (const [team, n] of Object.entries(teamCount)) {
    if (n > MAX_PER_CLUB) return `Too many players from ${team} (max ${MAX_PER_CLUB}).`;
  }
  return null;
}

async function rawCSV(repo, branch, path) {
  const res = await fetch(`https://raw.githubusercontent.com/${repo}/${branch}/${path}`);
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return parseCSV(await res.text());
}

function parseCSV(txt) {
  const lines = txt.trim().split(/\r?\n/);
  if (!lines[0]) return [];
  const head = lines[0].split(",");
  return lines.slice(1).filter((l) => l.length).map((l) => {
    const c = [];
    let cur = "", inQ = false;
    for (let i = 0; i < l.length; i++) {
      const ch = l[i];
      if (ch === '"') inQ = !inQ;
      else if (ch === "," && !inQ) { c.push(cur); cur = ""; }
      else cur += ch;
    }
    c.push(cur);
    const o = {};
    head.forEach((h, i) => (o[h] = c[i] !== undefined ? c[i] : ""));
    return o;
  });
}

function csvEscape(v) {
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function ghHeaders(token) {
  return {
    Authorization: `Bearer ${token}`,
    "User-Agent": "boxing-day-worker",
    Accept: "application/vnd.github+json",
    "Content-Type": "application/json",
  };
}

function json(body, status, extraHeaders) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...extraHeaders },
  });
}
