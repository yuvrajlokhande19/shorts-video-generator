const $ = (id) => document.getElementById(id);

/* ---------------- shared SSE reader ---------------- */
function streamSSE(resp, onEvent) {
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  return reader.read().then(function process({ value, done }) {
    if (done) return;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop();
    for (const part of parts) {
      const line = part.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      onEvent(JSON.parse(line.slice(5).trim()));
    }
    return reader.read().then(process);
  });
}

function addLog(listId, msg, cls) {
  const li = document.createElement("li");
  li.textContent = msg;
  if (cls) li.className = cls;
  $(listId).appendChild(li);
}

function showResult(prefix, data) {
  $(`result_${prefix}`).classList.remove("hidden");
  $(`result_${prefix}_title`).textContent = data.title || "Your video";
  $(`player_${prefix}`).src = data.url;
  const a = $(`download_${prefix}`);
  a.href = data.url;
  a.setAttribute("download", data.url.split("/").pop());
}

/* ---------------- AI Script Reel ---------------- */
async function loadVoices() {
  try {
    const r = await fetch("/api/voices");
    const voices = await r.json();
    const sel = $("voice");
    voices.forEach((v) => {
      const o = document.createElement("option");
      o.value = v.id; o.textContent = v.label;
      sel.appendChild(o);
    });
  } catch (e) { console.error(e); }
}

async function loadFonts() {
  try {
    const r = await fetch("/api/fonts");
    const fonts = await r.json();
    const sel = $("lyric_font");
    fonts.forEach((f) => {
      const o = document.createElement("option");
      o.value = f; o.textContent = f;
      sel.appendChild(o);
    });
  } catch (e) { console.error(e); }
}

$("music_vol").addEventListener("input", (e) => {
  $("mv_label").textContent = e.target.value + "%";
});

$("generate").addEventListener("click", async () => {
  const btn = $("generate");
  btn.disabled = true;
  $("log").innerHTML = "";
  $("result").classList.add("hidden");
  const orient = document.querySelector('input[name=orient]:checked').value;
  const opts = {
    topic: $("topic").value.trim(),
    orientation: orient,
    voice: $("voice").value,
    use_ai: $("use_ai").checked,
    music_volume: Number($("music_vol").value),
    subtitle_style: {
      font: $("sub_font").value,
      size: Number($("sub_size").value),
      color: $("sub_color").value,
      outline: $("sub_outline").value,
      position: $("sub_pos").value,
      bold: $("sub_bold").checked,
      box: $("sub_box").checked,
      highlight: $("sub_highlight").checked,
    },
  };
  if (!opts.topic) { alert("Please enter a topic."); btn.disabled = false; return; }
  try {
    const resp = await fetch("/api/generate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(opts),
    });
    await streamSSE(resp, (d) => {
      if (d.type === "progress") addLog("log", "• " + d.message);
      else if (d.type === "done") { addLog("log", "✓ " + d.message, "done"); showResult("", d); }
      else if (d.type === "error") addLog("log", "✗ " + d.message, "error");
    });
  } catch (e) { addLog("log", "✗ Network error: " + e.message, "error"); }
  btn.disabled = false;
});

/* ---------------- Lyric Reel ---------------- */
// tab switching
document.querySelectorAll(".tab").forEach((t) => {
  t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((x) => x.classList.add("hidden"));
    t.classList.add("active");
    $("panel-" + t.dataset.tab).classList.remove("hidden");
  });
});

// image mode boxes
document.querySelectorAll('input[name=imode]').forEach((r) => {
  r.addEventListener("change", () => {
    ["upload", "stock", "ai", "procedural"].forEach((m) => {
      $("im-" + m).classList.toggle("hidden", r.value !== m);
    });
  });
});
// lyrics mode
document.querySelectorAll('input[name=lmode]').forEach((r) => {
  r.addEventListener("change", () => {
    $("lyrics_text").classList.toggle("hidden", r.value !== "text");
    $("lyrics_file").classList.toggle("hidden", r.value !== "file");
  });
});

