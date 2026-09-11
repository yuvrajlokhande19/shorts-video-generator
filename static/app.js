const $ = (id) => document.getElementById(id);

/* ---------------- segmented control ---------------- */
function movePill() {
  const active = document.querySelector(".seg-btn.active");
  const pill = $("segPill");
  if (active && pill) {
    pill.style.width = active.offsetWidth + "px";
    pill.style.transform = `translateX(${active.offsetLeft - 5}px)`;
  }
}
document.querySelectorAll(".seg-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".seg-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    $("panel-" + btn.dataset.mode).classList.add("active");
    movePill();
  });
});
window.addEventListener("resize", movePill);
setTimeout(movePill, 60);

/* ---------------- radio cards ---------------- */
function updateVisibility(group, value) {
  if (group === "s_visual") {
    $("s_upload").classList.toggle("hidden", value !== "upload");
  } else if (group === "s_music") {
    $("s_music_up").classList.toggle("hidden", value !== "upload");
  } else if (group === "r_img") {
    $("r_upload").classList.toggle("hidden", value !== "upload");
    $("r_img_search").classList.toggle("hidden", value !== "stock");
    $("r_img_ai").classList.toggle("hidden", value !== "ai");
  }
}
document.querySelectorAll(".radio-card").forEach((card) => {
  card.addEventListener("click", () => {
    const group = card.dataset.name;
    const cards = [...document.querySelectorAll(`.radio-card[data-name="${group}"]`)];
    cards.forEach((c) => c.classList.remove("active"));
    card.classList.add("active");
    const idx = cards.indexOf(card);
    const radios = [...document.querySelectorAll(`input[type=radio][name="${group}"]`)];
    if (radios[idx]) radios[idx].checked = true;
    updateVisibility(group, radios[idx] ? radios[idx].value : "");
  });
});

/* ---------------- topic chips ---------------- */
$("s_chips").addEventListener("click", (e) => {
  if (e.target.classList.contains("chip")) $("s_topic").value = e.target.textContent;
});

/* ---------------- dropzones / previews ---------------- */
let sImages = [], sSong = null, rImage = null, rSong = null;

