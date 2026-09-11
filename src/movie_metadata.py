"""Movie metadata fetcher - auto-fetch movie information from various sources."""
import os
import requests
import re
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from urllib.parse import quote_plus


@dataclass
class MovieInfo:
    """Movie metadata container."""
    title: str
    original_title: Optional[str] = None
    year: Optional[int] = None
    overview: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    genres: Optional[list] = None
    runtime: Optional[int] = None
    language: Optional[str] = None
    imdb_id: Optional[str] = None
    tmdb_id: Optional[int] = None
    source: str = "unknown"


class MovieMetadataFetcher:
    """Fetch movie metadata from multiple sources."""
    
    def __init__(self):
        self.tmdb_api_key = os.getenv("TMDB_API_KEY", "")
        self.omdb_api_key = os.getenv("OMDB_API_KEY", "")
        
        # TMDB base URLs
        self.tmdb_base = "https://api.themoviedb.org/3"
        self.tmdb_image_base = "https://image.tmdb.org/t/p/w500"
        self.tmdb_backdrop_base = "https://image.tmdb.org/t/p/w1280"
        
        # OMDB base URL
        self.omdb_base = "http://www.omdbapi.com/"
    
    def search_tmdb(self, query: str, language: str = "en-US") -> Optional[MovieInfo]:
        """Search TMDB for movie."""
        if not self.tmdb_api_key:
            return None
        
        try:
            # Search for movie
            search_url = f"{self.tmdb_base}/search/movie"
            params = {
                "api_key": self.tmdb_api_key,
                "query": query,
                "language": language,
                "include_adult": "false"
            }
            
            response = requests.get(search_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("results"):
                return None
            
            # Get first result
            movie = data["results"][0]
            movie_id = movie["id"]
            
            # Get detailed info
            detail_url = f"{self.tmdb_base}/movie/{movie_id}"
            detail_params = {"api_key": self.tmdb_api_key, "language": language}
            detail_resp = requests.get(detail_url, params=detail_params, timeout=10)
            detail_resp.raise_for_status()
            detail = detail_resp.json()
            
            return MovieInfo(
                title=detail.get("title", ""),
                original_title=detail.get("original_title"),
                year=int(detail.get("release_date", "0000")[:4]) if detail.get("release_date") else None,
                overview=detail.get("overview"),
                poster_url=f"{self.tmdb_image_base}{detail['poster_path']}" if detail.get("poster_path") else None,
                backdrop_url=f"{self.tmdb_backdrop_base}{detail['backdrop_path']}" if detail.get("backdrop_path") else None,
                genres=[g["name"] for g in detail.get("genres", [])],
                runtime=detail.get("runtime"),
                language=detail.get("original_language"),
                imdb_id=detail.get("imdb_id"),
                tmdb_id=detail.get("id"),
                source="tmdb"
            )
        except Exception as e:
            print(f"TMDB search error: {e}")
            return None
    
    def search_omdb(self, query: str) -> Optional[MovieInfo]:
        """Search OMDB for movie."""
        if not self.omdb_api_key:
            return None
        
        try:
            params = {
                "apikey": self.omdb_api_key,
                "t": query,
                "plot": "full"
            }
            
            response = requests.get(self.omdb_base, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("Response") == "False":
                return None
            
            # Parse year
            year = None
            if data.get("Year"):
                year_match = re.search(r"\d{4}", data["Year"])
                if year_match:
                    year = int(year_match.group())
            
            # Parse runtime
            runtime = None
            if data.get("Runtime"):
                runtime_match = re.search(r"\d+", data["Runtime"])
                if runtime_match:
                    runtime = int(runtime_match.group())
            
            return MovieInfo(
                title=data.get("Title", ""),
                year=year,
                overview=data.get("Plot"),
                poster_url=data.get("Poster") if data.get("Poster") != "N/A" else None,
                genres=data.get("Genre", "").split(", ") if data.get("Genre") else None,
                runtime=runtime,
                language=data.get("Language"),
                imdb_id=data.get("imdbID"),
                source="omdb"
            )
        except Exception as e:
            print(f"OMDB search error: {e}")
            return None
    
    def extract_title_from_filename(self, filename: str) -> str:
        """Extract movie title from filename using common patterns."""
        # Remove extension
        name = Path(filename).stem
        
        # Common patterns to remove
        patterns = [
            r'\[.*?\]',  # [tags]
            r'\(.*?\)',  # (year) or (tags)
            r'\b(1080p|720p|480p|4k|2160p|bluray|webrip|web-dl|hdtv|dvdrip|bdrip)\b',
            r'\b(x264|x265|h264|h265|hevc|avc)\b',
            r'\b(aac|ac3|dts|mp3|flac)\b',
            r'\b(5\.1|7\.1|2\.0)\b',
            r'\b(hindi|english|eng|hin|tam|tel|mal|kan)\b',
            r'\b(official|trailer|teaser|full|movie|film)\b',
            r'[-_.]+',  # separators
        ]
        
        for pattern in patterns:
            name = re.sub(pattern, ' ', name, flags=re.IGNORECASE)
        
        # Clean up extra spaces
        name = re.sub(r'\s+', ' ', name).strip()
        
        # Try to extract year and remove it
        year_match = re.search(r'\b(19|20)\d{2}\b', name)
        if year_match:
            name = name[:year_match.start()].strip()
        
        return name.strip()
    
    def fetch_movie_info(self, query: str, language: str = "en-US") -> Optional[MovieInfo]:
        """Fetch movie info trying multiple sources."""
        # Try TMDB first (better for international movies)
        if self.tmdb_api_key:
            result = self.search_tmdb(query, language)
            if result:
                return result
        
        # Try OMDB
        if self.omdb_api_key:
            result = self.search_omdb(query)
            if result:
                return result
        
        # Return basic info from filename
        title = self.extract_title_from_filename(query)
        return MovieInfo(
            title=title,
            source="filename"
        )
    
    def fetch_by_imdb(self, imdb_id: str) -> Optional[MovieInfo]:
        """Fetch movie by IMDB ID."""
        # Try TMDB with IMDB ID
        if self.tmdb_api_key:
            try:
                url = f"{self.tmdb_base}/find/{imdb_id}"
                params = {
                    "api_key": self.tmdb_api_key,
                    "external_source": "imdb_id"
                }
                resp = requests.get(url, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                
                if data.get("movie_results"):
                    movie_id = data["movie_results"][0]["id"]
                    return self.search_tmdb(str(movie_id))
            except Exception:
                pass
        
        # Try OMDB
        if self.omdb_api_key:
            try:
                params = {"apikey": self.omdb_api_key, "i": imdb_id, "plot": "full"}
                resp = requests.get(self.omdb_base, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                
                if data.get("Response") == "True":
                    return self.search_omdb(data["Title"])
            except Exception:
                pass
        
        return None


def get_movie_metadata(query: str, language: str = "en-US") -> Optional[MovieInfo]:
    """Convenience function to fetch movie metadata."""
    fetcher = MovieMetadataFetcher()
    return fetcher.fetch_movie_info(query, language)