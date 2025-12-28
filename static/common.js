let supabase;

async function initSupabase() {
  const res = await fetch("/api/public-config");
  const cfg = await res.json();
  supabase = window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseAnonKey);
}

async function apiFetch(url, options = {}) {
  const session = (await supabase.auth.getSession()).data.session;
  if (!session) throw new Error("로그인 필요");

  options.headers = {
    ...(options.headers || {}),
    "Authorization": `Bearer ${session.access_token}`,
    "Content-Type": "application/json"
  };

  const res = await fetch(url, options);
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(text);
  }
}

function logout() {
  supabase.auth.signOut();
  location.href = "/login";
}