function bindDropzone(zoneId, inputId, onFiles) {
  const zone = $(zoneId), input = $(inputId);
  zone.addEventListener("click", () => input.click());
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("drag"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag"));
  zone.addEventListener("drop", (e) => { e.preventDefault(); zone.classList.remove("drag"); input.files = e.dataTransfer.files; onFiles(input.files); });
  input.addEventListener("change", () => onFiles(input.files));
}

function renderThumbs(containerId, files, onRemove) {
  const box = $(containerId);
  box.innerHTML = "";
  [...files].forEach((f, i) => {
    const wrap = document.createElement("div");
    wrap.className = "thumb-wrap";
    const img = document.createElement("img");
    img.src = URL.createObjectURL(f);
    const rm = document.createElement("button");
    rm.className = "rm"; rm.textContent = "×"; rm.type = "button";
    rm.onclick = () => onRemove(i);
    wrap.append(img, rm);
    box.appendChild(wrap);
  });
}

bindDropzone("s_upload", "s_images", (files) => {
  sImages = [...files];
  rerenderS();
});
function rerenderS() {
  renderThumbs("s_upload", sImages, (i) => { sImages.splice(i, 1); rerenderS(); });
}

bindDropzone("s_music_up", "s_bgsong", (files) => {
  sSong = files[0] || null;
  $("s_audio_prev").innerHTML = sSong ? `<audio class="audio-prev" controls src="${URL.createObjectURL(sSong)}"></audio>` : "";
});

bindDropzone("r_upload", "r_image_file", (files) => {
  rImage = files[0] || null;
  renderThumbs("r_upload", rImage ? [rImage] : [], () => { rImage = null; renderThumbs("r_upload", []); });
});

bindDropzone("r_song_dz", "r_song_file", (files) => {
  rSong = files[0] || null;
  $("r_audio_prev").innerHTML = rSong ? `<audio class="audio-prev" controls src="${URL.createObjectURL(rSong)}"></audio>` : "";
});

/* ---------------- SSE + progress ---------------- */
function streamSSE(resp, onEvent) {
  const reader = resp.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  return reader.read().then(function proc({ value, done }) {
    if (done) return;
    buf += dec.decode(value, { stream: true });
    buf.split("\n\n").forEach((part, i, arr) => {
      if (i === arr.length - 1) return;
      const line = part.split("\n").find((l) => l.startsWith("data:"));
      if (line) onEvent(JSON.parse(line.slice(5).trim()));
    });
    buf = buf.split("\n\n").pop();
    return reader.read().then(proc);
  });
}

function setupProgress(prefix) {
  $(prefix + "_steps").innerHTML = "";
  $(prefix + "_bar").style.width = "4%";
  $(prefix + "_progress").classList.add("show");
  $(prefix + "_result").classList.remove("show");
}
function step(prefix, msg, cls) {
  const li = document.createElement("li");
  if (cls) li.className = cls;
  li.innerHTML = `<span class="tick">${cls === "done" ? "✓" : cls === "error" ? "!" : ""}</span><span>${msg}</span>`;
  $(prefix + "_steps").appendChild(li);
  const pct = Math.min(96, ($(prefix + "_steps").children.length) * 15);
  $(prefix + "_bar").style.width = pct + "%";
}
function finishProgress(prefix) { $(prefix + "_bar").style.width = "100%"; }

function showResult(prefix, data) {
  $(prefix + "_result").classList.remove("show");
  void $(prefix + "_result").offsetWidth;
  $(prefix + "_result").classList.add("show");
  $(prefix + "_player").src = data.url;
  const a = $(prefix + "_download");
  a.href = data.url;
  a.setAttribute("download", data.url.split("/").pop());
}

/* ---------------- load options ---------------- */
async function loadVoices() {
  try {
    const v = await (await fetch("/api/voices")).json();
    v.forEach((x) => $("s_voice").appendChild(new Option(x.label, x.id)));
  } catch (e) {}
}
async function loadFonts() {
  try {
    const f = await (await fetch("/api/fonts")).json();
    f.forEach((x) => { $("r_font").appendChild(new Option(x, x)); });
  } catch (e) {}
}
loadVoices(); loadFonts();

/* ---------------- SHORT generate ---------------- */
$("s_generate").addEventListener("click", async () => {
  const btn = $("s_generate"); btn.disabled = true;
  if (!$("s_topic").value.trim()) { alert("Please enter a topic."); btn.disabled = false; return; }
  setupProgress("s");
  startFluid();
  const fd = new FormData();
  fd.append("topic", $("s_topic").value.trim());
  fd.append("orientation", document.querySelector('input[name=s_orient]:checked').value);
  fd.append("voice", $("s_voice").value);
  fd.append("script_lang", $("s_script_lang").value);
  if ($("s_use_ai").checked) fd.append("use_ai", "on");
  fd.append("music_volume", $("s_mvol").value);
  fd.append("font", $("s_font").value);
  fd.append("size", $("s_size").value);
  fd.append("color", $("s_color").value);
  fd.append("outline", $("s_outline").value);
  fd.append("position", $("s_pos").value);
  if ($("s_bold").checked) fd.append("bold", "on");
  if ($("s_box").checked) fd.append("box", "on");
  if ($("s_hl").checked) fd.append("highlight", "on");
  if (document.querySelector('input[name=s_visual]:checked').value === "upload")
    sImages.forEach((f) => fd.append("images", f));
  if (document.querySelector('input[name=s_music]:checked').value === "upload" && sSong)
    fd.append("bg_song", sSong);

  try {
    const resp = await fetch("/api/generate", { method: "POST", body: fd });
    await streamSSE(resp, (d) => {
      if (d.type === "progress") step("s", d.message, "done");
      else if (d.type === "done") { finishProgress("s"); stopFluid(); step("s", d.message, "done"); showResult("s", d); }
      else if (d.type === "error") { stopFluid(); step("s", d.message, "error"); }
    });
  } catch (e) { step("s", "Network error: " + e.message, "error"); }
  btn.disabled = false;
});

/* ---------------- REEL generate ---------------- */
$("r_img_btn").addEventListener("click", async () => {
  const box = $("r_img_results"); box.innerHTML = "searching…";
  try {
    const r = await fetch("/api/images/search", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: $("r_image_query").value.trim() || "couples" }),
    });
    const data = await r.json();
    box.innerHTML = "";
    (data.images || []).forEach((img) => {
      const el = document.createElement("img");
      el.src = img.thumb || img.url; el.className = "thumb";
      el.onclick = () => {
        document.querySelectorAll("#r_img_results .thumb").forEach((x) => (x.style.border = ""));
        el.style.border = "3px solid #db2777";
        window.__rImgUrl = img.url;
      };
      box.appendChild(el);
    });
    if (!(data.images || []).length) box.textContent = "No results (need a PEXELS/PIXABAY key in .env).";
  } catch (e) { box.textContent = "search failed: " + e.message; }
});

