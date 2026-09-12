document.addEventListener('DOMContentLoaded', () => {
  // --- DOM Elements ---
  const videoInput = document.getElementById('splitter_video');
  const dropzone = document.getElementById('splitter_dropzone');
  const previewDiv = document.getElementById('splitter_video_preview');
  const previewVideo = document.getElementById('splitter_preview_video');
  const videoName = document.getElementById('splitter_video_name');
  const videoDur = document.getElementById('splitter_video_dur');
  const fontSelect = document.getElementById('splitter_font');
  const fontSizeInput = document.getElementById('splitter_font_size');
  const fontColorInput = document.getElementById('splitter_font_color');
  const outlineColorInput = document.getElementById('splitter_outline_color');
  const generateBtn = document.getElementById('splitter_generate');
  const progress = document.getElementById('splitter_progress');
  const barFill = document.getElementById('splitter_bar');
  const resultArea = document.getElementById('resultArea');
  const reelsGrid = document.getElementById('splitter_reels_grid');

  // Position state
  let moviePos = 'top';
  let partPos = 'bottom-right';

  // --- Font Loading ---
  async function loadFonts() {
    try {
      const res = await fetch('/api/fonts');
      if (!res.ok) throw new Error('Fonts API failed');
      const fonts = await res.json();
      
      fonts.forEach(family => {
        const opt = document.createElement('option');
        opt.value = family;
        opt.textContent = family;
        fontSelect.appendChild(opt);
      });
    } catch (e) {
      console.error('Font load error:', e);
      // Fallback to system fonts
      const fallback = ['Poppins', 'Arial', 'Helvetica', 'sans-serif'];
      fallback.forEach(family => {
        const opt = document.createElement('option');
        opt.value = family;
        opt.textContent = family;
        fontSelect.appendChild(opt);
      });
    }
  }

  // --- Video Upload ---
  dropzone.addEventListener('click', () => videoInput.click());
  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('drag');
  });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag'));
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('drag');
    if (e.dataTransfer.files[0]) {
      videoInput.files = e.dataTransfer.files;
      videoInput.dispatchEvent(new Event('change'));
    }
  });

  videoInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const url = URL.createObjectURL(file);
    previewVideo.src = url;
    previewDiv.classList.remove('hidden');
    videoName.textContent = file.name;

    // Get video metadata
    const vid = previewVideo;
    vid.onloadedmetadata = () => {
      const dur = Math.floor(vid.duration);
      const mins = Math.floor(dur / 60);
      const secs = dur % 60;
      videoDur.textContent = `${mins}:${secs < 10 ? '0' : ''}${secs}`;
    };
  });

  // --- Position Selection ---
  document.querySelectorAll('.pos-btn-small').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.pos-btn-small').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      
      if (btn.dataset.pos === 'top') {
        moviePos = 'top';
        partPos = 'bottom-right';
      } else if (btn.dataset.pos === 'center') {
        moviePos = 'center';
        partPos = 'bottom-right';
      } else if (btn.dataset.pos === 'bottom') {
        moviePos = 'bottom';
        partPos = 'bottom-right';
      }
      
      // Update hidden inputs
      document.getElementById('splitter_movie_name_position').value = moviePos;
      document.getElementById('splitter_part_text_position').value = partPos;
    });
  });

  // Set initial active state
  document.querySelector('.pos-btn-small[data-pos="top"]').classList.add('active');

  // --- Generate Reels ---
  generateBtn.addEventListener('click', async () => {
    const video = videoInput.files[0];
    if (!video) {
      alert('Please upload a video first');
      return;
    }

    const font = fontSelect.value || 'Poppins';
    const fontSize = parseInt(fontSizeInput.value) || 40;
    const fontColor = fontColorInput.value || '#ffffff';
    const outlineColor = outlineColorInput.value || '#000000';

    // Show progress
    progress.style.display = 'block';
    generateBtn.disabled = true;
    generateBtn.textContent = 'Processing...';
    reelsGrid.innerHTML = '';

    try {
      const formData = new FormData();
      formData.append('video', video);
      formData.append('font', font);
      formData.append('font_size', fontSize);
      formData.append('font_color', fontColor);
      formData.append('outline_color', outlineColor);
      formData.append('movie_pos', moviePos);
      formData.append('part_pos', partPos);

      const res = await fetch('/api/movie/split', {
        method: 'POST',
        body: formData
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Split failed');
      }

      const result = await res.json();
      displayResults(result);

    } catch (err) {
      console.error(err);
      alert('Error: ' + err.message);
    } finally {
      progress.style.display = 'none';
      generateBtn.disabled = false;
      generateBtn.textContent = 'Generate Parts';
    }
  });

  function displayParts(parts) {
    reelsGrid.innerHTML = '';
    parts.forEach((part, i) => {
      const item = document.createElement('div');
      item.className = 'reel-item';
      item.innerHTML = `
        <div style="font-size: 12px; color: var(--muted); margin-bottom: 4px;">${part.name}</div>
        <video width="100%" controls playsinline style="border-radius: 6px; margin: 0 -10px 10px -10px;">
          <source src="${part.url}" type="video/mp4">
        </video>
        <small>Part ${i + 1} of ${parts.length}</small>
      `;
      reelsGrid.appendChild(item);
    });
  }

  function displayResults(result) {
    reelsGrid.innerHTML = '';
    if (result.success && result.reel_urls) {
      result.reel_urls.forEach((url, i) => {
        const div = document.createElement('div');
        div.className = 'reel';
        div.innerHTML = `
          <div style="font-size:10px; color:var(--muted); margin-bottom:4px;">${result.movie_name || 'Part'} ${i + 1} of ${result.total_parts}</div>
          <video controls playsinline style="width:100%; border-radius:4px; margin:4px -8px 8px -8px;">
            <source src="${url}" type="video/mp4">
          </video>
          <small>Part ${i + 1} of ${result.total_parts}</small>
        `;
        reelsGrid.appendChild(div);
      });
      
      const msg = document.createElement('div');
      msg.style = 'margin:8px 0; font-size:11px; color:var(--muted);';
      msg.textContent = 'Parts saved to: output/ directory. Click each video above to watch or download.';
      reelsGrid.appendChild(msg);
    } else if (result.error) {
      alert('Error: ' + result.error);
    }
    
    resultArea.style.display = 'block';
    previewDiv.classList.add('hidden');
    generateBtn.disabled = false;
    generateBtn.textContent = 'Generate Parts';
    progress.style.display = 'none';
  }

  // Initialize
  loadFonts();
});