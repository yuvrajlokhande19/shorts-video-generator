"""Movie-to-Reels Splitter: Split long videos into 30-second reel segments with text overlays."""
import subprocess
import json
import math
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import uuid


# Font directory - relative to where this script is run or installed
# The bundled fonts are in the fonts/ directory
FONTS_DIR = Path(__file__).parent.parent / "fonts" / "fonts"

# Mapped font names to filenames (matching config.py FONTS dict)
FONT_MAP = {
    "Dancing Script": "DancingScript.ttf",
    "Pacifico": "Pacifico.ttf",
    "Lobster": "Lobster.ttf",
    "Caveat": "Caveat.ttf",
    "Pinyon Script": "PinyonScript.ttf",
    "Great Vibes": "GreatVibes.ttf",
    "Sacramento": "Sacramento.ttf",
    "Kaushan Script": "KaushanScript.ttf",
    "Oleo Script": "OleoScript.ttf",
    "Tangerine": "Tangerine.ttf",
    # System fonts - these may or may not work depending on the system
    "Arial": None,  # Use system Arial
    "Arial Black": None,
    "Impact": None,
    "Georgia": None,
    "Times New Roman": None,
    "Verdana": None,
    "Tahoma": None,
    "Trebuchet MS": None,
    "Comic Sans MS": None,
    "Courier New": None,
    "Roboto": None,
    "Open Sans": None,
    "Montserrat": None,
    "Poppins": None,
    "Inter": None,
    "Noto Sans": None,
    "Noto Sans Devanagari": None,
    "Hind": None,
}