$("r_song_btn").addEventListener("click", async () => {
  const list = $("r_song_list"); list.innerHTML = "loading…";
  try {
    const r = await fetch("/api/songs?query=" + encodeURIComponent($("r_image_query").value || "lofi"));
    const songs = await r.json();
    list.innerHTML = "";
    songs.forEach((s) => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = s.url; a.target = "_blank"; a.textContent = `🎵 ${s.title} — ${s.artist}`;
      a.style.color = "#c4b5fd"; li.appendChild(a); list.appendChild(li);
    });
  } catch (e) { list.innerHTML = "failed: " + e.message; }
});

$("r_generate").addEventListener("click", async () => {
  const btn = $("r_generate"); btn.disabled = true;
  if (!$("r_song_file").files.length) { alert("Please choose a song file."); btn.disabled = false; return; }
  setupProgress("r");
  startFluid();
  const fd = new FormData();
  fd.append("orientation", document.querySelector('input[name=r_orient]:checked').value);
  fd.append("image_mode", document.querySelector('input[name=r_img]:checked').value);
  fd.append("lyrics_mode", document.querySelector('input[name=r_lyr]:checked').value);
  fd.append("lyrics_lang", $("r_lyrics_lang").value);
  fd.append("theme", $("r_theme").value);
  if ($("r_auto").checked) fd.append("auto_sync", "on");
  if ($("r_kenburns").checked) fd.append("kenburns", "on");
  fd.append("song_file", $("r_song_file").files[0]);
  if (document.querySelector('input[name=r_img]:checked').value === "upload" && rImage)
    fd.append("image_file", rImage);
  if (window.__rImgUrl) fd.append("image_url", window.__rImgUrl);
  if (document.querySelector('input[name=r_img]:checked').value === "stock")
    fd.append("image_query", $("r_image_query").value);
  if (document.querySelector('input[name=r_img]:checked').value === "ai")
    fd.append("image_prompt", $("r_image_prompt").value);
  if (document.querySelector('input[name=r_lyr]:checked').value === "file" && $("r_lyrics_file").files.length)
    fd.append("lyrics_file", $("r_lyrics_file").files[0]);
  else fd.append("lyrics_text", $("r_lyrics").value);
  fd.append("font", $("r_font").value);
  fd.append("size", $("r_size").value);
  fd.append("text_color", $("r_tcolor").value);
  fd.append("highlight_color", $("r_hcolor").value);
  fd.append("outline_color", $("r_ocolor").value);
  fd.append("position", $("r_pos").value);
  if ($("r_bold").checked) fd.append("bold", "on");
  if ($("r_box").checked) fd.append("box", "on");
  if ($("r_preview").checked) fd.append("preview", "on");

  try {
    const resp = await fetch("/api/lyric/generate", { method: "POST", body: fd });
    await streamSSE(resp, (d) => {
      if (d.type === "progress") step("r", d.message, "done");
      else if (d.type === "done") { finishProgress("r"); stopFluid(); step("r", d.message, "done"); showResult("r", d);
        if (d.job_id) {
          window.__rJobId = d.job_id;
          $("r_edit").classList.remove("hidden");
          $("r_edit_lyrics").value = d.lyrics || "";
          setRlyrMode("text");
          $("r_lyrics").value = d.lyrics || "";
        }
      }
      else if (d.type === "error") { stopFluid(); step("r", d.message, "error"); }
    });
  } catch (e) { step("r", "Network error: " + e.message, "error"); }
  btn.disabled = false;
});

/* lyrics file picker shows when "upload file" selected */
document.querySelectorAll('.radio-card[data-name="r_lyr"]').forEach((c) => {
  c.addEventListener("click", () => {
    const val = document.querySelector('input[name=r_lyr]:checked').value;
    $("r_lyrics").classList.toggle("hidden", val !== "text");
    $("r_lyrics_file").classList.toggle("hidden", val !== "file");
  });
});

