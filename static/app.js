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