// stock image search
$("img_search").addEventListener("click", async () => {
  const box = $("img_results");
  box.innerHTML = "searching…";
  try {
    const resp = await fetch("/api/images/search", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: $("image_query").value.trim() || "couples" }),
    });
    const data = await resp.json();
    box.innerHTML = "";
    (data.images || []).forEach((img) => {
      const el = document.createElement("img");
      el.src = img.thumb || img.url;
      el.className = "thumb";
      el.onclick = () => {
        document.querySelectorAll(".thumb").forEach((x) => x.style.border = "");
        el.style.border = "3px solid #6c8cff";
        $("image_url_holder") || box.appendChild(Object.assign(document.createElement("input"), { type: "hidden", id: "image_url_holder", value: img.url }));
        window.__selectedImageUrl = img.url;
      };
      box.appendChild(el);
    });
    if (!(data.images || []).length) box.textContent = "No results (need a PEXELS/PIXABAY key in .env).";
  } catch (e) { box.textContent = "search failed: " + e.message; }
});

// song suggestions
$("song_suggest").addEventListener("click", async () => {
  const list = $("song_list");
  list.innerHTML = "loading…";
  try {
    const resp = await fetch("/api/songs?query=" + encodeURIComponent($("image_query").value || "lofi"));
    const songs = await resp.json();
    list.innerHTML = "";
    songs.forEach((s) => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = s.url; a.target = "_blank"; a.textContent = `🎵 ${s.title} — ${s.artist} (${s.license})`;
      a.style.color = "#6c8cff";
      li.appendChild(a);
      list.appendChild(li);
    });
  } catch (e) { list.innerHTML = "failed: " + e.message; }
});

$("generate_lyric").addEventListener("click", async () => {
  const btn = $("generate_lyric");
  btn.disabled = true;
  $("log_lyric").innerHTML = "";
  $("result_lyric").classList.add("hidden");

  if (!$("song_file").files.length) { alert("Please choose a song file."); btn.disabled = false; return; }

  const fd = new FormData();
  const orient = document.querySelector('input[name=lorient]:checked').value;
  const imode = document.querySelector('input[name=imode]:checked').value;
  const lmode = document.querySelector('input[name=lmode]:checked').value;

  fd.append("orientation", orient);
  fd.append("image_mode", imode);
  fd.append("lyrics_mode", lmode);
  fd.append("auto_sync", $("auto_sync").checked ? "on" : "");
  fd.append("kenburns", $("lyric_kenburns").checked ? "on" : "");
  fd.append("song_file", $("song_file").files[0]);

  if (imode === "upload" && $("image_file").files.length) fd.append("image_file", $("image_file").files[0]);
  if (imode === "stock" && window.__selectedImageUrl) fd.append("image_url", window.__selectedImageUrl);
  if (imode === "stock") fd.append("image_query", $("image_query").value);
  if (imode === "ai") fd.append("image_prompt", $("image_prompt").value);

  if (lmode === "file" && $("lyrics_file").files.length) fd.append("lyrics_file", $("lyrics_file").files[0]);
  else fd.append("lyrics_text", $("lyrics_text").value);

  fd.append("font", $("lyric_font").value);
  fd.append("size", $("lyric_size").value);
  fd.append("text_color", $("lyric_text_color").value);
  fd.append("highlight_color", $("lyric_hl_color").value);
  fd.append("outline_color", $("lyric_outline").value);
  fd.append("position", $("lyric_pos").value);
  fd.append("bold", $("lyric_bold").checked ? "on" : "");
  fd.append("box", $("lyric_box").checked ? "on" : "");
  fd.append("preview", $("lyric_preview").checked ? "on" : "");

  try {
    const resp = await fetch("/api/lyric/generate", { method: "POST", body: fd });
    await streamSSE(resp, (d) => {
      if (d.type === "progress") addLog("log_lyric", "• " + d.message);
      else if (d.type === "done") { addLog("log_lyric", "✓ " + d.message, "done"); showResult("lyric", d); }
      else if (d.type === "error") addLog("log_lyric", "✗ " + d.message, "error");
    });
  } catch (e) { addLog("log_lyric", "✗ Network error: " + e.message, "error"); }
  btn.disabled = false;
});

loadVoices();
loadFonts();