/* set the Lyrics mode (auto/text/file) programmatically + update UI */
function setRlyrMode(mode) {
  const cards = [...document.querySelectorAll('.radio-card[data-name="r_lyr"]')];
  const order = ["auto", "text", "file"];
  const idx = order.indexOf(mode);
  cards.forEach((c, i) => c.classList.toggle("active", i === idx));
  const radios = [...document.querySelectorAll('input[name=r_lyr]')];
  if (radios[idx]) radios[idx].checked = true;
  $("r_lyrics").classList.toggle("hidden", mode !== "text");
  $("r_lyrics_file").classList.toggle("hidden", mode !== "file");
}

/* Draft lyrics (no song needed) -> fill editable textarea */
$("r_draft").addEventListener("click", async () => {
  setupProgress("r");
  startFluid();
  const fd = new FormData();
  fd.append("lyrics_lang", $("r_lyrics_lang").value);
  fd.append("theme", $("r_theme").value);
  fd.append("draft", "1");
  try {
    const resp = await fetch("/api/lyric/generate", { method: "POST", body: fd });
    await streamSSE(resp, (d) => {
      if (d.type === "progress") step("r", d.message, "done");
      else if (d.type === "done" && d.type2 === "lyrics") {
        finishProgress("r"); stopFluid(); step("r", d.message, "done");
        setRlyrMode("text");
        $("r_lyrics").value = d.lyrics || "";
      } else if (d.type === "error") { stopFluid(); step("r", d.message, "error"); }
    });
  } catch (e) { step("r", "Network error: " + e.message, "error"); }
});

/* Re-render a finished reel with edited lyrics / style */
$("r_rerender").addEventListener("click", async () => {
  if (!window.__rJobId) { alert("Generate a reel first."); return; }
  setupProgress("r");
  startFluid();
  const fd = new FormData();
  fd.append("job_id", window.__rJobId);
  fd.append("lyrics_text", $("r_edit_lyrics").value);
  fd.append("font", $("r_font").value);
  fd.append("size", $("r_size").value);
  fd.append("text_color", $("r_tcolor").value);
  fd.append("highlight_color", $("r_hcolor").value);
  fd.append("outline_color", $("r_ocolor").value);
  fd.append("position", $("r_pos").value);
  if ($("r_bold").checked) fd.append("bold", "on");
  if ($("r_box").checked) fd.append("box", "on");
  if ($("r_preview").checked) fd.append("preview", "on");
  if ($("r_kenburns").checked) fd.append("kenburns", "on");
  try {
    const resp = await fetch("/api/lyric/regenerate", { method: "POST", body: fd });
    await streamSSE(resp, (d) => {
      if (d.type === "progress") step("r", d.message, "done");
      else if (d.type === "done") {
        finishProgress("r"); stopFluid(); step("r", d.message, "done"); showResult("r", d);
        if (d.job_id) { window.__rJobId = d.job_id; $("r_edit_lyrics").value = d.lyrics || ""; }
      } else if (d.type === "error") { stopFluid(); step("r", d.message, "error"); }
    });
  } catch (e) { step("r", "Network error: " + e.message, "error"); }
});

/* ---------------- fluid simulation (generative background) ---------------- */
const fluid = $("fluid");
const fctx = fluid.getContext("2d");
let fluidRAF = null, fluidT = 0;
const BLOBS = [
  "rgba(124,58,237,0.55)", "rgba(219,39,119,0.5)",
  "rgba(225,29,72,0.45)", "rgba(56,189,248,0.4)",
];
function resizeFluid() { fluid.width = innerWidth; fluid.height = innerHeight; }
addEventListener("resize", resizeFluid);
function loopFluid() {
  fluidT += 0.012;
  const w = fluid.width, h = fluid.height;
  fctx.clearRect(0, 0, w, h);
  fctx.globalCompositeOperation = "lighter";
  for (let i = 0; i < BLOBS.length; i++) {
    const x = w / 2 + Math.cos(fluidT * 0.5 + i * 1.7) * w * 0.26 + Math.sin(fluidT * 0.9 + i) * 70;
    const y = h / 2 + Math.sin(fluidT * 0.6 + i * 2.1) * h * 0.26 + Math.cos(fluidT * 0.7 + i) * 70;
    const r = Math.max(w, h) * 0.34;
    const g = fctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, BLOBS[i]);
    g.addColorStop(1, "rgba(0,0,0,0)");
    fctx.fillStyle = g;
    fctx.beginPath(); fctx.arc(x, y, r, 0, 7); fctx.fill();
  }
  fluidRAF = requestAnimationFrame(loopFluid);
}
function startFluid() { resizeFluid(); fluid.classList.add("on"); if (!fluidRAF) loopFluid(); }
function stopFluid() { fluid.classList.remove("on"); if (fluidRAF) { cancelAnimationFrame(fluidRAF); fluidRAF = null; } }


