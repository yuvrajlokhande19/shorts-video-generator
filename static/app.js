const $ = (id) => document.getElementById(id);

async function loadVoices() {
  try {
    const r = await fetch("/api/voices");
    const voices = await r.json();
    const sel = $("voice");
    sel.innerHTML = "";
    voices.forEach((v) => {
      const o = document.createElement("option");
      o.value = v.id;
      o.textContent = v.label;
      sel.appendChild(o);
    });
  } catch (e) {
    console.error(e);
  }
}

$("music_vol").addEventListener("input", (e) => {
  $("mv_label").textContent = e.target.value + "%";
});

$("generate").addEventListener("click", async () => {
  const btn = $("generate");
  btn.disabled = true;
  const log = $("log");
  log.innerHTML = "";
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

  if (!opts.topic) {
    alert("Please enter a topic.");
    btn.disabled = false;
    return;
  }

  const addLog = (msg, cls) => {
    const li = document.createElement("li");
    li.textContent = msg;
    if (cls) li.className = cls;
    log.appendChild(li);
  };

  try {
    const resp = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(opts),
    });
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop();
      for (const part of parts) {
        const line = part.split("\n").find((l) => l.startsWith("data:"));
        if (!line) continue;
        const data = JSON.parse(line.slice(5).trim());
        if (data.type === "progress") addLog("• " + data.message);
        else if (data.type === "done") {
          addLog("✓ " + data.message, "done");
          showResult(data);
        } else if (data.type === "error") {
          addLog("✗ " + data.message, "error");
        }
      }
    }
  } catch (e) {
    addLog("✗ Network error: " + e.message, "error");
  }
  btn.disabled = false;
});

function showResult(data) {
  $("result").classList.remove("hidden");
  $("result_title").textContent = data.title || "Your video";
  $("player").src = data.url;
  $("download").href = data.url;
  const ext = data.url.split("/").pop();
  $("download").setAttribute("download", ext);
}

loadVoices();