class VideoSplitter:
    """Handles splitting videos into 30-second reel segments with text overlays."""
    
    REEL_DURATION = 30.0  # seconds
    REEL_RESOLUTION = (1080, 1920)  # 9:16 portrait
    
    def __init__(self, workdir: Path):
        self.workdir = workdir
        self.workdir.mkdir(parents=True, exist_ok=True)
    
    def get_font_path(self, font_name: str) -> Path:
        """Get the full path to a font file.
        
        Args:
            font_name: The display name of the font
            
        Returns:
            Path object pointing to the TTF font file, or the system font name
        """
        font_info = FONT_MAP.get(font_name)
        if not font_info:
            # Unknown font - try as system font name, fallback to bundled
            font_info = "DancingScript.ttf"
        
        if font_info is None:
            # System font - fall back to bundled DancingScript.ttf
            # FFmpeg on Windows needs a .ttf file path
            font_info = "DancingScript.ttf"
        
        # Bundled font - return full path
        font_path = FONTS_DIR / font_info
        if font_path.exists():
            return font_path
        # Fallback: try just the filename in the fonts dir
        fallback = FONTS_DIR / font_info
        if fallback.exists():
            return fallback
        
        # Last resort: return the font info as a path object (may fail if not found)
        return Path(font_info)
    
    def get_video_info(self, video_path: Path) -> Dict:
        """Get video duration, resolution, and other metadata using ffprobe."""
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        
        video_stream = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
        if not video_stream:
            raise ValueError("No video stream found")
        
        duration = float(info["format"].get("duration", 0))
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        
        return {
            "duration": duration,
            "width": width,
            "height": height,
            "fps": eval(video_stream.get("r_frame_rate", "30/1")),
            "codec": video_stream.get("codec_name", "unknown")
        }
    
    def calculate_segments(self, duration: float) -> List[Tuple[float, float]]:
        """Calculate segment start/end times for 30-second reels.
        
        Returns list of (start_time, end_time) tuples.
        Last segment is padded to 30 seconds if needed.
        """
        segments = []
        num_full_segments = int(duration // self.REEL_DURATION)
        
        for i in range(num_full_segments):
            start = i * self.REEL_DURATION
            end = start + self.REEL_DURATION
            segments.append((start, end))
        
        # Handle remaining time
        remaining = duration - (num_full_segments * self.REEL_DURATION)
        if remaining > 0:
            start = num_full_segments * self.REEL_DURATION
            end = duration
            segments.append((start, end))
        
        return segments
    
    def _get_drawtext_filter(
        self,
        movie_name: str,
        part_number: int,
        total_parts: int,
        font_size: int = 48,
        font_color: str = "#FFFFFF",
        outline_color: str = "#000000",
        font_family: str = "Poppins",
        movie_name_position: str = "top",
        part_text_position: str = "bottom"
    ) -> str:
        """Build the drawtext filter string for FFmpeg.
        
        Returns the filter portion that goes after scale/crop in the filter complex.
        Uses FFmpeg's fontfile parameter with actual TTF file paths.
        """
        # Get the font path
        font_path = self.get_font_path(font_family)
        
        # Escape text for FFmpeg
        movie_name_escaped = movie_name.replace(":", "\\:").replace("'", "\\'").replace("%", "\\%")
        part_text = f"Part {part_number} of {total_parts}"
        part_text_escaped = part_text.replace(":", "\\:").replace("'", "\\'").replace("%", "\\%")
        
        # Determine if we're using a full font path or a system font name
        uses_full_path = font_path.suffix == ".ttf"
        
        # Position calculations using FFmpeg w/h expressions
        # These use the video dimensions (1080x1920 after crop)
        margin = 80
        
        # Movie name position
        pos_exprs = {
            "top": "(W-text_w)/2",
            "bottom": "(W-text_w)/2",
            "center": "(W-text_w)/2",
            "top-left": "margin",
            "top-right": "W-text_w-margin",
            "bottom-left": "margin",
            "bottom-right": "W-text_w-margin",
        }
        movie_x = pos_exprs.get(movie_name_position, "(W-text_w)/2")
        movie_y_exprs = {
            "top": margin,
            "bottom": "H-text_h-margin",
            "center": "(H-text_h)/2",
            "top-left": margin,
            "top-right": "H-text_h-margin",
            "bottom-left": "H-text_h-margin",
            "bottom-right": "H-text_h-margin",
        }
        movie_y = movie_y_exprs.get(movie_name_position, "H-text_h-margin")
        
        # Part text position
        part_pos_exprs = {
            "top": "(W-text_w)/2",
            "bottom": "(W-text_w)/2",
            "center": "(W-text_w)/2",
            "top-left": "margin",
            "top-right": "W-text_w-margin",
            "bottom-left": "margin",
            "bottom-right": "W-text_w-margin",
        }
        part_x = part_pos_exprs.get(part_text_position, "(W-text_w)/2")
        part_pos_exprs_y = {
            "top": margin + 60,
            "bottom": "H-text_h-margin",
            "center": "(H-text_h)/2",
            "top-left": margin + 60,
            "top-right": "H-text_h-margin",
            "bottom-left": "H-text_h-margin",
            "bottom-right": "H-text_h-margin",
        }
        part_y = part_pos_exprs_y.get(part_text_position, "H-text_h-margin")
        
# Build the drawtext filter using fontfile (FFmpeg on Windows requires fontfile)
        # Look up font in bundled FONT_MAP, fallback to "Dancing Script"
        font_rel = FONT_MAP.get(font_family)
        if not font_rel or font_rel is None:
            font_rel = "DancingScript.ttf"  # fallback bundled font
        
        # Build absolute path to the font file
        font_path = FONTS_DIR / font_rel
        font_path_str = str(font_path)
        
        # Verify font file exists, fallback if not
        if not Path(font_path_str).exists():
            font_path_str = font_rel
        
        # Escape single quotes in path for FFmpeg filter syntax
        font_path_escaped = font_path_str.replace("'", "\\'")
        
        # Position calculations using FFmpeg w/h expressions
        # These use the video dimensions (1080x1920 after crop)
        margin = 80
        
        # Movie name position
        pos_exprs = {
            "top": "(W-text_w)/2",
            "bottom": "(W-text_w)/2",
            "center": "(W-text_w)/2",
            "top-left": "margin",
            "top-right": "W-text_w-margin",
            "bottom-left": "margin",
            "bottom-right": "W-text_w-margin",
        }
        movie_x = pos_exprs.get(movie_name_position, "(W-text_w)/2")
        movie_y_exprs = {
            "top": margin,
            "bottom": "H-text_h-margin",
            "center": "(H-text_h)/2",
            "top-left": margin,
            "top-right": "H-text_h-margin",
            "bottom-left": "H-text_h-margin",
            "bottom-right": "H-text_h-margin",
        }
        movie_y = movie_y_exprs.get(movie_name_position, "H-text_h-margin")
        
        # Part text position
        part_pos_exprs = {
            "top": "(W-text_w)/2",
            "bottom": "(W-text_w)/2",
            "center": "(W-text_w)/2",
            "top-left": "margin",
            "top-right": "W-text_w-margin",
            "bottom-left": "margin",
            "bottom-right": "W-text_w-margin",
        }
        part_x = part_pos_exprs.get(part_text_position, "(W-text_w)/2")
        part_pos_exprs_y = {
            "top": margin + 60,
            "bottom": "H-text_h-margin",
            "center": "(H-text_h)/2",
            "top-left": margin + 60,
            "top-right": "H-text_h-margin",
            "bottom-left": "H-text_h-margin",
            "bottom-right": "H-text_h-margin",
        }
        part_y = part_pos_exprs_y.get(part_text_position, "H-text_h-margin")
        
        # Build the drawtext filter using fontfile (required for FFmpeg on Windows)
        movie_filter = (
            f"drawtext=text='{movie_name_escaped}':"
            f"fontfile='{font_path_escaped}':"
            f"fontsize={font_size}:"
            f"fontcolor={font_color}:borderw=3:bordercolor={outline_color}:"
            f"x={movie_x}:y={movie_y}"
        )
        
        # Add part number drawtext
        part_filter = (
            f",drawtext=text='{part_text_escaped}':"
            f"fontfile='{font_path_escaped}':"
            f"fontsize={font_size - 8}:"
            f"fontcolor={font_color}:borderw=3:bordercolor={outline_color}:"
            f"x={part_x}:y={part_y}"
        )
        
        # Add part number drawtext
        part_filter = (
            f",drawtext=text='{part_text_escaped}':"
            f"fontfile='{font_path_escaped}':"
            f"fontsize={font_size - 8}:"
            f"fontcolor={font_color}:borderw=3:bordercolor={outline_color}:"
            f"x={part_x}:y={part_y}"
        )
        
        return movie_filter + part_filter
    
    def split_video(
        self,
        input_path: Path,
        movie_name: str,
        output_dir: Path,
        segment_duration: float = 30.0,
        font_size: int = 48,
        font_color: str = "#FFFFFF",
        outline_color: str = "#000000",
        font_family: str = "Poppins",
        movie_name_position: str = "top",
        part_text_position: str = "bottom",
        pad_last_segment: bool = True,
        background_color: str = "black"
    ) -> List[Path]:
        """Split video into reel segments with text overlays.
        
        Args:
            input_path: Path to source video
            movie_name: Name to display on each reel
            output_dir: Directory to save output reels
            segment_duration: Duration of each reel in seconds
            font_size: Font size for text overlays
            font_color: Text color (hex)
            outline_color: Text outline color (hex)
            font_family: Font family name (must be in FONT_MAP or a system font)
            movie_name_position: Position for movie name
            part_text_position: Position for part number
            pad_last_segment: If True, pad last segment to full duration
            background_color: Background color for letterboxing
            
        Returns:
            List of output video paths
        """
        self.REEL_DURATION = segment_duration
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get video info
        info = self.get_video_info(input_path)
        duration = info["duration"]
        
        # Calculate segments
        segments = self.calculate_segments(duration)
        total_parts = len(segments)
        
        output_paths = []
        
        for idx, (start, end) in enumerate(segments):
            part_num = idx + 1
            actual_duration = end - start
            
            # Determine if this is the last segment and needs padding
            is_last = (idx == len(segments) - 1)
            target_duration = self.REEL_DURATION if (is_last and pad_last_segment and actual_duration < self.REEL_DURATION) else actual_duration
            
            output_name = f"{movie_name.replace(' ', '_')}_part{part_num:03d}.mp4"
            output_path = output_dir / output_name
            
            # Build the complete filter complex
            # Filter chain:
            # 1. Trim the segment
            # 2. Scale and crop to 1080x1920 (9:16 portrait)
            # 3. Add text overlays (movie name + part number)
            # 4. If last segment needs padding, loop it
            
            # Step 1: Trim and set PTS
            trim_filter = f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS"
            
            # Step 2: Scale and crop to 9:16 portrait
            scale_crop = f"{trim_filter},scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
            
            # Step 3: Add text overlays
            text_filter = self._get_drawtext_filter(
                movie_name, part_num, total_parts,
                font_size, font_color, outline_color, font_family,
                movie_name_position, part_text_position
            )
            
            # Combine scale+crop with drawtext
            full_vf = f"{scale_crop},{text_filter}"
            
            # Audio filter - trim audio to match
            af_trim = f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS"
            if is_last and pad_last_segment and actual_duration < self.REEL_DURATION:
                af_trim = f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,aloop=loop=-1:size={int(actual_duration * 44100)},atrim=duration={self.REEL_DURATION}"
            
            # Full filter complex with audio
            full_filter = f"{full_vf};{af_trim}[a]"
            
            cmd = [
                "ffmpeg", "-y",
                "-i", str(input_path),
                "-filter_complex", full_filter,
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k",
                "-shortest",
                str(output_path)
            ]
            
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=self.workdir)
                output_paths.append(output_path)
            except subprocess.CalledProcessError as e:
                print(f"Error creating segment {part_num}: {e.stderr}")
                raise
        
        return output_paths
    
    def split_movie_to_reels(
        input_path: Path,
        movie_name: str,
        output_dir: Path,
        workdir: Optional[Path] = None,
        **kwargs
    ) -> List[Path]:
        """Convenience function to split a movie into reels."""
        if workdir is None:
            workdir = Path.cwd() / "temp" / uuid.uuid4().hex[:8]
        
        splitter = VideoSplitter(workdir)
        return splitter.split_video(
            input_path=input_path,
            movie_name=movie_name,
            output_dir=output_dir,
            **kwargs
        )