/* ============ MOVIE SPLITTER FUNCTIONALITY ============ */

let splitterVideo = null;
let splitterVideoUrl = null;

// Load fonts for splitter
async function loadSplitterFonts() {
  try {
    const f = await (await fetch("/api/fonts")).json();
    const select = $("splitter_font");
    select.innerHTML = "";
    f.forEach((x) => select.appendChild(new Option(x, x)));
    // Set default to Poppins if available
    if (f.includes("Poppins")) select.value = "Poppins";
  } catch (e) { console.error("Failed to load fonts:", e); }
}
loadSplitterFonts();

// Bind dropzone for movie upload - direct input change listener (input overlays dropzone)
const splitterVideoInput = $("splitter_video");
splitterVideoInput.addEventListener("change", () => {
  const files = splitterVideoInput.files;
  splitterVideo = files[0] || null;
  if (splitterVideo) {
    handleSplitterVideoSelect(splitterVideo);
  }
});

// Keep drag-and-drop functionality
const splitterDropzone = $("splitter_dropzone");
splitterDropzone.addEventListener("dragover", (e) => { e.preventDefault(); splitterDropzone.classList.add("drag"); });
splitterDropzone.addEventListener("dragleave", () => splitterDropzone.classList.remove("drag"));
splitterDropzone.addEventListener("drop", (e) => { 
  e.preventDefault(); 
  splitterDropzone.classList.remove("drag"); 
  const files = e.dataTransfer.files;
  splitterVideo = files[0] || null;
  if (splitterVideo) {
    handleSplitterVideoSelect(splitterVideo);
  }
});

function handleSplitterVideoSelect(file) {
  splitterVideoUrl = URL.createObjectURL(file);
  
  // Show video info
  $("splitter_video_name").textContent = file.name;
  $("splitter_video_info").classList.remove("hidden");
  $("splitter_preview_video").src = splitterVideoUrl;
  
  // Get video metadata
  const video = $("splitter_preview_video");
  video.onloadedmetadata = () => {
    const duration = video.duration;
    const width = video.videoWidth;
    const height = video.videoHeight;
    $("splitter_video_duration").textContent = formatDuration(duration);
    $("splitter_video_resolution").textContent = `${width}x${height}`;
    
    // Update segment estimate
    updateSegmentEstimate(duration);
    
    // Auto-fill movie name from filename if empty
    if (!$("splitter_movie_name").value.trim()) {
      const name = file.name.replace(/\.[^/.]+$/, "");
      $("splitter_movie_name").value = cleanMovieName(name);
    }
  };
}

function formatDuration(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function cleanMovieName(name) {
  return name
    .replace(/\[.*?\]/g, '')
    .replace(/\(.*?\)/g, '')
    .replace(/\b(1080p|720p|480p|4k|2160p|bluray|webrip|web-dl|hdtv|dvdrip|bdrip)\b/gi, '')
    .replace(/\b(x264|x265|h264|h265|hevc|avc)\b/gi, '')
    .replace(/\b(aac|ac3|dts|mp3|flac)\b/gi, '')
    .replace(/\b(5\.1|7\.1|2\.0)\b/gi, '')
    .replace(/\b(hindi|english|eng|hin|tam|tel|mal|kan)\b/gi, '')
    .replace(/\b(official|trailer|teaser|full|movie|film)\b/gi, '')
    .replace(/[-_.]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function updateSegmentEstimate(duration) {
  const segmentDuration = parseFloat($("splitter_segment_duration").value) || 30;
  const numSegments = Math.ceil(duration / segmentDuration);
  const lastSegmentDuration = duration % segmentDuration || segmentDuration;
  const needsPadding = lastSegmentDuration < segmentDuration;
  
  const html = `
    <div class="estimate-item"><span class="estimate-label">Video Duration</span><span class="estimate-value">${formatDuration(duration)}</span></div>
    <div class="estimate-item"><span class="estimate-label">Segment Duration</span><span class="estimate-value">${segmentDuration}s</span></div>
    <div class="estimate-item"><span class="estimate-label">Total Reels</span><span class="estimate-value highlight">${numSegments}</span></div>
    <div class="estimate-item"><span class="estimate-label">Last Segment</span><span class="estimate-value ${needsPadding ? 'highlight' : ''}">${formatDuration(lastSegmentDuration)}${needsPadding ? ' (will be padded)' : ''}</span></div>
  `;
  $("splitter_segment_estimate").innerHTML = html;
}

// Update estimate when segment duration changes
$("splitter_segment_duration").addEventListener("change", () => {
  const video = $("splitter_preview_video");
  if (video.duration) updateSegmentEstimate(video.duration);
});

// Position button handlers
function setupPositionButtons(containerId, hiddenInputId) {
  const container = $(containerId);
  const hiddenInput = $(hiddenInputId);
  container.querySelectorAll(".pos-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      container.querySelectorAll(".pos-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      hiddenInput.value = btn.dataset.pos;
      updatePreviewCanvas();
    });
  });
}
setupPositionButtons("splitter_movie_pos_buttons", "splitter_movie_name_position");
setupPositionButtons("splitter_part_pos_buttons", "splitter_part_text_position");

