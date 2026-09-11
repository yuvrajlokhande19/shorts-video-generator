"""Movie-to-Reels Splitter: Split long videos into 30-second portrait reels with text overlays."""
import subprocess
import json
import math
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import uuid


class VideoSplitter:
    """Handles splitting videos into 30-second reel segments with text overlays."""
    
    REEL_DURATION = 30.0  # seconds
    REEL_RESOLUTION = (1080, 1920)  # 9:16 portrait
    
    def __init__(self, workdir: Path):
        self.workdir = workdir
        self.workdir.mkdir(parents=True, exist_ok=True)
    
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
    
    def build_text_overlay_filter(
        self,
        movie_name: str,
        part_number: int,
        total_parts: int,
        position: str = "bottom",
        font_size: int = 48,
        font_color: str = "#FFFFFF",
        outline_color: str = "#000000",
        font_family: str = "Arial",
        movie_name_position: str = "top",
        part_text_position: str = "bottom"
    ) -> str:
        """Build FFmpeg drawtext filter for movie name and part number.
        
        Position options: top, bottom, center, top-left, top-right, bottom-left, bottom-right
        """
        w, h = self.REEL_RESOLUTION
        
        # Calculate positions based on preference
        def get_position_coords(pos: str, text_h: int = 100) -> Tuple[str, str]:
            margin = 80
            if pos == "top":
                return f"(w-text_w)/2", f"{margin}"
            elif pos == "bottom":
                return f"(w-text_w)/2", f"h-text_h-{margin}"
            elif pos == "center":
                return f"(w-text_w)/2", f"(h-text_h)/2"
            elif pos == "top-left":
                return f"{margin}", f"{margin}"
            elif pos == "top-right":
                return f"w-text_w-{margin}", f"{margin}"
            elif pos == "bottom-left":
                return f"{margin}", f"h-text_h-{margin}"
            elif pos == "bottom-right":
                return f"w-text_w-{margin}", f"h-text_h-{margin}"
            else:
                return f"(w-text_w)/2", f"h-text_h-{margin}"
        
        movie_x, movie_y = get_position_coords(movie_name_position)
        part_x, part_y = get_position_coords(part_text_position)
        
        # Escape text for FFmpeg
        movie_name_escaped = movie_name.replace(":", "\\:").replace("'", "\\'").replace("%", "\\%")
        part_text = f"Part {part_number} of {total_parts}"
        part_text_escaped = part_text.replace(":", "\\:").replace("'", "\\'").replace("%", "\\%")
        
        # Build drawtext filters
        movie_filter = (
            f"drawtext=text='{movie_name_escaped}':"
            f"fontfile={font_family}:fontsize={font_size}:"
            f"fontcolor={font_color}:borderw=3:bordercolor={outline_color}:"
            f"x={movie_x}:y={movie_y}"
        )
        
        part_filter = (
            f"drawtext=text='{part_text_escaped}':"
            f"fontfile={font_family}:fontsize={font_size - 8}:"
            f"fontcolor={font_color}:borderw=3:bordercolor={outline_color}:"
            f"x={part_x}:y={part_y}"
        )
        
        return f"[0:v]{movie_filter},{part_filter}[v]"
    
    def split_video(
        self,
        input_path: Path,
        movie_name: str,
        output_dir: Path,
        segment_duration: float = 30.0,
        font_size: int = 48,
        font_color: str = "#FFFFFF",
        outline_color: str = "#000000",
        font_family: str = "Arial",
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
            font_family: Font family name
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
            
            # Build filter complex
            # 1. Trim the segment
            # 2. Scale and crop to 9:16 portrait
            # 3. Add text overlays
            # 4. Pad last segment if needed
            
            filter_parts = []
            
            # Video filter chain
            # Scale to cover 1080x1920 maintaining aspect ratio, then crop center
            vf_scale = (
                f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS,"
                f"scale=1080:1920:force_original_aspect_ratio=increase,"
                f"crop=1080:1920"
            )
            
            # Add text overlays
            text_filter = self.build_text_overlay_filter(
                movie_name, part_num, total_parts,
                font_size=font_size,
                font_color=font_color,
                outline_color=outline_color,
                font_family=font_family,
                movie_name_position=movie_name_position,
                part_text_position=part_text_position
            )
            
            # Combine filters
            filter_complex = f"{vf_scale}{text_filter}"
            
            # If padding last segment
            if is_last and pad_last_segment and actual_duration < self.REEL_DURATION:
                # Loop the last segment to fill remaining time
                filter_complex = (
                    f"{vf_scale},"
                    f"loop=loop=-1:size={int(actual_duration * 30)}:start=0,"
                    f"trim=duration={self.REEL_DURATION},"
                    f"setpts=PTS-STARTPTS,"
                    f"{text_filter.replace('[0:v]', '[0:v]')}"
                )
            
            # Audio filter - trim audio to match
            af_trim = f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS"
            if is_last and pad_last_segment and actual_duration < self.REEL_DURATION:
                af_trim = f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,aloop=loop=-1:size={int(actual_duration * 44100)},atrim=duration={self.REEL_DURATION}"
            
            # Full filter complex
            full_filter = f"{filter_complex};{af_trim}[a]"
            
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