// Update preview canvas when style changes
["splitter_font", "splitter_font_size", "splitter_font_color", "splitter_outline_color",
 "splitter_movie_name_position", "splitter_part_text_position"].forEach(id => {
  const el = $(id);
  if (el) el.addEventListener("input", updatePreviewCanvas);
  if (el && el.tagName === "SELECT") el.addEventListener("change", updatePreviewCanvas);
});

// Live preview canvas
function updatePreviewCanvas() {
  const canvas = $("splitter_preview_canvas");
  const ctx = canvas.getContext("2d");
  const w = 540, h = 960;
  
  // Clear
  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, w, h);
  
  // Draw gradient background (simulating video)
  const gradient = ctx.createLinearGradient(0, 0, w, h);
  gradient.addColorStop(0, "#1a1a2e");
  gradient.addColorStop(1, "#16213e");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, w, h);
  
  // Movie name
  const movieName = $("splitter_movie_name").value || "Movie Title";
  const partText = `Part 1 of ${Math.ceil(($("splitter_preview_video").duration || 120) / ($("splitter_segment_duration").value || 30))}`;
  
  const fontSize = parseInt($("splitter_font_size").value) || 56;
  const fontFamily = $("splitter_font").value || "Poppins";
  const fontColor = $("splitter_font_color").value || "#ffffff";
  const outlineColor = $("splitter_outline_color").value || "#000000";
  
  const scale = 0.5; // Canvas is half resolution
  
  // Draw movie name
  ctx.font = `bold ${fontSize * scale}px "${fontFamily}"`;
  ctx.fillStyle = fontColor;
  ctx.strokeStyle = outlineColor;
  ctx.lineWidth = 3 * scale;
  
  const movieNamePos = $("splitter_movie_name_position").value;
  const partPos = $("splitter_part_text_position").value;
  
  const margin = 40 * scale;
  const textMetrics = ctx.measureText(movieName);
  const textHeight = fontSize * scale * 1.2;
  
  let movieX, movieY, partX, partY;
  
  // Movie name position
  switch (movieNamePos) {
    case "top": movieX = (w - textMetrics.width) / 2; movieY = margin + textHeight; break;
    case "top-left": movieX = margin; movieY = margin + textHeight; break;
    case "top-right": movieX = w - textMetrics.width - margin; movieY = margin + textHeight; break;
    case "center": movieX = (w - textMetrics.width) / 2; movieY = h / 2; break;
    case "bottom": movieX = (w - textMetrics.width) / 2; movieY = h - margin; break;
    case "bottom-left": movieX = margin; movieY = h - margin; break;
    case "bottom-right": movieX = w - textMetrics.width - margin; movieY = h - margin; break;
  }
  
  // Part text position
  ctx.font = `bold ${(fontSize - 8) * scale}px "${fontFamily}"`;
  const partMetrics = ctx.measureText(partText);
  const partHeight = (fontSize - 8) * scale * 1.2;
  
  switch (partPos) {
    case "top": partX = (w - partMetrics.width) / 2; partY = margin + partHeight; break;
    case "top-left": partX = margin; partY = margin + partHeight; break;
    case "top-right": partX = w - partMetrics.width - margin; partY = margin + partHeight; break;
    case "center": partX = (w - partMetrics.width) / 2; partY = h / 2; break;
    case "bottom": partX = (w - partMetrics.width) / 2; partY = h - margin; break;
    case "bottom-left": partX = margin; partY = h - margin; break;
    case "bottom-right": partX = w - partMetrics.width - margin; partY = h - margin; break;
  }
  
  // Draw with outline
  ctx.strokeText(movieName, movieX, movieY);
  ctx.fillText(movieName, movieX, movieY);
  
  ctx.strokeText(partText, partX, partY);
  ctx.fillText(partText, partX, partY);
}

// Auto-fetch movie metadata
$("splitter_fetch_meta").addEventListener("click", async () => {
  const btn = $("splitter_fetch_meta");
  const query = $("splitter_movie_name").value.trim() || (splitterVideo ? splitterVideo.name : "");
  if (!query) { alert("Enter a movie name or upload a video first."); return; }
  
  btn.disabled = true;
  btn.innerHTML = `<svg class="spinner" width="14" height="14" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" fill="none" stroke-dasharray="30 30" stroke-linecap="round" style="animation: spin 1s linear infinite"/></svg> Searching...`;
  
  try {
    const resp = await fetch("/api/movie/metadata", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, language: "en-US" })
    });
    const data = await resp.json();
    
    if (data.title) {
      displayMovieMeta(data);
    } else {
      alert("Could not find movie info. Try a different name.");
    }
  } catch (e) {
    alert("Search failed: " + e.message);
  }
  
  btn.disabled = false;
  btn.innerHTML = `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35" stroke-linecap="round" stroke-linejoin="round"/></svg> Auto-fetch Movie Info`;
});

function displayMovieMeta(data) {
  const content = $("splitter_meta_content");
  let html = "";
  if (data.title) html += `<strong>Title:</strong> ${data.title}<br>`;
  if (data.original_title && data.original_title !== data.title) html += `<strong>Original:</strong> ${data.original_title}<br>`;
  if (data.year) html += `<strong>Year:</strong> ${data.year}<br>`;
  if (data.runtime) html += `<strong>Runtime:</strong> ${data.runtime} min<br>`;
  if (data.language) html += `<strong>Language:</strong> ${data.language}<br>`;
  if (data.genres && data.genres.length) html += `<strong>Genres:</strong> ${data.genres.join(", ")}<br>`;
  if (data.overview) html += `<strong>Overview:</strong> ${data.overview.substring(0, 200)}...<br>`;
  html += `<br><small style="color:var(--muted)">Source: ${data.source}</small>`;
  
  content.innerHTML = html;
  $("splitter_meta_result").classList.remove("hidden");
  
  // Use this title button
  $("splitter_use_meta").onclick = () => {
    $("splitter_movie_name").value = data.title;
    updatePreviewCanvas();
  };
}

// Generate reels
$("splitter_generate").addEventListener("click", async () => {
  const btn = $("splitter_generate");
  
  if (!splitterVideo) { alert("Please upload a video file first."); return; }
  if (!$("splitter_movie_name").value.trim()) { alert("Please enter a movie name."); return; }
  
  btn.disabled = true;
  btn.innerHTML = `<svg class="spinner" width="18" height="18" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" fill="none" stroke-dasharray="30 30" stroke-linecap="round" style="animation: spin 1s linear infinite"/></svg> Generating...`;
  
  setupProgress("splitter");
  startFluid();
  
  const fd = new FormData();
  fd.append("video_file", splitterVideo);
  fd.append("movie_name", $("splitter_movie_name").value.trim());
  fd.append("segment_duration", $("splitter_segment_duration").value);
  fd.append("font_size", $("splitter_font_size").value);
  fd.append("font_color", $("splitter_font_color").value);
  fd.append("outline_color", $("splitter_outline_color").value);
  fd.append("font_family", $("splitter_font").value);
  fd.append("movie_name_position", $("splitter_movie_name_position").value);
  fd.append("part_text_position", $("splitter_part_text_position").value);
  fd.append("pad_last_segment", $("splitter_pad_last").checked ? "true" : "false");
  fd.append("background_color", $("splitter_bg_color").value);
  
  try {
    const resp = await fetch("/api/movie/split", { method: "POST", body: fd });
    await streamSSE(resp, (d) => {
      if (d.type === "progress") step("splitter", d.message, "done");
      else if (d.type === "done") {
        finishProgress("splitter");
        stopFluid();
        step("splitter", d.message, "done");
        showSplitterResults(d);
      }
      else if (d.type === "error") { stopFluid(); step("splitter", d.message, "error"); }
    });
  } catch (e) {
    stopFluid();
    step("splitter", "Network error: " + e.message, "error");
  }
  
  btn.disabled = false;
  btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="6 4 20 12 6 20 6 4" fill="currentColor" stroke="none"/></svg> Generate Reels`;
});

function showSplitterResults(data) {
  const grid = $("splitter_reels_grid");
  grid.innerHTML = "";
  
  if (data.reels && data.reels.length > 0) {
    data.reels.forEach((url, idx) => {
      const item = document.createElement("div");
      item.className = "reel-item";
      item.innerHTML = `
        <video playsinline muted loop preload="metadata">
          <source src="${url}" type="video/mp4">
        </video>
        <div class="reel-info">
          <div class="reel-title">${data.movie_name} - Part ${idx + 1} of ${data.total_parts}</div>
          <div class="reel-meta">
            <span>9:16 Portrait</span>
            <span>30s</span>
          </div>
          <div class="reel-actions">
            <a href="${url}" class="btn-download" download>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" stroke-linecap="round" stroke-linejoin="round"/></svg>
              Download
            </a>
            <button class="btn-share" onclick="shareReel('${url}', '${data.movie_name} - Part ${idx + 1}')">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.59 13.51a5 5 0 0 1 7.41 0M15.42 19a5 5 0 0 1-7.41 0"/></svg>
              Share
            </button>
          </div>
        </div>
      `;
      // Auto-play on hover
      const video = item.querySelector("video");
      item.addEventListener("mouseenter", () => video.play().catch(()=>{}));
      item.addEventListener("mouseleave", () => video.pause());
      grid.appendChild(item);
    });
    
    // Add download all button
    const downloadAll = document.createElement("div");
    downloadAll.className = "download-all";
    downloadAll.innerHTML = `
      <button class="btn-primary" onclick="downloadAllReels('${data.reels.join(",")}', '${data.movie_name}')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" stroke-linecap="round" stroke-linejoin="round"/></svg>
        Download All (${data.reels.length} reels)
      </button>
    `;
    grid.appendChild(downloadAll);
  }
  
  $("splitter_result").classList.remove("show");
  void $("splitter_result").offsetWidth;
  $("splitter_result").classList.add("show");
}

// Initial preview
updatePreviewCanvas();

// Initial pill position
setTimeout(movePill, 100);

// Share reel function
function shareReel(url, title) {
  if (navigator.share) {
    navigator.share({ title, url }).catch(() => {});
  } else {
    navigator.clipboard.writeText(url).then(() => {
      alert("Link copied to clipboard!");
    });
  }
}

// Download all reels as ZIP (client-side)
async function downloadAllReels(urlsStr, movieName) {
  const urls = urlsStr.split(",");
  const btn = event.target.closest("button");
  const originalText = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<svg class="spinner" width="16" height="16" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" fill="none" stroke-dasharray="30 30" stroke-linecap="round" style="animation: spin 1s linear infinite"/></svg> Preparing...`;
  
  try {
    // Use JSZip if available, otherwise download individually
    if (typeof JSZip !== "undefined") {
      const zip = new JSZip();
      for (let i = 0; i < urls.length; i++) {
        const resp = await fetch(urls[i]);
        const blob = await resp.blob();
        zip.file(`${movieName}_part${String(i+1).padStart(3, '0')}.mp4`, blob);
      }
      const content = await zip.generateAsync({ type: "blob" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(content);
      link.download = `${movieName}_reels.zip`;
      link.click();
    } else {
      // Fallback: download each file
      for (let i = 0; i < urls.length; i++) {
        const link = document.createElement("a");
        link.href = urls[i];
        link.download = `${movieName}_part${String(i+1).padStart(3, '0')}.mp4`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        await new Promise(r => setTimeout(r, 300)); // Small delay between downloads
      }
    }
  } catch (e) {
    console.error("Download failed:", e);
    alert("Download failed. Try downloading individually.");
  }
  
  btn.disabled = false;
  btn.innerHTML = originalText;
}
